"""Portier Hindsight : deux zones de mémoire, imposées hors de l'interface.

Hindsight n'a qu'une clé pour toutes ses banques. Ce portier tient cette clé ; chaque utilisateur
reçoit un jeton PROPRE qui ne donne accès qu'à DEUX banques :
  - sa banque PERSONNELLE (lecture et écriture complètes) ;
  - la banque d'ÉQUIPE de l'entreprise (mémoire métier commune), en lecture et en dépôt de faits
    seulement : jamais de suppression, jamais de changement de configuration, et chaque fait déposé
    porte l'auteur imposé par le portier (balise ``auteur:<nom>``), pas celui que l'appelant déclare.
Le portier refuse de verser dans la banque d'équipe un message électronique entier ou un secret.
Il écoute en boucle locale, un port par utilisateur ; il ne laisse passer que /health et les chemins
/v1/default/banks/<banque personnelle ou banque d'équipe>/...

Configuration (JSON, root:hindsight-gate 0640) :
  {"upstream": "http://127.0.0.1:18897", "upstream_key_file": "/etc/hindsight-gate/upstream_key",
   "team_bank": "arpagona-equipe",
   "tenants": [{"name": "mael", "bank": "arpagona-mael", "port": 18911,
                "token_sha256": "<hex>"}]}
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BANK_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "upgrade", "proxy-authorization",
              "host", "content-length", "authorization"}
MAX_BODY = 8 * 1024 * 1024
MAX_TEAM_ITEMS = 20
MAX_TEAM_CONTENT = 2000
MAIL_HEADER_RE = re.compile(r"(?im)^(from|to|cc|subject|message-id|date|received|return-path):")
SECRET_RE = re.compile(r"(?i)(api[_ -]?key|secret|passw|mot de passe|\btoken\b|bearer\s+\S|-----BEGIN|\bsk-[a-z0-9]{8,})")


def allowed_path(raw_path: str, bank: str) -> bool:
    """Vrai seulement pour /health ou pour le sous-arbre de la banque de l'utilisateur."""
    path = urllib.parse.urlsplit(raw_path).path
    if "%" in path or "\\" in path or "//" in path or ".." in path.split("/") or "\x00" in path:
        return False  # aucun encodage, aucune échappée : on refuse plutôt que de normaliser
    if path in ("/health", "/version"):
        return True
    prefix = f"/v1/default/banks/{bank}"
    return path == prefix or path.startswith(prefix + "/")


def team_allowed(method: str, raw_path: str, team_bank: str) -> bool:
    """Banque d'équipe : lecture, rappel et dépôt de faits. Ni suppression, ni configuration, ni synthèse."""
    if not allowed_path(raw_path, team_bank):
        return False
    path = urllib.parse.urlsplit(raw_path).path
    prefix = f"/v1/default/banks/{team_bank}"
    if method == "GET":
        return True
    if method == "POST":
        return path in (prefix + "/memories", prefix + "/memories/recall")
    return False


def team_refusal(item: dict) -> str | None:
    """Raison du refus d'un fait destiné à l'équipe, ou None. Aucun mail entier, aucun secret."""
    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        return "fait vide"
    if len(content) > MAX_TEAM_CONTENT:
        return "fait trop long : un fait d'équipe est une phrase ou un court paragraphe, pas un document"
    if len(MAIL_HEADER_RE.findall(content)) >= 2:
        return "un message électronique entier ne se verse pas dans la mémoire d'équipe"
    if SECRET_RE.search(content) or SECRET_RE.search(json.dumps(item.get("context", ""))):
        return "secret ou identifiant détecté : refusé"
    return None


