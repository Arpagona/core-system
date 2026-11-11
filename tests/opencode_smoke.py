"""Essai HTTP de Mission Control avec OpenCode réel et fournisseur local fictif."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from console import Console
from opencode_lab import OpenCodeLab

MODEL = "arpagona-smoke"


class Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, request.get("model"), bool(request.get("tools"))))
        if self.headers.get("x-api-key") != "synthetic":
            self.send_error(401)
            return
        events = [
            ("message_start", {"message": {
                "id": "msg_test", "type": "message", "role": "assistant",
                "model": MODEL, "content": [], "stop_reason": None,
                "stop_sequence": None, "usage": {"input_tokens": 24, "output_tokens": 0},
            }}),
            ("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"index": 0, "delta": {
                "type": "text_delta", "text": "quantity * unit_price",
            }}),
            ("content_block_stop", {"index": 0}),
            ("message_delta", {"delta": {"stop_reason": "end_turn", "stop_sequence": None},
                               "usage": {"output_tokens": 5}}),
            ("message_stop", {}),
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for name, event in events:
            self.wfile.write(f"event: {name}\ndata: {json.dumps({'type': name, **event})}\n\n".encode())


def smoke(executable):
    lab = OpenCodeLab(executable, f"anthropic/{MODEL}", "ANTHROPIC_API_KEY")
    with (
        ThreadingHTTPServer(("127.0.0.1", 0), Provider) as provider,
        ThreadingHTTPServer(("127.0.0.1", 0), Console) as console,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "synthetic"}),
    ):
        provider.requests = []
        console.token = "test-token"
        console.opencode_lab = lab
        config = lab.config()
        config["provider"] = {"anthropic": {
            "options": {"baseURL": f"http://127.0.0.1:{provider.server_port}/v1"},
            "models": {MODEL: {"name": "Fournisseur fictif",
                               "limit": {"context": 8192, "output": 256}}},
        }}
        for server in (provider, console):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{console.server_port}/api/opencode-lab"
        try:
            with patch.object(lab, "config", return_value=config):
                with urlopen(Request(url, b"{}", {
                    "Content-Type": "application/json", "X-Console-Token": console.token,
                }), timeout=5) as response:
                    assert response.status == 202
                deadline = time.monotonic() + 95
                while time.monotonic() < deadline:
                    with urlopen(url, timeout=5) as response:
                        result = json.load(response)
                    if result["state"] != "running":
                        break
                    time.sleep(0.1)
                assert result["state"] == "passed", result
                assert len(result["tests"]) == 3, result
                assert "+    return quantity * unit_price" in result["diff"], result
                assert provider.requests == [("/v1/messages", MODEL, False)], provider.requests
        finally:
            console.shutdown()
            provider.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opencode_bin")
    smoke(parser.parse_args().opencode_bin)
    print("Mission Control → OpenCode → fournisseur fictif : un appel, diff et trois tests réussis.")
