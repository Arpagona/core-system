#!/usr/bin/env python3
"""Reprend les cartes des anciens Kanban personnels dans le Kanban d'entreprise, sans doublon ni perte.

    migrate_kanban_equipe.py <hermes_cli> <hermes_home_entreprise> <login> [<login> ...]

Pour chaque compte, lit (en lecture seule, CLI officielle, sous son compte Unix) les cartes de son ancien
Kanban personnel et crée la carte équivalente dans le tableau d'entreprise : responsable = le compte,
auteur = le compte, même titre, même description, même statut (bloquée, terminée). La clé d'idempotence
``deux-zones-<login>-<ancien id>`` rend la reprise rejouable : une carte déjà reprise n'est jamais recréée.
Les anciennes bases personnelles ne sont ni modifiées ni supprimées. Les cartes déjà présentes dans le
tableau d'entreprise (démonstration, sans responsable) ne sont pas touchées.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

LOGIN = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def key(login: str, card_id: str) -> str:
    return f"deux-zones-{login}-{card_id}"


def run(cmd: list[str], runner=subprocess.run) -> subprocess.CompletedProcess:
    return runner(cmd, capture_output=True, text=True, timeout=60, check=False, cwd="/tmp")


def migrate(cli: str, company_home: str, logins: list[str], runner=subprocess.run) -> dict:
    report = {"reprises": 0, "deja_presentes": 0, "ignorees": 0, "echecs": 0, "detail": []}
    existing = json.loads(run(["sudo", "-n", "-u", "hermes-arpagona", "env", "HOME=/srv/hermes-arpagona",
                               f"HERMES_HOME={company_home}", cli, "kanban", "list", "--json"], runner).stdout or "[]")
    for login in logins:
        if not LOGIN.fullmatch(login):
            raise ValueError(f"compte invalide : {login}")
        own = ["sudo", "-n", "-u", f"agent-{login}", "env", f"HOME=/srv/agents/{login}",
               f"HERMES_HOME=/srv/agents/{login}/.hermes", cli, "kanban"]
        listed = run(own + ["list", "--json"], runner)
        if listed.returncode:
            report["echecs"] += 1
            report["detail"].append({"login": login, "erreur": "lecture de l'ancien Kanban impossible"})
            continue
        for card in json.loads(listed.stdout or "[]"):
            if card.get("status") == "archived":
                report["ignorees"] += 1
                continue
            company = ["sudo", "-n", "-u", "hermes-arpagona", "env", "HOME=/srv/hermes-arpagona",
                       f"HERMES_HOME={company_home}", cli, "kanban"]
            created = run(company + ["create", f"--assignee={login}", f"--created-by={login}",
                                     f"--idempotency-key={key(login, card['id'])}",
                                     "--body=" + (card.get("body") or ""), "--json", "--", card["title"]], runner)
            if created.returncode:
                report["echecs"] += 1
                report["detail"].append({"login": login, "ancien": card["id"], "erreur": created.stderr[:120]})
                continue
            new = json.loads(created.stdout)
            if new.get("id") and any(t.get("id") == new["id"] for t in existing):
                report["deja_presentes"] += 1
                continue
            report["reprises"] += 1
            if card.get("status") == "blocked":
                run(company + ["block", "--", new["id"], f"Reprise de l'ancien Kanban de {login} : en attente de sa décision"], runner)
            elif card.get("status") == "done":
                run(company + ["complete", "--", new["id"]], runner)
            report["detail"].append({"login": login, "ancien": card["id"], "nouveau": new["id"], "statut": card.get("status")})
    return report


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    result = migrate(sys.argv[1], sys.argv[2], sys.argv[3:])
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1 if result["echecs"] else 0)
