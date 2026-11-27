"""Tests du palier beta : missions, plafond, arrêt, envoi courriel, journal, export, rôles.

Tout est joué contre le faux moteur et un faux facteur de courriel.
La remise réelle se prouve sur le banc Atlas, pas ici.
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_api import Client, FakeEngine, PASSWORD_A, PASSWORD_B  # noqa: E402
from arpagona_api.hermes import HermesClient  # noqa: E402
from arpagona_api.server import App, make_handler  # noqa: E402
from arpagona_api.store import Store  # noqa: E402

SERVICE = "jeton-de-service-de-test"


class FakeMailer:
    def __init__(self):
        self.sent = []
        self.fail = False
        self.sender = 'contact@arpagona.com'

    def send(self, to, subject, body, message_id=None):
        if self.fail:
            from arpagona_api.mailer import MailError
            raise MailError("courriel non remis (SMTP)")
        self.sent.append((to, subject, body))
        return f"<{len(self.sent)}@test>"


class BetaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        static = Path(self.tmp.name) / "web"
        static.mkdir()
        (static / "index.html").write_text("ok", encoding="utf-8")
        self.engine = FakeEngine()
        self.mailer = FakeMailer()
        self.store = Store(str(Path(self.tmp.name) / "t.db"))
        self.store.add_user("alice", "Alice Fictive", PASSWORD_A)   # premier compte : admin
        self.store.add_user("bruno", "Bruno Fictif", PASSWORD_B)    # membre
        self.app = App(self.store, HermesClient(self.engine.url, "cle-de-test"), static, False, SERVICE,
                       max_mission_usd=0.50, max_day_usd=5.00, mailer=self.mailer)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]
        self.alice = Client(self.port)
        self.alice.login("alice", PASSWORD_A)
        self.bruno = Client(self.port)
        self.bruno.login("bruno", PASSWORD_B)
        self.alice_user = self.store.check_password("alice", PASSWORD_A)
        self.bruno_user = self.store.check_password("bruno", PASSWORD_B)
        self.session_a = self.store.conversation_for(self.alice_user["id"])["hermes_session_id"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.server.shutdown()
        self.engine.server.server_close()
        self.store.close()
        self.tmp.cleanup()

    def internal(self, method, path, body=None, session=None, token=SERVICE):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"X-Arpagona-Service": token, "X-Hermes-Session": session or self.session_a,
                   "Content-Type": "application/json"}
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read().decode() or "{}")
        conn.close()
        return out

    def draft(self, body="Bonjour M. Dupont, suite à notre échange…"):
        status, engagement = self.internal("POST", "/internal/engagements", {
            "client": "Dupont", "sujet": "devis 200 supports", "decision": "le relancer",
            "echeance": "2026-11-13T09:00:00+01:00", "certitude": "certain"})
        self.assertEqual(status, 201, engagement)
        status, draft = self.internal("POST", "/internal/drafts", {
            "engagement_id": engagement["id"], "cible": "dupont@exemple.invalid", "corps": body})
        self.assertEqual(status, 201, draft)
        listed = json.loads(self.alice.call("GET", "/api/drafts")[1])["drafts"]
        return next(d for d in listed if d["id"] == draft["id"])

    # --- missions ---------------------------------------------------------
    def test_budget_reserve_avant_appel_moteur(self):
        from unittest.mock import patch
        original = self.app.hermes.start_run
        observed = []
        def start(*args, **kwargs):
            observed.append(self.store.budget.snapshot(self.app.now())['reserve_usd'])
            return original(*args, **kwargs)
        with patch.object(self.app.hermes, 'start_run', side_effect=start):
            self.assertEqual(self.alice.call('POST', '/api/chat', {'text': 'test synthétique'})[0], 200)
        self.assertEqual(observed, [.5])

    def test_budget_cout_inconnu_bloque_aussi_autre_compte(self):
        from unittest.mock import patch
        original = self.app.hermes.start_run
        def start(*args, **kwargs):
            run = original(*args, **kwargs)
            self.engine.costs[run] = float('nan')
            return run
        with patch.object(self.app.hermes, 'start_run', side_effect=start):
            self.assertEqual(self.alice.call('POST', '/api/chat', {'text': 'test synthétique'})[0], 200)
        before = len(self.engine.runs)
        status, body, _ = self.bruno.call('POST', '/api/chat', {'text': 'ne pas facturer'})
        self.assertEqual(status, 429, body)
        self.assertEqual(len(self.engine.runs), before)

    def test_echeance_respecte_la_meme_limite(self):
        import time
        from arpagona_api.server import run_due_engagement
        self.app.max_day_usd = .25
        assert self.alice_user is not None
        self.store.add_engagement(self.alice_user['id'], 'Fictif', 'Recette', 'relancer',
                                  time.time()-1, '+0100', 'test', 'certain', None)
        due = self.store.claim_due(time.time())
        assert due is not None
        run_due_engagement(self.app, dict(due))
        self.assertEqual(len(self.engine.runs), 0)

    def test_echeance_est_suivie_et_cout_comptabilise(self):
        import time
        from arpagona_api.server import run_due_engagement
        assert self.alice_user is not None
        self.store.add_engagement(self.alice_user['id'], 'Fictif', 'Recette', 'relancer',
                                  time.time()-1, '+0100', 'test', 'certain', None)
        due = self.store.claim_due(time.time())
        assert due is not None
        run_due_engagement(self.app, dict(due))
        rows = self.store.missions(self.alice_user['id'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'terminee')
        self.assertEqual(self.store.budget.snapshot(self.app.now())['mesure_usd'], .0025)
        self.assertEqual(self.store.budget.snapshot(self.app.now())['reserve_usd'], 0)

    def test_chat_cree_une_mission_terminee_avec_cout(self):
        status, _, _ = self.alice.call("POST", "/api/chat", {"text": "prépare la relance Dupont"})
        self.assertEqual(status, 200)
        body = json.loads(self.alice.call("GET", "/api/missions")[1])
        self.assertEqual(len(body["missions"]), 1)
        mission = body["missions"][0]
        self.assertEqual(mission["titre"], "prépare la relance Dupont")
        self.assertEqual(mission["statut"], "terminee")
        self.assertAlmostEqual(mission["cout"], 0.0025)
        self.assertIn("écho", mission["resultat"])
        self.assertEqual(body["actives"], 0)

    def test_plafond_journalier_refuse_la_mission_suivante(self):
        self.alice.call("POST", "/api/chat", {"text": "première mission"})
        self.app.max_day_usd = 0.001  # déjà dépassé par la première mission
        status, body, _ = self.alice.call("POST", "/api/chat", {"text": "seconde mission"})
        self.assertEqual(status, 429)
        self.assertIn("plafond", json.loads(body)["error"])
        self.assertEqual(len(json.loads(self.alice.call("GET", "/api/missions")[1])["missions"]), 1)

    def test_depassement_plafond_mission_signale(self):
        self.app.max_mission_usd = 0.001
        self.alice.call("POST", "/api/chat", {"text": "mission coûteuse"})
        mission = json.loads(self.alice.call("GET", "/api/missions")[1])["missions"][0]
        self.assertEqual(mission["arret"], "depassement_plafond")

    def test_arret_demande_transmet_au_moteur(self):
        mission_id = self.store.start_mission(self.alice_user["id"], 1, "run_42", "mission longue")
        status, body, _ = self.alice.call("POST", "/api/missions/stop", {"id": mission_id})
        self.assertEqual(status, 200)
        self.assertIn("run_42", self.engine.stopped)
        self.assertEqual(json.loads(body)["moteur"], True)
        self.assertEqual(self.store.mission(mission_id)["stop_reason"], "demande")

    def test_arret_mission_d_autrui_refuse(self):
        mission_id = self.store.start_mission(self.alice_user["id"], 1, "run_43", "mission d'alice")
        self.assertEqual(self.bruno.call("POST", "/api/missions/stop", {"id": mission_id})[0], 403)

    # --- envoi ------------------------------------------------------------
    def test_envoi_apres_approbation(self):
        draft = self.draft()
        self.assertEqual(self.alice.call("POST", "/api/drafts/decide",
                                         {"id": draft["id"], "approve": True,
                                          "empreinte": draft["empreinte"]})[0], 200)
        status, body, _ = self.alice.call("POST", "/api/drafts/send",
                                          {"id": draft["id"], "empreinte": draft["empreinte"]})
        self.assertEqual(status, 200, body)
        self.assertEqual(len(self.mailer.sent), 1)
        to, subject, text = self.mailer.sent[0]
        self.assertEqual(to, "dupont@exemple.invalid")
        self.assertIn("200 supports", subject)
        self.assertIn("Dupont", text)
        drafts = json.loads(self.alice.call("GET", "/api/drafts")[1])["drafts"]
        self.assertEqual(drafts[0]["statut"], "envoye")
        # un second envoi est refusé
        self.assertEqual(self.alice.call("POST", "/api/drafts/send",
                                         {"id": draft["id"], "empreinte": draft["empreinte"]})[0], 409)

    def test_envoi_sans_approbation_refuse(self):
        draft = self.draft()
        status, _, _ = self.alice.call("POST", "/api/drafts/send",
                                       {"id": draft["id"], "empreinte": draft["empreinte"]})
        self.assertEqual(status, 409)
        self.assertEqual(self.mailer.sent, [])

    def test_envoi_empreinte_erronee_refuse(self):
        draft = self.draft()
        self.alice.call("POST", "/api/drafts/decide",
                        {"id": draft["id"], "approve": True, "empreinte": draft["empreinte"]})
        status, _, _ = self.alice.call("POST", "/api/drafts/send",
                                       {"id": draft["id"], "empreinte": "0" * 64})
        self.assertEqual(status, 409)
        self.assertEqual(self.mailer.sent, [])

    def test_echec_smtp_trace_sans_reprise(self):
        draft = self.draft()
        self.alice.call("POST", "/api/drafts/decide",
                        {"id": draft["id"], "approve": True, "empreinte": draft["empreinte"]})
        self.mailer.fail = True
        status, body, _ = self.alice.call("POST", "/api/drafts/send",
                                          {"id": draft["id"], "empreinte": draft["empreinte"]})
        self.assertEqual(status, 502)
        drafts = json.loads(self.alice.call("GET", "/api/drafts")[1])["drafts"]
        self.assertEqual(drafts[0]["statut"], "echec")
        self.mailer.fail = False
        self.assertEqual(self.alice.call("POST", "/api/drafts/send",
                                         {"id": draft["id"], "empreinte": draft["empreinte"]})[0], 409)

    def test_envoi_sans_configuration(self):
        self.app.mailer = None
        self.assertEqual(self.alice.call("POST", "/api/drafts/send", {"id": 1, "empreinte": "x"})[0], 503)

    def test_approbation_exige_boolean_strict(self):
        draft = self.draft()
        for value in ('false', 'true', 1, None):
            status, _, _ = self.alice.call('POST', '/api/drafts/decide',
                {'id': draft['id'], 'approve': value, 'empreinte': draft['empreinte']})
            self.assertEqual(status, 400)

    def test_approbation_du_brouillon_d_autrui_refusee(self):
        draft = self.draft()
        for approve in (True, False):
            status, _, _ = self.bruno.call("POST", "/api/drafts/decide",
                {"id": draft["id"], "approve": approve, "empreinte": draft["empreinte"]})
            self.assertEqual(status, 403)
            self.assertEqual(self.store.draft(draft["id"])["status"], "en_attente")

    def test_envoi_du_brouillon_d_autrui_refuse(self):
        draft = self.draft()
        self.alice.call("POST", "/api/drafts/decide",
                        {"id": draft["id"], "approve": True, "empreinte": draft["empreinte"]})
        status, _, _ = self.bruno.call("POST", "/api/drafts/send",
                                       {"id": draft["id"], "empreinte": draft["empreinte"]})
        self.assertEqual(status, 403)
        self.assertEqual(self.mailer.sent, [])

    # --- journal, export, rôles ------------------------------------------
    def test_membre_ne_peut_pas_exporter(self):
        self.assertEqual(self.bruno.call("GET", "/api/export")[0], 403)
        status, body, _ = self.alice.call("GET", "/api/export")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["format"], "arpagona-export-1")
        self.assertTrue(all("pw_hash" not in u for u in data["users"]))

    def test_membre_ne_voit_que_son_journal(self):
        self.alice.call("POST", "/api/chat", {"text": "mission d'alice"})
        events = json.loads(self.bruno.call("GET", "/api/audit")[1])["evenements"]
        self.assertTrue(all(e["compte"] == self.bruno_user["id"] for e in events))
        admin_events = json.loads(self.alice.call("GET", "/api/audit")[1])["evenements"]
        self.assertTrue(any(e["action"] == "chat" for e in admin_events))

    def test_roles_visibles_et_premier_compte_admin(self):
        me = json.loads(self.alice.call("GET", "/api/me")[1])
        self.assertEqual(me["role"], "admin")
        self.assertTrue(me["admin"])
        self.assertTrue(me["mail"])
        me_b = json.loads(self.bruno.call("GET", "/api/me")[1])
        self.assertEqual(me_b["role"], "membre")


if __name__ == "__main__":
    unittest.main()
