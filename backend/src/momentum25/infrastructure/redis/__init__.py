"""Redis infrastructure: client lifecycle, cache, and distributed lock abstractions.

Redis is exposed only through these abstractions (never used directly by business
code). Caching, job queue, rate limiting, and session storage are future concerns;
this phase provides the seams (ADD §24, Phase-2 brief).
"""

from momentum25.infrastructure.redis.cache import Cache, RedisCache
from momentum25.infrastructure.redis.client import RedisProvider, get_redis_provider
from momentum25.infrastructure.redis.lock import DistributedLock, RedisLockFactory

__all__ = [
    "Cache",
    "DistributedLock",
    "RedisCache",
    "RedisLockFactory",
    "RedisProvider",
    "get_redis_provider",
]
