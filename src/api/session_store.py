"""Persistent session storage for API authentication flows.

Stores session payloads in Postgres so OAuth state and tokens survive restarts.
"""

from __future__ import annotations

import json
import time
from typing import Any

import psycopg


class PostgresSessionStore:
    """Postgres-backed session store with TTL support."""

    def __init__(self, database_url: str, ttl_seconds: int = 60 * 60 * 24 * 30):
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


def create_session_store(database_url: str, ttl_seconds: int = 60 * 60 * 24 * 30):
    """Create a Postgres-backed persistent session store.

    DATABASE_URL is required. No SQLite fallback is supported.
    """
    url = (database_url or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required for session storage")
    return PostgresSessionStore(database_url=url, ttl_seconds=ttl_seconds)
