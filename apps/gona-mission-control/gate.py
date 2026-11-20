"""Portail de décision (decision gate) : ce qui attend Thibaud, en Oui / Non.

Sources : cartes Kanban bloquées needs_input (question fermée dans refonte/loop/gate.json)
et questions ouvertes de ask.py. Effets bornés : commentaire + unblock ou complete via le CLI
natif, ou ask.py decide. Chaque réponse est journalisée dans decisions.jsonl. Idempotent.
"""
import fcntl
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

PROFILE = Path(os.environ.get('GONA_PROFILE', '/home/thibaud/.hermes/profiles/gpt5'))
LOOP = PROFILE / 'refonte/loop'
GATE = LOOP / 'gate.json'
DECISIONS = LOOP / 'decisions.jsonl'
KANBAN_DB = Path(os.environ.get('HERMES_KANBAN_DB', '/home/thibaud/.hermes/kanban.db'))
CLI = ['/home/thibaud/.local/bin/hermes', '-p', 'gpt5', 'kanban', '--board', 'default']


def _ask():
    spec = importlib.util.spec_from_file_location('gona_ask', PROFILE / 'scripts/ask.py')
    import sys
    sys.path.insert(0, str(PROFILE / 'scripts'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def _gate():
    try:
        return {k: v for k, v in json.loads(GATE.read_text()).items() if k.startswith('t_')}
    except FileNotFoundError:
        return {}


def _answered():
    done = {}
    if DECISIONS.exists():
        for line in DECISIONS.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('type') == 'kanban-gate':
                done[(r['card'], r['question'])] = r
    return done


def items():
    gate, answered = _gate(), _answered()
    out = []
    with closing(sqlite3.connect(KANBAN_DB.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("select id,title,tenant,created_at from tasks where status='blocked' and block_kind='needs_input' order by created_at").fetchall()
        for r in rows:
            g = gate.get(r['id'])
            last = c.execute("select body from task_comments where task_id=? order by id desc limit 1", (r['id'],)).fetchone()
            if g and (r['id'], g['question']) in answered:
                continue
            out.append({'kind': 'card', 'id': r['id'], 'title': r['title'], 'tenant': r['tenant'],
                        'question': g['question'] if g else None,
                        'oui': (g or {}).get('oui', {}).get('note'), 'non': (g or {}).get('non', {}).get('note'),
                        'context': re.sub(r'^\[cycle:[0-9a-f]+\]\s*|^BLOCKED:\s*', '', (last['body'] if last else ''))[:300]})
    try:
        for a in _ask().pending():
            out.append({'kind': 'ask', 'id': str(a['num']), 'title': a['file'], 'tenant': 'propositions',
                        'question': a['question'], 'oui': a.get('oui') or 'GONA crée l’action correspondante.',
                        'non': 'Proposition refusée et archivée.', 'context': ''})
    except Exception:
        pass
    return out


def _cli(*args):
    r = subprocess.run(CLI + list(args), capture_output=True, text=True, timeout=25)
    if r.returncode:
        raise RuntimeError('Kanban refusé : ' + (r.stderr or r.stdout)[-200:])


def decide(kind, ident, answer):
    if answer not in ('oui', 'non'):
        raise ValueError('Réponse invalide')
    if kind == 'ask':
        if not re.fullmatch(r'[1-9][0-9]{0,5}', ident):
            raise ValueError('Question invalide')
        return _ask().decide(ident, 'accept' if answer == 'oui' else 'refuse', source='mission-control')
    if kind != 'card' or not re.fullmatch(r't_[0-9a-f]{8}', ident):
        raise ValueError('Carte invalide')
    with open(LOOP / '.gate.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        g = _gate().get(ident)
        if not g:
            raise ValueError('Pas de question fermée pour cette carte : utilise « Préciser »')
        prev = _answered().get((ident, g['question']))
        if prev:
            return dict(prev, duplicate=True)
        with closing(sqlite3.connect(KANBAN_DB.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as c:
            row = c.execute('select status,block_kind,assignee from tasks where id=?', (ident,)).fetchone()
        if not row or row[0] != 'blocked' or row[1] != 'needs_input':
            raise ValueError('Carte plus en attente de décision')
        eff = g[answer]
        text = f"Décision Thibaud (Mission Control) : {answer.upper()} — {g['question']} → {eff['note']}"
        if eff['effect'] == 'close':
            _cli('comment', ident, '--author', 'thibaud', text)
            _cli('unblock', ident, '--reason', 'Décision prise : ' + answer)
            _cli('complete', ident, '--result', text[:400])
        else:
            _cli('unblock', ident, '--reason', text[:500])
        rec = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'type': 'kanban-gate', 'card': ident,
               'question': g['question'], 'answer': answer, 'effect': eff['effect'], 'note': eff['note'],
               'source': 'mission-control'}
        with DECISIONS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n'); f.flush(); os.fsync(f.fileno())
        return rec
