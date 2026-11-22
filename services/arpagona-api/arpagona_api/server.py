"""API ARPAGONA : seule surface exposée au navigateur. Relaie le chat vers Hermès en boucle locale."""
from __future__ import annotations

import json
import os
import threading
import hmac
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engagements import InvalidEngagement, fingerprint, parse_due, validate_fields
from .hermes import TERMINAL, HermesClient, HermesError
from .store import SESSION_TTL_S, Store
from .kanban import KanbanClient

COOKIE = "arpagona_session"
MAX_BODY = 16 * 1024
MAX_TEXT = 8000
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                ".webmanifest": "application/manifest+json"}
LOGIN_MAX_FAILS = 5
LOGIN_LOCK_S = 60


class App:
    def __init__(self, store: Store, hermes: HermesClient, static_dir: Path, cookie_secure: bool,
                 service_token: str = ""):
        self.store = store
        self.hermes = hermes
        self.static_dir = static_dir.resolve()
        self.cookie_secure = cookie_secure
        self.service_token = service_token
        self.kanban: KanbanClient | None = None
        self._fails: dict[str, tuple[int, float]] = {}
        self._fails_lock = threading.Lock()

    # --- limitation des essais de connexion -------------------------------
    def login_locked(self, login: str) -> bool:
        with self._fails_lock:
            count, until = self._fails.get(login, (0, 0.0))
            return count >= LOGIN_MAX_FAILS and time.time() < until

    def login_failed(self, login: str) -> None:
        with self._fails_lock:
            count, until = self._fails.get(login, (0, 0.0))
            if time.time() > until:
                count = 0
            self._fails[login] = (count + 1, time.time() + LOGIN_LOCK_S)

    def login_ok(self, login: str) -> None:
        with self._fails_lock:
            self._fails.pop(login, None)

    # --- messages en attente ----------------------------------------------
    def settle_from_engine(self, message_id: int, run_id: str | None) -> None:
        """Arrête l'état d'une réponse d'après le moteur. Ne conclut rien si l'exécution est encore en cours."""
        if not run_id:
            self.store.settle_message(message_id, "La demande n'a pas pu être transmise.", "failed")
            return
        try:
            status = self.hermes.run_status(run_id)
        except HermesError:
            return
        state = status.get("status")
        if state == "completed":
            self.store.settle_message(message_id, str(status.get("output") or ""), "done")
        elif state in TERMINAL:
            self.store.settle_message(message_id, "La réponse n'a pas abouti.", "failed")


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ARPAGONA"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # journal applicatif dans la table audit, pas sur stderr
            return

        # --- utilitaires ---------------------------------------------------
        def _headers(self, status: int, ctype: str, length: int | None, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Cache-Control", "no-store")
            # Une connexion par requête : un corps non lu (requête refusée) ne peut pas être pris pour la suivante.
            self.send_header("Connection", "close")
            self.close_connection = True
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()

        def _json(self, status: int, payload: dict, extra: dict | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body), extra)
            self.wfile.write(body)

        def _token(self) -> str | None:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            return cookie[COOKIE].value if COOKIE in cookie else None

        def _user(self):
            token = self._token()
            return app.store.user_for_token(token) if token else None

        def _body(self, require_marker: bool = True) -> dict | None:
            """Corps JSON. L'en-tête X-Arpagona interdit les envois inter-sites simples côté navigateur ;
            les appels internes (outils du plugin) en sont dispensés mais exigent le jeton de service."""
            if require_marker and self.headers.get("X-Arpagona") != "1":
                return None
            if "application/json" not in self.headers.get("Content-Type", ""):
                return None
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if not 0 < length <= MAX_BODY:
                return None
            try:
                data = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return data if isinstance(data, dict) else None

        def _cookie(self, value: str, max_age: int) -> str:
            parts = [f"{COOKIE}={value}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
            if app.cookie_secure:
                parts.append("Secure")
            return "; ".join(parts)

        # --- routage -------------------------------------------------------
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/health":
                return self._json(200, {"status": "ok"})
            if path == "/api/me":
                user = self._user()
                if not user:
                    return self._json(401, {"error": "non connecté"})
                return self._json(200, {"login": user["login"], "name": user["display_name"]})
            if path.startswith("/api/kanban/"):
                return self._kanban(path, False)
            if path == "/api/conversation":
                return self._conversation()
            if path == "/api/engagements":
                return self._engagements()
            if path == "/api/drafts":
                return self._drafts()
            if path == "/internal/engagements":
                return self._internal_engagements()
            if path.startswith("/api/"):
                return self._json(404, {"error": "inconnu"})
            return self._static(path)

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/login":
                return self._login()
            if path == "/api/logout":
                return self._logout()
            if path.startswith("/api/kanban/"):
                return self._kanban(path, True)
            if path == "/api/chat":
                return self._chat()
            if path == "/api/drafts/decide":
                return self._decide()
            if path == "/internal/engagements":
                return self._internal_record()
            if path == "/internal/drafts":
                return self._internal_draft()
            return self._json(404, {"error": "inconnu"})

        def _kanban(self, path, mutation):
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            op = path.removeprefix("/api/kanban/")
            if mutation:
                data = self._body()
                allowed = {"create", "comment", "complete", "block", "unblock", "archive"}
            else:
                allowed = {"list", "show"}
                from urllib.parse import parse_qs, urlsplit
                query = parse_qs(urlsplit(self.path).query)
                data = {"id": query["id"][0]} if "id" in query else {}
            if op not in allowed or data is None:
                return self._json(400, {"error": "opération invalide"})
            data.pop("author", None)
            if op == "comment":
                # L'auteur vient du compte connecté, jamais du navigateur.
                data["author"] = user["display_name"]
            client = getattr(app, "kanban", None)
            status, result = client.call(op, data) if client else (503, {"error": "Kanban indisponible"})
            app.store.audit(user["id"], "kanban_" + op, str(status) + " " + str(data.get("id", ""))[:64])
            return self._json(status, result)

        # --- fichiers statiques ---------------------------------------------
        def _static(self, path: str) -> None:
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (app.static_dir / name).resolve()
            if (app.static_dir not in target.parents or not target.is_file()
                    or target.suffix not in STATIC_TYPES):
                return self._json(404, {"error": "inconnu"})
            body = target.read_bytes()
            self._headers(200, STATIC_TYPES[target.suffix], len(body))
            self.wfile.write(body)

        # --- session ---------------------------------------------------------
        def _login(self) -> None:
            data = self._body()
            if not data:
                return self._json(400, {"error": "requête invalide"})
            login, password = str(data.get("login", ""))[:64], str(data.get("password", ""))[:256]
            if app.login_locked(login):
                app.store.audit(None, "connexion_bloquée", login)
                return self._json(429, {"error": "trop d'essais, réessayez dans une minute"})
            user = app.store.check_password(login, password)
            if not user:
                app.login_failed(login)
                app.store.audit(None, "connexion_refusée", login)
                return self._json(401, {"error": "identifiants incorrects"})
            app.login_ok(login)
            token = app.store.open_session(user["id"])
            app.store.audit(user["id"], "connexion")
            self._json(200, {"login": user["login"], "name": user["display_name"]},
                       {"Set-Cookie": self._cookie(token, SESSION_TTL_S)})

        def _logout(self) -> None:
            if self._body() is None and self.headers.get("X-Arpagona") != "1":
                return self._json(400, {"error": "requête invalide"})
            token = self._token()
            user = self._user()
            if token:
                app.store.close_session(token)
            if user:
                app.store.audit(user["id"], "déconnexion")
            self._json(200, {"status": "ok"}, {"Set-Cookie": self._cookie("", 0)})

        # --- conversation ----------------------------------------------------
        def _conversation(self) -> None:
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            conv = app.store.conversation_for(user["id"])
            for row in app.store.messages(conv["id"]):
                if row["status"] == "pending":
                    app.settle_from_engine(row["id"], row["run_id"])
            rows = app.store.messages(conv["id"])
            self._json(200, {"messages": [
                {"id": r["id"], "role": r["role"], "text": r["content"], "status": r["status"], "at": r["created_at"]}
                for r in rows]})

        def _chat(self) -> None:
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            data = self._body()
            text = str(data.get("text", "")).strip() if data else ""
            if not text or len(text) > MAX_TEXT:
                return self._json(400, {"error": "message vide ou trop long"})
            conv = app.store.conversation_for(user["id"])
            if app.store.has_pending(conv["id"]):
                return self._json(409, {"error": "une réponse est déjà en cours"})
            app.store.add_message(conv["id"], "user", text)
            answer_id = app.store.add_message(conv["id"], "assistant", "", status="pending")
            try:
                run_id = app.hermes.start_run(text, conv["hermes_session_id"],
                                              f"arpagona-{conv['hermes_session_id']}-msg-{answer_id}")
            except HermesError as exc:
                app.store.settle_message(answer_id, "Le moteur est indisponible.", "failed")
                app.store.audit(user["id"], "chat_échec", str(exc))
                return self._json(502, {"error": "moteur indisponible"})
            app.store.set_run_id(answer_id, run_id)
            app.store.audit(user["id"], "chat", f"message {answer_id}")

            self._headers(200, "text/event-stream; charset=utf-8", None,
                          {"X-Accel-Buffering": "no"})
            client_alive = True

            def send(payload: dict) -> None:
                nonlocal client_alive
                if not client_alive:
                    return
                try:
                    self.wfile.write(b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n")
                    self.wfile.flush()
                except OSError:
                    client_alive = False  # le navigateur est parti : on continue de suivre l'exécution

            send({"type": "start", "id": answer_id})
            try:
                for event in app.hermes.events(run_id):
                    kind = event.get("event", "")
                    if kind == "message.delta":
                        send({"type": "delta", "text": event.get("delta", "")})
                    elif kind in ("tool.started", "tool.completed"):
                        send({"type": "tool", "name": str(event.get("tool", "")), "state": kind.split(".")[1]})
            except HermesError:
                pass
            # L'état final vient toujours du moteur, pas du flux relayé.
            deadline = time.time() + 30
            while time.time() < deadline:
                app.settle_from_engine(answer_id, run_id)
                if not app.store.has_pending(conv["id"]):
                    break
                time.sleep(1)
            final = next((r for r in app.store.messages(conv["id"]) if r["id"] == answer_id), None)
            send({"type": "end", "id": answer_id, "status": final["status"] if final else "pending",
                  "text": final["content"] if final else ""})

        # --- engagements et approbations (utilisateur) ----------------------
        def _engagements(self) -> None:
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            rows = app.store.engagements(user["id"])
            self._json(200, {"engagements": [
                {"id": r["id"], "client": r["client"], "sujet": r["subject"], "decision": r["decision"],
                 "echeance": r["due_at"], "fuseau": r["due_tz"], "expression": r["due_expression"],
                 "certitude": r["confidence"], "statut": r["status"]} for r in rows]})

        def _drafts(self) -> None:
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            rows = app.store.drafts(user["id"])
            self._json(200, {"drafts": [
                {"id": r["id"], "engagement_id": r["engagement_id"], "cible": r["target"], "corps": r["body"],
                 "empreinte": r["fingerprint"], "statut": r["status"], "livraison": r["delivery"],
                 "cree": r["created_at"]} for r in rows]})

        def _decide(self) -> None:
            user = self._user()
            if not user:
                return self._json(401, {"error": "non connecté"})
            data = self._body()
            if not data:
                return self._json(400, {"error": "requête invalide"})
            try:
                draft_id = int(data.get("id", 0))
            except (TypeError, ValueError):
                return self._json(400, {"error": "identifiant invalide"})
            outcome = app.store.decide_draft(draft_id, bool(data.get("approve")), user["id"],
                                             str(data.get("empreinte", "")))
            if outcome == "contenu_modifie":
                app.store.audit(user["id"], "validation_refusée_contenu_modifié", str(draft_id))
                return self._json(409, {"error": "le brouillon a changé : relisez-le avant de décider"})
            if outcome in ("inconnu", "deja_decide"):
                return self._json(409, {"error": "brouillon inconnu ou déjà décidé"})
            if outcome == "approuve":
                # Aucun connecteur d'envoi n'est autorisé à ce stade : le brouillon est prêt, pas envoyé.
                app.store.set_delivery_note(draft_id, "non envoyé : aucun connecteur autorisé")
            app.store.audit(user["id"], "brouillon_" + outcome, str(draft_id))
            self._json(200, {"statut": outcome, "livraison": "non envoyé : aucun connecteur autorisé"
                             if outcome == "approuve" else None})

        # --- routes internes (outils du plugin) -----------------------------
        def _service_user(self):
            """Authentifie l'appel d'outil et rattache la session Hermès à un utilisateur."""
            token = self.headers.get("X-Arpagona-Service", "")
            if not app.service_token or not hmac.compare_digest(token, app.service_token):
                return None
            session = self.headers.get("X-Hermes-Session", "")
            return app.store.user_for_hermes_session(session) if session else None

        def _internal_engagements(self) -> None:
            user = self._service_user()
            if not user:
                return self._json(401, {"error": "service non autorisé"})
            rows = app.store.engagements(user["id"])
            self._json(200, {"engagements": [
                {"id": r["id"], "client": r["client"], "sujet": r["subject"], "decision": r["decision"],
                 "echeance": r["due_at"], "fuseau": r["due_tz"], "certitude": r["confidence"],
                 "statut": r["status"]} for r in rows]})

        def _internal_record(self) -> None:
            user = self._service_user()
            if not user:
                return self._json(401, {"error": "service non autorisé"})
            data = self._body(require_marker=False)
            if not data:
                return self._json(400, {"error": "requête invalide"})
            try:
                client, subject, decision, confidence = validate_fields(
                    str(data.get("client", "")), str(data.get("sujet", "")),
                    str(data.get("decision", "")), str(data.get("certitude", "")))
                due_at, due_tz, expression = parse_due(str(data.get("echeance", "")))
            except InvalidEngagement as exc:
                return self._json(400, {"error": str(exc)})
            engagement_id = app.store.add_engagement(user["id"], client, subject, decision, due_at, due_tz,
                                                     expression, confidence, None)
            app.store.audit(user["id"], "engagement_enregistré", f"{engagement_id} {client}")
            self._json(201, {"id": engagement_id, "statut": "planifie", "echeance": due_at, "fuseau": due_tz})

        def _internal_draft(self) -> None:
            user = self._service_user()
            if not user:
                return self._json(401, {"error": "service non autorisé"})
            data = self._body(require_marker=False)
            if not data:
                return self._json(400, {"error": "requête invalide"})
            try:
                engagement_id = int(data.get("engagement_id", 0))
            except (TypeError, ValueError):
                return self._json(400, {"error": "engagement invalide"})
            engagement = app.store.engagement(engagement_id)
            if not engagement or engagement["user_id"] != user["id"]:
                return self._json(404, {"error": "engagement inconnu"})
            target = str(data.get("cible", "")).strip()
            body = str(data.get("corps", "")).strip()
            if not target or not body or len(body) > 8000:
                return self._json(400, {"error": "cible ou corps manquant"})
            draft_id = app.store.add_draft(engagement_id, user["id"], target, body,
                                           fingerprint(target, body))
            app.store.release_engagement(engagement_id, "en_attente")
            app.store.audit(user["id"], "brouillon_créé", f"{draft_id} engagement {engagement_id}")
            self._json(201, {"id": draft_id, "statut": "en_attente"})

    return Handler


def start_trigger(app: App, interval_s: float = 30.0) -> threading.Thread:
    """Déclencheur d'échéances : réveille l'agent pour un engagement arrivé à terme, sans cron externe."""

    def loop() -> None:
        while True:
            try:
                due = app.store.claim_due(time.time())
                if due:
                    run_due_engagement(app, due)
            except Exception:  # le déclencheur ne doit jamais mourir
                pass
            time.sleep(interval_s)

    thread = threading.Thread(target=loop, name="echeances", daemon=True)
    thread.start()
    return thread


def run_due_engagement(app: App, engagement: dict) -> None:
    conv = app.store.conversation_for(engagement["user_id"])
    prompt = (
        "Échéance atteinte. Engagement enregistré :\n"
        f"- client : {engagement['client']}\n- sujet : {engagement['subject']}\n"
        f"- décision : {engagement['decision']}\n- échéance : {engagement['due_expression']}\n\n"
        "Prépare un brouillon de relance avec l'outil arpagona_draft_create. "
        "Rappelle le motif et la décision dans le corps. N'envoie rien."
    )
    try:
        # La clé porte la session (aléatoire, propre au compte) et le numéro de tentative : un numéro de
        # ligne seul peut être réattribué par SQLite, et une nouvelle tentative doit relancer une exécution.
        run_id = app.hermes.start_run(
            prompt, conv["hermes_session_id"],
            f"arpagona-{conv['hermes_session_id']}-echeance-{engagement['id']}-{engagement['attempts']}")
    except HermesError:
        app.store.release_engagement(engagement["id"], "planifie")
        return
    deadline = time.time() + 240
    while time.time() < deadline:
        try:
            status = app.hermes.run_status(run_id)
        except HermesError:
            time.sleep(5)
            continue
        if status.get("status") in TERMINAL:
            app.store.audit(engagement["user_id"], "échéance_traitée",
                            f"{engagement['id']} {status.get('status')}")
            fresh = app.store.engagement(engagement["id"])
            if fresh and fresh["status"] == "en_preparation":
                app.store.release_engagement(engagement["id"], "planifie")
            return
        time.sleep(3)


def main() -> None:
    db_path = os.environ.get("ARPAGONA_DB", "/var/lib/arpagona-api/arpagona.db")
    key_file = os.environ.get("ARPAGONA_HERMES_KEY_FILE", "/etc/arpagona-api/hermes_key")
    static_dir = Path(os.environ.get("ARPAGONA_STATIC_DIR", "/opt/arpagona/current/apps/mission-control-web"))
    host = os.environ.get("ARPAGONA_BIND", "127.0.0.1")
    port = int(os.environ.get("ARPAGONA_PORT", "8700"))
    hermes = HermesClient(os.environ.get("ARPAGONA_HERMES_URL", "http://127.0.0.1:8642"),
                          Path(key_file).read_text(encoding="ascii").strip())
    app = App(Store(db_path), hermes, static_dir, os.environ.get("ARPAGONA_COOKIE_SECURE", "0") == "1")
    token_file = os.environ.get("ARPAGONA_SERVICE_TOKEN_FILE", "")
    app.service_token = Path(token_file).read_text(encoding="ascii").strip() if token_file else ""
    kanban_file = os.environ.get("ARPAGONA_KANBAN_TOKEN_FILE", "")
    if kanban_file:
        kanban_token = Path(kanban_file).read_text(encoding="ascii").strip()
        if kanban_token:
            app.kanban = KanbanClient(kanban_token, os.environ.get("ARPAGONA_KANBAN_URL", "http://127.0.0.1:8701"))
    start_trigger(app, float(os.environ.get("ARPAGONA_TRIGGER_INTERVAL", "30")))
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
