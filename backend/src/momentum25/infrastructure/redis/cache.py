"""Caching abstraction backed by Redis.

Business caching is intentionally not implemented yet; this provides the generic
get/set/delete primitive that future caches (e.g. latest rankings) will build on.
"""

from __future__ import annotations

from typing import Protocol, cast, runtime_checkable

import redis.asyncio as redis


@runtime_checkable
class Cache(Protocol):
    """A minimal string cache abstraction."""

    async def get(self, key: str) -> str | None:
        """Return the cached value for ``key`` or ``None``."""
        ...

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Cache ``value`` under ``key`` with an optional TTL."""
        ...

    async def delete(self, key: str) -> None:
        """Remove ``key`` from the cache."""
        ...


class RedisCache:
    """Redis-backed :class:`Cache` implementation."""

    def __init__(self, client: redis.Redis, *, namespace: str = "m25") -> None:
        """Bind the cache to a Redis client and key namespace."""
        self._client = client
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}:{key}"

    async def get(self, key: str) -> str | None:
        """Return the cached value for ``key`` or ``None``."""
        return cast("str | None", await self._client.get(self._k(key)))

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Cache ``value`` under ``key`` with an optional TTL."""
        await self._client.set(self._k(key), value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        """Remove ``key`` from the cache."""
        await self._client.delete(self._k(key))
