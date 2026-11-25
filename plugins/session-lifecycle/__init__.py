"""session-lifecycle — sessions propres, invisibles pour l'utilisateur (plugin Hermes).

Deux gestes, tous deux paresseux (aucun minuteur, aucune écriture de fond) :

1. **Rotation** (``pre_gateway_dispatch``) : au premier message entrant après
   ``idle_minutes`` sans activité de l'utilisateur, ou après la frontière
   quotidienne ``daily_hour`` (heure locale de la machine), la conversation est
   tournée par le chemin natif du ``/new`` du gateway. Jamais pendant un tour
   en cours, jamais sur une commande « / ».
2. **Passation** (``pre_llm_call``) : au premier tour d'une session ouverte par
   cette rotation, le plugin injecte un bloc de reprise déterministe (les
   derniers échanges de la session précédente). Un ``/new`` manuel n'en reçoit
   pas : l'utilisateur a demandé un fil neuf.

Horloge d'activité : le dernier message *utilisateur* réel de la session dans
``state.db`` (Telegram ET Mission Control écrivent dans la même session), pas
``updated_at`` (avancé par les tours internes) ni une horloge propre au hook
(qui ne verrait pas les envois de Mission Control).

La mémoire n'est pas gérée ici : Hindsight retient à chaque tour
(``auto_retain``) et le chemin natif de ``/new`` clôt la session pour les
fournisseurs de mémoire.

Traces (sans contenu de message) dans ``<profil>/session-lifecycle/`` :
``rotations.jsonl`` (une ligne par rotation, aussi écrite par Mission Control
quand il tourne lui-même avant un envoi) et ``handoffs.jsonl``.

Réglages : ``plugins.entries.session-lifecycle.settings`` du profil ::

    idle_minutes: 240   # 0 = pas de rotation sur inactivité
    daily_hour: 4       # -1 = pas de frontière quotidienne
    handoff: true

Le cœur de la rotation (résolution de clé, entonnoir ``/new``, repli dégradé,
garde « tour en cours », commandes ignorées) reprend le plugin MIT
``hermes-session-reset-policy`` de Samuel Proulx (fastfinge, v0.3.0,
0f2ea5ad) ; voir LICENSE-session-reset-policy.
"""
from __future__ import annotations

import contextlib
import dataclasses
import inspect
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("hermes.plugins.session_lifecycle")

__version__ = "0.1.0"

DEFAULTS = {"idle_minutes": 240, "daily_hour": 4, "handoff": True}
HANDOFF_MESSAGES = 8
HANDOFF_PER_MESSAGE = 600
HANDOFF_MAX_CHARS = 4000
AUTO_REASONS = ("idle", "daily")
USER_KINDS = (None, "", "steer")  # tours réels de l'utilisateur (pas internal_notification, model_switch…)
TRACE_DIR = "session-lifecycle"
TRACE_MAX_LINES = 500


# --- réglages ----------------------------------------------------------------

def normalize_settings(raw: Any) -> dict:
    s = dict(DEFAULTS)
    if isinstance(raw, dict):
        s.update({k: raw[k] for k in DEFAULTS if k in raw})
    try:
        s["idle_minutes"] = max(0.0, float(s["idle_minutes"]))
    except (TypeError, ValueError):
        s["idle_minutes"] = 0.0
    try:
        s["daily_hour"] = int(s["daily_hour"])
    except (TypeError, ValueError):
        s["daily_hour"] = -1
    if not 0 <= s["daily_hour"] <= 23:
        s["daily_hour"] = -1
    s["handoff"] = bool(s["handoff"])
    return s


def rotation_reason(settings: dict, last: Optional[datetime], now: datetime) -> Optional[str]:
    """'idle' / 'daily' si la dernière activité est au-delà de la frontière, sinon None."""
    if last is None:
        return None
    idle = settings.get("idle_minutes") or 0
    if idle > 0 and now - last >= timedelta(minutes=idle):
        return "idle"
    hour = settings.get("daily_hour", -1)
    if isinstance(hour, int) and 0 <= hour <= 23:
        boundary = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if boundary > now:
            boundary -= timedelta(days=1)
        if last < boundary:
            return "daily"
    return None


# --- state.db (lecture seule) --------------------------------------------------

