"""Tests de l'API ARPAGONA contre un FAUX moteur local.

Ces tests vérifient l'authentification, la séparation des utilisateurs et le relais.
Ils ne prouvent rien sur Hermès lui-même : la recette réelle se fait sur le banc Atlas.
"""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from arpagona_api.hermes import HermesClient
from arpagona_api.server import App, make_handler
from arpagona_api.store import Store

PASSWORD_A = "mot-de-passe-fictif-A"
PASSWORD_B = "mot-de-passe-fictif-B"


class FakeEngine:
    """Faux moteur : répond « écho : <texte> » et note les identifiants de session reçus."""

    def __init__(self):
        self.runs = {}
        self.sessions = []
        self.keys = []
        engine = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _send(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.headers.get("Authorization") != "Bearer cle-de-test":
                    return self._send(401, {})
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                run_id = f"run_{len(engine.runs) + 1}"
                engine.runs[run_id] = "écho : " + data["input"]
                engine.sessions.append(data["session_id"])
                engine.keys.append(self.headers.get("Idempotency-Key"))
                self._send(202, {"run_id": run_id, "status": "started"})

            def do_GET(self):
                run_id = self.path.split("/")[3]
                if self.path.endswith("/events"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for part in ("écho", " : …"):
                        self.wfile.write(("data: " + json.dumps({"event": "message.delta", "delta": part}) + "\n\n").encode())
                    return
                self._send(200, {"run_id": run_id, "status": "completed", "output": engine.runs[run_id]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


class Client:
    def __init__(self, port):
        self.port = port
        self.cookie = None

    def call(self, method, path, body=None, marker=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if marker:
            headers["X-Arpagona"] = "1"
        if self.cookie:
            headers["Cookie"] = self.cookie
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        set_cookie = resp.getheader("Set-Cookie")
        if set_cookie:
            self.cookie = set_cookie.split(";")[0]
        conn.close()
        return resp.status, raw, set_cookie

    def login(self, login, password):
        return self.call("POST", "/api/login", {"login": login, "password": password})[0]


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        static = Path(self.tmp.name) / "web"
        static.mkdir()
        (static / "index.html").write_text("<title>ARPAGONA</title>", encoding="utf-8")
        (Path(self.tmp.name) / "secret.html").write_text("hors racine", encoding="utf-8")
        self.engine = FakeEngine()
        self.store = Store(str(Path(self.tmp.name) / "test.db"))
        self.store.add_user("alice", "Alice Fictive", PASSWORD_A)
        self.store.add_user("bruno", "Bruno Fictif", PASSWORD_B)
        self.app = App(self.store, HermesClient(self.engine.url, "cle-de-test"), static, cookie_secure=False)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.server.shutdown()
        self.engine.server.server_close()
        self.store.close()
        self.tmp.cleanup()

    def test_sans_session_tout_est_refuse(self):
        anon = Client(self.port)
        self.assertEqual(anon.call("GET", "/api/conversation")[0], 401)
        self.assertEqual(anon.call("GET", "/api/me")[0], 401)
        self.assertEqual(anon.call("POST", "/api/chat", {"text": "bonjour"})[0], 401)
        self.assertEqual(self.engine.runs, {})

    def test_mauvais_mot_de_passe_puis_blocage(self):
        anon = Client(self.port)
        for _ in range(5):
            self.assertEqual(anon.login("alice", "faux-mot-de-passe"), 401)
        self.assertEqual(anon.login("alice", PASSWORD_A), 429)

    def test_cookie_protege(self):
        alice = Client(self.port)
        status, _, set_cookie = alice.call("POST", "/api/login", {"login": "alice", "password": PASSWORD_A})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)

    def test_requete_sans_marqueur_refusee(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        self.assertEqual(alice.call("POST", "/api/chat", {"text": "bonjour"}, marker=False)[0], 400)
        self.assertEqual(self.engine.runs, {})

    def test_chat_relaye_et_conserve(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        status, raw, _ = alice.call("POST", "/api/chat", {"text": "bonjour"})
        self.assertEqual(status, 200)
        events = [json.loads(line[6:]) for line in raw.split("\n\n") if line.startswith("data: ")]
        self.assertEqual([e["type"] for e in events], ["start", "delta", "delta", "end"])
        self.assertEqual(events[-1]["status"], "done")
        self.assertEqual(events[-1]["text"], "écho : bonjour")
        messages = json.loads(alice.call("GET", "/api/conversation")[1])["messages"]
        self.assertEqual([(m["role"], m["text"], m["status"]) for m in messages],
                         [("user", "bonjour", "done"), ("assistant", "écho : bonjour", "done")])

    def test_separation_des_utilisateurs(self):
        alice, bruno = Client(self.port), Client(self.port)
        alice.login("alice", PASSWORD_A)
        bruno.login("bruno", PASSWORD_B)
        alice.call("POST", "/api/chat", {"text": "secret d'Alice", "session_id": "session-choisie-par-le-client"})
        self.assertEqual(json.loads(bruno.call("GET", "/api/conversation")[1])["messages"], [])
        bruno.call("POST", "/api/chat", {"text": "bonjour de Bruno"})
        self.assertEqual(len(set(self.engine.sessions)), 2)
        self.assertTrue(all(s.startswith("arpagona-u") for s in self.engine.sessions))
        self.assertNotIn("session-choisie-par-le-client", self.engine.sessions)
        texts = [m["text"] for m in json.loads(bruno.call("GET", "/api/conversation")[1])["messages"]]
        self.assertNotIn("secret d'Alice", " ".join(texts))

    def test_meme_utilisateur_meme_session_moteur(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        alice.call("POST", "/api/chat", {"text": "un"})
        alice.call("POST", "/api/chat", {"text": "deux"})
        self.assertEqual(len(set(self.engine.sessions)), 1)
        self.assertEqual(len(set(self.engine.keys)), 2)

    def test_reponse_en_attente_reglee_a_la_reconnexion(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        user_id = self.store.check_password("alice", PASSWORD_A)["id"]
        conv = self.store.conversation_for(user_id)
        self.engine.runs["run_x"] = "réponse arrivée pendant l'absence"
        self.store.add_message(conv["id"], "user", "question", "done")
        self.store.add_message(conv["id"], "assistant", "", "pending", "run_x")
        messages = json.loads(alice.call("GET", "/api/conversation")[1])["messages"]
        self.assertEqual((messages[-1]["status"], messages[-1]["text"]), ("done", "réponse arrivée pendant l'absence"))

    def test_moteur_arrete(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        self.engine.server.shutdown()
        self.engine.server.server_close()
        self.assertEqual(alice.call("POST", "/api/chat", {"text": "bonjour"})[0], 502)
        messages = json.loads(alice.call("GET", "/api/conversation")[1])["messages"]
        self.assertEqual(messages[-1]["status"], "failed")

    def test_deconnexion(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        old = alice.cookie
        self.assertEqual(alice.call("POST", "/api/logout", {})[0], 200)
        alice.cookie = old
        self.assertEqual(alice.call("GET", "/api/me")[0], 401)

    def test_fichiers_hors_racine_refuses(self):
        anon = Client(self.port)
        self.assertEqual(anon.call("GET", "/")[0], 200)
        self.assertEqual(anon.call("GET", "/../secret.html")[0], 404)
        self.assertEqual(anon.call("GET", "/%2e%2e/secret.html")[0], 404)
        self.assertEqual(anon.call("GET", "/test.db")[0], 404)

    def test_suppression_de_compte(self):
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        alice.call("POST", "/api/chat", {"text": "bonjour"})
        self.assertTrue(self.store.delete_user("alice"))
        self.assertFalse(self.store.delete_user("alice"))
        self.assertEqual(alice.call("GET", "/api/me")[0], 401)
        self.assertIsNone(self.store.check_password("alice", PASSWORD_A))
        self.assertIsNotNone(self.store.check_password("bruno", PASSWORD_B))

    def test_cle_d_idempotence_unique_apres_suppression(self):
        """Un compte supprimé puis un nouveau compte réutilisent les mêmes numéros de ligne : la clé doit différer."""
        self.store.delete_user("bruno")
        alice = Client(self.port)
        alice.login("alice", PASSWORD_A)
        alice.call("POST", "/api/chat", {"text": "un"})
        self.store.delete_user("alice")
        self.store.add_user("carla", "Carla Fictive", PASSWORD_A)
        carla = Client(self.port)
        carla.login("carla", PASSWORD_A)
        self.assertEqual(carla.call("POST", "/api/chat", {"text": "deux"})[0], 200)
        self.assertEqual(len(self.engine.keys), 2)
        self.assertEqual(len(set(self.engine.keys)), 2)

    def test_kanban_sans_session(self):
        anon = Client(self.port)
        for method, path, body in [('GET', '/api/kanban/list', None),
                                   ('GET', '/api/kanban/show?id=t_16192f3a', None),
                                   ('POST', '/api/kanban/create', {'title': 'Mission'})]:
            self.assertEqual(anon.call(method, path, body)[0], 401)

    def test_kanban_non_configure_chat_preserve(self):
        alice = Client(self.port)
        alice.login('alice', PASSWORD_A)
        self.assertEqual(alice.call('GET', '/api/kanban/list')[0], 503)
        self.assertEqual(alice.call('POST', '/api/kanban/create', {'title': 'Mission'})[0], 503)
        self.assertEqual(alice.call('GET', '/api/conversation')[0], 200)
        self.assertEqual(alice.call('POST', '/api/chat', {'text': 'bonjour'})[0], 200)

    def test_kanban_relais_et_audit(self):
        from unittest.mock import Mock
        self.app.kanban = Mock()
        self.app.kanban.call.return_value = (200, {'status': 'ok'})
        alice = Client(self.port)
        alice.login('alice', PASSWORD_A)
        for path, op, data in [('/api/kanban/list', 'list', {}),
                               ('/api/kanban/show?id=t_16192f3a', 'show', {'id': 't_16192f3a'})]:
            self.assertEqual(alice.call('GET', path)[0], 200)
            self.app.kanban.call.assert_called_with(op, data)
        for op in ('create', 'comment', 'complete', 'block', 'unblock', 'archive'):
            data = {'title': 'Mission'} if op == 'create' else {'id': 't_16192f3a'}
            status, raw, _ = alice.call('POST', '/api/kanban/' + op, data)
            self.assertEqual((status, json.loads(raw)), (200, {'status': 'ok'}))
            self.app.kanban.call.assert_called_with(op, data)
        actions = [row['action'] for row in self.store.audit_rows()]
        self.assertEqual(actions, ['connexion', 'kanban_list', 'kanban_show'] + ['kanban_' + op for op in
                         ('create', 'comment', 'complete', 'block', 'unblock', 'archive')])
        self.assertEqual(alice.call('POST', '/api/kanban/dispatch', {})[0], 400)
        self.assertEqual(alice.call('POST', '/api/kanban/create', {'title': 'x'}, marker=False)[0], 400)

    def test_kanban_erreurs_controlees(self):
        from unittest.mock import Mock
        self.app.kanban = Mock()
        alice = Client(self.port)
        alice.login('alice', PASSWORD_A)
        for status in (400, 502, 503):
            self.app.kanban.call.return_value = (status, {'error': 'indisponible'})
            self.assertEqual(alice.call('GET', '/api/kanban/list')[0], status)
            self.assertEqual(alice.call('POST', '/api/kanban/create', {'title': 'Mission'})[0], status)
        self.assertEqual([row['action'] for row in self.store.audit_rows()],
                         ['connexion'] + ['kanban_list', 'kanban_create'] * 3)

    def test_journal(self):
        alice = Client(self.port)
        alice.login("alice", "faux-mot-de-passe")
        alice.login("alice", PASSWORD_A)
        actions = [row["action"] for row in self.store.audit_rows()]
        self.assertEqual(actions, ["connexion_refusée", "connexion"])


if __name__ == "__main__":
    unittest.main()
