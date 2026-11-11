#!/usr/bin/env python3
"""Vérificateur déterministe du banc de régression (contrat C-10, anneau 0).

Hors ligne, sans modèle. Évalue un livrable Markdown contre les attendus scellés
d'un cas (`bench/cas/<ID>/attendus.json`). Les motifs sont des expressions
régulières heuristiques : un contrôle `present` satisfait ne prouve pas la
qualité ; un contrôle `absent` violé prouve un défaut.

Usage :
  python3 bench/verifier.py                      # tous les cas, tous les historiques (+ oracle si présent)
  python3 bench/verifier.py --cas Q-01-calcul-derive --livrable chemin/synthese.md
  python3 bench/verifier.py --json

Codes de sortie : 0 = aucun FAIL ; 1 = au moins un FAIL ; 2 = erreur d'usage ou de banc.
Les livrables de `historique/` sont attendus en FAIL (ce sont des défauts observés) :
ils sont rapportés mais n'affectent pas le code de sortie, sauf avec --strict-historique.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
CAS_DIR = BENCH_DIR / "cas"
SEVERITES = {"bloquant", "avertissement"}
TYPES = {"present", "absent"}


class BancError(Exception):
    pass


def charger_attendus(cas: Path) -> dict:
    fichier = cas / "attendus.json"
    if not fichier.is_file():
        raise BancError(f"{cas.name}: attendus.json manquant")
    try:
        data = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BancError(f"{cas.name}: attendus.json illisible ({exc})") from exc
    for c in data.get("controles", []):
        if c.get("severite") not in SEVERITES or c.get("type") not in TYPES:
            raise BancError(f"{cas.name}: contrôle {c.get('id')} mal formé")
        if not c.get("motifs"):
            raise BancError(f"{cas.name}: contrôle {c.get('id')} sans motif")
        for m in c["motifs"]:
            try:
                re.compile(m, re.IGNORECASE)
            except re.error as exc:
                raise BancError(f"{cas.name}: regex invalide dans {c.get('id')}: {exc}") from exc
    return data


def sha256_dossier(cas: Path, data: dict) -> str | None:
    """Empreinte du dossier d'entrée : `dossier/` local ou `dossier.ref` (chemin relatif au dépôt)."""
    racine = cas / "dossier"
    if not racine.is_dir():
        ref = cas / "dossier.ref"
        if not ref.is_file():
            return None
        racine = (BENCH_DIR.parent / ref.read_text(encoding="utf-8").strip()).resolve()
        if not racine.is_dir():
            raise BancError(f"{cas.name}: dossier.ref pointe vers un répertoire absent")
    h = hashlib.sha256()
    for f in sorted(p for p in racine.rglob("*") if p.is_file()):
        h.update(f.relative_to(racine).as_posix().encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def evaluer(texte: str, data: dict) -> dict:
    resultats = []
    for c in data["controles"]:
        mode = c.get("mode", "any")
        trouves = [bool(re.search(m, texte, re.IGNORECASE)) for m in c["motifs"]]
        present = all(trouves) if mode == "all" else any(trouves)
        ok = present if c["type"] == "present" else not present
        resultats.append({
            "id": c["id"],
            "severite": c["severite"],
            "type": c["type"],
            "description": c.get("description", ""),
            "ok": ok,
        })
    bloquants = [r for r in resultats if not r["ok"] and r["severite"] == "bloquant"]
    avert = [r for r in resultats if not r["ok"] and r["severite"] == "avertissement"]
    verdict = "FAIL" if bloquants else ("WARN" if avert else "PASS")
    return {"verdict": verdict, "controles": resultats,
            "echecs_bloquants": [r["id"] for r in bloquants],
            "avertissements": [r["id"] for r in avert]}


def evaluer_fichier(cas: Path, livrable: Path, data: dict) -> dict:
    try:
        texte = livrable.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BancError(f"{cas.name}: livrable illisible {livrable} ({exc})") from exc
    res = evaluer(texte, data)
    res.update({"cas": cas.name, "livrable": str(livrable),
                "sha256_livrable": hashlib.sha256(texte.encode("utf-8")).hexdigest()})
    return res


def lister_cas(filtre: str | None) -> list[Path]:
    if not CAS_DIR.is_dir():
        raise BancError("bench/cas absent")
    cas = sorted(p for p in CAS_DIR.iterdir() if p.is_dir())
    if filtre:
        cas = [p for p in cas if p.name == filtre]
        if not cas:
            raise BancError(f"cas introuvable : {filtre}")
    return cas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cas", help="identifiant du cas (nom du répertoire)")
    ap.add_argument("--livrable", help="livrable à évaluer (exige --cas)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    ap.add_argument("--strict-historique", action="store_true",
                    help="les FAIL des historiques comptent dans le code de sortie")
    args = ap.parse_args(argv)
    if args.livrable and not args.cas:
        ap.error("--livrable exige --cas")

    rapport = {"cas": [], "resultats": []}
    try:
        for cas in lister_cas(args.cas):
            data = charger_attendus(cas)
            empreinte = sha256_dossier(cas, data)
            attendu = data.get("sha256_dossier")
            rapport["cas"].append({
                "id": cas.name, "sha256_dossier": empreinte,
                "dossier_conforme": (attendu == empreinte) if attendu else None,
                "scelle_le": data.get("scelle_le"), "scelle_par": data.get("scelle_par"),
            })
            if attendu and attendu != empreinte:
                raise BancError(f"{cas.name}: dossier modifié depuis le scellement "
                                f"(attendu {attendu[:12]}…, observé {str(empreinte)[:12]}…)")
            if args.livrable:
                r = evaluer_fichier(cas, Path(args.livrable), data)
                r["role"] = "candidat"
                rapport["resultats"].append(r)
                continue
            for h in sorted((cas / "historique").glob("*.md")) if (cas / "historique").is_dir() else []:
                r = evaluer_fichier(cas, h, data)
                r["role"] = "historique"
                rapport["resultats"].append(r)
            oracle = cas / "oracle.md"
            if oracle.is_file():
                r = evaluer_fichier(cas, oracle, data)
                r["role"] = "oracle"
                rapport["resultats"].append(r)
    except BancError as exc:
        print(f"ERREUR BANC : {exc}", file=sys.stderr)
        return 2

    code = 0
    for r in rapport["resultats"]:
        if r["verdict"] == "FAIL" and (r["role"] != "historique" or args.strict_historique):
            code = 1
        if r["role"] == "oracle" and r["verdict"] != "PASS":
            code = 1  # un oracle qui ne passe pas = banc incohérent

    if args.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
    else:
        for c in rapport["cas"]:
            conf = {True: "conforme", False: "MODIFIÉ", None: "non scellé"}[c["dossier_conforme"]]
            print(f"[cas] {c['id']}  dossier {conf}  scellé {c['scelle_le']} par {c['scelle_par']}")
        for r in rapport["resultats"]:
            print(f"[{r['role']:<10}] {r['cas']}  {r['verdict']:<4}  {Path(r['livrable']).name}")
            for ctl in r["controles"]:
                if not ctl["ok"]:
                    print(f"    - {ctl['id']} ({ctl['severite']}, {ctl['type']}) : {ctl['description']}")
        print(f"code de sortie : {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
