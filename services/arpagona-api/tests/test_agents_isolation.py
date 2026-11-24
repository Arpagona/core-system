"""Isolation des agents personnels : chaque compte n'atteint que SON moteur, SON Kanban, SES outils.

Faux moteurs et fausses passerelles locaux, données fictives. Ne prouve rien sur Hermès lui-même :
la preuve système (comptes Unix, permissions) est dans tests/e2e/isolation_agents.py sur le banc.
"""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from arpagona_api.agents import AgentProfile, AgentRegistry
from arpagona_api.hermes import HermesClient
from arpagona_api.kanban import KanbanClient
from arpagona_api.server import App, make_handler
from arpagona_api.store import Store
from test_api import Client, FakeEngine

PW = {"mael": "mot-de-passe-mael-1", "thibaud": "mot-de-passe-thibaud-1", "orphelin": "mot-de-passe-orphelin-1"}


class FakeBridge:
    """Passerelle Kanban fictive : une liste de cartes par propriétaire, jeton obligatoire."""

    def __init__(self, token, cards):
        self.cards = list(cards)
        self.calls = []
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
                if self.headers.get("X-Arpagona-Service") != token:
                    payload, status = {"error": "service non autorisé"}, 401
                else:
                    op = self.path.removeprefix("/kanban/")
                    bridge.calls.append((op, body))
                    if op == "create":
                        bridge.cards.append({"id": f"t_{len(bridge.cards):08x}", "title": body["title"]})
                        payload, status = bridge.cards[-1], 200
                    elif op == "list":
                        payload, status = bridge.cards, 200
                    else:
                        payload, status = {"status": "ok"}, 200
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "web").mkdir()
        (root / "web" / "index.html").write_text("<title>x</title>", encoding="utf-8")
        self.engines = {"mael": FakeEngine(), "thibaud": FakeEngine()}
        self.bridges = {"mael": FakeBridge("kb-mael", [{"id": "t_00000001", "title": "[MAËL] relance fictive"}]),
                        "thibaud": FakeBridge("kb-thibaud", [{"id": "t_00000002", "title": "[THIBAUD] devis fictif"}])}
        profiles = {
            login: AgentProfile(login, HermesClient(self.engines[login].url, "cle-de-test"),
                                KanbanClient(f"kb-{login}", self.bridges[login].url), f"outils-{login}")
            for login in ("mael", "thibaud")}
        self.store = Store(str(root / "t.db"))
        for login, password in PW.items():
            self.store.add_user(login, login.capitalize(), password)
        self.app = App(self.store, HermesClient("http://127.0.0.1:9", "cle"), root / "web", False)
        self.app.agents = AgentRegistry(profiles)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        for engine in self.engines.values():
            engine.server.shutdown()
            engine.server.server_close()
        for bridge in self.bridges.values():
            bridge.stop()
        self.store.close()
        self.tmp.cleanup()

    def client(self, login):
        client = Client(self.port)
        self.assertEqual(client.login(login, PW[login]), 200)
        return client

    def test_chaque_compte_atteint_son_moteur(self):
        mael, thibaud = self.client("mael"), self.client("thibaud")
        self.assertEqual(mael.call("POST", "/api/chat", {"text": "bonjour de Maël"})[0], 200)
        self.assertEqual(len(self.engines["mael"].runs), 1)
        self.assertEqual(self.engines["thibaud"].runs, {})
        self.assertEqual(thibaud.call("POST", "/api/chat", {"text": "bonjour de Thibaud"})[0], 200)
        self.assertEqual(len(self.engines["thibaud"].runs), 1)
        self.assertEqual(len(self.engines["mael"].runs), 1)
        self.assertFalse(set(self.engines["mael"].sessions) & set(self.engines["thibaud"].sessions))

    def test_kanban_filtre_par_proprietaire(self):
        mael, thibaud = self.client("mael"), self.client("thibaud")
        titles = lambda c: [x["title"] for x in json.loads(c.call("GET", "/api/kanban/list")[1])]
        self.assertEqual(titles(mael), ["[MAËL] relance fictive"])
        self.assertEqual(titles(thibaud), ["[THIBAUD] devis fictif"])
        mael.call("POST", "/api/kanban/create", {"title": "[MAËL] carte créée"})
        self.assertIn("[MAËL] carte créée", titles(mael))
        self.assertNotIn("[MAËL] carte créée", titles(thibaud))
        self.assertEqual([op for op, _ in self.bridges["thibaud"].calls], ["list", "list"])

    def test_compte_sans_agent_refuse_net(self):
        orphan = self.client("orphelin")
        status, _, _ = orphan.call("POST", "/api/chat", {"text": "bonjour"})
        self.assertEqual(status, 503)
        self.assertEqual(orphan.call("GET", "/api/kanban/list")[0], 503)
        self.assertTrue(all(not e.runs for e in self.engines.values()))
        self.assertTrue(all(not b.calls for b in self.bridges.values()))

    def internal(self, token, session, path="/internal/engagements"):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path, headers={"X-Arpagona-Service": token, "X-Hermes-Session": session})
        status = conn.getresponse().status
        conn.close()
        return status

    def test_jeton_d_outils_limite_a_son_proprietaire(self):
        mael = self.client("mael")
        mael.call("POST", "/api/chat", {"text": "bonjour"})
        mael_session = self.store.conversation_for(self.store.check_password("mael", PW["mael"])["id"])["hermes_session_id"]
        self.assertEqual(self.internal("outils-mael", mael_session), 200)
        # L'agent de Thibaud connaît la session de Maël : refusé quand même.
        self.assertEqual(self.internal("outils-thibaud", mael_session), 401)
        self.assertEqual(self.internal("jeton-inconnu", mael_session), 401)
        # Un ancien jeton commun ne marche plus quand le registre est actif.
        self.app.service_token = "commun"
        self.assertEqual(self.internal("commun", mael_session), 401)

    def test_registre_refuse_jeton_partage(self):
        a = AgentProfile("a", HermesClient("http://x", "k"), KanbanClient("t"), "meme")
        b = AgentProfile("b", HermesClient("http://x", "k"), KanbanClient("t"), "meme")
        with self.assertRaises(ValueError):
            AgentRegistry({"a": a, "b": b})

    def test_chargement_depuis_fichiers(self):
        root = Path(self.tmp.name)
        for name, value in (("hk", "cle"), ("kt", "kjeton"), ("st", "sjeton")):
            (root / name).write_text(value + "\n", encoding="ascii")
        conf = root / "agents.json"
        conf.write_text(json.dumps({"agents": {"mael": {
            "hermes_url": "http://127.0.0.1:1", "hermes_key_file": str(root / "hk"),
            "kanban_url": "http://127.0.0.1:2", "kanban_token_file": str(root / "kt"),
            "service_token_file": str(root / "st")}}}), encoding="utf-8")
        registry = AgentRegistry.load(conf)
        self.assertEqual(registry.logins(), ["mael"])
        self.assertEqual(registry.owner_of_token("sjeton"), "mael")
        self.assertIsNone(registry.owner_of_token("autre"))


if __name__ == "__main__":
    unittest.main()
