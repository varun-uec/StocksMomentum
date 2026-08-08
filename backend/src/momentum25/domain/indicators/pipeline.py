"""The indicator pipeline contract.

Computes an :class:`IndicatorSet` for a single security from its price series and the
benchmark series. Implementation is deferred to milestone M2; insufficient history
must yield ``None`` fields (never an exception).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.value_objects.indicators import IndicatorSet


@runtime_checkable
class IndicatorPipeline(Protocol):
    """Computes indicators deterministically for one security."""

    def compute(
        self, series: OHLCVSeries, benchmark: OHLCVSeries, config: dict[str, Any]
    ) -> IndicatorSet:
        """Return the :class:`IndicatorSet` for ``series`` (implemented in M2)."""
        ...
