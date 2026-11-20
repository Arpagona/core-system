import http.client, http.server, json, os, sys, tempfile, threading, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tok = tempfile.NamedTemporaryFile('w', suffix='.token', delete=False); _tok.write('fixture-token'); _tok.close()
os.environ.setdefault('GONA_MC_TOKEN_FILE', _tok.name); os.environ.setdefault('GONA_MC_LEGACY_TOKEN_FILE', _tok.name)
import backend_api, server
from unittest.mock import patch


class FakeHermes(http.server.BaseHTTPRequestHandler):
    runs = {}; keys = {}; started = 0; fail = False; slow = threading.Event()
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0')); body = json.loads(self.rfile.read(n) or b'{}')
        if self.path == '/v1/runs':
            if FakeHermes.fail: return self._json({'error': 'x'}, 500)
            key = self.headers.get('Idempotency-Key')
            if key in FakeHermes.keys: return self._json({'run_id': FakeHermes.keys[key]})
            FakeHermes.started += 1; rid = 'run_%d' % FakeHermes.started
            FakeHermes.keys[key] = rid; FakeHermes.runs[rid] = {'input': body['input'], 'session': body['session_id'], 'status': 'running'}
            return self._json({'run_id': rid})
        if self.path.endswith('/stop'):
            FakeHermes.runs[self.path.split('/')[3]]['status'] = 'cancelled'; FakeHermes.slow.set()
            return self._json({'status': 'stopping'})
        self._json({}, 404)
    def do_GET(self):
        parts = self.path.split('/')
        rid = parts[3]; run = FakeHermes.runs[rid]
        if self.path.endswith('/events'):
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
            def ev(o): self.wfile.write(('data: ' + json.dumps(o) + '\n\n').encode()); self.wfile.flush()
            ev({'event': 'tool.started', 'tool': 'search', 'preview': 'q'}); ev({'event': 'tool.completed', 'tool': 'search'})
            ev({'event': 'message.delta', 'delta': 'Bon'})
            if run['input'].startswith('lent'):
                FakeHermes.slow.wait(5)
                return
            ev({'event': 'message.delta', 'delta': 'jour'})
            run['status'] = 'completed'; run['output'] = 'Bonjour ' + run['input']
            return
        self._json({'status': run['status'], 'output': run.get('output', '')})


class ApiBackendTests(unittest.TestCase):
    def setUp(self):
        FakeHermes.runs = {}; FakeHermes.keys = {}; FakeHermes.started = 0; FakeHermes.fail = False; FakeHermes.slow = threading.Event()
        self.fake = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeHermes)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'chat.db'
        self.new_backend()
    def new_backend(self):
        self.be = backend_api.ApiBackend(self.db, backend_api.HermesClient('http://127.0.0.1:%d' % self.fake.server_port), 'gpt5')
    def tearDown(self):
        self.fake.shutdown(); self.fake.server_close(); self.tmp.cleanup()
    def wait(self, sid, sub, state='ready', t=8):
        end = time.time() + t
        while time.time() < end:
            if self.be.reply(sid, sub)['state'] == state: return
            time.sleep(0.05)
        self.fail('état %s non atteint : %s' % (state, self.be.reply(sid, sub)))

    def test_send_stream_history_and_idempotence(self):
        sid = self.be.active_id(); q, live = self.be.subscribe(sid); self.assertFalse(live['running'])
        self.assertEqual(self.be.reply(sid, 'imac-mc-abcdefgh')['state'], 'waiting')
        self.assertEqual(self.be.send(sid, 'salut', 'imac-mc-abcdefgh')['state'], 'queued')
        self.assertEqual(self.be.send(sid, 'salut', 'imac-mc-abcdefgh')['state'], 'duplicate')
        self.wait(sid, 'imac-mc-abcdefgh')
        self.assertEqual(FakeHermes.started, 1)
        types = []
        while not q.empty(): types.append(q.get()['type'])
        self.assertEqual(types[0], 'writing'); self.assertIn('tool', types); self.assertIn('tool_done', types)
        self.assertIn('delta', types); self.assertEqual(types[-1], 'complete')
        msgs = self.be.messages(sid)['messages']
        self.assertEqual([m['role'] for m in msgs], ['user', 'assistant']); self.assertEqual(msgs[1]['text'], 'Bonjour salut')
        self.assertTrue(all(m['ts'] for m in msgs))

    def test_session_kept_and_new_conversation(self):
        sid = self.be.active_id(); self.be.send(sid, 'un', 'imac-mc-00000001'); self.wait(sid, 'imac-mc-00000001')
        self.be.send(sid, 'deux', 'imac-mc-00000002'); self.wait(sid, 'imac-mc-00000002')
        sessions = {r['session'] for r in FakeHermes.runs.values()}; self.assertEqual(len(sessions), 1)
        r = self.be.command(sid, '/new'); self.assertEqual(r['kind'], 'new'); self.assertNotEqual(r['new_session_id'], sid)
        self.assertEqual(self.be.active_id(), r['new_session_id']); self.assertEqual(self.be.messages(r['new_session_id'])['messages'], [])
        with self.assertRaises(ValueError): self.be.valid(sid)
        self.be.send(r['new_session_id'], 'trois', 'imac-mc-00000003'); self.wait(r['new_session_id'], 'imac-mc-00000003')
        self.assertEqual(len({x['session'] for x in FakeHermes.runs.values()}), 2)

    def test_stop(self):
        sid = self.be.active_id(); self.be.send(sid, 'lent', 'imac-mc-00000010')
        end = time.time() + 5
        while time.time() < end and not (self.be._live.get(sid) or {}).get('run_id'): time.sleep(0.05)
        self.assertTrue(self.be.command(sid, '/stop')['ok']); self.wait(sid, 'imac-mc-00000010')
        self.assertEqual(self.be.messages(sid)['messages'][-1]['role'], 'assistant')

    def test_engine_down_is_readable_not_stuck(self):
        FakeHermes.fail = True; sid = self.be.active_id(); self.be.send(sid, 'x', 'imac-mc-00000020'); self.wait(sid, 'imac-mc-00000020')
        self.assertIn('indisponible', self.be.messages(sid)['messages'][-1]['text'])

    def test_restart_does_not_replay(self):
        sid = self.be.active_id(); self.be.send(sid, 'a', 'imac-mc-00000030'); self.wait(sid, 'imac-mc-00000030')
        self.new_backend()
        self.assertEqual(self.be.active_id(), sid); self.assertEqual(len(self.be.messages(sid)['messages']), 2)
        self.assertEqual(self.be.send(sid, 'a', 'imac-mc-00000030')['state'], 'duplicate'); self.assertEqual(FakeHermes.started, 1)

    def test_unsupported_commands_honest(self):
        sid = self.be.active_id()
        for c in ('/model', '/reasoning high', '/restart'):
            r = self.be.command(sid, c); self.assertFalse(r['ok']); self.assertIn('pas pris en charge', r['error'])
        self.assertTrue(self.be.command(sid, '/help')['ok']); self.assertTrue(self.be.command(sid, '/status')['ok'])


