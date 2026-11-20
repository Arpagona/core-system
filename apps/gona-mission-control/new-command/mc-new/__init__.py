"""Prototype pinned to Hermes ae2a81ccc0. NOT certified for activation: see RAPPORT.md.

No core monkeypatch, no second agent, no storage mutation outside the native handler.
The RPC uses one-shot, session-bound local UID proofs, because Hermes does not give
plugin handlers the authenticated actor. Proofs exist only in process memory.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import threading
import time

SID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


def refused(reason, *, uncertain=False):
    return {"ok": False, "new_session_id": None, "error": reason, "uncertain": uncertain}


class LocalProofBroker:
    """Linux-only AF_UNIX, peercred checked even inside a 0700 directory.

    A single-use proof authorizes only one exact session id, expires in 30 seconds,
    is never logged or persisted, and cannot serve as a gateway authentication.
    """
    def __init__(self, home):
        self.directory = Path(home) / "mc-new-runtime"
        self.path = self.directory / "proof.sock"
        self.pending = {}
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        if not hasattr(socket, "SO_PEERCRED"):
            raise RuntimeError("Linux SO_PEERCRED required")
        home = Path(home)
        for path in (home,):
            info = path.lstat()
            if path.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise RuntimeError("unsafe plugin home")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        info = self.directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise RuntimeError("unsafe proof directory")
        # Never delete an existing socket: another loaded copy might own it.
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.server.bind(str(self.path))
            os.chmod(self.path, 0o600)
            self.inode = self.path.stat().st_ino
            self.server.listen(8)
            self.server.settimeout(0.2)
        except Exception:
            self.server.close()
            raise
        self.thread = threading.Thread(target=self._serve, name="mc-new-local-proof", daemon=True)
        self.thread.start()

    @staticmethod
    def same_uid(peer):
        _, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        return uid == os.getuid()

    def _serve(self):
        while not self.stopped.is_set():
            try:
                peer, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with peer:
                try:
                    peer.settimeout(1)
                    if not self.same_uid(peer):
                        continue
                    with peer.makefile("rb") as reader:
                        data = json.loads(reader.readline(1025))
                    sid = data.get("id") if isinstance(data, dict) else None
                    if not isinstance(sid, str) or not SID.fullmatch(sid):
                        continue
                    now = time.monotonic()
                    with self.lock:
                        self.pending = {k: v for k, v in self.pending.items() if v[1] > now}
                        if len(self.pending) >= 128:
                            continue
                        proof = secrets.token_urlsafe(32)
                        self.pending[proof] = (sid, now + 30)
                    peer.sendall(json.dumps({"proof": proof}).encode() + b"\n")
                except (OSError, ValueError, AttributeError):
                    continue

    def consume(self, proof, sid):
        if not isinstance(proof, str) or len(proof) > 128:
            return False
        with self.lock:
            value = self.pending.pop(proof, None)
        return bool(value and value[0] == sid and value[1] > time.monotonic())

    def close(self):
        self.stopped.set()
        self.server.close()
        self.thread.join(2)
        with self.lock:
            self.pending.clear()
        if self.path.exists() and self.path.stat().st_ino == self.inode:
            self.path.unlink()


def runtime_for_home(home):
    # Internal seam, deliberately explicit. Not part of the public plugin ABI.
    from gateway.run import _gateway_runner_ref
    runner = _gateway_runner_ref()
    loop = getattr(runner, "_gateway_loop", None)
    if not runner or not getattr(runner, "_running", False) or not loop or not loop.is_running():
        raise RuntimeError("gateway unavailable in this process (host isolation unsupported)")
    registry = getattr(runner, "session_authorities", None)
    authority = registry.for_home(home) if registry else getattr(runner, "session_authority", None)
    if authority is None or Path(authority.profile_id).resolve() != Path(home).resolve():
        raise RuntimeError("profile authority mismatch")
    return runner, loop, authority


def session_is_busy(runner, adapter, live, key):
    """Native busy definition for this session: a claimed turn or adapter-held input."""
    task = getattr(live, "task", None)
    running_check = getattr(runner, "_is_session_running", None)
    if callable(running_check):
        running = bool(running_check(key))
    else:
        running = key in getattr(runner, "_running_agents", {})
    return bool(
        (task is not None and not task.done())
        or running
        or key in getattr(adapter, "_active_sessions", {})
        or key in getattr(adapter, "_pending_messages", {})
        or key in getattr(adapter, "_text_debounce_store", lambda: {})()
    )


async def native_new(runner, authority, sid, home, target):
    """Run only on the owner's gateway loop and context. No resume of a stale id.

    Scope: an exact physical id on a private Telegram DM, explicitly pinned chat/user/thread.
    An idle reset calls the native handler; an occupied one goes through the adapter's own
    busy dispatcher (cancel/debounce/drain) and then the native busy /new path.
    """
    from gateway.config import Platform
    from gateway.platforms.event import MessageEvent
    from gateway.session import SessionSource
    from gateway.slash_access import policy_for_runner_source

    if Path(authority.profile_id).resolve() != Path(home).resolve() or getattr(authority, "retiring", False):
        return refused("profile_mismatch")
    owner = authority.logical_owner(sid)
    live = authority.sessions.get(owner)
    source = getattr(live, "source", None)
    if (not isinstance(source, SessionSource) or source.platform != Platform.TELEGRAM
            or source.chat_type != "dm" or source.detached_route or source.shared_session
            or source.delivered_via_upstream_relay or source.profile_route_rejected):
        return refused("not_live_private_telegram")
    expected = (target.get("chat_id"), target.get("user_id"), target.get("thread_id"))
    actual = (source.chat_id, source.user_id, source.thread_id)
    if (not expected[0] or not expected[1] or actual != expected
            or source.chat_id != source.user_id):
        return refused("target_mismatch")
    key = runner._session_key_for_source(source)
    if live.route != key or runner.session_store.peek_session_id(key) != sid:
        return refused("stale_session")
    if not runner._is_user_authorized_for_source(source):
        return refused("telegram_user_denied")
    if not policy_for_runner_source(runner, source).can_run(source.user_id, "new"):
        return refused("telegram_slash_denied")
    # An adapter has extra cancellation/debounce/drain effects outside the native
    # reset handler. Do not claim that the handler alone handles a busy Telegram turn.
    adapter = runner._adapter_for_source(source)
    if adapter is None:
        return refused("adapter_unavailable")
    event = MessageEvent(text="/new", source=copy.deepcopy(source),
                         user_id=source.user_id, internal=False)
    # Recheck immediately before mutation. Concurrent RPCs cannot reset an old id
    # after the first has rotated it; the loop and native handler own publication.
    # This lock only serializes THIS plugin, not Telegram's independent ingress.
    locks = getattr(runner, "_mc_new_locks", None)
    if locks is None:
        locks = runner._mc_new_locks = {}
    lock = locks.setdefault(key, asyncio.Lock())
    async with lock:
        if runner.session_store.peek_session_id(key) != sid:
            return refused("stale_session")
        try:
            async with runner._async_profile_scope_for_source(source):
                if session_is_busy(runner, adapter, live, key):
                    # Busy /new has side effects outside the reset handler: cancel the
                    # running turn, drop its debounce, drain the pending follow-up. The
                    # adapter's own dispatcher owns that tail; its message handler then
                    # routes to the native _busy_new_command -> _handle_reset_command.
                    from gateway.platforms.base_session_command import dispatch_active_session_command
                    await dispatch_active_session_command(adapter, event, key, "new")
                else:
                    # Call the real implementation; no duplicated reset algorithm.
                    await runner._handle_reset_command(event)
            new_sid = runner.session_store.peek_session_id(key)
        except Exception:
            return refused("native_reset_failed", uncertain=True)
        if not new_sid or new_sid == sid:
            return refused("rotation_not_observed", uncertain=True)
        return {"ok": True, "new_session_id": new_sid}


def register(ctx):
    home = Path(ctx._manager.home_path).resolve()
    broker = None
    if ctx.get_config("armed", False) is True:
        broker = LocalProofBroker(home)
        ctx.on_unload(broker.close)

    def new(params, *, session_id, **kwargs):
        if ctx.get_config("armed", False) is not True or broker is None:
            return refused("not_armed")
        if (not isinstance(session_id, str) or not SID.fullmatch(session_id)
                or set(params) != {"session_id", "local_proof"}
                or params["session_id"] != session_id):
            return refused("invalid_params")
        if not broker.consume(params.get("local_proof"), session_id):
            return refused("same_uid_proof_required")
        try:
            runner, loop, authority = runtime_for_home(home)
            future = asyncio.run_coroutine_threadsafe(
                native_new(runner, authority, session_id, home, ctx.get_config("target", {})), loop)
            return future.result(timeout=60)
        except Exception:
            # Do not cancel a partially executed reset. Caller MUST NOT retry blindly.
            return refused("gateway_failed_or_timeout", uncertain=True)

    ctx.register_rpc("mc.new", new)
