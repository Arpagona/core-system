"""Engagements : validation des champs, empreinte de brouillon et échéances."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

CONFIDENCES = ("certain", "probable", "a_confirmer")


class InvalidEngagement(ValueError):
    pass


def parse_due(value: str) -> tuple[float, str, str]:
    """Lit une échéance ISO 8601 avec fuseau. Refuse toute date sans fuseau : l'ambiguïté se règle dans la conversation."""
    text = (value or "").strip()
    if not text:
        raise InvalidEngagement("échéance absente")
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidEngagement("échéance illisible : format attendu AAAA-MM-JJTHH:MM:SS+HH:MM") from exc
    if moment.tzinfo is None:
        raise InvalidEngagement("échéance sans fuseau horaire : demander la date absolue à l'utilisateur")
    return moment.timestamp(), moment.strftime("%z"), text


def fingerprint(target: str, body: str) -> str:
    return hashlib.sha256((target.strip() + "\n" + body.strip()).encode("utf-8")).hexdigest()


def mail_fingerprint(target: str, subject: str, body: str, sender: str) -> str:
    """Version 2 : message exact, champs séparés sans ambiguïté, aucun strip implicite."""
    payload = json.dumps(["arpagona-mail-v2", sender, target, subject, body],
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_fields(client: str, subject: str, decision: str, confidence: str) -> tuple[str, str, str, str]:
    fields = {"client": client, "sujet": subject, "décision": decision}
    for label, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise InvalidEngagement(f"{label} manquant")
        if len(value) > 500:
            raise InvalidEngagement(f"{label} trop long")
    if confidence not in CONFIDENCES:
        raise InvalidEngagement("niveau de certitude parmi : " + ", ".join(CONFIDENCES))
    return client.strip(), subject.strip(), decision.strip(), confidence
