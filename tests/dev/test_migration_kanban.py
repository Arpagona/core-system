"""Reprise des cartes des anciens Kanban personnels dans le Kanban d'entreprise : sans perte, sans doublon."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("migre", Path(__file__).resolve().parents[2] / "deploy/atlas/migrate_kanban_equipe.py")
migre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migre)


class FakeCli:
    def __init__(self, personal, company):
        self.personal, self.company, self.calls = personal, company, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        who = cmd[cmd.index("-u") + 1]
        verb = cmd[cmd.index("kanban") + 1]
        if verb == "list":
            data = self.company if who == "hermes-arpagona" else self.personal[who.removeprefix("agent-")]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(data), "")
        assert who == "hermes-arpagona", "les anciens tableaux personnels ne sont jamais modifiés"
        if verb == "create":
            key = next(a for a in cmd if a.startswith("--idempotency-key=")).split("=", 1)[1]
            found = next((t for t in self.company if t.get("idempotency_key") == key), None)
            if not found:
                found = {"id": f"t_{len(self.company) + 1:08x}", "idempotency_key": key,
                         "assignee": next(a for a in cmd if a.startswith("--assignee=")).split("=", 1)[1], "title": cmd[-1]}
                self.company.append(found)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(found), "")
        return subprocess.CompletedProcess(cmd, 0, "", "")


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.personal = {"mael": [{"id": "t_aaaaaaa1", "title": "[MAEL] carte", "body": "b", "status": "ready"},
                                  {"id": "t_aaaaaaa2", "title": "[MAEL] décision", "body": "", "status": "blocked"},
                                  {"id": "t_aaaaaaa3", "title": "[MAEL] vieille", "body": "", "status": "archived"}],
                         "thibaud": [{"id": "t_bbbbbbb1", "title": "[THIBAUD] carte", "body": "", "status": "done"}]}
        self.company = [{"id": "t_00000001", "title": "[DEMO] existante", "assignee": None, "idempotency_key": None}]

    def run_migration(self):
        cli = FakeCli(self.personal, self.company)
        return migre.migrate("/cli", "/home/legacy", ["mael", "thibaud"], cli), cli

    def test_reprise_complete_puis_rejeu_sans_doublon(self):
        report, cli = self.run_migration()
        self.assertEqual((report["reprises"], report["echecs"], report["ignorees"]), (3, 0, 1))
        self.assertEqual(len(self.company), 4)  # la carte existante + 3 reprises
        self.assertEqual({t["title"]: t["assignee"] for t in self.company if t["assignee"]},
                         {"[MAEL] carte": "mael", "[MAEL] décision": "mael", "[THIBAUD] carte": "thibaud"})
        verbs = [c[c.index("kanban") + 1] for c in cli.calls]
        self.assertEqual(verbs.count("block"), 1)
        self.assertEqual(verbs.count("complete"), 1)
        report2, _ = self.run_migration()
        self.assertEqual((report2["reprises"], report2["deja_presentes"]), (0, 3))
        self.assertEqual(len(self.company), 4)  # aucun doublon
        self.assertEqual(self.company[0]["title"], "[DEMO] existante")  # carte existante intacte

    def test_compte_invalide_refuse(self):
        with self.assertRaises(ValueError):
            migre.migrate("/cli", "/h", ["Mael;rm"], FakeCli({}, []))


if __name__ == "__main__":
    unittest.main()
