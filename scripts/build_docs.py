"""Vue HTML autonome, sans dépendances, du Markdown de référence."""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]

def build():
    paths = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md"]
    paths += sorted((ROOT / "docs").rglob("*.md"))
    nav, sections = [], []
    for i, path in enumerate(paths):
        label = escape(str(path.relative_to(ROOT)))
        nav.append(f'<li><a href="#doc-{i}">{label}</a></li>')
        # Affichage fidèle du Markdown, pas un parseur riche ni une analyse du code.
        sections.append(f'<section id="doc-{i}"><h2>{label}</h2><pre>{escape(path.read_text(encoding="utf-8"))}</pre></section>')
    page = '<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Agent Core — atelier</title><style>body{max-width:1100px;margin:2rem auto;padding:1rem;font:17px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:1rem}section{border-top:1px solid #ccc}</style><h1>Agent Core — atelier ARPAGONA</h1><p>Vue générée des sources Markdown. Architecture proposée, non approuvée. Aucun déploiement public.</p><nav><ul>' + ''.join(nav) + '</ul></nav>' + ''.join(sections) + '</html>'
    out = ROOT / 'site' / 'index.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding='utf-8')
    print(f'{len(paths)} documents → {out}')
    return out

if __name__ == '__main__':
    build()
