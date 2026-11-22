"""Moteur simulé : imite les routes /v1/runs du serveur API d'Hermès, sans modèle ni clé payante.

Usage réservé au poste de développement et aux tests. Les réponses sont scriptées, mais les
outils métier passent par le vrai plugin `plugins/arpagona-core` : l'API ARPAGONA reçoit donc
les mêmes appels qu'avec Hermès (jeton de service, session, validation des champs).

Comportements :
- message contenant une relance datée (« relance le client Dupont dans 2 minutes au sujet du devis »)
  → outil `arpagona_engagement_record` avec une échéance absolue ;
- consigne d'échéance envoyée par l'API (« Échéance atteinte… ») → `arpagona_engagement_list`
  puis `arpagona_draft_create` ;
- tout autre message → réponse d'aide.
"""
from __future__ import annotations

import argparse
import hmac
import importlib.util
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
TERMINAUX = {"completed", "failed", "cancelled"}
UNITES = {"seconde": 1, "minute": 60, "heure": 3600, "jour": 86400}


def charger_plugin():
    spec = importlib.util.spec_from_file_location("arpagona_core", RACINE / "plugins/arpagona-core/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Execution:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.status = "running"
        self.output = ""
        self.events: list[dict] = []
        self.cond = threading.Condition()

    def emit(self, event: dict) -> None:
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    def finish(self, status: str, output: str) -> None:
        with self.cond:
            self.status, self.output = status, output
            self.events.append({"event": "run." + status})
            self.cond.notify_all()


def echeance_relative(texte: str, maintenant: datetime) -> str | None:
    """« dans 2 minutes » → date ISO absolue avec fuseau. Le vrai agent fait ce travail lui-même."""
    m = re.search(r"dans\s+(\d+)\s+(seconde|minute|heure|jour)s?", texte, re.IGNORECASE)
    if m:
        return (maintenant + timedelta(seconds=int(m.group(1)) * UNITES[m.group(2).lower()])).isoformat(timespec="seconds")
    m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)", texte)
    return m.group(0) if m else None


def analyser_relance(texte: str, maintenant: datetime) -> dict | None:
    if not re.search(r"\b(relance|rappelle|rappel|engagement)", texte, re.IGNORECASE):
        return None
    echeance = echeance_relative(texte, maintenant)
    if not echeance:
        return {"manque": "échéance"}
    client = re.search(r"(?:client|chez|à)\s+([A-ZÉÈ][\w&\-]+(?:\s+[A-ZÉÈ][\w&\-]+)*)", texte)
    sujet = re.search(r"(?:au sujet d[eu]s?|pour|concernant)\s+(.+?)(?:[.,;!?]|$)", texte, re.IGNORECASE)
    return {
        "client": client.group(1) if client else "Client à préciser",
        "sujet": (sujet.group(1).strip() if sujet else "suivi commercial")[:200],
        "decision": "Relancer " + (client.group(1) if client else "le client") + " concernant : "
                    + (sujet.group(1).strip() if sujet else "suivi commercial")[:200],
        "echeance": echeance,
        "certitude": "probable",
    }


