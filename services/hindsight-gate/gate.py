"""Portier Hindsight : une banque de mémoire par utilisateur, imposée hors de l'interface.

Hindsight n'a qu'une clé pour toutes ses banques. Ce portier tient cette clé ; chaque utilisateur
reçoit un jeton PROPRE qui ne donne accès qu'à SA banque. Il écoute en boucle locale, un port par
utilisateur, et ne laisse passer que /health et /v1/default/banks/<banque de l'utilisateur>/...

Configuration (JSON, root:hindsight-gate 0640) :
  {"upstream": "http://127.0.0.1:18897", "upstream_key_file": "/etc/hindsight-gate/upstream_key",
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


def allowed_path(raw_path: str, bank: str) -> bool:
    """Vrai seulement pour /health ou pour le sous-arbre de la banque de l'utilisateur."""
    path = urllib.parse.urlsplit(raw_path).path
    if "%" in path or "\\" in path or "//" in path or ".." in path.split("/") or "\x00" in path:
        return False  # aucun encodage, aucune échappée : on refuse plutôt que de normaliser
    if path in ("/health", "/version"):
        return True
    prefix = f"/v1/default/banks/{bank}"
    return path == prefix or path.startswith(prefix + "/")


class Tenant:
    def __init__(self, name: str, bank: str, token_sha256: str):
        if not BANK_RE.match(bank):
            raise ValueError("nom de banque invalide")
        self.name, self.bank, self.token_sha256 = name, bank, token_sha256.lower()

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
            if not allowed_path(self.path, tenant.bank):
                return self._deny(403, "banque non autorisée")
            length = int(self.headers.get("Content-Length") or 0)
            if length < 0 or length > MAX_BODY:
                return self._deny(413, "corps trop grand")
            body = self.rfile.read(length) if length else None
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
        tenant = Tenant(entry["name"], entry["bank"], entry["token_sha256"])
        server = ThreadingHTTPServer(("127.0.0.1", int(entry["port"])), make_handler(tenant, conf["upstream"], key))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()


if __name__ == "__main__":
    serve(sys.argv[1])
