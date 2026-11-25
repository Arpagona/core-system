#!/usr/bin/python3
"""GONA Mission Control. Une surface, aucune nouvelle session/base/autorité agent."""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import select
import sqlite3
from contextlib import closing
import subprocess
import time
import urllib.request
import urllib.error
import queue
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
import bridge
import gate
import config
import backend_api
import session_rotation
import bridge_token

ROOT = Path(__file__).resolve().parent
PROFILE = config.PROFILE
TOKEN_FILE = config.TOKEN_FILE
TOKEN = TOKEN_FILE.read_text().strip()
COOKIE = hashlib.sha256(('gona-mc-v1:' + TOKEN).encode()).hexdigest()
BRIDGE_KEY = b''
if config.BRIDGE_KEY_FILE and Path(config.BRIDGE_KEY_FILE).is_file():
    BRIDGE_KEY = Path(config.BRIDGE_KEY_FILE).read_text().strip().encode('ascii')
OLD = config.LEGACY_TOKEN_FILE
ASK = PROFILE / 'scripts/ask.py'
KANBAN_DB = config.KANBAN_DB
MAPPING = PROFILE / 'refonte/loop/kanban_map.json'
HERMES = config.HERMES_SRC
HERMES_PY = HERMES / 'venv/bin/python'
LIVE = ROOT / 'gateway_live.py'
API = None
if config.BACKEND == 'api':
    API = backend_api.ApiBackend(config.DATA_DIR / 'chat.db',
                                 backend_api.HermesClient(config.HERMES_URL, config.HERMES_KEY_FILE), config.PROFILE_NAME)
    ALIAS_MODELS = {'terra': ('gpt-6.1-terra', 'openai-codex'), 'sol': ('gpt-6.1-sol', 'openai-codex'),
                    'luna': ('gpt-5.6-luna', 'openai-codex'), 'opus': ('claude-opus-5-5', 'anthropic'),
                    'fable': ('claude-fable-5.1', 'anthropic'), 'sonnet': ('claude-sonnet-5-5', 'anthropic'),
                    'deepseek': ('deepseek-v4.1-flash', 'opencode-go'), 'kimi': ('kimi-k3', 'kimi-coding')}
    API.resolver = lambda name, prov: ALIAS_MODELS.get(name.lower(), (name, prov)) if not prov else (name, prov)

    def _model_list(sid, text):
        # liste des fournisseurs/modèles : lue sur la passerelle (catalogue), le réglage reste local à Agent Core
        try:
            tg = next(c for c in old_api('/api/channels')['channels'] if c.get('profile') == config.PROFILE_NAME and c.get('session'))
            out = old_api('/api/channel/command', {'id': tg['session'], 'profile': config.PROFILE_NAME, 'command': '/model'})
            cfg = API.settings()
            if cfg.get('model'):
                out = dict(out, model=cfg['model'], model_label=cfg['model'], provider=cfg.get('provider') or out.get('provider'))
            return out
        except Exception:
            return {'ok': True, 'kind': 'info', 'text': 'Catalogue indisponible. Utilise /model <alias> (terra, sol, opus, sonnet, deepseek, kimi) ou /model reset.'}
    API.lister = _model_list
COMMANDS = [
    {'command': '/status', 'description': 'Modèle, réflexion et état du fil', 'arg': False},
    {'command': '/model', 'description': 'Choisir le fournisseur puis le modèle', 'arg': False},
    {'command': '/reasoning', 'description': 'Niveau de réflexion (low → xhigh)', 'arg': False},
    {'command': '/stop', 'description': 'Interrompre le tour en cours', 'arg': False},
    {'command': '/new', 'description': 'Ouvrir une nouvelle conversation', 'arg': False},
    {'command': '/restart', 'description': 'Redémarrer le gateway quand il est inactif', 'arg': False},
    {'command': '/help', 'description': 'Lister les commandes disponibles', 'arg': False},
]
MEDIA_ROOTS = (ROOT, config.HOME / 'projects', config.HOME / 'Pictures', config.HOME / 'Downloads',
               config.HOME / 'Desktop', Path('/tmp'), PROFILE / 'cache') + config.MEDIA_EXTRA
