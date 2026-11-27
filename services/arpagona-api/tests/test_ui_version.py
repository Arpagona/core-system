"""Empreinte d'interface : détecte un déploiement pour les clients déjà ouverts."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arpagona_api.server import UI_FILES, ui_version  # noqa: E402


class UiVersionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.dir = Path(self.directory.name)
        for name in UI_FILES:
            (self.dir / name).write_text(f"contenu initial {name}\n", encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_empreinte_stable_sans_modification(self):
        first = ui_version(self.dir)
        self.assertEqual(first, ui_version(self.dir))
        self.assertRegex(first, r"^[0-9a-f]{12}$")

    def test_empreinte_change_des_qu_une_interface_est_modifiee(self):
        first = ui_version(self.dir)
        for name in UI_FILES:
            (self.dir / name).write_text(f"contenu livré {name}\n", encoding="utf-8")
            changed = ui_version(self.dir)
            self.assertNotEqual(first, changed, name)
            first = changed

    def test_fichier_absent_ne_bloque_pas_le_calcul(self):
        (self.dir / "kanban-view.js").unlink()
        self.assertRegex(ui_version(self.dir), r"^[0-9a-f]{12}$")

    def test_repertoire_absent_ne_leve_pas(self):
        self.assertRegex(ui_version(self.dir / "inexistant"), r"^[0-9a-f]{12}$")
