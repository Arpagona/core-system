#!/usr/bin/env python3
"""Offline sandbox: rewrite fixed OS paths; never invokes the host installer."""
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/install.sh"

class InstallSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.put(self.bin / "id", "#!/bin/sh\necho 0\n", 0o755)
        self.put(self.bin / "install", "#!/usr/bin/python3\nimport os,sys\na=sys.argv[1:]; b=[]\nwhile a:\n x=a.pop(0)\n if x in ('-o','-g'): a.pop(0)\n else: b.append(x)\nos.execv('/usr/bin/install',['install']+b)\n", 0o755)
        text = SCRIPT.read_text()
        for p in ("/var/backups/agentcore", "/etc/agentcore", "/var/lib/agentcore", "/opt/agentcore", "/usr/local/bin/agentcore"):
            text = text.replace(p, str(self.root) + p)
        self.put(self.bundle / "install.sh", text, 0o755)
        self.put(self.bundle / "VERSION", "version=2\n")
        self.put(self.bundle / "agentcore", "#!/bin/sh\necho synthetic-version\n", 0o755)
        for name in ("rollback.sh", "recette.sh", "config.example.toml"):
            self.put(self.bundle / name, "synthetic\n")
        self.put(self.bundle / "demo/input", "synthetic\n")
        digest = hashlib.sha256((self.bundle / "agentcore").read_bytes()).hexdigest()
        self.put(self.bundle / "SHA256SUMS", digest + "  agentcore\n")
        (self.root / "usr/local/bin").mkdir(parents=True)

    def put(self, path, data, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        path.chmod(mode)

    def old(self):
        release = self.root / "opt/agentcore/releases/1"
        self.put(release / "agentcore", "#!/bin/sh\necho old\n", 0o755)
        self.put(release / "content", "old release\n")
        (self.root / "opt/agentcore/current").symlink_to(release)
        self.put(self.root / "etc/agentcore/api_key", "synthetic-key\n", 0o640)
        self.put(self.root / "var/lib/agentcore/state", "state\n")
        return release

    def run_install(self):
        env = dict(os.environ, PATH=str(self.bin) + ":/usr/bin:/bin", AGENTCORE_USER="nobody")
        return subprocess.run([str(self.bundle / "install.sh")], env=env, text=True, capture_output=True, umask=0o022)

    def backups(self):
        return self.root / "var/backups/agentcore"

    def test_existing_install_backup_and_permissions(self):
        old = self.old()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "opt/agentcore/current").resolve().name, "2")
        archive, = self.backups().glob("avant-*.tar.gz")
        prev, = self.backups().glob("previous-*")
        self.assertEqual(prev.read_text().strip(), str(old))
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(prev.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.backups().stat().st_mode & 0o777, 0o700)
        with tarfile.open(archive) as tar:
            names = tar.getnames()
            self.assertIn(str(old / "content").lstrip("/"), names)
            self.assertIn(str(self.root / "etc/agentcore/api_key").lstrip("/"), names)
            self.assertEqual(tar.extractfile(str(old / "content").lstrip("/")).read(), b"old release\n")

    def test_first_install(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(list(self.backups().glob("previous-*")))
        archive, = self.backups().glob("avant-*.tar.gz")
        with tarfile.open(archive) as tar: self.assertEqual(tar.getnames(), [])

    def test_tar_creation_and_verification_failure_do_not_switch(self):
        for failure in ("-czf", "-tzf", "-dzf"):
            with self.subTest(failure=failure):
                if not (self.root / "opt/agentcore/current").is_symlink(): self.old()
                self.put(self.bin / "tar", "#!/bin/sh\n[ \"$1\" != \"" + failure + "\" ] || exit 42\nexec /usr/bin/tar \"$@\"\n", 0o755)
                result = self.run_install()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.root / "opt/agentcore/current").resolve().name, "1")
                self.assertFalse((self.root / "opt/agentcore/releases/2").exists())

    def test_existing_release_never_overwritten(self):
        self.old()
        target = self.root / "opt/agentcore/releases/2"
        self.put(target / "marker", "keep")
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "marker").read_text(), "keep")
        self.assertEqual((self.root / "opt/agentcore/current").resolve().name, "1")

    def test_dangling_current_fails_closed(self):
        current = self.root / "opt/agentcore/current"
        current.parent.mkdir(parents=True)
        current.symlink_to("missing")
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(os.readlink(current), "missing")

if __name__ == "__main__": unittest.main(verbosity=2)
