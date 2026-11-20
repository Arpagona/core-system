"""Offline contract tests: real reset handler + isolated real SessionStore, fake runner/adapters."""
import asyncio
from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mc_new_test_plugin", ROOT / "mc-new" / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
import gateway_new


@pytest.fixture
def anyio_backend():
    # anyio ships with Hermes' venv; pytest-asyncio is intentionally not installed.
    return "asyncio"


def proof_home():
    # AF_UNIX paths are limited to 108 bytes: pytest's tmp_path is too deep for proof.sock.
    home = ROOT / ".test-runtime" / "proof-home"
    home.mkdir(mode=0o700, exist_ok=True)
    return home


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from gateway.config import GatewayConfig, Platform
    from gateway.session import SessionStore, SessionSource
    from gateway.slash_commands_session import GatewaySessionCommandsMixin
    import gateway.session_automation as automation
    import gateway.slash_commands_session as reset
    import gateway.slash_access as access

    home = tmp_path / "profile"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("HERMES_HOME", str(home))
    log = []
    source = SessionSource(Platform.TELEGRAM, "123", user_id="123", thread_id="9", profile="gpt5")
    store = SessionStore(home / "sessions", GatewayConfig())
    entry = store.get_or_create_session(source)
    key = entry.session_key
    live = SimpleNamespace(source=source, route=key, task=None)
    authority = SimpleNamespace(profile_id=str(home), sessions={entry.session_id: live},
                                logical_owner=lambda sid: sid, retiring=False)
    debounce = {}
    adapter = SimpleNamespace(
        name="fake-telegram", _active_sessions={}, _pending_messages={},
        _text_debounce_store=lambda: debounce, _authorization_check=object(),
        _session_tasks={}, _session_task_is_stale=lambda key, *a: False)

    def record(name):
        def fn(*args, **kwargs):
            log.append(name)
        return fn

    @asynccontextmanager
    async def scope(*args):
        yield

    async def async_record(name, *args, **kwargs):
        log.append(name)

    async def rotate(key):
        log.append("rotate")
        return store.reset_session(key)

    runner = SimpleNamespace(
        session_store=store, async_session_store=SimpleNamespace(reset_session=rotate),
        _session_key_for_source=lambda src: key, _async_profile_scope_for_source=scope,
        _is_user_authorized_for_source=lambda src: True, _adapter_for_source=lambda src: adapter,
        _running_agents={}, _session_db=None,
        _hm_stop_owner_turn=lambda *a: async_record("stop"),
        _invalidate_session_run_generation=record("generation"),
        _release_running_agent_state=record("release"),
        _cleanup_old_agent_for_reset=lambda *a: async_record("cleanup"),
        _evict_cached_agent=record("evict"), _clear_conversation_scope=record("clear"),
        _fire_session_reset_hooks=lambda *a: async_record("hooks"),
        _fire_plugin_session_reset=lambda *a: async_record("plugin_hook"),
        _reset_notice_session_info=lambda *a: "fake model",
        _telegram_topic_new_header=lambda *a: "new topic", _is_telegram_topic_lane=lambda *a: True,
        _record_telegram_topic_binding=lambda src, ent: bindings.update({src.thread_id: ent.session_id}))
    bindings = {source.thread_id: entry.session_id}
    runner._handle_reset_command = lambda ev: GatewaySessionCommandsMixin._handle_reset_command(runner, ev)

    # Native busy path: adapter dispatch -> real message handler -> GatewayBusySessionMixin.
    from gateway.run_busy import GatewayBusySessionMixin
    from hermes_cli.commands import resolve_command

    async def busy_new(event, session_key, source):
        return await GatewayBusySessionMixin._busy_new_command(runner, event, session_key, source)

    async def dispatch_busy(event, cmd_def, session_key, source):
        return await GatewayBusySessionMixin._dispatch_busy_slash_command(
            runner, event, cmd_def, session_key, source)

    runner._busy_new_command = busy_new
    runner._dispatch_busy_slash_command = dispatch_busy
    runner._busy_slash_route = lambda cmd_def: GatewayBusySessionMixin._busy_slash_route(runner, cmd_def)
    runner._BUSY_SPECIAL_HANDLERS = GatewayBusySessionMixin._BUSY_SPECIAL_HANDLERS
    runner._interrupt_and_clear_session = lambda *a, **k: async_record("interrupt")

    async def message_handler(event):
        log.append("busy_new")
        return await runner._dispatch_busy_slash_command(
            event, resolve_command("new"), key, source)

    async def inline_reply(event, *, log_cmd=None):
        log.append("reply")
        adapter.last_reply = await message_handler(event)

    async def cancel_session_processing(session_key, *, release_guard, discard_pending):
        log.append("cancel")

    def discard_text_debounce(session_key):
        log.append("discard_debounce")
        debounce.pop(session_key, None)

    async def flush_text_debounce_now(session_key):
        log.append("flush")

    async def drain_pending(session_key, command_guard):
        log.append("drain")
        pending = adapter._pending_messages.pop(session_key, None)
        adapter._release_session_guard(session_key, guard=command_guard)
        if pending is not None:
            adapter._start_session_processing(pending, session_key)

    adapter._message_handler = message_handler
    adapter._dispatch_inline_reply = inline_reply
    adapter.cancel_session_processing = cancel_session_processing
    adapter._discard_text_debounce = discard_text_debounce
    adapter._flush_text_debounce_now = flush_text_debounce_now
    adapter._drain_pending_after_session_command = drain_pending
    adapter._release_session_guard = record("release_guard")
    adapter._start_session_processing = record("start_pending")
    monkeypatch.setattr(automation, "route_owner_lock", scope)
    monkeypatch.setattr(automation, "move_route_wakes", lambda *a: async_record("wakes"))
    monkeypatch.setattr(reset, "paused_followers", AsyncMock(return_value=0))
    monkeypatch.setattr(reset, "_reset_process_scoped_tool_state", record("tool_reset"))
    monkeypatch.setattr(access, "policy_for_runner_source", lambda *a: SimpleNamespace(can_run=lambda *a: True))
    monkeypatch.setitem(sys.modules, "tools.async_delegation", SimpleNamespace(interrupt_for_session=record("delegations")))
    target = {"chat_id": "123", "user_id": "123", "thread_id": "9"}
    return SimpleNamespace(home=home, runner=runner, authority=authority, sid=entry.session_id,
                           source=source, key=key, log=log, bindings=bindings, target=target,
                           adapter=adapter, debounce=debounce)


