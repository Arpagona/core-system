#!/usr/bin/env python3
"""Garde-fous bornés, pas un scanner de secrets ni un audit CVE complet."""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

lock = tomllib.loads(Path("Cargo.lock").read_text())
# Liste PROPOSÉE en M0 (docs/contrats/M0-CONTRATS.md §11), non approuvée à trois.
# Toute entrée ajoutée ici est un changement de règle de contrôle.
REVIEWED = {"serde", "serde_core", "serde_derive", "serde_json", "proc-macro2", "quote", "syn",
            "unicode-ident", "itoa", "memchr", "ryu", "zmij"}
external = [p["name"] for p in lock.get("package", []) if "source" in p and p["name"] not in REVIEWED]
if external:
    sys.exit("Dépendances externes non examinées: " + ", ".join(sorted(set(external))))
files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
# Exemples de signatures connues uniquement ; ne pas imprimer les valeurs détectées.
patterns = [re.compile(rb"gh[pousr]_" + rb"[A-Za-z0-9]{36,}"), re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
for name in filter(None, files):
    path = Path(name)
    if path.is_file() and any(pattern.search(path.read_bytes()) for pattern in patterns):
        sys.exit("Motif sensible détecté dans " + name)
print("Dépendances externes limitées à la liste examinée et aucun des motifs sensibles ciblés détectés (couverture limitée).")
