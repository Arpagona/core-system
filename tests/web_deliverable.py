"""Vérifie la lecture du livrable par l’API de Mission Control."""

from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from console import Console, MAX_DELIVERABLE

MISSION = "m-20261111-120000-a1b2c3"


class DeliverableTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / "missions" / MISSION / "workspace"
        self.workspace.mkdir(parents=True)
        self.document = self.workspace / "résultat.md"
        self.content = "## Synthèse\n<script>Texte littéral</script>"
        self.document.write_text(self.content)
        self.report = {"state": "completed", "verification": {
            "ok": True, "path": self.document.name, "bytes": self.document.stat().st_size,
        }}
        cli = patch.object(Console, "cli_json", return_value={"report": self.report})
        self.cli = cli.start()
        self.addCleanup(cli.stop)
        version = patch.object(Console, "version", return_value={"état": str(self.root)})
        version.start()
        self.addCleanup(version.stop)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Console)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}/api/missions/{MISSION}/deliverable"

    def assert_refused(self):
        with self.assertRaises(HTTPError) as denied:
            urlopen(self.url, timeout=3)
        with denied.exception as response:
            self.assertEqual(response.code, 409)
            self.assertNotIn("Texte littéral", response.read().decode())

    def test_verified_document_as_text(self):
        with urlopen(self.url, timeout=3) as response:
            self.assertEqual(response.headers.get_content_type(), "application/json")
            self.assertEqual(json.load(response), {"name": self.document.name, "text": self.content})
        self.cli.assert_called_once_with("mission", "log", MISSION, "--json")

    def test_incomplete_or_changed_document(self):
        self.report["state"] = "running"
        self.assert_refused()
        self.report["state"] = "completed"
        self.report["verification"]["ok"] = False
        self.assert_refused()
        self.report["verification"]["ok"] = True
        self.document.write_text("Contenu différent")
        self.assert_refused()
        self.report["verification"]["bytes"] = MAX_DELIVERABLE + 1
        self.assert_refused()

    def test_outside_paths_and_links(self):
        outside = self.root / "hors-perimetre.md"
        outside.write_text(self.content)
        self.report["verification"]["path"] = str(outside)
        self.assert_refused()
        self.report["verification"]["path"] = "../hors-perimetre.md"
        self.assert_refused()
        self.report["verification"]["path"] = self.document.name
        self.document.unlink()
        self.document.symlink_to(outside)
        self.assert_refused()
        self.document.unlink()
        os.link(outside, self.document)
        self.assert_refused()
        nested = self.workspace / "dossier"
        nested.symlink_to(self.root, target_is_directory=True)
        self.report["verification"]["path"] = f"{nested.name}/{outside.name}"
        self.assert_refused()


if __name__ == "__main__":
    unittest.main()
