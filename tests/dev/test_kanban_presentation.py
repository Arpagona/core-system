"""Régressions de l'affichage Kanban et fidélité de son faux CLI, sans service réel."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


class KanbanPresentationTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node requis pour les tests de présentation JavaScript')
    def test_javascript_filter_order_and_labels(self):
        result=subprocess.run(['node','--test',str(ROOT/'tests/ui/kanban-view.test.cjs')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_simulator_persists_human_owner_and_block_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,ARPAGONA_DEV_KANBAN_FILE=str(Path(tmp)/'board.json'))
            def cli(*args):
                result=subprocess.run([sys.executable,str(ROOT/'dev/kanban_simule.py'),'kanban',*args],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                return result.stdout
            created=json.loads(cli('create','--assignee=demo','--created-by=demo','--body=Résultat fictif','--json','--','Carte fictive'))
            self.assertEqual((created['assignee'],created['created_by']),('demo','demo'))
            ident=created['id']
            cli('assign','--',ident,'lea')
            self.assertEqual(json.loads(cli('show',ident,'--json'))['task']['assignee'],'lea')
            reason='Attendre la validation pour reprendre.'
            cli('block','--',ident,reason)
            shown=json.loads(cli('show',ident,'--json'))
            self.assertEqual(shown['task']['status'],'blocked')
            self.assertEqual(shown['events'][-1]['payload']['reason'],reason)
