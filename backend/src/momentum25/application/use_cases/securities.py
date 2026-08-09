"""Security price-series use case (for charts)."""

from __future__ import annotations

from datetime import date

from momentum25.application.dto.market_data import (
    OHLCVBarDTO,
    SecurityOHLCVDTO,
    SecuritySearchResultDTO,
)
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import OHLCVRepository, SecurityRepository

DEFAULT_LOOKBACK_DAYS = 500


class SearchSecurities:
    """Return symbol suggestions for a partial query (typeahead)."""

    def __init__(self, securities: SecurityRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities

    async def execute(self, query: str, limit: int) -> list[SecuritySearchResultDTO]:
        """Return up to *limit* matches for *query*, best match first."""
        matches = await self._securities.search(query, limit)
        return [
            SecuritySearchResultDTO(
                symbol=str(s.symbol), name=s.name, sector=s.sector
            )
            for s in matches
        ]


class GetSecurityOHLCV:
    """Return a symbol's OHLCV series for charting."""

    def __init__(self, securities: SecurityRepository, ohlcv: OHLCVRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv

    async def execute(
        self,
        symbol: str,
        from_: date | None = None,
        to: date | None = None,
    ) -> SecurityOHLCVDTO:
        """Return bars in ``[from_, to]``, honouring the full requested range.

        ``lookback_days`` on the repository is a row-count cap, not a calendar
        window, so it is sized from the requested ``from_`` date rather than a
        fixed constant -- otherwise a range older than the default window would
        silently come back truncated instead of covering what was asked for.
        """
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        as_of = to or date.today()
        lookback_days = (as_of - from_).days + 1 if from_ else DEFAULT_LOOKBACK_DAYS
        series = await self._ohlcv.get_series(
            security.id, lookback_days=lookback_days, as_of=as_of
        )
        bars = [
            OHLCVBarDTO(
                date=b.date, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume
            )
            for b in series.bars
            if from_ is None or b.date >= from_
        ]
        return SecurityOHLCVDTO(symbol=str(security.symbol), bars=bars)
