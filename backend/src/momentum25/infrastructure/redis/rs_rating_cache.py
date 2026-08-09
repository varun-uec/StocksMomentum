"""Redis-backed cache for one day's universe RS ratings.

``compute_universe_rs_ratings`` walks every active security's price history
(~2,000 symbols) -- cheap once, expensive if repeated per watchlist request.
Keyed by (trading date, strategy) so it never serves a stale rating across
days, and degrades to "no cache" on any Redis error, matching
:class:`RedisRefreshGate`.
"""

from __future__ import annotations

import json
from datetime import date

import redis.asyncio as redis
from structlog import get_logger

_logger = get_logger("rs_rating_cache")

_TTL_SECONDS = 6 * 60 * 60  # a trading date's ratings don't change intraday


class RedisRsRatingCache:
    """Caches ``{symbol: rating}`` for one (as_of, strategy_name) pair."""

    def __init__(self, client: redis.Redis, *, namespace: str = "m25") -> None:
        """Bind the cache to a Redis client and key namespace."""
        self._client = client
        self._ns = namespace

    def _key(self, as_of: date, strategy_name: str) -> str:
        return f"{self._ns}:rs_ratings:{strategy_name}:{as_of.isoformat()}"

    async def get(self, as_of: date, strategy_name: str) -> dict[str, int] | None:
        """Return the cached ratings for *as_of*/*strategy_name*, or ``None`` on a miss."""
        try:
            raw = await self._client.get(self._key(as_of, strategy_name))
        except Exception as exc:
            _logger.warning("rs_rating_cache_get_failed", error=str(exc))
            return None
        if raw is None:
            return None
        return {k: int(v) for k, v in json.loads(raw).items()}

    async def set(self, as_of: date, strategy_name: str, ratings: dict[str, int]) -> None:
        """Cache *ratings* for *as_of*/*strategy_name*."""
        try:
            await self._client.set(
                self._key(as_of, strategy_name), json.dumps(ratings), ex=_TTL_SECONDS
            )
        except Exception as exc:
            _logger.warning("rs_rating_cache_set_failed", error=str(exc))
