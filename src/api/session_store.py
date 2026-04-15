"""Persistent session storage for API authentication flows.

Stores session payloads in SQLite so OAuth state and tokens survive process restarts.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

try:
    import psycopg
except Exception:  # pragma: no cover - optional import when postgres is unused
    psycopg = None


class SQLiteSessionStore:
    """Simple SQLite-backed session store with TTL support."""

    def __init__(self, db_path: str, ttl_seconds: int = 60 * 60 * 24 * 30):
        self.db_path = Path(db_path)
        self.ttl_seconds = ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)"
            )
            conn.commit()

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.commit()
            return cur.rowcount or 0

    def get(self, session_id: str) -> Optional[dict[str, Any]]:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT payload, expires_at FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            payload_raw, expires_at = row
            if float(expires_at) < now:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                return None

            try:
                payload = json.loads(payload_raw)
                if not isinstance(payload, dict):
                    return None
                return payload
            except json.JSONDecodeError:
                return None

    def set(self, session_id: str, payload: dict[str, Any]) -> None:
        now = time.time()
        expires_at = now + self.ttl_seconds
        payload_text = json.dumps(payload)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, payload, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (session_id, payload_text, now, now, expires_at),
            )
            conn.commit()

    def delete(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()


class PostgresSessionStore:
    """Postgres-backed session store with TTL support."""

    def __init__(self, database_url: str, ttl_seconds: int = 60 * 60 * 24 * 30):
        if psycopg is None:
            raise RuntimeError("psycopg is required for Postgres session storage")
        self.database_url = database_url
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)"
                )
            conn.commit()

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE expires_at < %s", (now,))
                deleted = cur.rowcount or 0
            conn.commit()
            return deleted

    def get(self, session_id: str) -> Optional[dict[str, Any]]:
        now = time.time()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload, expires_at FROM sessions WHERE id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                payload_raw, expires_at = row
                if float(expires_at) < now:
                    cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                    conn.commit()
                    return None

                try:
                    payload = json.loads(payload_raw)
                    if not isinstance(payload, dict):
                        return None
                    return payload
                except json.JSONDecodeError:
                    return None

    def set(self, session_id: str, payload: dict[str, Any]) -> None:
        now = time.time()
        expires_at = now + self.ttl_seconds
        payload_text = json.dumps(payload)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions (id, payload, created_at, updated_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        updated_at = EXCLUDED.updated_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (session_id, payload_text, now, now, expires_at),
                )
            conn.commit()

    def delete(self, session_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
            conn.commit()


def create_session_store(
    db_path: str,
    ttl_seconds: int = 60 * 60 * 24 * 30,
    database_url: Optional[str] = None,
):
    """Create a persistent session store.

    Uses Postgres when DATABASE_URL is provided, otherwise falls back to SQLite.
    """
    if database_url and database_url.strip():
        return PostgresSessionStore(database_url=database_url.strip(), ttl_seconds=ttl_seconds)
    return SQLiteSessionStore(db_path=db_path, ttl_seconds=ttl_seconds)
