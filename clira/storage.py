import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from .config import CliraError


def now():
    return datetime.now(UTC).isoformat()


def uid(prefix):
    return prefix + "_" + uuid.uuid4().hex


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS channels(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL, profile TEXT NOT NULL,
 connection TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS records(
 id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id), kind TEXT NOT NULL,
 data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_channel_kind ON records(channel_id,kind);
CREATE TABLE IF NOT EXISTS conversations(
 id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id), messages TEXT NOT NULL,
 updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(
 id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id), operation TEXT NOT NULL,
 payload TEXT NOT NULL, payload_hash TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, approved_by TEXT, used_at TEXT);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id), operation TEXT NOT NULL,
 payload TEXT NOT NULL, approval_id TEXT REFERENCES approvals(id), state TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE, attempts INTEGER NOT NULL DEFAULT 0,
 result TEXT, last_error TEXT, next_run_at TEXT, lease_until TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_running_channel ON jobs(channel_id) WHERE state='RUNNING';
CREATE TABLE IF NOT EXISTS audit_events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, channel_id TEXT,
 actor TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT, decision TEXT NOT NULL,
 metadata TEXT NOT NULL, at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
 BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
 BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO migrations VALUES(1,?)", (now(),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, params=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, params)]

    def execute(self, sql, params=()):
        with self.connect() as db:
            return db.execute(sql, params).rowcount

    def channel(self, channel_id):
        rows = self.rows("SELECT * FROM channels WHERE id=?", (channel_id,))
        if not rows:
            raise CliraError("CHANNEL_NOT_FOUND", "Select an authorized channel by its immutable ID.")
        row = rows[0]
        row["profile"], row["connection"] = json.loads(row["profile"]), json.loads(row["connection"])
        return row

    def add_channel(self, channel_id, name, mode, profile=None, connection=None):
        self.execute(
            "INSERT INTO channels VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "name=excluded.name, connection=excluded.connection",
            (
                channel_id,
                name,
                mode,
                encode(
                    profile
                    or {
                        "niche": "",
                        "voice": "clear and practical",
                        "language": "English",
                        "timezone": "Asia/Kolkata",
                        "rules": "",
                    }
                ),
                encode(connection or {}),
                now(),
            ),
        )
        return self.channel(channel_id)

    def put(self, channel_id, kind, data, record_id=None):
        self.channel(channel_id)
        record_id = record_id or uid(kind)
        with self.connect() as db:
            old = db.execute("SELECT channel_id,kind FROM records WHERE id=?", (record_id,)).fetchone()
            if old and (old["channel_id"] != channel_id or old["kind"] != kind):
                raise CliraError("CHANNEL_MISMATCH", "This record belongs to another channel or record type.")
            db.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "data=excluded.data,updated_at=excluded.updated_at",
                (record_id, channel_id, kind, encode(data), now(), now()),
            )
        return {**data, "id": record_id, "channel_id": channel_id, "kind": kind}

    def get(self, channel_id, record_id, kind=None):
        rows = self.rows("SELECT * FROM records WHERE channel_id=? AND id=?", (channel_id, record_id))
        if not rows or (kind and rows[0]["kind"] != kind):
            raise CliraError("NOT_FOUND", "Record not found in this channel.")
        r = rows[0]
        return {**json.loads(r["data"]), "id": r["id"], "channel_id": r["channel_id"], "kind": r["kind"]}

    def list(self, channel_id, kind):
        self.channel(channel_id)
        return [
            {**json.loads(r["data"]), "id": r["id"], "channel_id": channel_id, "kind": kind}
            for r in self.rows(
                "SELECT * FROM records WHERE channel_id=? AND kind=? ORDER BY created_at DESC",
                (channel_id, kind),
            )
        ]

    def audit(self, channel_id, action, decision, object_id=None, metadata=None, actor="owner"):
        # Callers supply structural metadata, never API bodies, tokens, or comment text.
        self.execute(
            "INSERT INTO audit_events(id,channel_id,actor,action,object_id,decision,metadata,at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uid("audit"), channel_id, actor, action, object_id, decision, encode(metadata or {}), now()),
        )

    def setting(self, key, default=None):
        rows = self.rows("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set_setting(self, key, value):
        self.execute(
            "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, encode(value)),
        )

    def consume_budget(self, maximum, prefix="model_calls"):
        key = prefix + ":" + now()[:10]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            count = int(row[0]) if row else 0
            if count >= maximum:
                raise CliraError(
                    "REQUEST_BUDGET", f"Daily {prefix} request cap reached. No further calls made."
                )
            db.execute(
                "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(count + 1)),
            )


class SecretStore:
    """Opaque references only in SQLite. Local owner-only secret files; never exposed through API."""

    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        if directory.stat().st_mode & 0o077:
            raise CliraError("SECRET_PERMISSIONS", "Secret storage must support owner-only permissions.")

    def path(self, ref):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", ref):
            raise CliraError("INVALID_SECRET_REF", "Invalid secret reference.")
        return self.directory / (ref + ".json")

    def put(self, ref, data):
        import os
        import tempfile

        fd, temp = tempfile.mkstemp(dir=self.directory)
        try:
            with os.fdopen(fd, "w") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(encode(data))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path(ref))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def get(self, ref):
        path = self.path(ref)
        if not path.exists():
            raise CliraError("AUTH_REQUIRED", "Credentials missing. Connect this channel with clira connect.")
        if path.stat().st_mode & 0o077:
            raise CliraError("SECRET_PERMISSIONS", "Secret file permissions are too broad.")
        return json.loads(path.read_text())

    def delete(self, ref):
        self.path(ref).unlink(missing_ok=True)
