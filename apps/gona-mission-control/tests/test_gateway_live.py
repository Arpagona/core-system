import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gateway_live as live


class GatewayLiveTests(unittest.TestCase):
    def test_delta_and_writing(self):
        self.assertEqual(live.sanitize_event({'type': 'message.start', 'payload': {}}), {
            'session': '', 'admission': '', 'generation': None, 'type': 'writing'})
        out = live.sanitize_event({'type': 'message.delta', 'session_id': 's', 'payload': {'text': '<b>x</b>'}})
        self.assertEqual(out['text'], '<b>x</b>')
        self.assertEqual(out['type'], 'delta')
        self.assertNotIn('payload', out)

    def test_tool_never_exposes_args(self):
        params = {'type': 'tool.start', 'session_id': 's', 'payload': {
            'name': 'terminal', 'args': {'command': 'OPENCODE_GO_API_KEY="secret123" ls'},
            'context': 'OPENCODE_GO_API_KEY="secret123" curl https://example.test'}}
        out = live.sanitize_event(params)
        self.assertEqual(out['type'], 'tool')
        self.assertEqual(out['name'], 'terminal')
        self.assertNotIn('secret123', str(out))
        self.assertNotIn('args', out)
        self.assertLessEqual(len(out['preview']), 41)

    def test_real_capture_fixture(self):
        path = Path(__file__).parent / 'fixtures' / 'gateway_events.json'
        events = json.loads(path.read_text())['events']
        out = [live.sanitize_event(event) for event in events]
        self.assertEqual(out[0]['type'], 'info')
        self.assertEqual(out[0]['info']['model'], 'claude-opus-5-5')
        self.assertEqual(out[1]['type'], 'writing')
        self.assertEqual(out[3]['type'], 'tool')
        self.assertEqual(out[3]['name'], 'terminal')
        self.assertNotIn('fixture-secret', str(out))
        self.assertEqual(out[5]['type'], 'delta')
        self.assertEqual(out[5]['text'], 'Bonjour')
        self.assertEqual(out[6]['type'], 'complete')
        self.assertEqual(out[6]['status'], 'complete')

    def test_authorization_and_long_tokens(self):
        for value in ('Authorization: Bearer abc.def.ghi', 'api_key=abcdef', 'sk-abcdefgh12345678'):
            self.assertNotIn('abcdef', live.redact(value))

    def test_approval_and_clarify_prompts(self):
        approval = live.sanitize_event({'type': 'approval.request', 'payload': {
            'kind': 'approval', 'prompt_id': 'p1', 'execution_generation': 7,
            'command': 'rm -rf x', 'description': 'danger', 'choices': ['once', 'deny'], 'timeout_s': 30}})
        self.assertEqual(approval['type'], 'control')
        self.assertEqual(approval['prompt']['kind'], 'approval')
        self.assertEqual(approval['prompt']['choices'], ['once', 'deny'])
        clarify = live.sanitize_event({'type': 'clarify.request', 'payload': {
            'kind': 'clarify', 'prompt_id': 'q1', 'question': 'Quel format ?',
            'choices': ['court', 'long'], 'multi_select': False}})
        self.assertEqual(clarify['prompt']['question'], 'Quel format ?')
        self.assertEqual(clarify['prompt']['choices'], ['court', 'long'])

    def test_snapshot_redacts_prompt_and_hides_messages(self):
        state = {'stored_session_id': 's', 'running': False, 'execution_generation': 2,
                 'last_sequence': 4, 'info': {'model': 'm', 'title': 't'},
                 'prompts': [{'kind': 'approval', 'prompt_id': 'p', 'command': 'token=abcdef'}],
                 'messages': [{'text': 'private'}]}
        out = live.snapshot_event(state)
        self.assertEqual(out['type'], 'snapshot')
        self.assertNotIn('messages', out)
        self.assertNotIn('abcdef', str(out))

    def test_validate_rejects_injection(self):
        for value in ({}, {'id': '../x'}, {'id': 's', 'op': 'nope'},
                      {'id': 's', 'op': 'respond', 'kind': 'approval', 'prompt_id': 'p'},
                      {'id': 's', 'op': 'interrupt', 'extra': 1}):
            with self.assertRaises(ValueError):
                live.validate(value)
        self.assertEqual(live.validate({'id': 's', 'op': 'interrupt'}), 'interrupt')


if __name__ == '__main__':
    unittest.main()