IMAGE_EXT = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
DENIED_MEDIA_NAMES = {'.env', '.ssh', '.gnupg', '.netrc', 'token', 'credentials',
                      'id_rsa', 'id_ed25519', '.git-credentials'}


UPLOAD_DIR = PROFILE / 'cache' / 'documents' / 'mc-uploads'
UPLOAD_MAX = 10_000_000
TEXT_EXT = {'.txt', '.md', '.csv', '.tsv', '.json', '.log', '.py', '.yaml', '.yml', '.xml', '.html', '.ini', '.toml', '.sh', '.js', '.css', '.sql', '.tex', '.rtf'}


def store_upload(data, filename):
    """Pièce jointe : type détecté sur les octets, copie privée sous un nom neuf, chemin renvoyé au client
    uniquement comme texte pour l'agent (jamais relu comme chemin par ce serveur)."""
    if not 0 < len(data) <= UPLOAD_MAX:
        raise ValueError('Fichier vide ou trop gros (10 Mo max)')
    ext = None
    if data[:8] == b'\x89PNG\r\n\x1a\n': ext, kind = '.png', 'image'
    elif data[:3] == b'\xff\xd8\xff': ext, kind = '.jpg', 'image'
    elif data[:6] in (b'GIF87a', b'GIF89a'): ext, kind = '.gif', 'image'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP': ext, kind = '.webp', 'image'
    elif data[:5] == b'%PDF-': ext, kind = '.pdf', 'document'
    else:
        want = Path(filename or '').suffix.lower()
        if want not in TEXT_EXT or b'\x00' in data[:8192]:
            raise ValueError('Type non pris en charge (images, PDF, texte)')
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('Texte UTF-8 requis')
        ext, kind = want, 'document'
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(filename or 'fichier').stem)[:40] or 'fichier'
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = UPLOAD_DIR / (time.strftime('%Y%m%d-%H%M%S-') + os.urandom(4).hex() + '-' + safe + ext)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    label = '[Image attached at: %s]' if kind == 'image' else '[Document attached at: %s]'
    return {'ok': True, 'kind': kind, 'name': safe + ext, 'ref': label % path}


