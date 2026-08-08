"""Base contracts for evaluation engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import EngineConfig
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.domain.value_objects.results import EngineResult, SectorStats


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Everything an engine needs to evaluate a single security.

    Assembled once per security per run by the screening orchestrator. Pure data:
    engines never perform I/O.
    """

    security: Security
    series: OHLCVSeries
    indicators: IndicatorSet
    benchmark: OHLCVSeries
    sector_stats: SectorStats


@runtime_checkable
class EvaluationEngine(Protocol):
    """A deterministic evaluation engine.

    Implementations register themselves in the engine registry under ``engine_id``
    and are wired into a strategy via configuration (ADR-005).
    """

    engine_id: str

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate ``ctx`` against ``cfg`` and return an :class:`EngineResult`."""
        ...
