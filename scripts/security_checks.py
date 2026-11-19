#!/usr/bin/env python3
"""Garde-fous bornés, pas un scanner de secrets ni un audit CVE complet."""
import re
import subprocess
import sys
from pathlib import Path

files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
# Exemples de signatures connues uniquement ; ne pas imprimer les valeurs détectées.
patterns = [re.compile(rb"gh[pousr]_" + rb"[A-Za-z0-9]{36,}"), re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
for name in filter(None, files):
    path = Path(name)
    if path.is_file() and any(pattern.search(path.read_bytes()) for pattern in patterns):
        sys.exit("Motif sensible détecté dans " + name)
print("Aucun des motifs sensibles ciblés détectés (couverture limitée ; pas un audit de sécurité).")
