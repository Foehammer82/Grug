"""Centralized caching — in-memory by default, optional Redis / Valkey backend.

Every module that needs caching should use :func:`get_cache` to obtain the
shared cache instance rather than rolling its own dict-based cache.

Usage::

    from grug.cache import get_cache

    cache = get_cache()
    await cache.set("aon:items:5:permanent:20", item_list)          # permanent
    await cache.set("monster:goblin:pf2e:10", results, ttl=300)     # 5-min TTL
    value = await cache.get("aon:items:5:permanent:20")

Backend selection
-----------------
* If ``Settings.redis_url`` is set **and** the ``redis`` package is installed,
  a :class:`RedisCache` is returned.
* Otherwise an in-memory :class:`MemoryCache` is used (default).

Redis / Valkey use the same wire protocol, so either can be used.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Memory backend
# ---------------------------------------------------------------------------


class MemoryCache:
    """Bounded in-memory cache with optional per-key TTL.

    Entries stored *without* a TTL live for the lifetime of the process
    (permanent).  When the cache reaches *maxsize* it evicts expired entries
    first, then falls back to FIFO eviction of the oldest entry.
    """

    def __init__(self, maxsize: int = 4096) -> None:
        self._maxsize = maxsize
        # key → (value, expires_at_monotonic | None)
        self._data: dict[str, tuple[Any, float | None]] = {}

    async def get(self, key: str) -> Any | None:
        """Return the cached value or ``None`` on miss / expiry."""
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        """Store *value* under *key*.  Pass *ttl* in seconds for expiry."""
        if key not in self._data and len(self._data) >= self._maxsize:
            self._evict()
        expires_at = (time.monotonic() + ttl) if ttl is not None else None
        self._data[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Remove *key* if it exists."""
        self._data.pop(key, None)

    async def clear(self) -> None:
        """Drop all entries."""
        self._data.clear()

    # -- internals ---------------------------------------------------------

    def _evict(self) -> None:
        """Remove expired entries first, then FIFO if still at capacity."""
        now = time.monotonic()
        expired = [
            k for k, (_, exp) in self._data.items() if exp is not None and now > exp
        ]
        for k in expired:
            del self._data[k]
        if len(self._data) >= self._maxsize:
            del self._data[next(iter(self._data))]


# ---------------------------------------------------------------------------
# Redis / Valkey backend
# ---------------------------------------------------------------------------


class RedisCache:
    """Redis / Valkey cache backend.

    Requires the ``redis`` package (``pip install redis``).  Data is stored as
    JSON; dataclass instances are auto-converted via ``dataclasses.asdict()``.
    """

    def __init__(self, url: str) -> None:
        import redis.asyncio as _redis

        self._redis: Any = _redis.from_url(url, decode_responses=True)
        self._prefix = "grug:"

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(self._prefix + key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        raw = json.dumps(value, default=_json_default)
        if ttl is not None:
            await self._redis.setex(self._prefix + key, ttl, raw)
        else:
            await self._redis.set(self._prefix + key, raw)

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._prefix + key)

    async def clear(self) -> None:
        """Delete all ``grug:`` prefixed keys."""
        cursor: int | str = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=self._prefix + "*", count=100
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break


def _json_default(obj: Any) -> Any:
    """JSON fallback serialiser for dataclass instances."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache: MemoryCache | RedisCache | None = None


def get_cache() -> MemoryCache | RedisCache:
    """Return the shared cache instance (created on first call).

    If ``Settings.redis_url`` is set *and* the ``redis`` package is
    installed, a :class:`RedisCache` is returned.  Otherwise an
    in-memory :class:`MemoryCache` is used.
    """
    global _cache
    if _cache is not None:
        return _cache

    from grug.config.settings import get_settings

    settings = get_settings()
    redis_url: str = getattr(settings, "redis_url", "") or ""

    if redis_url:
        try:
            _cache = RedisCache(redis_url)
            logger.info("Using Redis/Valkey cache backend")
        except Exception:
            logger.warning(
                "Failed to initialise Redis cache — falling back to in-memory",
                exc_info=True,
            )
            _cache = MemoryCache()
    else:
        _cache = MemoryCache()
        logger.debug("Using in-memory cache backend")

    return _cache
