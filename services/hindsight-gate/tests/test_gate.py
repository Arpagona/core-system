import hashlib
import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gate


class Upstream:
    def __init__(self):
        self.seen = []
        up = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def _all(self):
                n = int(self.headers.get("Content-Length") or 0)
                up.seen.append((self.command, self.path, self.headers.get("Authorization"), self.rfile.read(n)))
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_DELETE = _all

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


def start_gate(upstream_url, name, bank, token):
    tenant = gate.Tenant(name, bank, hashlib.sha256(token.encode()).hexdigest())
    server = ThreadingHTTPServer(("127.0.0.1", 0), gate.make_handler(tenant, upstream_url, "cle-amont"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def call(server, method, path, token, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, json.dumps(body) if body is not None else None, headers)
    status = conn.getresponse().status
    conn.close()
    return status


class GateTest(unittest.TestCase):
    def setUp(self):
        self.up = Upstream()
        self.mael = start_gate(self.up.url, "mael", "arpagona-mael", "jeton-mael")
        self.thibaud = start_gate(self.up.url, "thibaud", "arpagona-thibaud", "jeton-thibaud")

    def tearDown(self):
        for s in (self.mael, self.thibaud, self.up.server):
            s.shutdown()
            s.server_close()

    def test_sa_banque_passe_avec_la_cle_amont(self):
        self.assertEqual(call(self.mael, "POST", "/v1/default/banks/arpagona-mael/memories", "jeton-mael", {"items": []}), 200)
        method, path, auth, _ = self.up.seen[-1]
        self.assertEqual(auth, "Bearer cle-amont")  # la clé de l'utilisateur ne va jamais en amont, ni l'inverse
        self.assertEqual(path, "/v1/default/banks/arpagona-mael/memories")

    def test_banque_de_l_autre_refusee(self):
        before = len(self.up.seen)
        for path in ("/v1/default/banks/arpagona-thibaud/memories/recall",
                     "/v1/default/banks/arpagona-thibaud",
                     "/v1/default/banks/arpagona-mael-bis/memories",
                     "/v1/default/banks",
                     "/v1/default/banks/arpagona-mael/../arpagona-thibaud/memories",
                     "/v1/default/banks/arpagona-mael/%2e%2e/arpagona-thibaud/memories",
                     "/v1/default/banks//arpagona-thibaud/memories",
                     "/v1/default/banks/arpagona-mael%2f..%2farpagona-thibaud"):
            self.assertEqual(call(self.mael, "POST", path, "jeton-mael", {}), 403, path)
        self.assertEqual(len(self.up.seen), before)

    def test_jeton_de_l_autre_refuse(self):
        self.assertEqual(call(self.mael, "GET", "/v1/default/banks/arpagona-mael/stats", "jeton-thibaud"), 401)
        self.assertEqual(call(self.mael, "GET", "/v1/default/banks/arpagona-mael/stats", None), 401)
        self.assertEqual(call(self.thibaud, "GET", "/v1/default/banks/arpagona-mael/stats", "jeton-mael"), 401)
        self.assertEqual(self.up.seen, [])

    def test_banque_invalide_refusee_a_la_creation(self):
        with self.assertRaises(ValueError):
            gate.Tenant("x", "../autre", "00")

    def test_sante_sans_banque(self):
        self.assertEqual(call(self.mael, "GET", "/health", "jeton-mael"), 200)


if __name__ == "__main__":
    unittest.main()
