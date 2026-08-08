"""Stock explainability and history use cases."""

from __future__ import annotations

from typing import Any

from momentum25.domain.errors import NotFoundError, StrategyNotFoundError
from momentum25.domain.ports.repositories import (
    ScreeningRunRepository,
    SecurityRepository,
    StrategyRepository,
)
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl, StockExplanation

_DEFAULT_STRATEGY = "minervini_trend_template"


class GetStockExplanation:
    """Return the full explainability payload for a stock."""

    def __init__(
        self,
        securities: SecurityRepository,
        screening_run_repo: ScreeningRunRepository,
        explainability_builder: ExplainabilityBuilderImpl,
        strategies: StrategyRepository | None = None,
    ) -> None:
        self._securities = securities
        self._screening_run_repo = screening_run_repo
        self._explainability_builder = explainability_builder
        self._strategies = strategies

    async def execute(
        self,
        symbol: str,
        run_id: int | None,
        strategy_name: str = _DEFAULT_STRATEGY,
    ) -> StockExplanation:
        """Return a stock explanation from ``run_id``.

        If ``run_id`` is omitted, uses the latest completed run for
        ``strategy_name`` (e.g. a Momentum Horizon) instead.
        """
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        if run_id is None:
            if self._strategies is None:
                raise NotFoundError("No strategy repository configured.")
            strategy = await self._strategies.get_active(strategy_name)
            if strategy is None or strategy.id is None:
                raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")
            run = await self._screening_run_repo.latest_completed(strategy.id)
            if run is None or run.id is None:
                raise NotFoundError(f"No completed runs found for strategy {strategy_name}.")
            run_id = run.id

        rule_results = await self._screening_run_repo.get_rule_results(
            run_id, security.id
        )
        if not rule_results:
            raise NotFoundError(
                f"No screening results for {symbol} in run {run_id}."
            )

        ranking = await self._screening_run_repo.get_screening_result(run_id, security.id)
        explanation = self._explainability_builder.build_historical_explanation(
            run_id, security.id, rule_results, ranking
        )
        return StockExplanation(
            symbol=symbol,
            security_id=explanation.security_id,
            overall_passed=explanation.overall_passed,
            momentum_score=explanation.momentum_score,
            buy_setup_score=explanation.buy_setup_score,
            composite_score=explanation.composite_score,
            rank=explanation.rank,
            percentile=explanation.percentile,
            rule_explanations=explanation.rule_explanations,
            engine_explanations=explanation.engine_explanations,
            hard_filter_failures=explanation.hard_filter_failures,
            overall_rationale=explanation.overall_rationale,
        )


class GetStockHistory:
    """Return a stock's score/rank history across runs."""

    def __init__(
        self,
        securities: SecurityRepository,
        screening_run_repo: ScreeningRunRepository,
        strategies: StrategyRepository | None = None,
    ) -> None:
        self._securities = securities
        self._screening_run_repo = screening_run_repo
        self._strategies = strategies

    async def execute(self, symbol: str, strategy_name: str, limit: int) -> dict[str, Any]:
        """Return history points for a symbol, scoped to one strategy (e.g. a Momentum Horizon)."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        strategy_id: int | None = None
        if self._strategies is not None:
            strategy = await self._strategies.get_active(strategy_name)
            if strategy is None or strategy.id is None:
                raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")
            strategy_id = strategy.id

        runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED", limit=limit, offset=0, strategy_id=strategy_id
        )

        points = []
        for run in runs:
            if run.id is None:
                continue
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id, limit=10000, offset=0
            )
            for r in rankings:
                if r.security_id == security.id:
                    points.append({
                        "run_date": run.run_date.isoformat(),
                        "security_id": security.id,
                        "rank": r.rank,
                        "momentum_score": str(r.momentum_score),
                        "buy_setup_score": str(r.buy_setup_score),
                    })
                    break

        return {"symbol": symbol, "score_history": points}
