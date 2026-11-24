"""Stockage SQLite de l'API ARPAGONA : utilisateurs, sessions web, conversations, journal."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    pw_salt BLOB NOT NULL,
    pw_hash BLOB NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    hermes_session_id TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    closed_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('done', 'pending', 'failed')),
    run_id TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    client TEXT NOT NULL,
    subject TEXT NOT NULL,
    decision TEXT NOT NULL,
    due_at REAL NOT NULL,
    due_tz TEXT NOT NULL,
    due_expression TEXT NOT NULL,
    source_message_id INTEGER REFERENCES messages(id),
    confidence TEXT NOT NULL CHECK (confidence IN ('certain', 'probable', 'a_confirmer')),
    status TEXT NOT NULL CHECK (status IN ('planifie', 'en_preparation', 'pret', 'en_attente',
                                          'approuve', 'refuse', 'envoye', 'echec', 'annule')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at REAL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL REFERENCES engagements(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    target TEXT NOT NULL,
    body TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('en_attente', 'approuve', 'refuse', 'envoye', 'echec')),
    decided_at REAL,
    decided_by INTEGER REFERENCES users(id),
    delivery TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS engagements_due ON engagements(status, due_at);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""

SESSION_TTL_S = 12 * 3600
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "ignore")).hexdigest()


class Store:
    """Une connexion SQLite partagée, protégée par un verrou (charge de prototype)."""

    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.executescript(SCHEMA)
            self._migrate()
            # Une seule conversation ouverte par compte ; /new ferme la précédente.
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS conversations_open"
                             " ON conversations(user_id) WHERE closed_at IS NULL")

    def _migrate(self) -> None:
        """Bases antérieures : une conversation par compte (user_id UNIQUE), sans closed_at.

        SQLite ne sait pas retirer une contrainte : la table est reconstruite à l'identique,
        mêmes identifiants, dans une transaction. Les messages gardent leur conversation.
        """
        cols = [r["name"] for r in self._db.execute("PRAGMA table_info(conversations)")]
        if "closed_at" in cols:
            return
        self._db.execute("PRAGMA foreign_keys=OFF")
        try:
            self._db.execute("BEGIN")
            self._db.execute("CREATE TABLE conversations_v2 (id INTEGER PRIMARY KEY,"
                             " user_id INTEGER NOT NULL REFERENCES users(id),"
                             " hermes_session_id TEXT NOT NULL UNIQUE, created_at REAL NOT NULL, closed_at REAL)")
            self._db.execute("INSERT INTO conversations_v2(id, user_id, hermes_session_id, created_at)"
                             " SELECT id, user_id, hermes_session_id, created_at FROM conversations")
            self._db.execute("DROP TABLE conversations")
            self._db.execute("ALTER TABLE conversations_v2 RENAME TO conversations")
            if self._db.execute("PRAGMA foreign_key_check").fetchall():
                raise sqlite3.IntegrityError("migration des conversations : clés étrangères rompues")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        finally:
            self._db.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, args)

    def _all(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    # --- utilisateurs -----------------------------------------------------
    def add_user(self, login: str, display_name: str, password: str) -> int:
        if len(password) < 12:
            raise ValueError("mot de passe trop court (12 caractères minimum)")
        salt = secrets.token_bytes(16)
        cur = self._run(
            "INSERT INTO users(login, display_name, pw_salt, pw_hash, created_at) VALUES (?,?,?,?,?)",
            (login, display_name, salt, _hash_password(password, salt), time.time()),
        )
        return int(cur.lastrowid or 0)

    def set_password(self, login: str, password: str) -> bool:
        """Remplace le mot de passe et ferme les sessions ouvertes du compte."""
        if len(password) < 12:
            raise ValueError("mot de passe trop court (12 caractères minimum)")
        salt = secrets.token_bytes(16)
        with self._lock:
            row = self._db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
            if row is None:
                return False
            self._db.execute("BEGIN")
            try:
                self._db.execute("UPDATE users SET pw_salt = ?, pw_hash = ? WHERE id = ?",
                                 (salt, _hash_password(password, salt), row["id"]))
                self._db.execute("DELETE FROM web_sessions WHERE user_id = ?", (row["id"],))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return True

    def delete_user(self, login: str) -> bool:
        """Supprime un compte et tout ce qui lui appartient (comptes de recette). Transaction unique."""
        with self._lock:
            row = self._db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
            if not row:
                return False
            uid = row["id"]
            self._db.execute("BEGIN")
            try:
                self._db.execute("DELETE FROM drafts WHERE user_id = ?", (uid,))
                self._db.execute("DELETE FROM engagements WHERE user_id = ?", (uid,))
                self._db.execute("DELETE FROM messages WHERE conversation_id IN"
                                 " (SELECT id FROM conversations WHERE user_id = ?)", (uid,))
                self._db.execute("DELETE FROM conversations WHERE user_id = ?", (uid,))
                self._db.execute("DELETE FROM web_sessions WHERE user_id = ?", (uid,))
                self._db.execute("DELETE FROM users WHERE id = ?", (uid,))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return True

    def check_password(self, login: str, password: str) -> sqlite3.Row | None:
        row = self._one("SELECT * FROM users WHERE login = ?", (login,))
        # Calcul fait même si le compte n'existe pas, pour ne pas le révéler par le temps de réponse.
        salt = row["pw_salt"] if row else b"\0" * 16
        candidate = _hash_password(password, salt)
        if row and hmac.compare_digest(candidate, row["pw_hash"]):
            return row
        return None

    # --- sessions web -----------------------------------------------------
    def open_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._run("DELETE FROM web_sessions WHERE expires_at < ?", (time.time(),))
        self._run(
            "INSERT INTO web_sessions(token_hash, user_id, expires_at) VALUES (?,?,?)",
            (_token_hash(token), user_id, time.time() + SESSION_TTL_S),
        )
        return token

    def close_session(self, token: str) -> None:
        self._run("DELETE FROM web_sessions WHERE token_hash = ?", (_token_hash(token),))

    def user_for_token(self, token: str) -> sqlite3.Row | None:
        return self._one(
            "SELECT u.* FROM web_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (_token_hash(token), time.time()),
        )

    # --- conversation -----------------------------------------------------
    def conversation_for(self, user_id: int) -> sqlite3.Row:
        """Conversation ouverte de l'utilisateur. L'identifiant de session Hermès est tiré ici, jamais reçu du client."""
        row = self._one("SELECT * FROM conversations WHERE user_id = ? AND closed_at IS NULL", (user_id,))
        if row:
            return row
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO conversations(user_id, hermes_session_id, created_at) VALUES (?,?,?)",
                (user_id, self._new_session_id(user_id), time.time()),
            )
            return self._db.execute("SELECT * FROM conversations WHERE user_id = ? AND closed_at IS NULL",
                                    (user_id,)).fetchone()

    @staticmethod
    def _new_session_id(user_id: int) -> str:
        return f"arpagona-u{user_id}-{secrets.token_hex(12)}"

    def new_conversation(self, user_id: int) -> sqlite3.Row:
        """/new : ferme la conversation ouverte et en ouvre une neuve, avec une nouvelle session Hermès.

        L'ancienne reste en base (historique, engagements liés) mais n'est plus jamais envoyée au moteur.
        La mémoire d'équipe (Hindsight) n'est pas touchée : elle appartient à l'instance (ADR 0008).
        """
        now = time.time()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("UPDATE conversations SET closed_at = ? WHERE user_id = ? AND closed_at IS NULL",
                                 (now, user_id))
                self._db.execute("INSERT INTO conversations(user_id, hermes_session_id, created_at) VALUES (?,?,?)",
                                 (user_id, self._new_session_id(user_id), now))
                row = self._db.execute("SELECT * FROM conversations WHERE user_id = ? AND closed_at IS NULL",
                                       (user_id,)).fetchone()
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
            return row

    def conversation_count(self, user_id: int) -> int:
        return int(self._one("SELECT COUNT(*) AS n FROM conversations WHERE user_id = ?", (user_id,))["n"])

    def add_message(self, conversation_id: int, role: str, content: str, status: str = "done",
                    run_id: str | None = None) -> int:
        cur = self._run(
            "INSERT INTO messages(conversation_id, role, content, status, run_id, created_at) VALUES (?,?,?,?,?,?)",
            (conversation_id, role, content, status, run_id, time.time()),
        )
        return int(cur.lastrowid or 0)

    def set_run_id(self, message_id: int, run_id: str) -> None:
        self._run("UPDATE messages SET run_id = ? WHERE id = ?", (run_id, message_id))

    def settle_message(self, message_id: int, content: str, status: str) -> None:
        self._run("UPDATE messages SET content = ?, status = ? WHERE id = ? AND status = 'pending'",
                  (content, status, message_id))

    def messages(self, conversation_id: int) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))

    def has_pending(self, conversation_id: int) -> bool:
        return self._one("SELECT 1 FROM messages WHERE conversation_id = ? AND status = 'pending'",
                         (conversation_id,)) is not None

    # --- journal ----------------------------------------------------------
    # --- engagements ------------------------------------------------------
    def add_engagement(self, user_id: int, client: str, subject: str, decision: str, due_at: float,
                       due_tz: str, due_expression: str, confidence: str,
                       source_message_id: int | None) -> int:
        cur = self._run(
            "INSERT INTO engagements(user_id, client, subject, decision, due_at, due_tz, due_expression,"
            " source_message_id, confidence, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,'planifie',?)",
            (user_id, client, subject, decision, due_at, due_tz, due_expression, source_message_id,
             confidence, time.time()),
        )
        return int(cur.lastrowid or 0)

    def engagements(self, user_id: int, statuses: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM engagements WHERE user_id = ?"
        args: list = [user_id]
        if statuses:
            sql += " AND status IN (" + ",".join("?" * len(statuses)) + ")"
            args.extend(statuses)
        return self._all(sql + " ORDER BY due_at", tuple(args))

    def engagement(self, engagement_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM engagements WHERE id = ?", (engagement_id,))

    def claim_due(self, now: float, retry_after_s: float = 600.0) -> sqlite3.Row | None:
        """Réserve atomiquement un engagement arrivé à échéance. Un seul déclencheur peut l'obtenir."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM engagements WHERE status = 'planifie' AND due_at <= ?"
                " AND (last_attempt_at IS NULL OR last_attempt_at < ?) ORDER BY due_at LIMIT 1",
                (now, now - retry_after_s)).fetchone()
            if not row:
                return None
            self._db.execute(
                "UPDATE engagements SET status = 'en_preparation', attempts = attempts + 1, last_attempt_at = ?"
                " WHERE id = ? AND status = 'planifie'", (now, row["id"]))
            return self._db.execute("SELECT * FROM engagements WHERE id = ?", (row["id"],)).fetchone()

    def release_engagement(self, engagement_id: int, status: str) -> None:
        self._run("UPDATE engagements SET status = ? WHERE id = ?", (status, engagement_id))

    def add_draft(self, engagement_id: int, user_id: int, target: str, body: str, fingerprint: str) -> int:
        cur = self._run(
            "INSERT INTO drafts(engagement_id, user_id, target, body, fingerprint, status, created_at)"
            " VALUES (?,?,?,?,?,'en_attente',?)",
            (engagement_id, user_id, target, body, fingerprint, time.time()),
        )
        return int(cur.lastrowid or 0)

    def drafts(self, user_id: int | None = None) -> list[sqlite3.Row]:
        if user_id is None:
            return self._all("SELECT * FROM drafts ORDER BY created_at")
        return self._all("SELECT * FROM drafts WHERE user_id = ? ORDER BY created_at", (user_id,))

    def draft(self, draft_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM drafts WHERE id = ?", (draft_id,))

    def decide_draft(self, draft_id: int, approve: bool, user_id: int, expected_fingerprint: str) -> str:
        """Décide d'un brouillon. Refuse si le contenu a changé depuis l'affichage."""
        with self._lock:
            row = self._db.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if not row:
                return "inconnu"
            if row["status"] != "en_attente":
                return "deja_decide"
            if not hmac.compare_digest(row["fingerprint"], expected_fingerprint):
                return "contenu_modifie"
            status = "approuve" if approve else "refuse"
            self._db.execute("UPDATE drafts SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
                             (status, time.time(), user_id, draft_id))
            self._db.execute("UPDATE engagements SET status = ? WHERE id = ?", (status, row["engagement_id"]))
            return status

    def set_delivery_note(self, draft_id: int, note: str) -> None:
        self._run("UPDATE drafts SET delivery = ? WHERE id = ?", (note, draft_id))

    def user_by_id(self, user_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM users WHERE id = ?", (user_id,))

    def user_for_hermes_session(self, hermes_session_id: str) -> sqlite3.Row | None:
        return self._one("SELECT u.* FROM conversations c JOIN users u ON u.id = c.user_id"
                         " WHERE c.hermes_session_id = ?", (hermes_session_id,))

    def mark_delivery(self, draft_id: int, delivery: str, ok: bool) -> None:
        with self._lock:
            row = self._db.execute("SELECT engagement_id FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            self._db.execute("UPDATE drafts SET delivery = ? WHERE id = ?", (delivery, draft_id))
            if row:
                self._db.execute("UPDATE engagements SET status = ? WHERE id = ?",
                                 ("envoye" if ok else "echec", row["engagement_id"]))

    def audit(self, user_id: int | None, action: str, detail: str = "") -> None:
        self._run("INSERT INTO audit(ts, user_id, action, detail) VALUES (?,?,?,?)",
                  (time.time(), user_id, action, detail[:500]))

    def audit_rows(self) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM audit ORDER BY id")
