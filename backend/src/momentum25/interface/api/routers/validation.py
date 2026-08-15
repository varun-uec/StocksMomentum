"""Strategy Validation & Alpha Research API endpoints (Phase 6).

Exposes all validation and research capabilities through versioned APIs:
    - Historical validation across configurable windows
    - Alpha measurement against benchmarks
    - Strategy scorecards with full performance metrics
    - Rule effectiveness analysis
    - Engine effectiveness analysis
    - Parameter experiments
    - Detailed historical replay
    - Research dashboard aggregation
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.validation import (
    AlphaAnalysisResponse,
    BenchmarkComparisonDTO,
    EngineEffectivenessDTO,
    EngineEffectivenessResponse,
    HistoricalValidationResponse,
    HistoricalValidationResultDTO,
    MeasurabilityDTO,
    ParameterExperimentRequest,
    ParameterExperimentResponse,
    ParameterExperimentResultDTO,
    ResearchDashboardRequest,
    ResearchDashboardResponse,
    RuleEffectivenessDTO,
    RuleEffectivenessResponse,
    StrategyScorecardDTO,
    ValidationWindowDTO,
)
from momentum25.application.use_cases.validation import (
    AlphaMeasurementUseCase,
    EngineEffectivenessUseCase,
    HistoricalValidationUseCase,
    ParameterResearchUseCase,
    RuleEffectivenessUseCase,
    StrategyScorecardUseCase,
)
from momentum25.interface.api.dependencies_validation import (
    get_alpha_measurement_use_case,
    get_engine_effectiveness_use_case,
    get_historical_validation_use_case,
    get_parameter_research_use_case,
    get_rule_effectiveness_use_case,
    get_scorecard_use_case,
)


def _measurability(report: Any) -> MeasurabilityDTO:
    """Map a domain report's measurability block to its DTO."""
    return MeasurabilityDTO(
        forward_returns_available=report.measurability.forward_returns_available,
        reason=report.measurability.reason,
    )


def _rule_dto(r: Any) -> RuleEffectivenessDTO:
    """Map one domain RuleEffectiveness to its DTO, preserving nulls."""
    return RuleEffectivenessDTO(
        rule_id=r.rule_id,
        engine_id=r.engine_id,
        rule_name=r.rule_name,
        total_evaluations=r.total_evaluations,
        pass_count=r.pass_count,
        fail_count=r.fail_count,
        pass_rate=r.pass_rate,
        contribution_to_successful=r.contribution_to_successful,
        contribution_to_unsuccessful=r.contribution_to_unsuccessful,
        avg_return_when_passes=r.avg_return_when_passes,
        avg_return_when_fails=r.avg_return_when_fails,
        return_delta=r.return_delta,
        significance_score=r.significance_score,
        is_weak=r.is_weak,
        is_redundant=r.is_redundant,
        is_high_value=r.is_high_value,
    )


def _scorecard_dto(sc: Any) -> StrategyScorecardDTO:
    """Map a domain StrategyScorecard to its DTO, preserving nulls."""
    return StrategyScorecardDTO(
        strategy_name=sc.strategy_name,
        strategy_id=sc.strategy_id,
        period_label=sc.period_label,
        start_date=sc.start_date,
        end_date=sc.end_date,
        total_trading_days=sc.total_trading_days,
        total_runs=sc.total_runs,
        cagr=sc.cagr,
        annual_return=sc.annual_return,
        cumulative_return=sc.cumulative_return,
        avg_holding_return=sc.avg_holding_return,
        best_return=sc.best_return,
        worst_return=sc.worst_return,
        win_rate=sc.win_rate,
        avg_winner=sc.avg_winner,
        avg_loser=sc.avg_loser,
        total_wins=sc.total_wins,
        total_losses=sc.total_losses,
        profit_factor=sc.profit_factor,
        max_drawdown=sc.max_drawdown,
        max_drawdown_duration=sc.max_drawdown_duration,
        volatility=sc.volatility,
        downside_volatility=sc.downside_volatility,
        sharpe_ratio=sc.sharpe_ratio,
        sortino_ratio=sc.sortino_ratio,
        calmar_ratio=sc.calmar_ratio,
        information_ratio=sc.information_ratio,
        alpha=sc.alpha,
        beta=sc.beta,
        r_squared=sc.r_squared,
        avg_pass_rate=sc.avg_pass_rate,
        avg_momentum_score=sc.avg_momentum_score,
        avg_buy_setup_score=sc.avg_buy_setup_score,
        false_positive_rate=sc.false_positive_rate,
        false_negative_rate=sc.false_negative_rate,
        measurability=_measurability(sc),
        monthly_returns=list(sc.monthly_returns),
        yearly_returns=list(sc.yearly_returns),
        rolling_sharpe=list(sc.rolling_sharpe),
    )


