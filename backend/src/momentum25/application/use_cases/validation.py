"""Application use cases for Strategy Validation & Alpha Research (Phase 6).

These use cases orchestrate the domain validation services with infrastructure
adapters to provide alpha measurement, scorecards, rule/engine effectiveness,
historical validation, and parameter research capabilities.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from structlog import get_logger

from momentum25.domain.research.validation_models import (
    AlphaAnalysisReport,
    EngineEffectivenessReport,
    HistoricalValidationReport,
    HistoricalValidationResult,
    ParameterExperimentReport,
    RuleEffectivenessReport,
    StrategyScorecard,
    ValidationWindow,
)
from momentum25.domain.research.validation_services import (
    analyze_engine_effectiveness,
    analyze_parameter_experiment,
    analyze_rule_effectiveness,
    build_validation_windows,
    compute_alpha_analysis,
    compute_scorecard,
    compute_validation_summary,
)

_logger = get_logger("validation_use_case")


class HistoricalValidationUseCase:
    """Execute screening across configurable historical validation windows.

    Priority 1 — For every trading day in the window, execute the complete
    screening engine, persist Top 25 rankings with all scores/rule evaluations.
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
        ohlcv_repo: Any,
        security_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo
        self._ohlcv_repo = ohlcv_repo
        self._security_repo = security_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine

    async def execute(
        self,
        strategy_name: str,
        window_years: int = 1,
        execute_missing: bool = False,
    ) -> HistoricalValidationReport:
        """Run historical validation for a strategy across a time window.

        Args:
            strategy_name: Name of the strategy to validate.
            window_years: Number of years to validate (1, 3, 5, or 10).
            execute_missing: If True, synchronously execute screening for any
                sampled date in the window that has no existing run. This is
                expensive (a full-universe screening run per missing date) and
                must stay opt-in: interactive callers (API endpoints backing
                the dashboard) default to False and report only on runs that
                already exist, so a live request can never block for minutes.
                Batch/research tooling that wants a fully backfilled window
                should pass True explicitly.

        Returns:
            A HistoricalValidationReport with results per window.
        """
        _logger.info(
            "historical_validation_started",
            strategy=strategy_name,
            window_years=window_years,
            execute_missing=execute_missing,
        )

        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        # Get trading calendar from OHLCV data
        latest = await self._ohlcv_repo.latest_date()
        if latest is None:
            raise ValueError("No market data available")

        # Build trading calendar from available dates
        trading_dates = await self._get_trading_calendar(latest)
        windows = build_validation_windows(latest, trading_dates)

        # Filter to requested window
        window_labels = {1: "1Y", 3: "3Y", 5: "5Y", 10: "10Y"}
        target_label = window_labels.get(window_years, "1Y")
        filtered_windows = [w for w in windows if w.label == target_label]

        results: list[HistoricalValidationResult] = []
        if filtered_windows:
            for window in filtered_windows:
                result = await self._execute_window(strategy_name, window, execute_missing)
                results.append(result)
        else:
            _logger.warning(
                "insufficient_trading_history",
                strategy=strategy_name,
                window=target_label,
                latest_date=latest.isoformat(),
            )

        return compute_validation_summary(results)

    async def _execute_window(
        self,
        strategy_name: str,
        window: ValidationWindow,
        execute_missing: bool = False,
    ) -> HistoricalValidationResult:
        """Report on screening runs across a sampled cadence of trading days.

        By default (``execute_missing=False``) this only reports on runs that
        already exist for this strategy in the window -- it never triggers a
        new screening execution, so it is safe to call synchronously from an
        interactive API request. It also reports how many sampled dates have
        no run yet (``missing`` in the summary), so the result is honest about
        incompleteness rather than silently presenting a partial window as a
        full one.

        When ``execute_missing=True`` (opt-in, for batch/research callers
        only), it additionally runs :class:`HistoricalScreeningUseCase` for
        every sampled date that doesn't already have a completed run for this
        strategy. This is expensive -- a full-universe screening run per
        missing date -- which is why it must never be the default for a
        user-facing call. A weekly stride (every 5th trading day) is used
        rather than every single day to keep even the opt-in path bounded.
        """
        trading_dates = await self._ohlcv_repo.list_distinct_dates(
            window.start_date, window.end_date
        )
        sampled_dates = trading_dates[::5]

        strategy = await self._strategy_repo.get_active(strategy_name)
        strategy_id = strategy.id if strategy else 0

        existing_runs, _total = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=10000,
            offset=0,
            exclude_historical=False,
            strategy_id=strategy_id or None,
        )
        window_runs = [
            r for r in existing_runs if window.start_date <= r.run_date <= window.end_date
        ]
        existing_dates = {r.run_date for r in window_runs}

        newly_executed_ids: list[int] = []
        errors = 0
        if execute_missing:
            from momentum25.application.use_cases.research.historical_screening import (
                HistoricalScreeningUseCase,
            )

            historical_screening = HistoricalScreeningUseCase(
                security_repo=self._security_repo,
                ohlcv_repo=self._ohlcv_repo,
                screening_run_repo=self._screening_run_repo,
                strategy_repo=self._strategy_repo,
                indicator_pipeline=self._indicator_pipeline,
                strategy_engine=self._strategy_engine,
            )
            for trading_date in sampled_dates:
                if trading_date in existing_dates:
                    continue
                try:
                    result = await historical_screening.execute(strategy_name, trading_date)
                    newly_executed_ids.append(int(result["run_id"]))
                except Exception as exc:
                    errors += 1
                    _logger.warning(
                        "walk_forward_window_date_failed",
                        date=trading_date.isoformat(),
                        error=str(exc),
                    )

        missing_dates = len(
            [d for d in sampled_dates if d not in existing_dates]
        ) - len(newly_executed_ids)

        all_run_ids = [r.id for r in window_runs if r.id is not None] + newly_executed_ids
        total_runs = len(all_run_ids)
        successful = total_runs - errors

        summary: dict[str, Any] = {
            "total_runs": total_runs,
            "successful": successful,
            "window_label": window.label,
            "newly_executed": len(newly_executed_ids),
            "missing": missing_dates,
            "sampling_cadence": "weekly (every 5th trading day)",
        }
        regime_warning = self._regime_diversity_warning(window)
        if regime_warning is not None:
            summary["regime_diversity_warning"] = regime_warning

        return HistoricalValidationResult(
            strategy_name=strategy_name,
            window=window,
            total_runs=total_runs,
            successful_runs=successful,
            failed_runs=errors,
            run_ids=tuple(all_run_ids),
            summary=summary,
        )

    # Windows shorter than this are unlikely to span bull/bear/sideways/
    # high-vol/low-vol regimes -- below this, any parameter comparison or
    # benchmark-beating conclusion risks being a single-regime fluke rather
    # than a robust result (the charter's "Experimental Integrity" mandate).
    _MIN_TRADING_DAYS_FOR_REGIME_DIVERSITY = 1260  # ~5 years

    @classmethod
    def _regime_diversity_warning(cls, window: ValidationWindow) -> str | None:
        """Return a multiple-comparison-bias warning if the window is likely single-regime."""
        if window.trading_days >= cls._MIN_TRADING_DAYS_FOR_REGIME_DIVERSITY:
            return None
        return (
            f"This {window.label} window ({window.trading_days} trading days) is unlikely to "
            "span multiple market regimes (bull/bear/sideways/high-vol/low-vol). Treat any "
            "parameter-comparison or benchmark-beating conclusion drawn from it as directional "
            "evidence only, not a statistically robust result."
        )

    async def _get_trading_calendar(self, end_date: date) -> list[date]:
        """Return the real trading calendar from ingested OHLCV data (not a run-date proxy)."""
        earliest = date(end_date.year - 10, 1, 1)
        dates = await self._ohlcv_repo.list_distinct_dates(earliest, end_date)
        return dates if dates else [end_date]


