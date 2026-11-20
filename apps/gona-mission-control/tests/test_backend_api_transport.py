import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from backend_api import HermesClient, HermesError


class FakeHermes(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append((self.path, data, self.headers.get('Idempotency-Key')))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'run_id': 'run_1'} if self.path == '/v1/runs' else {'ok': True}).encode())

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        if self.path.endswith('/events'):
            self.wfile.write(b'data: {"event":"message.delta","delta":"bonjour"}\n\ndata: {"event":"run.completed"}\n\n')
        else:
            self.wfile.write(b'{"status":"completed","output":"bonjour"}')


class TransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeHermes)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = HermesClient('http://127.0.0.1:%d' % cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_transport_run_events_and_stop(self):
        self.assertEqual(self.client.start_run('salut', 'session_1', 'stable-1'), 'run_1')
        self.assertEqual(FakeHermes.calls[-1], ('/v1/runs', {'input': 'salut', 'session_id': 'session_1'}, 'stable-1'))
        self.assertEqual(self.client.status('run_1')['output'], 'bonjour')
        self.assertEqual([e['event'] for e in self.client.events('run_1')], ['message.delta', 'run.completed'])
        self.assertTrue(self.client.stop('run_1')['ok'])
        self.assertEqual(FakeHermes.calls[-1][0], '/v1/runs/run_1/stop')

    def test_invalid_run_id_refused(self):
        with self.assertRaises(HermesError):
            self.client.status('../other')

    def test_unreachable_is_readable(self):
        s = ThreadingHTTPServer(('127.0.0.1', 0), FakeHermes)
        port = s.server_port
        s.server_close()
        with self.assertRaisesRegex(HermesError, 'injoignable'):
            HermesClient('http://127.0.0.1:%d' % port, timeout=1).status('run_1')

    def test_missing_key_is_readable(self):
        with self.assertRaisesRegex(HermesError, 'Clé du moteur inaccessible'):
            HermesClient('http://127.0.0.1', '/no/such/key').status('run_1')


if __name__ == '__main__':
    unittest.main()
