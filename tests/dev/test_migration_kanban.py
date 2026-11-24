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
            assert who == "hermes-arpagona", "l'ancien tableau personnel est lu en SQLite, jamais par la CLI"
            return subprocess.CompletedProcess(cmd, 0, json.dumps(self.company), "")
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
        return migre.migrate("/cli", "/home/legacy", ["mael", "thibaud"], cli, reader=lambda login: self.personal[login]), cli

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
            migre.migrate("/cli", "/h", ["Mael;rm"], FakeCli({}, []), reader=lambda login: [])

    def test_lecture_sqlite_en_lecture_seule(self):
        import sqlite3, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "kanban.db"
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE tasks (id TEXT, title TEXT, body TEXT, status TEXT)")
            con.execute("INSERT INTO tasks VALUES ('t_1','Titre','Corps','ready')")
            con.commit(); con.close()
            before = db.read_bytes()
            real = migre.sqlite3.connect
            migre.sqlite3.connect = lambda target, **kw: real(target.replace("/srv/agents/mael/.hermes/kanban.db", str(db)), **kw)
            try:
                self.assertEqual(migre.read_personal_cards("mael"), [{"id": "t_1", "title": "Titre", "body": "Corps", "status": "ready"}])
            finally:
                migre.sqlite3.connect = real
            self.assertEqual(db.read_bytes(), before)
        with self.assertRaises(OSError):
            migre.read_personal_cards("absent-xyz")


if __name__ == "__main__":
    unittest.main()