class ApiServerTests(ApiBackendTests):
    """Même backend derrière le vrai serveur HTTP (mode GONA_MC_BACKEND=api)."""
    def setUp(self):
        super().setUp()
        self.ps = [patch.object(server, 'API', self.be), patch.object(server, 'TOKEN', 'fixture-token'), patch.object(server, 'COOKIE', 'c')]
        for p in self.ps: p.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
    def tearDown(self):
        self.http.shutdown(); self.http.server_close()
        for p in reversed(self.ps): p.stop()
        super().tearDown()
    def req(self, path, body=None):
        c = http.client.HTTPConnection('127.0.0.1', self.http.server_port)
        c.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), {'X-MC-Token': 'fixture-token', 'X-Gona': '1'})
        r = c.getresponse(); raw = r.read(); c.close(); return r.status, json.loads(raw)
    def test_http_chat_flow(self):
        st, ch = self.req('/api/channels'); sid = ch['channels'][0]['session']; self.assertEqual(st, 200)
        self.assertEqual(self.req('/api/me')[1]['backend'], 'api')
        self.assertEqual(self.req('/api/chat', {'id': sid, 'text': 'salut', 'submission_id': 'imac-mc-http0001'})[0], 200)
        self.wait(sid, 'imac-mc-http0001')
        self.assertEqual(self.req('/api/channel/reply?id=%s&submission=imac-mc-http0001' % sid)[1]['state'], 'ready')
        self.assertEqual(self.req('/api/channel/messages?id=' + sid)[1]['messages'][-1]['text'], 'Bonjour salut')
        st, r = self.req('/api/command', {'id': sid, 'command': '/new'}); self.assertEqual(r['kind'], 'new')
        st, r = self.req('/api/chat', {'id': sid, 'text': 'x', 'submission_id': 'imac-mc-http0002'}); self.assertEqual(st, 400)
        self.assertIn('Session active', r['error'])
    def test_http_sse_stream(self):
        sid = self.be.active_id(); got = []
        def reader():
            c = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=10)
            c.request('GET', '/api/stream?id=' + sid, headers={'X-MC-Token': 'fixture-token'})
            r = c.getresponse()
            for line in r:
                if line.startswith(b'data:'):
                    got.append(json.loads(line[5:]))
                    if got[-1]['type'] == 'complete': break
            c.close()
        t = threading.Thread(target=reader); t.start(); time.sleep(0.5)
        self.be.send(sid, 'sse', 'imac-mc-sse00001'); t.join(10)
        self.assertEqual(got[0]['type'], 'snapshot'); self.assertEqual(got[-1]['type'], 'complete'); self.assertEqual(got[-1]['text'], 'Bonjour sse')

if __name__ == '__main__':
    unittest.main()
