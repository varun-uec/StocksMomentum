"""Ranking engine — orders scored securities deterministically and assigns ranks.

Implements the deterministic compound sort from ``IMPLEMENTATION_SPEC.md`` §10.
"""

from __future__ import annotations

from momentum25.domain.entities.strategy import StrategyConfig
from momentum25.domain.value_objects.results import Ranking, StockScore


class RankingEngineImpl:
    """Orders scored securities deterministically and assigns ranks.

    Gate check: equities failing hard filters receive ``rank=None`` and are
    excluded from the competitive ranking tier. Passing equities are sorted by
    ``momentum_score`` desc → ``buy_setup_score`` desc → ``rs_rating`` desc →
    ``symbol`` asc, then assigned sequential 1-based ranks.
    """

    def rank(self, scores: list[StockScore], cfg: StrategyConfig) -> list[Ranking]:
        """Return rankings for ``scores``.

        Args:
            scores: Stock scores from the scoring engine.
            cfg: The strategy configuration (unused directly; reserved for
                future ranking rules such as sector caps).

        Returns:
            A list of :class:`Ranking` objects in the same order as ``scores``,
            with ``rank`` set to ``None`` for filtered-out equities.
        """
        passing = [s for s in scores if s.hard_filters_passed]

        passing_sorted = sorted(
            passing,
            key=lambda s: (
                -s.momentum_score,
                -s.buy_setup_score,
                -_extract_rs_rating(s),
                s.security_id,  # deterministic proxy for symbol ascending
            ),
        )

        rank_by_security: dict[int, int] = {
            s.security_id: i for i, s in enumerate(passing_sorted, start=1)
        }

        return [
            Ranking(
                security_id=s.security_id,
                momentum_score=s.momentum_score,
                buy_setup_score=s.buy_setup_score,
                rank=rank_by_security.get(s.security_id),
            )
            for s in scores
        ]


def _extract_rs_rating(score: StockScore) -> int:
    """Extract the best available rs_rating from rule results, defaulting to 0."""
    for er in score.engine_results:
        for rr in er.rule_results:
            if "rs_rating" in rr.rule_id and rr.raw_value is not None:
                return int(rr.raw_value)
    return 0
