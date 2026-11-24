"""Plugin arpagona-mail : agent de messagerie PERSONNEL, sur une boîte fictive au format Maildir.

La boîte est celle du compte Unix qui fait tourner l'instance Hermès (ARPAGONA_MAIL_DIR, 0700).
Le plugin ne connaît aucune autre boîte, n'a aucun outil d'envoi et refuse tout identifiant qui
sortirait du dossier. Les permissions Unix font l'isolation ; ce code n'ajoute qu'une défense en plus.

Disposition : <MAIL_DIR>/INBOX/{new,cur}/<id>  et  <MAIL_DIR>/Drafts/cur/<id>  (un message RFC 822 par fichier).
"""
from __future__ import annotations

import email
import email.policy
import json
import os
import re
import secrets
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
ADDR_RE = re.compile(r"^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$")
MAX_BODY = 20000


class MailError(Exception):
    pass


def _root() -> Path:
    raw = os.environ.get("ARPAGONA_MAIL_DIR", "").strip()
    if not raw:
        raise MailError("boîte non configurée (ARPAGONA_MAIL_DIR absent)")
    return Path(raw)


def _owner() -> str:
    return os.environ.get("ARPAGONA_MAIL_ADDRESS", "").strip()


def _folder_files(folder: str) -> list[Path]:
    root = _root() / folder
    files = []
    for sub in ("new", "cur"):
        directory = root / sub
        if directory.is_dir():
            files.extend(p for p in directory.iterdir() if p.is_file())
    return sorted(files, key=lambda p: p.name)


def _parse(path: Path):
    return email.message_from_bytes(path.read_bytes(), policy=email.policy.default)


def _body(msg) -> str:
    part = msg.get_body(preferencelist=("plain",))
    text = part.get_content() if part else ""
    return text[:MAX_BODY]


def inbox(args: dict, **_kw) -> str:
    try:
        rows = []
        for path in _folder_files("INBOX"):
            msg = _parse(path)
            rows.append({"id": path.name, "de": str(msg["From"] or ""), "sujet": str(msg["Subject"] or ""),
                         "date": str(msg["Date"] or "")})
        return json.dumps({"boite": _owner(), "messages": rows}, ensure_ascii=False)
    except (MailError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def read(args: dict, **_kw) -> str:
    ident = str(args.get("id", ""))
    if not ID_RE.match(ident) or ident in (".", ".."):
        return json.dumps({"error": "identifiant invalide"})
    try:
        for folder in ("INBOX", "Drafts"):
            for path in _folder_files(folder):
                if path.name == ident:
                    msg = _parse(path)
                    return json.dumps({"id": ident, "dossier": folder, "de": str(msg["From"] or ""),
                                       "a": str(msg["To"] or ""), "sujet": str(msg["Subject"] or ""),
                                       "corps": _body(msg)}, ensure_ascii=False)
        return json.dumps({"error": "message inconnu"})
    except (MailError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def draft(args: dict, **_kw) -> str:
    to = str(args.get("a", "")).strip()
    subject = str(args.get("sujet", "")).strip()
    body = str(args.get("corps", "")).strip()
    if not ADDR_RE.match(to) or "\n" in subject or "\r" in subject or not subject or not body or len(body) > MAX_BODY:
        return json.dumps({"error": "destinataire, sujet ou corps invalide"})
    try:
        directory = _root() / "Drafts" / "cur"
        directory.mkdir(parents=True, exist_ok=True)
        msg = EmailMessage()
        msg["From"] = _owner() or "boite@banc.invalid"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain="banc.invalid")
        msg["X-Arpagona-Statut"] = "brouillon-non-envoye"
        msg.set_content(body)
        name = f"{int(time.time())}.{secrets.token_hex(6)}.draft"
        tmp = directory / (name + ".tmp")
        tmp.write_bytes(msg.as_bytes())
        os.chmod(tmp, 0o600)
        os.replace(tmp, directory / name)
        return json.dumps({"id": name, "dossier": "Drafts", "statut": "brouillon-non-envoye"})
    except (MailError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


INBOX_SCHEMA = {"name": "arpagona_mail_inbox",
                "description": "Liste les messages de TA boîte de réception (boîte fictive du banc).",
                "parameters": {"type": "object", "properties": {}}}
READ_SCHEMA = {"name": "arpagona_mail_read",
               "description": "Lit un message de ta boîte (réception ou brouillons) par son identifiant.",
               "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}}
DRAFT_SCHEMA = {"name": "arpagona_mail_draft",
                "description": ("Dépose un brouillon dans le dossier Brouillons de TA boîte. Rien n'est envoyé : "
                                "aucun outil d'envoi n'existe."),
                "parameters": {"type": "object", "properties": {
                    "a": {"type": "string", "description": "Adresse du destinataire"},
                    "sujet": {"type": "string"}, "corps": {"type": "string"}},
                    "required": ["a", "sujet", "corps"]}}


def register(ctx) -> None:
    ctx.register_tool(name="arpagona_mail_inbox", toolset="arpagona", schema=INBOX_SCHEMA, handler=inbox,
                      description="Liste la boîte de réception personnelle")
    ctx.register_tool(name="arpagona_mail_read", toolset="arpagona", schema=READ_SCHEMA, handler=read,
                      description="Lit un message de la boîte personnelle")
    ctx.register_tool(name="arpagona_mail_draft", toolset="arpagona", schema=DRAFT_SCHEMA, handler=draft,
                      description="Dépose un brouillon dans la boîte personnelle")
