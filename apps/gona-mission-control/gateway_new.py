#!/usr/bin/env python3
"""Mission Control adapter: stdin {id: physical_session_id}, stdout JSON.

No resume, reset/mutate fallback, prompt submission, retry or gateway lifecycle.
Use Hermes' venv/PYTHONPATH and the intended HERMES_HOME explicitly.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys


def get_local_proof(home, sid):
    directory = Path(home) / "mc-new-runtime"
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError("unsafe proof directory")
    path = directory / "proof.sock"
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("unsafe proof socket")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(3)
        peer.connect(str(path))
        peer.sendall(json.dumps({"id": sid}).encode() + b"\n")
        with peer.makefile("rb") as reader:
            result = json.loads(reader.readline(1025))
    return result["proof"]


async def operate(data):
    if (not isinstance(data, dict) or set(data) != {"id"}
            or not isinstance(data["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", data["id"])):
        raise ValueError("expected JSON {id: session_id}")
    home = os.environ["HERMES_HOME"]
    from hermes_cli.gateway_client import connect_gateway
    from hermes_cli.gateway_runtime import discover_gateway_endpoint, attachable
    owner = await asyncio.to_thread(discover_gateway_endpoint, home)
    if not attachable(owner):
        raise ValueError("gateway unavailable; no other agent started")
    # Do not session.resume: stale, detached or compressed aliases must be refused
    # by the server, not implicitly moved onto another conversation.
    proof = await asyncio.to_thread(get_local_proof, home, data["id"])
    async with connect_gateway(endpoint=owner.endpoint) as gateway:
        result = await gateway.rpc("plugin.mc-new.mc.new", session_id=data["id"], local_proof=proof)
    if not isinstance(result, dict) or type(result.get("ok")) is not bool:
        raise RuntimeError("invalid gateway response")
    if result["ok"] and (not isinstance(result.get("new_session_id"), str)
                         or result["new_session_id"] == data["id"]):
        raise RuntimeError("rotation not observed")
    return result


def main():
    try:
        raw = sys.stdin.read(4097)
        if len(raw) > 4096:
            raise ValueError("input too large")
        result = asyncio.run(operate(json.loads(raw)))
    except Exception as exc:
        # Never print exception details: an RPC parameter may contain a local proof.
        result = {"ok": False, "new_session_id": None, "error": type(exc).__name__,
                  "uncertain": not isinstance(exc, (ValueError, FileNotFoundError))}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
