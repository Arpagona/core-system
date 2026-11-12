"""Plugin arpagona-core : outils d'engagement pour l'agent, sans accès d'envoi.

Les outils écrivent dans l'API ARPAGONA (boucle locale), qui rattache l'appel à
l'utilisateur par l'identifiant de session Hermès. Aucun outil de ce plugin
n'envoie de message : un brouillon ne peut être envoyé que par l'API, après
validation humaine.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = os.environ.get("ARPAGONA_API_URL", "http://127.0.0.1:8700")
TOKEN_FILE = os.environ.get("ARPAGONA_SERVICE_TOKEN_FILE", "/etc/arpagona-api/service_token")


def _token() -> str:
    value = os.environ.get("ARPAGONA_SERVICE_TOKEN", "").strip()
    if value:
        return value
    try:
        return Path(TOKEN_FILE).read_text(encoding="ascii").strip()
    except OSError:
        return ""


def _call(method: str, path: str, payload: dict | None, session_id: str) -> str:
    """Appelle l'API ARPAGONA. Toute erreur revient en JSON, jamais en exception."""
    token = _token()
    if not token:
        return json.dumps({"error": "service ARPAGONA non configuré (jeton absent)"})
    if not session_id:
        return json.dumps({"error": "session inconnue : impossible de rattacher l'action à un utilisateur"})
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(API_URL.rstrip("/") + path, data=data, method=method)
    req.add_header("X-Arpagona-Service", token)
    req.add_header("X-Hermes-Session", session_id)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        try:
            return exc.read().decode("utf-8")
        except OSError:
            return json.dumps({"error": f"API ARPAGONA : HTTP {exc.code}"})
    except (urllib.error.URLError, OSError):
        return json.dumps({"error": "API ARPAGONA injoignable"})


def record(args: dict, session_id: str = "", **_kw) -> str:
    payload = {
        "client": args.get("client", ""),
        "sujet": args.get("sujet", ""),
        "decision": args.get("decision", ""),
        "echeance": args.get("echeance", ""),
        "certitude": args.get("certitude", "a_confirmer"),
        "source": args.get("source", ""),
    }
    return _call("POST", "/internal/engagements", payload, session_id)


def listing(args: dict, session_id: str = "", **_kw) -> str:
    return _call("GET", "/internal/engagements", None, session_id)


def draft(args: dict, session_id: str = "", **_kw) -> str:
    payload = {
        "engagement_id": args.get("engagement_id", 0),
        "cible": args.get("cible", ""),
        "corps": args.get("corps", ""),
    }
    return _call("POST", "/internal/drafts", payload, session_id)


RECORD_SCHEMA = {
    "name": "arpagona_engagement_record",
    "description": (
        "Consigne un engagement pris avec un client : qui, quel sujet, quelle décision, quelle échéance. "
        "N'appelle cet outil que lorsque l'utilisateur a énoncé la décision et la date. La date doit être "
        "absolue et accompagnée de son fuseau (ex. 2026-11-13T09:00:00+01:00) ; si elle est ambiguë, "
        "demande-la d'abord à l'utilisateur au lieu d'inventer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "client": {"type": "string", "description": "Nom du client ou du tiers concerné"},
            "sujet": {"type": "string", "description": "Objet de l'engagement (devis, relance, réunion…)"},
            "decision": {"type": "string", "description": "Ce qui a été décidé, en une phrase"},
            "echeance": {"type": "string", "description": "Échéance ISO 8601 avec fuseau, ex. 2026-11-13T09:00:00+01:00"},
            "certitude": {"type": "string", "enum": ["certain", "probable", "a_confirmer"]},
            "source": {"type": "string", "description": "Citation courte de l'échange d'origine"},
        },
        "required": ["client", "sujet", "decision", "echeance", "certitude"],
    },
}

LIST_SCHEMA = {
    "name": "arpagona_engagement_list",
    "description": "Liste les engagements enregistrés de cet utilisateur, avec échéance et statut.",
    "parameters": {"type": "object", "properties": {}},
}

DRAFT_SCHEMA = {
    "name": "arpagona_draft_create",
    "description": (
        "Dépose un brouillon de message pour un engagement. Le brouillon part en attente de validation "
        "humaine : il n'est jamais envoyé par cet outil."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "engagement_id": {"type": "integer", "description": "Identifiant de l'engagement concerné"},
            "cible": {"type": "string", "description": "Destinataire exact (nom, adresse ou canal)"},
            "corps": {"type": "string", "description": "Corps du message, prêt à relire"},
        },
        "required": ["engagement_id", "cible", "corps"],
    },
}


def register(ctx) -> None:
    ctx.register_tool(name="arpagona_engagement_record", toolset="arpagona", schema=RECORD_SCHEMA,
                      handler=record, description="Consigne un engagement client")
    ctx.register_tool(name="arpagona_engagement_list", toolset="arpagona", schema=LIST_SCHEMA,
                      handler=listing, description="Liste les engagements")
    ctx.register_tool(name="arpagona_draft_create", toolset="arpagona", schema=DRAFT_SCHEMA,
                      handler=draft, description="Dépose un brouillon à valider")
