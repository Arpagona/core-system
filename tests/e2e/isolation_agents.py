#!/usr/bin/env python3
"""Recette des deux zones sur le banc : espaces PERSONNELS privés, ENTREPRISE commune (à lancer en root sur la VM).

    sudo python3 /opt/arpagona/current/tests/e2e/isolation_agents.py [--live] [--json rapport.json]

Zone personnelle (privée) : permissions Unix réelles (sudo -u mael / agent-mael / agent-thibaud), jetons croisés
refusés sur le moteur et le portier Hindsight, brouillon dans la seule boîte du bon utilisateur, faits perso et
secrets fictifs introuvables par l'autre (rappel, API, fichiers).
Zone commune : fait métier d'équipe écrit par l'un et retrouvé par l'autre (avec auteur et source), dossiers clients
créés et modifiés dans les deux sens (droits des nouveaux fichiers, traversées et liens refusés), un seul Kanban
d'entreprise avec responsable par carte, décision visible mais approuvée par son seul responsable.
--live ajoute deux vrais tours de modèle (outils d'équipe) : coût minime, données fictives. Les fixtures créées
(faits, fichiers, cartes) sont retirées à la fin ; rien d'autre n'est supprimé. Aucune donnée réelle, aucun secret affiché.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

USERS = {"mael": {"engine": 8652, "gate": 18911}, "thibaud": {"engine": 8653, "gate": 18912}}
TEAM_BANK = "arpagona-equipe"
CLIENTS = "/srv/arpagona/clients"
UPSTREAM = "http://127.0.0.1:18897"
RUN = str(int(time.time()))  # fixtures uniques par exécution : la recette est rejouable
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
        for name in (".env", "api_server_key", "arpagona_service_token", "hindsight_gate_token"):
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
        gtoken = secret(me, "hindsight_gate_token")
        base = f"http://127.0.0.1:{own['gate']}"
        # 200 si la banque existe déjà, 404 si elle n'a encore rien reçu : dans les deux cas le portier a laissé passer.
        check(f"Hindsight : {me} atteint sa banque", http("GET", f"{base}/v1/default/banks/arpagona-{me}/stats", gtoken)[0] in (200, 404))
        check(f"Hindsight : {me} lit la banque d'équipe", http("GET", f"{base}/v1/default/banks/{TEAM_BANK}/stats", gtoken)[0] in (200, 404))
        for method, path in (("DELETE", f"/v1/default/banks/{TEAM_BANK}"), ("DELETE", f"/v1/default/banks/{TEAM_BANK}/memories"),
                             ("PUT", f"/v1/default/banks/{TEAM_BANK}"), ("POST", f"/v1/default/banks/{TEAM_BANK}/reflect")):
            check(f"Hindsight : {me} ne peut pas {method} {path.rsplit('/', 1)[-1]} sur la banque d'équipe",
                  http(method, base + path, gtoken, {})[0] == 403)
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
           "ARPAGONA_KANBAN_TOKEN_FILE=/etc/arpagona-api/kanban_token "
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
        # --- Kanban d'entreprise : un seul tableau, responsable par carte, décision au seul responsable ---
        lists = {}
        for login in pw:
            status, raw = call(login, "GET", "/api/kanban/list")
            lists[login] = json.loads(raw) if status == 200 else None
            check(f"Kanban d'entreprise lisible par {login}", status == 200)
        ids = {login: sorted(c["id"] for c in (lists[login] or [])) for login in pw}
        check("même tableau pour les deux comptes (mêmes cartes)", ids["mael"] == ids["thibaud"] and len(ids["mael"]) > 0,
              f"{len(ids['mael'])} carte(s)")
        check("aucun doublon de carte (identifiants uniques)", len(ids["mael"]) == len(set(ids["mael"])))
        titles_all = [c.get("title", "") for c in lists["mael"] or []]
        for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
            check(f"cartes de {me} et de {other} visibles des deux", any(f"[{me.upper()}]" in t for t in titles_all)
                  and any(f"[{other.upper()}]" in t for t in titles_all))
            status, raw = call(me, "GET", "/api/kanban/list?scope=mine")
            mine = json.loads(raw) if status == 200 else []
            check(f"« mes cartes » de {me} : seulement ses cartes", bool(mine) and all(c.get("assignee") == me for c in mine), f"{len(mine)} carte(s)")
            check(f"« toutes » cohérent : cartes de {me} = « mes cartes »", sorted(c["id"] for c in mine) ==
                  sorted(c["id"] for c in lists[me] if c.get("assignee") == me))
        demo = [c for c in lists["mael"] if "[DEMO]" in c.get("title", "")]
        check("cartes existantes de démonstration préservées (sans responsable)", len(demo) >= 1 and all(not c.get("assignee") for c in demo), f"{len(demo)} carte(s)")
        # Décisions : visibles de l'autre, mais seul le responsable décide.
        created: list[str] = []
        for me, other in (("mael", "thibaud"), ("thibaud", "mael")):
            title = f"[{me.upper()}] RECETTE-{RUN} décision à valider"
            status, raw = call(me, "POST", "/api/kanban/create", {"title": title, "body": "Décision fictive de recette."})
            card = json.loads(raw) if status == 200 else {}
            created.append(card.get("id", ""))
            check(f"{me} crée une carte : responsable = {me}, auteur = {me}",
                  status == 200 and card.get("assignee") == me and card.get("created_by") == me, f"HTTP {status}")
            call(me, "POST", "/api/kanban/block", {"id": card.get("id", ""), "text": "Décision attendue"})
            seen = [c for c in json.loads(call(other, "GET", "/api/kanban/list")[1]) if c["id"] == card.get("id")]
            check(f"décision de {me} visible de {other}", len(seen) == 1 and seen[0].get("assignee") == me and seen[0].get("mine") is False)
            for op in ("unblock", "complete", "archive"):
                status, _ = call(other, "POST", f"/api/kanban/{op}", {"id": card.get("id", "")})
                check(f"{other} ne peut pas « {op} » la décision de {me}", status == 403, f"HTTP {status}")
            status, _ = call(other, "POST", "/api/kanban/assign", {"id": card.get("id", ""), "assignee": other})
            check(f"{other} ne peut pas se réaffecter la décision de {me}", status == 403, f"HTTP {status}")
            status, _ = call(other, "POST", "/api/kanban/comment", {"id": card.get("id", ""), "text": f"avis de {other} (recette)"})
            check(f"{other} peut commenter la décision de {me} (visibilité commune)", status == 200, f"HTTP {status}")
            _, shown = call(me, "GET", f"/api/kanban/show?id={card.get('id', '')}")
            check(f"la décision de {me} est toujours bloquée et à {me}", json.loads(shown).get("task", {}).get("status") == "blocked"
                  if shown.startswith("{") else False)
            status, _ = call(me, "POST", "/api/kanban/unblock", {"id": card.get("id", "")})
            check(f"{me} (responsable) approuve sa décision", status == 200, f"HTTP {status}")
        status, _ = call("mael", "POST", "/api/kanban/create", {"title": f"RECETTE-{RUN} intrus", "assignee": "inconnu"})
        check("responsable hors équipe refusé", status == 400, f"HTTP {status}")
        for card_id in created:  # nettoyage : seulement les cartes de la recette (archivées par leur responsable)
            owner = next((c["assignee"] for c in json.loads(call("mael", "GET", "/api/kanban/list")[1]) if c["id"] == card_id), "")
            if owner:
                call(owner, "POST", "/api/kanban/archive", {"id": card_id})
        after = sorted(c["id"] for c in json.loads(call("mael", "GET", "/api/kanban/list")[1]))
        check("après nettoyage : tableau identique à l'état initial (aucune carte existante perdue)", after == ids["mael"], f"{len(after)} carte(s)")
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


def plugin_call(who: str, func: str, args: dict, umask: str = "077") -> dict:
    """Appelle un outil du plugin arpagona-equipe sous le compte Unix de l'agent, avec l'environnement de son service."""
    code = (
        "import importlib.util,json,sys;"
        "s=importlib.util.spec_from_file_location('e','/opt/arpagona/current/plugins/arpagona-equipe/__init__.py');"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        f"print(getattr(m,'{func}')(json.loads(sys.argv[1])))")
    env = f"set -a; . {home(who)}/.hermes/.env; set +a; umask {umask}; python3 -c {shlex.quote(code)} {shlex.quote(json.dumps(args))}"
    out = sh(f"agent-{who}", env, timeout=240)
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": "sortie illisible : " + (out.stderr or out.stdout)[:160]}


def upstream_key() -> str:
    return Path("/etc/hindsight-gate/upstream_key").read_text().strip()


def team_memory() -> None:
    """Mémoire d'équipe : écrite par l'un, retrouvée par l'autre (avec auteur et source) ; perso et secrets étanches."""
    facts = {"mael": f"Le client fictif ZORBA-{RUN} exige une livraison par lots de 50 pièces (recette deux zones).",
             "thibaud": f"Le client fictif QUILLON-{RUN} a validé le devis 2026-{RUN[-4:]} sous réserve d'un contrôle dimensionnel."}
    doc_ids = {who: f"recette-equipe-{who}-{RUN}" for who in USERS}
    personal = {"mael": f"PERSO-MAEL-{RUN}: Maël préfère les réponses en liste courte.",
                "thibaud": f"PERSO-THIBAUD-{RUN}: Thibaud lit ses mails le matin seulement."}
    secrets_ = {"mael": f"CANARI-SECRET-MAEL-{RUN}", "thibaud": f"CANARI-SECRET-THIBAUD-{RUN}"}
    personal_docs = {who: f"recette-perso-{who}-{RUN}" for who in USERS}
    try:
        for who in USERS:
            out = plugin_call(who, "team_remember", {"fait": facts[who], "source": f"recette deux zones {RUN}", "id": doc_ids[who]})
            check(f"{who} écrit un fait métier dans la mémoire d'équipe", out.get("zone") == "equipe", str(out)[:140])
        for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
            key = "ZORBA" if who == "mael" else "QUILLON"
            out = plugin_call(other, "team_recall", {"requete": f"client {key}-{RUN} exigences"})
            hits = [r for r in out.get("resultats", []) if f"{key}-{RUN}" in r.get("fait", "")]
            check(f"{other} retrouve depuis sa session le fait métier écrit par {who}", len(hits) >= 1, str(out)[:140])
            if hits:
                check(f"auteur et source conservés pour le fait de {who}",
                      hits[0].get("auteur") == who and RUN in hits[0].get("source", ""), f"auteur={hits[0].get('auteur')!r} source={hits[0].get('source')!r}")
        # Fait personnel et secret fictifs : déposés dans la banque PERSONNELLE de chacun, via son portier.
        for who in USERS:
            base = f"http://127.0.0.1:{USERS[who]['gate']}/v1/default/banks/arpagona-{who}/memories"
            for content, doc in ((personal[who], personal_docs[who]), (f"Mot de passe fictif du compte de {who} : {secrets_[who]}", personal_docs[who] + "-secret")):
                status, _ = http("POST", base, secret(who, "hindsight_gate_token"), {"items": [{"content": content, "document_id": doc}], "async": False})
                check(f"{who} écrit dans SA mémoire personnelle ({'secret' if 'secret' in doc else 'préférence'} fictif)", status == 200, f"HTTP {status}")
            out = plugin_call(who, "team_remember", {"fait": f"Mot de passe fictif {secrets_[who]}", "source": "recette"})
            check(f"{who} ne verse pas un secret dans la mémoire d'équipe (refusé par le portier)", "error" in out, str(out)[:100])
            mail = "From: client-fictif@exemple.invalid\nTo: x@banc.invalid\nSubject: Devis\n\nBonjour"
            out = plugin_call(who, "team_remember", {"fait": mail, "source": "recette"})
            check(f"{who} ne verse pas un mail entier dans la mémoire d'équipe", "error" in out, str(out)[:100])
        for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
            gate_other = f"http://127.0.0.1:{USERS[other]['gate']}"
            tok = secret(other, "hindsight_gate_token")
            for canary in (personal[who].split(":")[0], secrets_[who]):
                # 1. Rappel d'équipe (ce que l'autre peut interroger) : jamais le perso ni le secret.
                out = plugin_call(other, "team_recall", {"requete": canary})
                check(f"{other} ne retrouve pas {canary[:22]}… de {who} dans la mémoire d'équipe", canary not in json.dumps(out, ensure_ascii=False), str(out)[:80])
                # 2. Demande explicite à l'API Hindsight sur la banque de l'autre : refusée par le portier.
                for method, path, body in (("POST", f"/v1/default/banks/arpagona-{who}/memories/recall", {"query": canary}),
                                           ("GET", f"/v1/default/banks/arpagona-{who}/memories/list", None),
                                           ("GET", "/v1/default/banks", None)):
                    status, raw = http(method, gate_other + path, tok, body)
                    check(f"{other} : API {method} {path.split('/banks')[-1] or '/'} refusée pour la banque de {who}", status == 403 and canary not in raw, f"HTTP {status}")
                # 3. Même demande dans SA propre banque : le fait de l'autre n'y est pas.
                status, raw = http("POST", f"{gate_other}/v1/default/banks/arpagona-{other}/memories/recall", tok, {"query": canary})
                check(f"{other} ne retrouve pas {canary[:22]}… de {who} dans sa propre banque", status == 200 and canary not in raw, f"HTTP {status}")
            status, raw = http("POST", f"{gate_other}/v1/default/banks/{TEAM_BANK}/memories/recall", tok, {"query": secrets_[who]})
            check(f"API équipe : le secret de {who} introuvable par {other}", status == 200 and secrets_[who] not in raw, f"HTTP {status}")
    finally:
        # Nettoyage des seules fixtures de la recette (documents par identifiant), avec la clé du portier côté root.
        key = upstream_key()
        removed = 0
        for bank, docs in ((TEAM_BANK, list(doc_ids.values())), *((f"arpagona-{w}", [personal_docs[w], personal_docs[w] + "-secret"]) for w in USERS)):
            for doc in docs:
                status, _ = http("DELETE", f"{UPSTREAM}/v1/default/banks/{bank}/documents/{doc}", key)
                removed += status in (200, 202, 204)
        check("fixtures de mémoire retirées (par identifiant de document, aucune autre donnée touchée)", removed >= 1, f"{removed} document(s)")


