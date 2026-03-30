"""Tests for the cache store."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from papercheck.cache.store import CacheStore


@pytest.fixture
def cache(tmp_path: Path) -> CacheStore:
    store = CacheStore(tmp_path / "test_cache.db", default_ttl_hours=1)
    yield store
    store.close()


class TestCacheStore:
    def test_set_and_get(self, cache: CacheStore):
        cache.set("test:key", b"hello")
        assert cache.get("test:key") == b"hello"

    def test_get_missing_returns_none(self, cache: CacheStore):
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self, cache: CacheStore):
        # Set with 0-hour TTL (immediately expired)
        cache.set("test:expired", b"data", ttl_hours=0)
        # Need a tiny delay so time check fails
        time.sleep(0.01)
        assert cache.get("test:expired") is None

    def test_invalidate(self, cache: CacheStore):
        cache.set("test:remove", b"data")
        cache.invalidate("test:remove")
        assert cache.get("test:remove") is None

    def test_clear_expired(self, cache: CacheStore):
        cache.set("test:keep", b"keep", ttl_hours=999)
        cache.set("test:expire", b"gone", ttl_hours=0)
        time.sleep(0.01)
        count = cache.clear_expired()
        assert count == 1
        assert cache.get("test:keep") == b"keep"

    def test_stats(self, cache: CacheStore):
        cache.set("a", b"1")
        cache.set("b", b"2")
        s = cache.stats()
        assert s["total_entries"] == 2
        assert s["size_bytes"] > 0

    def test_overwrite(self, cache: CacheStore):
        cache.set("test:key", b"v1")
        cache.set("test:key", b"v2")
        assert cache.get("test:key") == b"v2"
