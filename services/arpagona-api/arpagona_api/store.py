"""Stockage SQLite de l'API ARPAGONA : utilisateurs, sessions web, conversations, journal."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time

from .engagements import fingerprint, mail_fingerprint
from email.utils import make_msgid

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'membre' CHECK (role IN ('admin', 'membre')),
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
    closed_at REAL,
    closed_reason TEXT,
    parent_id INTEGER REFERENCES conversations(id)
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
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    run_id TEXT,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('en_cours', 'terminee', 'echouee', 'arretee')),
    created_at REAL NOT NULL,
    ended_at REAL,
    cost_usd REAL,
    result TEXT,
    stop_reason TEXT
);
CREATE INDEX IF NOT EXISTS missions_user ON missions(user_id, created_at);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""

SESSION_TTL_S = 90 * 24 * 3600  # téléphone personnel : une connexion tous les 90 jours
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
            from .budget import BudgetLedger
            self.budget = BudgetLedger(self._db, self._lock)
            # Une seule conversation ouverte par compte ; /new ferme la précédente.
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS conversations_open"
                             " ON conversations(user_id) WHERE closed_at IS NULL")

    def _migrate(self) -> None:
        """Bases antérieures : une conversation par compte (user_id UNIQUE), sans closed_at.

        SQLite ne sait pas retirer une contrainte : la table est reconstruite à l'identique,
        mêmes identifiants, dans une transaction. Les messages gardent leur conversation.
        """
        cols = [r["name"] for r in self._db.execute("PRAGMA table_info(conversations)")]
        if "closed_at" not in cols:
            self._migrate_legacy()
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(conversations)")}
        for name, kind in (("closed_reason", "TEXT"), ("parent_id", "INTEGER REFERENCES conversations(id)")):
            if name not in cols:
                self._db.execute(f"ALTER TABLE conversations ADD COLUMN {name} {kind}")
        # Aucun privilège ajouté par migration/restart : l'opérateur nomme
        # explicitement l'admin avec manage set-role (le plus ancien peut être une démo).
        user_cols = {r["name"] for r in self._db.execute("PRAGMA table_info(users)")}
        if "role" not in user_cols:
            self._db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'membre'")
        draft_cols = {r['name'] for r in self._db.execute('PRAGMA table_info(drafts)')}
        for name, kind in (("subject", "TEXT"), ("sender", "TEXT"), ("send_message_id", "TEXT")):
            if name not in draft_cols:
                self._db.execute(f'ALTER TABLE drafts ADD COLUMN {name} {kind}')

    def _migrate_legacy(self) -> None:
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
    def add_user(self, login: str, display_name: str, password: str, role: str = "membre") -> int:
        if len(password) < 12:
            raise ValueError("mot de passe trop court (12 caractères minimum)")
        if role not in ("admin", "membre"):
            raise ValueError("rôle invalide")
        salt = secrets.token_bytes(16)
        # SQLite peut réutiliser un INTEGER PRIMARY KEY supprimé. L'audit conservé
        # porterait alors les événements d'un ancien compte vers le nouveau : interdit.
        # Allocation et rôle du premier compte dans UNE instruction SQLite sérialisée.
        cur = self._run(
            "INSERT INTO users(id, login, display_name, role, pw_salt, pw_hash, created_at)"
            " VALUES ((SELECT COALESCE(MAX(v),0)+1 FROM (SELECT id AS v FROM users"
            " UNION ALL SELECT user_id AS v FROM audit UNION ALL SELECT user_id AS v FROM budget_entries)),?,?,"
            " CASE WHEN EXISTS(SELECT 1 FROM users) THEN ? ELSE 'admin' END,?,?,?)",
            (login, display_name, role, salt, _hash_password(password, salt), time.time()),
        )
        return int(cur.lastrowid or 0)

    def set_role(self, login: str, role: str) -> bool:
        if role not in ("admin", "membre"):
            raise ValueError("rôle invalide")
        with self._lock:
            row = self._db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
            if not row:
                return False
            if role == "membre":
                # Ne jamais laisser une instance sans administrateur.
                admins = self._db.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"]
                if admins <= 1 and self._db.execute(
                        "SELECT role FROM users WHERE id = ?", (row["id"],)).fetchone()["role"] == "admin":
                    raise ValueError("dernier administrateur : nommer un autre admin d'abord")
            self._db.execute("UPDATE users SET role = ? WHERE id = ?", (role, row["id"]))
        return True

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
                self._db.execute("DELETE FROM missions WHERE user_id = ?", (uid,))
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

    def new_conversation(self, user_id: int, reason: str = "manual", now: float | None = None) -> sqlite3.Row:
        """/new : ferme la conversation ouverte et en ouvre une neuve, avec une nouvelle session Hermès.

        L'ancienne reste en base (historique, engagements liés) mais n'est plus jamais envoyée au moteur.
        La mémoire d'équipe (Hindsight) n'est pas touchée : elle appartient à l'instance (ADR 0008).
        """
        if reason not in ("manual", "idle", "daily"):
            raise ValueError("raison de fermeture invalide")
        now = time.time() if now is None else now
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                old = self._db.execute("SELECT id FROM conversations WHERE user_id = ? AND closed_at IS NULL", (user_id,)).fetchone()
                self._db.execute("UPDATE conversations SET closed_at = ?, closed_reason = ? WHERE user_id = ? AND closed_at IS NULL",
                                 (now, reason, user_id))
                self._db.execute("INSERT INTO conversations(user_id, hermes_session_id, created_at, parent_id) VALUES (?,?,?,?)",
                                 (user_id, self._new_session_id(user_id), now, old["id"] if old else None))
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
                    run_id: str | None = None, created_at: float | None = None) -> int:
        cur = self._run(
            "INSERT INTO messages(conversation_id, role, content, status, run_id, created_at) VALUES (?,?,?,?,?,?)",
            (conversation_id, role, content, status, run_id, time.time() if created_at is None else created_at),
        )
        return int(cur.lastrowid or 0)

    def set_run_id(self, message_id: int, run_id: str) -> None:
        self._run("UPDATE messages SET run_id = ? WHERE id = ?", (run_id, message_id))

    def settle_message(self, message_id: int, content: str, status: str) -> None:
        self._run("UPDATE messages SET content = ?, status = ? WHERE id = ? AND status = 'pending'",
                  (content, status, message_id))

    def messages(self, conversation_id: int) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))

    def conversation_by_id(self, conversation_id: int, user_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))

    def visible_messages(self, conv: sqlite3.Row) -> list[sqlite3.Row]:
        chain = [conv["id"]]
        while conv["parent_id"] and len(chain) < 10000:
            parent = self.conversation_by_id(conv["parent_id"], conv["user_id"])
            if not parent or parent["closed_reason"] not in ("idle", "daily") or parent["id"] in chain:
                break
            chain.append(parent["id"])
            conv = parent
        rows = []
        for cid in chain:
            rows.extend(reversed(self.messages(cid)))
            if len(rows) >= 200:
                break
        return list(reversed(rows[:200]))

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

    def add_draft(self, engagement_id: int, user_id: int, target: str, body: str, fingerprint: str,
                  subject: str | None = None, sender: str | None = None) -> int:
        cur = self._run(
            "INSERT INTO drafts(engagement_id, user_id, target, body, fingerprint, status, created_at, subject, sender)"
            " VALUES (?,?,?,?,?,'en_attente',?,?,?)",
            (engagement_id, user_id, target, body, fingerprint, time.time(), subject, sender),
        )
        return int(cur.lastrowid or 0)

    def drafts(self, user_id: int | None = None) -> list[sqlite3.Row]:
        if user_id is None:
            return self._all("SELECT * FROM drafts ORDER BY created_at")
        return self._all("SELECT * FROM drafts WHERE user_id = ? ORDER BY created_at", (user_id,))

    def draft(self, draft_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM drafts WHERE id = ?", (draft_id,))

    def decide_draft(self, draft_id: int, approve: bool, user_id: int, expected_fingerprint: str) -> str:
        """Décision et engagement atomiques entre processus ; contenu exact revérifié."""
        with self._lock:
            self._db.execute('BEGIN IMMEDIATE')
            try:
                row = self._db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
                if not row:
                    return 'inconnu'
                if row['user_id'] != user_id:
                    return 'interdit'
                if row['status'] != 'en_attente':
                    return 'deja_decide'
                current = (mail_fingerprint(row['target'], row['subject'], row['body'], row['sender'])
                           if row['subject'] is not None and row['sender'] is not None else
                           fingerprint(row['target'], row['body']))
                if not hmac.compare_digest(row['fingerprint'], expected_fingerprint) or not hmac.compare_digest(current, row['fingerprint']):
                    return 'contenu_modifie'
                status = 'approuve' if approve else 'refuse'
                self._db.execute('UPDATE drafts SET status=?, decided_at=?, decided_by=?, delivery=? WHERE id=?',
                    (status, time.time(), user_id, 'approuvé : prêt à envoyer' if approve else 'refusé', draft_id))
                self._db.execute('UPDATE engagements SET status=? WHERE id=?', (status, row['engagement_id']))
                self._db.execute('COMMIT')
                return status
            finally:
                if self._db.in_transaction:
                    self._db.execute('ROLLBACK')

    def set_delivery_note(self, draft_id: int, note: str) -> None:
        self._run("UPDATE drafts SET delivery = ? WHERE id = ? AND send_message_id IS NULL", (note, draft_id))

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

    # --- envoi courriel ---------------------------------------------------
    def claim_send(self, draft_id: int, user_id: int, expected_fingerprint: str,
                   is_admin: bool = False) -> tuple[str, sqlite3.Row | None]:
        """Réserve un brouillon approuvé pour envoi unique, après re-calcul de l'empreinte.

        Renvoie (code, ligne). Codes : ok, inconnu, non_approuve, interdit, contenu_modifie, deja_en_cours.
        """
        with self._lock:
            row = self._db.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if not row:
                return "inconnu", None
            if row["user_id"] != user_id and not is_admin:
                return "interdit", None
            if row["status"] == "envoye" or (row["delivery"] or "").startswith("envoi_en_cours"):
                return "deja_en_cours", row
            if row["status"] != "approuve":
                return "non_approuve", row
            if row['subject'] is None or row['sender'] is None:
                return 'ancien_brouillon', row
            recomputed = mail_fingerprint(row['target'], row['subject'], row['body'], row['sender'])
            if not hmac.compare_digest(recomputed, row["fingerprint"]):
                return "contenu_modifie", row
            if not hmac.compare_digest(row["fingerprint"], expected_fingerprint or ""):
                return "contenu_modifie", row
            # Compare-and-swap SQLite : un seul gagnant, même avec deux Store/processus.
            message_id = make_msgid(domain='arpagona.com')
            cur = self._db.execute(
                "UPDATE drafts SET delivery='envoi_en_cours', send_message_id=?"
                " WHERE id=? AND status='approuve' AND send_message_id IS NULL"
                " AND fingerprint=? AND target=? AND body=? AND subject=? AND sender=?",
                (message_id, draft_id, row['fingerprint'], row['target'], row['body'], row['subject'], row['sender']))
            if cur.rowcount != 1:
                return 'deja_en_cours', row
            return "ok", self._db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()

    def mark_send_uncertain(self, draft_id: int) -> None:
        self._run("UPDATE drafts SET delivery='envoi_inconnu : vérifier manuellement, ne pas réessayer'"
                  " WHERE id=?", (draft_id,))

    def mark_sent(self, draft_id: int, message_id: str) -> None:
        with self._lock:
            row = self._db.execute("SELECT engagement_id FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            self._db.execute("UPDATE drafts SET status = 'envoye', delivery = ? WHERE id = ?",
                             (f"envoyé {message_id}"[:200], draft_id))
            if row:
                self._db.execute("UPDATE engagements SET status = 'envoye' WHERE id = ?", (row["engagement_id"],))

    def mark_send_failed(self, draft_id: int, reason: str) -> None:
        with self._lock:
            row = self._db.execute("SELECT engagement_id FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            self._db.execute("UPDATE drafts SET status = 'echec', delivery = ? WHERE id = ?",
                             (f"échec : {reason}"[:200], draft_id))
            if row:
                self._db.execute("UPDATE engagements SET status = 'echec' WHERE id = ?", (row["engagement_id"],))

    # --- missions ---------------------------------------------------------
    def start_mission(self, user_id: int, conversation_id: int, run_id: str, title: str) -> int:
        cur = self._run(
            "INSERT INTO missions(user_id, conversation_id, run_id, title, status, created_at)"
            " VALUES (?,?,?,?,'en_cours',?)",
            (user_id, conversation_id, run_id, title[:120], time.time()),
        )
        return int(cur.lastrowid or 0)

    def mission(self, mission_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM missions WHERE id = ?", (mission_id,))

    def mission_for_run(self, run_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM missions WHERE run_id = ?", (run_id,))

    def missions(self, user_id: int, limit: int = 50, active_only: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM missions WHERE user_id = ?"
        if active_only:
            sql += " AND status = 'en_cours'"
        return self._all(sql + " ORDER BY id DESC LIMIT ?", (user_id, int(limit)))

    def finish_mission(self, mission_id: int, status: str, result: str = "",
                       cost_usd: float | None = None, stop_reason: str | None = None) -> None:
        if status not in ("terminee", "echouee", "arretee"):
            raise ValueError("statut de mission invalide")
        self._run("UPDATE missions SET status = ?, ended_at = ?, result = ?, cost_usd = ?,"
                  " stop_reason = COALESCE(?, stop_reason) WHERE id = ? AND status = 'en_cours'",
                  (status, time.time(), (result or "")[:20000], cost_usd, stop_reason, mission_id))

    def request_stop(self, mission_id: int, user_id: int, is_admin: bool = False) -> str:
        with self._lock:
            row = self._db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
            if not row:
                return "inconnu"
            if row["user_id"] != user_id and not is_admin:
                return "interdit"
            if row["status"] != "en_cours":
                return "deja_terminee"
            self._db.execute("UPDATE missions SET stop_reason = 'demande' WHERE id = ?", (mission_id,))
            return "ok"

    def cost_since(self, since: float) -> float:
        row = self._one("SELECT COALESCE(SUM(cost_usd), 0) AS total FROM missions WHERE created_at >= ?", (since,))
        return float(row["total"] or 0.0) if row else 0.0

    # --- journal ----------------------------------------------------------
    def audit(self, user_id: int | None, action: str, detail: str = "") -> None:
        self._run("INSERT INTO audit(ts, user_id, action, detail) VALUES (?,?,?,?)",
                  (time.time(), user_id, action, detail[:500]))

    def audit_rows(self, limit: int = 200, user_id: int | None = None) -> list[sqlite3.Row]:
        """Les N événements les plus récents, rendus dans l'ordre chronologique."""
        limit = max(1, min(int(limit), 1000))
        if user_id is None:
            return self._all("SELECT * FROM (SELECT * FROM audit ORDER BY id DESC LIMIT ?) ORDER BY id",
                             (limit,))
        return self._all("SELECT * FROM (SELECT * FROM audit WHERE user_id = ? ORDER BY id DESC LIMIT ?)"
                         " ORDER BY id", (user_id, limit))

    def export_data(self, user_id: int | None = None) -> dict:
        """Export métier : aucune donnée d'authentification (ni sel, ni empreinte, ni session)."""
        def rows(sql: str, args: tuple = ()) -> list[dict]:
            return [dict(r) for r in self._all(sql, args)]
        scope = "" if user_id is None else " WHERE user_id = ?"
        args: tuple = () if user_id is None else (user_id,)
        data = {"format": "arpagona-export-1", "exported_at": time.time()}
        data["users"] = [{k: r[k] for k in ("login", "display_name", "role", "created_at")}
                         for r in rows("SELECT * FROM users" + ("" if user_id is None else " WHERE id = ?"), args)]
        data["conversations"] = rows("SELECT * FROM conversations" + scope, args)
        data["messages"] = rows(
            "SELECT m.* FROM messages m JOIN conversations c ON c.id = m.conversation_id"
            + ("" if user_id is None else " WHERE c.user_id = ?") + " ORDER BY m.id", args)
        data["engagements"] = rows("SELECT * FROM engagements" + scope + " ORDER BY id", args)
        data["drafts"] = rows("SELECT * FROM drafts" + scope + " ORDER BY id", args)
        data["missions"] = rows("SELECT * FROM missions" + scope + " ORDER BY id", args)
        data["budget"] = rows("SELECT * FROM budget_entries" + scope + " ORDER BY created_at,key", args)
        data["audit"] = rows("SELECT * FROM audit" + scope + " ORDER BY id", args)
        return data
