"""Envoi courriel de l'API ARPAGONA.

Un seul canal sortant. L'agent ne l'atteint jamais : seul le serveur, après approbation
explicite d'un brouillon et recalcul de son empreinte, peut appeler ``Mailer.send``.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


class MailError(Exception):
    """Échec d'envoi lisible par l'utilisateur, sans fuite de secret."""


class Mailer:
    def __init__(self, host: str, port: int = 587, user: str = "", password: str = "",
                 sender: str = "", starttls: bool = True, timeout_s: float = 15.0):
        self.host = host
        self.port = int(port)
        self.user = user
        self._password = password
        self.sender = sender or user
        self.starttls = starttls
        self.timeout = timeout_s

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Mailer | None":
        env = os.environ if env is None else env
        host = (env.get("ARPAGONA_SMTP_HOST") or "").strip()
        if not host:
            return None
        password = env.get("ARPAGONA_SMTP_PASSWORD") or ""
        pw_file = (env.get("ARPAGONA_SMTP_PASSWORD_FILE") or "").strip()
        if not password and pw_file and Path(pw_file).is_file():
            password = Path(pw_file).read_text(encoding="utf-8").strip()
        try:
            port = int(env.get("ARPAGONA_SMTP_PORT") or 587)
        except ValueError:
            port = 587
        return cls(host, port, env.get("ARPAGONA_SMTP_USER", ""), password,
                   env.get("ARPAGONA_SMTP_FROM", "") or env.get("ARPAGONA_SMTP_USER", ""),
                   (env.get("ARPAGONA_SMTP_STARTTLS", "1") != "0"))

    def __repr__(self) -> str:  # ne jamais afficher le mot de passe
        return f"Mailer(host={self.host!r}, port={self.port}, sender={self.sender!r})"

    def send(self, to: str, subject: str, body: str) -> str:
        to = (to or "").strip()
        subject = (subject or "").strip()
        if not to or "@" not in to or any(ch in to for ch in "\r\n"):
            raise MailError("destinataire invalide")
        if any(ch in subject for ch in "\r\n"):
            raise MailError("objet invalide")
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject or "Message ARPAGONA"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="arpagona.com")
        msg.set_content(body or "")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                if self.starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if self.user:
                    smtp.login(self.user, self._password)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            raise MailError(f"courriel non remis ({type(exc).__name__})") from exc
        return str(msg["Message-ID"])
