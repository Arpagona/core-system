#!/usr/bin/env python3
"""Recette de bout en bout sur le banc réel (à lancer en root sur la VM de test).

Chaque contrôle parle aux vrais services : API ARPAGONA, Hermès, modèle. Rien n'est simulé.
Les comptes utilisés sont créés pour l'occasion, avec des données fictives, puis supprimés.

Sortie : un tableau lisible, un fichier JSON (--json), code de retour 0 si tout passe.
Un contrôle « modèle » qui échoue peut tenir au modèle et non au code : le détail est conservé.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.parse

RESULTS: list[dict] = []


def check(ident: str, label: str, ok: bool, detail: str = "", kind: str = "déterministe") -> bool:
    RESULTS.append({"id": ident, "contrôle": label, "résultat": "réussi" if ok else "ÉCHEC",
                    "nature": kind, "détail": detail[:300]})
    print(f"[{'ok' if ok else 'ÉCHEC':5}] {ident} {label}" + (f" — {detail[:160]}" if detail and not ok else ""))
    return ok


class Session:
    def __init__(self, base: str):
        url = urllib.parse.urlparse(base)
        self.host, self.port = url.hostname, url.port
        self.cookie = None

    def call(self, method: str, path: str, body: dict | None = None, headers: dict | None = None,
             timeout: float = 30.0) -> tuple[int, str]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        hdrs = {"X-Arpagona": "1"}
        if body is not None:
            hdrs["Content-Type"] = "application/json"
        if self.cookie:
            hdrs["Cookie"] = self.cookie
        hdrs.update(headers or {})
        conn.request(method, path, json.dumps(body) if body is not None else None, hdrs)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        cookie = resp.getheader("Set-Cookie")
        if cookie:
            self.cookie = cookie.split(";")[0]
        conn.close()
        return resp.status, raw

    def login(self, login: str, password: str) -> int:
        return self.call("POST", "/api/login", {"login": login, "password": password})[0]

    def chat(self, text: str, timeout: float = 240.0) -> dict:
        """Envoie un message et attend la fin du flux. Renvoie l'événement final."""
        status, raw = self.call("POST", "/api/chat", {"text": text}, timeout=timeout)
        if status != 200:
            return {"status": f"http {status}", "text": raw[:200]}
        events = [json.loads(block[6:]) for block in raw.split("\n\n") if block.startswith("data: ")]
        end = next((e for e in events if e.get("type") == "end"), {"status": "sans fin", "text": ""})
        end["deltas"] = sum(1 for e in events if e.get("type") == "delta")
        end["tools"] = sorted({e.get("name", "") for e in events if e.get("type") == "tool"})
        return end


def manage(args_ns, *cmd: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {"ARPAGONA_DB": args_ns.db, "PYTHONPATH": args_ns.service_dir, "PATH": "/usr/bin:/bin"}
    return subprocess.run(["sudo", "-u", "arpagona-api", "env", *[f"{k}={v}" for k, v in env.items()],
                           "python3", "-m", "arpagona_api.manage", *cmd],
                          input=stdin, capture_output=True, text=True, cwd=args_ns.service_dir, timeout=60)


def raw_status(base: str, method: str, path: str, headers: dict | None = None, body: dict | None = None) -> int:
    url = urllib.parse.urlparse(base)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=15)
    hdrs = dict(headers or {})
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    conn.request(method, path, json.dumps(body) if body is not None else None, hdrs)
    status = conn.getresponse().status
    conn.close()
    return status


