import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(UTC).isoformat()


def new_id():
    return str(uuid4())


class Database:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "eval.db"
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                    role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL,
                    expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS catalog (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, version INTEGER NOT NULL,
                    body TEXT NOT NULL, secret TEXT, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
                    created TEXT NOT NULL, PRIMARY KEY(id,version));
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, snapshot TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '{}', created TEXT NOT NULL,
                    finished TEXT, cancelled INTEGER NOT NULL DEFAULT 0, parent_id TEXT,
                    schedule_key TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS results (
                    run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(run_id,ordinal));
                CREATE TABLE IF NOT EXISTS schedule_state (
                    id TEXT PRIMARY KEY, next_due TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, at TEXT NOT NULL, user_id TEXT, action TEXT NOT NULL,
                    entity_id TEXT);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def audit(self, user_id, action, entity_id=None):
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit(at,user_id,action,entity_id) VALUES(?,?,?,?)",
                (now(), user_id, action, entity_id),
            )

    def list_catalog(self, kind):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM catalog WHERE kind=? ORDER BY created DESC", (kind,)
            ).fetchall()
        return [self.public(row) for row in rows]

    def get_catalog(self, kind, id, internal=False):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM catalog WHERE kind=? AND id=?", (kind, id)
            ).fetchone()
        if not row:
            raise KeyError(id)
        result = self.public(row)
        if internal:
            result["_secret"] = row["secret"]
        return result

    @staticmethod
    def public(row):
        return {
            **json.loads(row["body"]),
            "id": row["id"],
            "version": row["version"],
            "created": row["created"],
            "has_secret": bool(row["secret"]),
        }

    def save_catalog(self, kind, body, id=None, secret=None):
        id = id or new_id()
        with self.connect() as connection:
            old = connection.execute("SELECT * FROM catalog WHERE id=?", (id,)).fetchone()
            version = old["version"] + 1 if old else 1
            encrypted = secret if secret is not None else old["secret"] if old else None
            created = old["created"] if old else now()
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False)
            connection.execute(
                "INSERT OR REPLACE INTO catalog VALUES(?,?,?,?,?,?)",
                (id, kind, version, encoded, encrypted, created),
            )
            connection.execute(
                "INSERT INTO versions VALUES(?,?,?,?)", (id, version, encoded, now())
            )
        return self.get_catalog(kind, id)
