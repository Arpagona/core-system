"""Contrat CLI et frontière HTTP, sans toucher au Kanban réel."""
import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).parents[1] / 'bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
ID = 't_16192f3a'


class BridgeTest(unittest.TestCase):
    def test_arguments_exacts(self):
        cases = [
            ('list', {}, ['--json']),
            ('show', {'id': ID}, [ID, '--json']),
            ('create', {'title': '--assignee=intrus', 'body': 'un corps'},
             ['--body=un corps', '--json', '--', '--assignee=intrus']),
            ('comment', {'id': ID, 'text': '--option; $(touch /danger)'},
             ['--', ID, '--option; $(touch /danger)']),
            ('comment', {'id': ID, 'text': 'vu', 'author': 'Thibaud'},
             ['--author=Thibaud', '--', ID, 'vu']),
            ('block', {'id': ID, 'text': 'attente'}, ['--', ID, 'attente']),
        ]
        cases += [(op, {'id': ID}, ['--', ID]) for op in ('complete', 'unblock', 'archive')]
        for op, data, suffix in cases:
            with self.subTest(op=op):
                runner = Mock(return_value=subprocess.CompletedProcess([], 0, '{}'))
                bridge.execute(op, data, runner)
                runner.assert_called_once_with([bridge.CLI, 'kanban', op] + suffix,
                                               capture_output=True, text=True, timeout=25, check=False)

    def test_refus_champs_operations_et_injections(self):
        bad = [('create', {'title': 'ok', 'assignee': 'agent'}),
               ('create', {'title': 'x' * 201}), ('create', {'title': ' '}),
               ('create', {'title': 'a\x00b'}), ('dispatch', {}),
               ('list;id', {}), ('list', {'tenant': 'autre'}), ('list', []),
               ('block', {'id': ID, 'text': 'x', 'author': 'intrus'}),
               ('comment', {'id': ID, 'text': 'x', 'author': 'a' * 81})]
        bad += [('show', {'id': value}) for value in
                ('--help', 't_1234567', 't_xyz12345', 't_16192f3a;id', '../test', 't_' + 'a' * 33, None)]
        for op, data in bad:
            with self.subTest(op=op, data=data):
                runner = Mock()
                with self.assertRaises(ValueError):
                    bridge.execute(op, data, runner)
                runner.assert_not_called()

    def test_ids_reels(self):
        for value in (ID, 't_' + 'a' * 32):
            self.assertEqual(bridge.arguments('show', {'id': value})[-2:], [value, '--json'])

    def test_creation_sans_assignee(self):
        args = bridge.arguments('create', {'title': 'Mission'})
        self.assertEqual(args, [bridge.CLI, 'kanban', 'create', '--body=', '--json', '--', 'Mission'])

    def test_reponses_json_et_accuse_texte(self):
        for op, data in [('list', {}), ('show', {'id': ID}), ('create', {'title': 'Mission'})]:
            self.assertEqual(bridge.execute(op, data, Mock(return_value=subprocess.CompletedProcess([], 0, '{"id": "test"}'))), {'id': 'test'})
        self.assertEqual(bridge.execute('complete', {'id': ID}, Mock(return_value=subprocess.CompletedProcess([], 0, 'Carte terminée'))), {'status': 'ok'})

    def test_echec_cli(self):
        with self.assertRaises(RuntimeError):
            bridge.execute('list', {}, Mock(return_value=subprocess.CompletedProcess([], 1, '')))

    def test_http_auth_et_validation(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, '[]'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.handler('jeton-fictif', runner))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            cases = [(None, '/kanban/list', {}, 401), ('faux', '/kanban/list', {}, 401),
                     ('jeton-fictif', '/list', {}, 400),
                     ('jeton-fictif', '/kanban/create', {'title': 'ok', 'assignee': 'agent'}, 400),
                     ('jeton-fictif', '/kanban/list', {}, 200)]
            for token, path, data, expected in cases:
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
                headers = {'X-Arpagona-Service': token} if token else {}
                conn.request('POST', path, json.dumps(data), headers)
                response = conn.getresponse()
                self.assertEqual(response.status, expected)
                json.loads(response.read())
                conn.close()
            self.assertEqual(runner.call_count, 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