def team_files() -> None:
    """Dossiers clients : création et modification croisées, droits des nouveaux fichiers, traversées et liens refusés."""
    check("espace commun : dossier en setgid, groupe arpagona-equipe, fermé aux autres",
          oct(os.stat(CLIENTS).st_mode & 0o7777) == "0o2770" and sh(None, f"stat -c %G {CLIENTS}").stdout.strip() == "arpagona-equipe")
    base = f"recette-{RUN}"
    rel = {who: f"{base}/fiche-{who}.md" for who in USERS}
    try:
        for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
            out = plugin_call(who, "clients_write", {"chemin": rel[who], "contenu": f"Fiche client fictive créée par {who}\n"})
            check(f"{who} crée un fichier client dans l'espace commun", out.get("ecrit", 0) > 0, str(out)[:100])
            mode = oct(os.stat(f"{CLIENTS}/{rel[who]}").st_mode & 0o777)
            grp = sh(None, f"stat -c %G {CLIENTS}/{rel[who]}").stdout.strip()
            check(f"fichier de {who} : 0660, groupe d'équipe (créé avec un umask 077)", mode == "0o660" and grp == "arpagona-equipe", f"{mode} {grp}")
            dmode = oct(os.stat(f"{CLIENTS}/{base}").st_mode & 0o7777)
            check("dossier créé : setgid, rwx pour le groupe", dmode == "0o2770", dmode)
            out = plugin_call(other, "clients_read", {"chemin": rel[who]})
            check(f"{other} lit le fichier client de {who}", f"créée par {who}" in out.get("contenu", ""), str(out)[:100])
            out = plugin_call(other, "clients_write", {"chemin": rel[who], "contenu": f"Modifié par {other}\n", "ajouter": True})
            check(f"{other} modifie le fichier client de {who}", out.get("ecrit", 0) > 0, str(out)[:100])
            text = Path(f"{CLIENTS}/{rel[who]}").read_text()
            check(f"relecture : le fichier de {who} contient la modification de {other}", f"Modifié par {other}" in text and f"créée par {who}" in text)
        listing = plugin_call("mael", "clients_list", {"chemin": base})
        check("les deux fichiers sont listés pour les deux agents", len(listing.get("entrees", [])) == 2, str(listing)[:100])
        if sh(None, "id mael").returncode == 0:
            check("humain habilité (mael) lit un fichier client", sh("mael", f"cat {CLIENTS}/{rel['thibaud']}").returncode == 0)
            check("humain habilité (mael) modifie un fichier client", sh("mael", f"echo 'ligne humaine' >> {CLIENTS}/{rel['thibaud']}").returncode == 0)
            check("l'agent relit la modification de l'humain", "ligne humaine" in plugin_call("thibaud", "clients_read", {"chemin": rel["thibaud"]}).get("contenu", ""))
            sh("mael", f"touch {CLIENTS}/{base}/note-humaine.md")
            check("fichier créé par un humain : groupe d'équipe via ACL par défaut, agent peut le modifier",
                  plugin_call("mael", "clients_write", {"chemin": f"{base}/note-humaine.md", "contenu": "x"}).get("ecrit", 0) > 0)
        check("compte tiers (nobody) : aucun accès à l'espace commun", denied("nobody", f"ls {CLIENTS}"))
        # Traversées et liens : refusés par l'outil ET par les droits Unix.
        for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
            for bad in (f"../../agents/{other}/.hermes/.env", f"/srv/agents/{other}/.hermes/.env", f"{base}/../../agents/{other}/mail"):
                check(f"{who} : outil clients refuse « {bad[:40]} »", "error" in plugin_call(who, "clients_read", {"chemin": bad}))
            sh(f"agent-{who}", f"ln -s {home(other)}/.hermes/.env {CLIENTS}/{base}/piege-{who}; ln -s {home(other)} {CLIENTS}/{base}/dossier-piege-{who}")
            check(f"{other} : lien symbolique de {who} vers un fichier privé refusé par l'outil", "error" in plugin_call(other, "clients_read", {"chemin": f"{base}/piege-{who}"}))
            check(f"{other} : lien symbolique vers un dossier privé refusé (lecture et écriture)",
                  "error" in plugin_call(other, "clients_read", {"chemin": f"{base}/dossier-piege-{who}/.hermes/.env"})
                  and "error" in plugin_call(other, "clients_write", {"chemin": f"{base}/dossier-piege-{who}/intrus.txt", "contenu": "x"}))
            check(f"{who} : son propre lien vers le privé de {other} ne lui ouvre rien (droits Unix)", denied(f"agent-{who}", f"cat {CLIENTS}/{base}/piege-{who}"))
        check("aucun fichier créé chez l'autre par les tentatives d'écriture", not Path(home("thibaud"), "intrus.txt").exists() and not Path(home("mael"), "intrus.txt").exists())
        for who, other in (("mael", "thibaud"), ("thibaud", "mael")):
            check(f"agent-{who} : l'espace commun ne rouvre pas les dossiers privés de {other}",
                  denied(f"agent-{who}", f"ls {home(other)}/mail") and denied(f"agent-{who}", f"cat {home(other)}/.hermes/.env"))
    finally:
        shutil.rmtree(f"{CLIENTS}/{base}", ignore_errors=True)
        check("fixtures de dossiers clients retirées", not Path(f"{CLIENTS}/{base}").exists())


