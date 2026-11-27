"""Rotation paresseuse et continuité de la conversation."""
import json
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import test_api as helpers


class RotationTest(unittest.TestCase):
    store: helpers.Store
    engine: helpers.FakeEngine
    app: helpers.App
    port: int
    setUp = helpers.ApiTest.setUp
    tearDown = helpers.ApiTest.tearDown

    def client(self):
        self.clock = [time.time()]
        self.app.now = lambda: self.clock[0]
        self.app.session_daily_hour = -1
        client = helpers.Client(self.port)
        self.assertEqual(client.login('alice', helpers.PASSWORD_A), 200)
        return client

    def send(self, client, text):
        return client.call('POST', '/api/chat', {'text': text})

    def messages(self, client):
        return json.loads(client.call('GET', '/api/conversation')[1])['messages']

    def user_id(self):
        return self.store.check_password('alice', helpers.PASSWORD_A)['id']

    def test_inactivite_passation_chaine_et_une_seule_fois(self):
        c = self.client()
        self.send(c, 'première question')
        self.clock[0] += 241 * 60
        self.send(c, 'suite')
        self.assertNotEqual(*self.engine.sessions)
        self.assertIn('Utilisateur : première question', self.engine.instructions[-1])
        self.assertIn('Agent : écho : première question', self.engine.instructions[-1])
        msgs = self.messages(c)
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[0]['conversation'], msgs[1]['conversation'])
        self.assertNotEqual(msgs[1]['conversation'], msgs[2]['conversation'])
        parent = self.store.conversation_by_id(msgs[0]['conversation'], self.user_id())
        self.assertEqual(parent['closed_reason'], 'idle')
        audit = self.store._all("SELECT * FROM audit WHERE action = 'rotation_session'", ())
        self.assertEqual(len(audit), 1)
        self.assertIn('idle', audit[0]['detail'])
        self.send(c, 'encore')
        self.assertIsNone(self.engine.instructions[-1])

    def test_239_minutes(self):
        c = self.client()
        self.send(c, 'un')
        self.clock[0] += 239 * 60
        self.send(c, 'deux')
        self.assertEqual(len(set(self.engine.sessions)), 1)

    def test_quotidienne(self):
        c = self.client()
        self.app.session_idle_minutes = 0
        self.app.session_daily_hour = 4
        tz = ZoneInfo('Europe/Paris')
        self.clock[0] = datetime(2026, 10, 27, 23, tzinfo=tz).timestamp()
        self.send(c, 'hier')
        self.clock[0] = datetime(2026, 10, 28, 9, tzinfo=tz).timestamp()
        self.send(c, "aujourd'hui")
        self.assertNotEqual(*self.engine.sessions)
        self.assertIn('frontière quotidienne', self.engine.instructions[-1])
        current = self.store.conversation_for(self.user_id())
        parent = self.store.conversation_by_id(current['parent_id'], self.user_id())
        self.assertEqual(parent['closed_reason'], 'daily')

    def test_vide_et_pending(self):
        c = self.client()
        conv = self.store.conversation_for(self.user_id())
        self.clock[0] += 100000
        self.send(c, 'premier')
        self.assertEqual(conv['id'], self.store.conversation_for(self.user_id())['id'])
        self.store.add_message(conv['id'], 'assistant', '', status='pending')
        self.clock[0] += 100000
        self.assertEqual(self.send(c, 'suite')[0], 409)
        self.assertEqual(conv['id'], self.store.conversation_for(self.user_id())['id'])

    def test_desactivee_et_status(self):
        c = self.client()
        self.app.session_idle_minutes = 0
        self.send(c, 'un')
        self.clock[0] += 1000000
        self.send(c, 'deux')
        self.assertEqual(len(set(self.engine.sessions)), 1)
        raw = self.send(c, '/status')[1]
        self.assertIn('Rotation auto : désactivée', raw)
        self.assertIn('6 message(s)', raw)

    def test_new_coupe_chaine(self):
        c = self.client()
        self.send(c, 'avant')
        self.clock[0] += 241 * 60
        self.send(c, 'suite')
        self.send(c, '/new')
        self.assertEqual(self.messages(c), [])
        self.send(c, 'neuf')
        self.assertIsNone(self.engine.instructions[-1])
        self.assertEqual(len(self.messages(c)), 2)

    def test_echec_reessaie_passation(self):
        c = self.client()
        self.send(c, 'avant')
        self.clock[0] += 241 * 60
        self.engine.fail_next = True
        self.assertEqual(self.send(c, 'échec')[0], 502)
        # Nouveau contrat : 503 ne prouve pas une absence d'effet à travers un proxy.
        self.assertEqual(self.send(c, 'réessai sans preuve')[0], 429)
        key = self.store._one("SELECT key FROM budget_entries WHERE state='unknown'")['key']
        # Dans CE faux moteur, fail_next refuse avant de créer un run : preuve locale.
        self.assertEqual(len(self.engine.runs), 1)
        self.store.budget.reconcile_unknown(key, 0, 'Fixture FakeEngine : rejet avant création du run',
                                            self.user_id(), self.clock[0])
        self.assertEqual(self.send(c, 'réessai')[0], 200)
        self.assertIn('Utilisateur : avant', self.engine.instructions[-1])

    def test_passation_limitee(self):
        c = self.client()
        conv = self.store.conversation_for(self.user_id())
        for i in range(12):
            self.store.add_message(conv['id'], 'user', str(i) + 'x' * 1000, created_at=self.clock[0])
        self.clock[0] += 241 * 60
        self.send(c, 'suite')
        handoff = self.engine.instructions[-1]
        self.assertLessEqual(len(handoff), 4000)
        self.assertIn('11' + 'x' * 20, handoff)
        self.assertIn('…', handoff)
        self.assertNotIn('Utilisateur : 4' + 'x' * 20, handoff)

    def test_chaine_limitee_200(self):
        c = self.client()
        conv = self.store.conversation_for(self.user_id())
        for i in range(205):
            self.store.add_message(conv['id'], 'user', str(i), created_at=self.clock[0])
        self.clock[0] += 241 * 60
        self.send(c, 'suite')
        msgs = self.messages(c)
        self.assertEqual(len(msgs), 200)
        self.assertEqual(msgs[0]['text'], '7')
