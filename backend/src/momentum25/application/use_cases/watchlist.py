"""Watchlist use cases (Phase 6.9)."""

from __future__ import annotations

from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import SecurityRepository, WatchlistRepository


async def _resolve_security_id(securities: SecurityRepository, symbol: str) -> int:
    """Return the security id for ``symbol``, or raise :class:`NotFoundError`."""
    security = await securities.get_by_symbol(symbol)
    if security is None or security.id is None:
        raise NotFoundError(f"Security not found: {symbol}")
    return security.id


class GetWatchlist:
    """Return the watchlisted symbols."""

    def __init__(self, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._watchlist = watchlist

    async def execute(self) -> list[str]:
        """Return the watchlisted symbols, oldest addition first."""
        return await self._watchlist.list_symbols()


class AddToWatchlist:
    """Add a symbol to the watchlist."""

    def __init__(self, securities: SecurityRepository, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._watchlist = watchlist

    async def execute(self, symbol: str) -> None:
        """Add ``symbol``; idempotent, raises if the symbol is unknown."""
        await self._watchlist.add(await _resolve_security_id(self._securities, symbol))


class RemoveFromWatchlist:
    """Remove a symbol from the watchlist."""

    def __init__(self, securities: SecurityRepository, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._watchlist = watchlist

    async def execute(self, symbol: str) -> None:
        """Remove ``symbol``; idempotent, raises if the symbol is unknown."""
        await self._watchlist.remove(await _resolve_security_id(self._securities, symbol))
