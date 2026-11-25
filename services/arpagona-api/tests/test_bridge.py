import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from arpagona_api import bridge_token
from arpagona_api.hermes import HermesClient
from arpagona_api.server import App, make_handler
from arpagona_api.store import Store

KEY = b"k" * 40
ALLOWED = {"thibaud"}


class BridgeTokenTest(unittest.TestCase):
    def test_roundtrip(self):
        t = bridge_token.issue(KEY, "thibaud", 100, now=1000)
        self.assertEqual(bridge_token.verify(KEY, t, ALLOWED, now=1050), "thibaud")

    def test_expired(self):
        t = bridge_token.issue(KEY, "thibaud", 100, now=1000)
        self.assertIsNone(bridge_token.verify(KEY, t, ALLOWED, now=1100))

    def test_wrong_key_and_tampering(self):
        t = bridge_token.issue(KEY, "thibaud", 100, now=1000)
        self.assertIsNone(bridge_token.verify(b"x" * 40, t, ALLOWED, now=1010))
        body, sig = t.split(".")
        forged = bridge_token._b64(b"mael|9999999999") + "." + sig
        self.assertIsNone(bridge_token.verify(KEY, forged, {"mael", "thibaud"}, now=1010))
        self.assertIsNone(bridge_token.verify(KEY, "n'importe quoi", ALLOWED))
        self.assertIsNone(bridge_token.verify(KEY, "", ALLOWED))

    def test_login_not_allowed_is_refused(self):
        t = bridge_token.issue(KEY, "mael", 100, now=1000)
        self.assertIsNone(bridge_token.verify(KEY, t, ALLOWED, now=1010))

    def test_short_key_and_bad_login(self):
        with self.assertRaises(ValueError):
            bridge_token.issue(b"court", "thibaud", 10)
        with self.assertRaises(ValueError):
            bridge_token.issue(KEY, "a|b", 10)


class BridgeCookieTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        static = Path(self.tmp.name) / "web"
        static.mkdir()
        (static / "index.html").write_text("x", encoding="utf-8")
        self.store = Store(str(Path(self.tmp.name) / "t.db"))
        self.store.add_user("thibaud", "Thibaud", "mot-de-passe-thibaud")
        self.store.add_user("mael", "Maël", "mot-de-passe-mael-ok")
        self.app = App(self.store, HermesClient("http://127.0.0.1:1", "k"), static, cookie_secure=False)
        self.app.bridge_key = KEY
        self.app.bridge_logins = set(ALLOWED)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.store.close()
        self.tmp.cleanup()

    def _post(self, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request("POST", path, json.dumps(body),
                     {"Content-Type": "application/json", "X-Arpagona": "1"})
        resp = conn.getresponse()
        resp.read()
        cookies = resp.msg.get_all("Set-Cookie") or []
        conn.close()
        return resp.status, cookies

    def test_thibaud_receives_bridge_cookie_valid_90_days(self):
        status, cookies = self._post("/api/login", {"login": "thibaud", "password": "mot-de-passe-thibaud"})
        self.assertEqual(status, 200)
        bridge = [c for c in cookies if c.startswith(bridge_token.COOKIE + "=")]
        self.assertEqual(len(bridge), 1)
        self.assertIn("Max-Age=7776000", bridge[0])
        self.assertIn("HttpOnly", bridge[0])
        value = bridge[0].split(";")[0].split("=", 1)[1]
        self.assertEqual(bridge_token.verify(KEY, value, ALLOWED), "thibaud")
        self.assertTrue(any(c.startswith("arpagona_session=") for c in cookies))

    def test_mael_never_receives_bridge_cookie(self):
        status, cookies = self._post("/api/login", {"login": "mael", "password": "mot-de-passe-mael-ok"})
        self.assertEqual(status, 200)
        self.assertFalse(any(c.startswith(bridge_token.COOKIE + "=") for c in cookies))
        self.assertTrue(any(c.startswith("arpagona_session=") for c in cookies))

    def test_wrong_password_gives_no_cookie(self):
        status, cookies = self._post("/api/login", {"login": "thibaud", "password": "faux-faux-faux"})
        self.assertEqual(status, 401)
        self.assertEqual(cookies, [])

    def test_bridge_disabled_without_key(self):
        self.app.bridge_key = b""
        status, cookies = self._post("/api/login", {"login": "thibaud", "password": "mot-de-passe-thibaud"})
        self.assertEqual(status, 200)
        self.assertFalse(any(c.startswith(bridge_token.COOKIE + "=") for c in cookies))

    def _me(self, login, password):
        _, cookies = self._post("/api/login", {"login": login, "password": password})
        sess = [c.split(";")[0] for c in cookies if c.startswith("arpagona_session=")][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request("GET", "/api/me", headers={"Cookie": sess})
        data = json.loads(conn.getresponse().read())
        conn.close()
        return data

    def test_me_exposes_gona_switch_only_for_thibaud(self):
        self.assertTrue(self._me("thibaud", "mot-de-passe-thibaud").get("gona"))
        self.assertNotIn("gona", self._me("mael", "mot-de-passe-mael-ok"))

    def test_me_has_no_switch_when_bridge_disabled(self):
        self.app.bridge_key = b""
        self.assertNotIn("gona", self._me("thibaud", "mot-de-passe-thibaud"))

    def _me(self, login, password):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request("POST", "/api/login", json.dumps({"login": login, "password": password}),
                     {"Content-Type": "application/json", "X-Arpagona": "1"})
        r = conn.getresponse()
        r.read()
        session = [c.split(";")[0] for c in r.msg.get_all("Set-Cookie") if c.startswith("arpagona_session=")][0]
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request("GET", "/api/me", headers={"Cookie": session})
        r = conn.getresponse()
        body = json.loads(r.read())
        conn.close()
        return body

    def test_me_shows_switch_for_thibaud_only(self):
        self.assertTrue(self._me("thibaud", "mot-de-passe-thibaud").get("gona"))
        self.assertNotIn("gona", self._me("mael", "mot-de-passe-mael-ok"))

    def test_me_hides_switch_when_bridge_disabled(self):
        self.app.bridge_key = b""
        self.assertNotIn("gona", self._me("thibaud", "mot-de-passe-thibaud"))

    def test_logout_clears_both_cookies(self):
        _, cookies = self._post("/api/logout", {})
        names = {c.split("=")[0] for c in cookies}
        self.assertEqual(names, {"arpagona_session", bridge_token.COOKIE})
        self.assertTrue(all("Max-Age=0" in c for c in cookies))


if __name__ == "__main__":
    unittest.main()
