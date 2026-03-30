"""SQLite-backed key-value cache with TTL."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class CacheStore:
    """Simple key-value cache backed by SQLite.

    Keys are namespaced strings like "s2:paper:abc123" or "llm:prompt:sha256".
    Values are bytes (callers serialize/deserialize).
    """

    def __init__(self, db_path: Path, default_ttl_hours: int = 168):
        self._db_path = db_path
        self._default_ttl_hours = default_ttl_hours
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                created_at REAL NOT NULL,
                ttl_hours INTEGER NOT NULL
            )"""
        )
        self._conn.commit()

    def get(self, key: str) -> bytes | None:
        """Return cached value or None if missing/expired."""
        row = self._conn.execute(
            "SELECT value, created_at, ttl_hours FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, created_at, ttl_hours = row
        if time.time() - created_at > ttl_hours * 3600:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return value

    def set(self, key: str, value: bytes, ttl_hours: int | None = None) -> None:
        """Store a value in the cache."""
        ttl = ttl_hours if ttl_hours is not None else self._default_ttl_hours
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at, ttl_hours) VALUES (?, ?, ?, ?)",
            (key, value, time.time(), ttl),
        )
        self._conn.commit()

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        self._conn.commit()

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count of deleted rows."""
        now = time.time()
        cursor = self._conn.execute(
            "DELETE FROM cache WHERE (? - created_at) > (ttl_hours * 3600)", (now,)
        )
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        now = time.time()
        expired = self._conn.execute(
            "SELECT COUNT(*) FROM cache WHERE (? - created_at) > (ttl_hours * 3600)",
            (now,),
        ).fetchone()[0]
        page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = self._conn.execute("PRAGMA page_size").fetchone()[0]
        return {
            "total_entries": total,
            "expired_entries": expired,
            "size_bytes": page_count * page_size,
        }

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
