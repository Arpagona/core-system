"""Une migration ne distribue jamais des privilèges à un compte démo."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from arpagona_api.store import Store


class RoleMigrationTest(unittest.TestCase):
    def test_reopen_does_not_promote_oldest_member(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / 'test.db')
            store = Store(path)
            store.add_user('demo', 'Démo', 'fictif-test-password')
            store.close()
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE users SET role='membre'")
            store = Store(path)
            try:
                self.assertEqual(store.user_by_id(1)['role'], 'membre')
            finally:
                store.close()

    def test_last_admin_cannot_be_demoted(self):
        store = Store(':memory:')
        try:
            store.add_user('owner', 'Owner', 'fictif-test-password', role='admin')
            with self.assertRaises(ValueError):
                store.set_role('owner', 'membre')
        finally:
            store.close()