def live_zones() -> None:
    """Deux vrais tours de modèle : les outils d'équipe sont bien câblés dans l'agent réel (coût minime)."""
    fact = f"Le client fictif LIVE-{RUN} paie à 45 jours."
    key = secret("mael", "api_server_key")
    sid = f"zones-{RUN}"
    prompt = (f"Avec arpagona_equipe_memoire_ecrire, enregistre ce fait métier d'équipe avec source « recette live » et id « recette-live-{RUN} » : {fact} "
              f"Puis avec arpagona_clients_ecrire écris le fichier recette-live-{RUN}/note.md contenant « paiement 45 jours ». Réponds OK.")
    status, raw = http("POST", f"http://127.0.0.1:{USERS['mael']['engine']}/v1/runs", key, {"input": prompt, "session_id": sid}, {"Idempotency-Key": sid})
    run = json.loads(raw)["run_id"] if status == 202 else ""
    state = ""
    for _ in range(45):
        time.sleep(4)
        st, body = http("GET", f"http://127.0.0.1:{USERS['mael']['engine']}/v1/runs/{run}", key)
        state = json.loads(body).get("status", "") if st == 200 else ""
        if state in ("completed", "failed", "cancelled"):
            break
    check("run réel : l'agent de Maël utilise les outils d'équipe", state == "completed", state)
    note = Path(f"{CLIENTS}/recette-live-{RUN}/note.md")
    check("run réel : fichier client créé par l'agent de Maël, lisible par l'agent de Thibaud",
          note.exists() and "45 jours" in plugin_call("thibaud", "clients_read", {"chemin": f"recette-live-{RUN}/note.md"}).get("contenu", ""))
    out = plugin_call("thibaud", "team_recall", {"requete": f"LIVE-{RUN} délai de paiement"})
    hits = [r for r in out.get("resultats", []) if f"LIVE-{RUN}" in r.get("fait", "")]
    check("run réel : Thibaud retrouve le fait enregistré par l'agent de Maël (auteur mael)", bool(hits) and hits[0].get("auteur") == "mael", str(out)[:120])
    shutil.rmtree(f"{CLIENTS}/recette-live-{RUN}", ignore_errors=True)
    status, _ = http("DELETE", f"{UPSTREAM}/v1/default/banks/{TEAM_BANK}/documents/recette-live-{RUN}", upstream_key())
    check("fixtures du tour réel retirées", status in (200, 202, 204) and not note.exists(), f"HTTP {status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="inclut un vrai tour de modèle")
    parser.add_argument("--json")
    args = parser.parse_args()
    if os.geteuid() != 0:
        sys.exit("à lancer en root")
    # Hermès remet .hermes à 0700 à chaque démarrage (masque ACL) : on rejoue les droits de lecture du socle
    # pour les contrôles faits « hors service ». Les services eux-mêmes n'en dépendent pas (montage lecture seule).
    subprocess.run(["bash", "/opt/arpagona/current/deploy/atlas/agents-perso.sh", "acl"], check=True)
    unix_isolation()
    network_isolation()
    mail_isolation(args.live)
    team_memory()
    team_files()
    api_isolation(args.live)
    if args.live:
        live_zones()
    failed = [r for r in RESULTS if not r["ok"]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} contrôles réussis")
    if args.json:
        Path(args.json).write_text(json.dumps({"total": len(RESULTS), "failed": len(failed), "results": RESULTS},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
