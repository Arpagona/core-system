import os, sys, tempfile, unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tok = tempfile.NamedTemporaryFile('w', suffix='.token', delete=False); _tok.write('fixture-token'); _tok.close()
os.environ.setdefault('GONA_MC_TOKEN_FILE', _tok.name); os.environ.setdefault('GONA_MC_LEGACY_TOKEN_FILE', _tok.name)
import session_rotation as sr
import server


class RotationRuleTests(unittest.TestCase):
    def test_policy_from_profile_requires_plugin(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'config.yaml').write_text('plugins:\n  enabled: [mc-new]\n')
            self.assertIsNone(sr.policy(d))
            (Path(d) / 'config.yaml').write_text('plugins:\n  enabled: [session-lifecycle]\n  entries:\n'
                                                 '    session-lifecycle:\n      settings: {idle_minutes: 90, daily_hour: 5}\n')
            self.assertEqual(sr.policy(d), {'idle_minutes': 90.0, 'daily_hour': 5})

    def test_reason(self):
        p = {'idle_minutes': 240.0, 'daily_hour': 4}
        now = datetime(2026, 11, 25, 15, 0)
        self.assertEqual(sr.reason(p, now - timedelta(minutes=241), now), 'idle')
        self.assertIsNone(sr.reason(p, now - timedelta(minutes=60), now))
        self.assertEqual(sr.reason(p, datetime(2026, 11, 25, 3, 0), datetime(2026, 11, 25, 5, 0)), 'daily')
        self.assertIsNone(sr.reason(None, now - timedelta(days=2), now))

    def test_handoff_text_bounded(self):
        rows = [('user' if i % 2 else 'assistant', 'm%d ' % i + 'z' * 900) for i in range(30)]
        t = sr.handoff_text(rows, 'idle')
        self.assertLessEqual(len(t), sr.HANDOFF_MAX_CHARS); self.assertIn('m29', t); self.assertNotIn('m21 ', t)
        self.assertIsNone(sr.handoff_text([('user', '  ')], 'idle'))


class TelegramModeRotationTests(unittest.TestCase):
    def test_rotate_when_due_and_idle(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(server, 'PROFILE', Path(d)), \
                patch.object(sr, 'policy', return_value={'idle_minutes': 240.0, 'daily_hour': -1}), \
                patch.object(sr, 'last_user_activity', return_value=datetime.now() - timedelta(hours=6)), \
                patch.object(server, 'idle_state', return_value=True), \
                patch.object(server, 'gateway_new', return_value={'ok': True, 'new_session_id': 's2'}):
            self.assertEqual(server.rotate_if_due('s1'), ('s2', 'idle'))
            self.assertIn('"old_session_id": "s1"', (Path(d) / 'session-lifecycle/rotations.jsonl').read_text())

    def test_keep_session_when_busy_recent_or_failed(self):
        base = dict(policy={'idle_minutes': 240.0, 'daily_hour': -1})
        with patch.object(sr, 'policy', return_value=base['policy']), \
                patch.object(sr, 'last_user_activity', return_value=datetime.now() - timedelta(hours=6)):
            with patch.object(server, 'idle_state', return_value=False):
                self.assertEqual(server.rotate_if_due('s1'), ('s1', None))  # tour en cours
            with patch.object(server, 'idle_state', return_value=True), \
                    patch.object(server, 'gateway_new', side_effect=RuntimeError('x')):
                self.assertEqual(server.rotate_if_due('s1'), ('s1', None))  # échec : on garde
        with patch.object(sr, 'policy', return_value=base['policy']), \
                patch.object(sr, 'last_user_activity', return_value=datetime.now() - timedelta(minutes=5)):
            self.assertEqual(server.rotate_if_due('s1'), ('s1', None))  # activité récente


if __name__ == '__main__':
    unittest.main()