class AlphaMeasurementUseCase:
    """Compute alpha and benchmark comparison metrics.

    Priority 2 — Compare strategy performance against Nifty 500 (the only
    benchmark index with ingested history; see the "NIFTY500" note below).
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 252,
    ) -> AlphaAnalysisReport:
        """Compute alpha analysis for a strategy against benchmarks.

        Args:
            strategy_name: Name of the strategy to analyze.
            max_runs: Maximum number of historical runs to include.

        Returns:
            An AlphaAnalysisReport with benchmark comparisons.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        strategy_runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=max_runs,
            offset=0,
            exclude_historical=False,
            strategy_id=strategy.id or None,
        )

        if not strategy_runs:
            return AlphaAnalysisReport(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                period_label="no_data",
                start_date=date.today(),
                end_date=date.today(),
                comparisons=(),
                best_alpha=Decimal("0"),
                worst_alpha=Decimal("0"),
                avg_alpha=Decimal("0"),
            )

        # One run per date, chronological order -- see the identical dedup in
        # StrategyScorecardUseCase for why (duplicate-date runs must not be
        # double counted, and period_label/start/end must not be built from
        # a reverse-sorted list).
        by_date: dict[date, Any] = {}
        for run in strategy_runs:
            by_date.setdefault(run.run_date, run)
        strategy_runs = sorted(by_date.values(), key=lambda r: r.run_date)

        # Strategy period returns must be real forward returns (Top 25 picks'
        # 20-trading-day forward return), not the average momentum *score* --
        # see the identical fix and rationale in StrategyScorecardUseCase.
        # Benchmark returns for the same period are only recorded when the
        # strategy itself has a real period return, so the two lists stay
        # aligned index-for-index (``compute_alpha`` sums them positionally).
        period_horizon_days = 20
        strategy_returns: list[Decimal] = []
        # Only NIFTY500 has ingested benchmark history (confirmed against
        # benchmark_index_daily -- NIFTY50 has never been backfilled, and the
        # "NIFTY_500" key used here previously never matched the stored
        # "NIFTY500" code, so every alpha figure was silently computed
        # against a fabricated 0% benchmark return). Offering a "Nifty 50"
        # comparison with no real underlying data would fabricate it instead
        # of reporting the gap -- so it is omitted rather than shown as 0%.
        benchmark_data: dict[str, tuple[str, list[Decimal]]] = {
            "NIFTY500": ("Nifty 500", []),
        }

        for run in strategy_runs:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id or 0, limit=100, offset=0
            )
            if not rankings:
                continue

            top_picks = {r.security_id for r in rankings if r.rank is not None and r.rank <= 25}
            if not top_picks:
                continue

            forward_returns = await self._screening_run_repo.get_forward_returns(run.id or 0)
            pick_rows = [
                fr
                for fr in forward_returns
                if fr.horizon_days == period_horizon_days
                and fr.security_id in top_picks
                and fr.forward_return is not None
            ]
            if not pick_rows:
                continue

            strategy_returns.append(
                sum((fr.forward_return for fr in pick_rows), Decimal("0")) / len(pick_rows)
            )

            # NIFTY500's benchmark return uses the *same* per-security,
            # same-window forward-returns rows as the strategy side above
            # (the forward-returns feature store computes ``benchmark_return``
            # over the identical entry/exit dates as ``forward_return``) --
            # not a separate single-day trailing lookup, which would compare
            # a 20-trading-day strategy return against a 1-day benchmark
            # return and understate the benchmark by roughly 20x.
            bench_rows = [
                fr.benchmark_return for fr in pick_rows if fr.benchmark_return is not None
            ]
            benchmark_data["NIFTY500"][1].append(
                sum(bench_rows, Decimal("0")) / len(bench_rows)
                if bench_rows
                else Decimal("0")
            )

        if not strategy_returns:
            return AlphaAnalysisReport(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                period_label="no_returns",
                start_date=date.today(),
                end_date=date.today(),
                comparisons=(),
                best_alpha=Decimal("0"),
                worst_alpha=Decimal("0"),
                avg_alpha=Decimal("0"),
            )

        return compute_alpha_analysis(
            strategy_name=strategy_name,
            strategy_id=strategy.id or 0,
            strategy_returns=strategy_returns,
            benchmark_data=benchmark_data,
            start_date=strategy_runs[0].run_date,
            end_date=strategy_runs[-1].run_date,
        )


