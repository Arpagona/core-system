import tempfile
import unittest
from pathlib import Path

from arpagona_api.store import Store


class SetPasswordTest(unittest.TestCase):
    def test_change_password_closes_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(str(Path(d) / "a.db"))
            uid = store.add_user("alice", "Alice", "ancien-mot-de-passe")
            token = store.open_session(uid)
            self.assertTrue(store.set_password("alice", "nouveau-mot-de-passe"))
            self.assertIsNone(store.check_password("alice", "ancien-mot-de-passe"))
            self.assertIsNotNone(store.check_password("alice", "nouveau-mot-de-passe"))
            self.assertIsNone(store.user_for_token(token))

    def test_unknown_and_short(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(str(Path(d) / "a.db"))
            self.assertFalse(store.set_password("personne", "un-mot-de-passe-long"))
            store.add_user("bob", "Bob", "mot-de-passe-long")
            with self.assertRaises(ValueError):
                store.set_password("bob", "court")


if __name__ == "__main__":
    unittest.main()
