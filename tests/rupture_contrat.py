#!/usr/bin/env python3
"""Rupture et correction en copie isolée ; aucun fichier source modifié."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="atelier-contrat-", dir=os.environ.get("TMPDIR")) as tmp:
    dest = Path(tmp)
    for name in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "experiments"):
        src = root / name
        if src.is_dir():
            shutil.copytree(src, dest / name)
        else:
            shutil.copy2(src, dest / name)
    contract = dest / "experiments/contrat/src/lib.rs"
    baseline = contract.read_text()
    assert "nombre: u32" in baseline
    contract.write_text(baseline.replace("nombre: u32", "nombre: &str"))
    env = dict(os.environ, CARGO_NET_OFFLINE="true")
    command = ["cargo", "test", "--workspace", "--locked"]
    broken = subprocess.run(command, cwd=dest, env=env, capture_output=True, text=True)
    print("RUPTURE exit:", broken.returncode)
    print(broken.stderr)
    assert broken.returncode != 0 and "E0308" in broken.stderr, "rupture non détectée comme incompatibilité de type"
    contract.write_text(baseline)
    fixed = subprocess.run(command, cwd=dest, env=env, capture_output=True, text=True)
    print("CORRECTION exit:", fixed.returncode)
    print(fixed.stdout, fixed.stderr)
    assert fixed.returncode == 0, "baseline corrigée en échec"
