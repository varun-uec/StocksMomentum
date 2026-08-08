"""Contracts for scoring, ranking, and explainability.

All three are pure and deterministic (ADR-009). Implementations are deferred to
milestone M3; see ``IMPLEMENTATION_SPEC.md`` §10 for the exact scoring/ranking math.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from momentum25.domain.entities.strategy import StrategyConfig
from momentum25.domain.value_objects.results import (
    EngineResult,
    Ranking,
    RuleResult,
    StockScore,
)


@runtime_checkable
class ScoringEngine(Protocol):
    """Combines engine results into momentum and buy-setup scores."""

    def score(
        self, security_id: int, engine_results: list[EngineResult], cfg: StrategyConfig
    ) -> StockScore:
        """Return the combined :class:`StockScore` (implemented in M3)."""
        ...


@runtime_checkable
class RankingEngine(Protocol):
    """Orders scored securities deterministically and assigns ranks."""

    def rank(self, scores: list[StockScore], cfg: StrategyConfig) -> list[Ranking]:
        """Return rankings for ``scores`` (implemented in M3)."""
        ...


@runtime_checkable
class ExplainabilityBuilder(Protocol):
    """Builds human-readable rationale from a stock's rule results."""

    def build_rationale(self, stock_score: StockScore, rule_results: list[RuleResult]) -> str:
        """Return an explanation string for a stock's score (implemented in M3)."""
        ...