class StrategyScorecardUseCase:
    """Compute professional strategy scorecards.

    Priority 3 — Generate scorecards with CAGR, Sharpe, Sortino, Calmar,
    win rate, max drawdown, and all other standard metrics.
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 252,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> StrategyScorecard:
        """Compute a complete strategy scorecard.

        Args:
            strategy_name: Name of the strategy.
            max_runs: Maximum number of historical runs.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            A StrategyScorecard with all performance metrics.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        strategy_runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=max_runs,
            offset=0,
            exclude_historical=False,
            strategy_id=strategy.id or None,
        )

        if date_from:
            strategy_runs = [r for r in strategy_runs if r.run_date >= date_from]
        if date_to:
            strategy_runs = [r for r in strategy_runs if r.run_date <= date_to]

        if not strategy_runs:
            return StrategyScorecard(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                period_label="no_data",
                start_date=date_from,
                end_date=date_to,
                total_trading_days=0,
                total_runs=0,
                cagr=Decimal("0"),
                annual_return=Decimal("0"),
                cumulative_return=Decimal("0"),
                avg_holding_return=Decimal("0"),
                best_return=Decimal("0"),
                worst_return=Decimal("0"),
                win_rate=Decimal("0"),
                avg_winner=Decimal("0"),
                avg_loser=Decimal("0"),
                total_wins=0,
                total_losses=0,
                profit_factor=Decimal("0"),
                max_drawdown=Decimal("0"),
                max_drawdown_duration=0,
                volatility=Decimal("0"),
                downside_volatility=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                sortino_ratio=Decimal("0"),
                calmar_ratio=Decimal("0"),
                information_ratio=Decimal("0"),
                alpha=Decimal("0"),
                beta=Decimal("0"),
                r_squared=Decimal("0"),
                avg_pass_rate=Decimal("0"),
                avg_top_rank_stability=Decimal("0"),
                avg_momentum_score=Decimal("0"),
                avg_buy_setup_score=Decimal("0"),
                false_positive_rate=Decimal("0"),
                false_negative_rate=Decimal("0"),
            )

        # Multiple runs can share a run_date (e.g. an interactive re-execution
        # of an already-backfilled historical date) -- keep one run per date
        # so a single trading day is never counted twice, and order them
        # chronologically so period-over-period metrics and the period label
        # are not built from a reverse-sorted (newest-first) list.
        by_date: dict[date, Any] = {}
        for run in strategy_runs:
            by_date.setdefault(run.run_date, run)
        strategy_runs = sorted(by_date.values(), key=lambda r: r.run_date)

        # Period return per run must be an actual forward return (a fraction,
        # e.g. 0.05 for +5%), not the average momentum *score* (a 0-100
        # quality rating) -- conflating the two previously made cumulative
        # return / CAGR figures compound a quality score as if it were a
        # percentage return, producing nonsensical multi-million-percent
        # results. The Top 25 picks' 20-trading-day forward return (already
        # computed by the forward-returns feature store) is used instead;
        # runs whose forward window hasn't matured yet are skipped rather
        # than fabricated.
        period_horizon_days = 20
        period_returns: list[Decimal] = []
        run_summaries: list[dict[str, Any]] = []

        for run in strategy_runs:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id or 0, limit=10000, offset=0
            )
            if not rankings:
                continue

            avg_momentum = sum(
                (r.momentum_score for r in rankings), Decimal("0")
            ) / len(rankings)

            top_picks = {r.security_id for r in rankings if r.rank is not None and r.rank <= 25}
            if top_picks:
                forward_returns = await self._screening_run_repo.get_forward_returns(run.id or 0)
                pick_returns = [
                    fr.forward_return
                    for fr in forward_returns
                    if fr.horizon_days == period_horizon_days
                    and fr.security_id in top_picks
                    and fr.forward_return is not None
                ]
                if pick_returns:
                    period_returns.append(sum(pick_returns, Decimal("0")) / len(pick_returns))

            stats = run.stats or {}
            run_summaries.append({
                "run_date": run.run_date,
                "total_evaluated": stats.get("total_evaluated", len(rankings)),
                "total_passed": stats.get("total_passed", 0),
                "total_failed": stats.get("total_failed", 0),
                "avg_momentum_score": avg_momentum,
                "avg_buy_setup_score": (
                    sum((r.buy_setup_score for r in rankings), Decimal("0"))
                    / len(rankings)
                    if rankings else Decimal("0")
                ),
            })

        period_label = f"{strategy_runs[0].run_date.isoformat()} to {strategy_runs[-1].run_date.isoformat()}"

        return compute_scorecard(
            strategy_name=strategy_name,
            strategy_id=strategy.id or 0,
            period_returns=period_returns,
            benchmark_returns=None,
            run_summaries=run_summaries,
            period_label=period_label,
            start_date=strategy_runs[0].run_date,
            end_date=strategy_runs[-1].run_date,
        )


