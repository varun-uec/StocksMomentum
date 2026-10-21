"""Security price-series use case (for charts)."""

from __future__ import annotations

from datetime import date, timedelta

from momentum25.application.dto.market_data import (
    AdjustmentStepDTO,
    IndexCloseBarDTO,
    IndexOHLCVDTO,
    Interval,
    OHLCVBarDTO,
    SecurityOHLCVDTO,
    SecuritySearchResultDTO,
)
from momentum25.domain.engine_version import INDICATOR_VERSION
from momentum25.domain.entities.market_data import (
    OHLCVBar,
    OHLCVSeries,
    Period,
    period_bars,
    series_data_version,
)
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import (
    BenchmarkIndexRepository,
    OHLCVRepository,
    SecurityRepository,
)
from momentum25.domain.ports.trading_calendar import TradingCalendar

# With no ``from`` date the chart asks for its whole history (the MAX range).
# The repository caps by row count, so "everything" is a cap no stored series
# reaches: 20,000 sessions is about 80 years of daily bars.
ALL_HISTORY_SESSIONS = 20_000


def interval_bars(
    series: OHLCVSeries, interval: Interval, calendar: TradingCalendar
) -> list[tuple[OHLCVBar, bool]]:
    """Return the series' adjusted bars at ``interval``, each with its ``partial`` flag.

    Weekly and monthly bars aggregate the adjusted daily bars, never raw
    prints, so a period with a split or bonus has no jump inside it
    (ADR-013 §4).
    """
    daily = [b.adjusted() for b in series.bars]
    if interval == "1D" or not daily:
        return [(b, False) for b in daily]
    last = daily[-1].date
    if interval == "1W":
        period_end = last + timedelta(days=6 - last.weekday())
    else:
        period_end = date(last.year + last.month // 12, last.month % 12 + 1, 1) - timedelta(days=1)
    sessions = calendar.sessions_between(daily[0].date, period_end)
    period: Period = "week" if interval == "1W" else "month"
    return [(b.bar, b.partial) for b in period_bars(daily, sessions, period)]


class SearchSecurities:
    """Return symbol suggestions for a partial query (typeahead)."""

    def __init__(self, securities: SecurityRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities

    async def execute(self, query: str, limit: int) -> list[SecuritySearchResultDTO]:
        """Return up to *limit* matches for *query*, best match first."""
        matches = await self._securities.search(query, limit)
        return [
            SecuritySearchResultDTO(symbol=str(s.symbol), name=s.name, sector=s.sector)
            for s in matches
        ]


class GetSecurityOHLCV:
    """Return a symbol's OHLCV series for charting, adjusted for corporate actions.

    The chart shows the same adjusted series that screening reads, so a price on
    the chart and the price behind a rule's verdict always agree (ADR-013 §4).
    """

    def __init__(
        self, securities: SecurityRepository, ohlcv: OHLCVRepository, calendar: TradingCalendar
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv
        self._calendar = calendar

    async def execute(
        self,
        symbol: str,
        from_: date | None = None,
        to: date | None = None,
        interval: Interval = "1D",
        as_of: date | None = None,
    ) -> SecurityOHLCVDTO:
        """Return bars in ``[from_, to]`` and the adjustment schedule of the whole history.

        With ``as_of`` (bar replay), the series is as it stood on that date: no later
        bar, no later corporate action, and a period bar holds only its sessions up
        to that date (see :meth:`OHLCVSeries.as_of`).
        """
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        # The whole history, even for a short range: the adjustment schedule
        # must cover every date a saved drawing can sit on.
        end = min(d for d in (to, as_of, date.today()) if d is not None)
        series = await self._ohlcv.get_series(
            security.id, lookback_days=ALL_HISTORY_SESSIONS, as_of=end
        )
        if as_of is not None:
            series = series.as_of(as_of)
        bars = [
            OHLCVBarDTO(
                date=b.date,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                partial=partial,
            )
            for b, partial in interval_bars(series, interval, self._calendar)
            if from_ is None or b.date >= from_
        ]
        adjustments = [
            AdjustmentStepDTO(until=s.until, factor=s.factor) for s in series.adjustment_schedule()
        ]
        return SecurityOHLCVDTO(
            symbol=str(security.symbol),
            interval=interval,
            data_version=series_data_version(series.bars, INDICATOR_VERSION),
            bars=bars,
            adjustments=adjustments,
        )


class GetIndexCloseSeries:
    """Return a benchmark index's daily close series for charting."""

    def __init__(self, benchmark: BenchmarkIndexRepository) -> None:
        """Wire the use case with its collaborators."""
        self._benchmark = benchmark

    async def execute(
        self,
        index_code: str,
        from_: date | None = None,
        to: date | None = None,
    ) -> IndexOHLCVDTO:
        """Return closes in ``[from_, to]``, oldest first.

        An index with no persisted closes is a missing resource, not an empty
        series: returning ``[]`` would let a chart silently render a flat or
        absent benchmark instead of surfacing that the backfill never ran.
        """
        code = index_code.strip().upper()
        closes = await self._benchmark.get_close_series(code)
        if not closes:
            raise NotFoundError(f"Benchmark index not found: {index_code}")
        bars = [
            IndexCloseBarDTO(date=d, close=c)
            for d, c in sorted(closes.items())
            if (from_ is None or d >= from_) and (to is None or d <= to)
        ]
        return IndexOHLCVDTO(index_code=code, bars=bars)
