"""Génération locale depuis sources versionnées et métadonnées Cargo."""
from html import escape
from pathlib import Path
from urllib.parse import quote
from architecture import ROOT, inspect


def build():
    registry, _, errors = inspect()
    if errors:
        raise ValueError(str(errors))
    paths = [ROOT / 'README.md', ROOT / 'AGENTS.md', ROOT / 'CONTRIBUTING.md']
    paths += sorted((ROOT / 'docs').rglob('*.md'))
    e = escape
    rows = []
    for m in registry['modules']:
        rows.append('<tr>' + ''.join(f'<td>{e(str(x))}</td>' for x in [m['name'], m['responsibility'], ', '.join(m['dependencies']) or '—', ', '.join(m['contracts'])]) + '</tr>')
    contracts = ''.join(f"<li>{e(c['id'])} — {e(c['status'])} — <a href='../{quote(c['source'])}'>{e(c['source'])}</a> — <a href='../{quote(c['test'])}'>test</a></li>" for c in registry['contracts'])
    sections = []
    for i, path in enumerate(paths):
        label = path.relative_to(ROOT).as_posix()
        sections.append(f'<section id="doc-{i}"><h2><a href="../{quote(label)}">{e(label)}</a></h2><pre>{e(path.read_text(encoding="utf-8"))}</pre></section>')
    page = '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Architecture ARPAGONA</title><style>body{max-width:1100px;margin:2rem auto;font:17px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{border:1px solid #aaa;padding:.4em}</style><h1>Architecture expérimentale</h1><p>Généré localement depuis registre et cargo metadata ; propositions non approuvées.</p><table><tr><th>Module</th><th>Responsabilité</th><th>Dépendances réelles contrôlées</th><th>Contrats</th></tr>' + ''.join(rows) + '</table><h2>Contrats</h2><ul>' + contracts + '</ul><h2>Sources et ADR</h2>' + ''.join(sections) + '</html>'
    out = ROOT / 'site/index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding='utf-8')
    print(f'{len(paths)} documents → {out}')
    return out


if __name__ == '__main__':
    build()