def _ro(home: Path) -> Optional[sqlite3.Connection]:
    db = Path(home) / "state.db"
    if not db.is_file():
        return None
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def last_user_activity(home: Path, session_id: Optional[str]) -> Optional[datetime]:
    """Horodatage local du dernier message utilisateur réel de la session (None si aucun)."""
    conn = _ro(home)
    if conn is None or not session_id:
        return None
    try:
        row = conn.execute(
            "SELECT MAX(timestamp) AS t FROM messages WHERE session_id = ? AND role = 'user'"
            " AND (display_kind IS NULL OR display_kind IN ('', 'steer'))"
            " AND TRIM(COALESCE(content, '')) != ''",
            (session_id,)).fetchone()
        return datetime.fromtimestamp(float(row["t"])) if row and row["t"] is not None else None
    finally:
        conn.close()


def parent_of(home: Path, session_id: str) -> Optional[str]:
    conn = _ro(home)
    if conn is None or not session_id:
        return None
    try:
        row = conn.execute("SELECT parent_session_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row["parent_session_id"] if row else None
    finally:
        conn.close()


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_handoff(home: Path, parent_id: str, reason: str) -> Optional[str]:
    """Bloc de reprise déterministe, sans appel LLM. None si rien d'utile."""
    conn = _ro(home)
    if conn is None:
        return None
    try:
        meta = conn.execute("SELECT started_at FROM sessions WHERE id = ?", (parent_id,)).fetchone()
        rows = conn.execute(
            "SELECT role, content, display_kind, finish_reason FROM messages WHERE session_id = ?"
            " AND role IN ('user', 'assistant') ORDER BY id DESC LIMIT 200", (parent_id,)).fetchall()
    finally:
        conn.close()
    picked = []
    for r in rows:
        content = (r["content"] or "").strip()
        if not content:
            continue
        if r["role"] == "user" and r["display_kind"] not in USER_KINDS:
            continue
        if r["role"] == "assistant" and (r["display_kind"] or r["finish_reason"] not in (None, "stop")):
            continue
        picked.append(("Utilisateur" if r["role"] == "user" else "Agent", _clip(content, HANDOFF_PER_MESSAGE)))
        if len(picked) >= HANDOFF_MESSAGES:
            break
    if not picked:
        return None
    picked.reverse()
    opened = ""
    if meta and meta["started_at"]:
        opened = " (ouverte le " + datetime.fromtimestamp(float(meta["started_at"])).strftime("%d/%m %H:%M") + ")"
    why = "après inactivité" if reason == "idle" else "à la frontière quotidienne"
    head = (f"Reprise de conversation : la session précédente{opened} a été close {why} et archivée. "
            "Derniers échanges, du plus ancien au plus récent, pour reprendre le fil sans le redemander "
            "à l'utilisateur. Ne mentionne pas ce changement de session sauf si on te le demande.")
    lines = [f"{who} : {txt}" for who, txt in picked]
    while lines and len(head) + sum(len(x) + 1 for x in lines) > HANDOFF_MAX_CHARS:
        lines.pop(0)
    return head + "\n" + "\n".join(lines) if lines else None


# --- traces ------------------------------------------------------------------

def _trace(home: Path, name: str, record: dict) -> None:
    path = Path(home) / TRACE_DIR / name
    with contextlib.suppress(Exception):
        path.parent.mkdir(mode=0o700, exist_ok=True)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        lines = (lines + [json.dumps(record, ensure_ascii=False)])[-TRACE_MAX_LINES:]
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, path)


def record_rotation(home: Path, old_sid: Optional[str], new_sid: Optional[str], reason: str, by: str) -> None:
    _trace(home, "rotations.jsonl", {"at": time.time(), "old_session_id": old_sid, "new_session_id": new_sid,
                                     "reason": reason, "by": by})


def rotation_for_parent(home: Path, parent_id: Optional[str], session_id: Optional[str] = None) -> Optional[dict]:
    """Rotation automatique qui a ouvert *session_id* depuis *parent_id* (None sinon : /new manuel,
    compression, sous-agent…). Le nouvel identifiant noté doit correspondre quand il est connu."""
    path = Path(home) / TRACE_DIR / "rotations.jsonl"
    if not parent_id or not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        with contextlib.suppress(ValueError):
            rec = json.loads(line)
            if rec.get("old_session_id") != parent_id or rec.get("reason") not in AUTO_REASONS:
                continue
            if session_id and rec.get("new_session_id") and rec["new_session_id"] != session_id:
                continue
            return rec
    return None


def _handoff_done(home: Path, session_id: str) -> bool:
    path = Path(home) / TRACE_DIR / "handoffs.jsonl"
    return path.exists() and f'"session_id": "{session_id}"' in path.read_text(encoding="utf-8")


