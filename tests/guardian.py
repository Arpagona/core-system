"""Tests des verdicts Guardian dans une copie Git sans réseau."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / 'repo'
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns('.git', 'target', 'site', '__pycache__'))
        env = dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid', GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=repo, env=env, text=True).strip()
        git('init', '-q')
        git('add', '.')
        git('commit', '-qm', 'fixture saine')
        base = git('rev-parse', 'HEAD')
        def guardian(ci):
            p = subprocess.run(['python3', 'scripts/guardian.py', '--base', base, '--ci', ci], cwd=repo, text=True, capture_output=True)
            return p, json.loads(p.stdout)
        p, report = guardian('success')
        assert p.returncode == 0 and report['verdict'] == 'accord' and report['sha'] == base
        p, report = guardian('unknown')
        assert p.returncode == 0 and report['verdict'] == 'réserves'
        p, report = guardian('failure')
        assert p.returncode != 0 and report['verdict'] == 'à corriger'
        data = json.loads((repo / 'docs/modules.json').read_text())
        data['modules'][1]['dependencies'] = []
        (repo / 'docs/modules.json').write_text(json.dumps(data))
        git('add', 'docs/modules.json')
        git('commit', '-qm', 'fixture divergente')
        p, report = guardian('success')
        assert p.returncode != 0 and report['verdict'] == 'à corriger'
    print('Guardian : sain, CI inconnue/échec, divergence : OK')


if __name__ == '__main__':
    run()
