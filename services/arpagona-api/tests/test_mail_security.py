"""Tests adversariaux synthétiques : enveloppe, concurrence SQLite, reprise et SMTP réel local."""
import concurrent.futures
import email
import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from arpagona_api.engagements import mail_fingerprint, fingerprint
from arpagona_api.mailer import Mailer, MailError, mailbox
from arpagona_api.store import Store


class MailStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 't.db')
        self.store = Store(self.path)
        self.uid = self.store.add_user('owner', 'Owner', 'fictif-password-only')
        self.eid = self.store.add_engagement(self.uid, 'Dupont', 'Devis', 'relancer', 1, '+0100', 'hier', 'certain', None)
        self.fp = mail_fingerprint('to@example.invalid', 'Objet', 'Corps', 'from@example.invalid')
        self.did = self.store.add_draft(self.eid, self.uid, 'to@example.invalid', 'Corps', self.fp,
                                        'Objet', 'from@example.invalid')
        self.store.decide_draft(self.did, True, self.uid, self.fp)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_canonical_fields_all_matter(self):
        fields = ['to@example.invalid', 'Objet', 'Corps', 'from@example.invalid']
        for i in range(4):
            changed = fields.copy(); changed[i] += ' '
            self.assertNotEqual(self.fp, mail_fingerprint(*changed))

    def test_mutation_subject_refused(self):
        self.store._run("UPDATE drafts SET subject='Autre' WHERE id=?", (self.did,))
        self.assertEqual(self.store.claim_send(self.did, self.uid, self.fp)[0], 'contenu_modifie')

    def test_two_connections_one_claim(self):
        other = Store(self.path)
        barrier = threading.Barrier(2)
        def claim(s):
            barrier.wait()
            return s.claim_send(self.did, self.uid, self.fp)[0]
        try:
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                a = pool.submit(claim, self.store); b = pool.submit(claim, other)
                codes = [a.result(), b.result()]
            self.assertEqual(codes.count('ok'), 1)
            self.assertEqual(codes.count('deja_en_cours'), 1)
        finally:
            other.close()

    def test_restart_after_claim_does_not_replay(self):
        code, row = self.store.claim_send(self.did, self.uid, self.fp)
        self.assertEqual(code, 'ok')
        mid = row['send_message_id']; self.assertTrue(mid)
        other = Store(self.path)
        try:
            self.assertEqual(other.claim_send(self.did, self.uid, self.fp)[0], 'deja_en_cours')
            other.set_delivery_note(self.did, 'note tardive')
            self.assertEqual(other.draft(self.did)['delivery'], 'envoi_en_cours')
            self.assertEqual(other.draft(self.did)['send_message_id'], mid)
        finally:
            other.close()

    def test_legacy_draft_cannot_be_sent(self):
        fp = fingerprint('to@example.invalid', 'Corps')
        d = self.store.add_draft(self.eid, self.uid, 'to@example.invalid', 'Corps', fp)
        self.store.decide_draft(d, True, self.uid, fp)
        self.assertEqual(self.store.claim_send(d, self.uid, fp)[0], 'ancien_brouillon')


class SMTPWireTest(unittest.TestCase):
    def test_real_local_smtp_envelope_and_message_id(self):
        messages, commands = [], []
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.wfile.write(b'220 localhost test\r\n')
                while True:
                    line = self.rfile.readline()
                    if not line: break
                    commands.append(line.decode().strip())
                    verb = line.split()[0].upper()
                    if verb == b'DATA':
                        self.wfile.write(b'354 data\r\n')
                        chunks = []
                        while True:
                            part = self.rfile.readline()
                            if part == b'.\r\n' or not part: break
                            chunks.append(part)
                        messages.append(b''.join(chunks))
                        self.wfile.write(b'250 accepted\r\n')
                    elif verb == b'QUIT':
                        # Serveur accepté puis QUIT rompu : succès, pas un faux échec.
                        return
                    else:
                        self.wfile.write(b'250 localhost\r\n')
        server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            m = Mailer('127.0.0.1', server.server_address[1], sender='from@example.invalid', starttls=False)
            mid = m.send('to@example.invalid', 'Objet exact', 'Corps exact', message_id='<persisted@example.invalid>')
            self.assertEqual(mid, '<persisted@example.invalid>')
            self.assertEqual(len(messages), 1)
            msg = email.message_from_bytes(messages[0])
            self.assertEqual(msg['Subject'], 'Objet exact')
            self.assertEqual(msg['Message-ID'], mid)
            self.assertIn('rcpt TO:<to@example.invalid>'.lower(), [c.lower() for c in commands])
        finally:
            server.shutdown(); server.server_close()

    def test_plaintext_auth_or_remote_forbidden(self):
        for host, user in [('smtp.example.invalid', ''), ('127.0.0.1', 'user')]:
            with self.assertRaises(ValueError):
                Mailer(host, user=user, starttls=False)

    def test_multiple_recipients_and_header_injection_refused(self):
        for addr in ['a@example.invalid,b@example.invalid', 'A <a@example.invalid>', 'a@example.invalid\r\nBcc:x@y', 'x']:
            with self.assertRaises(MailError): mailbox(addr)

    def test_recette_allowlist_before_network(self):
        m = Mailer('smtp.example.invalid', sender='from@example.invalid', allowed_to=('self@example.invalid',))
        with patch('arpagona_api.mailer.smtplib.SMTP') as smtp:
            with self.assertRaises(MailError):
                m.send('client@example.invalid', 'Objet', 'Corps')
            smtp.assert_not_called()

    def test_disconnect_during_submission_is_uncertain(self):
        with patch('arpagona_api.mailer.smtplib.SMTP') as factory:
            factory.return_value.send_message.side_effect = OSError('dropped')
            m = Mailer('127.0.0.1', 2525, sender='from@example.invalid', starttls=False)
            with self.assertRaises(MailError) as caught:
                m.send('to@example.invalid', 'Objet', 'Corps', '<stable@example.invalid>')
            self.assertTrue(caught.exception.uncertain)
