#!/usr/bin/env python3
"""Mission Control live adapter.

Reads one JSON object on stdin. ``op=stream`` prints sanitized gateway events as JSON
lines until the connection ends, for the SSE relay. Other ops (interrupt, approval,
clarify) call the gateway's native RPC and print one JSON result.

Read-only unless an explicit user control op is requested. Use Hermes' venv/PYTHONPATH
and HERMES_HOME explicitly. Never prints exception details or raw tool arguments.
"""
import asyncio
import json
import os
import re
import sys

SID_RE = re.compile(r"[A-Za-z0-9_-]{1,100}")
TOOL_RE = re.compile(r"[A-Za-z0-9_.:/-]{1,80}")
SECRET_PATTERNS = (
    re.compile(r"(?i)([A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|passwd))"
               r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(authorization)\b(\s*[:=]\s*)([^\s,;]+)"),
)
CONTROL_TYPES = frozenset({
    "approval.request", "approval.settled", "clarify.request", "clarify.settled",
})
MAX_PREVIEW = 40


def redact(value):
    text = value if isinstance(value, str) else ""
    for pattern in SECRET_PATTERNS:
        if pattern.groups == 3:
            text = pattern.sub(lambda m: m.group(1) + m.group(2) + "[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


def _text(value, limit=0):
    if not isinstance(value, str):
        return ""
    text = redact(value)
    return text[:limit] + ("…" if limit and len(text) > limit else "")


def _preview(payload):
    for key in ("context",):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            line = " ".join(value.split())
            return _text(line, MAX_PREVIEW)
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    for key in ("command", "path", "file_path", "query", "url", "pattern", "description", "title"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return _text(" ".join(value.split()), MAX_PREVIEW)
    return ""


def _tool_name(payload):
    name = payload.get("tool_name") or payload.get("name") or "tool"
    return name if isinstance(name, str) and TOOL_RE.fullmatch(name) else "tool"


def _prompt(payload, kind):
    prompt = {
        "kind": kind,
        "prompt_id": _text(payload.get("prompt_id"), 120),
        "generation": payload.get("execution_generation"),
    }
    if kind == "approval":
        prompt["command"] = _text(payload.get("command"), 600)
        prompt["description"] = _text(payload.get("description"), 400)
        choices = payload.get("choices")
        prompt["choices"] = [c for c in choices if c in {"once", "deny", "session", "always"}] if isinstance(choices, list) else []
        if isinstance(payload.get("edit"), dict):
            prompt["edit"] = True
    else:
        prompt["question"] = _text(payload.get("question"), 1200)
        choices = payload.get("choices")
        prompt["choices"] = [_text(c, 200) for c in choices[:30]] if isinstance(choices, list) else []
        prompt["multi_select"] = bool(payload.get("multi_select"))
    if isinstance(payload.get("timeout_s"), (int, float)) and not isinstance(payload.get("timeout_s"), bool):
        prompt["timeout_s"] = payload["timeout_s"]
    return prompt


def sanitize_event(params):
    """One gateway event frame -> the small, safe event the browser may receive."""
    if not isinstance(params, dict):
        return None
    kind = params.get("type")
    payload = params.get("payload") if isinstance(params.get("payload"), dict) else {}
    base = {
        "session": _text(params.get("session_id"), 100),
        "admission": _text(params.get("admission_id"), 100),
        "generation": params.get("execution_generation"),
    }
    if kind == "message.start":
        return {**base, "type": "writing"}
    if kind == "message.delta":
        text = payload.get("text") or payload.get("delta") or payload.get("content") or ""
        return {**base, "type": "delta", "text": text} if isinstance(text, str) and text else None
    if kind == "message.complete":
        text = payload.get("text") or payload.get("content") or ""
        event = {"type": "complete", **base, "text": text if isinstance(text, str) else ""}
        status = payload.get("status")
        if status in ("complete", "interrupted", "error"):
            event["status"] = status
        warning = _text(payload.get("warning"), 800)
        if warning:
            event["warning"] = warning
        return event
    if kind == "tool.start":
        return {**base, "type": "tool", "name": _tool_name(payload), "preview": _preview(payload)}
    if kind == "tool.complete":
        return {**base, "type": "tool_done", "name": _tool_name(payload),
                "preview": _preview(payload), "is_error": bool(payload.get("is_error"))}
    if kind in ("approval.request", "clarify.request"):
        return {**base, "type": "control", "prompt": _prompt(payload, "approval" if kind.startswith("approval") else "clarify")}
    if kind in ("approval.settled", "clarify.settled"):
        return {**base, "type": "control_settled", "kind": kind.split(".")[0],
                "prompt_id": _text(payload.get("prompt_id"), 120)}
    if kind == "session.info":
        info = {
            "model": _text(payload.get("model"), 120),
            "reasoning": _text(payload.get("reasoning_effort"), 40),
            "title": _text(payload.get("title"), 200),
            "yolo": bool(payload.get("yolo")),
        }
        return {**base, "type": "info", "info": info}
    if kind in ("status.update", "notification.show"):
        text = _text(payload.get("text"), 2000)
        return {**base, "type": "notice", "text": text} if text.strip() else None
    if kind == "session.replay_gap":
        return {"type": "gap"}
    return None


def sanitize_prompt(prompt):
    if not isinstance(prompt, dict) or prompt.get("kind") not in ("approval", "clarify"):
        return None
    return _prompt(prompt, prompt["kind"])


def snapshot_event(state):
    info = state.get("info") if isinstance(state.get("info"), dict) else {}
    return {
        "type": "snapshot",
        "session": _text(state.get("stored_session_id") or state.get("session_id"), 100),
        "running": bool(state.get("running")),
        "generation": state.get("execution_generation"),
        "replay_epoch": _text(state.get("replay_epoch"), 64),
        "last_sequence": state.get("last_sequence"),
        "info": {
            "model": _text(info.get("model"), 120),
            "reasoning": _text(info.get("reasoning_effort"), 40),
            "title": _text(info.get("title"), 200),
            "yolo": bool(info.get("yolo")),
        },
        "prompts": [p for p in (sanitize_prompt(p) for p in state.get("prompts") or []) if p],
        "pending": [{"admission_id": _text(row.get("admission_id"), 100), "status": _text(row.get("status"), 40)}
                    for row in state.get("pending") or [] if isinstance(row, dict)],
    }


def emit(item):
    sys.stdout.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


async def _connect(home):
    from hermes_cli.gateway_client import connect_gateway
    from hermes_cli.gateway_runtime import attachable, discover_gateway_endpoint
    owner = await asyncio.to_thread(discover_gateway_endpoint, home)
    if not attachable(owner):
        raise ValueError("gateway unavailable; no other agent started")
    return connect_gateway(endpoint=owner.endpoint)


async def stream(sid, home):
    async with await _connect(home) as gateway:
        state = await gateway.rpc("session.resume", session_id=sid)
        target = state.get("stored_session_id") or state.get("session_id") or sid
        try:
            info = await gateway.rpc("session.info", session_id=target)
            if isinstance(info, dict):
                state["info"] = {**(state.get("info") or {}), **info}
        except Exception:
            pass
        emit(snapshot_event(state))
        emit({"type": "ready", "session": _text(target, 100)})
        while True:
            frame = await gateway.events.get()
            if isinstance(frame, Exception):
                raise frame
            params = frame.get("params") if isinstance(frame, dict) else None
            if not isinstance(params, dict) or params.get("session_id") != target:
                continue
            event = sanitize_event(params)
            if event is None:
                continue
            emit(event)
            if event["type"] in ("gap",):
                return


async def control(data, home):
    sid = data["id"]
    op = data["op"]
    async with await _connect(home) as gateway:
        state = await gateway.rpc("session.resume", session_id=sid)
        target = state.get("stored_session_id") or state.get("session_id") or sid
        requested = data.get("generation")
        generation = requested if isinstance(requested, int) and not isinstance(requested, bool) else state.get("execution_generation", 0)
        if op == "interrupt":
            result = await gateway.rpc("session.interrupt", session_id=target,
                                       execution_generation=generation)
        elif op == "respond":
            kind = data.get("kind")
            if kind not in ("approval", "clarify"):
                raise ValueError("invalid control kind")
            method = kind + ".respond"
            params = {"session_id": target, "execution_generation": generation,
                      "prompt_id": data.get("prompt_id")}
            if kind == "approval":
                params["choice"] = data.get("choice")
            else:
                params["answer"] = data.get("answer")
            result = await gateway.rpc(method, **params)
        else:
            raise ValueError("invalid operation")
    return {"ok": True, "status": (result or {}).get("status"),
            "prompt_id": _text((result or {}).get("prompt_id"), 120)}


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not SID_RE.fullmatch(data["id"]):
        raise ValueError("expected JSON {id: session_id}")
    op = data.get("op", "stream")
    if op not in ("stream", "interrupt", "respond"):
        raise ValueError("invalid operation")
    allowed = {"id", "op"} | ({"kind", "prompt_id", "choice", "answer", "generation"} if op == "respond" else set())
    if set(data) - allowed:
        raise ValueError("unexpected field")
    if op == "respond":
        if data.get("kind") not in ("approval", "clarify"):
            raise ValueError("invalid control kind")
        if not isinstance(data.get("prompt_id"), str) or not data["prompt_id"]:
            raise ValueError("prompt id required")
        if data["kind"] == "approval" and not isinstance(data.get("choice"), str):
            raise ValueError("choice required")
        if data["kind"] == "clarify" and not isinstance(data.get("answer"), str):
            raise ValueError("answer required")
    return op


def main():
    try:
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            raise ValueError("input too large")
        data = json.loads(raw)
        op = validate(data)
        home = os.environ["HERMES_HOME"]
        if op == "stream":
            asyncio.run(stream(data["id"], home))
            return 0
        emit(asyncio.run(control(data, home)))
        return 0
    except Exception as exc:
        emit({"type": "fatal", "error": type(exc).__name__, "ok": False})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
