"""Contrôles objectifs limités au registre expérimental et aux métadonnées Cargo."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect(root=ROOT):
    registry = json.loads((root / 'docs/modules.json').read_text(encoding='utf-8'))
    raw = subprocess.check_output(['cargo', 'metadata', '--format-version', '1', '--locked', '--offline', '--no-deps'], cwd=root, text=True)
    meta = json.loads(raw)
    packages = {p['name']: p for p in meta['packages'] if p['id'] in meta['workspace_members']}
    modules = registry['modules']
    errors = []
    def error(message):
        errors.append({'severity': 'erreur', 'file': 'docs/modules.json', 'line': 1, 'test': 'architecture', 'message': message})
    names = [m['name'] for m in modules]
    if len(names) != len(set(names)) or set(names) != set(packages):
        error(f'crates déclarées {sorted(names)} != workspace {sorted(packages)}')
    ids = [c['id'] for c in registry['contracts']]
    if len(ids) != len(set(ids)):
        error('identifiants de contrat dupliqués')
    for m in modules:
        p = packages.get(m['name'])
        if p:
            realpath = Path(p['manifest_path']).resolve().parent.relative_to(root.resolve()).as_posix()
            deps = sorted(d['name'] for d in p['dependencies'] if d['name'] in packages)
            if m['path'] != realpath or sorted(m['dependencies']) != deps:
                error(f"{m['name']}: chemin/dépendances déclarés {m['path']} {m['dependencies']} != réels {realpath} {deps}")
        for cid in m['contracts']:
            if cid not in ids:
                error(f"contrat inconnu {cid}")
    for c in registry['contracts']:
        for field in ('source', 'test'):
            path = (root / c[field]).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                error(f"{c['id']}: {field} absent ou hors dépôt")
        source = (root / c['source']).resolve()
        if source.is_relative_to(root.resolve()) and source.is_file() and c['id'] not in source.read_text(encoding='utf-8'):
            error(f"{c['id']}: identifiant absent de {c['source']}")
        if c['status'] not in ('proposé', 'validé'):
            error(f"{c['id']}: statut inconnu")
    return registry, packages, errors


if __name__ == '__main__':
    _, _, findings = inspect()
    print(json.dumps(findings, ensure_ascii=False, indent=2))
    raise SystemExit(bool(findings))
