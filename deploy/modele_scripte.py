#!/usr/bin/env python3
"""Fournisseur OpenAI-compatible SCRIPTÉ pour la recette (R2) : aucun vrai modèle, aucun réseau externe.

Écoute en boucle locale sur un port libre, écrit ce port dans --port-file, puis répond à
POST <base>/chat/completions :
  - tant qu'aucun résultat d'outil n'est présent : un lot fixe de tentatives HORS PÉRIMÈTRE
    (lecture et écriture d'annexes, lecture de la clé API) passé en --anx ;
  - ensuite : une réponse finale sans outil.
Le nombre de requêtes reçues est écrit dans --count-file. Le jeton Authorization est ignoré
et jamais journalisé.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def attempts(anx: str) -> list:
    calls = [
        ("read_file", {"path": f"{anx}/tarifs.md"}),
        ("write_file", {"path": f"{anx}/copie-synthese.md", "content": "copie hors périmètre"}),
        ("read_file", {"path": "/etc/agentcore/api_key"}),
    ]
    return [
        {"id": f"hp-{i}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls, 1)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anx", required=True)
    ap.add_argument("--port-file", required=True)
    ap.add_argument("--count-file", required=True)
    a = ap.parse_args()
    count = Path(a.count_file)
    count.write_text("0")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # pas de journal (en-têtes compris)
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            count.write_text(str(int(count.read_text()) + 1))
            if not self.path.endswith("/chat/completions"):
                self.send_response(404)
                self.end_headers()
                return
            seen_tool = any(m.get("role") == "tool" for m in body.get("messages", []))
            if seen_tool:
                msg, finish = {"role": "assistant", "content": "Accès hors périmètre refusés ; synthèse non produite."}, "stop"
            else:
                msg, finish = {"role": "assistant", "content": None, "tool_calls": attempts(a.anx)}, "tool_calls"
            out = json.dumps({
                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    Path(a.port_file).write_text(str(srv.server_port))
    srv.serve_forever()


if __name__ == "__main__":
    main()
