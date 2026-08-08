"""Elliott Wave analysis use case (Phase 7) — fetch bars, label them, return.

Orchestration only: the labelling itself is pure domain logic in
``domain/analytics/elliott_wave.py``. Bars come from the same
:class:`OHLCVRepository` path the live stock analysis uses, not a second
ingestion route.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.analytics.elliott_wave import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    ElliottWaveAnalysis,
    analyze_elliott_wave,
)
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import OHLCVRepository, SecurityRepository

DEFAULT_LOOKBACK_DAYS = 500


class GetElliottWaveAnalysis:
    """Label the wave structure of a symbol's stored daily price history."""

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
    ) -> ElliottWaveAnalysis:
        """Return the primary (and any alternative) wave count for ``symbol``."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        series = await self._ohlcv.get_series(
            security.id, lookback_days=lookback_days, as_of=as_of or date.today()
        )
        return analyze_elliott_wave(symbol.upper(), series.bars, threshold_pct)