async def invoke(r):
    return await plugin.native_new(r.runner, r.authority, r.sid, r.home, r.target)


@pytest.mark.anyio
async def test_real_native_handler_rotates_real_store_and_rebinds_fake_topic(rig):
    result = await invoke(rig)
    assert result["ok"] and result["new_session_id"] != rig.sid
    assert rig.runner.session_store.peek_session_id(rig.key) == result["new_session_id"]
    assert rig.bindings["9"] == result["new_session_id"]
    assert rig.log == ["stop", "generation", "release", "cleanup", "evict", "clear",
                       "delegations", "tool_reset", "rotate", "wakes", "hooks", "plugin_hook"]
    assert rig.source.thread_id == "9"  # original live source is not rewritten


@pytest.mark.anyio
async def test_repeated_old_id_refused_without_second_reset(rig):
    assert (await invoke(rig))["ok"]
    log = list(rig.log)
    assert (await invoke(rig))["error"] == "stale_session"
    assert rig.log == log


@pytest.mark.anyio
@pytest.mark.parametrize("case,reason", [
    ("wrong_profile", "profile_mismatch"), ("wrong_user", "target_mismatch"),
    ("wrong_thread", "target_mismatch"), ("stale", "stale_session"),
    ("group", "not_live_private_telegram"), ("detached", "not_live_private_telegram"),
    ("missing", "not_live_private_telegram"), ("denied", "telegram_user_denied"),
])
async def test_refusals_are_nonmutating(rig, case, reason):
    if case == "wrong_profile": rig.authority.profile_id = str(rig.home / "other")
    if case == "wrong_user": rig.target["user_id"] = "456"
    if case == "wrong_thread": rig.target["thread_id"] = "8"
    if case == "stale": rig.sid = "stale"
    if case == "group": rig.source.chat_type = "group"
    if case == "detached": rig.source.detached_route = "detached-x"
    if case == "missing": rig.authority.sessions.clear()
    if case == "denied": rig.runner._is_user_authorized_for_source = lambda src: False
    if case == "stale":
        # live owner exists, but its route is now a different physical id
        rig.authority.sessions[rig.sid] = next(iter(rig.authority.sessions.values()))
    result = await invoke(rig)
    assert result["error"] == reason
    assert not rig.log


@pytest.mark.anyio
async def test_concurrent_same_old_id_rotates_once(rig):
    results = await asyncio.gather(invoke(rig), invoke(rig))
    assert sum(r["ok"] for r in results) == 1
    assert rig.log.count("rotate") == 1


@pytest.mark.anyio
async def test_busy_session_uses_native_adapter_dispatch_and_rotates(rig):
    # Busy by both runner state and adapter guard; a held debounce and a pending follow-up exist.
    rig.runner._running_agents[rig.key] = object()
    rig.adapter._active_sessions[rig.key] = object()
    rig.debounce[rig.key] = SimpleNamespace(cancel_timer=lambda: rig.log.append("debounce_cancel"))
    pending = object()
    rig.adapter._pending_messages[rig.key] = pending
    result = await invoke(rig)
    assert result["ok"] and result["new_session_id"] != rig.sid, result
    assert rig.runner.session_store.peek_session_id(rig.key) == result["new_session_id"]
    assert "debounce_cancel" in rig.log
    assert rig.log[rig.log.index("reply"):rig.log.index("reply") + 3] == ["reply", "busy_new", "interrupt"]
    assert rig.log.count("rotate") == 1
    # Same adapter tail as a native busy /new: discard debounce, cancel the turn, drain the follow-up.
    assert rig.log[-5:] == ["discard_debounce", "cancel", "drain", "release_guard", "start_pending"]
    assert pending not in rig.adapter._pending_messages.values()


