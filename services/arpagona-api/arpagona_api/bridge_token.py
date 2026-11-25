"""Jeton « pont » : prouve à un second Mission Control qu'Atlas a authentifié `login`.

Format : base64url(login|expiration) . hex(HMAC-SHA256(clé, login|expiration)).
Pas de base partagée, pas d'appel réseau : le vérificateur n'a besoin que de la clé.
Les cookies d'un hôte sont partagés entre ports ; ce jeton circule donc sur 10.68.100.1:8700 et :8710.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

COOKIE = "gona_bridge"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(key: bytes, login: str, ttl_s: int, now: float | None = None) -> str:
    if len(key) < 32:
        raise ValueError("clé trop courte")
    if "|" in login or not login:
        raise ValueError("login invalide")
    payload = f"{login}|{int((now if now is not None else time.time()) + ttl_s)}".encode("utf-8")
    sig = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return f"{_b64(payload)}.{sig}"


def verify(key: bytes, token: str, allowed: set[str], now: float | None = None) -> str | None:
    """Renvoie le login si le jeton est authentique, non expiré et autorisé ; sinon None."""
    try:
        body, sig = token.split(".", 1)
        payload = _unb64(body)
        expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        login, exp = payload.decode("utf-8").rsplit("|", 1)
        if int(exp) <= (now if now is not None else time.time()):
            return None
    except (ValueError, UnicodeDecodeError):
        return None
    return login if login in allowed else None
