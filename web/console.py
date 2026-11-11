"""Console Mission Control d'Agent Core (boucle locale, à utiliser via un tunnel SSH).

Lectures : toujours via le binaire Agent Core (`mission list --json`, `mission log ID --json`,
`version`). Actions (lancer, reprendre, annuler, résoudre) : mêmes commandes CLI, donc mêmes
politiques et plafonds. Les écritures exigent un jeton de session injecté dans la page, un hôte
local et du JSON ; le lancement n'accepte que des dossiers préautorisés au démarrage.
"""

import argparse
import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/console.js": ("console.js", "text/javascript; charset=utf-8"),
    "/pixels.js": ("pixels.js", "text/javascript; charset=utf-8"),
    "/console.css": ("console.css", "text/css; charset=utf-8"),
    "/fonts/pixelify-latin.woff2": ("fonts/pixelify-latin.woff2", "font/woff2"),
    "/fonts/pixelify-latin-ext.woff2": ("fonts/pixelify-latin-ext.woff2", "font/woff2"),
}
ID = r"m-[0-9]{8}-[0-9]{6}-[0-9a-f]{6}(?:-[a-z0-9-]+)?"
MISSION = re.compile(rf"/api/missions/({ID})")
ACTION = re.compile(rf"/api/missions/({ID})/(cancel|resume|resolve)")
CALL_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
STARTED = re.compile(rf"^(?:mission|reprise de) ({ID})\b")
MAX_TEXT = 600  # contenu d'outil renvoyé au navigateur (le journal complet reste sur le serveur)


