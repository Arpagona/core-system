"""Zone commune : dossiers clients (traversées, liens, droits) et mémoire d'équipe (portier fictif)."""
import importlib.util
import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location("arpagona_equipe", ROOT / "plugins/arpagona-equipe/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClientsTest(unittest.TestCase):
    def setUp(self):
        self.eq = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.old = dict(os.environ)
        self.clients = Path(self.tmp.name) / "clients"
        self.clients.mkdir()
        self.private = Path(self.tmp.name) / "prive-mael"
        self.private.mkdir()
        (self.private / "secret.txt").write_text("CANARI-PRIVE", encoding="utf-8")
        os.environ["ARPAGONA_CLIENTS_DIR"] = str(self.clients)
        self._umask = os.umask(0o077)  # umask strict d'un service : les droits doivent venir du plugin

    def tearDown(self):
        os.umask(self._umask)
        os.environ.clear()
        os.environ.update(self.old)
        self.tmp.cleanup()

    def call(self, fn, **args):
        return json.loads(fn(args))

    def test_creer_lire_modifier_et_droits(self):
        out = self.call(self.eq.clients_write, chemin="dupont/fiche.md", contenu="Fiche Dupont")
        self.assertEqual(out.get("ecrit"), 12, out)
        f = self.clients / "dupont" / "fiche.md"
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o660)
        self.assertEqual(stat.S_IMODE(f.parent.stat().st_mode) & 0o770, 0o770)  # groupe rwx sur le dossier créé
        self.assertEqual(self.call(self.eq.clients_read, chemin="dupont/fiche.md")["contenu"], "Fiche Dupont")
        self.call(self.eq.clients_write, chemin="dupont/fiche.md", contenu=" + suite", ajouter=True)
        self.assertEqual(f.read_text(encoding="utf-8"), "Fiche Dupont + suite")
        names = [e["nom"] for e in self.call(self.eq.clients_list, chemin="dupont")["entrees"]]
        self.assertEqual(names, ["fiche.md"])

    def test_fichier_d_un_collegue_modifiable_sans_etre_proprietaire(self):
        """Un fichier existant n'est jamais chmodé : un collègue qui n'en est pas propriétaire peut le modifier."""
        self.call(self.eq.clients_write, chemin="a/fiche.md", contenu="x")
        os.chmod(self.clients / "a" / "fiche.md", 0o640)
        out = self.call(self.eq.clients_write, chemin="a/fiche.md", contenu="y", ajouter=True)
        self.assertEqual(out.get("ecrit"), 1, out)
        self.assertEqual((self.clients / "a" / "fiche.md").read_text(encoding="utf-8"), "xy")
        self.assertEqual(stat.S_IMODE((self.clients / "a" / "fiche.md").stat().st_mode), 0o640)  # droits d'un existant inchangés
        out = self.call(self.eq.clients_write, chemin="a/fiche.md", contenu="z")
        self.assertEqual((self.clients / "a" / "fiche.md").read_text(encoding="utf-8"), "z")

    def test_lien_physique_vers_un_fichier_prive_refuse_sans_changer_ses_droits(self):
        prive = self.private / "secret.txt"
        os.chmod(prive, 0o600)
        os.link(prive, self.clients / "lien-dur.txt")
        out = self.call(self.eq.clients_write, chemin="lien-dur.txt", contenu="ECRASE")
        self.assertIn("error", out)
        self.assertEqual(prive.read_text(encoding="utf-8"), "CANARI-PRIVE")
        self.assertEqual(stat.S_IMODE(prive.stat().st_mode), 0o600)  # jamais élargi

    def test_dossier_remplace_par_un_lien_entre_deux_appels(self):
        """Résolution par descripteurs : un dossier devenu lien symbolique est refusé à l'ouverture."""
        self.call(self.eq.clients_write, chemin="d/f.md", contenu="ok")
        (self.clients / "d" / "f.md").unlink()
        (self.clients / "d").rmdir()
        (self.clients / "d").symlink_to(self.private)
        self.assertIn("error", self.call(self.eq.clients_read, chemin="d/secret.txt"))
        self.assertIn("error", self.call(self.eq.clients_write, chemin="d/nouveau.txt", contenu="x"))
        self.assertIn("error", self.call(self.eq.clients_list, chemin="d"))
        self.assertFalse((self.private / "nouveau.txt").exists())

    def test_traversees_refusees(self):
        for bad in ("../prive-mael/secret.txt", "/etc/passwd", "dupont/../../prive-mael/secret.txt",
                    "a\\b", ".cache/x", "dupont/\x00x", "%2e%2e/x"):
            self.assertIn("error", self.call(self.eq.clients_read, chemin=bad), bad)
            self.assertIn("error", self.call(self.eq.clients_write, chemin=bad, contenu="x"), bad)
        self.assertFalse((Path(self.tmp.name) / "x").exists())

    def test_liens_symboliques_refuses(self):
        (self.clients / "piege").symlink_to(self.private)
        (self.clients / "fichier-piege").symlink_to(self.private / "secret.txt")
        self.assertIn("error", self.call(self.eq.clients_read, chemin="piege/secret.txt"))
        self.assertIn("error", self.call(self.eq.clients_read, chemin="fichier-piege"))
        self.assertIn("error", self.call(self.eq.clients_write, chemin="piege/nouveau.txt", contenu="x"))
        self.assertIn("error", self.call(self.eq.clients_write, chemin="fichier-piege", contenu="ECRASE"))
        self.assertEqual((self.private / "secret.txt").read_text(encoding="utf-8"), "CANARI-PRIVE")
        self.assertFalse((self.private / "nouveau.txt").exists())
        # La liste ne montre pas les liens.
        self.assertEqual(self.call(self.eq.clients_list)["entrees"], [])

    def test_racine_lien_symbolique_refusee(self):
        link = Path(self.tmp.name) / "lien"
        link.symlink_to(self.private)
        os.environ["ARPAGONA_CLIENTS_DIR"] = str(link)
        self.assertIn("error", self.call(self.eq.clients_list))

    def test_taille_et_chemin_vide(self):
        self.assertIn("error", self.call(self.eq.clients_write, chemin="", contenu="x"))
        self.assertIn("error", self.call(self.eq.clients_write, chemin="a.txt", contenu="x" * (200 * 1024 + 1)))


