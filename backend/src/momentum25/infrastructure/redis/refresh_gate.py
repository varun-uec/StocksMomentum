"""Redis-backed per-symbol refresh cooldown for the live lookup endpoint (Phase 1.3).

Prevents ``GET /stocks/{symbol}/live?refresh=true`` from triggering an NSE
round-trip on every request -- naive per-request scraping is exactly what NSE
will detect and block (backlog item 1.3).
"""

from __future__ import annotations

import redis.asyncio as redis
from structlog import get_logger

from momentum25.application.use_cases.stocks import RefreshGate

_logger = get_logger("live_refresh_gate")


class RedisRefreshGate(RefreshGate):
    """Refresh gate backed by a Redis key with a TTL.

    Every call is wrapped so a Redis outage degrades to "no cooldown"
    (behaves like the base no-op ``RefreshGate``), never a request failure.
    """

    def __init__(
        self, client: redis.Redis, *, cooldown_seconds: int, namespace: str = "m25"
    ) -> None:
        """Bind the gate to a Redis client, cooldown window, and key namespace."""
        self._client = client
        self._cooldown_seconds = cooldown_seconds
        self._ns = namespace

    def _key(self, symbol: str) -> str:
        return f"{self._ns}:live:refresh:{symbol.upper()}"

    async def should_refresh(self, symbol: str) -> bool:
        """Return ``True`` if *symbol* is outside its refresh cooldown window."""
        try:
            exists = await self._client.exists(self._key(symbol))
            return not bool(exists)
        except Exception as exc:
            _logger.warning("refresh_gate_check_failed", symbol=symbol, error=str(exc))
            return True

    async def mark_refreshed(self, symbol: str) -> None:
        """Start the cooldown window for *symbol*."""
        try:
            await self._client.set(self._key(symbol), "1", ex=self._cooldown_seconds)
        except Exception as exc:
            _logger.warning("refresh_gate_mark_failed", symbol=symbol, error=str(exc))
