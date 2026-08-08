"""Research & Validation Platform API endpoints.

Exposes all research capabilities through versioned, consistent, deterministic APIs:
    - Historical screening replay
    - Run comparison / validation
    - Strategy evaluation
    - Contribution analysis
    - Strategy comparison
    - Experiment laboratory
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from momentum25.application.dto.research import (
    ContributionAnalysisResponse,
    DeterminismVerificationResponse,
    EngineContributionStatsDTO,
    ExperimentConfigDTO,
    ExperimentResponse,
    HistoricalRunSummaryDTO,
    HistoricalScreeningRequest,
    HistoricalScreeningResponse,
    PortfolioPerformanceDTO,
    RuleContributionStatsDTO,
    RunComparisonResponse,
    ScorePointDTO,
    StrategyComparisonResponse,
    StrategyEvaluationResponse,
)
from momentum25.application.use_cases.research.comparison import StrategyComparisonUseCase
from momentum25.application.use_cases.research.contribution import ContributionAnalysisUseCase
from momentum25.application.use_cases.research.evaluation import EvaluateStrategyUseCase
from momentum25.application.use_cases.research.experiment import ExperimentUseCase
from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.application.use_cases.research.refresh_corporate_actions import (
    RefreshCorporateActions,
)
from momentum25.application.use_cases.research.validation import (
    DeterminismVerificationUseCase,
    ValidateRunComparisonUseCase,
)
from momentum25.interface.api.dependencies import get_refresh_corporate_actions
from momentum25.interface.api.dependencies_research import (
    get_contribution_analysis_use_case,
    get_determinism_verification_use_case,
    get_experiment_use_case,
    get_historical_screening_use_case,
    get_strategy_comparison_use_case,
    get_strategy_evaluation_use_case,
    get_validate_run_comparison_use_case,
)

router = APIRouter(prefix="/research", tags=["research"])


# ── Historical Screening ────────────────────────────────────────────────


@router.post(
    "/historical/screen",
    response_model=HistoricalScreeningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Replay screening engine for a historical date",
    description="Execute the complete screening pipeline for any past trading date. "
    "Uses only data available on that date. No future data leakage.",
)
async def historical_screen(
    body: HistoricalScreeningRequest,
    use_case: Annotated[HistoricalScreeningUseCase, Depends(get_historical_screening_use_case)],
) -> HistoricalScreeningResponse:
    """Execute a historical screening run and return the results."""
    result = await use_case.execute(
        strategy_name=body.strategy_name,
        as_of_date=body.as_of_date,
        symbol_filter=body.symbol_filter,
    )
    return HistoricalScreeningResponse(
        run_id=result["run_id"],
        run_date=result["run_date"] if isinstance(result["run_date"], date) else body.as_of_date,
        total_evaluated=result["total_evaluated"],
        total_passed=result["total_passed"],
        total_failed=result["total_failed"],
        strategy_name=body.strategy_name,
    )


# ── Corporate Actions ───────────────────────────────────────────────────


@router.post(
    "/corporate-actions/refresh",
    summary="Refresh corporate-action price adjustments for the active universe",
    description=(
        "Fetches corporate actions per active security, persists them, and "
        "recomputes each bar's backward adjustment factor and adjusted close. "
        "Until this runs, every bar's adj_factor is 1, so splits and bonuses "
        "corrupt long-window indicators for affected securities (Phase 0.5). "
        "Deliberately a separate periodic operation, not part of the daily "
        "screening request path -- NSE's endpoint is per-symbol, so refreshing "
        "the whole universe costs one external call per security."
    ),
)
async def refresh_corporate_actions(
    use_case: Annotated[RefreshCorporateActions, Depends(get_refresh_corporate_actions)],
    as_of: Annotated[date | None, Query()] = None,
) -> dict[str, int]:
    """Refresh adjustment factors for every active security."""
    return await use_case.execute(as_of)


# ── Run Comparison / Validation ─────────────────────────────────────────


@router.post(
    "/compare/runs",
    response_model=RunComparisonResponse,
    summary="Compare two screening runs",
    description="Produce a deterministic diff between any two screening runs. "
    "Identifies ranking changes, score changes, and rule-level regressions.",
)
async def compare_runs(
    run_id_a: Annotated[int, Query(description="Baseline run ID")],
    run_id_b: Annotated[int, Query(description="Comparison run ID")],
    use_case: Annotated[ValidateRunComparisonUseCase, Depends(get_validate_run_comparison_use_case)],
) -> RunComparisonResponse:
    """Compare two screening runs and return a deterministic diff."""
    report = await use_case.execute(run_id_a, run_id_b)

    return RunComparisonResponse(
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        run_date_a=report.run_date_a,
        run_date_b=report.run_date_b,
        strategy_name=report.strategy_name,
        ranking_changed=report.ranking_changed,
        score_changed=report.score_changed,
        ranking_diffs=[
            {
                "security_id": d.security_id,
                "symbol": d.symbol,
                "rank_a": d.rank_a,
                "rank_b": d.rank_b,
                "rank_delta": d.rank_delta,
                "direction": d.direction,
            }
            for d in report.ranking_diffs
        ],
        score_diffs=[
            {
                "security_id": d.security_id,
                "symbol": d.symbol,
                "momentum_a": d.momentum_a,
                "momentum_b": d.momentum_b,
                "momentum_delta": d.momentum_delta,
                "buy_setup_a": d.buy_setup_a,
                "buy_setup_b": d.buy_setup_b,
                "buy_setup_delta": d.buy_setup_delta,
            }
            for d in report.score_diffs
        ],
        rule_diffs=[
            {
                "security_id": d.security_id,
                "symbol": d.symbol,
                "rule_id": d.rule_id,
                "engine_id": d.engine_id,
                "passed_a": d.passed_a,
                "passed_b": d.passed_b,
                "changed": d.changed,
            }
            for d in report.rule_diffs
        ],
        top_gainers=[
            {
                "security_id": d.security_id,
                "symbol": d.symbol,
                "rank_a": d.rank_a,
                "rank_b": d.rank_b,
                "rank_delta": d.rank_delta,
                "direction": d.direction,
            }
            for d in report.top_gainers
        ],
        top_losers=[
            {
                "security_id": d.security_id,
                "symbol": d.symbol,
                "rank_a": d.rank_a,
                "rank_b": d.rank_b,
                "rank_delta": d.rank_delta,
                "direction": d.direction,
            }
            for d in report.top_losers
        ],
        is_identical=report.is_identical(),
        indicator_version_a=report.indicator_version_a,
        indicator_version_b=report.indicator_version_b,
        indicator_versions_differ=report.indicator_versions_differ(),
    )


@router.post(
    "/verify/determinism",
    response_model=DeterminismVerificationResponse,
    summary="Verify screening determinism",
    description="Run the same historical screening twice and verify identical outputs. "
    "Confirms the engine produces reproducible results.",
)
async def verify_determinism(
    as_of_date: Annotated[date, Query()],
    use_case: Annotated[DeterminismVerificationUseCase, Depends(get_determinism_verification_use_case)],
    strategy_name: Annotated[str, Query()] = "minervini_trend_template",
) -> DeterminismVerificationResponse:
    """Verify determinism by re-running the same screening twice."""
    result = await use_case.verify(strategy_name, as_of_date)
    return DeterminismVerificationResponse(
        run_id_a=result["run_id_a"],
        run_id_b=result["run_id_b"],
        is_deterministic=result["is_deterministic"],
        ranking_changed=result["diffs"]["ranking_changed"],
        score_changed=result["diffs"]["score_changed"],
        rule_diffs=result["diffs"]["rule_diffs"],
    )


# ── Strategy Evaluation ─────────────────────────────────────────────────


@router.get(
    "/evaluate/{strategy_name}",
    response_model=StrategyEvaluationResponse,
    summary="Evaluate strategy performance",
    description="Compute deterministic performance metrics for a strategy across "
    "historical runs: win rate, Sharpe/Sortino ratios, max drawdown, volatility, "
    "profit factor, and rank stability.",
)
async def evaluate_strategy(
    strategy_name: str,
    use_case: Annotated[EvaluateStrategyUseCase, Depends(get_strategy_evaluation_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=200)] = 50,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StrategyEvaluationResponse:
    """Evaluate a strategy and return performance metrics."""
    result = await use_case.execute(strategy_name, max_runs, date_from, date_to)
    p = result.performance
    return StrategyEvaluationResponse(
        strategy_name=result.strategy_name,
        performance=PortfolioPerformanceDTO(
            strategy_name=p.strategy_name,
            run_count=p.run_count,
            first_run_date=p.first_run_date,
            last_run_date=p.last_run_date,
            avg_momentum_score=p.avg_momentum_score,
            median_momentum_score=p.median_momentum_score,
            avg_buy_setup_score=p.avg_buy_setup_score,
            median_buy_setup_score=p.median_buy_setup_score,
            momentum_score_volatility=p.momentum_score_volatility,
            buy_setup_score_volatility=p.buy_setup_score_volatility,
            max_momentum_score=p.max_momentum_score,
            min_momentum_score=p.min_momentum_score,
            max_drawdown_pct=p.max_drawdown_pct,
            avg_pass_rate=p.avg_pass_rate,
            avg_top_rank_stability=p.avg_top_rank_stability,
            sharpe_ratio=p.sharpe_ratio,
            sortino_ratio=p.sortino_ratio,
            profit_factor=p.profit_factor,
        ),
        run_summaries=[
            HistoricalRunSummaryDTO(
                run_id=r.run_id,
                strategy_name=r.strategy_name,
                run_date=r.run_date,
                total_evaluated=r.total_evaluated,
                total_passed=r.total_passed,
                total_failed=r.total_failed,
                data_version=r.data_version,
                config_hash=r.config_hash,
                started_at=r.started_at,
                finished_at=r.finished_at,
            )
            for r in result.run_summaries
        ],
        score_history=[
            ScorePointDTO(
                run_date=s["run_date"],
                security_id=s["security_id"],
                rank=s["rank"],
                momentum_score=s["momentum_score"],
                buy_setup_score=s["buy_setup_score"],
            )
            for s in result.score_history
        ],
    )


# ── Contribution Analysis ───────────────────────────────────────────────


@router.get(
    "/contribution/{strategy_name}",
    response_model=ContributionAnalysisResponse,
    summary="Analyze rule & engine contributions",
    description="Measure how each rule and engine contributes to screening outcomes "
    "across historical runs. Identifies the most impactful rules, least impactful "
    "rules, and redundant rules (100% pass rate).",
)
async def contribution_analysis(
    strategy_name: str,
    use_case: Annotated[ContributionAnalysisUseCase, Depends(get_contribution_analysis_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ContributionAnalysisResponse:
    """Analyze rule contribution across runs for a given strategy."""
    result = await use_case.execute(
        strategy_id=0,
        strategy_name=strategy_name,
        max_runs=max_runs,
    )
    def _rule_dto(r: object) -> RuleContributionStatsDTO:
        return RuleContributionStatsDTO(
            rule_id=r.rule_id,
            engine_id=r.engine_id,
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            avg_contribution=r.avg_contribution,
            total_contribution=r.total_contribution,
            importance_score=r.importance_score,
            pass_rate=r.pass_rate,
            is_redundant=getattr(r, "is_redundant", False),
        )

    return ContributionAnalysisResponse(
        strategy_name=result.strategy_name,
        run_count=result.run_count,
        date_range=(
            f"{result.date_range[0].isoformat()} to {result.date_range[1].isoformat()}"
            if result.date_range else None
        ),
        engine_stats=[
            EngineContributionStatsDTO(
                engine_name=e.engine_id,
                rule_count=len(e.rule_stats),
                avg_pass_rate=e.avg_pass_rate,
                avg_importance=sum((r.importance_score for r in e.rule_stats), Decimal("0")) / max(len(e.rule_stats), 1),
                total_importance=sum((r.total_contribution for r in e.rule_stats), Decimal("0")),
            )
            for e in result.engine_stats
        ],
        top_rules=[_rule_dto(r) for r in result.top_rules],
        bottom_rules=[_rule_dto(r) for r in result.bottom_rules],
        redundant_rules=[_rule_dto(r) for r in result.redundant_rules],
    )


# ── Strategy Comparison ─────────────────────────────────────────────────


@router.get(
    "/compare/strategies",
    response_model=StrategyComparisonResponse,
    summary="Compare two strategies",
    description="Compare two strategy configurations across their historical runs. "
    "Shows ranking differences, score differences, rule-level diffs, and agreement rate.",
)
async def compare_strategies(
    strategy_a: Annotated[str, Query(description="Baseline strategy name")],
    strategy_b: Annotated[str, Query(description="Comparison strategy name")],
    use_case: Annotated[StrategyComparisonUseCase, Depends(get_strategy_comparison_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StrategyComparisonResponse:
    """Compare two strategy configurations."""
    result = await use_case.execute(strategy_a, strategy_b, max_runs)
    from momentum25.application.dto.research import StrategyComparisonPointDTO
    total = len(result.score_deltas)
    agreements = sum(
        1 for s in result.score_deltas
        if s.strategy_a_passed == s.strategy_b_passed
    )
    return StrategyComparisonResponse(
        strategy_a_name=result.strategy_a_name,
        strategy_b_name=result.strategy_b_name,
        total_comparisons=total,
        agreement_count=agreements,
        agreement_rate=result.rank_correlation,
        a_wins=result.strategy_a_wins_score,
        b_wins=result.strategy_b_wins_score,
        comparisons=[
            StrategyComparisonPointDTO(
                security_id=0,
                symbol=f"{s.run_date}",
                rank_a=s.strategy_a_rank,
                rank_b=s.strategy_b_rank,
                momentum_a=s.strategy_a_score,
                momentum_b=s.strategy_b_score,
                agreement=s.strategy_a_passed == s.strategy_b_passed,
            )
            for s in result.score_deltas
        ],
        rule_level_diffs=[
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "a_pass_rate": str(r.strategy_a_pass_rate),
                "b_pass_rate": str(r.strategy_b_pass_rate),
                "pass_rate_delta": str(r.pass_rate_delta),
            }
            for r in result.rule_differences
        ],
    )


# ── Experiment Laboratory ───────────────────────────────────────────────


@router.post(
    "/experiment/run",
    response_model=ExperimentResponse,
    summary="Run a controlled experiment",
    description="Execute a controlled experiment: run base + variant strategy "
    "configurations across multiple dates. Variants use parameter overrides "
    "and remain isolated from production configurations.",
)
async def run_experiment(
    body: ExperimentConfigDTO,
    use_case: Annotated[ExperimentUseCase, Depends(get_experiment_use_case)],
) -> ExperimentResponse:
    """Run an experiment comparing base and variant strategy configurations."""
    from momentum25.application.dto.research import ExperimentResultDTO
    from momentum25.domain.research.models import ExperimentConfig
    config = ExperimentConfig(
        name=f"exp_{body.base_strategy_name}",
        description=f"Experiment for {body.base_strategy_name}",
        base_strategy_name=body.base_strategy_name,
        base_strategy_id=0,
        overrides=tuple(),
        run_dates=tuple(body.run_dates) if body.run_dates else (),
    )
    result = await use_case.run_experiment(config)

    def _to_result_dto(r: object, label: str) -> ExperimentResultDTO:
        return ExperimentResultDTO(
            variant_label=label,
            run_id=getattr(r, "run_id", 0),
            run_date=getattr(r, "run_date", None),
            total_evaluated=getattr(r, "total_evaluated", 0),
            total_passed=getattr(r, "total_passed", 0),
            avg_momentum_score=getattr(r, "avg_momentum_score", Decimal("0")),
            avg_buy_setup_score=getattr(r, "avg_buy_setup_score", Decimal("0")),
        )

    base_dtos = [_to_result_dto(r, "base") for r in result.base_results]
    variant_dtos = [_to_result_dto(r, r.variant_name) for r in result.variants]

    return ExperimentResponse(
        base_strategy_name=result.base_strategy_name,
        variant_label=result.best_variant or "base",
        run_count=len(base_dtos),
        date_range=None,
        base_results=base_dtos,
        variant_results=variant_dtos,
        avg_improvement=result.best_variant_improvement,
        best_run_date=base_dtos[0].run_date if base_dtos else None,
        is_better=result.best_variant is not None,
        summary=result.summary,
    )