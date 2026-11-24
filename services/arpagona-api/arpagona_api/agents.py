"""Registre des agents personnels : un moteur, une passerelle Kanban et un jeton d'outils PAR utilisateur.

Le registre est un fichier JSON lu au démarrage (root:arpagona-api, 0640) :

    {"agents": {"mael": {"hermes_url": "http://127.0.0.1:8652", "hermes_key_file": "...",
                          "kanban_url": "http://127.0.0.1:8702", "kanban_token_file": "...",
                          "service_token_file": "..."}}}

Règle : quand un registre est chargé, un compte SANS entrée n'a PAS d'agent (refus net, jamais de
repli sur un moteur commun). Un jeton d'outils n'est valable que pour la session de son propriétaire.
"""
from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from pathlib import Path

from .hermes import HermesClient
from .kanban import KanbanClient


@dataclass(frozen=True)
class AgentProfile:
    login: str
    hermes: HermesClient
    kanban: KanbanClient
    service_token: str


def _secret(path: str) -> str:
    value = Path(path).read_text(encoding="ascii").strip()
    if not value:
        raise ValueError(f"secret vide : {path}")
    return value


class AgentRegistry:
    def __init__(self, profiles: dict[str, AgentProfile]):
        tokens = [p.service_token for p in profiles.values()]
        if len(set(tokens)) != len(tokens):
            raise ValueError("deux agents partagent le même jeton d'outils")
        self._profiles = dict(profiles)

    @classmethod
    def load(cls, path: str | Path) -> "AgentRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        profiles = {}
        for login, entry in raw["agents"].items():
            profiles[login] = AgentProfile(
                login=login,
                hermes=HermesClient(entry["hermes_url"], _secret(entry["hermes_key_file"])),
                kanban=KanbanClient(_secret(entry["kanban_token_file"]), entry["kanban_url"]),
                service_token=_secret(entry["service_token_file"]),
            )
        return cls(profiles)

    def logins(self) -> list[str]:
        return sorted(self._profiles)

    def for_login(self, login: str) -> AgentProfile | None:
        return self._profiles.get(login)

    def owner_of_token(self, token: str) -> str | None:
        """Propriétaire d'un jeton d'outils ; comparaison à temps constant sur tous les jetons."""
        found = None
        for login, profile in self._profiles.items():
            if hmac.compare_digest(token.encode("utf-8"), profile.service_token.encode("utf-8")):
                found = login
        return found
