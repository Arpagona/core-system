#!/usr/bin/env python3
"""Recette d'isolation des agents personnels sur le banc (à lancer en root sur la VM).

    sudo python3 /opt/arpagona/current/tests/e2e/isolation_agents.py [--live] [--json rapport.json]

Preuves : permissions Unix réelles (sudo -u mael / agent-mael / agent-thibaud), jetons croisés refusés
sur le moteur, la passerelle Kanban et le portier Hindsight, brouillon dans la seule boîte du bon
utilisateur, Kanban et décisions filtrés par propriétaire. --live ajoute un vrai tour de conversation
par le modèle (coût minime, données fictives). Aucune donnée réelle, aucun secret affiché.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

USERS = {"mael": {"engine": 8652, "bridge": 8702, "gate": 18911},
         "thibaud": {"engine": 8653, "bridge": 8703, "gate": 18912}}
RESULTS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"test": name, "ok": bool(ok), "detail": detail})
    print(("OK    " if ok else "ÉCHEC ") + name + (f" — {detail}" if detail else ""))


def sh(user: str | None, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
    args = ["sudo", "-n", "-u", user, "bash", "-c", command] if user else ["bash", "-c", command]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def http(method: str, url: str, token: str | None = None, body: dict | None = None,
         headers: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def home(login: str) -> str:
    return f"/srv/agents/{login}"


def secret(login: str, name: str) -> str:
    return Path(home(login), ".hermes", name).read_text().strip()


def denied(user: str, command: str) -> bool:
    proc = sh(user, command)
    return proc.returncode != 0


def unix_isolation() -> None:
    # Cibles sensibles de chaque utilisateur, du point de vue de l'autre.
    targets = lambda who: [  # noqa: E731
        f"{home(who)}/.hermes/.env", f"{home(who)}/.hermes/config.yaml", f"{home(who)}/.hermes/kanban.db",
        f"{home(who)}/.hermes/state.db", f"{home(who)}/.hermes/hindsight/config.json",
        f"{home(who)}/.hermes/hindsight_gate_token", f"{home(who)}/.hermes/skills/perso/gestion-mail/SKILL.md",
        f"{home(who)}/mail/INBOX/new/001-devis"]
    for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
        for target in targets(other):
            check(f"agent-{me} ne lit pas {target}", denied(f"agent-{me}", f"cat '{target}' >/dev/null"))
        check(f"agent-{me} ne liste pas la boîte de {other}", denied(f"agent-{me}", f"ls {home(other)}/mail"))
        check(f"agent-{me} n'écrit pas dans les brouillons de {other}",
              denied(f"agent-{me}", f"touch {home(other)}/mail/Drafts/cur/intrus"))
        check(f"agent-{me} n'écrit pas dans la mémoire/Kanban de {other}",
              denied(f"agent-{me}", f"touch {home(other)}/.hermes/kanban.db-intrus"))
    # Le compte humain de Maël (sans sudo) : rien chez Thibaud, rien chez l'agent de Thibaud, pas de sudo.
    if sh(None, "id mael").returncode == 0:
        check("mael (humain) sans sudo", sh("mael", "sudo -n true").returncode != 0)
        for who in ("thibaud", "mael"):
            check(f"mael (humain) ne lit pas la boîte de l'agent {who}", denied("mael", f"ls {home(who)}/mail"))
            check(f"mael (humain) ne lit pas l'état de l'agent {who}", denied("mael", f"cat {home(who)}/.hermes/.env"))
    # Secrets communs et Hermès commun.
    for me in ("mael", "thibaud"):
        for target in ("/srv/hermes-arpagona/.hermes/.env", "/srv/hermes-arpagona/.hermes/kanban.db",
                       "/etc/arpagona-api/agents.json", "/etc/arpagona-api/service_token",
                       "/etc/hindsight-gate/upstream_key", "/etc/hindsight-arpagona/api.env",
                       "/var/lib/arpagona-api/arpagona.db"):
            check(f"agent-{me} ne lit pas {target}", denied(f"agent-{me}", f"cat '{target}' >/dev/null"))
        # Socle partagé en lecture seule.
        check(f"agent-{me} lit le code Hermès partagé",
              sh(f"agent-{me}", "head -c1 /srv/hermes-arpagona/.hermes/hermes-agent/run_agent.py").returncode == 0)
        check(f"agent-{me} n'écrit pas dans le code Hermès partagé",
              denied(f"agent-{me}", "touch /srv/hermes-arpagona/.hermes/hermes-agent/intrus"))
        check(f"agent-{me} n'écrit pas dans les plugins partagés",
              denied(f"agent-{me}", "touch /opt/arpagona/shared-plugins/intrus /opt/arpagona/current/plugins/intrus"))
        check(f"agent-{me} ne liste pas l'Hermès commun",
              denied(f"agent-{me}", "ls /srv/hermes-arpagona/.hermes"))
    # Modes des secrets.
    for who in USERS:
        for name in (".env", "api_server_key", "arpagona_kanban_token", "arpagona_service_token", "hindsight_gate_token"):
            st = os.stat(Path(home(who), ".hermes", name))
            check(f"{who}/{name} en 0600, propriété de agent-{who}",
                  oct(st.st_mode & 0o777) == "0o600" and st.st_uid == int(sh(None, f"id -u agent-{who}").stdout))
        check(f"{who} : maison et boîte en 0700", all(oct(os.stat(p).st_mode & 0o777) == "0o700"
              for p in (home(who), f"{home(who)}/.hermes", f"{home(who)}/mail")))


def network_isolation() -> None:
    for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
        own, theirs = USERS[me], USERS[other]
        key = secret(me, "api_server_key")
        check(f"moteur {me} : clé propre acceptée", http("GET", f"http://127.0.0.1:{own['engine']}/v1/health")[0] == 200)
        check(f"moteur {other} refuse la clé de {me}",
              http("POST", f"http://127.0.0.1:{theirs['engine']}/v1/runs", key, {"input": "x"})[0] == 401)
        check(f"moteur {other} refuse sans clé",
              http("POST", f"http://127.0.0.1:{theirs['engine']}/v1/runs", None, {"input": "x"})[0] == 401)
        ktoken = secret(me, "arpagona_kanban_token")
        status, _ = http("POST", f"http://127.0.0.1:{theirs['bridge']}/kanban/list", None, {},
                         {"X-Arpagona-Service": ktoken})
        check(f"passerelle Kanban {other} refuse le jeton de {me}", status == 401)
        gtoken = secret(me, "hindsight_gate_token")
        base = f"http://127.0.0.1:{own['gate']}"
        # 200 si la banque existe déjà, 404 si elle n'a encore rien reçu : dans les deux cas le portier a laissé passer.
        check(f"Hindsight : {me} atteint sa banque", http("GET", f"{base}/v1/default/banks/arpagona-{me}/stats", gtoken)[0] in (200, 404))
        for path in (f"/v1/default/banks/arpagona-{other}/stats", "/v1/default/banks",
                     f"/v1/default/banks/arpagona-{me}/../arpagona-{other}/stats",
                     f"/v1/default/banks/arpagona-{me}%2f..%2farpagona-{other}/stats"):
            check(f"Hindsight : {me} refusé sur {path}", http("GET", base + path, gtoken)[0] == 403)
        check(f"Hindsight : portier de {other} refuse le jeton de {me}",
              http("GET", f"http://127.0.0.1:{theirs['gate']}/v1/default/banks/arpagona-{other}/stats", gtoken)[0] == 401)
        check("Hindsight : accès direct sans clé amont refusé",
              http("GET", "http://127.0.0.1:18897/v1/default/banks/arpagona-" + me + "/stats", gtoken)[0] in (401, 403))


def mail_isolation(live: bool) -> None:
    plugin = "/opt/arpagona/current/plugins/arpagona-mail/__init__.py"
    script = (
        "import importlib.util,json,sys;"
        f"s=importlib.util.spec_from_file_location('m','{plugin}');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "print(m.draft({'a':'client-fictif@exemple.invalid','sujet':'Isolation CANARI-BROUILLON-%s','corps':'corps %s'}))")
    for who in USERS:
        env = (f"ARPAGONA_MAIL_DIR={home(who)}/mail ARPAGONA_MAIL_ADDRESS={who}@banc.invalid "
               f"python3 -c \"{script % (who.upper(), who)}\"")
        out = sh(f"agent-{who}", env)
        check(f"brouillon créé par l'outil de {who}", out.returncode == 0 and '"brouillon-non-envoye"' in out.stdout,
              out.stderr.strip()[:120])
    for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
        mine = sh(f"agent-{who}", f"grep -rl 'CANARI-BROUILLON-{who.upper()}' {home(who)}/mail/Drafts").stdout.split()
        check(f"brouillon de {who} visible dans la boîte de {who}", len(mine) >= 1, f"{len(mine)} fichier(s)")
        leaks = subprocess.run(["grep", "-rl", f"CANARI-BROUILLON-{who.upper()}", "/srv/agents", "/srv/hermes-arpagona/.hermes/kanban.db"],
                               capture_output=True, text=True).stdout.split()
        outside = [p for p in leaks if not p.startswith(f"{home(who)}/mail/Drafts/")]
        check(f"brouillon de {who} absent de tout autre emplacement (autre boîte, Kanban, état)", not outside, ", ".join(outside)[:160])
        check(f"agent de {other} ne lit pas les messages de {who}",
              "CANARI-MAIL-" + who.upper() not in sh(f"agent-{other}", f"cat {home(who)}/mail/INBOX/new/* 2>&1").stdout)
    if live:
        key = secret("mael", "api_server_key")
        sid = f"isolation-{int(time.time())}"
        canary = f"CANARI-LIVE-MAEL-{sid[-10:]}"  # unique par exécution : la recette est rejouable
        status, raw = http("POST", f"http://127.0.0.1:{USERS['mael']['engine']}/v1/runs", key, {
            "input": "Avec arpagona_mail_draft, dépose un brouillon à client-fictif@exemple.invalid, sujet "
                     f"\"{canary}\", corps \"Test d'isolation\". Réponds OK.", "session_id": sid},
            {"Idempotency-Key": sid})
        run = json.loads(raw)["run_id"] if status == 202 else ""
        state = ""
        for _ in range(40):
            time.sleep(4)
            st, body = http("GET", f"http://127.0.0.1:{USERS['mael']['engine']}/v1/runs/{run}", key)
            state = json.loads(body).get("status", "") if st == 200 else ""
            if state in ("completed", "failed", "cancelled"):
                break
        found = subprocess.run(["grep", "-rl", canary, "/srv/agents"], capture_output=True, text=True).stdout.split()
        in_mael = [p for p in found if p.startswith(f"{home('mael')}/mail/Drafts/")]
        elsewhere = [p for p in found if not p.startswith(f"{home('mael')}/")]
        check("run réel : l'agent de Maël crée le brouillon dans la boîte de Maël", state == "completed" and len(in_mael) == 1, state)
        check("run réel : rien chez Thibaud", not elsewhere and not any(p.startswith(home("thibaud")) for p in found))


def api_isolation(live: bool) -> None:
    """Instance d'API jetable (copie de la base, port 8790) : même code, mêmes agents, mots de passe de test."""
    tmp = Path("/tmp/isolation-api")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for suffix in ("", "-wal", "-shm"):
        src = Path(f"/var/lib/arpagona-api/arpagona.db{suffix}")
        if src.exists():
            shutil.copy(src, tmp / f"arpagona.db{suffix}")
    subprocess.run(["chown", "-R", "arpagona-api:arpagona-api", str(tmp)], check=True)
    os.chmod(tmp, 0o700)
    base_env = ("ARPAGONA_DB=/tmp/isolation-api/arpagona.db cd /opt/arpagona/current/services/arpagona-api && ")
    pw = {"mael": "mdp-test-isolation-mael-1", "thibaud": "mdp-test-isolation-thibaud-1"}
    for login, password in pw.items():
        proc = subprocess.run(["sudo", "-n", "-u", "arpagona-api", "bash", "-c",
                               base_env + f"ARPAGONA_DB=/tmp/isolation-api/arpagona.db python3 -m arpagona_api.manage set-password {login} --password-stdin"],
                              input=password + "\n", capture_output=True, text=True)
        if proc.returncode:
            check(f"mot de passe de test pour {login}", False, proc.stderr[:100])
            return
    env = ("ARPAGONA_DB=/tmp/isolation-api/arpagona.db ARPAGONA_PORT=8790 ARPAGONA_BIND=127.0.0.1 "
           "ARPAGONA_HERMES_KEY_FILE=/etc/arpagona-api/hermes_key ARPAGONA_SERVICE_TOKEN_FILE=/etc/arpagona-api/service_token "
           "ARPAGONA_AGENTS_FILE=/etc/arpagona-api/agents.json ARPAGONA_TRIGGER_INTERVAL=100000 "
           "ARPAGONA_STATIC_DIR=/opt/arpagona/current/apps/mission-control-web")
    server = subprocess.Popen(["sudo", "-n", "-u", "arpagona-api", "bash", "-c",
                               f"cd /opt/arpagona/current/services/arpagona-api && {env} exec python3 -m arpagona_api.server"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            time.sleep(1)
            if http("GET", "http://127.0.0.1:8790/api/health")[0] == 200:
                break
        cookies = {}

        def call(login, method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request("http://127.0.0.1:8790" + path, data=data, method=method)
            req.add_header("X-Arpagona", "1")
            if data:
                req.add_header("Content-Type", "application/json")
            if login in cookies:
                req.add_header("Cookie", cookies[login])
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    cookie = resp.headers.get("Set-Cookie")
                    if cookie:
                        cookies[login] = cookie.split(";")[0]
                    return resp.status, resp.read().decode()
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read().decode()

        for login, password in pw.items():
            check(f"connexion MC {login}", call(login, "POST", "/api/login", {"login": login, "password": password})[0] == 200)
        titles = {}
        for login in pw:
            status, raw = call(login, "GET", "/api/kanban/list")
            titles[login] = [c.get("title", "") for c in json.loads(raw)] if status == 200 else None
            check(f"Kanban MC de {login} lisible", status == 200)
        for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
            mine, theirs = titles[me] or [], titles[other] or []
            check(f"Kanban de {me} : ses cartes seulement",
                  any(f"[{me.upper()}]" in t for t in mine) and not any(f"[{other.upper()}]" in t for t in mine), str(mine)[:140])
        # Décisions : cartes bloquées routées vers le bon compte.
        for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
            status, raw = call(me, "GET", "/api/kanban/list")
            blocked = [c for c in json.loads(raw) if c.get("status") == "blocked"]
            ok = blocked and all(f"{me.upper()}-4417" in json.dumps(c, ensure_ascii=False) for c in blocked) \
                and not any(f"{other.upper()}-4417" in json.dumps(c, ensure_ascii=False) for c in blocked)
            check(f"décision en attente routée vers {me} seulement", bool(ok), f"{len(blocked)} carte(s) bloquée(s)")
        # Carte créée par Maël : seulement dans le Kanban de Maël.
        card = f"[MAEL] carte de recette {int(time.time())}"
        check("création de carte par mael", call("mael", "POST", "/api/kanban/create", {"title": card})[0] == 200)
        _, raw_t = call("thibaud", "GET", "/api/kanban/list")
        _, raw_m = call("mael", "GET", "/api/kanban/list")
        check("carte créée par mael visible chez mael seulement", card in raw_m and card not in raw_t)
        # Carte de l'autre : identifiants inconnus, refus.
        other_id = next((c["id"] for c in json.loads(raw_t) if "THIBAUD" in c.get("title", "")), "")
        status, _ = call("mael", "POST", "/api/kanban/comment", {"id": other_id, "text": "intrusion"})
        check("mael ne commente pas une carte de thibaud", status in (400, 502) and other_id != "", f"HTTP {status}")
        status, _ = call("mael", "POST", "/api/kanban/complete", {"id": other_id})
        check("mael ne termine pas une carte de thibaud", status in (400, 502), f"HTTP {status}")
        _, raw_t2 = call("thibaud", "GET", "/api/kanban/list")
        check("la carte de thibaud est intacte", "intrusion" not in raw_t2 and
              any(c["id"] == other_id and c.get("status") != "done" for c in json.loads(raw_t2)))
        # Jeton d'outils de l'un, session de l'autre.
        stoken = secret("thibaud", "arpagona_service_token")
        import sqlite3
        call("mael", "GET", "/api/conversation")  # ouvre la conversation de mael (session moteur)
        db = sqlite3.connect("file:/tmp/isolation-api/arpagona.db?mode=ro", uri=True)
        row = db.execute("SELECT hermes_session_id FROM conversations c JOIN users u ON u.id=c.user_id WHERE u.login='mael' LIMIT 1").fetchone()
        if row:
            st, _ = http("GET", "http://127.0.0.1:8790/internal/engagements", None, None,
                         {"X-Arpagona-Service": stoken, "X-Hermes-Session": row[0]})
            check("l'agent de thibaud ne peut pas agir sur une session de mael", st == 401, f"HTTP {st}")
        status, _ = http("GET", "http://127.0.0.1:8790/internal/engagements", None, None,
                         {"X-Arpagona-Service": Path("/etc/arpagona-api/service_token").read_text().strip(),
                          "X-Hermes-Session": row[0] if row else "x"})
        check("l'ancien jeton commun est refusé", status == 401, f"HTTP {status}")
        if live:
            status, raw = call("mael", "POST", "/api/chat", {"text": "Réponds seulement : bonjour."})
            check("chat MC de mael : réponse de son agent", status == 200 and '"status": "done"' in raw.replace('":"', '": "'), f"HTTP {status}")
            sessions_m = sh("agent-mael", f"HERMES_HOME={home('mael')}/.hermes python3 - <<'PY'\nimport sqlite3\nd=sqlite3.connect('file:{home('mael')}/.hermes/state.db?mode=ro',uri=True)\nprint(d.execute('select count(*) from sessions').fetchone()[0])\nPY")
            sessions_t = sh("agent-thibaud", f"python3 - <<'PY'\nimport sqlite3\nd=sqlite3.connect('file:{home('thibaud')}/.hermes/state.db?mode=ro',uri=True)\nprint(d.execute('select count(*) from sessions').fetchone()[0])\nPY")
            check("la conversation de mael est dans l'état de mael, pas dans celui de thibaud",
                  sessions_m.stdout.strip().isdigit() and int(sessions_m.stdout) >= 1 and sessions_t.stdout.strip() in ("0", ""),
                  f"mael={sessions_m.stdout.strip()} thibaud={sessions_t.stdout.strip() or sessions_t.stderr.strip()[:60]}")
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="inclut un vrai tour de modèle")
    parser.add_argument("--json")
    args = parser.parse_args()
    if os.geteuid() != 0:
        sys.exit("à lancer en root")
    unix_isolation()
    network_isolation()
    mail_isolation(args.live)
    api_isolation(args.live)
    failed = [r for r in RESULTS if not r["ok"]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} contrôles réussis")
    if args.json:
        Path(args.json).write_text(json.dumps({"total": len(RESULTS), "failed": len(failed), "results": RESULTS},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
