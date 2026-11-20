import json, os, shutil, sqlite3, tempfile, unittest
from pathlib import Path
from unittest import mock

class GateTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); (self.d/'refonte/loop').mkdir(parents=True); (self.d/'scripts').mkdir()
        db = self.d/'k.db'; c = sqlite3.connect(db)
        c.execute('create table tasks(id,title,tenant,created_at,status,block_kind,assignee)')
        c.execute('create table task_comments(id integer primary key,task_id,body)')
        c.execute("insert into tasks values('t_aaaaaaaa','Vase','lab3d',1,'blocked','needs_input',null)")
        c.execute("insert into tasks values('t_bbbbbbbb','Sans question','lab3d',2,'blocked','needs_input',null)")
        c.execute("insert into task_comments(task_id,body) values('t_bbbbbbbb','BLOCKED: GONA attend Thibaud')"); c.commit(); c.close()
        (self.d/'refonte/loop/gate.json').write_text(json.dumps({'t_aaaaaaaa':{'question':'On imprime ?','oui':{'effect':'unblock','note':'go'},'non':{'effect':'close','note':'stop'}}}))
        os.environ['GONA_PROFILE']=str(self.d); os.environ['HERMES_KANBAN_DB']=str(db)
        import importlib, gate; self.g = importlib.reload(gate)
    def test_items_and_decide_idempotent(self):
        it = {i['id']:i for i in self.g.items()}
        self.assertEqual(it['t_aaaaaaaa']['question'], 'On imprime ?')
        self.assertIsNone(it['t_bbbbbbbb']['question'])
        self.assertIn('GONA attend', it['t_bbbbbbbb']['context'])
        with mock.patch.object(self.g, '_cli') as cli:
            r = self.g.decide('card','t_aaaaaaaa','non')
            self.assertEqual(r['effect'],'close'); self.assertEqual([c.args[0] for c in cli.call_args_list],['comment','unblock','complete'])
            r2 = self.g.decide('card','t_aaaaaaaa','oui'); self.assertTrue(r2['duplicate']); self.assertEqual(cli.call_count,3)
        self.assertNotIn('t_aaaaaaaa', [i['id'] for i in self.g.items()])
    def test_refuse_bad_input(self):
        for args in [('card','t_bbbbbbbb','oui'),('card','x','oui'),('card','t_aaaaaaaa','peut-être'),('ask','abc','oui')]:
            with self.assertRaises(ValueError): self.g.decide(*args)
if __name__=='__main__': unittest.main()
