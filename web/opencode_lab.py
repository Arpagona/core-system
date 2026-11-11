"""Premier essai OpenCode sur un exemple synthétique."""

import difflib
import json
import os
import operator
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

SOURCE = "def total(quantity, unit_price):\n    return quantity - unit_price\n"
EXPRESSION = re.compile(r"quantity ([+*\-]) unit_price")
CASES = ((3, 7, 21), (0, 19, 0), (1, 9, 9))
PROMPT = (
    "Corrige la fonction Python total ci-dessous. Elle doit retourner le prix total "
    "pour une quantité et un prix unitaire. Réponds uniquement par l'expression Python "
    "à mettre après return, sur une seule ligne, en conservant les noms et leur ordre.\n\n"
    + SOURCE
)


def verify_proposal(output):
    parts = []
    for line in output.splitlines():
        event = json.loads(line)
        if event.get("type") == "error":
            raise ValueError("OpenCode a signalé une erreur. Vérifier le modèle et son accès.")
        if event.get("type") == "text":
            parts.append(event["part"]["text"])
    expression = "".join(parts).strip()
    match = EXPRESSION.fullmatch(expression)
    if not match:
        raise ValueError("OpenCode n’a pas fourni une expression au format attendu.")
    candidate = f"def total(quantity, unit_price):\n    return {expression}\n"
    diff = "".join(difflib.unified_diff(
        SOURCE.splitlines(keepends=True), candidate.splitlines(keepends=True),
        fromfile="a/order.py", tofile="b/order.py",
    ))
    operation = {"+": operator.add, "*": operator.mul, "-": operator.sub}[match[1]]
    tests = []
    for quantity, price, expected in CASES:
        actual = operation(quantity, price)
        tests.append({"quantity": quantity, "price": price,
                      "expected": expected, "actual": actual, "passed": actual == expected})
    return {"state": "passed" if all(t["passed"] for t in tests) else "failed",
            "diff": diff, "tests": tests}


class OpenCodeLab:
    def __init__(self, executable, model, key_env):
        self.executable = str(Path(executable).resolve()) if executable else None
        self.model = model
        self.key_env = key_env
        self.sandbox = shutil.which("bwrap")
        self.lock = threading.Lock()
        self.result = {"state": "idle"}

    def configured(self):
        return bool(self.executable and Path(self.executable).is_file()
                    and os.access(self.executable, os.X_OK)
                    and self.sandbox and self.model and self.key_env
                    and os.environ.get(self.key_env))

    def status(self):
        with self.lock:
            return {"configured": self.configured(), **self.result}

    def start(self):
        with self.lock:
            if self.result["state"] == "running":
                return 409, {"error": "Un essai OpenCode est déjà en cours."}
            if not self.configured():
                return 503, {"error": "Configurer OpenCode, le modèle, sa clé dédiée et bubblewrap."}
            self.result = {"state": "running"}
            threading.Thread(target=self.run, daemon=True).start()
        return 202, {"state": "running"}

    def run(self):
        try:
            result = verify_proposal(self.request())
        except subprocess.TimeoutExpired:
            result = {"state": "failed", "error": "Délai OpenCode dépassé (90 secondes)."}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            message = str(error) if type(error) is ValueError else "Sortie OpenCode illisible."
            result = {"state": "failed", "error": message}
        with self.lock:
            self.result = result

    def config(self):
        return {
            "permission": {"*": "deny"},
            "agent": {"build": {"steps": 1}},
        }

    def request(self):
        command = [
            self.sandbox, "--unshare-all", "--share-net", "--die-with-parent",
            "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind-try", "/lib", "/lib", "--ro-bind-try", "/lib64", "/lib64",
            "--ro-bind-try", "/etc/ssl/certs", "/etc/ssl/certs",
            "--ro-bind-try", "/etc/resolv.conf", "/etc/resolv.conf",
            "--ro-bind", self.executable, "/opencode",
            "--dev", "/dev", "--proc", "/proc",
            "--tmpfs", "/tmp", "--tmpfs", "/work",
            "--chdir", "/work", "--setenv", "HOME", "/work",
            "--setenv", "PATH", "/usr/bin",
            "--setenv", "OPENCODE_CONFIG_CONTENT",
            json.dumps(self.config()),
            "--setenv", "OPENCODE_DISABLE_AUTOUPDATE", "true",
            "--setenv", "OPENCODE_DISABLE_DEFAULT_PLUGINS", "true",
            "/opencode", "run", "--format", "json", "--model", self.model, "--title", "Essai Arpagona", PROMPT,
        ]
        with tempfile.TemporaryFile() as output:
            process = subprocess.run(command, env={self.key_env: os.environ[self.key_env]},
                                     stdin=subprocess.DEVNULL, stdout=output,
                                     stderr=subprocess.DEVNULL, timeout=90, check=False)
            if process.returncode:
                raise ValueError("OpenCode ou son isolation a échoué. Vérifier l’installation du serveur.")
            output.seek(0)
            data = output.read(65_537)
        if len(data) > 65_536:
            raise ValueError("La sortie OpenCode dépasse la taille admise pour cet essai.")
        return data.decode()