def read_secret(path: str) -> str:
    try:
        with open(path, encoding="ascii") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8700")
    parser.add_argument("--hermes", default="http://127.0.0.1:8642")
    parser.add_argument("--db", default="/var/lib/arpagona-api/arpagona.db")
    parser.add_argument("--service-dir", default="/opt/arpagona/current/services/arpagona-api")
    parser.add_argument("--hermes-env", default="/srv/hermes-arpagona/.hermes/.env")
    parser.add_argument("--service-token", default="/etc/arpagona-api/service_token")
    parser.add_argument("--json", default="")
    parser.add_argument("--skip-restart", action="store_true", help="ne pas redémarrer les services")
    ns = parser.parse_args()
    if os.geteuid() != 0:
        print("à lancer en root sur la VM de test", file=sys.stderr)
        return 2

    tag = secrets.token_hex(3)
    user_a, user_b = f"recette-a-{tag}", f"recette-b-{tag}"
    pw_a, pw_b = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    code = "ZEPHYR-" + secrets.token_hex(3).upper()
    started = time.time()
    try:
        ok_a = manage(ns, "add-user", user_a, "--name", "Recette A", "--password-stdin", stdin=pw_a + "\n")
        ok_b = manage(ns, "add-user", user_b, "--name", "Recette B", "--password-stdin", stdin=pw_b + "\n")
        if not check("P0", "comptes de recette créés", ok_a.returncode == 0 and ok_b.returncode == 0,
                     (ok_a.stderr + ok_b.stderr)):
            return 1

        # --- surface exposée -------------------------------------------------
        anon = Session(ns.api)
        check("S1", "API ARPAGONA en vie", anon.call("GET", "/api/health")[0] == 200)
        check("S2", "conversation refusée sans session", anon.call("GET", "/api/conversation")[0] == 401)
        check("S3", "chat refusé sans session", anon.call("POST", "/api/chat", {"text": "x"})[0] == 401)
        check("S4", "API Hermès refusée sans clé", raw_status(ns.hermes, "POST", "/v1/runs", body={}) == 401)
        check("S5", "mauvais mot de passe refusé", Session(ns.api).login(user_a, "mauvais-mot-de-passe") == 401)

        # --- routes internes ---------------------------------------------------
        hermes_key = ""
        try:
            with open(ns.hermes_env, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("API_SERVER_KEY="):
                        hermes_key = line.split("=", 1)[1].strip()
        except OSError:
            pass
        service_token = read_secret(ns.service_token)
        check("I1", "route interne refusée sans jeton",
              raw_status(ns.api, "GET", "/internal/engagements", {"X-Hermes-Session": "x"}) == 401)
        check("I2", "jeton de service distinct de la clé Hermès",
              bool(service_token) and bool(hermes_key) and service_token != hermes_key)
        check("I3", "la clé Hermès n'ouvre pas les routes internes",
              raw_status(ns.api, "GET", "/internal/engagements",
                         {"X-Arpagona-Service": hermes_key, "X-Hermes-Session": "x"}) == 401)
        check("I4", "jeton valide mais session inconnue refusé",
              raw_status(ns.api, "GET", "/internal/engagements",
                         {"X-Arpagona-Service": service_token, "X-Hermes-Session": "inconnue"}) == 401)

        # --- politique d'outils ------------------------------------------------
        tools = subprocess.run(
            ["sudo", "-u", "hermes-arpagona", "-H", "bash", "-lc",
             "export PATH=$HOME/.local/bin:$PATH; hermes tools list --platform api_server"],
            capture_output=True, text=True, timeout=60).stdout
        enabled = sorted(line.split()[2] for line in tools.splitlines()
                         if "enabled" in line and "disabled" not in line and len(line.split()) > 2)
        allowed = {"web", "todo", "arpagona"}
        check("O1", "outils du canal API limités à la liste permise",
              bool(enabled) and set(enabled) <= allowed, "actifs : " + ", ".join(enabled))

        # --- chat réel -----------------------------------------------------------
        a, b = Session(ns.api), Session(ns.api)
        check("C1", "connexion du compte A", a.login(user_a, pw_a) == 200)
        check("C2", "connexion du compte B", b.login(user_b, pw_b) == 200)
        first = a.chat(f"Pour la suite de notre travail, le nom de code du projet est {code}. "
                       "Retiens-le durablement. Réponds seulement : noté.")
        check("C3", "réponse réelle du moteur, reçue en flux",
              first.get("status") == "done" and first.get("deltas", 0) > 0, json.dumps(first)[:200], "modèle")
        recall = a.chat("Quel est le nom de code du projet ? Réponds par le code seul.")
        check("C4", "le compte A retrouve son propre contexte", code in recall.get("text", ""),
              recall.get("text", ""), "modèle")

        # --- isolation entre comptes ------------------------------------------------
        probe = b.chat("Quel est le nom de code du projet ? Cherche dans ta mémoire et dans toutes les "
                       "conversations passées auxquelles tu as accès. Si tu ne trouves rien, réponds exactement : INCONNU.")
        check("X1", "le compte B ne retrouve pas le secret du compte A",
              probe.get("status") == "done" and code not in probe.get("text", ""),
              f"outils : {probe.get('tools')} ; réponse : {probe.get('text', '')}", "modèle")
        conv_b = json.loads(b.call("GET", "/api/conversation")[1])
        check("X2", "la conversation de B ne contient aucun message de A",
              code not in json.dumps(conv_b, ensure_ascii=False))

        # --- engagement réel -----------------------------------------------------------
        due = time.strftime("%Y-%m-%dT09:00:00+01:00", time.gmtime(time.time() + 3 * 86400))
        a.chat(f"Pour le client fictif Martin-{tag}, on a décidé de le relancer le {due} au sujet de la commande. "
               "Consigne cet engagement.")
        eng_a = json.loads(a.call("GET", "/api/engagements")[1]).get("engagements", [])
        eng_b = json.loads(b.call("GET", "/api/engagements")[1]).get("engagements", [])
        mine = [e for e in eng_a if f"Martin-{tag}" in e["client"]]
        check("E1", "l'agent consigne l'engagement avec date absolue",
              len(mine) == 1 and mine[0]["statut"] == "planifie" and mine[0]["fuseau"] == "+0100",
              json.dumps(eng_a, ensure_ascii=False)[:250], "modèle")
        check("E2", "l'engagement de A est invisible pour B", eng_b == [])
        check("E3", "aucun brouillon avant l'échéance",
              json.loads(a.call("GET", "/api/drafts")[1]).get("drafts", []) == [])

        # --- persistance ------------------------------------------------------------------
        if not ns.skip_restart:
            subprocess.run(["systemctl", "restart", "arpagona-api.service"], check=False, timeout=60)
            subprocess.run(["systemctl", "restart", "hermes-arpagona-gateway.service"], check=False, timeout=90)
            deadline = time.time() + 60
            alive = False
            while time.time() < deadline and not alive:
                time.sleep(3)
                try:
                    alive = (raw_status(ns.api, "GET", "/api/health") == 200
                             and raw_status(ns.hermes, "GET", "/v1/health") == 200)
                except OSError:
                    alive = False
            check("R1", "les deux services reviennent après redémarrage", alive)
            conv_a = json.loads(a.call("GET", "/api/conversation")[1]).get("messages", [])
            check("R2", "session web et conversation conservées après redémarrage",
                  any(code in m["text"] for m in conv_a), f"{len(conv_a)} messages")
            eng_after = json.loads(a.call("GET", "/api/engagements")[1]).get("engagements", [])
            check("R3", "engagement conservé après redémarrage", len(eng_after) == len(eng_a))
            again = a.chat("Rappelle-moi le nom de code du projet. Réponds par le code seul.")
            check("R4", "le moteur reprend la même conversation après redémarrage",
                  code in again.get("text", ""), again.get("text", ""), "modèle")
    finally:
        for login in (user_a, user_b):
            manage(ns, "del-user", login)

    failed = [r for r in RESULTS if r["résultat"] != "réussi"]
    summary = {"date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "durée_s": round(time.time() - started),
               "total": len(RESULTS), "réussis": len(RESULTS) - len(failed), "échecs": len(failed),
               "contrôles": RESULTS}
    if ns.json:
        with open(ns.json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(f"\n{summary['réussis']}/{summary['total']} contrôles réussis en {summary['durée_s']} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