def _alpha_dto(a: Any) -> AlphaAnalysisResponse:
    """Map a domain AlphaAnalysisReport to its DTO."""
    return AlphaAnalysisResponse(
        strategy_name=a.strategy_name,
        strategy_id=a.strategy_id,
        period_label=a.period_label,
        start_date=a.start_date,
        end_date=a.end_date,
        comparisons=[
            BenchmarkComparisonDTO(
                benchmark_code=c.benchmark_code,
                benchmark_name=c.benchmark_name,
                strategy_return=c.strategy_return,
                benchmark_return=c.benchmark_return,
                alpha=c.alpha,
                excess_return=c.excess_return,
                relative_performance=c.relative_performance,
                annualized_return=c.annualized_return,
                benchmark_annualized_return=c.benchmark_annualized_return,
                cagr=c.cagr,
                benchmark_cagr=c.benchmark_cagr,
                rolling_returns=list(c.rolling_returns),
            )
            for c in a.comparisons
        ],
        best_alpha=a.best_alpha,
        worst_alpha=a.worst_alpha,
        avg_alpha=a.avg_alpha,
        measurability=_measurability(a),
    )


def _rules_dto(rules: Any) -> RuleEffectivenessResponse:
    """Map a domain RuleEffectivenessReport to its DTO."""
    return RuleEffectivenessResponse(
        strategy_name=rules.strategy_name,
        strategy_id=rules.strategy_id,
        total_runs_analyzed=rules.total_runs_analyzed,
        date_range=(
            f"{rules.date_range[0].isoformat()} to {rules.date_range[1].isoformat()}"
            if rules.date_range
            else None
        ),
        rules=[_rule_dto(r) for r in rules.rules],
        weak_rules=[_rule_dto(r) for r in rules.weak_rules],
        redundant_rules=[_rule_dto(r) for r in rules.redundant_rules],
        high_value_rules=[_rule_dto(r) for r in rules.high_value_rules],
        summary=rules.summary,
        measurability=_measurability(rules),
    )


def _engines_dto(engines: Any) -> EngineEffectivenessResponse:
    """Map a domain EngineEffectivenessReport to its DTO."""
    return EngineEffectivenessResponse(
        strategy_name=engines.strategy_name,
        strategy_id=engines.strategy_id,
        total_runs_analyzed=engines.total_runs_analyzed,
        engines=[
            EngineEffectivenessDTO(
                engine_id=e.engine_id,
                engine_name=e.engine_name,
                total_evaluations=e.total_evaluations,
                avg_score=e.avg_score,
                avg_rules_passed=e.avg_rules_passed,
                avg_rules_failed=e.avg_rules_failed,
                avg_pass_rate=e.avg_pass_rate,
                contribution_to_final_score=e.contribution_to_final_score,
                correlation_with_outcome=e.correlation_with_outcome,
                improves_performance=e.improves_performance,
                avg_forward_return_when_engine_scores_high=(
                    e.avg_forward_return_when_engine_scores_high
                ),
            )
            for e in engines.engines
        ],
        best_engine=engines.best_engine,
        worst_engine=engines.worst_engine,
        recommended_exclusions=list(engines.recommended_exclusions),
        summary=engines.summary,
        measurability=_measurability(engines),
    )


router = APIRouter(prefix="/validation", tags=["validation"])


# ── Priority 1: Historical Validation ─────────────────────────────────────


