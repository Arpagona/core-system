"""Rapport déterministe local, sans LLM ; les fichiers examinés sont des données."""
import argparse
import json
import subprocess
from architecture import ROOT, inspect


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def report(base, ci):
    sha = git('rev-parse', 'HEAD')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=ROOT).returncode:
        raise RuntimeError('Arbre suivi modifié : impossible de lier le contrôle au SHA HEAD.')
    # Argument Git validé comme objet commit, jamais interpolé dans un shell.
    base = git('rev-parse', '--verify', base + '^{commit}')
    paths = subprocess.check_output(['git', 'diff', '--name-only', '-z', base, sha, '--'], cwd=ROOT).decode().split('\0')
    paths = [p for p in paths if p]
    registry, _, findings = inspect()
    signals = []
    for path in paths:
        if path.startswith(('.github/', 'scripts/')) or path in ('AGENTS.md', 'CONTRIBUTING.md', 'docs/INTERFACES.md') or path.endswith(('Cargo.toml', '.rs')):
            signals.append({'file': path, 'line': 1, 'severity': 'attention', 'test': 'diff chemins', 'message': 'Interface, API potentielle, règles, CI ou permissions : revue élargie à trois.'})
    if ci == 'failure':
        findings.append({'file': 'CI', 'line': 0, 'severity': 'erreur', 'test': 'état CI fourni', 'message': 'CI en échec ; aucun accord.'})
    elif ci == 'unknown':
        signals.append({'file': 'CI', 'line': 0, 'severity': 'attention', 'test': 'état CI fourni', 'message': 'CI inconnue ; aucun accord.'})
    affected = [m['name'] for m in registry['modules'] if any(p.startswith(m['path'] + '/') for p in paths)]
    return {'sha': sha, 'base': base, 'synthese': 'Contrôle déterministe borné ; ne constitue pas une revue sémantique indépendante.', 'modules': affected, 'exigences': ['OBJ-04', 'OBJ-05', 'GU-02', 'GU-03'], 'anomalies': findings, 'signaux': signals, 'recommandations': ['Revue humaine et accord des trois selon le type de changement.', 'Consulter les résultats CI exacts séparément.'], 'limites': ['Aucune analyse sémantique, aucun LLM, aucune garantie de détection exhaustive des API.', 'CI fournie par appelant, non vérifiée par Guardian ; exécuter les tests séparément.', 'Une PR peut modifier ce contrôle ; absence de protection serveur.'], 'verdict': 'à corriger' if findings else ('réserves' if signals else 'accord')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--ci', choices=['success', 'failure', 'unknown'], default='unknown')
    args = parser.parse_args()
    result = report(args.base, args.ci)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['anomalies'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
