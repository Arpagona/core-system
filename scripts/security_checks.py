#!/usr/bin/env python3
"""Garde-fous bornés, pas un scanner de secrets ni un audit CVE complet."""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

lock = tomllib.loads(Path("Cargo.lock").read_text())
# Liste PROPOSÉE en M0 (docs/contrats/M0-CONTRATS.md §11) + client HTTPS ureq/rustls (spike v0.1).
# Non approuvée à trois. windows-* : dépendances de plateforme verrouillées, non compilées sous Linux.
# Toute entrée ajoutée ici est un changement de règle de contrôle.
REVIEWED = {
    "base64",
    "bytes",
    "cc",
    "cfg-if",
    "find-msvc-tools",
    "getrandom",
    "http",
    "httparse",
    "itoa",
    "libc",
    "log",
    "memchr",
    "once_cell",
    "percent-encoding",
    "proc-macro2",
    "quote",
    "ring",
    "rustls",
    "rustls-pki-types",
    "rustls-webpki",
    "serde",
    "serde_core",
    "serde_derive",
    "serde_json",
    "shlex",
    "subtle",
    "syn",
    "unicode-ident",
    "untrusted",
    "ureq",
    "ureq-proto",
    "utf8-zero",
    "wasi",
    "webpki-roots",
    "windows-sys",
    "windows-targets",
    "windows_aarch64_gnullvm",
    "windows_aarch64_msvc",
    "windows_i686_gnu",
    "windows_i686_gnullvm",
    "windows_i686_msvc",
    "windows_x86_64_gnu",
    "windows_x86_64_gnullvm",
    "windows_x86_64_msvc",
    "zeroize",
    "zmij",
}
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
