"""Tests du plugin session-lifecycle contre un faux gateway et un state.db synthétique."""
import asyncio
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location("session_lifecycle", Path(__file__).resolve().parents[1] / "__init__.py")
sl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sl)

SETTINGS = sl.normalize_settings({"idle_minutes": 240, "daily_hour": 4, "handoff": True})
NOW = datetime(2026, 11, 25, 15, 0, 0)


def make_db(home: Path):
    c = sqlite3.connect(home / "state.db")
    c.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, parent_session_id TEXT, started_at REAL)")
    c.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT,"
              " display_kind TEXT, finish_reason TEXT, timestamp REAL)")
    c.commit()
    return c


def add(c, sid, role, content, at, kind=None, finish="stop"):
    c.execute("INSERT INTO messages(session_id, role, content, display_kind, finish_reason, timestamp)"
              " VALUES (?,?,?,?,?,?)", (sid, role, content, kind, finish if role == "assistant" else None,
                                        at.timestamp()))
    c.commit()


class FakeStore:
    def __init__(self, db, sid="s1"):
        self.db, self.entry, self.n = db, SimpleNamespace(session_id=sid, active_turn_token=None), 1

    def lookup_by_session_key(self, key):
        return self.entry

    def reset_session(self, key):
        self.n += 1
        old = self.entry.session_id
        new = f"s{self.n}"
        self.db.execute("INSERT INTO sessions(id, parent_session_id, started_at) VALUES (?,?,?)",
                        (new, old, NOW.timestamp()))
        self.db.commit()
        self.entry = SimpleNamespace(session_id=new, active_turn_token=None)
        return self.entry


class FakeGateway:
    def __init__(self, home, store):
        self.home, self.store, self.resets = home, store, 0

    def _session_key_for_source(self, source):
        return "agent:gpt5:telegram:dm:1"

    def _resolve_profile_home_for_source(self, source):
        return self.home

    async def _handle_reset_command(self, event):
        self.resets += 1
        self.store.reset_session("k")


