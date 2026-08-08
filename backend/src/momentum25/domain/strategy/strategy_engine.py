"""The strategy orchestrator.

Given a strategy and per-security evaluation contexts, runs the enabled engines (in
deterministic order), then scoring and ranking.

This foundational implementation provides working orchestration with placeholder
engine/scoring results. The full scoring/ranking math arrives in milestone M3.
"""

from __future__ import annotations

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.scoring.contracts import RankingEngine, ScoringEngine
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.value_objects.results import EngineResult, Ranking, StockScore


class StrategyEngine:
    """Orchestrates engines → scoring → ranking for a strategy."""

    def __init__(
        self,
        engines: EngineRegistry,
        scoring: ScoringEngine,
        ranking: RankingEngine,
    ) -> None:
        """Wire the orchestrator with its collaborators.

        Args:
            engines: Registry resolving ``engine_id`` to an engine implementation.
            scoring: The scoring engine combining engine results into scores.
            ranking: The ranking engine assigning deterministic ranks.
        """
        self._engines = engines
        self._scoring = scoring
        self._ranking = ranking

    def score_security(self, ctx: EvaluationContext, strategy: Strategy) -> StockScore:
        """Run all enabled engines for one security and return its score.

        The iteration order follows the strategy's engine order (deterministic).

        Args:
            ctx: The evaluation context for a single security.
            strategy: The strategy configuration.

        Returns:
            A :class:`StockScore` with engine results and combined scores.
        """
        engine_results: list[EngineResult] = []
        for engine_cfg in strategy.config.enabled_engines():
            engine = self._engines.get(engine_cfg.id)
            result = engine.evaluate(ctx, engine_cfg)
            engine_results.append(result)
        sec_id = ctx.security.id if ctx.security.id else 0
        return self._scoring.score(sec_id, engine_results, strategy.config)

    def rank(self, scores: list[StockScore], strategy: Strategy) -> list[Ranking]:
        """Rank pre-computed scores deterministically.

        Args:
            scores: Stock scores from :meth:`score_security`.
            strategy: The strategy configuration.

        Returns:
            A list of :class:`Ranking` objects.
        """
        return self._ranking.rank(scores, strategy.config)

    def run(
        self, contexts: list[EvaluationContext], strategy: Strategy
    ) -> tuple[list[StockScore], list[Ranking]]:
        """Score every context and rank the universe.

        Args:
            contexts: Evaluation contexts for all securities in the universe.
            strategy: The strategy configuration.

        Returns:
            A tuple of (stock_scores, rankings).
        """
        scores = [self.score_security(ctx, strategy) for ctx in contexts]
        rankings = self.rank(scores, strategy)
        return scores, rankings
