"""Deux zones : chaque compte n'atteint que SON moteur et SES outils (privé) ; le Kanban d'entreprise est commun,
avec un responsable par carte (visible de tous, décidé par le seul responsable).

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
                        bridge.cards.append({"id": f"t_{len(bridge.cards) + 1:08x}", "title": body["title"],
                                             "assignee": body.get("assignee"), "created_by": body.get("created_by"),
                                             "status": "ready", "comments": []})
                        payload, status = bridge.cards[-1], 200
                    elif op == "list":
                        payload, status = bridge.cards, 200
                    elif op == "show":
                        card = next((c for c in bridge.cards if c["id"] == body.get("id")), None)
                        payload, status = ({"task": card}, 200) if card else ({"error": "inconnue"}, 404)
                    else:
                        card = next((c for c in bridge.cards if c["id"] == body.get("id")), {})
                        if op == "assign":
                            card["assignee"] = body["assignee"]
                        elif op == "comment":
                            card.setdefault("comments", []).append({"author": body.get("author"), "text": body.get("text")})
                        elif op in ("complete", "unblock", "block", "archive"):
                            card["status"] = {"complete": "done", "unblock": "ready", "block": "blocked",
                                              "archive": "archived"}[op]
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
        # Un seul Kanban d'entreprise ; cartes existantes (une sans responsable, une par personne).
        self.bridge = FakeBridge("kb-equipe", [
            {"id": "t_00000001", "title": "[MAËL] relance fictive", "assignee": "mael", "status": "ready"},
            {"id": "t_00000002", "title": "[THIBAUD] devis fictif", "assignee": "thibaud", "status": "ready"},
            {"id": "t_00000003", "title": "Décision : valider le devis 4417", "assignee": "thibaud", "status": "blocked"},
            {"id": "t_00000004", "title": "[DEMO] carte ancienne", "assignee": None, "status": "ready"}])
        profiles = {
            login: AgentProfile(login, HermesClient(self.engines[login].url, "cle-de-test"), f"outils-{login}")
            for login in ("mael", "thibaud")}
        self.store = Store(str(root / "t.db"))
        for login, password in PW.items():
            self.store.add_user(login, login.capitalize(), password)
        self.app = App(self.store, HermesClient("http://127.0.0.1:9", "cle"), root / "web", False)
        self.app.agents = AgentRegistry(profiles)
        self.app.kanban = KanbanClient("kb-equipe", self.bridge.url)
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
        self.bridge.stop()
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

    def cards(self, client, scope=""):
        status, raw, _ = client.call("GET", "/api/kanban/list" + (f"?scope={scope}" if scope else ""))
        self.assertEqual(status, 200)
        return json.loads(raw)

    def test_kanban_commun_visible_des_deux_avec_responsables(self):
        mael, thibaud = self.client("mael"), self.client("thibaud")
        for c in (mael, thibaud):
            cards = self.cards(c)
            self.assertEqual(len(cards), 4)  # même tableau, aucune carte perdue ni dupliquée
            self.assertEqual({x["id"]: x["assignee"] for x in cards}["t_00000003"], "thibaud")
        self.assertEqual([x["id"] for x in self.cards(mael, "mine")], ["t_00000001"])
        self.assertEqual(sorted(x["id"] for x in self.cards(thibaud, "mine")), ["t_00000002", "t_00000003"])
        self.assertTrue(all(x["mine"] == (x["assignee"] == "mael") for x in self.cards(mael)))
        # Carte créée par Maël : responsable par défaut = Maël, auteur conservé, visible de Thibaud.
        self.assertEqual(mael.call("POST", "/api/kanban/create", {"title": "Nouvelle carte"})[0], 200)
        created = [x for x in self.cards(thibaud) if x["title"] == "Nouvelle carte"]
        self.assertEqual((created[0]["assignee"], created[0]["created_by"]), ("mael", "mael"))
        self.assertEqual(len([x for x in self.cards(mael) if x["title"] == "Nouvelle carte"]), 1)
        # Responsable choisi dans l'équipe seulement ; l'auteur ne vient pas du navigateur.
        status, _, _ = mael.call("POST", "/api/kanban/create", {"title": "Pour Thibaud", "assignee": "thibaud", "created_by": "thibaud"})
        self.assertEqual(status, 200)
        card = [x for x in self.cards(mael) if x["title"] == "Pour Thibaud"][0]
        self.assertEqual((card["assignee"], card["created_by"]), ("thibaud", "mael"))
        self.assertEqual(mael.call("POST", "/api/kanban/create", {"title": "x", "assignee": "intrus"})[0], 400)

    def test_decision_visible_mais_seul_le_responsable_approuve(self):
        mael, thibaud = self.client("mael"), self.client("thibaud")
        decision = "t_00000003"
        shown = json.loads(mael.call("GET", f"/api/kanban/show?id={decision}")[1])
        self.assertEqual(shown["task"]["title"], "Décision : valider le devis 4417")  # visible
        self.assertFalse(shown["task"]["can_decide"])
        for op in ("complete", "unblock", "block", "archive"):
            self.assertEqual(mael.call("POST", f"/api/kanban/{op}", {"id": decision, "text": "x"})[0], 403, op)
        self.assertEqual(mael.call("POST", "/api/kanban/assign", {"id": decision, "assignee": "mael"})[0], 403)
        self.assertEqual(next(c for c in self.bridge.cards if c["id"] == decision)["status"], "blocked")
        self.assertEqual(next(c for c in self.bridge.cards if c["id"] == decision)["assignee"], "thibaud")
        # Commenter reste ouvert, avec l'auteur du compte connecté.
        self.assertEqual(mael.call("POST", "/api/kanban/comment", {"id": decision, "text": "avis de Maël", "author": "Thibaud"})[0], 200)
        self.assertEqual(self.bridge.cards[2]["comments"][0]["author"], "Mael")
        # Le responsable décide.
        self.assertEqual(thibaud.call("POST", "/api/kanban/unblock", {"id": decision})[0], 200)
        self.assertEqual(self.bridge.cards[2]["status"], "ready")
        # Carte sans responsable : aucune décision tant qu'elle n'est pas affectée ; on la rattache, puis son responsable décide.
        self.assertEqual(thibaud.call("POST", "/api/kanban/complete", {"id": "t_00000004"})[0], 403)
        self.assertEqual(mael.call("POST", "/api/kanban/archive", {"id": "t_00000004"})[0], 403)
        self.assertEqual(mael.call("POST", "/api/kanban/assign", {"id": "t_00000004", "assignee": "mael"})[0], 200)
        self.assertEqual(thibaud.call("POST", "/api/kanban/complete", {"id": "t_00000004"})[0], 403)
        self.assertEqual(mael.call("POST", "/api/kanban/complete", {"id": "t_00000004"})[0], 200)

    def test_compte_sans_agent_refuse_net(self):
        orphan = self.client("orphelin")
        status, _, _ = orphan.call("POST", "/api/chat", {"text": "bonjour"})
        self.assertEqual(status, 503)
        self.assertEqual(orphan.call("GET", "/api/kanban/list")[0], 503)
        self.assertEqual(orphan.call("POST", "/api/kanban/create", {"title": "x"})[0], 503)
        self.assertTrue(all(not e.runs for e in self.engines.values()))
        self.assertEqual(self.bridge.calls, [])

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
        a = AgentProfile("a", HermesClient("http://x", "k"), "meme")
        b = AgentProfile("b", HermesClient("http://x", "k"), "meme")
        with self.assertRaises(ValueError):
            AgentRegistry({"a": a, "b": b})

    def test_chargement_depuis_fichiers(self):
        root = Path(self.tmp.name)
        for name, value in (("hk", "cle"), ("st", "sjeton")):
            (root / name).write_text(value + "\n", encoding="ascii")
        conf = root / "agents.json"
        conf.write_text(json.dumps({"agents": {"mael": {
            "hermes_url": "http://127.0.0.1:1", "hermes_key_file": str(root / "hk"),
            "service_token_file": str(root / "st")}}}), encoding="utf-8")
        registry = AgentRegistry.load(conf)
        self.assertEqual(registry.logins(), ["mael"])
        self.assertEqual(registry.owner_of_token("sjeton"), "mael")
        self.assertIsNone(registry.owner_of_token("autre"))


if __name__ == "__main__":
    unittest.main()
