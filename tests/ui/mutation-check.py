#!/usr/bin/env python3
"""Preuve de détection : on casse volontairement une règle protégée, la suite doit échouer.

Chaque mutation est appliquée à un seul fichier, la commande de test correspondante doit
sortir en erreur, puis le fichier est restauré à l'octet près (empreinte SHA-256 vérifiée).
Prérequis : Node 22+, Chrome CDP 9223 et la démo « adversarial » servie sur 18810 pour les
mutations d'interface. Script de preuve locale, non exécuté par la CI.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'apps/mission-control-web'
NODE_TEST = ['node', '--test', str(ROOT / 'tests/ui/kanban-view.test.cjs')]
BROWSER = ['node', str(ROOT / 'tests/ui/kanban-adversarial.cjs'), str(ROOT / '.local/kanban-mutation')]  # sortie à part : ne pollue pas les preuves

MUTATIONS = [
    ('recherche : un seul terme suffirait', 'kanban-view.js',
     'return words.every(word => text.includes(word));',
     'return words.some(word => text.includes(word));', NODE_TEST),
    ('recherche : accents et casse non ignorés', 'kanban-view.js',
     'const fold = value => String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLocaleLowerCase("fr").trim();',
     'const fold = value => String(value || "").trim();', NODE_TEST),
    ('archives réaffichées comme du travail actif', 'kanban-view.js',
     'if (card.status === "archived" || (!showDone && card.status === "done")) return false;',
     'if (!showDone && card.status === "done") return false;', NODE_TEST),
    ('filtre « mes cartes » inopérant', 'kanban-view.js',
     'if (scope === "mine" && card.assignee !== login) return false;',
     'if (scope === "mine" && false) return false;', NODE_TEST),
    ('priorité la plus haute reléguée en fin de liste', 'kanban-view.js',
     '(Number(b.priority)||0)-(Number(a.priority)||0)',
     '(Number(a.priority)||0)-(Number(b.priority)||0)', NODE_TEST),
    ('réponse tardive réécrit la carte ouverte', 'app.js',
     '    const result = await kanban("show?id=" + encodeURIComponent(id));\n    if (ticket !== cardOpenSequence) return;',
     '    const result = await kanban("show?id=" + encodeURIComponent(id));', BROWSER),
    ('session expirée laisse un tableau mort', 'app.js',
     '  if (res.status === 401) { sessionExpired(); throw new Error("Session expirée : reconnectez-vous."); }\n',
     '', BROWSER),
    ('état vide muet sur des cartes toutes terminées', 'app.js',
     '    else if (!restantes && !showDone) aide = "Toutes les cartes sont terminées. Cochez « Afficher les terminées » pour les revoir.";\n',
     '', BROWSER),
]


def run(command):
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)


def main():
    if not WEB.is_dir():
        raise SystemExit(f'interface introuvable : {WEB}')
    rapport = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    survivors, restore_failures, detail = [], [], []
    for label, name, old, new, command in MUTATIONS:
        path = WEB / name
        original = path.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        text = original.decode('utf-8')
        if text.count(old) != 1:
            raise SystemExit(f'mutation ambiguë ({label}) : {text.count(old)} occurrence(s)')
        backup = path.with_suffix(path.suffix + '.mutation-backup')
        shutil.copy2(path, backup)
        try:
            path.write_text(text.replace(old, new), encoding='utf-8')
            result = run(command)
            caught = result.returncode != 0
            if not caught and command is NODE_TEST:
                caught = '"fail": 0' not in result.stdout and 'fail 0' not in result.stdout
            print(('DÉTECTÉE  ' if caught else 'SURVIVANTE ') + label + f'  [{name}]')
            detail.append({'mutation': label, 'fichier': name, 'detectee': caught})
            if not caught:
                survivors.append(label)
        finally:
            path.write_bytes(original)
            backup.unlink(missing_ok=True)
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                restore_failures.append(name)
    for name in sorted(set(restore_failures)):
        print(f'ERREUR : {name} non restauré à l’identique', file=sys.stderr)
    print(f'\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} mutations détectées.')
    if rapport:
        rapport.write_text(json.dumps({'total': len(MUTATIONS), 'detectees': len(MUTATIONS) - len(survivors),
            'survivantes': survivors, 'restauration_incomplete': restore_failures, 'detail': detail},
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if survivors or restore_failures:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