# --- rotation (repris de hermes-session-reset-policy, MIT) ---------------------

def _is_slash_command(event: Any) -> bool:
    get_command = getattr(event, "get_command", None)
    if callable(get_command):
        with contextlib.suppress(Exception):
            return bool(get_command())
    text = getattr(event, "text", None)
    return isinstance(text, str) and text.lstrip().startswith("/")


def _resolve_session_key(gateway: Any, source: Any, from_payload: Optional[str]) -> Optional[str]:
    if from_payload:
        return str(from_payload)
    helper = getattr(gateway, "_session_key_for_source", None)
    if not callable(helper):
        return None  # pas de repli build_session_key : risque de clé d'un autre profil
    try:
        key = helper(source)
        return str(key) if key else None
    except Exception:
        return None


def _lookup_entry(session_store: Any, key: Optional[str]) -> Any:
    if not key:
        return None
    try:
        return session_store.lookup_by_session_key(key)
    except Exception:
        return None


class _CommandFreeEvent:
    __slots__ = ("source",)

    def __init__(self, source: Any) -> None:
        self.source = source

    def get_command_args(self) -> str:
        return ""


def _command_free_event(event: Any) -> Any:
    try:
        return dataclasses.replace(event, text="")
    except Exception:
        return _CommandFreeEvent(getattr(event, "source", None))


def _reset_via_store(source: Any, session_store: Any, key: str) -> Any:
    old_sid = getattr(_lookup_entry(session_store, key), "session_id", None)
    with contextlib.suppress(Exception):
        from tools.async_delegation import interrupt_for_session
        interrupt_for_session(session_key=key, reason="session_reset", parent_session_id=str(old_sid or ""))
    new_entry = session_store.reset_session(key)
    new_sid = getattr(new_entry, "session_id", None) if new_entry is not None else None
    with contextlib.suppress(Exception):
        from hermes_cli.lifecycle import invoke_hook
        platform = str(getattr(getattr(source, "platform", None), "value", "") or "")
        invoke_hook("on_session_finalize", session_id=old_sid, platform=platform, reason="new_session",
                    old_session_id=old_sid, new_session_id=new_sid)
        invoke_hook("on_session_reset", session_id=new_sid, platform=platform, reason="new_session",
                    old_session_id=old_sid, new_session_id=new_sid)
    return new_entry


async def _reset_session(gateway: Any, event: Any, source: Any, session_store: Any, key: str) -> Any:
    funnel = getattr(gateway, "_handle_reset_command", None)
    if callable(funnel):
        old_sid = getattr(_lookup_entry(session_store, key), "session_id", None)
        try:
            outcome = funnel(_command_free_event(event))
            if inspect.isawaitable(outcome):
                await outcome
            return _lookup_entry(session_store, key)
        except Exception:
            new_entry = _lookup_entry(session_store, key)
            if new_entry is not None and getattr(new_entry, "session_id", None) != old_sid:
                logger.warning("session-lifecycle: entonnoir /new en échec après rotation de %s", key, exc_info=True)
                return new_entry
            logger.warning("session-lifecycle: entonnoir /new en échec pour %s ; rotation dégradée", key, exc_info=True)
    return _reset_via_store(source, session_store, key)


_SETTINGS_CACHE: dict = {}
_DISPATCH_SEEN: set = set()


def profile_settings(home: Path) -> Optional[dict]:
    """Réglages du plugin pour le profil *home*, ou None s'il n'y est pas activé.

    Lu directement dans ``<home>/config.yaml`` (cache par date de modification) : sous un gateway
    multiplexé, ``pre_gateway_dispatch`` s'exécute avant la portée du profil, donc le plugin
    chargé à la racine agit pour le profil du message seulement si CE profil l'active.
    """
    path = Path(home) / "config.yaml"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    cached = _SETTINGS_CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    result = None
    try:
        import yaml
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        plugins = config.get("plugins") or {}
        enabled = plugins.get("enabled") or []
        disabled = plugins.get("disabled") or []
        if "session-lifecycle" in enabled and "session-lifecycle" not in disabled:
            entry = (plugins.get("entries") or {}).get("session-lifecycle") or {}
            if isinstance(entry.get("settings"), dict) and entry["settings"]:
                # Réglages explicites exigés : le plugin chargé à la racine pour le crochet de
                # dispatch ne doit pas tourner les sessions d'un profil qui ne l'a pas demandé.
                result = normalize_settings(entry["settings"])
    except Exception:
        logger.debug("session-lifecycle: lecture de %s impossible", path, exc_info=True)
    _SETTINGS_CACHE[str(path)] = (mtime, result)
    return result