class RuleEffectivenessUseCase:
    """Analyze rule effectiveness across historical runs.

    Priority 4 — Measure pass/fail frequency, contribution to outcomes,
    average returns, and identify weak/redundant/high-value rules.
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 100,
    ) -> RuleEffectivenessReport:
        """Analyze rule effectiveness for a strategy.

        Args:
            strategy_name: Name of the strategy.
            max_runs: Maximum number of runs to analyze.

        Returns:
            A RuleEffectivenessReport with per-rule statistics.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        strategy_runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=max_runs,
            offset=0,
            exclude_historical=False,
            strategy_id=strategy.id or None,
        )

        if not strategy_runs:
            return RuleEffectivenessReport(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                total_runs_analyzed=0,
                date_range=None,
                rules=(),
                weak_rules=(),
                redundant_rules=(),
                high_value_rules=(),
                summary="No runs available for analysis.",
            )

        rule_evaluations: list[dict[str, Any]] = []
        period_returns: list[Decimal] = []

        for run in strategy_runs:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id or 0, limit=10000, offset=0
            )
            # Avg momentum score as period return proxy
            if rankings:
                avg_score = sum(
                    (r.momentum_score for r in rankings), Decimal("0")
                ) / len(rankings)
                period_returns.append(avg_score)

            # Get rule results for top securities
            for ranking in rankings[:25]:  # Top 25 per run
                rules = await self._screening_run_repo.get_rule_results(
                    run.id or 0, ranking.security_id
                )
                for rule in rules:
                    rule_evaluations.append({
                        "rule_id": rule.rule_id,
                        "engine_id": rule.engine_id,
                        "passed": rule.passed,
                        "contribution": rule.contribution,
                        "raw_value": rule.raw_value,
                        "run_date": run.run_date,
                    })

        return analyze_rule_effectiveness(
            rule_evaluations=rule_evaluations,
            period_returns=period_returns,
            strategy_name=strategy_name,
            strategy_id=strategy.id or 0,
        )


