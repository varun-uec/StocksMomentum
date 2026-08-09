"""Use cases for retrieving screening results, rankings, and explanations."""

from __future__ import annotations

from typing import Any

from momentum25.application.dto.rankings import RankingItemDTO, RankingsResponseDTO
from momentum25.domain.errors import NotFoundError
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl, StockExplanation


class GetRankings:
    """Retrieve paginated rankings for a completed screening run."""

    def __init__(
        self,
        screening_run_repo: Any,
        security_repo: Any,
        strategy_repo: Any,
        explainability_builder: ExplainabilityBuilderImpl | None = None,
    ) -> None:
        """Initialize with screening-run, security, and strategy repositories."""
        self._screening_run_repo = screening_run_repo
        self._security_repo = security_repo
        self._strategy_repo = strategy_repo
        self._explainability_builder = explainability_builder or ExplainabilityBuilderImpl()

    async def execute(
        self,
        run_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> RankingsResponseDTO:
        """Return ranked results for a run with security metadata."""
        from momentum25.application.dto.runs import RunDTO

        run = await self._screening_run_repo.get(run_id)
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")

        rankings, total = await self._screening_run_repo.get_rankings(run_id, limit, offset)

        security_ids = [r.security_id for r in rankings]
        rule_results_by_security = await self._screening_run_repo.get_rule_results_bulk(
            run_id, security_ids
        )
        previous_ranks = await self._screening_run_repo.get_previous_run_ranks(
            run.strategy_id, run_id, run.run_date
        )

        items = []
        for ranking in rankings:
            security = await self._security_repo.get(ranking.security_id)
            rule_results = rule_results_by_security.get(ranking.security_id, [])
            summary = self._explainability_builder.build_dashboard_summary(rule_results)

            explanation: dict[str, Any] = {
                "checklist": summary["checklist"],
                "risk_rating": summary["risk"],
                "volume_quality": summary["volume"],
                "breakout_quality": summary["breakout"],
                "pattern": summary["pattern"],
            }
            prev_rank = previous_ranks.get(ranking.security_id)
            if prev_rank is not None and ranking.rank is not None:
                explanation["rank_change"] = ranking.rank - prev_rank

            items.append(
                RankingItemDTO(
                    rank=ranking.rank or 0,
                    symbol=security.symbol if security else "",
                    name=security.name if security else "",
                    momentum_score=ranking.momentum_score,
                    buy_setup_score=ranking.buy_setup_score,
                    sector=getattr(security, "sector", None),
                    rs_rating=summary["rs_rating"],
                    explanation=explanation,
                )
            )

        strategies = await self._strategy_repo.list()
        strategy_name = next(
            (s.name for s in strategies if s.id == run.strategy_id), "unknown"
        )
        run_dto = RunDTO(
            id=run.id,
            status=run.status.value,
            run_date=run.run_date,
            trigger=run.trigger.value,
            strategy=strategy_name,
            data_version=run.data_version,
            config_hash=run.config_hash,
            started_at=run.started_at,
            finished_at=run.finished_at,
            stats=run.stats,
            error=run.error,
        )

        return RankingsResponseDTO(
            run=run_dto, items=items, total=total, limit=limit, offset=offset
        )


class GetStockExplanation:
    """Retrieve explainability for a single stock in a run."""

    def __init__(
        self, screening_run_repo: Any, explainability_builder: ExplainabilityBuilderImpl
    ) -> None:
        """Initialize with screening-run repository and explainability builder."""
        self._screening_run_repo = screening_run_repo
        self._explainability_builder = explainability_builder

    async def execute(self, run_id: int, security_id: int) -> StockExplanation:
        """Return the full explanation for one stock in a run."""
        rule_results = await self._screening_run_repo.get_rule_results(run_id, security_id)
        ranking = await self._screening_run_repo.get_screening_result(run_id, security_id)
        historical = self._explainability_builder.build_historical_explanation(
            run_id, security_id, rule_results, ranking
        )
        return historical