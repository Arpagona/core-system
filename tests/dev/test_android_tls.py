"""Contrats de transport de l'enveloppe Android ; pas une recette appareil."""
from pathlib import Path
import unittest
# XML de ressources suivi dans Git uniquement, jamais de fichier client ou réseau.
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/android'

class AndroidTLS(unittest.TestCase):
    def test_cleartext_disabled_and_local_ca_scoped(self):
        root = ET.parse(APP / 'res/xml/network_security_config.xml').getroot()
        base = root.find('base-config')
        assert base is not None
        self.assertEqual(base.get('cleartextTrafficPermitted'), 'false')
        configs = root.findall('domain-config')
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].get('cleartextTrafficPermitted'), 'false')
        self.assertEqual({d.text for d in configs[0].findall('domain')}, {'10.68.100.1', '192.168.68.240'})
        cert = configs[0].find('trust-anchors/certificates')
        assert cert is not None
        self.assertEqual(cert.get('src'), '@raw/arpagona_local_ca')

    def test_no_tls_bypass(self):
        src = (APP/'src/com/arpagona/missioncontrol/MainActivity.java').read_text()
        self.assertIn('HOTE = "https://10.68.100.1"', src)
        self.assertNotIn('onReceivedSslError', src)
        self.assertNotIn('handler.proceed', src)
        cert = (APP/'res/raw/arpagona_local_ca.crt').read_text()
        self.assertIn('BEGIN CERTIFICATE', cert)
        self.assertNotIn('PRIVATE KEY', cert)

    def test_upgrade_same_package_and_explicit_version(self):
        root = ET.parse(APP/'AndroidManifest.xml').getroot()
        self.assertEqual(root.get('package'), 'com.arpagona.missioncontrol')
        self.assertEqual(root.get('{http://schemas.android.com/apk/res/android}versionCode'), '11')

if __name__ == '__main__':
    unittest.main()