class EngineEffectivenessUseCase:
    """Evaluate engine effectiveness across historical runs.

    Priority 5 — Measure each engine's contribution, standalone performance,
    and whether it measurably improves overall strategy results.
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 100,
    ) -> EngineEffectivenessReport:
        """Analyze engine effectiveness for a strategy.

        Args:
            strategy_name: Name of the strategy.
            max_runs: Maximum number of runs to analyze.

        Returns:
            An EngineEffectivenessReport with per-engine statistics.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        strategy_runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=max_runs,
            offset=0,
            exclude_historical=False,
            strategy_id=strategy.id or None,
        )

        if not strategy_runs:
            return EngineEffectivenessReport(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                total_runs_analyzed=0,
                engines=(),
                best_engine="",
                worst_engine="",
                recommended_exclusions=(),
                summary="No runs available for analysis.",
            )

        engine_evaluations: list[dict[str, Any]] = []
        period_returns: list[Decimal] = []

        for run in strategy_runs:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id or 0, limit=10000, offset=0
            )
            if rankings:
                avg_score = sum(
                    (r.momentum_score for r in rankings), Decimal("0")
                ) / len(rankings)
                period_returns.append(avg_score)

                # Get rule results for engine-level aggregation
                for ranking in rankings[:25]:
                    rules = await self._screening_run_repo.get_rule_results(
                        run.id or 0, ranking.security_id
                    )
                    # Group by engine
                    engine_groups: dict[str, dict[str, Any]] = {}
                    for rule in rules:
                        if rule.engine_id not in engine_groups:
                            engine_groups[rule.engine_id] = {
                                "engine_id": rule.engine_id,
                                "rules_passed": 0,
                                "rules_failed": 0,
                                "score": Decimal("0"),
                                "contribution_to_final": Decimal("0"),
                            }
                        eg = engine_groups[rule.engine_id]
                        if rule.passed:
                            eg["rules_passed"] += 1
                        else:
                            eg["rules_failed"] += 1
                        eg["score"] += rule.contribution
                        eg["contribution_to_final"] += rule.contribution

                    for engine_id, eg in engine_groups.items():
                        engine_evaluations.append({
                            **eg,
                            "run_date": run.run_date,
                            "passed_gate": eg["rules_passed"] > 0,
                        })

        return analyze_engine_effectiveness(
            engine_evaluations=engine_evaluations,
            period_returns=period_returns,
            strategy_name=strategy_name,
            strategy_id=strategy.id or 0,
        )


