"""Banc d'essai isolé : Mission Control (backend api) + faux moteur Hermes, sur un port dédié.
Aucune donnée réelle : base, jeton et réponses sont jetables. Usage : python3 sandbox.py 8719
Le faux moteur répond « Réponse à : <message> » ; un message commençant par « lent » dure 6 s."""
import http.server, json, os, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
tmp = Path(tempfile.mkdtemp(prefix='mc-sandbox-', dir=os.environ.get('TMPDIR')))
(tmp / 'token').write_text('sandbox-token')
os.environ.update(GONA_MC_BACKEND='api', GONA_MC_DATA_DIR=str(tmp), GONA_MC_TOKEN_FILE=str(tmp / 'token'),
                  GONA_MC_LEGACY_TOKEN_FILE=str(tmp / 'token'), GONA_MC_BRIDGE_KEY_FILE='')

class Fake(http.server.BaseHTTPRequestHandler):
    runs = {}; n = 0
    def log_message(self, *a): pass
    def _json(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
        if self.path == '/v1/runs':
            Fake.n += 1; rid = 'run_%d' % Fake.n
            Fake.runs[rid] = {'input': body.get('input', ''), 'status': 'running'}
            return self._json({'run_id': rid})
        if self.path.endswith('/stop'):
            Fake.runs[self.path.split('/')[3]]['status'] = 'cancelled'; return self._json({'status': 'stopping'})
        self._json({}, 404)
    def do_GET(self):
        parts = self.path.split('/'); rid = parts[3] if len(parts) > 3 else ''; run = Fake.runs.get(rid)
        if run is None: return self._json({'error': 'inconnu'}, 404)
        if self.path.endswith('/events'):
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
            def ev(o): self.wfile.write(('data: ' + json.dumps(o) + '\n\n').encode()); self.wfile.flush()
            ev({'event': 'message.delta', 'delta': 'Je vais chercher dans mes notes. '}); time.sleep(0.3)
            ev({'event': 'tool.started', 'tool': 'web_search', 'preview': 'recherche'})
            time.sleep(0.4); ev({'event': 'tool.completed', 'tool': 'web_search'})
            out = 'Réponse à : ' + run['input'][:200]
            for w in out.split(' '):
                if run['status'] == 'cancelled': return
                ev({'event': 'message.delta', 'delta': w + ' '}); time.sleep(6 / 8 if run['input'].startswith('lent') else 0.05)
            run['status'] = 'completed'; run['output'] = out
            return
        self._json({'status': run['status'], 'output': run.get('output', '')})

fake = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ['GONA_MC_HERMES_URL'] = 'http://127.0.0.1:%d' % fake.server_port
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8719
srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), server.Handler); srv.daemon_threads = True
print('sandbox prêt', port, tmp, flush=True)
srv.serve_forever()
