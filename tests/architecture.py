"""Fixtures isolées ; aucune modification du dépôt réel."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / 'repo'
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', 'target', 'site', '__pycache__'))
        def check():
            return subprocess.run(['python3', 'scripts/architecture.py'], cwd=copy, capture_output=True, text=True)
        assert check().returncode == 0
        path = copy / 'docs/modules.json'
        original = path.read_text()
        data = json.loads(original)
        data['modules'][1]['dependencies'] = []
        path.write_text(json.dumps(data))
        bad = check()
        assert bad.returncode != 0 and 'dépendances' in bad.stdout
        path.write_text(original)
        assert check().returncode == 0
        data = json.loads(original)
        data['contracts'][0]['id'] = 'ABSENT-999'
        path.write_text(json.dumps(data))
        assert check().returncode != 0
        path.write_text(original)
        # Le contenu hostile reste une donnée échappée dans la page générée.
        data = json.loads(original)
        data['modules'][0]['responsibility'] = '<script>window.pwned=true</script>'
        path.write_text(json.dumps(data))
        subprocess.run(['python3', 'scripts/build_docs.py'], cwd=copy, check=True)
        page = (copy / 'site/index.html').read_text()
        assert '&lt;script&gt;window.pwned=true&lt;/script&gt;' in page
        assert '<script>window.pwned=true</script>' not in page
    print('architecture : sain, divergence A→B, correction, ID absent, entrée hostile : OK')


if __name__ == '__main__':
    run()
