#!/usr/bin/env python3
"""Kanban simulé : imite les sous-commandes `hermes kanban` utilisées par la passerelle.

Stockage dans un fichier JSON (variable KANBAN_SIMULE_FICHIER). Même forme de sortie que la CLI
officielle pour `list --json`, `show --json` et `create --json`. Poste de développement uniquement.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

try:
    import fcntl  # verrou entre appels concurrents (Linux, macOS)
except ImportError:  # Windows : poste mono-utilisateur, pas de verrou
    fcntl = None

FICHIER = Path(os.environ.get("KANBAN_SIMULE_FICHIER", ".local/dev/kanban.json"))

EXEMPLES = [
    ("Préparer la démo PME : 200 supports industriels",
     "Scénario fictif : matière, tolérances, délai et incertitudes à préciser avant devis.", "ready"),
    ("Deux instances clients isolées sur le banc",
     "Lot 3 proposé : script paramétré, secrets et ports distincts, tests croisés négatifs.", "todo"),
    ("HTTPS et cookie Secure avant tout accès client",
     "Prérequis P0 de l'audit d'utilisabilité du 19/11.", "blocked"),
]


def tache(titre: str, corps: str, statut: str) -> dict:
    return {"id": "t_" + secrets.token_hex(4), "title": titre, "body": corps, "assignee": None,
            "status": statut, "priority": 0, "tenant": None, "created_by": "mission-control",
            "created_at": int(time.time()), "completed_at": None, "comments": []}


def charger() -> list[dict]:
    if not FICHIER.exists():
        return [tache(*e) for e in EXEMPLES]
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "kanban":
        print("usage : kanban <op> …", file=sys.stderr)
        return 2
    op, reste = argv[1], argv[2:]
    options = [a for a in reste if a.startswith("--") and a != "--"]
    positionnels = reste[reste.index("--") + 1:] if "--" in reste else [a for a in reste if not a.startswith("--")]
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    with open(FICHIER.with_suffix(".lock"), "w") as verrou:
        if fcntl:
            fcntl.flock(verrou, fcntl.LOCK_EX)
        taches = charger()
        actives = [t for t in taches if t["status"] != "archived"]
        par_id = {t["id"]: t for t in taches}
        sortie = None
        if op == "list":
            sortie = [{k: v for k, v in t.items() if k != "comments"} for t in actives]
        elif op == "create":
            corps = next((o.split("=", 1)[1] for o in options if o.startswith("--body=")), "")
            nouvelle = tache(positionnels[0], corps, "ready")
            for field,flag in (("assignee","--assignee="),("created_by","--created-by=")):
                value=next((o.split("=",1)[1] for o in options if o.startswith(flag)),None)
                if value is not None:nouvelle[field]=value
            taches.append(nouvelle)
            sortie = {k: v for k, v in nouvelle.items() if k != "comments"}
        else:
            ident = positionnels[0] if positionnels else ""
            t = par_id.get(ident)
            if not t:
                print("carte inconnue", file=sys.stderr)
                return 1
            if op == "show":
                sortie = {"task": {k: v for k, v in t.items() if k != "comments"},
                          "comments": t["comments"], "events": t.get("events", []), "parents": [], "children": [], "runs": []}
            elif op == "assign":
                t["assignee"] = positionnels[1]
            elif op == "comment":
                auteur = next((o.split("=", 1)[1] for o in options if o.startswith("--author=")), "utilisateur")
                if not positionnels[1].strip():
                    print("commentaire vide refusé", file=sys.stderr)
                    return 1
                t["comments"].append({"author": auteur, "body": positionnels[1], "created_at": int(time.time())})
            elif op in {"complete", "block", "unblock", "archive"}:
                # Transitions refusées comme par le noyau natif (block_task/complete_task).
                if op == "block":
                    if t["status"] not in {"ready", "running"}:
                        print(f"cannot block {ident}: statut {t['status']}", file=sys.stderr)
                        return 1
                    motif = positionnels[1] if len(positionnels) > 1 else ""
                    if not motif.strip():
                        print("cannot block: motif vide", file=sys.stderr)
                        return 1
                    auteur = next((o.split("=", 1)[1] for o in options if o.startswith("--author=")), "utilisateur")
                    # La CLI native enregistre d'abord le motif en commentaire « BLOCKED: … ».
                    t["comments"].append({"author": auteur, "body": "BLOCKED: " + motif, "created_at": int(time.time())})
                    t.setdefault("events", []).append({"kind": "blocked", "payload": {"reason": motif, "kind": None,
                        "source_status": t["status"], "recurrences": 1}, "created_at": int(time.time())})
                    t["status"] = "blocked"
                elif op == "complete":
                    if t["status"] in {"done", "archived", "triage"}:
                        print(f"cannot complete {ident}: statut {t['status']}", file=sys.stderr)
                        return 1
                    t["status"] = "done"
                elif op == "unblock":
                    if t["status"] not in {"blocked", "scheduled", "triage"}:
                        print(f"cannot unblock {ident}: statut {t['status']}", file=sys.stderr)
                        return 1
                    t["status"] = "ready"
                else:
                    t["status"] = "archived"
            else:
                print("opération non simulée", file=sys.stderr)
                return 2
        FICHIER.write_text(json.dumps(taches, ensure_ascii=False, indent=1), encoding="utf-8")
    if sortie is not None:
        print(json.dumps(sortie, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