@pytest.mark.anyio
async def test_busy_adapter_guard_alone_uses_native_dispatch(rig):
    rig.adapter._active_sessions[rig.key] = object()
    result = await invoke(rig)
    assert result["ok"], result
    assert "busy_new" in rig.log and "cancel" in rig.log
    assert rig.log.count("rotate") == 1


def test_local_uid_proof_single_use_bound_and_expiring():
    home = proof_home()
    broker = plugin.LocalProofBroker(home)
    try:
        proof = gateway_new.get_local_proof(home, "s1")
        assert broker.consume(proof, "s1")
        assert not broker.consume(proof, "s1")
        proof = gateway_new.get_local_proof(home, "s1")
        assert not broker.consume(proof, "s2")
        assert not broker.consume(proof, "s1")
        broker.pending["expired"] = ("s1", time.monotonic() - 1)
        assert not broker.consume("expired", "s1")
    finally:
        broker.close()
    assert not broker.path.exists()


def test_peer_uid_rejected():
    import struct
    class Peer:
        def getsockopt(self, *a): return struct.pack("3i", 1, plugin.os.getuid() + 1, 1)
    assert not plugin.LocalProofBroker.same_uid(Peer())


def test_unsafe_directory_refused(tmp_path):
    directory = tmp_path / "mc-new-runtime"
    directory.mkdir(mode=0o755)
    with pytest.raises(RuntimeError, match="unsafe proof directory"):
        plugin.LocalProofBroker(tmp_path)


def test_unarmed_plugin_registers_namespaced_rpc_only(tmp_path):
    from hermes_cli import plugins
    import hermes_yaml as yaml
    home = tmp_path
    directory = home / "plugins" / "mc-new"
    directory.mkdir(parents=True)
    import shutil
    for name in ("__init__.py", "plugin.yaml"):
        shutil.copyfile(ROOT / "mc-new" / name, directory / name)
    (home / "config.yaml").write_text(yaml.safe_dump({"plugins": {"enabled": ["mc-new"]}}))
    manager = plugins.PluginManager(scope_key=str(home))
    manager.discover_and_load()
    handler = manager._plugin_rpc_methods["plugin.mc-new.mc.new"]
    assert handler({}, session_id="s1")["error"] == "not_armed"
    assert not (home / "mc-new-runtime").exists()


@pytest.mark.anyio
async def test_generic_reset_refuses_messaging_without_local_policy(tmp_path):
    from hermes_state import SessionDB
    from hermes_state_mutation_reset import reset_in_transaction
    from hermes_state_runtime import RuntimeStoreError
    db = SessionDB(tmp_path / "state.db")
    db.create_session(session_id="telegram-s", source="telegram", model="fake")
    with db._read_ctx() as conn:
        with pytest.raises(RuntimeStoreError) as error:
            reset_in_transaction(db, conn, "telegram-s", {})
    assert error.value.reason == "runtime_coordination_required"
    assert db.get_session("telegram-s")["ended_at"] is None
    db.close()


@pytest.mark.anyio
async def test_client_calls_only_plugin_rpc(monkeypatch, tmp_path):
    import hermes_cli.gateway_client as client
    import hermes_cli.gateway_runtime as runtime
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    calls = []
    class Connection:
        async def rpc(self, method, **params):
            calls.append((method, params))
            return {"ok": True, "new_session_id": "s2"}
    @asynccontextmanager
    async def connect(**kw): yield Connection()
    monkeypatch.setattr(runtime, "discover_gateway_endpoint", lambda h: SimpleNamespace(endpoint="fake"))
    monkeypatch.setattr(runtime, "attachable", lambda o: True)
    monkeypatch.setattr(client, "connect_gateway", connect)
    monkeypatch.setattr(gateway_new, "get_local_proof", lambda *a: "in-memory-fake")
    assert await gateway_new.operate({"id": "s1"}) == {"ok": True, "new_session_id": "s2"}
    assert calls == [("plugin.mc-new.mc.new", {"session_id": "s1", "local_proof": "in-memory-fake"})]


@pytest.mark.anyio
@pytest.mark.parametrize("data", [{}, {"id": "s", "op": "reset"}, {"id": "../x"}, {"id": None}])
async def test_client_invalid_json_shape(data):
    with pytest.raises(ValueError): await gateway_new.operate(data)