def stamp_team_retain(body: bytes, author: str) -> tuple[bytes | None, str]:
    """Impose l'auteur et la zone sur un dépôt dans la banque d'équipe ; refuse sinon (corps ou message)."""
    try:
        data = json.loads(body or b"{}")
        items = data["items"]
    except (ValueError, KeyError, TypeError):
        return None, "corps invalide"
    if not isinstance(items, list) or not 0 < len(items) <= MAX_TEAM_ITEMS:
        return None, "nombre de faits invalide"
    for item in items:
        if not isinstance(item, dict):
            return None, "fait invalide"
        reason = team_refusal(item)
        if reason:
            return None, reason
        tags = [t for t in item.get("tags", []) if isinstance(t, str) and not t.startswith(("auteur:", "zone:"))]
        item["tags"] = tags + [f"auteur:{author}", "zone:equipe"]
        meta = {str(k): str(v) for k, v in (item.get("metadata") or {}).items() if k not in ("auteur", "zone")}
        meta.setdefault("source", f"agent:{author}")
        meta["auteur"], meta["zone"] = author, "equipe"
        item["metadata"] = meta
    return json.dumps(data, ensure_ascii=False).encode("utf-8"), ""


class Tenant:
    def __init__(self, name: str, bank: str, token_sha256: str, team_bank: str | None = None):
        if not BANK_RE.match(bank) or (team_bank is not None and not BANK_RE.match(team_bank)):
            raise ValueError("nom de banque invalide")
        if team_bank is not None and team_bank == bank:
            raise ValueError("la banque d'équipe ne peut pas être une banque personnelle")
        self.name, self.bank, self.token_sha256 = name, bank, token_sha256.lower()
        self.team_bank = team_bank

    def accepts(self, header: str) -> bool:
        if not header.startswith("Bearer "):
            return False
        digest = hashlib.sha256(header[7:].encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, self.token_sha256)


def make_handler(tenant: Tenant, upstream: str, upstream_key: str):
    host, _, port = upstream.removeprefix("http://").partition(":")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            return

        def _deny(self, status: int, message: str) -> None:
            body = json.dumps({"error": message}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def _forward(self) -> None:
            if not tenant.accepts(self.headers.get("Authorization", "")):
                return self._deny(401, "jeton refusé")
            team = bool(tenant.team_bank) and allowed_path(self.path, tenant.team_bank) \
                and not allowed_path(self.path, tenant.bank)
            if team:
                if not team_allowed(self.command, self.path, tenant.team_bank):
                    return self._deny(403, "banque d'équipe : lecture, rappel et dépôt seulement")
            elif not allowed_path(self.path, tenant.bank):
                return self._deny(403, "banque non autorisée")
            length = int(self.headers.get("Content-Length") or 0)
            if length < 0 or length > MAX_BODY:
                return self._deny(413, "corps trop grand")
            body = self.rfile.read(length) if length else None
            if team and self.command == "POST" and urllib.parse.urlsplit(self.path).path.endswith("/memories"):
                body, reason = stamp_team_retain(body or b"", tenant.name)
                if body is None:
                    return self._deny(422, reason)
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            headers["Authorization"] = f"Bearer {upstream_key}"
            conn = http.client.HTTPConnection(host, int(port or 80), timeout=300)
            try:
                conn.request(self.command, self.path, body, headers)
                resp = conn.getresponse()
                data = resp.read()
            except OSError:
                return self._deny(502, "Hindsight injoignable")
            finally:
                conn.close()
            self.send_response(resp.status)
            for key, value in resp.getheaders():
                if key.lower() not in HOP_BY_HOP and key.lower() not in ("date", "server"):
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _forward

    return Handler


def serve(config_path: str) -> None:
    conf = json.loads(Path(config_path).read_text(encoding="utf-8"))
    key = Path(conf["upstream_key_file"]).read_text(encoding="ascii").strip()
    for entry in conf["tenants"]:
        tenant = Tenant(entry["name"], entry["bank"], entry["token_sha256"], conf.get("team_bank"))
        server = ThreadingHTTPServer(("127.0.0.1", int(entry["port"])), make_handler(tenant, conf["upstream"], key))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()


if __name__ == "__main__":
    serve(sys.argv[1])
