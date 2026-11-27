"""Tests des engagements et des approbations, contre un faux moteur."""
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_api import Client, FakeEngine, PASSWORD_A  # noqa: E402
from arpagona_api.engagements import InvalidEngagement, fingerprint, parse_due  # noqa: E402
from arpagona_api.hermes import HermesClient  # noqa: E402
from arpagona_api.server import App, make_handler, run_due_engagement  # noqa: E402
from arpagona_api.store import Store  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

SERVICE = "jeton-de-service-de-test"


class EngagementApiTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        static = Path(self.tmp.name) / "web"; static.mkdir()
        (static / "index.html").write_text("ok", encoding="utf-8")
        self.engine = FakeEngine()
        self.store = Store(str(Path(self.tmp.name) / "t.db"))
        self.store.add_user("alice", "Alice Fictive", PASSWORD_A)
        self.app = App(self.store, HermesClient(self.engine.url, "cle-de-test"), static, False, SERVICE)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]
        self.user = self.store.check_password("alice", PASSWORD_A)
        self.session = self.store.conversation_for(self.user["id"])["hermes_session_id"]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.engine.server.shutdown(); self.engine.server.server_close()
        self.store.close(); self.tmp.cleanup()

    def internal(self, method, path, body=None, session=None, token=SERVICE):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"X-Arpagona-Service": token, "X-Hermes-Session": self.session if session is None else session,
                   "Content-Type": "application/json"}
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read().decode() or "{}")
        conn.close()
        return out

    def test_date_sans_fuseau_refusee(self):
        status, body = self.internal("POST", "/internal/engagements", {
            "client": "Dupont", "sujet": "devis", "decision": "relancer vendredi",
            "echeance": "2026-11-13T09:00:00", "certitude": "certain"})
        self.assertEqual(status, 400)
        self.assertIn("fuseau", body["error"])

    def test_service_sans_jeton_refuse(self):
        self.assertEqual(self.internal("POST", "/internal/engagements", {}, token="faux")[0], 401)
        self.assertEqual(self.internal("GET", "/internal/engagements", token="")[0], 401)

    def test_session_inconnue_refusee(self):
        self.assertEqual(self.internal("GET", "/internal/engagements", session="inconnue")[0], 401)

    def scenario_dupont(self):
        status, body = self.internal("POST", "/internal/engagements", {
            "client": "Dupont", "sujet": "devis", "decision": "le relancer au sujet du devis",
            "echeance": "2026-11-13T09:00:00+01:00", "certitude": "certain"})
        self.assertEqual(status, 201, body)
        return body["id"]

    def test_engagement_enregistre_et_liste(self):
        engagement_id = self.scenario_dupont()
        status, body = self.internal("GET", "/internal/engagements")
        self.assertEqual(status, 200)
        self.assertEqual([(e["client"], e["statut"]) for e in body["engagements"]], [("Dupont", "planifie")])
        alice = Client(self.port); alice.login("alice", PASSWORD_A)
        listed = json.loads(alice.call("GET", "/api/engagements")[1])["engagements"]
        self.assertEqual([e["id"] for e in listed], [engagement_id])

    def test_brouillon_et_validation(self):
        engagement_id = self.scenario_dupont()
        status, body = self.internal("POST", "/internal/drafts", {
            "engagement_id": engagement_id, "cible": "dupont@exemple.invalid",
            "corps": "Bonjour M. Dupont, suite à notre échange au sujet du devis…"})
        self.assertEqual(status, 201)
        draft_id = body["id"]
        alice = Client(self.port); alice.login("alice", PASSWORD_A)
        draft = json.loads(alice.call("GET", "/api/drafts")[1])["drafts"][0]
        self.assertEqual(draft["statut"], "en_attente")
        # empreinte modifiée : refus
        self.assertEqual(alice.call("POST", "/api/drafts/decide",
                                    {"id": draft_id, "approve": True, "empreinte": "0" * 64})[0], 409)
        status, body, _ = alice.call("POST", "/api/drafts/decide",
                                  {"id": draft_id, "approve": True, "empreinte": draft["empreinte"]})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["statut"], "approuve")
        self.assertIn("prêt à envoyer", result["livraison"])
        drafts = json.loads(alice.call("GET", "/api/drafts")[1])["drafts"]
        self.assertEqual(drafts[0]["statut"], "approuve")
        # seconde décision refusée
        self.assertEqual(alice.call("POST", "/api/drafts/decide",
                                    {"id": draft_id, "approve": False, "empreinte": draft["empreinte"]})[0], 409)

    def test_refus_du_brouillon(self):
        engagement_id = self.scenario_dupont()
        _, body = self.internal("POST", "/internal/drafts", {"engagement_id": engagement_id,
                                                             "cible": "dupont@exemple.invalid", "corps": "texte"})
        alice = Client(self.port); alice.login("alice", PASSWORD_A)
        draft = json.loads(alice.call("GET", "/api/drafts")[1])["drafts"][0]
        status, out, _ = alice.call("POST", "/api/drafts/decide",
                                 {"id": draft["id"], "approve": False, "empreinte": draft["empreinte"]})
        self.assertEqual((status, out), (200, json.dumps({"statut": "refuse", "livraison": None})))

    def test_brouillon_d_un_autre_utilisateur_inaccessible(self):
        engagement_id = self.scenario_dupont()
        self.store.add_user("bruno", "Bruno Fictif", "mot-de-passe-fictif-B")
        bruno = Client(self.port); bruno.login("bruno", "mot-de-passe-fictif-B")
        self.assertEqual(json.loads(bruno.call("GET", "/api/drafts")[1])["drafts"], [])
        self.assertEqual(bruno.call("POST", "/internal/drafts", {})[0], 401)

    def test_echeance_reclamee_une_seule_fois(self):
        engagement_id = self.scenario_dupont()
        row = self.store.engagement(engagement_id)
        self.store._run("UPDATE engagements SET due_at = ? WHERE id = ?", (1.0, engagement_id))
        first = self.store.claim_due(1_000.0)
        second = self.store.claim_due(1_000.0)
        self.assertEqual(first["id"], engagement_id)
        self.assertIsNone(second)
        self.assertEqual(first["status"], "en_preparation")

    def test_declencheur_produit_un_brouillon(self):
        engagement_id = self.scenario_dupont()
        self.store._run("UPDATE engagements SET due_at = ? WHERE id = ?", (1.0, engagement_id))
        engagement = self.store.claim_due(1_000.0)
        # le faux moteur ne crée pas de brouillon : on vérifie le déclenchement et l'appel réel au moteur
        run_due_engagement(self.app, engagement)
        self.assertEqual(len(self.engine.runs), 1)
        self.assertIn("arpagona_draft_create", list(self.engine.runs.values())[0])
        self.assertEqual(self.engine.sessions, [self.session])
        # sans brouillon créé, l'engagement repart en planification pour une nouvelle tentative
        self.assertEqual(self.store.engagement(engagement_id)["status"], "planifie")


class ParseTest(unittest.TestCase):
    def test_parse_due(self):
        ts, tz, expr = parse_due("2026-11-13T09:00:00+01:00")
        self.assertEqual(tz, "+0100")
        self.assertEqual(expr, "2026-11-13T09:00:00+01:00")
        with self.assertRaises(InvalidEngagement):
            parse_due("vendredi")
        with self.assertRaises(InvalidEngagement):
            parse_due("2026-11-13T09:00:00")

    def test_empreinte(self):
        a = fingerprint("x@y", "corps")
        self.assertEqual(a, fingerprint("x@y ", "corps\n"))
        self.assertNotEqual(a, fingerprint("x@z", "corps"))


if __name__ == "__main__":
    unittest.main()
