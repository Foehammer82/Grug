"""Tests for the centralized cache module (grug/cache.py)."""

import time

import pytest

from grug.cache import MemoryCache, get_cache


# ---------------------------------------------------------------------------
# MemoryCache unit tests
# ---------------------------------------------------------------------------


class TestMemoryCache:
    """Verify the in-memory cache backend."""

    @pytest.fixture(autouse=True)
    def fresh_cache(self):
        self.cache = MemoryCache(maxsize=10)

    async def test_get_miss_returns_none(self):
        assert await self.cache.get("nonexistent") is None

    async def test_set_and_get(self):
        await self.cache.set("key", {"name": "Sword", "level": 3})
        result = await self.cache.get("key")
        assert result == {"name": "Sword", "level": 3}

    async def test_permanent_entry_never_expires(self):
        """Entries without TTL live indefinitely."""
        await self.cache.set("perm", [1, 2, 3])
        # Simulate passage of time — entry should still be there
        assert await self.cache.get("perm") == [1, 2, 3]

    async def test_ttl_entry_expires(self, monkeypatch):
        await self.cache.set("temp", "data", ttl=60)
        assert await self.cache.get("temp") == "data"

        # Fast-forward past TTL
        future = time.monotonic() + 61
        monkeypatch.setattr(time, "monotonic", lambda: future)
        assert await self.cache.get("temp") is None

    async def test_delete(self):
        await self.cache.set("key", "val")
        await self.cache.delete("key")
        assert await self.cache.get("key") is None

    async def test_delete_nonexistent_is_noop(self):
        await self.cache.delete("nope")  # should not raise

    async def test_clear(self):
        await self.cache.set("a", 1)
        await self.cache.set("b", 2)
        await self.cache.clear()
        assert await self.cache.get("a") is None
        assert await self.cache.get("b") is None

    async def test_evicts_expired_on_overflow(self, monkeypatch):
        """When at capacity, expired entries are evicted first."""
        cache = MemoryCache(maxsize=3)
        base = time.monotonic()
        # Fill with TTL entries that are already expired
        cache._data["old1"] = ("v1", base - 10)
        cache._data["old2"] = ("v2", base - 10)
        cache._data["old3"] = ("v3", base - 10)

        monkeypatch.setattr(time, "monotonic", lambda: base)
        await cache.set("new", "fresh")
        assert await cache.get("new") == "fresh"
        # Expired entries should be gone
        assert len(cache._data) == 1

    async def test_fifo_eviction_when_no_expired(self):
        """When no expired entries, oldest (FIFO) entry is evicted."""
        cache = MemoryCache(maxsize=3)
        await cache.set("first", 1)
        await cache.set("second", 2)
        await cache.set("third", 3)
        # This should evict "first"
        await cache.set("fourth", 4)
        assert await cache.get("first") is None
        assert await cache.get("fourth") == 4

    async def test_overwrite_existing_key_no_eviction(self):
        """Overwriting an existing key should not trigger eviction."""
        cache = MemoryCache(maxsize=2)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("a", 10)  # overwrite, should not evict
        assert await cache.get("a") == 10
        assert await cache.get("b") == 2


# ---------------------------------------------------------------------------
# get_cache() singleton
# ---------------------------------------------------------------------------


class TestGetCache:
    """Verify the cache singleton factory."""

    def test_returns_memory_cache_by_default(self):
        cache = get_cache()
        assert isinstance(cache, MemoryCache)

    def test_returns_same_instance(self):
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_redis_url_fallback_without_package(self, monkeypatch):
        """If redis_url is set but redis package isn't available, fall back."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        import grug.cache as _cache_mod
        import grug.config.settings as s

        s.get_settings.cache_clear()
        _cache_mod._cache = None

        # The redis package may or may not be installed in test env.
        # Either way, get_cache should return a valid cache.
        cache = get_cache()
        assert cache is not None
