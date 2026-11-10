#!/usr/bin/env python3
"""Garde-fous bornés, pas un scanner de secrets ni un audit CVE complet."""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

lock = tomllib.loads(Path("Cargo.lock").read_text())
external = [p["name"] for p in lock.get("package", []) if "source" in p]
if external:
    sys.exit("Dépendances externes non examinées: " + ", ".join(external))
files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
# Exemples de signatures connues uniquement ; ne pas imprimer les valeurs détectées.
patterns = [re.compile(rb"gh[pousr]_" + rb"[A-Za-z0-9]{36,}"), re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
for name in filter(None, files):
    path = Path(name)
    if path.is_file() and any(pattern.search(path.read_bytes()) for pattern in patterns):
        sys.exit("Motif sensible détecté dans " + name)
print("Aucune dépendance externe et aucun des motifs sensibles ciblés détectés (couverture limitée).")