def event(text="bonjour"):
    return SimpleNamespace(text=text, source=SimpleNamespace(profile="gpt5"),
                           get_command=lambda: text[1:].split()[0] if text.startswith("/") else None)


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.db = make_db(self.home)
        self.db.execute("INSERT INTO sessions VALUES ('s1', NULL, ?)", ((NOW - timedelta(hours=6)).timestamp(),))
        self.store = FakeStore(self.db)
        self.gw = FakeGateway(self.home, self.store)
        self.clock = NOW

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def hooks(self, settings=SETTINGS):
        return sl.make_hooks(self.home, settings_for=lambda h: settings, clock=lambda: self.clock)

    def dispatch(self, ev, settings=SETTINGS):
        rotate, _ = self.hooks(settings)
        return asyncio.run(rotate(event=ev, gateway=self.gw, session_store=self.store))

    def test_reason_idle_daily_and_disabled(self):
        r = sl.rotation_reason
        self.assertEqual(r(SETTINGS, NOW - timedelta(minutes=241), NOW), "idle")
        self.assertIsNone(r(SETTINGS, NOW - timedelta(minutes=239), NOW))
        self.assertEqual(r(SETTINGS, datetime(2026, 11, 25, 3, 0), datetime(2026, 11, 25, 5, 0)), "daily")
        self.assertIsNone(r(SETTINGS, datetime(2026, 11, 25, 4, 30), datetime(2026, 11, 25, 6, 0)))
        off = sl.normalize_settings({"idle_minutes": 0, "daily_hour": -1})
        self.assertIsNone(r(off, NOW - timedelta(days=3), NOW))
        self.assertIsNone(r(SETTINGS, None, NOW))

    def test_idle_rotation_then_single_handoff(self):
        add(self.db, "s1", "user", "Peux-tu chiffrer le devis Dupont ?", NOW - timedelta(hours=5))
        add(self.db, "s1", "assistant", "Devis Dupont : 1 240 € HT, point 2 en attente.", NOW - timedelta(hours=5))
        self.dispatch(event())
        self.assertEqual(self.gw.resets, 1)
        self.assertEqual(self.store.entry.session_id, "s2")
        rec = json.loads((self.home / "session-lifecycle/rotations.jsonl").read_text().splitlines()[-1])
        self.assertEqual((rec["old_session_id"], rec["new_session_id"], rec["reason"]), ("s1", "s2", "idle"))
        _, handoff = self.hooks()
        out = handoff(session_id="s2", is_first_turn=True, conversation_history=[])
        self.assertIn("Devis Dupont : 1 240 € HT", out["context"])
        self.assertIn("Utilisateur : Peux-tu chiffrer", out["context"])
        self.assertIsNone(handoff(session_id="s2", is_first_turn=True, conversation_history=[]))  # une seule fois
        # La nouvelle session n'a pas encore de message utilisateur : un second message ne retourne pas.
        self.dispatch(event())
        self.assertEqual(self.gw.resets, 1)

    def test_recent_activity_no_rotation(self):
        add(self.db, "s1", "user", "salut", NOW - timedelta(minutes=30))
        self.dispatch(event())
        self.assertEqual(self.gw.resets, 0)

    def test_internal_messages_do_not_count_as_activity(self):
        add(self.db, "s1", "user", "vrai message", NOW - timedelta(hours=5))
        add(self.db, "s1", "user", "fin de délégation", NOW - timedelta(minutes=5), kind="internal_notification")
        self.dispatch(event())
        self.assertEqual(self.gw.resets, 1)

    def test_commands_in_flight_and_disabled_profile(self):
        add(self.db, "s1", "user", "vieux", NOW - timedelta(hours=5))
        self.dispatch(event("/status"))
        self.store.entry.active_turn_token = "tour"
        self.dispatch(event())
        self.store.entry.active_turn_token = None
        self.dispatch(event(), settings=None)
        self.assertEqual(self.gw.resets, 0)

    def test_empty_session_never_rotates(self):
        self.dispatch(event())
        self.assertEqual(self.gw.resets, 0)

    def test_manual_new_gets_no_handoff(self):
        add(self.db, "s1", "user", "on repart à zéro", NOW - timedelta(hours=1))
        self.store.reset_session("k")  # /new manuel : aucune trace de rotation automatique
        _, handoff = self.hooks()
        self.assertIsNone(handoff(session_id="s2", is_first_turn=True, conversation_history=[]))

    def test_mission_control_rotation_record_enables_handoff(self):
        add(self.db, "s1", "user", "question depuis Mission Control", NOW - timedelta(hours=5))
        self.store.reset_session("k")
        sl.record_rotation(self.home, "s1", "s2", "daily", "mission-control")
        _, handoff = self.hooks()
        out = handoff(session_id="s2", is_first_turn=True, conversation_history=[])
        self.assertIn("frontière quotidienne", out["context"])

    def test_subagent_of_rotated_parent_gets_no_handoff(self):
        add(self.db, "s1", "user", "vieux", NOW - timedelta(hours=5))
        self.dispatch(event())  # s1 -> s2, trace
        self.db.execute("INSERT INTO sessions VALUES ('sub', 's1', ?)", (NOW.timestamp(),)); self.db.commit()
        _, handoff = self.hooks()
        self.assertIsNone(handoff(session_id="sub", is_first_turn=True, conversation_history=[]))
        self.assertIsNotNone(handoff(session_id="s2", is_first_turn=True, conversation_history=[]))

    def test_handoff_truncation_and_filtering(self):
        for i in range(20):
            add(self.db, "s1", "user", f"question {i} " + "x" * 900, NOW - timedelta(hours=5, minutes=20 - i))
            add(self.db, "s1", "assistant", "", NOW - timedelta(hours=5), finish="tool_calls")
            add(self.db, "s1", "assistant", f"réponse {i} " + "y" * 900, NOW - timedelta(hours=5, minutes=20 - i))
        text = sl.build_handoff(self.home, "s1", "idle")
        self.assertLessEqual(len(text), sl.HANDOFF_MAX_CHARS)
        self.assertIn("réponse 19", text)
        self.assertNotIn("question 5 ", text)
        self.assertTrue(all(len(line) <= sl.HANDOFF_PER_MESSAGE + 20 for line in text.splitlines()[1:]))

    def test_profile_settings_requires_enable(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML absent")
        cfg = self.home / "config.yaml"
        cfg.write_text("plugins:\n  enabled: [autre]\n", encoding="utf-8")
        self.assertIsNone(sl.profile_settings(self.home))
        sl._SETTINGS_CACHE.clear()
        cfg.write_text("plugins:\n  enabled: [session-lifecycle]\n", encoding="utf-8")
        self.assertIsNone(sl.profile_settings(self.home))  # activé sans réglages : n'agit pas
        cfg.write_text("plugins:\n  enabled: [session-lifecycle]\n  entries:\n    session-lifecycle:\n"
                       "      settings:\n        idle_minutes: 90\n        daily_hour: -1\n", encoding="utf-8")
        sl._SETTINGS_CACHE.clear()
        s = sl.profile_settings(self.home)
        self.assertEqual((s["idle_minutes"], s["daily_hour"], s["handoff"]), (90.0, -1, True))


if __name__ == "__main__":
    unittest.main()