def _target_home(gateway: Any, source: Any) -> Optional[Path]:
    """Répertoire du profil qui sert ce message (gateway multiplexé ou non)."""
    resolver = getattr(gateway, "_resolve_profile_home_for_source", None)
    if callable(resolver):
        with contextlib.suppress(Exception):
            return Path(resolver(source))
    with contextlib.suppress(Exception):
        from hermes_cli.profiles import get_profile_dir
        return Path(get_profile_dir(getattr(source, "profile", None) or "default"))
    return None


def make_hooks(home: Path, settings_for=profile_settings, clock=datetime.now):
    """Crochets du plugin. *home* = profil qui a chargé le plugin (passation) ;
    la rotation, elle, agit pour le profil du message (résolu par le gateway)."""
    home = Path(home)

    async def maybe_rotate(event: Any = None, gateway: Any = None, session_store: Any = None,
                           session_key: Optional[str] = None, **_extra: Any) -> None:
        if session_store is None or event is None:
            return None
        source = getattr(event, "source", None)
        if source is None or _is_slash_command(event):
            return None
        target = _target_home(gateway, source)
        settings = settings_for(target) if target is not None else None
        if not settings:
            return None
        if str(target) not in _DISPATCH_SEEN:  # preuve, une fois par profil et par processus
            _DISPATCH_SEEN.add(str(target))
            logger.info("session-lifecycle: crochet de dispatch actif pour %s (chargé par %s)", target, home)
        key = _resolve_session_key(gateway, source, session_key)
        entry = _lookup_entry(session_store, key)
        if key is None or entry is None:
            return None
        old_sid = str(getattr(entry, "session_id", "") or "")
        try:
            last = last_user_activity(target, old_sid)
        except Exception:
            logger.debug("session-lifecycle: lecture d'activité impossible", exc_info=True)
            return None
        reason = rotation_reason(settings, last, clock())
        if reason is None:
            return None
        if getattr(entry, "active_turn_token", None):
            logger.info("session-lifecycle: frontière %s atteinte pour %s mais tour en cours ; report", reason, key)
            return None
        try:
            scope = getattr(gateway, "_async_profile_scope_for_source", None)
            if callable(scope):
                async with scope(source):
                    new_entry = await _reset_session(gateway, event, source, session_store, key)
            else:
                new_entry = await _reset_session(gateway, event, source, session_store, key)
        except Exception:
            logger.warning("session-lifecycle: rotation de %s impossible ; session conservée", key, exc_info=True)
            return None
        new_sid = getattr(new_entry, "session_id", None) if new_entry is not None else None
        if new_sid and new_sid != old_sid:
            record_rotation(target, old_sid, new_sid, reason, "gateway")
            logger.info("session-lifecycle: rotation %s (%s) %s -> %s", key, reason, old_sid, new_sid)
        return None

    def inject_handoff(session_id: str = "", is_first_turn: bool = False,
                       conversation_history: Optional[list] = None, **_extra: Any):
        settings = settings_for(home)
        if not settings or not settings.get("handoff") or not session_id:
            return None
        if not is_first_turn and conversation_history:
            return None
        try:
            parent = parent_of(home, session_id)
            rotation = rotation_for_parent(home, parent, session_id) if parent else None
            if not parent or not rotation or _handoff_done(home, session_id):
                return None
            text = build_handoff(home, parent, rotation["reason"])
        except Exception:
            logger.debug("session-lifecycle: passation impossible", exc_info=True)
            return None
        if not text:
            return None
        _trace(home, "handoffs.jsonl", {"at": time.time(), "session_id": session_id, "parent": parent,
                                        "reason": rotation["reason"], "chars": len(text)})
        return {"context": text}

    return maybe_rotate, inject_handoff


def register(ctx: Any) -> None:
    home = Path(getattr(ctx._manager, "home_path", None) or os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    rotate, handoff = make_hooks(home)
    ctx.register_hook("pre_gateway_dispatch", rotate)
    ctx.register_hook("pre_llm_call", handoff)
    logger.info("session-lifecycle v%s chargé (%s) ; réglages lus par profil", __version__, home)


__all__ = ["register", "__version__", "normalize_settings", "profile_settings", "rotation_reason", "build_handoff",
           "record_rotation", "rotation_for_parent", "last_user_activity", "make_hooks"]
