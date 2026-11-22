"""Migration : base créée avec l'ancien schéma (une conversation par compte) puis ouverte par le code actuel."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from arpagona_api.store import Store

OLD = """
CREATE TABLE users (id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
    pw_salt BLOB NOT NULL, pw_hash BLOB NOT NULL, created_at REAL NOT NULL);
CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    hermes_session_id TEXT NOT NULL UNIQUE, created_at REAL NOT NULL);
CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, run_id TEXT, created_at REAL NOT NULL);
INSERT INTO users VALUES (2, 'thibaud', 'Thibaud', x'00', x'00', 1);
INSERT INTO conversations VALUES (7, 2, 'arpagona-u2-ancienne', 1);
INSERT INTO messages VALUES (1, 7, 'user', 'bonjour', 'done', NULL, 1);
"""


class MigrationTest(unittest.TestCase):
    def test_ancienne_base_migree_sans_perte(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "old.db")
            with sqlite3.connect(path) as conn:
                conn.executescript(OLD)
            store = Store(path)
            conv = store.conversation_for(2)
            self.assertEqual((conv["id"], conv["hermes_session_id"]), (7, "arpagona-u2-ancienne"))
            self.assertEqual([m["content"] for m in store.messages(7)], ["bonjour"])
            fresh = store.new_conversation(2)
            self.assertNotEqual(fresh["hermes_session_id"], "arpagona-u2-ancienne")
            self.assertEqual(store.conversation_for(2)["id"], fresh["id"])
            self.assertEqual(store.conversation_count(2), 2)
            # L'ancienne session reste rattachée au bon compte (routes internes d'un run déjà lancé).
            owner = store.user_for_hermes_session("arpagona-u2-ancienne")
            self.assertIsNotNone(owner)
            self.assertEqual(owner["login"] if owner else None, "thibaud")
            store.close()
            # Réouverture : la migration ne se rejoue pas et l'index d'unicité tient.
            store = Store(path)
            self.assertEqual(store.conversation_for(2)["id"], fresh["id"])
            with self.assertRaises(sqlite3.IntegrityError):
                store._run("INSERT INTO conversations(user_id, hermes_session_id, created_at) VALUES (2,'x',1)")
            self.assertTrue(store.delete_user("thibaud"))
            store.close()


if __name__ == "__main__":
    unittest.main()
