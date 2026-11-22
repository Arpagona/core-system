"""Parcours complet sur le poste local : lanceur, moteur simulé, plugin réel, API, passerelle Kanban.

Connexion → chat → engagement consigné par le plugin → échéance → brouillon → approbation
« non envoyé » ; Kanban : création, commentaire signé par le compte, archivage.
Aucun réseau externe, aucune clé réelle, aucun modèle.
"""
import http.cookiejar
from contextlib import closing
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class PosteLocal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.port = port_libre()
        cls.proc = subprocess.Popen(
            [sys.executable, str(RACINE / "dev/lancer.py"), "--port", str(cls.port),
             "--moteur-port", str(port_libre()), "--kanban-port", str(port_libre()),
             "--data", cls.tmp.name, "--echeances", "0.5"],
            stdout=subprocess.PIPE, text=True, env=dict(os.environ, MOTEUR_SIMULE_DELAI="0"))
        cls.infos = json.loads(cls.proc.stdout.readline())
        cls.base = cls.infos["url"]
        cls.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.proc.stdout.close()
        cls.tmp.cleanup()

    def appel(self, chemin, donnees=None):
        req = urllib.request.Request(self.base + chemin, method="POST" if donnees is not None else "GET",
                                     data=json.dumps(donnees).encode() if donnees is not None else None,
                                     headers={"Content-Type": "application/json", "X-Arpagona": "1"})
        try:
            with self.opener.open(req, timeout=30) as rep:
                return rep.status, rep.read().decode()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read().decode()

    def connexion(self):
        status, _ = self.appel("/api/login", {"login": self.infos["login"], "password": self.infos["mot_de_passe"]})
        self.assertEqual(status, 200)

    def chat(self, texte):
        status, flux = self.appel("/api/chat", {"text": texte})
        self.assertEqual(status, 200, flux)
        fin = [json.loads(l[5:]) for l in flux.splitlines() if l.startswith("data:")][-1]
        self.assertEqual(fin["type"], "end")
        return fin

    def test_1_refus_sans_session(self):
        self.assertEqual(self.appel("/api/conversation")[0], 401)
        self.assertEqual(self.appel("/api/kanban/list")[0], 401)

    def test_2_relance_jusqu_a_approbation(self):
        self.connexion()
        fin = self.chat("Relance le client Dupont dans 1 seconde au sujet du devis de 200 supports")
        self.assertEqual(fin["status"], "done")
        self.assertIn("consigné pour Dupont", fin["text"])
        engagements = json.loads(self.appel("/api/engagements")[1])["engagements"]
        self.assertEqual(engagements[0]["client"], "Dupont")

        brouillon, limite = None, time.time() + 20
        while not brouillon and time.time() < limite:
            brouillons = json.loads(self.appel("/api/drafts")[1])["drafts"]
            brouillon = brouillons[0] if brouillons else None
            time.sleep(0.3)
        self.assertIsNotNone(brouillon, "aucun brouillon à l'échéance")
        self.assertEqual(brouillon["cible"], "Dupont")
        self.assertIn("devis de 200 supports", brouillon["corps"])

        status, _ = self.appel("/api/drafts/decide", {"id": brouillon["id"], "approve": True, "empreinte": "0" * 64})
        self.assertEqual(status, 409, "une empreinte fausse doit être refusée")
        status, corps = self.appel("/api/drafts/decide",
                                   {"id": brouillon["id"], "approve": True, "empreinte": brouillon["empreinte"]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(corps)["livraison"], "non envoyé : aucun connecteur autorisé")
        self.assertEqual(self.appel("/api/drafts/decide", {"id": brouillon["id"], "approve": False,
                                                           "empreinte": brouillon["empreinte"]})[0], 409)

    def test_3_kanban(self):
        self.connexion()
        taches = json.loads(self.appel("/api/kanban/list")[1])
        self.assertGreaterEqual(len(taches), 3)
        status, corps = self.appel("/api/kanban/create", {"title": "Carte de test", "body": "corps"})
        self.assertEqual(status, 200, corps)
        ident = json.loads(corps)["id"]
        self.assertEqual(self.appel("/api/kanban/comment", {"id": ident, "text": "vu", "author": "intrus"})[0], 200)
        detail = json.loads(self.appel("/api/kanban/show?id=" + ident)[1])
        self.assertEqual(detail["comments"][0]["author"], "Démo ARPAGONA")
        self.assertIsNone(detail["task"]["assignee"])
        self.assertEqual(self.appel("/api/kanban/archive", {"id": ident})[0], 200)
        restantes = json.loads(self.appel("/api/kanban/list")[1])
        self.assertNotIn(ident, [t["id"] for t in restantes])

    @unittest.skipIf(os.name == "nt", "droits POSIX")
    def test_4_secrets_hors_depot_et_proteges(self):
        for nom in ("service_token", "kanban_token", "hermes_key"):
            self.assertEqual((Path(self.tmp.name) / nom).stat().st_mode & 0o077, 0, nom)
        with closing(sqlite3.connect(Path(self.tmp.name) / "arpagona.db")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
