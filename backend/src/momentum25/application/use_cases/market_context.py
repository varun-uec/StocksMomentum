"""Universe-level market context: breadth and sector relative strength (Phase 6.6/6.7).

Index-level, not per-stock: these figures describe the tracked universe as a
whole and are never attached to, or used to score, an individual security.

Both panels read the same trailing year of universe closes, so they are computed
in one use case from one bulk fetch rather than two -- the query is the expensive
part, and running it twice would also allow the two panels to disagree about the
universe they describe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.analytics.market_context import (
    BREADTH_52W_WINDOW,
    MarketBreadth,
    SectorRelativeStrength,
    compute_market_breadth,
    compute_sector_relative_strength,
    relative_strength_vs_index,
)
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import (
    BenchmarkIndexRepository,
    OHLCVRepository,
    SecurityRepository,
)

# Calendar days fetched to guarantee BREADTH_52W_WINDOW *trading* sessions.
# ~252 sessions span ~365 calendar days; the margin absorbs holidays and any
# gap in ingestion without ever truncating a real 52-week window.
_CALENDAR_LOOKBACK_DAYS = 500

# Why the sector panel is empty. The endpoint reports this rather than letting
# the client infer it: SectorStrengthTable used to blame missing benchmark
# history while benchmark_index_daily held 2858 rows and the real cause was
# securities.sector being NULL for all 3235 rows (2026-08-09 audit §1.2.8).
NO_SECTOR_CLASSIFICATION = "no_sector_classification"
NO_BENCHMARK_HISTORY = "no_benchmark_history"


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Breadth counts and sector relative-strength ranking for one date."""

    as_of: date
    benchmark_index: str | None
    breadth: MarketBreadth
    sectors: tuple[SectorRelativeStrength, ...] = field(default_factory=tuple)
    sectors_unavailable_reason: str | None = None


class GetMarketContext:
    """Compute universe breadth and sector relative strength as of the latest bar."""

    def __init__(
        self,
        securities: SecurityRepository,
        ohlcv_repo: OHLCVRepository,
        benchmark_repo: BenchmarkIndexRepository,
        benchmark_index: str,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv_repo = ohlcv_repo
        self._benchmark_repo = benchmark_repo
        self._benchmark_index = benchmark_index

    async def execute(self, as_of: date | None = None) -> MarketContext:
        """Return the market context as of ``as_of`` (default: the latest stored bar).

        Defaulting to the latest *stored* bar date rather than today keeps the
        panel honest on weekends, holidays and during an ingestion outage: it
        reports the last session actually measured instead of an empty one.
        """
        latest = await self._ohlcv_repo.latest_date()
        if latest is None:
            raise NotFoundError("No price history has been ingested yet.")

        # A date before the first stored bar produced HTTP 200 with
        # `evaluated: 0`, which reads as a real zero rather than "we have no
        # data for that day" (2026-08-09 audit §1.2.12). The rest of the API
        # returns a crisp 404 in this situation; so does this now.
        if as_of is not None:
            earliest = await self._ohlcv_repo.earliest_date()
            if earliest is not None and as_of < earliest:
                raise NotFoundError(
                    f"No price history on or before {as_of.isoformat()}; "
                    f"the earliest stored bar is {earliest.isoformat()}."
                )
        reference_date = as_of or latest

        universe = await self._securities.list_active()
        symbol_by_id = {s.id: str(s.symbol) for s in universe if s.id is not None}
        sector_by_symbol = {str(s.symbol): s.sector for s in universe if s.id is not None}

        closes_by_id = await self._ohlcv_repo.closes_between(
            reference_date - timedelta(days=_CALENDAR_LOOKBACK_DAYS), reference_date
        )

        closes_by_symbol: dict[str, list[Decimal]] = {}
        dated_by_symbol: dict[str, dict[date, Decimal]] = {}
        for security_id, rows in closes_by_id.items():
            symbol = symbol_by_id.get(security_id)
            if symbol is None:
                continue
            # Breadth is defined on exactly the trailing 52 weeks; the relative-
            # strength series keeps the full fetch, because a 12-month return
            # needs 253 closes -- one more than the 252-session breadth window.
            closes_by_symbol[symbol] = [close for _, close in rows[-BREADTH_52W_WINDOW:]]
            dated_by_symbol[symbol] = dict(rows)

        breadth = compute_market_breadth(reference_date, closes_by_symbol)

        index_closes = await self._benchmark_repo.get_close_series(self._benchmark_index)
        sectors: tuple[SectorRelativeStrength, ...] = ()
        has_sector_classification = any(v for v in sector_by_symbol.values())
        if index_closes and has_sector_classification:
            excess_by_symbol = {
                symbol: {
                    point.period: point.excess_return_pct
                    for point in relative_strength_vs_index(stock_closes, index_closes)
                }
                for symbol, stock_closes in dated_by_symbol.items()
            }
            sectors = compute_sector_relative_strength(excess_by_symbol, sector_by_symbol)

        # Benchmark history is checked second because sector classification is
        # the binding constraint in practice: it is unavailable from any free
        # NSE source, so the panel stays empty even with a full index history.
        reason: str | None = None
        if not sectors:
            reason = (
                NO_BENCHMARK_HISTORY if not index_closes else NO_SECTOR_CLASSIFICATION
            )

        return MarketContext(
            as_of=reference_date,
            benchmark_index=self._benchmark_index if index_closes else None,
            breadth=breadth,
            sectors=sectors,
            sectors_unavailable_reason=reason,
        )