@router.get(
    "/historical/{strategy_name}",
    response_model=HistoricalValidationResponse,
    summary="Run historical validation across time windows",
    description="Execute the screening engine across configurable historical "
    "validation windows (1Y, 3Y, 5Y, 10Y). Returns pass rates, run counts, "
    "and summary statistics for each window.",
)
async def historical_validation(
    strategy_name: str,
    use_case: Annotated[HistoricalValidationUseCase, Depends(get_historical_validation_use_case)],
    window_years: Annotated[int, Query(ge=1, le=10)] = 1,
) -> HistoricalValidationResponse:
    """Run historical validation for a strategy."""
    result = await use_case.execute(strategy_name, window_years)

    return HistoricalValidationResponse(
        strategy_name=result.strategy_name,
        strategy_id=result.strategy_id,
        windows=[
            HistoricalValidationResultDTO(
                strategy_name=w.strategy_name,
                window=ValidationWindowDTO(
                    label=w.window.label,
                    start_date=w.window.start_date,
                    end_date=w.window.end_date,
                    trading_days=w.window.trading_days,
                ),
                total_runs=w.total_runs,
                successful_runs=w.successful_runs,
                failed_runs=w.failed_runs,
                run_ids=list(w.run_ids),
                summary=w.summary,
            )
            for w in result.windows
        ],
        total_trading_days=result.total_trading_days,
        total_successful_runs=result.total_successful_runs,
        overall_pass_rate=result.overall_pass_rate,
        generated_at=result.generated_at,
    )


# ── Priority 2: Alpha Measurement ─────────────────────────────────────────


@router.get(
    "/alpha/{strategy_name}",
    response_model=AlphaAnalysisResponse,
    summary="Compute alpha against benchmarks",
    description="Compare strategy performance against Nifty 50 and Nifty 500 "
    "benchmarks. Measures alpha, excess return, CAGR, rolling returns, "
    "and relative performance.",
)
async def alpha_measurement(
    strategy_name: str,
    use_case: Annotated[AlphaMeasurementUseCase, Depends(get_alpha_measurement_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=500)] = 252,
) -> AlphaAnalysisResponse:
    """Compute alpha analysis for a strategy."""
    result = await use_case.execute(strategy_name, max_runs)

    return _alpha_dto(result)


# ── Priority 3: Strategy Scorecard ────────────────────────────────────────