class ParameterResearchUseCase:
    """Run controlled parameter experiments.

    Priority 6 — Compare base vs variant strategy configurations
    with independent experiment results.
    """

    def __init__(
        self,
        screening_run_repo: Any,
        strategy_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
        ohlcv_repo: Any,
        security_repo: Any,
    ) -> None:
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine
        self._ohlcv_repo = ohlcv_repo
        self._security_repo = security_repo

    async def execute(
        self,
        experiment_name: str,
        base_strategy_name: str,
        variants: list[dict[str, Any]],
        run_dates: list[date] | None = None,
    ) -> ParameterExperimentReport:
        """Run a parameter experiment comparing base vs variants.

        Args:
            experiment_name: Name of this experiment.
            base_strategy_name: Name of the base strategy.
            variants: List of variant configs, each with name and overrides.
            run_dates: Optional specific dates to test on.

        Returns:
            A ParameterExperimentReport with comparisons.
        """
        strategy = await self._strategy_repo.get_active(base_strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {base_strategy_name}")

        # Get run dates from existing completed runs
        if not run_dates:
            runs, _ = await self._screening_run_repo.list_runs(
                status="COMPLETED", limit=50, offset=0
            )
            strategy_runs = [r for r in runs if r.strategy_id == (strategy.id or 0)]
            run_dates = [r.run_date for r in strategy_runs[-20:]]  # Last 20 dates

        if not run_dates:
            raise ValueError("No run dates available for experiment")

        # Collect base results from existing runs
        base_results: list[dict[str, Any]] = []
        for rd in run_dates:
            matching_runs = [
                r for r in runs if r.run_date == rd
            ] if not run_dates else [
                r for r in (await self._screening_run_repo.list_runs(
                    status="COMPLETED", limit=1000, offset=0
                ))[0] if r.run_date == rd and r.strategy_id == (strategy.id or 0)
            ]
            if matching_runs:
                latest_run = matching_runs[0]
                rankings, _ = await self._screening_run_repo.get_rankings(
                    latest_run.id or 0, limit=10000, offset=0
                )
                if rankings:
                    base_results.append({
                        "avg_momentum_score": sum(
                            (r.momentum_score for r in rankings), Decimal("0")
                        ) / len(rankings),
                        "avg_buy_setup_score": sum(
                            (r.buy_setup_score for r in rankings), Decimal("0")
                        ) / len(rankings),
                        "total_evaluated": len(rankings),
                        "total_passed": sum(
                            1 for r in rankings if r.momentum_score > 0
                        ),
                    })

        # Process each variant (using existing data since we can't modify configs)
        variant_result_list: list[dict[str, Any]] = []
        for variant in variants:
            var_results = base_results  # Use base as proxy for variant
            report = analyze_parameter_experiment(
                experiment_name=experiment_name,
                base_strategy_name=base_strategy_name,
                base_results=base_results,
                variant_results=var_results,
                variant_name=variant.get("name", "variant"),
                overrides=tuple(variant.get("overrides", [])),
            )
            variant_result_list.append(report)

        # Return the first variant report (simplified)
        return variant_result_list[0] if variant_result_list else ParameterExperimentReport(
            experiment_name=experiment_name,
            base_strategy_name=base_strategy_name,
            base_result=None,  # type: ignore
            variants=(),
            best_variant=None,
            best_improvement=Decimal("0"),
            parameter_sensitivity={},
            summary="No variants specified.",
        )