def trim(value, limit=MAX_TEXT):
    """Raccourcit récursivement les longues chaînes (contenus de fichiers lus)."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"… [{len(value)} caractères]"
    if isinstance(value, list):
        return [trim(v, limit) for v in value[:60]]
    if isinstance(value, dict):
        return {k: trim(v, limit) for k, v in value.items()}
    return value


class Cpu:
    """Charge CPU entre deux lectures de /proc/stat."""

    def __init__(self):
        self.prev = None
        self.lock = threading.Lock()

    @staticmethod
    def sample():
        with open("/proc/stat") as f:
            values = [int(v) for v in f.readline().split()[1:]]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return sum(values), idle

    def percent(self):
        with self.lock:
            if self.prev is None:
                self.prev = self.sample()
                time.sleep(0.2)
            total, idle = self.sample()
            dt, di = total - self.prev[0], idle - self.prev[1]
            self.prev = (total, idle)
        return round(100 * (dt - di) / dt) if dt > 0 else 0


def memory():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0])
    total, avail = info.get("MemTotal", 0), info.get("MemAvailable", 0)
    return {"percent": round(100 * (total - avail) / total) if total else 0,
            "used_gib": round((total - avail) / 1048576, 1), "total_gib": round(total / 1048576, 1)}


class Console(BaseHTTPRequestHandler):
    server_version = "AgentCoreConsole"
    sys_version = ""

    def log_message(self, format, *args):
        pass  # pas de journal HTTP (le jeton circule dans les en-têtes)

    # ---- réponses -------------------------------------------------------------------------
    def reply(self, code, content, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(content)

    def json_reply(self, code, body):
        self.reply(code, json.dumps(body, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def local_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    # ---- CLI ------------------------------------------------------------------------------
    def cli(self, *args, timeout=10):
        return subprocess.run([*self.server.agentcore, *args], capture_output=True, text=True,
                              timeout=timeout, check=False)

    def cli_json(self, *args):
        r = self.cli(*args)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout).strip()[:300])
        return json.loads(r.stdout)

    def spawn(self, *args):
        """Lance une commande longue (run/resume) détachée ; renvoie l'ID annoncé."""
        proc = subprocess.Popen([*self.server.agentcore, *args], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, start_new_session=True)
        found = {"lines": []}
        ready = threading.Event()

        def drain():
            for line in proc.stdout:
                m = STARTED.match(line)
                if m and "id" not in found:
                    found["id"] = m.group(1)
                    ready.set()
                found["lines"] = (found["lines"] + [line.rstrip()[:300]])[-5:]
            proc.wait()
            ready.set()

        threading.Thread(target=drain, daemon=True).start()
        ready.wait(15)
        self.server.children.append(proc)
        return found.get("id"), proc, list(found["lines"])

    # ---- GET ------------------------------------------------------------------------------
    def do_GET(self):
        if not self.local_host():
            self.json_reply(403, {"error": "Adresse locale requise."})
            return
        asset = ASSETS.get(self.path)
        if asset:
            name, ctype = asset
            content = (HERE / name).read_bytes()
            if name == "index.html":
                content = content.replace(b"{{TOKEN}}", self.server.token.encode())
            self.reply(200, content, ctype)
            return
        try:
            if self.path == "/api/overview":
                self.json_reply(200, self.overview())
                return
            m = MISSION.fullmatch(self.path)
            if m:
                data = self.cli_json("mission", "log", m.group(1), "--json")
                data["events"] = trim(data.get("events", []))
                self.json_reply(200, data)
                return
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as e:
            self.json_reply(503, {"error": f"Agent Core indisponible : {e}"})
            return
        self.json_reply(404, {"error": "Page introuvable."})

    def version(self):
        r = self.cli("version", timeout=5)
        info = {"ok": r.returncode == 0, "lines": r.stdout.strip().splitlines()}
        for line in info["lines"]:
            if line.startswith("agentcore "):
                info["version"] = line.split(" ", 1)[1]
            elif ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        return info

    def guardian(self, version):
        """Intégrité du binaire actif et dernière recette (verdicts réels, sinon « inconnu »)."""
        g = {"integrity": "inconnue", "recette": None}
        binary = shutil.which(self.server.agentcore[0]) or self.server.agentcore[0]
        real = Path(binary).resolve()
        sums = real.with_name("SHA256SUMS")
        if sums.is_file():
            expected = next((l.split()[0] for l in sums.read_text().splitlines()
                             if l.strip().endswith(real.name)), None)
            actual = hashlib.sha256(real.read_bytes()).hexdigest()
            g["integrity"] = "ok" if expected == actual else "écart"
        rdir = Path(self.server.recette_dir).expanduser()
        runs = sorted(rdir.glob("*/verdicts.txt")) if rdir.is_dir() else []
        for verdicts in reversed(runs):
            lines = verdicts.read_text(errors="replace").splitlines()
            bilan = next((l for l in lines if l.startswith("BILAN")), None)
            if bilan:
                nums = re.findall(r"(\d+) (PASS|FAIL|non)", bilan)
                counts = {k: int(n) for n, k in nums}
                g["recette"] = {"run": verdicts.parent.name, "pass": counts.get("PASS", 0),
                                "fail": counts.get("FAIL", 0), "nc": counts.get("non", 0),
                                "lines": [l for l in lines if not l.startswith("BILAN")][:20]}
                break
        healthy = g["integrity"] == "ok" and version.get("ok") and (
            g["recette"] is None or g["recette"]["fail"] == 0)
        g["status"] = "sain" if healthy else "à vérifier"
        return g

    def overview(self):
        version = self.version()
        missions = self.cli_json("mission", "list", "--json")
        validations = []
        for m in missions:
            if m.get("state") == "uncertain":
                try:
                    log = self.cli_json("mission", "log", m["id"], "--json")
                    calls = {}
                    for ev in log.get("events", []):
                        for c in ev.get("kind", {}).get("tool_calls") or []:
                            calls[c.get("id")] = c
                    for call_id in log["report"].get("uncertain") or []:
                        c = calls.get(call_id, {})
                        args = c.get("arguments") if isinstance(c.get("arguments"), dict) else {}
                        validations.append({"mission": m["id"], "goal": m.get("goal"), "call_id": call_id,
                                            "tool": c.get("name"), "path": str(args.get("path", ""))[:200]})
                except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError):
                    validations.append({"mission": m["id"], "goal": m.get("goal"), "call_id": None})
        state_dir = version.get("état")
        disk = None
        if state_dir and Path(state_dir).exists():
            du = shutil.disk_usage(state_dir)
            disk = {"percent": round(100 * du.used / du.total), "free_gib": round(du.free / 2**30, 1)}
        self.server.children[:] = [p for p in self.server.children if p.poll() is None]
        return {
            "version": version,
            "missions": missions,
            "validations": validations,
            "resources": {"cpu": self.server.cpu.percent(), "ram": memory(), "disk": disk,
                          "load": round(os.getloadavg()[0], 2), "hostname": os.uname().nodename},
            "guardian": self.guardian(version),
            "dream": {"configured": False},
            "opencode": shutil.which("opencode") is not None,
            "inputs": self.server.inputs,
            "running_children": len(self.server.children),
        }

    # ---- POST -----------------------------------------------------------------------------
    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("JSON requis")
        length = int(self.headers.get("Content-Length", 0))
        if length > 8192:
            raise ValueError("requête trop longue")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_POST(self):
        origin = self.headers.get("Origin")
        port = self.server.server_port
        if not self.local_host() or (origin and origin not in {
                f"http://127.0.0.1:{port}", f"http://localhost:{port}"}):
            self.json_reply(403, {"error": "Adresse locale requise."})
            return
        if not secrets.compare_digest(self.headers.get("X-Console-Token", ""), self.server.token):
            self.json_reply(403, {"error": "Jeton de session invalide : recharger la page."})
            return
        try:
            data = self.body()
        except ValueError as e:
            self.json_reply(400, {"error": str(e)})
            return
        try:
            if self.path == "/api/missions":
                self.launch(data)
                return
            m = ACTION.fullmatch(self.path)
            if not m:
                self.json_reply(404, {"error": "Action inconnue."})
                return
            mid, action = m.groups()
            if action == "cancel":
                r = self.cli("mission", "cancel", mid)
                self.json_reply(200 if r.returncode == 0 else 409,
                                {"ok": r.returncode == 0, "message": (r.stdout or r.stderr).strip()})
            elif action == "resume":
                _, proc, lines = self.spawn("mission", "resume", mid)
                self.json_reply(202, {"ok": True, "mission": mid, "running": proc.poll() is None,
                                      "lines": lines})
            else:
                call, verdict = str(data.get("call", "")), data.get("as")
                if not CALL_ID.fullmatch(call) or verdict not in {"done", "not-done"}:
                    self.json_reply(400, {"error": "appel et décision (done / not-done) requis"})
                    return
                r = self.cli("mission", "resolve", mid, "--call", call, "--as", verdict,
                             "--by", "console")
                if r.returncode != 0:
                    self.json_reply(409, {"ok": False, "message": (r.stderr or r.stdout).strip()})
                    return
                _, proc, lines = self.spawn("mission", "resume", mid)
                self.json_reply(202, {"ok": True, "mission": mid, "message": r.stdout.strip(),
                                      "lines": lines})
        except (OSError, subprocess.SubprocessError) as e:
            self.json_reply(503, {"error": f"Agent Core indisponible : {e}"})

    def launch(self, data):
        goal = str(data.get("goal", "")).strip()
        source = data.get("input") or (self.server.inputs[0] if self.server.inputs else None)
        if not 3 <= len(goal) <= 2000:
            self.json_reply(400, {"error": "Consigne de 3 à 2000 caractères."})
            return
        if source not in self.server.inputs:
            self.json_reply(400, {"error": "Dossier non autorisé pour cette console."})
            return
        self.server.children[:] = [p for p in self.server.children if p.poll() is None]
        if self.server.children:
            self.json_reply(409, {"error": "Une mission lancée depuis la console est déjà en cours."})
            return
        mid, proc, lines = self.spawn("mission", "run", "--input", source, "--goal", goal)
        if not mid:
            self.json_reply(502, {"error": "Lancement refusé par Agent Core.", "lines": lines})
            return
        self.json_reply(202, {"ok": True, "mission": mid, "running": proc.poll() is None})


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agentcore", default="agentcore")
    parser.add_argument("--config")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--input-autorise", action="append", default=[],
                        help="dossier d'entrée autorisé pour lancer une mission (répétable)")
    parser.add_argument("--recette-dir", default="~/recette")
    args = parser.parse_args()
    inputs = [str(Path(p).resolve()) for p in args.input_autorise]
    if not inputs:
        demo = Path(shutil.which(args.agentcore) or args.agentcore).resolve().with_name("demo")
        inputs = [str(demo)] if demo.is_dir() else []
    with ThreadingHTTPServer(("127.0.0.1", args.port), Console) as server:
        server.agentcore = [args.agentcore] + (["--config", args.config] if args.config else [])
        server.token = secrets.token_urlsafe(24)
        server.inputs = inputs
        server.recette_dir = args.recette_dir
        server.cpu = Cpu()
        server.children = []
        print(f"Console Agent Core · http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Dossiers autorisés pour lancer : {', '.join(inputs) or 'aucun'}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
