"""Placeholder indicator pipeline — returns an empty IndicatorSet.

The full indicator math (SMA, EMA, RSI, ATR, etc.) is implemented in milestone M2.
See ``IMPLEMENTATION_SPEC.md`` §8 for exact formulas.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.value_objects.indicators import IndicatorSet


class IndicatorPipelinePlaceholder:
    """Computes indicators deterministically for one security.

    The placeholder returns an empty IndicatorSet (all fields None) for any input.
    The full implementation in M2 will compute SMA(50/150/200), EMA(10/21), RSI(14),
    ATR(14), ADR%(20), 52-week high/low, RS rating, volume metrics, and more.
    """

    def compute(
        self, series: OHLCVSeries, benchmark: OHLCVSeries, config: dict[str, Any]
    ) -> IndicatorSet:
        """Return a placeholder :class:`IndicatorSet` with all fields as ``None``.

        Args:
            series: The security's OHLCV price series.
            benchmark: The benchmark index series for RS calculation.
            config: Indicator configuration from the strategy.

        Returns:
            An IndicatorSet with all fields set to None, indicating the indicator
            pipeline is not yet implemented.
        """
        as_of: date = (
            series.latest.date
            if series.latest is not None
            else date.today()
        )
        return IndicatorSet(as_of=as_of)