"""Agent mail personnel : brouillon dans SA boîte seulement, aucune sortie du dossier, aucun envoi."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location("arpagona_mail", ROOT / "plugins/arpagona-mail/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MailPersoTest(unittest.TestCase):
    def setUp(self):
        self.mail = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.old = dict(os.environ)
        self.boxes = {}
        for who in ("mael", "thibaud"):
            box = Path(self.tmp.name) / who
            (box / "INBOX/new").mkdir(parents=True)
            (box / "INBOX/new" / f"{who}-001").write_text(
                f"From: client@exemple.invalid\nTo: {who}@banc.invalid\nSubject: Devis {who}\n"
                f"Date: Tue, 24 Nov 2026 10:00:00 +0000\n\nBonjour {who}, secret-{who}\n", encoding="utf-8")
            self.boxes[who] = box

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        self.tmp.cleanup()

    def as_user(self, who):
        os.environ["ARPAGONA_MAIL_DIR"] = str(self.boxes[who])
        os.environ["ARPAGONA_MAIL_ADDRESS"] = f"{who}@banc.invalid"

    def test_brouillon_uniquement_dans_sa_boite(self):
        self.as_user("mael")
        out = json.loads(self.mail.draft({"a": "client@exemple.invalid", "sujet": "Relance", "corps": "Bonjour"}))
        self.assertEqual(out["statut"], "brouillon-non-envoye")
        self.assertEqual(len(list((self.boxes["mael"] / "Drafts/cur").iterdir())), 1)
        self.assertFalse((self.boxes["thibaud"] / "Drafts").exists())
        self.as_user("thibaud")
        self.assertNotIn("Relance", self.mail.inbox({}))
        self.assertFalse(any("Relance" in p.read_text() for p in self.boxes["thibaud"].rglob("*") if p.is_file()))

    def test_lecture_limitee_a_sa_boite(self):
        self.as_user("mael")
        self.assertIn("secret-mael", self.mail.read({"id": "mael-001"}))
        self.assertIn("inconnu", self.mail.read({"id": "thibaud-001"}))
        for bad in ("../../thibaud/INBOX/new/thibaud-001", "/etc/passwd", "..", ".", "a/b", ""):
            self.assertIn("invalide", self.mail.read({"id": bad}), bad)

    def test_pas_de_boite_pas_d_acces(self):
        os.environ.pop("ARPAGONA_MAIL_DIR", None)
        self.assertIn("non configurée", self.mail.inbox({}))
        self.assertIn("error", self.mail.draft({"a": "x@y.zz", "sujet": "s", "corps": "c"}))

    def test_entrees_invalides_refusees(self):
        self.as_user("mael")
        for args in ({"a": "pas-une-adresse", "sujet": "s", "corps": "c"},
                     {"a": "x@y.zz", "sujet": "s\nBcc: autre@y.zz", "corps": "c"},
                     {"a": "x@y.zz", "sujet": "", "corps": "c"},
                     {"a": "x@y.zz", "sujet": "s", "corps": "x" * 20001}):
            self.assertIn("error", self.mail.draft(args))
        self.assertFalse((self.boxes["mael"] / "Drafts").exists())

    def test_aucun_outil_d_envoi(self):
        names = [n for n in dir(self.mail) if "send" in n.lower() or "smtp" in n.lower()]
        self.assertEqual(names, [])
        self.assertNotIn("smtplib", (ROOT / "plugins/arpagona-mail/__init__.py").read_text())


if __name__ == "__main__":
    unittest.main()
