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


class SessionDurationTest(unittest.TestCase):
    def test_session_lasts_90_days_and_survives_a_week(self):
        import time
        from arpagona_api import store as st
        with tempfile.TemporaryDirectory() as d:
            store = Store(str(Path(d) / "a.db"))
            uid = store.add_user("alice", "Alice", "mot-de-passe-long")
            token = store.open_session(uid)
            self.assertEqual(st.SESSION_TTL_S, 90 * 24 * 3600)
            real = time.time
            try:
                time.time = lambda: real() + 7 * 24 * 3600
                self.assertIsNotNone(store.user_for_token(token))
                time.time = lambda: real() + 91 * 24 * 3600
                self.assertIsNone(store.user_for_token(token))
            finally:
                time.time = real


if __name__ == "__main__":
    unittest.main()