class Moteur:
    def __init__(self, cle: str, plugin, delai_mot: float = 0.02):
        self.cle = cle
        self.plugin = plugin
        self.delai_mot = delai_mot
        self.executions: dict[str, Execution] = {}
        self.idempotence: dict[str, str] = {}
        self.verrou = threading.Lock()

    def demarrer(self, texte: str, session: str, cle_idem: str) -> str:
        with self.verrou:
            if cle_idem and cle_idem in self.idempotence:
                return self.idempotence[cle_idem]
            run = Execution("run_" + uuid.uuid4().hex[:16])
            self.executions[run.run_id] = run
            if cle_idem:
                self.idempotence[cle_idem] = run.run_id
        threading.Thread(target=self._executer, args=(run, texte, session), daemon=True).start()
        return run.run_id

    def _outil(self, run: Execution, nom: str, fonction, args: dict, session: str) -> dict:
        run.emit({"event": "tool.started", "tool": nom})
        try:
            resultat = json.loads(fonction(args, session_id=session))
        except (ValueError, TypeError):
            resultat = {"error": "réponse illisible"}
        run.emit({"event": "tool.completed", "tool": nom})
        return resultat

    def _parler(self, run: Execution, texte: str) -> None:
        for mot in re.findall(r"\S+\s*", texte):
            run.emit({"event": "message.delta", "delta": mot})
            time.sleep(self.delai_mot)

    def _executer(self, run: Execution, texte: str, session: str) -> None:
        try:
            reponse = self._repondre(run, texte, session)
            self._parler(run, reponse)
            run.finish("completed", reponse)
        except Exception as exc:  # un moteur simulé ne doit pas tomber silencieusement
            run.finish("failed", f"erreur du moteur simulé : {exc}")

    def _repondre(self, run: Execution, texte: str, session: str) -> str:
        if texte.startswith("Échéance atteinte"):
            return self._preparer_brouillon(run, texte, session)
        relance = analyser_relance(texte, datetime.now().astimezone())
        if relance and "manque" in relance:
            return ("Je peux consigner cette relance, mais il me manque l'échéance. "
                    "Précisez « dans 2 minutes » ou une date comme 2026-11-23T09:00:00+01:00.")
        if relance:
            res = self._outil(run, "arpagona_engagement_record", self.plugin.record, relance, session)
            if "error" in res:
                return f"Engagement refusé par l'API : {res['error']}."
            return (f"Engagement n°{res['id']} consigné pour {relance['client']} ({relance['sujet']}), "
                    f"échéance {relance['echeance']}. À l'échéance, je préparerai un brouillon ; "
                    "rien ne sera envoyé sans votre approbation.")
        return ("Mode développement : je suis le moteur simulé, sans modèle de langage. "
                "Essayez : « Relance le client Dupont dans 1 minute au sujet du devis de 200 supports ». "
                "Pour un vrai agent, lancez `python3 dev/lancer.py --hermes-url …`.")

    def _preparer_brouillon(self, run: Execution, texte: str, session: str) -> str:
        client = re.search(r"- client : (.+)", texte)
        sujet = re.search(r"- sujet : (.+)", texte)
        liste = self._outil(run, "arpagona_engagement_list", self.plugin.listing, {}, session)
        candidats = [e for e in liste.get("engagements", [])
                     if e.get("statut") == "en_preparation" and client and e.get("client") == client.group(1).strip()]
        if not candidats:
            return "Aucun engagement en préparation ne correspond : brouillon non créé."
        engagement = candidats[0]
        corps = ("Bonjour,\n\nComme convenu, je reviens vers vous concernant : "
                 f"{sujet.group(1).strip() if sujet else engagement['sujet']}.\n"
                 "Pouvez-vous me confirmer où vous en êtes ? Je reste disponible pour en parler.\n\n"
                 "Bien cordialement,")
        res = self._outil(run, "arpagona_draft_create", self.plugin.draft,
                          {"engagement_id": engagement["id"], "cible": engagement["client"], "corps": corps}, session)
        if "error" in res:
            return f"Brouillon refusé par l'API : {res['error']}."
        return f"Brouillon n°{res['id']} préparé pour {engagement['client']}. Il attend votre décision dans Approbations."


def gestionnaire(moteur: Moteur):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            return

        def _json(self, status: int, payload: dict) -> None:
            corps = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(corps)

        def _autorise(self) -> bool:
            if hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + moteur.cle):
                return True
            self._json(401, {"error": "clé invalide"})
            return False

        def do_GET(self):
            if self.path == "/v1/health":
                return self._json(200, {"status": "ok", "moteur": "simulé"})
            if not self._autorise():
                return
            m = re.fullmatch(r"/v1/runs/(run_[0-9a-f]+)(/events)?", self.path)
            run = moteur.executions.get(m.group(1)) if m else None
            if not run:
                return self._json(404, {"error": "exécution inconnue"})
            if not m.group(2):
                return self._json(200, {"run_id": run.run_id, "status": run.status, "output": run.output})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            vu = 0
            while True:
                with run.cond:
                    while vu >= len(run.events) and run.status not in TERMINAUX:
                        run.cond.wait(timeout=1)
                    nouveaux, vu = run.events[vu:], len(run.events)
                    fini = run.status in TERMINAUX and vu >= len(run.events)
                try:
                    for ev in nouveaux:
                        self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode("utf-8") + b"\n\n")
                    self.wfile.flush()
                except OSError:
                    return
                if fini:
                    return

        def do_POST(self):
            if not self._autorise():
                return
            if self.path != "/v1/runs":
                return self._json(404, {"error": "route inconnue"})
            try:
                corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                texte, session = str(corps["input"]), str(corps["session_id"])
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"error": "requête invalide"})
            run_id = moteur.demarrer(texte, session, self.headers.get("Idempotency-Key", ""))
            self._json(202, {"run_id": run_id, "status": "running"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=18642)
    parser.add_argument("--cle-fichier", required=True, help="fichier contenant la clé attendue")
    args = parser.parse_args()
    cle = Path(args.cle_fichier).read_text(encoding="ascii").strip()
    # Le plugin lit ARPAGONA_API_URL et ARPAGONA_SERVICE_TOKEN(_FILE) dans l'environnement.
    moteur = Moteur(cle, charger_plugin(), float(os.environ.get("MOTEUR_SIMULE_DELAI", "0.02")))
    serveur = ThreadingHTTPServer(("127.0.0.1", args.port), gestionnaire(moteur))
    serveur.daemon_threads = True
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
