"""Redis client lifecycle management."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis

from momentum25.infrastructure.config.settings import get_settings


class RedisProvider:
    """Owns a single async Redis connection pool for the application."""

    def __init__(self, url: str) -> None:
        """Create the Redis client from a connection URL."""
        self._client: redis.Redis = redis.from_url(url, decode_responses=True)

    @property
    def client(self) -> redis.Redis:
        """Return the underlying async Redis client."""
        return self._client

    async def ping(self) -> bool:
        """Return ``True`` if Redis responds to PING (used by health checks)."""
        return bool(await self._client.ping())

    async def close(self) -> None:
        """Close the connection pool (graceful shutdown)."""
        await self._client.aclose()


@lru_cache(maxsize=1)
def get_redis_provider() -> RedisProvider:
    """Return the cached :class:`RedisProvider` singleton."""
    return RedisProvider(get_settings().redis_url)
