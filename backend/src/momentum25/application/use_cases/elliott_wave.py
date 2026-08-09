"""Elliott Wave analysis use case — fetch bars and indicators, label them, return.

Orchestration only: the labelling itself is pure domain logic in
``domain/analytics/elliott``. Bars come from the same :class:`OHLCVRepository`
path the live stock analysis uses, and the per-bar RSI/ADX used for wave
personality come from the same :meth:`compute_series` the chart sub-panes read,
so no second ingestion route and no duplicated indicator math exist here.

Personality context is *additive*: when the indicator pipeline cannot produce a
series (short history, missing strategy, warm-up), the analysis still runs and
every personality check reports itself as not measurable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from momentum25.domain.analytics.elliott_wave import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    ElliottWaveAnalysis,
    PersonalityContext,
    analyze_elliott_wave,
)
from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.errors import NotFoundError
from momentum25.domain.ports.repositories import (
    OHLCVRepository,
    SecurityRepository,
    StrategyRepository,
)
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("elliott_wave")

DEFAULT_LOOKBACK_DAYS = 500
DEFAULT_STRATEGY = "minervini_trend_template"
"""Whose indicator configuration the personality series is computed under — the
same default the live stock analysis and the chart sub-panes use, so a bar's RSI
reads identically on every surface."""


class GetElliottWaveAnalysis:
    """Label the wave structure of a symbol's stored daily price history."""

    def __init__(
        self,
        securities: SecurityRepository,
        ohlcv: OHLCVRepository,
        strategies: StrategyRepository,
        indicator_pipeline: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._ohlcv = ohlcv
        self._strategies = strategies
        self._indicator_pipeline = indicator_pipeline

    async def execute(
        self,
        symbol: str,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
        as_of: date | None = None,
        strategy_name: str = DEFAULT_STRATEGY,
    ) -> ElliottWaveAnalysis:
        """Return the ranked wave counts for ``symbol``."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        series = await self._ohlcv.get_series(
            security.id, lookback_days=lookback_days, as_of=as_of or date.today()
        )
        context = await self._personality_context(symbol, series, strategy_name)
        return analyze_elliott_wave(symbol.upper(), series.bars, threshold_pct, context)

    async def _personality_context(
        self, symbol: str, series: OHLCVSeries, strategy_name: str
    ) -> PersonalityContext | None:
        """Align the indicator series to the loaded bars, or return ``None``.

        The pipeline computes over its own history window, so the two series are
        joined on bar date rather than by position: a positional zip would
        silently attribute one bar's RSI to another. Only bars present in both
        contribute; volume always comes from the bars themselves.
        """
        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or not series.bars:
            return None
        try:
            indicators = await self._indicator_pipeline.compute_series(
                symbol, series.bars[-1].date, strategy.config.indicators
            )
        except Exception:  # noqa: BLE001 - see below
            # Personality corroboration is additive evidence about a labelling.
            # A pipeline failure must degrade it to "not measurable", never take
            # down the wave count itself, which does not depend on indicators.
            _logger.warning("Indicator series unavailable for %s; personality unmeasured", symbol)
            return None
        by_date = {
            bar_date: (rsi, adx)
            for bar_date, rsi, adx in zip(
                indicators.dates, indicators.rsi14, indicators.adx14, strict=True
            )
        }
        if not by_date:
            return None
        return PersonalityContext(
            dates=tuple(bar.date for bar in series.bars),
            rsi14=tuple(by_date.get(bar.date, (None, None))[0] for bar in series.bars),
            adx14=tuple(by_date.get(bar.date, (None, None))[1] for bar in series.bars),
            volumes=tuple(bar.volume for bar in series.bars),
        )
