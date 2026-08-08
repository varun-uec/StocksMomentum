"""Chart-pattern detection use case (Phase 8) — fetch bars, detect, return.

Orchestration only: detection is pure domain logic in
``domain/analytics/chart_patterns.py``. Bars come from the same
:class:`OHLCVRepository` path the live stock analysis and Elliott Wave
labelling use, not a second ingestion route.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.analytics.chart_patterns import (
    ChartPatternAnalysis,
    detect_chart_patterns,
)
from momentum25.domain.analytics.elliott_wave import DEFAULT_ZIGZAG_THRESHOLD_PCT
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import OHLCVRepository, SecurityRepository

DEFAULT_LOOKBACK_DAYS = 500


class DetectChartPatterns:
    """Detect classical chart patterns in a symbol's stored daily price history."""

    def __init__(self, securities: SecurityRepository, ohlcv: OHLCVRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv

    async def execute(
        self,
        symbol: str,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
        as_of: date | None = None,
    ) -> ChartPatternAnalysis:
        """Return every pattern candidate the stored history supports."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        series = await self._ohlcv.get_series(
            security.id, lookback_days=lookback_days, as_of=as_of or date.today()
        )
        return detect_chart_patterns(symbol.upper(), series.bars, threshold_pct)
