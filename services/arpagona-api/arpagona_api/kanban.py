"""Client de la passerelle ; le jeton ne quitte jamais le serveur."""
import json
import urllib.request
import urllib.error


class KanbanClient:
    def __init__(self, token, url='http://127.0.0.1:8701'):
        self.token, self.url = token, url

    def call(self, op, data):
        req = urllib.request.Request(self.url + '/kanban/' + op,
            data=json.dumps(data).encode(), headers={'Content-Type': 'application/json',
            'X-Arpagona-Service': self.token})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return 200, json.load(res)
        except urllib.error.HTTPError as exc:
            return exc.code, {'error': 'requête Kanban refusée'}
        except (OSError, ValueError):
            return 502, {'error': 'Kanban indisponible'}
