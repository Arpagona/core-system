import http.client
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tok = tempfile.NamedTemporaryFile('w', suffix='.token', delete=False)
_tok.write('fixture-token')
_tok.close()
os.environ.setdefault('GONA_MC_TOKEN_FILE', _tok.name)
os.environ.setdefault('GONA_MC_LEGACY_TOKEN_FILE', _tok.name)
import server  # noqa: E402
import bridge_token  # noqa: E402

KEY = b'k' * 40


class BridgeAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = (server.BRIDGE_KEY, server.config.BRIDGE_LOGINS)
        server.BRIDGE_KEY = KEY
        server.config.BRIDGE_LOGINS = {'thibaud'}
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        server.BRIDGE_KEY, server.config.BRIDGE_LOGINS = cls.old

    def status(self, cookie=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/api/me', headers={'Cookie': cookie} if cookie else {})
        r = c.getresponse()
        r.read()
        c.close()
        return r.status

    def test_no_cookie_refused(self):
        self.assertEqual(self.status(), 401)

    def test_valid_thibaud_bridge_cookie_accepted(self):
        t = bridge_token.issue(KEY, 'thibaud', 3600)
        self.assertEqual(self.status(f'{bridge_token.COOKIE}={t}'), 200)

    def test_mael_bridge_cookie_refused(self):
        t = bridge_token.issue(KEY, 'mael', 3600)
        self.assertEqual(self.status(f'{bridge_token.COOKIE}={t}'), 401)

    def test_expired_refused(self):
        t = bridge_token.issue(KEY, 'thibaud', 10, now=1000)
        self.assertEqual(self.status(f'{bridge_token.COOKIE}={t}'), 401)

    def test_forged_or_wrong_key_refused(self):
        t = bridge_token.issue(b'z' * 40, 'thibaud', 3600)
        self.assertEqual(self.status(f'{bridge_token.COOKIE}={t}'), 401)
        self.assertEqual(self.status(f'{bridge_token.COOKIE}=abc.def'), 401)

    def test_disabled_without_key(self):
        t = bridge_token.issue(KEY, 'thibaud', 3600)
        server.BRIDGE_KEY = b''
        try:
            self.assertEqual(self.status(f'{bridge_token.COOKIE}={t}'), 401)
        finally:
            server.BRIDGE_KEY = KEY

    def me(self, headers):
        import json
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/api/me', headers=headers)
        r = c.getresponse()
        body = json.loads(r.read())
        c.close()
        return r.status, body

    def test_atlas_switch_only_when_arrived_via_bridge(self):
        t = bridge_token.issue(KEY, 'thibaud', 3600)
        st, body = self.me({'Cookie': f'{bridge_token.COOKIE}={t}'})
        self.assertEqual(st, 200)
        self.assertTrue(body.get('atlas'))
        st, body = self.me({'X-MC-Token': server.TOKEN})
        self.assertEqual(st, 200)
        self.assertNotIn('atlas', body)

    def test_gona_own_token_still_works(self):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('GET', '/api/me', headers={'X-MC-Token': server.TOKEN})
        r = c.getresponse()
        r.read()
        c.close()
        self.assertEqual(r.status, 200)


if __name__ == '__main__':
    unittest.main()