def read_kanban(ident=None):
    # Default board = kanban.db ; les autres boards ont un fichier distinct.
    with closing(sqlite3.connect(KANBAN_DB.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as c:
        c.row_factory = sqlite3.Row
        if ident is not None:
            if not isinstance(ident, str) or not re.fullmatch(r't_[0-9a-f]{8,32}', ident):
                raise ValueError('Identifiant invalide')
            row = c.execute('select * from tasks where id=?', (ident,)).fetchone()
            if row is None:
                raise ValueError('Carte inconnue')
            return {'task':dict(row)}
        tasks = [dict(r) for r in c.execute('select * from tasks order by created_at desc, id')]
    return {'tasks':tasks, 'mapping':json.loads(MAPPING.read_text()), 'total':len(tasks), 'board':'default'}


def old_api(path, body=None):
    req = urllib.request.Request(config.LEGACY_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json', 'X-MC-Token':OLD.read_text().strip()})
    with urllib.request.urlopen(req, timeout=80) as response:
        result = json.load(response)
    if result.get('error'):
        raise RuntimeError(result['error'])
    return result


def voice_proxy(path, data, ctype):
    """Voix : relais binaire vers l'ancien Mission Control (8790) — transcription locale faster-whisper,
    synthèse Edge (voix de mission-control/voice.json, fr-CA) avec repli Piper. Rien n'est stocké ici."""
    req = urllib.request.Request(config.LEGACY_URL + path, data=data, method='POST',
        headers={'Content-Type': ctype, 'X-MC-Token': OLD.read_text().strip()})
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return r.status, r.read(), r.headers.get('Content-Type', 'application/octet-stream')
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get('Content-Type', 'application/json')


def live_op(payload, timeout=45):
    env = dict(os.environ, HERMES_HOME=str(PROFILE), PYTHONPATH=str(HERMES))
    p = subprocess.run([str(HERMES_PY), str(LIVE)], input=json.dumps(payload), capture_output=True,
                       text=True, env=env, timeout=timeout)
    lines = [line for line in (p.stdout or '').splitlines() if line.strip()]
    if not lines:
        raise RuntimeError('réponse vide')
    try:
        out = json.loads(lines[-1])
    except (ValueError, TypeError):
        raise RuntimeError('réponse illisible')
    if not isinstance(out, dict) or out.get('ok') is not True:
        raise RuntimeError(str(out.get('error') or 'refusé')[:80])
    return out


def media_file(raw):
    if not isinstance(raw, str) or not raw or len(raw) > 4096 or '\x00' in raw:
        raise ValueError('Chemin invalide')
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        raise ValueError('Chemin invalide')
    p = p.resolve(strict=True)
    if not p.is_file() or p.suffix.lower() not in IMAGE_EXT:
        raise ValueError('Image uniquement')
    if p.stat().st_size > 12_000_000:
        raise ValueError('Image trop volumineuse')
    if any(part.lower() in DENIED_MEDIA_NAMES for part in p.parts):
        raise ValueError('Chemin refusé')
    for root in MEDIA_ROOTS:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if p == resolved or resolved in p.parents:
            return p, IMAGE_EXT[p.suffix.lower()]
    raise ValueError('Image hors zone autorisée')


FILE_EXT = {'.apk': 'application/vnd.android.package-archive', '.pdf': 'application/pdf', '.zip': 'application/zip',
            '.txt': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8', '.csv': 'text/csv; charset=utf-8',
            '.json': 'application/json', '.stl': 'model/stl', '.3mf': 'model/3mf', '.step': 'application/step',
            '.stp': 'application/step', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.gcode': 'text/plain; charset=utf-8'}
DENIED_FILE_WORDS = ('secret', 'token', 'password', 'passwd', 'credential', '.jks', '.pass', 'private', 'id_rsa', '.env', '.ssh', '.gnupg')
FILE_ROOTS = (PROFILE / 'cache', config.HOME / 'Downloads', config.HOME / 'Desktop', config.HOME / 'Documents',
              config.HOME / 'lab3d-venture-zero', config.HOME / 'enseignement', PROFILE / 'reports') + config.MEDIA_EXTRA


def download_file(raw):
    """Fichier envoyé par l'agent (MEDIA:/chemin) : téléchargement forcé, extensions et dossiers listés."""
    if not isinstance(raw, str) or not raw or len(raw) > 4096 or '\x00' in raw:
        raise ValueError('Chemin invalide')
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        raise ValueError('Chemin invalide')
    p = p.resolve(strict=True)
    if not p.is_file() or p.suffix.lower() not in FILE_EXT:
        raise ValueError('Type de fichier non autorisé')
    if p.stat().st_size > 100_000_000:
        raise ValueError('Fichier trop volumineux')
    low = str(p).lower()
    if any(w in low for w in DENIED_FILE_WORDS):
        raise ValueError('Chemin refusé')
    for root in FILE_ROOTS:
        try:
            r = root.resolve()
        except OSError:
            continue
        if r in p.parents:
            return p, FILE_EXT[p.suffix.lower()]
    raise ValueError('Fichier hors zone autorisée')


GATEWAY_UNIT = 'hermes-gateway.service'
GRACEFUL = ['systemctl', '--user', 'kill', '--kill-whom=main', '-s', 'SIGUSR1', GATEWAY_UNIT]


def gateway_new(sid):
    """Plugin mc-new (profil gpt5) : appelle le vrai /new du gateway sur la session Telegram vivante."""
    hermes = str(HERMES)
    env = dict(os.environ, HERMES_HOME=str(PROFILE), PYTHONPATH=hermes)
    r = subprocess.run([hermes + '/venv/bin/python', str(ROOT / 'gateway_new.py')], input=json.dumps({'id': sid}),
                       capture_output=True, text=True, env=env, timeout=90)
    return json.loads(r.stdout or '{}')


def rotate_if_due(sid):
    """Mode Telegram : avant un envoi, tourne la session si la politique session-lifecycle l'exige.
    Renvoie (session à utiliser, raison | None). En cas de doute ou d'échec, on garde la session
    courante : le message part quand même, rien n'est perdu."""
    try:
        p = session_rotation.policy(PROFILE)
        why = session_rotation.reason(p, session_rotation.last_user_activity(PROFILE, sid)) if p else None
        if not why or not idle_state(sid):
            return sid, None
        out = gateway_new(sid)
        new = out.get('new_session_id') if out.get('ok') else None
        if not isinstance(new, str) or not new or new == sid:
            return sid, None
        session_rotation.record_rotation(PROFILE, sid, new, why)
        return new, why
    except Exception:
        return sid, None


def command(sid, text):
    """Commandes « / » du chat. Jamais transmises à l'agent comme message.
    /restart : SIGUSR1 au gateway = redémarrage natif « quand inactif » (comme /restart Telegram).
    /model, /status, /reasoning, /help : même réglage par conversation que Telegram (gateway natif)."""
    if API:
        return API.command(sid, text)
    parts = text.strip().split()
    name = parts[0].lstrip('/').lower()
    if name == 'stop':
        try:
            live_op({'id': sid, 'op': 'interrupt'}, timeout=30)
        except Exception:
            return {'ok': False, 'error': 'Interruption non confirmée ; vérifie le fil avant de renvoyer.'}
        return {'ok': True, 'kind': 'info', 'text': 'Interruption demandée sur le tour en cours (même mécanisme que /stop dans Telegram).'}
    if name == 'reasoning' and len(parts) == 1:
        current = command(sid, '/status')
        if not current.get('ok'):
            return current
        return {'ok': True, 'kind': 'reasoning', 'current': current.get('reasoning') or '',
                'levels': ['low', 'medium', 'high', 'xhigh', 'reset']}
    if name == 'reasoning' and len(parts) >= 2 and parts[1].lower() not in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'reset', 'show', 'hide'):
        return {'ok': False, 'error': 'Niveau inconnu. Valeurs : low, medium, high, xhigh, reset (show/hide pour l\u2019affichage).'}
    if name == 'restart':
        r = subprocess.run(GRACEFUL, capture_output=True, text=True, timeout=10)
        if r.returncode:
            return {'ok': False, 'error': 'Redémarrage refusé par systemd'}
        return {'ok': True, 'kind': 'info', 'text': 'Redémarrage du gateway demandé. Il attend la fin du travail en cours, '
                'puis redémarre (comme /restart dans Telegram). Le chat revient seul dans une minute environ.'}
    if name in ('new', 'reset'):
        try:
            out = gateway_new(sid)
        except Exception:
            return {'ok': False, 'error': 'Résultat /new incertain : vérifie le fil avant de recommencer.'}
        if out.get('ok'):
            return {'ok': True, 'kind': 'new', 'new_session_id': out.get('new_session_id'),
                    'text': 'Nouvelle conversation ouverte (même effet que /new dans Telegram).'}
        reason = out.get('error') or out.get('reason') or 'refusé'
        if 'FileNotFound' in str(reason) or 'ConnectionRefused' in str(reason) or 'proof' in str(reason) or 'armed' in str(reason) or 'unavailable' in str(reason):
            return {'ok': False, 'error': '/new pas encore chargé : fais /restart une fois, puis réessaie.'}
        return {'ok': False, 'error': '/new refusé (' + str(reason)[:80] + '). Utilise /new dans Telegram.'}
    return old_api('/api/channel/command', {'id': sid, 'profile': config.PROFILE_NAME, 'command': text.strip()[:300]})


def idle_state(sid):
    """True si plus aucun tour n'est en cours (lecture seule : premier « snapshot » du flux, puis fermeture)."""
    if API:
        return not (API._live.get(sid) or {}).get('running')
    if not HERMES_PY.is_file() or not LIVE.is_file():
        return False
    env = dict(os.environ, HERMES_HOME=str(PROFILE), PYTHONPATH=str(HERMES))
    proc = subprocess.Popen([str(HERMES_PY), str(LIVE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, env=env)
    try:
        proc.stdin.write(json.dumps({'id': sid, 'op': 'stream'}) + '\n'); proc.stdin.close()
        end = time.time() + 15
        while time.time() < end:
            ready, _, _ = select.select([proc.stdout], [], [], 1)
            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                return False
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'snapshot':
                return not ev.get('running') and not ev.get('prompts') and not ev.get('pending')
        return False
    finally:
        proc.terminate()
        try: proc.wait(timeout=2)
        except Exception: proc.kill()


def channels():
    if API:
        return API.channels()
    return [c for c in old_api('/api/channels')['channels'] if c.get('profile') == config.PROFILE_NAME and c.get('session')]


def valid_session(sid):
    if not isinstance(sid, str) or not any(c['session'] == sid for c in channels()):
        raise ValueError('Session active requise ; actualiser le fil')
    return sid


class UserError(ValueError):
    """Refus lisible, renvoyé tel quel à l'interface (aucune donnée sensible)."""


MAX_TEXT = 16000


def ask(*args):
    p = subprocess.run(['/usr/bin/python3', str(ASK), *args], capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError('ask.py a refusé la demande')
    return p.stdout


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Aucune URL, aucun message ni credential dans le journal.

    def send(self, status, payload, content_type='application/json', cookie=None, location=None):
        body = json.dumps(payload, ensure_ascii=False).encode() if content_type == 'application/json' else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; media-src 'self' blob: data:; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie is not None:
            self.send_header('Set-Cookie', 'gona_mc=' + cookie + '; Path=/; HttpOnly; SameSite=Strict')
        if location:
            self.send_header('Location', location)
        self.end_headers()
        self.wfile.write(body)

    def stream_api(self, sid):
        q, live = API.subscribe(sid)
        self.close_connection = True
        self.send_response(200)
        for k, v in (('Content-Type', 'text/event-stream; charset=utf-8'), ('Cache-Control', 'no-cache, no-store'),
                     ('Connection', 'close'), ('X-Accel-Buffering', 'no'), ('X-Content-Type-Options', 'nosniff'),
                     ('Referrer-Policy', 'no-referrer'), ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")):
            self.send_header(k, v)
        self.end_headers()
        def emit(obj):
            self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode()); self.wfile.flush()
        try:
            emit({'type': 'snapshot', 'session': sid, 'running': bool(live.get('running')), 'prompts': [], 'info': {}})
            if live.get('running') and live.get('text'):
                emit({'type': 'delta', 'text': live['text']})
            while True:
                try:
                    emit(q.get(timeout=10))
                except queue.Empty:
                    self.wfile.write(b': keep-alive\n\n'); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            API.unsubscribe(sid, q)

    def stream(self, sid):
        if API:
            return self.stream_api(sid)
        if not HERMES_PY.is_file() or not LIVE.is_file():
            return self.send(502, {'error':'Flux indisponible'})
        env = dict(os.environ, HERMES_HOME=str(PROFILE), PYTHONPATH=str(HERMES))
        try:
            proc = subprocess.Popen([str(HERMES_PY), str(LIVE)], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    text=True, encoding='utf-8', bufsize=1, env=env)
        except OSError:
            return self.send(502, {'error':'Flux indisponible'})
        self.close_connection = True
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            proc.stdin.write(json.dumps({'id': sid, 'op': 'stream'}) + '\n')
            proc.stdin.close()
            while True:
                try:
                    ready, _, _ = select.select([proc.stdout], [], [], 10)
                except (OSError, ValueError):
                    break
                if not ready:
                    self.wfile.write(b': keep-alive\n\n')
                    self.wfile.flush()
                    continue
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    self.wfile.write(('data: ' + line + '\n\n').encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            try:
                self.wfile.write(b'data: {"type":"fatal","error":"flux interrompu"}\n\n')
                self.wfile.flush()
            except Exception:
                pass
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            try:
                proc.stdout.close()
            except Exception:
                pass

    def via_bridge(self):
        """Vrai si la requête porte un cookie pont valide (session Atlas), faux pour le jeton local de l'iMac."""
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie[bridge_token.COOKIE].value if bridge_token.COOKIE in cookie else ''
        except Exception:
            return False
        return bool(BRIDGE_KEY and token and bridge_token.verify(BRIDGE_KEY, token, config.BRIDGE_LOGINS))

    def authorized(self):
        cookie = SimpleCookie()
        bridge = ''
        try:
            cookie.load(self.headers.get('Cookie', ''))
            value = cookie['gona_mc'].value if 'gona_mc' in cookie else ''
            bridge = cookie[bridge_token.COOKIE].value if bridge_token.COOKIE in cookie else ''
        except Exception:
            value = ''
        if hmac.compare_digest(value, COOKIE) or hmac.compare_digest(self.headers.get('X-MC-Token',''), TOKEN):
            return True
        # Session Atlas reconnue : cookie signé, non expiré, compte autorisé (jamais les autres comptes du banc).
        return bool(BRIDGE_KEY and bridge and bridge_token.verify(BRIDGE_KEY, bridge, config.BRIDGE_LOGINS))

    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        if u.path == '/' and 't' in q:
            if hmac.compare_digest(q['t'][0], TOKEN):
                return self.send(303, b'', 'text/plain', COOKIE, '/')
            return self.send(401, {'error':'Jeton invalide'})
        if u.path in ('/', '/index.html', '/app.js', '/markdown.js', '/style.css', '/alpha.css', '/logo.png', '/voice.js', '/kiosk.js'):
            f = ROOT / 'web' / ('index.html' if u.path == '/' else u.path[1:])
            return self.send(200, f.read_bytes(), mimetypes.guess_type(f)[0] or 'text/plain')
        if u.path == '/api/version':   # empreinte de l'interface : les écrans ouverts se rechargent seuls après un déploiement
            h = hashlib.sha256()
            for name in ('index.html', 'app.js', 'voice.js', 'markdown.js', 'style.css', 'alpha.css', 'kiosk.js'):
                try: h.update((ROOT / 'web' / name).read_bytes())
                except OSError: pass
            return self.send(200, {'version': h.hexdigest()[:16]})
        if not self.authorized():
            return self.send(401, {'error':'Authentification requise'})
        try:
            if u.path == '/api/me':
                me = {'name':'Thibaud · GONA / gpt5', 'backend': 'api' if API else 'telegram'}
                if self.via_bridge():
                    me['atlas'] = True  # arrivé par Atlas : le bouton « ⇄ Atlas » ramène sur le banc, même session
                return self.send(200, me)
            if u.path == '/api/channels':
                return self.send(200, {'channels':channels()})
            if u.path == '/api/channel/idle':
                sid = q.get('id', [''])[0]
                valid_session(sid)
                return self.send(200, {'idle': idle_state(sid)})
            if u.path == '/api/commands':
                return self.send(200, {'commands': COMMANDS})
            if u.path == '/api/stream':
                sid = q.get('id', [''])[0]
                valid_session(sid)
                return self.stream(sid)
            if u.path == '/api/file':
                path, ctype = download_file(q.get('path', [''])[0])
                data = path.read_bytes()
                self.send_response(200); self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + urlencode({'': path.name})[1:])
                self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Cache-Control', 'no-store')
                self.end_headers(); self.wfile.write(data)
                return
            if u.path == '/api/media':
                path, ctype = media_file(q.get('path', [''])[0])
                return self.send(200, path.read_bytes(), ctype)
            if u.path in ('/api/channel/messages', '/api/channel/reply'):
                valid_session(q.get('id',[''])[0])
                if u.path.endswith('/reply') and not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}', q.get('submission',[''])[0]):
                    raise ValueError('Identifiant d’envoi invalide')
                if API:
                    sid = q['id'][0]
                    return self.send(200, API.messages(sid) if u.path.endswith('/messages') else API.reply(sid, q['submission'][0]))
                return self.send(200, old_api(self.path))
            if u.path in ('/api/kanban/list', '/kanban'):
                return self.send(200, read_kanban())
            if u.path == '/api/kanban/show':
                return self.send(200, read_kanban(q.get('id',[''])[0]))
            if u.path == '/api/gate':
                return self.send(200, {'items':gate.items()})
            if u.path == '/api/decisions':
                return self.send(200, {'text':ask('list')})
            return self.send(404, {'error':'Route inconnue'})
        except (ValueError, TypeError) as e:
            self.send(400, {'error': 'Session active requise ; actualiser le fil' if 'Session active requise' in str(e) else 'Requête invalide'})
        except Exception:
            self.send(502, {'error':'Source indisponible ; aucune confirmation d’effet'})

    def do_POST(self):
        try:
            if self.headers.get('X-Gona') != '1':
                return self.send(400, {'error':'Marqueur de requête requis'})
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://' + self.headers.get('Host',''), 'https://' + self.headers.get('Host','')):
                return self.send(403, {'error':'Origine refusée'})
            if self.path == '/api/upload':
                if not self.authorized():
                    return self.send(401, {'error':'Authentification requise'})
                n = int(self.headers.get('Content-Length','0'))
                if not 0 < n <= UPLOAD_MAX:
                    return self.send(413, {'error':'Fichier vide ou trop gros (10 Mo max)'})
                from urllib.parse import unquote
                return self.send(200, store_upload(self.rfile.read(n), unquote(self.headers.get('X-Filename',''))))
            if self.path in ('/api/voice/transcribe', '/api/voice/speak'):
                if not self.authorized():
                    return self.send(401, {'error':'Authentification requise'})
                n = int(self.headers.get('Content-Length','0'))
                ctype = (self.headers.get('Content-Type') or '').lower()
                if self.path.endswith('transcribe') and not (ctype.startswith('audio/') and 0 < n <= 8_000_000):
                    return self.send(415, {'error':'Audio requis (8 Mo max)'})
                if self.path.endswith('speak') and not (ctype.startswith('application/json') and 0 < n <= 40000):
                    return self.send(400, {'error':'Texte requis'})
                st, data, rtype = voice_proxy(self.path, self.rfile.read(n), ctype)
                self.send_response(st); self.send_header('Content-Type', rtype)
                self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store')
                self.end_headers(); self.wfile.write(data)
                return
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 131072:
                raise ValueError('Corps invalide')
            b = json.loads(self.rfile.read(length))
            if not isinstance(b, dict):
                raise ValueError('Objet requis')
            if self.path == '/api/login':
                if not isinstance(b.get('password'), str) or not hmac.compare_digest(b['password'], TOKEN):
                    time.sleep(0.4)
                    return self.send(401, {'error':'Jeton invalide'})
                return self.send(200, {'ok':True}, cookie=COOKIE)
            if not self.authorized():
                return self.send(401, {'error':'Authentification requise'})
            if self.path == '/api/kiosk/close':
                try:
                    import imac_kiosk_api
                except ImportError:
                    return self.send(404, {'error':'Indisponible'})
                st, data = imac_kiosk_api.close(self.headers.get('Host',''))
                return self.send(st, data)
            if self.path == '/api/logout':
                return self.send(200, {'ok':True}, cookie='')
            if self.path == '/api/chat':
                sid = valid_session(b.get('id'))
                text, submission = b.get('text'), b.get('submission_id')
                if not isinstance(text,str) or not text.strip():
                    raise UserError('Message vide')
                if len(text) > MAX_TEXT:
                    raise UserError('Message trop long (%d caractères max) : découpe-le ou joins un fichier 📎' % MAX_TEXT)
                if text.lstrip().startswith('/'):
                    raise UserError('Commande inconnue : tape / pour voir la liste')
                if not isinstance(submission,str) or not re.fullmatch(r'imac-mc-[a-zA-Z0-9_-]{8,80}', submission):
                    raise UserError('Clé d’envoi invalide : recharge la page')
                rotated = None
                if not API:
                    sid, rotated = rotate_if_due(sid)
                for attempt in range(4 if rotated else 1):
                    try:
                        r = API.send(sid, text, submission) if API else old_api('/api/channel/send', {'id':sid, 'profile':config.PROFILE_NAME, 'text':text, 'submission_id':submission})
                        break
                    except RuntimeError as e:  # nouvelle session pas encore visible côté lecture
                        if attempt == 3 or 'active' not in str(e):
                            raise
                        time.sleep(1.5)
                if rotated or (isinstance(r, dict) and r.get('rotated')):
                    r = dict(r, session=r.get('session') or sid, rotated=rotated or r.get('rotated'))
                if not r.get('ok'):
                    return self.send(502, r)
                return self.send(200, r)
            if self.path == '/api/command':
                sid = valid_session(b.get('id'))
                text = b.get('command')
                if not isinstance(text, str) or not re.fullmatch(r'/[a-z]{2,20}( [A-Za-z0-9._:/@ -]{0,200})?', text.strip()):
                    raise ValueError('Commande invalide')
                return self.send(200, command(sid, text))
            if self.path == '/api/control/respond':
                sid = valid_session(b.get('id'))
                if API:
                    raise RuntimeError('non pris en charge')
                kind = b.get('kind')
                pid = b.get('prompt_id')
                if kind not in ('approval', 'clarify'):
                    raise ValueError('Contrôle invalide')
                if not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', pid):
                    raise ValueError('Contrôle invalide')
                payload = {'id': sid, 'op': 'respond', 'kind': kind, 'prompt_id': pid}
                generation = b.get('generation')
                if isinstance(generation, int) and not isinstance(generation, bool):
                    payload['generation'] = generation
                if kind == 'approval':
                    if b.get('choice') not in ('once', 'deny', 'session', 'always'):
                        raise ValueError('Contrôle invalide')
                    payload['choice'] = b['choice']
                else:
                    if not isinstance(b.get('answer'), str) or not b['answer'].strip() or len(b['answer']) > 16000:
                        raise ValueError('Réponse invalide')
                    payload['answer'] = b['answer']
                return self.send(200, live_op(payload, timeout=60))
            if self.path == '/api/kanban/create':
                return self.send(200, bridge.execute('create', b))
            if self.path == '/api/gate/decide':
                if set(b) != {'kind','id','answer'} or not all(isinstance(b[k],str) for k in b):
                    raise ValueError('Décision invalide')
                return self.send(200, gate.decide(b['kind'], b['id'], b['answer']))
            if self.path == '/api/decisions/decide':
                if set(b) != {'target','action'} or not isinstance(b['target'],str) or not re.fullmatch(r'[1-9][0-9]{0,5}', b['target']) or b['action'] not in ('accept','refuse','defer','seen'):
                    raise ValueError('Décision invalide')
                return self.send(200, json.loads(ask('decide', b['target'], b['action'])))
            return self.send(404, {'error':'Opération interdite'})
        except UserError as e:
            self.send(400, {'error': str(e)})
        except (ValueError, TypeError) as e:
            self.send(400, {'error': 'Session active requise ; actualiser le fil' if 'Session active requise' in str(e) else 'Requête invalide'})
        except Exception:
            self.send(502, {'error':'Source indisponible ; ne pas renvoyer automatiquement'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8710'))
    ThreadingHTTPServer.request_queue_size = 128   # iMac + Android + flux SSE + sondes : la file par défaut (5) refusait des connexions
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    server.serve_forever()
