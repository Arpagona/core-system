"""Passerelle locale vers la CLI officielle ; aucune base secondaire."""
import hmac
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CLI = os.environ.get('KANBAN_CLI', '/srv/hermes-arpagona/.local/bin/hermes')
OPS = {'list', 'show', 'create', 'comment', 'complete', 'block', 'unblock', 'archive'}


def text(value, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value or (required and not value.strip()):
        raise ValueError('texte invalide')
    return value


def arguments(op, data):
    if op not in OPS or not isinstance(data, dict):
        raise ValueError('opération interdite')
    allowed = {'title', 'body'} if op == 'create' else ({'id', 'text', 'author'} if op == 'comment' else {'id', 'text'} if op == 'block' else ({'id'} if op != 'list' else set()))
    if set(data) - allowed:
        raise ValueError('champ interdit')
    args = [CLI, 'kanban', op]
    if op == 'list':
        return args + ['--json']
    if op == 'create':
        # -- sépare le titre des options. Aucun assignee, aucune spécification automatique.
        return args + ['--body=' + text(data.get('body', ''), 8000, False), '--json', '--', text(data.get('title'), 200)]
    ident = data.get('id')
    if not isinstance(ident, str) or not re.fullmatch(r't_[0-9a-f]{8,32}', ident):
        raise ValueError('identifiant invalide')
    if op == 'show':
        return args + [ident, '--json']
    if op == 'comment' and 'author' in data:
        args.append('--author=' + text(data.get('author'), 80))
    if op in {'comment', 'block'}:
        return args + ['--', ident, text(data.get('text'), 8000)]
    return args + ['--', ident]


def execute(op, data, runner=subprocess.run):
    args = arguments(op, data)
    if args[0].endswith('.py'):  # Kanban simulé du poste de développement, portable
        args = [sys.executable] + args
    result = runner(args, capture_output=True, text=True, timeout=25, check=False)
    if result.returncode:
        raise RuntimeError('commande refusée ou carte inconnue')
    if op in {'list', 'show', 'create'}:
        return json.loads(result.stdout)
    return {'status': 'ok'}


def handler(token, runner=subprocess.run):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            status, payload = 200, {}
            try:
                if not token or not hmac.compare_digest(self.headers.get('X-Arpagona-Service', ''), token):
                    status, payload = 401, {'error': 'service non autorisé'}
                else:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 16384:
                        raise ValueError('corps invalide')
                    data = json.loads(self.rfile.read(length))
                    if not self.path.startswith('/kanban/'):
                        raise ValueError('route invalide')
                    payload = execute(self.path.removeprefix('/kanban/'), data, runner)
            except (ValueError, TypeError):
                status, payload = 400, {'error': 'requête invalide'}
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                status, payload = 502, {'error': 'commande indisponible'}
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
    return Handler


if __name__ == '__main__':
    token = Path(os.environ['KANBAN_TOKEN_FILE']).read_text().strip()
    port = int(os.environ.get('KANBAN_BRIDGE_PORT', '8701'))
    ThreadingHTTPServer(('127.0.0.1', port), handler(token)).serve_forever()
