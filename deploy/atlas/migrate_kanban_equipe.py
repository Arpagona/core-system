#!/usr/bin/env python3
"""Reprend les cartes des anciens Kanban personnels dans le Kanban d'entreprise, sans doublon ni perte.

    migrate_kanban_equipe.py <hermes_cli> <hermes_home_entreprise> <dossier_marqueurs> <login> [<login> ...]

Pour chaque compte, lit (SQLite en lecture seule, sous root : aucune écriture, aucune dépendance aux droits
du socle Hermès) les cartes de son ancien Kanban personnel et crée la carte équivalente dans le tableau d'entreprise : responsable = le compte,
auteur = le compte, même titre, même description, même statut (bloquée, terminée). La clé d'idempotence
``deux-zones-<login>-<ancien id>`` rend la reprise rejouable : une carte déjà reprise n'est jamais recréée.
Une fois un compte repris, un marqueur (``<dossier>/<login>.kanban-repris``) évite toute seconde reprise : une carte
archivée depuis ne ressuscite pas. Les anciennes bases personnelles ne sont ni modifiées ni supprimées. Les cartes déjà présentes dans le
tableau d'entreprise (démonstration, sans responsable) ne sont pas touchées.
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

LOGIN = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def key(login: str, card_id: str) -> str:
    return f"deux-zones-{login}-{card_id}"


def run(cmd: list[str], runner=subprocess.run) -> subprocess.CompletedProcess:
    return runner(cmd, capture_output=True, text=True, timeout=60, check=False, cwd="/tmp")


def read_personal_cards(login: str) -> list[dict]:
    """Cartes de l'ancien Kanban personnel (lecture seule). Une base absente = aucune carte à reprendre."""
    path = f"/srv/agents/{login}/.hermes/kanban.db"
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise OSError(str(exc)) from exc
    try:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute("SELECT id, title, body, status FROM tasks")]
    except sqlite3.Error as exc:
        raise OSError(str(exc)) from exc
    finally:
        db.close()


def migrate(cli: str, company_home: str, logins: list[str], runner=subprocess.run, reader=read_personal_cards,
            markers: str | None = None) -> dict:
    report = {"comptes_deja_repris": [], "reprises": 0, "deja_presentes": 0, "ignorees": 0, "echecs": 0, "detail": []}
    existing = json.loads(run(["sudo", "-n", "-u", "hermes-arpagona", "env", "HOME=/srv/hermes-arpagona",
                               f"HERMES_HOME={company_home}", cli, "kanban", "list", "--json"], runner).stdout or "[]")
    for login in logins:
        if not LOGIN.fullmatch(login):
            raise ValueError(f"compte invalide : {login}")
        marker = Path(markers) / f"{login}.kanban-repris" if markers else None
        if marker is not None and marker.exists():
            report["comptes_deja_repris"].append(login)
            continue
        try:
            cards = reader(login)
        except OSError:
            report["echecs"] += 1
            report["detail"].append({"login": login, "erreur": "lecture de l'ancien Kanban impossible"})
            continue
        failures_before = report["echecs"]
        for card in cards:
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
            status_cmd = None
            if card.get("status") == "blocked":
                status_cmd = ["block", "--", new["id"], f"Reprise de l'ancien Kanban de {login} : en attente de sa décision"]
            elif card.get("status") == "done":
                status_cmd = ["complete", "--", new["id"]]
            if status_cmd and run(company + status_cmd, runner).returncode:
                # Le statut n'a pas pu être repris : pas de marqueur, la reprise sera relancée (la carte existe déjà).
                report["echecs"] += 1
                report["detail"].append({"login": login, "ancien": card["id"], "nouveau": new["id"], "erreur": "statut non repris"})
                continue
            report["detail"].append({"login": login, "ancien": card["id"], "nouveau": new["id"], "statut": card.get("status")})
        if marker is not None and report["echecs"] == failures_before:
            marker.write_text("repris\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    result = migrate(sys.argv[1], sys.argv[2], sys.argv[4:], markers=sys.argv[3])
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1 if result["echecs"] else 0)