class FakeGate:
    def __init__(self):
        self.seen = []
        gate = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gate.seen.append((self.path, self.headers.get("Authorization"), body))
                if self.path.endswith("/recall"):
                    payload, status = {"results": [{"text": "Dupont préfère 48 h", "tags": ["auteur:mael"],
                                                    "metadata": {"auteur": "mael", "source": "réunion"}}]}, 200
                elif "secret" in json.dumps(body):
                    payload, status = {"error": "secret détecté"}, 422
                else:
                    payload, status = {"success": True}, 200
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


class MemoireEquipeTest(unittest.TestCase):
    def setUp(self):
        self.eq = load()
        self.gate = FakeGate()
        self.old = dict(os.environ)
        os.environ.update({"ARPAGONA_TEAM_MEMORY_URL": self.gate.url, "ARPAGONA_TEAM_BANK": "arpagona-equipe",
                           "HINDSIGHT_API_KEY": "jeton-mael"})

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        self.gate.server.shutdown()
        self.gate.server.server_close()

    def test_ecriture_explicite_vers_la_banque_d_equipe(self):
        out = json.loads(self.eq.team_remember({"fait": "Dupont préfère 48 h", "source": "réunion du 24/11"}))
        self.assertEqual(out["zone"], "equipe")
        path, auth, body = self.gate.seen[-1]
        self.assertEqual(path, "/v1/default/banks/arpagona-equipe/memories")
        self.assertEqual(auth, "Bearer jeton-mael")
        self.assertEqual(body["items"][0]["metadata"]["source"], "réunion du 24/11")
        self.assertFalse(body["async"])

    def test_source_obligatoire_et_refus_du_portier_remonte(self):
        self.assertIn("error", json.loads(self.eq.team_remember({"fait": "x"})))
        self.assertEqual(self.gate.seen, [])
        out = json.loads(self.eq.team_remember({"fait": "le secret du client", "source": "s"}))
        self.assertIn("422", out["error"])

    def test_rappel_avec_auteur_et_source(self):
        out = json.loads(self.eq.team_recall({"requete": "Dupont"}))
        self.assertEqual(out["resultats"][0]["auteur"], "mael")
        self.assertEqual(out["resultats"][0]["source"], "réunion")

    def test_non_configure(self):
        os.environ.pop("ARPAGONA_TEAM_BANK")
        self.assertIn("error", json.loads(self.eq.team_recall({"requete": "x"})))


if __name__ == "__main__":
    unittest.main()
