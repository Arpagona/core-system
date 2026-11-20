import http.client
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import bridge

SID = '20261120_071804_09c429dc'
ID = 't_12345678'


class AlphaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir='/home/thibaud/.hermes/profiles/gpt5/cache/scratch')
        cls.root = Path(cls.tmp.name)
        # Snapshot réel copié par l'API backup SQLite, jamais de mutation sur la source.
        source = sqlite3.connect('file:/home/thibaud/.hermes/kanban.db?mode=ro', uri=True)
        copied = sqlite3.connect(cls.root / 'copied.db')
        source.backup(copied); source.close(); copied.close()
        # Fixture dédiée pour tester précisément les états et les injections.
        c = sqlite3.connect(cls.root / 'fixture-source.db')
        c.execute('create table tasks(id text primary key,title text,body text,status text,tenant text,block_kind text,created_at integer,assignee text)')
        c.execute('insert into tasks values (?,?,?,?,?,?,?,?)', (ID,'Projet test','Fixture','blocked','prof','needs_input',1,None))
        c.commit(); c.close()
        shutil.copyfile(cls.root / 'fixture-source.db',cls.root / 'fixture.db')
        (cls.root / 'map.json').write_text(json.dumps({'umbrellas':{'cours':ID},'projects':{}}))
        (cls.root / 'ask.py').write_text('import json,sys\nprint("1. [decider] Fixture (2026-11-20 ; fixture.md)\\n1 question(s) ouverte(s)." if sys.argv[1]=="list" else json.dumps({"target":sys.argv[2],"action":sys.argv[3]}))\n')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.patches = [patch.object(server,'TOKEN','fixture-token'),patch.object(server,'COOKIE','fixture-cookie'),patch.object(server,'KANBAN_DB',self.root/'fixture.db'),patch.object(server,'MAPPING',self.root/'map.json'),patch.object(server,'ASK',self.root/'ask.py'),patch.object(server,'old_api',side_effect=self.fake_bridge)]
        for p in self.patches: p.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever);self.thread.start()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        for p in reversed(self.patches):p.stop()

    def fake_bridge(self,path,body=None):
        if path=='/api/channels':return {'channels':[{'profile':'gpt5','session':SID},{'profile':'task','session':'other'}]}
        if path.startswith('/api/channel/messages'):return {'session':SID,'profile':'gpt5','messages':[{'role':'assistant','text':'Fixture'}]}
        if path.startswith('/api/channel/reply'):return {'state':'ready','text':'Fixture'}
        if path=='/api/channel/send':return {'ok':True,'session':body['id']}
        raise AssertionError(path)

    def request(self,path,body=None,auth=True,extra=None):
        headers={'X-MC-Token':'fixture-token','X-Gona':'1'} if auth else {}
        headers.update(extra or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        conn.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),headers)
        r=conn.getresponse();raw=r.read();status=r.status;heads=dict(r.getheaders());conn.close()
        return status,heads,json.loads(raw) if heads['Content-Type']=='application/json' else raw

    def test_auth_and_brand(self):
        self.assertEqual(self.request('/api/kanban/list',auth=False)[0],401)
        code,h,raw=self.request('/?t=fixture-token',auth=False)
        self.assertEqual(code,303);self.assertEqual(h['Location'],'/');self.assertIn('HttpOnly',h['Set-Cookie'])
        self.assertIn(b'ARPAGONA',self.request('/')[2])
        self.assertEqual(self.request('/api/me',auth=False,extra={'Cookie':'gona_mc=fixture-cookie'})[0],200)

    def test_login_logout(self):
        self.assertEqual(self.request('/api/login',{'password':'fixture-token'},auth=False,extra={'X-Gona':'1'})[0],200)
        self.assertEqual(self.request('/api/logout',{})[0],200)

    def test_csrf(self):
        self.assertEqual(self.request('/api/login',{'password':'fixture-token'},auth=False)[0],400)
        self.assertEqual(self.request('/api/logout',{},extra={'Origin':'http://evil.invalid'})[0],403)

    def test_read_only_cards(self):
        data=self.request('/kanban')[2]
        self.assertEqual(data['total'],1);self.assertEqual(data['tasks'][0]['block_kind'],'needs_input')
        self.assertIsNone(data['tasks'][0]['assignee'])
        self.assertEqual(self.request('/api/kanban/show?id='+ID)[2]['task']['title'],'Projet test')
        self.assertEqual(self.request('/api/kanban/show?id=t_12345678%27')[0],400)

    def test_real_snapshot_count(self):
        with patch.object(server,'KANBAN_DB',self.root/'copied.db'):
            count=server.read_kanban()['total']
        c=sqlite3.connect(self.root/'copied.db')
        self.assertEqual(count,c.execute('select count(*) from tasks').fetchone()[0]);c.close()

    def test_read_connection_is_mode_ro(self):
        real=sqlite3.connect
        with patch.object(server.sqlite3,'connect',wraps=real) as connect:
            server.read_kanban()
            self.assertIn('?mode=ro',connect.call_args.args[0]);self.assertTrue(connect.call_args.kwargs['uri'])

    def test_ask_script_list_and_decide_fixture_only(self):
        expected=subprocess.check_output(['/usr/bin/python3',str(self.root/'ask.py'),'list'],text=True)
        self.assertEqual(self.request('/api/decisions')[2]['text'],expected)
        self.assertEqual(self.request('/api/decisions/decide',{'target':'1','action':'seen'})[2]['action'],'seen')
        self.assertEqual(self.request('/api/decisions/decide',{'target':'../fixture','action':'seen'})[0],400)

    def test_chat_bridge_same_session_fixture_only(self):
        self.assertEqual(self.request('/api/channels')[2]['channels'],[{'profile':'gpt5','session':SID}])
        self.assertEqual(self.request('/api/channel/messages?id='+SID)[2]['session'],SID)
        self.assertEqual(self.request('/api/chat',{'id':SID,'text':'fixture','submission_id':'imac-mc-fixture-12345678'})[2]['session'],SID)
        self.assertEqual(self.request('/api/chat',{'id':'orphan','text':'fixture','submission_id':'imac-mc-fixture-12345678'})[0],400)

    def test_create_mock_cli_no_assignee(self):
        runner=Mock(return_value=subprocess.CompletedProcess([],0,'{"id":"fixture"}'))
        bridge.execute('create',{'title':'--assignee=intrus','body':'test'},runner)
        args=runner.call_args.args[0]
        self.assertEqual(args[:7],[bridge.CLI,'-p','gpt5','kanban','--board','default','create'])
        self.assertEqual(args[-2:],['--','--assignee=intrus'])
        self.assertNotIn('--assignee',args)
        self.assertEqual(self.request('/api/kanban/create',{'title':'fixture','assignee':'gpt5'})[0],400)

    def test_forbid_existing_mutations(self):
        for op in ('comment','complete','archive','block','unblock','dispatch'):
            self.assertEqual(self.request('/api/kanban/'+op,{'id':ID})[0],404)
            with self.assertRaises(ValueError):bridge.arguments(op,{'id':ID})

    def test_backend_failure_does_not_leak(self):
        with patch.object(server,'old_api',side_effect=RuntimeError('SECRET')):
            status,_,body=self.request('/api/channels')
            self.assertEqual(status,502);self.assertNotIn('SECRET',str(body))

    def test_commands_and_native_stop(self):
        data=self.request('/api/commands')[2]
        self.assertIn('/stop',[c['command'] for c in data['commands']])
        with patch.object(server,'live_op',return_value={'ok':True,'status':'interrupted'}) as op:
            out=self.request('/api/command',{'id':SID,'command':'/stop'})[2]
        self.assertTrue(out['ok']);self.assertIn('Interruption',out['text'])
        self.assertEqual(op.call_args.args[0],{'id':SID,'op':'interrupt'})

    def test_control_respond_forwards_only_allowed_fields(self):
        with patch.object(server,'live_op',return_value={'ok':True,'status':'delivered'}) as op:
            out=self.request('/api/control/respond',{'id':SID,'kind':'approval','prompt_id':'p_1',
                                                      'choice':'once','generation':43})[2]
        self.assertTrue(out['ok'])
        self.assertEqual(op.call_args.args[0],{'id':SID,'op':'respond','kind':'approval',
                                               'prompt_id':'p_1','generation':43,'choice':'once'})
        self.assertEqual(self.request('/api/control/respond',{'id':SID,'kind':'approval','prompt_id':'p','choice':'rm -rf'})[0],400)
        self.assertEqual(self.request('/api/control/respond',{'id':SID,'kind':'nope','prompt_id':'p'})[0],400)

    def test_media_allowlist_and_content_type(self):
        pic=self.root/'pic.png';pic.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        with patch.object(server,'MEDIA_ROOTS',(self.root,)):
            status,heads,raw=self.request('/api/media?path='+str(pic))
        self.assertEqual(status,200);self.assertEqual(heads['Content-Type'],'image/png');self.assertIn(b'fixture',raw)
        with patch.object(server,'MEDIA_ROOTS',(self.root,)):
            self.assertEqual(self.request('/api/media?path=/etc/passwd')[0],400)
            self.assertEqual(self.request('/api/media?path=relative.png')[0],400)

    def test_sse_relays_sanitized_lines(self):
        fake=self.root/'live.py'
        fake.write_text('import json,sys\njson.load(sys.stdin)\n'
                        'print(\'{"type":"ready"}\',flush=True)\n'
                        'print(\'{"type":"delta","text":"bonjour"}\',flush=True)\n')
        with patch.object(server,'HERMES_PY',Path(sys.executable)),patch.object(server,'LIVE',fake),patch.object(server,'HERMES',self.root):
            status,heads,raw=self.request('/api/stream?id='+SID)
        self.assertEqual(status,200)
        self.assertTrue(heads['Content-Type'].startswith('text/event-stream'))
        self.assertIn(b'"type":"ready"',raw)
        self.assertIn(b'"text":"bonjour"',raw)


if __name__=='__main__':unittest.main()
