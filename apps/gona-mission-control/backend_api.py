"""Transport stdlib vers l'API locale Hermes ; non encore branché au serveur MC.

Le fichier de clé n'est lu qu'au moment d'une requête. Aucune URL contenant un
secret, corps de réponse d'erreur ou exception réseau n'est exposée à l'UI.
"""
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


class HermesError(RuntimeError):
    """Erreur présentable sans divulguer les paramètres de connexion."""


class HermesClient:
    def __init__(self, base_url, key_file=None, timeout=10, stream_timeout=600):
        self.base_url = base_url.rstrip('/')
        self.key_file = Path(key_file) if key_file else None
        self.timeout = timeout
        self.stream_timeout = stream_timeout

    @staticmethod
    def _run_path(run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', run_id):
            raise HermesError('Identifiant du tour invalide')
        return '/v1/runs/' + run_id

    def _request(self, method, path, body=None, headers=None, timeout=None):
        try:
            key = self.key_file.read_text(encoding='utf-8').strip() if self.key_file else ''
        except (OSError, UnicodeError):
            raise HermesError('Clé du moteur inaccessible') from None
        request_headers = dict(headers or {})
        if key:
            request_headers['Authorization'] = 'Bearer ' + key
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.base_url + path, data=data, headers=request_headers, method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as exc:
            raise HermesError('Moteur : HTTP ' + str(exc.code)) from None
        except (urllib.error.URLError, OSError, ValueError):
            raise HermesError('Moteur injoignable') from None

    def _json(self, method, path, body=None, headers=None):
        try:
            with self._request(method, path, body, headers) as resp:
                obj = json.load(resp)
        except (ValueError, UnicodeError, OSError):
            raise HermesError('Réponse du moteur illisible') from None
        if not isinstance(obj, dict):
            raise HermesError('Réponse du moteur illisible')
        return obj

    def start_run(self, text, session_id, idempotency_key):
        result = self._json('POST', '/v1/runs', {'input': text, 'session_id': session_id},
                            {'Idempotency-Key': idempotency_key})
        run_id = result.get('run_id')
        self._run_path(run_id)
        return run_id

    def status(self, run_id):
        return self._json('GET', self._run_path(run_id))

    def stop(self, run_id):
        return self._json('POST', self._run_path(run_id) + '/stop', {})

    def events(self, run_id):
        """Lit les champs data SSE JSON ; le serveur ferme le flux en fin de tour."""
        path = self._run_path(run_id) + '/events'
        try:
            with self._request('GET', path, timeout=self.stream_timeout) as resp:
                data = []
                for raw in resp:
                    line = raw.decode('utf-8', 'replace').rstrip('\r\n')
                    if not line:
                        if data:
                            try:
                                item = json.loads('\n'.join(data))
                            except ValueError:
                                item = None
                            if isinstance(item, dict):
                                yield item
                            data = []
                    elif line.startswith('data:'):
                        data.append(line[5:].lstrip(' '))
        except (OSError, urllib.error.URLError):
            raise HermesError('Flux du moteur interrompu') from None


# ---------------------------------------------------------------------------
# Backend « api » : même contrat que le relais Telegram (channels/messages/send/reply/stream/command),
# sans Telegram. Conversation persistante en SQLite, tours exécutés par l'API locale de Hermes.
# ---------------------------------------------------------------------------
import queue
import secrets
import sqlite3
import threading
import time
from contextlib import closing

SCHEMA = """
create table if not exists conversations(id text primary key, hermes_session text not null, title text, created real, active integer default 0);
create table if not exists messages(id integer primary key autoincrement, conv text not null, role text not null, text text not null, ts real not null, submission text);
create table if not exists submissions(submission text primary key, conv text not null, text text not null, created real not null,
  state text not null default 'queued', run_id text);
create index if not exists msg_conv on messages(conv, id);
"""
HELP_TEXT = ('Commandes : /new (nouvelle conversation), /stop (interrompre le tour en cours), /status (état), '
             '/help. /model, /reasoning et /restart se règlent côté serveur de cette instance.')


class ApiBackend:
    def __init__(self, db_path, client, profile_name='gpt5'):
        self.client = client
        self.profile = profile_name
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._subs = {}      # conv -> [queue.Queue]
        self._live = {}      # conv -> {'running': bool, 'text': str, 'run_id': str|None}
        self._workers = {}   # conv -> queue.Queue de submissions
        with self._db() as c:
            c.executescript(SCHEMA)
            if not c.execute('select 1 from conversations').fetchone():
                self._new_conv(c)
            # Reprise après redémarrage : un tour interrompu est signalé, jamais rejoué.
            c.execute("update submissions set state='interrupted' where state in ('queued','running')")

    # -- stockage -----------------------------------------------------------
    def _db(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return closing_ctx(c)

    def _new_conv(self, c):
        cid = time.strftime('%Y%m%d_%H%M%S_') + secrets.token_hex(4)
        c.execute('update conversations set active=0')
        c.execute('insert into conversations(id,hermes_session,title,created,active) values(?,?,?,?,1)',
                  (cid, 'mc-' + secrets.token_hex(12), 'Conversation', time.time()))
        return cid

    def active_id(self):
        with self._db() as c:
            return c.execute('select id from conversations where active=1 order by created desc').fetchone()['id']

    def _conv(self, cid):
        with self._db() as c:
            r = c.execute('select * from conversations where id=?', (cid,)).fetchone()
        if r is None:
            raise ValueError('Session active requise ; actualiser le fil')
        return r

    # -- contrat lecture ------------------------------------------------------
    def channels(self):
        cid = self.active_id()
        with self._db() as c:
            n = c.execute('select count(*) n from messages where conv=?', (cid,)).fetchone()['n']
        return [{'profile': self.profile, 'session': cid, 'title': 'Conversation', 'count': n, 'chat_id': None}]

    def valid(self, sid):
        if not isinstance(sid, str) or sid != self.active_id():
            raise ValueError('Session active requise ; actualiser le fil')
        return sid

    def messages(self, sid):
        self._conv(sid)
        with self._db() as c:
            rows = c.execute('select role,text,ts from messages where conv=? order by id', (sid,)).fetchall()
        return {'session': sid, 'profile': self.profile, 'messages': [dict(r) for r in rows]}

    def reply(self, sid, submission):
        with self._db() as c:
            r = c.execute('select state from submissions where submission=? and conv=?', (submission, sid)).fetchone()
        if r is None:
            return {'state': 'waiting'}
        return {'state': {'queued': 'working', 'running': 'working', 'done': 'ready'}.get(r['state'], 'ready'),
                'detail': r['state']}

    # -- envoi idempotent ----------------------------------------------------
    def send(self, sid, text, submission):
        self._conv(sid)
        with self._lock, self._db() as c:
            if c.execute('select 1 from submissions where submission=?', (submission,)).fetchone():
                return {'ok': True, 'session': sid, 'state': 'duplicate'}
            now = time.time()
            c.execute('insert into submissions(submission,conv,text,created) values(?,?,?,?)', (submission, sid, text, now))
            c.execute('insert into messages(conv,role,text,ts,submission) values(?,?,?,?,?)', (sid, 'user', text, now, submission))
            q = self._workers.get(sid)
            if q is None:
                q = self._workers[sid] = queue.Queue()
                threading.Thread(target=self._worker, args=(sid, q), daemon=True).start()
            q.put(submission)
        return {'ok': True, 'session': sid, 'state': 'queued'}

    def _publish(self, sid, event):
        with self._lock:
            for q in list(self._subs.get(sid, [])):
                q.put(event)

    def _worker(self, sid, q):
        while True:
            submission = q.get()
            try:
                self._run_turn(sid, submission)
            except Exception:
                self._finish(sid, submission, 'Le tour a échoué ; renvoie le message.', 'failed')

    def _finish(self, sid, submission, text, state):
        now = time.time()
        with self._lock, self._db() as c:
            c.execute('update submissions set state=? where submission=?', (state, submission))
            if text:
                c.execute('insert into messages(conv,role,text,ts) values(?,?,?,?)', (sid, 'assistant', text, now))
            self._live[sid] = {'running': False, 'text': '', 'run_id': None}
        self._publish(sid, {'type': 'complete', 'text': text, 'status': 'error' if state == 'failed' else (
            'interrupted' if state == 'cancelled' else 'complete')})

    def _run_turn(self, sid, submission):
        with self._db() as c:
            text = c.execute('select text from submissions where submission=?', (submission,)).fetchone()['text']
            session = c.execute('select hermes_session from conversations where id=?', (sid,)).fetchone()['hermes_session']
            c.execute("update submissions set state='running' where submission=?", (submission,))
        self._live[sid] = {'running': True, 'text': '', 'run_id': None}
        self._publish(sid, {'type': 'writing'})
        try:
            run_id = self.client.start_run(text, session, submission)
        except HermesError as exc:
            return self._finish(sid, submission, 'Le moteur est indisponible (%s). Renvoie le message plus tard.' % exc, 'failed')
        with self._db() as c:
            c.execute('update submissions set run_id=? where submission=?', (run_id, submission))
        self._live[sid]['run_id'] = run_id
        acc = []
        try:
            for ev in self.client.events(run_id):
                kind = ev.get('event', '')
                if kind == 'message.delta':
                    d = ev.get('delta') or ev.get('text') or ''
                    if d:
                        acc.append(d)
                        self._live[sid]['text'] = ''.join(acc)
                        self._publish(sid, {'type': 'delta', 'text': d})
                elif kind == 'tool.started':
                    self._publish(sid, {'type': 'tool', 'name': str(ev.get('tool', '')), 'preview': str(ev.get('preview', ''))[:200]})
                elif kind == 'tool.completed':
                    self._publish(sid, {'type': 'tool_done', 'name': str(ev.get('tool', '')), 'is_error': bool(ev.get('error'))})
        except HermesError:
            pass
        # L'état final vient toujours du moteur, pas du flux relayé.
        status, output = 'unknown', ''
        for _ in range(30):
            try:
                st = self.client.status(run_id)
            except HermesError:
                time.sleep(1); continue
            status = st.get('status')
            output = str(st.get('output') or '')
            if status in ('completed', 'failed', 'cancelled'):
                break
            time.sleep(1)
        if status == 'completed':
            self._finish(sid, submission, output or ''.join(acc), 'done')
        elif status == 'cancelled':
            self._finish(sid, submission, ''.join(acc) or 'Tour interrompu.', 'cancelled')
        else:
            self._finish(sid, submission, 'La réponse n’a pas abouti.' if status in ('failed', 'unknown') else '', 'failed')

    # -- flux SSE -----------------------------------------------------------
    def subscribe(self, sid):
        q = queue.Queue()
        with self._lock:
            self._subs.setdefault(sid, []).append(q)
            live = dict(self._live.get(sid) or {'running': False, 'text': ''})
        return q, live

    def unsubscribe(self, sid, q):
        with self._lock:
            if q in self._subs.get(sid, []):
                self._subs[sid].remove(q)

    # -- commandes ----------------------------------------------------------
    def command(self, sid, text):
        name = text.strip().split()[0].lstrip('/').lower()
        if name == 'stop':
            run_id = (self._live.get(sid) or {}).get('run_id')
            if not run_id:
                return {'ok': True, 'kind': 'info', 'text': 'Aucun tour en cours.'}
            try:
                self.client.stop(run_id)
            except HermesError:
                return {'ok': False, 'error': 'Interruption non confirmée ; vérifie le fil avant de renvoyer.'}
            return {'ok': True, 'kind': 'info', 'text': 'Interruption demandée sur le tour en cours.'}
        if name in ('new', 'reset'):
            with self._lock, self._db() as c:
                cid = self._new_conv(c)
            return {'ok': True, 'kind': 'new', 'new_session_id': cid, 'text': 'Nouvelle conversation ouverte.'}
        if name == 'status':
            live = self._live.get(sid) or {}
            return {'ok': True, 'kind': 'info', 'reasoning': '', 'text': 'Conversation %s · %s.' % (
                sid, 'un tour est en cours' if live.get('running') else 'inactive')}
        if name == 'help':
            return {'ok': True, 'kind': 'info', 'text': HELP_TEXT}
        return {'ok': False, 'error': '/%s n’est pas pris en charge par cette instance (réglage côté serveur).' % name}


class closing_ctx:
    """sqlite3 : commit à la sortie puis fermeture (la fermeture native n'est pas faite par `with`)."""
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self.conn
    def __exit__(self, et, ev, tb):
        try:
            if et is None: self.conn.commit()
            else: self.conn.rollback()
        finally:
            self.conn.close()
        return False
