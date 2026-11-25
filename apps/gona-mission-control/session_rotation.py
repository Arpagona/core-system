"""Rotation de session vue depuis Mission Control (même règle que le plugin Hermes session-lifecycle).

Mode Telegram : avant un envoi, si la session est restée inactive au-delà de la politique, Mission
Control tourne la session par le vrai /new du gateway (gateway_new.py) et l'inscrit dans
``<profil>/session-lifecycle/rotations.jsonl`` ; le plugin injecte la passation au premier tour.
Mode api (sans Telegram) : backend_api applique la même règle à ses propres conversations.

Politique : ``plugins.entries.session-lifecycle.settings`` du profil (si le plugin y est activé),
sinon variables MC_SESSION_IDLE_MINUTES (défaut 240, 0 = off) et MC_SESSION_DAILY_HOUR (défaut 4,
-1 = off). Aucun minuteur : la décision se prend au moment de l'envoi.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_IDLE, DEFAULT_HOUR = 240.0, 4
TRACE_DIR = 'session-lifecycle'
HANDOFF_MESSAGES, HANDOFF_PER_MESSAGE, HANDOFF_MAX_CHARS = 8, 600, 4000


def _norm(idle, hour):
    try:
        idle = max(0.0, float(idle))
    except (TypeError, ValueError):
        idle = 0.0
    try:
        hour = int(hour)
    except (TypeError, ValueError):
        hour = -1
    return {'idle_minutes': idle, 'daily_hour': hour if 0 <= hour <= 23 else -1}


def policy(profile_home=None):
    """Politique effective, ou None si la rotation est désactivée."""
    if profile_home is not None:
        try:
            import yaml
            cfg = yaml.safe_load((Path(profile_home) / 'config.yaml').read_text(encoding='utf-8')) or {}
            plugins = cfg.get('plugins') or {}
            if 'session-lifecycle' in (plugins.get('enabled') or []) and \
                    'session-lifecycle' not in (plugins.get('disabled') or []):
                s = ((plugins.get('entries') or {}).get('session-lifecycle') or {}).get('settings') or {}
                if not isinstance(s, dict) or not s:
                    return None
                p = _norm(s.get('idle_minutes', DEFAULT_IDLE), s.get('daily_hour', DEFAULT_HOUR))
                return p if p['idle_minutes'] or p['daily_hour'] >= 0 else None
            return None
        except Exception:
            return None
    p = _norm(os.environ.get('MC_SESSION_IDLE_MINUTES', DEFAULT_IDLE), os.environ.get('MC_SESSION_DAILY_HOUR', DEFAULT_HOUR))
    return p if p['idle_minutes'] or p['daily_hour'] >= 0 else None


def reason(p, last, now=None):
    """'idle' / 'daily' si *last* (datetime local) est au-delà de la frontière, sinon None."""
    if not p or last is None:
        return None
    now = now or datetime.now()
    if p['idle_minutes'] and now - last >= timedelta(minutes=p['idle_minutes']):
        return 'idle'
    if p['daily_hour'] >= 0:
        boundary = now.replace(hour=p['daily_hour'], minute=0, second=0, microsecond=0)
        if boundary > now:
            boundary -= timedelta(days=1)
        if last < boundary:
            return 'daily'
    return None


def last_user_activity(profile_home, session_id):
    """Dernier message utilisateur réel de la session Hermes (state.db en lecture seule)."""
    db = Path(profile_home) / 'state.db'
    if not db.is_file():
        return None
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as c:
        row = c.execute("select max(timestamp) from messages where session_id=? and role='user'"
                        " and (display_kind is null or display_kind in ('', 'steer'))"
                        " and trim(coalesce(content,''))!=''", (session_id,)).fetchone()
    return datetime.fromtimestamp(float(row[0])) if row and row[0] is not None else None


def record_rotation(profile_home, old_sid, new_sid, why, by='mission-control'):
    path = Path(profile_home) / TRACE_DIR / 'rotations.jsonl'
    path.parent.mkdir(mode=0o700, exist_ok=True)
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    lines = (lines + [json.dumps({'at': time.time(), 'old_session_id': old_sid, 'new_session_id': new_sid,
                                  'reason': why, 'by': by}, ensure_ascii=False)])[-500:]
    tmp = path.with_suffix('.tmp')
    tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def _clip(text, limit):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def handoff_text(rows, why, opened_ts=None):
    """Bloc de reprise déterministe depuis [(role, texte), ...] dans l'ordre chronologique."""
    picked = [('Utilisateur' if r == 'user' else 'Agent', _clip(t, HANDOFF_PER_MESSAGE))
              for r, t in rows if (t or '').strip()][-HANDOFF_MESSAGES:]
    if not picked:
        return None
    opened = ' (ouverte le %s)' % datetime.fromtimestamp(opened_ts).strftime('%d/%m %H:%M') if opened_ts else ''
    head = ('Reprise de conversation : la session précédente%s a été close %s et archivée. Derniers échanges, '
            'du plus ancien au plus récent, pour reprendre le fil sans le redemander à l\'utilisateur. '
            'Ne mentionne pas ce changement de session sauf si on te le demande.'
            % (opened, 'après inactivité' if why == 'idle' else 'à la frontière quotidienne'))
    lines = ['%s : %s' % x for x in picked]
    while lines and len(head) + sum(len(x) + 1 for x in lines) > HANDOFF_MAX_CHARS:
        lines.pop(0)
    return head + '\n' + '\n'.join(lines) if lines else None
