"""Console de test locale. Les lectures passent par le binaire Agent Core."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess

ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/console.js": ("console.js", "text/javascript; charset=utf-8"),
    "/console.css": ("console.css", "text/css; charset=utf-8"),
}
MISSION_LOG = re.compile(r"/api/missions/(m-[0-9]{8}-[0-9]{6}-[0-9a-f]{6})/log")


class Console(BaseHTTPRequestHandler):
    def reply(self, code, content, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)

    def json_reply(self, code, body):
        self.reply(code, json.dumps(body, ensure_ascii=False).encode(), "application/json")

    def do_GET(self):
        port = self.server.server_port
        if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            self.json_reply(403, {"error": "Adresse locale requise."})
            return

        asset = ASSETS.get(self.path)
        if asset:
            filename, content_type = asset
            content = Path(__file__).resolve().with_name(filename).read_bytes()
            self.reply(200, content, content_type)
            return

        if self.path == "/api/opencode":
            self.json_reply(200, {"available": shutil.which("opencode") is not None})
            return

        match = MISSION_LOG.fullmatch(self.path)
        if self.path == "/api/missions":
            args = ["list", "--json"]
        elif match:
            args = ["log", match.group(1)]
        else:
            self.json_reply(404, {"error": "Page introuvable."})
            return

        try:
            result = subprocess.run(
                [*self.server.agentcore, "mission", *args],
                capture_output=True, text=True, check=True, timeout=5,
            )
            body = {"log": result.stdout} if match else json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            self.json_reply(503, {"error": "Le journal Agent Core est indisponible."})
            return
        self.json_reply(200, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agentcore", default="agentcore")
    parser.add_argument("--config")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Console) as server:
        server.agentcore = [args.agentcore]
        if args.config:
            server.agentcore.extend(["--config", args.config])
        print(f"Console Agent Core · http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
