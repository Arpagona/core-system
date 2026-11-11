#!/usr/bin/env python3
"""Tests du banc de régression C-10 (anneau 0).

Vérifie que :
1. le banc est cohérent (attendus valides, dossiers conformes aux empreintes scellées) ;
2. chaque livrable historique défectueux est bien détecté (FAIL sur les contrôles attendus) ;
3. chaque oracle passe ;
4. un dossier modifié après scellement est refusé (code 2) ;
5. un livrable candidat vide échoue.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
VERIFIER = RACINE / "bench" / "verifier.py"

ATTENDU_HISTORIQUE = {
    "Q-01-calcul-derive": {"fail": {"Q-01-a"}, "warn": {"Q-01-f"}},
    "Q-02-contradiction-non-prouvee": {"fail": {"Q-02-e"}, "warn": {"Q-02-f"}},
}


def run(*args: str, cwd: Path = RACINE) -> tuple[int, dict | None, str]:
    p = subprocess.run([sys.executable, str(VERIFIER), "--json", *args],
                       cwd=cwd, capture_output=True, text=True)
    data = json.loads(p.stdout) if p.stdout.strip().startswith("{") else None
    return p.returncode, data, p.stderr


def main() -> int:
    erreurs: list[str] = []

    code, data, err = run()
    if code != 0 or data is None:
        return _fin([f"exécution globale : code {code}, stderr={err.strip()}"])
    for c in data["cas"]:
        if c["dossier_conforme"] is not True:
            erreurs.append(f"{c['id']}: dossier non scellé ou modifié")

    vus = set()
    for r in data["resultats"]:
        cas = r["cas"]
        if r["role"] == "historique":
            vus.add(cas)
            att = ATTENDU_HISTORIQUE.get(cas)
            if att is None:
                erreurs.append(f"{cas}: historique sans attendu dans ce test")
                continue
            if r["verdict"] != "FAIL":
                erreurs.append(f"{cas}: historique devrait être FAIL, obtenu {r['verdict']}")
            if set(r["echecs_bloquants"]) != att["fail"]:
                erreurs.append(f"{cas}: échecs bloquants {r['echecs_bloquants']} ≠ {sorted(att['fail'])}")
            if set(r["avertissements"]) != att["warn"]:
                erreurs.append(f"{cas}: avertissements {r['avertissements']} ≠ {sorted(att['warn'])}")
        elif r["role"] == "oracle":
            if r["verdict"] != "PASS":
                erreurs.append(f"{cas}: oracle devrait être PASS, obtenu {r['verdict']} ({r['echecs_bloquants']}, {r['avertissements']})")
    manquants = set(ATTENDU_HISTORIQUE) - vus
    if manquants:
        erreurs.append(f"cas sans historique évalué : {sorted(manquants)}")

    # Dossier modifié après scellement → refus (code 2), sur une copie temporaire du dépôt.
    with tempfile.TemporaryDirectory() as tmp:
        copie = Path(tmp) / "repo"
        shutil.copytree(RACINE / "bench", copie / "bench")
        shutil.copytree(RACINE / "demo", copie / "demo")
        cible = copie / "bench" / "cas" / "Q-02-contradiction-non-prouvee" / "dossier" / "reunion.md"
        cible.write_text(cible.read_text(encoding="utf-8") + "\nligne ajoutée\n", encoding="utf-8")
        p = subprocess.run([sys.executable, str(copie / "bench" / "verifier.py")],
                           cwd=copie, capture_output=True, text=True)
        if p.returncode != 2 or "modifié depuis le scellement" not in p.stderr:
            erreurs.append(f"dossier altéré non refusé (code {p.returncode}, stderr={p.stderr.strip()[:120]})")

    # Candidat vide → FAIL (code 1).
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("")
        vide = f.name
    code, data, _ = run("--cas", "Q-01-calcul-derive", "--livrable", vide)
    if code != 1 or not data or data["resultats"][0]["verdict"] != "FAIL":
        erreurs.append(f"candidat vide : code {code}, attendu 1/FAIL")
    Path(vide).unlink(missing_ok=True)

    # Candidat = oracle → PASS (code 0).
    oracle = RACINE / "bench" / "cas" / "Q-02-contradiction-non-prouvee" / "oracle.md"
    code, data, _ = run("--cas", "Q-02-contradiction-non-prouvee", "--livrable", str(oracle))
    if code != 0 or not data or data["resultats"][0]["verdict"] != "PASS":
        erreurs.append(f"candidat oracle : code {code}, attendu 0/PASS")

    return _fin(erreurs)


def _fin(erreurs: list[str]) -> int:
    if erreurs:
        print("ÉCHEC tests banc :")
        for e in erreurs:
            print(" -", e)
        return 1
    print("tests banc : OK (historiques détectés, oracles PASS, scellement respecté, candidats vide/oracle)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