@router.get(
    "/scorecard/{strategy_name}",
    response_model=StrategyScorecardDTO,
    summary="Generate professional strategy scorecard",
    description="Compute a complete professional scorecard with CAGR, Sharpe, "
    "Sortino, Calmar, win rate, max drawdown, volatility, profit factor, "
    "alpha, beta, information ratio, and all other standard metrics.",
)
async def strategy_scorecard(
    strategy_name: str,
    use_case: Annotated[StrategyScorecardUseCase, Depends(get_scorecard_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=500)] = 252,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> StrategyScorecardDTO:
    """Compute strategy scorecard."""
    result = await use_case.execute(strategy_name, max_runs, date_from, date_to)

    return _scorecard_dto(result)


# ── Priority 4: Rule Effectiveness ────────────────────────────────────────


@router.get(
    "/rules/{strategy_name}",
    response_model=RuleEffectivenessResponse,
    summary="Analyze rule effectiveness",
    description="Measure every rule's pass frequency, contribution to outcomes, "
    "average returns when passed/failed, and identify weak, redundant, and "
    "high-value rules with statistical significance scoring.",
)
async def rule_effectiveness(
    strategy_name: str,
    use_case: Annotated[RuleEffectivenessUseCase, Depends(get_rule_effectiveness_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=200)] = 100,
) -> RuleEffectivenessResponse:
    """Analyze rule effectiveness."""
    result = await use_case.execute(strategy_name, max_runs)

    return _rules_dto(result)


# ── Priority 5: Engine Effectiveness ──────────────────────────────────────


@router.get(
    "/engines/{strategy_name}",
    response_model=EngineEffectivenessResponse,
    summary="Evaluate engine effectiveness",
    description="Measure each engine's contribution, standalone performance, "
    "and whether it measurably improves overall strategy results. Identifies "
    "engines that could be excluded without harming performance.",
)
async def engine_effectiveness(
    strategy_name: str,
    use_case: Annotated[EngineEffectivenessUseCase, Depends(get_engine_effectiveness_use_case)],
    max_runs: Annotated[int, Query(ge=1, le=200)] = 100,
) -> EngineEffectivenessResponse:
    """Analyze engine effectiveness."""
    result = await use_case.execute(strategy_name, max_runs)

    return _engines_dto(result)


# ── Priority 6: Parameter Research ────────────────────────────────────────


@router.post(
    "/experiment/run",
    response_model=ParameterExperimentResponse,
    summary="Run a parameter experiment",
    description="Run a controlled experiment comparing base vs variant strategy "
    "configurations. Variants use parameter overrides and remain isolated from "
    "production configurations. Returns performance comparisons.",
)
async def parameter_experiment(
    body: ParameterExperimentRequest,
    use_case: Annotated[ParameterResearchUseCase, Depends(get_parameter_research_use_case)],
) -> ParameterExperimentResponse:
    """Run a parameter experiment."""
    variants = [
        {"name": v.name, "overrides": [o.model_dump() for o in v.overrides]} for v in body.variants
    ]
    result = await use_case.execute(
        experiment_name=body.experiment_name,
        base_strategy_name=body.base_strategy_name,
        variants=variants,
        run_dates=body.run_dates,
    )

    return ParameterExperimentResponse(
        experiment_name=result.experiment_name,
        base_strategy_name=result.base_strategy_name,
        base_result=ParameterExperimentResultDTO(
            variant_name=result.base_result.variant_name,
            run_count=result.base_result.run_count,
            avg_momentum_score=result.base_result.avg_momentum_score,
            avg_buy_setup_score=result.base_result.avg_buy_setup_score,
            avg_pass_rate=result.base_result.avg_pass_rate,
        ),
        variants=[
            ParameterExperimentResultDTO(
                variant_name=v.variant_name,
                run_count=v.run_count,
                avg_momentum_score=v.avg_momentum_score,
                avg_buy_setup_score=v.avg_buy_setup_score,
                avg_pass_rate=v.avg_pass_rate,
            )
            for v in result.variants
        ],
        best_variant=result.best_variant,
        best_improvement=result.best_improvement,
        parameter_sensitivity=result.parameter_sensitivity,
        summary=result.summary,
    )


# ── Priority 8: Research Dashboard ────────────────────────────────────────


@router.post(
    "/dashboard",
    response_model=ResearchDashboardResponse,
    summary="Get research dashboard data",
    description="Aggregated research dashboard with scorecard, alpha analysis, "
    "rule/engine effectiveness, historical validation, and screening quality metrics. "
    "Provides a comprehensive view of strategy performance and research findings.",
)
async def research_dashboard(
    body: ResearchDashboardRequest,
    historical_validation_uc: Annotated[
        HistoricalValidationUseCase, Depends(get_historical_validation_use_case)
    ],
    alpha_uc: Annotated[AlphaMeasurementUseCase, Depends(get_alpha_measurement_use_case)],
    scorecard_uc: Annotated[StrategyScorecardUseCase, Depends(get_scorecard_use_case)],
    rules_uc: Annotated[RuleEffectivenessUseCase, Depends(get_rule_effectiveness_use_case)],
    engines_uc: Annotated[EngineEffectivenessUseCase, Depends(get_engine_effectiveness_use_case)],
) -> ResearchDashboardResponse:
    """Get complete research dashboard data."""
    scorecard = await scorecard_uc.execute(
        strategy_name=body.strategy_name,
        max_runs=252,
    )

    alpha = await alpha_uc.execute(
        strategy_name=body.strategy_name,
        max_runs=252,
    )

    rules = await rules_uc.execute(
        strategy_name=body.strategy_name,
        max_runs=100,
    )

    engines = await engines_uc.execute(
        strategy_name=body.strategy_name,
        max_runs=100,
    )

    validation = await historical_validation_uc.execute(
        strategy_name=body.strategy_name,
        window_years=body.window_years,
    )

    return ResearchDashboardResponse(
        strategy_name=body.strategy_name,
        strategy_id=scorecard.strategy_id,
        scorecard=_scorecard_dto(scorecard),
        alpha_analysis=_alpha_dto(alpha),
        rule_effectiveness=_rules_dto(rules),
        engine_effectiveness=_engines_dto(engines),
        historical_validation=HistoricalValidationResponse(
            strategy_name=validation.strategy_name,
            strategy_id=validation.strategy_id,
            windows=[
                HistoricalValidationResultDTO(
                    strategy_name=w.strategy_name,
                    window=ValidationWindowDTO(
                        label=w.window.label,
                        start_date=w.window.start_date,
                        end_date=w.window.end_date,
                        trading_days=w.window.trading_days,
                    ),
                    total_runs=w.total_runs,
                    successful_runs=w.successful_runs,
                    failed_runs=w.failed_runs,
                    run_ids=list(w.run_ids),
                    summary=w.summary,
                )
                for w in validation.windows
            ],
            total_trading_days=validation.total_trading_days,
            total_successful_runs=validation.total_successful_runs,
            overall_pass_rate=validation.overall_pass_rate,
            generated_at=validation.generated_at,
        ),
        ranking_stability=scorecard.avg_top_rank_stability,
        false_positive_rate=scorecard.false_positive_rate,
        false_negative_rate=scorecard.false_negative_rate,
    )
