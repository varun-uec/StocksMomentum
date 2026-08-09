"""Pure domain services for Strategy Validation & Alpha Research (Phase 6).

All services are deterministic, stateless, and perform no I/O. They operate
on domain value objects only and implement the core logic for alpha measurement,
scorecards, rule/engine effectiveness, and parameter research.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from momentum25.domain.research.validation_models import (
    MEASURABLE,
    NO_FORWARD_RETURNS,
    NO_RUNS,
    AlphaAnalysisReport,
    BenchmarkComparison,
    EngineEffectiveness,
    EngineEffectivenessReport,
    HistoricalValidationReport,
    HistoricalValidationResult,
    Measurability,
    ParameterExperimentReport,
    ParameterExperimentResult,
    RuleEffectiveness,
    RuleEffectivenessReport,
    StrategyScorecard,
    ValidationWindow,
)

_QUANT = Decimal("0.0001")
_TRADING_DAYS_PER_YEAR = Decimal("252")


def _mean_or_none(values: list[Decimal]) -> Decimal | None:
    """Return the mean of *values*, or ``None`` when there is nothing to average.

    ``None`` rather than ``0``: an empty sample is an absence of measurement,
    not a measurement of zero.
    """
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(str(len(values)))


def _quant_or_none(value: Decimal | None) -> Decimal | None:
    """Quantize *value*, preserving ``None`` instead of collapsing it to 0."""
    return None if value is None else value.quantize(_QUANT)


def _quant(value: Decimal | None) -> Decimal:
    """Quantize a Decimal to fixed precision, defaulting to 0."""
    if value is None:
        return Decimal("0").quantize(_QUANT)
    return value.quantize(_QUANT)


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    """Safely divide two Decimals, returning 0 if denominator is 0."""
    if den == Decimal("0"):
        return Decimal("0")
    return (num / den).quantize(_QUANT)


def _variance(values: list[Decimal], mean: Decimal) -> float:
    """Compute population variance."""
    if len(values) < 2:
        return 0.0
    squared_diffs = [float((v - mean) ** 2) for v in values]
    return sum(squared_diffs) / len(values)


def _std(values: list[Decimal]) -> Decimal:
    """Compute population standard deviation."""
    if len(values) < 2:
        return Decimal("0")
    mean = sum(values, Decimal("0")) / len(values)
    var = _variance(values, mean)
    return Decimal(str(var ** 0.5)).quantize(_QUANT)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 1 — Historical Validation
# ═══════════════════════════════════════════════════════════════════════════════


def build_validation_windows(
    end_date: date,
    trading_calendar: list[date],
) -> tuple[ValidationWindow, ...]:
    """Build standard validation windows from a trading calendar.

    Args:
        end_date: The end date for all windows.
        trading_calendar: Sorted list of all trading dates.

    Returns:
        Tuple of ValidationWindow for 1Y, 3Y, 5Y, 10Y.
    """
    windows: list[ValidationWindow] = []
    labels = [("1Y", 252), ("3Y", 756), ("5Y", 1260), ("10Y", 2520)]

    for label, trading_days in labels:
        if len(trading_calendar) >= trading_days:
            start_idx = len(trading_calendar) - trading_days
            start_date = trading_calendar[start_idx]
            windows.append(
                ValidationWindow(
                    label=label,
                    start_date=start_date,
                    end_date=end_date,
                    trading_days=trading_days,
                )
            )

    return tuple(windows)


def compute_validation_summary(
    results: list[HistoricalValidationResult],
) -> HistoricalValidationReport:
    """Aggregate individual validation window results into a report.

    Args:
        results: List of HistoricalValidationResult for each window.

    Returns:
        A consolidated HistoricalValidationReport.
    """
    total_trading_days = sum(r.window.trading_days for r in results)
    total_successful = sum(r.successful_runs for r in results)
    total_runs = sum(r.total_runs for r in results)

    overall_pass_rate = _safe_div(
        Decimal(str(total_successful)),
        Decimal(str(total_runs)) if total_runs > 0 else Decimal("1"),
    )

    return HistoricalValidationReport(
        strategy_name=results[0].strategy_name if results else "",
        strategy_id=0,
        windows=tuple(results),
        total_trading_days=total_trading_days,
        total_successful_runs=total_successful,
        overall_pass_rate=overall_pass_rate,
        generated_at=date.today().isoformat(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 2 — Alpha Measurement
# ═══════════════════════════════════════════════════════════════════════════════


def compute_alpha(
    strategy_returns: list[Decimal],
    benchmark_returns: list[Decimal],
    benchmark_code: str,
    benchmark_name: str,
    start_date: date,
    end_date: date,
) -> BenchmarkComparison:
    """Compute alpha and related metrics comparing strategy vs benchmark.

    Args:
        strategy_returns: List of period returns for the strategy.
        benchmark_returns: List of period returns for the benchmark.
        benchmark_code: Code identifying the benchmark (e.g. "NIFTY_50").
        benchmark_name: Human-readable benchmark name.
        start_date: Start of the analysis period.
        end_date: End of the analysis period.

    Returns:
        A BenchmarkComparison with all alpha metrics.
    """
    if not strategy_returns or not benchmark_returns:
        return BenchmarkComparison(
            benchmark_code=benchmark_code,
            benchmark_name=benchmark_name,
            strategy_return=Decimal("0"),
            benchmark_return=Decimal("0"),
            alpha=Decimal("0"),
            excess_return=Decimal("0"),
            relative_performance=Decimal("0"),
            annualized_return=Decimal("0"),
            benchmark_annualized_return=Decimal("0"),
            cagr=Decimal("0"),
            benchmark_cagr=Decimal("0"),
            rolling_returns=(),
        )

    # Cumulative returns
    strategy_cum = sum(strategy_returns, Decimal("0"))
    benchmark_cum = sum(benchmark_returns, Decimal("0"))

    # Simple returns
    strategy_return = _quant(strategy_cum)
    benchmark_return = _quant(benchmark_cum)
    alpha = _quant(strategy_return - benchmark_return)
    excess_return = _quant(strategy_return - benchmark_return)
    relative_perf = _safe_div(strategy_return, benchmark_return) - Decimal("1")

    # Annualized returns
    #
    # ``years`` must reflect the real calendar span (``start_date`` to
    # ``end_date``, always supplied by the caller), not the period-return
    # entry count -- an entry is one screening run's period return over
    # whatever horizon it was measured, not necessarily one trading day.
    # Deriving years from entry count silently assumed daily-cadence input
    # and produced absurd annualized/CAGR figures for weekly/monthly-cadence
    # runs (the normal case). See the identical fix in ``compute_scorecard``.
    n_periods = len(strategy_returns)
    if end_date > start_date:
        years = Decimal((end_date - start_date).days) / Decimal("365.25")
    else:
        years = Decimal(str(n_periods)) / _TRADING_DAYS_PER_YEAR
    ann_factor = years
    ann_return = _safe_div(strategy_return, ann_factor) if ann_factor > 0 else Decimal("0")
    bench_ann_return = _safe_div(benchmark_return, ann_factor) if ann_factor > 0 else Decimal("0")

    # CAGR: (1 + total_return)^(1/years) - 1
    # `base` is clamped to a small positive epsilon (not just an upper bound):
    # float precision loss can push it to <= 0 even when the Decimal guard
    # (`return > Decimal("-1")`) holds, and a non-positive base raised to a
    # fractional exponent silently returns a Python complex number rather than
    # raising -- which then fails Decimal(str(...)) with InvalidOperation
    # instead of ValueError/OverflowError. Both are now handled.
    if years > 0 and strategy_return > Decimal("-1"):
        try:
            base = 1 + float(strategy_return)
            base = min(max(base, 1e-12), 1e308)
            cagr = Decimal(str(base ** (1 / float(years)) - 1)).quantize(_QUANT)
        except (OverflowError, ValueError, ArithmeticError):
            cagr = Decimal("0")
    else:
        cagr = Decimal("0")
    if years > 0 and benchmark_return > Decimal("-1"):
        try:
            bench_base = 1 + float(benchmark_return)
            bench_base = min(max(bench_base, 1e-12), 1e308)
            bench_cagr = Decimal(
                str(bench_base ** (1 / float(years)) - 1)
            ).quantize(_QUANT)
        except (OverflowError, ValueError, ArithmeticError):
            bench_cagr = Decimal("0")
    else:
        bench_cagr = Decimal("0")

    # Rolling returns (simplified: 20-day rolling windows)
    rolling = []
    window = min(20, len(strategy_returns))
    for i in range(len(strategy_returns) - window + 1):
        strat_win = sum(strategy_returns[i : i + window], Decimal("0"))
        bench_win = sum(benchmark_returns[i : i + window], Decimal("0"))
        rolling.append({
            "period_start": i,
            "period_end": i + window - 1,
            "strategy_return": _quant(strat_win),
            "benchmark_return": _quant(bench_win),
        })

    return BenchmarkComparison(
        benchmark_code=benchmark_code,
        benchmark_name=benchmark_name,
        strategy_return=strategy_return,
        benchmark_return=benchmark_return,
        alpha=alpha,
        excess_return=excess_return,
        relative_performance=relative_perf,
        annualized_return=ann_return,
        benchmark_annualized_return=bench_ann_return,
        cagr=cagr,
        benchmark_cagr=bench_cagr,
        rolling_returns=tuple(rolling),
    )


def compute_alpha_analysis(
    strategy_name: str,
    strategy_id: int,
    strategy_returns: list[Decimal],
    benchmark_data: dict[str, tuple[str, list[Decimal]]],  # code → (name, returns)
    start_date: date,
    end_date: date,
) -> AlphaAnalysisReport:
    """Compute alpha analysis against multiple benchmarks.

    Args:
        strategy_name: Name of the strategy.
        strategy_id: ID of the strategy.
        strategy_returns: List of period returns for the strategy.
        benchmark_data: Dict mapping benchmark code to (name, returns list).
        start_date: Start of the analysis period.
        end_date: End of the analysis period.

    Returns:
        An AlphaAnalysisReport with comparisons against all benchmarks.
    """
    comparisons: list[BenchmarkComparison] = []
    alphas: list[Decimal] = []

    for code, (name, bench_returns) in benchmark_data.items():
        comp = compute_alpha(
            strategy_returns=strategy_returns,
            benchmark_returns=bench_returns,
            benchmark_code=code,
            benchmark_name=name,
            start_date=start_date,
            end_date=end_date,
        )
        comparisons.append(comp)
        alphas.append(comp.alpha)

    period_label = f"{start_date.isoformat()} to {end_date.isoformat()}"
    best_alpha = max(alphas) if alphas else Decimal("0")
    worst_alpha = min(alphas) if alphas else Decimal("0")
    avg_alpha = _safe_div(sum(alphas, Decimal("0")), Decimal(str(len(alphas)))) if alphas else Decimal("0")

    return AlphaAnalysisReport(
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        period_label=period_label,
        start_date=start_date,
        end_date=end_date,
        comparisons=tuple(comparisons),
        best_alpha=best_alpha,
        worst_alpha=worst_alpha,
        avg_alpha=avg_alpha,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3 — Strategy Scorecards
# ═══════════════════════════════════════════════════════════════════════════════


def _screening_metrics(
    run_summaries: list[dict[str, Any]], period_returns: list[Decimal]
) -> dict[str, Decimal | None]:
    """Screening-side scorecard metrics, shared by the measured and unmeasured paths.

    Pass rates and average scores come from run stats and are always
    computable. The false-positive/negative rates are return-derived and are
    ``None`` when no forward return exists.
    """
    n = len(period_returns)
    if not run_summaries:
        return {
            "avg_pass_rate": Decimal("0"),
            "avg_momentum_score": Decimal("0"),
            "avg_buy_setup_score": Decimal("0"),
            "false_positive_rate": None,
            "false_negative_rate": None,
        }

    total_evaluated = sum(s.get("total_evaluated", 0) for s in run_summaries)
    total_passed = sum(s.get("total_passed", 0) for s in run_summaries)
    avg_pass_rate = _safe_div(
        Decimal(str(total_passed)),
        Decimal(str(total_evaluated)) if total_evaluated > 0 else Decimal("1"),
    )

    momentum_scores = [
        s["avg_momentum_score"]
        for s in run_summaries
        if s.get("avg_momentum_score") is not None
    ]
    buy_scores = [
        s["avg_buy_setup_score"]
        for s in run_summaries
        if s.get("avg_buy_setup_score") is not None
    ]

    if n == 0:
        false_positive_rate = false_negative_rate = None
    else:
        # FP: run qualified securities but the period return was negative.
        # FN: run qualified nothing yet the period return was positive.
        fp_count = sum(
            1
            for i, r in enumerate(period_returns)
            if i < len(run_summaries)
            and run_summaries[i].get("total_passed", 0) > 0
            and r < 0
        )
        fn_count = sum(
            1
            for i, r in enumerate(period_returns)
            if i < len(run_summaries)
            and run_summaries[i].get("total_passed", 0) == 0
            and r > 0
        )
        false_positive_rate = _safe_div(Decimal(str(fp_count)), Decimal(str(n)))
        false_negative_rate = _safe_div(Decimal(str(fn_count)), Decimal(str(n)))

    return {
        "avg_pass_rate": avg_pass_rate,
        "avg_momentum_score": _mean_or_none(momentum_scores) or Decimal("0"),
        "avg_buy_setup_score": _mean_or_none(buy_scores) or Decimal("0"),
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
    }


def compute_scorecard(
    strategy_name: str,
    strategy_id: int,
    period_returns: list[Decimal],
    benchmark_returns: list[Decimal] | None,
    run_summaries: list[dict[str, Any]],
    period_label: str = "all",
    start_date: date | None = None,
    end_date: date | None = None,
) -> StrategyScorecard:
    """Compute a complete professional strategy scorecard.

    Args:
        strategy_name: Name of the strategy.
        strategy_id: ID of the strategy.
        period_returns: List of period returns (e.g. daily or weekly).
        benchmark_returns: Optional list of benchmark returns for beta/alpha.
        run_summaries: List of run summary dicts with screening stats.
        period_label: Label for the analysis period.
        start_date: Start date of the analysis.
        end_date: End date of the analysis.

    Returns:
        A fully populated StrategyScorecard.
    """
    n = len(period_returns)
    if n == 0:
        # No matured forward return for any analysed run. Every return-derived
        # metric is null with an explicit reason, so a reader can tell "never
        # measured" from "measured, and it earned nothing". Screening-side
        # metrics come from run stats and stay populated.
        screening = _screening_metrics(run_summaries, period_returns)
        return StrategyScorecard(
            strategy_name=strategy_name,
            strategy_id=strategy_id,
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            total_trading_days=0,
            total_runs=len(run_summaries),
            cagr=None,
            annual_return=None,
            cumulative_return=None,
            avg_holding_return=None,
            best_return=None,
            worst_return=None,
            win_rate=None,
            avg_winner=None,
            avg_loser=None,
            total_wins=None,
            total_losses=None,
            profit_factor=None,
            max_drawdown=None,
            max_drawdown_duration=None,
            volatility=None,
            downside_volatility=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            information_ratio=None,
            alpha=None,
            beta=None,
            r_squared=None,
            avg_pass_rate=screening["avg_pass_rate"],
            avg_top_rank_stability=Decimal("0"),
            avg_momentum_score=screening["avg_momentum_score"],
            avg_buy_setup_score=screening["avg_buy_setup_score"],
            false_positive_rate=None,
            false_negative_rate=None,
            measurability=Measurability(
                forward_returns_available=False,
                reason=NO_RUNS if not run_summaries else NO_FORWARD_RETURNS,
            ),
        )

    # ── Return metrics ────────────────────────────────────────────────────
    cumulative_return = sum(period_returns, Decimal("0"))
    avg_holding_return = _safe_div(cumulative_return, Decimal(str(n)))
    best_return = max(period_returns)
    worst_return = min(period_returns)

    # Annualized return
    #
    # ``years`` must reflect the actual calendar span the period returns
    # cover, not the entry count -- an entry is one screening run's period
    # return (whatever horizon that return was measured over), not
    # necessarily one trading day. Deriving years from entry count silently
    # assumed daily-cadence input; for weekly/monthly-cadence runs (the
    # normal case) that overstated the number of compounding periods per
    # year and produced absurd CAGR figures. The real date range is always
    # available from the caller (``start_date``/``end_date``), so use it.
    if start_date is not None and end_date is not None and end_date > start_date:
        years = Decimal((end_date - start_date).days) / Decimal("365.25")
    else:
        years = Decimal(str(n)) / _TRADING_DAYS_PER_YEAR
    annual_return = _safe_div(cumulative_return, years) if years > 0 else Decimal("0")

    # CAGR
    if years > 0 and cumulative_return > Decimal("-1"):
        try:
            base = 1 + float(cumulative_return)
            # Clamp to (epsilon, 1e308]: avoids float overflow with extreme proxy
            # returns, and guards against `base` landing at/below 0 due to float
            # precision loss near cumulative_return == -1 (Decimal(-1) compares
            # greater than -1, but the float conversion can still round to <= 0,
            # which makes `base ** fractional_exponent` return a Python complex
            # number instead of raising -- and Decimal(str(complex)) then raises
            # decimal.InvalidOperation rather than ValueError/OverflowError).
            base = min(max(base, 1e-12), 1e308)
            cagr = Decimal(
                str(base ** (1 / float(years)) - 1)
            ).quantize(_QUANT)
        except (OverflowError, ValueError, ArithmeticError):
            cagr = Decimal("0")
    else:
        cagr = Decimal("0")

    # ── Win/loss metrics ──────────────────────────────────────────────────
    winners = [r for r in period_returns if r > 0]
    losers = [r for r in period_returns if r < 0]
    total_wins = len(winners)
    total_losses = len(losers)
    win_rate = _safe_div(Decimal(str(total_wins)), Decimal(str(n)))
    avg_winner = _safe_div(sum(winners, Decimal("0")), Decimal(str(total_wins))) if winners else Decimal("0")
    avg_loser = _safe_div(sum(losers, Decimal("0")), Decimal(str(total_losses))) if losers else Decimal("0")

    # Profit factor
    gains = sum((r for r in period_returns if r > 0), Decimal("0"))
    losses = abs(sum((r for r in period_returns if r < 0), Decimal("0")))
    profit_factor = _safe_div(gains, losses) if losses > 0 else (Decimal("999.9999") if gains > 0 else Decimal("0"))

    # ── Risk metrics ──────────────────────────────────────────────────────
    volatility = _std(period_returns) * Decimal(str(252.0 ** 0.5))  # annualized

    # Downside deviation
    downside = [float(r) for r in period_returns if r < 0]
    if downside:
        downside_var = sum(d ** 2 for d in downside) / len(downside)
        downside_vol = Decimal(str(downside_var ** 0.5)) * Decimal(str(252.0 ** 0.5))
    else:
        downside_vol = Decimal("0")

    # Max drawdown
    max_dd = Decimal("0")
    max_dd_duration = 0
    peak = Decimal("1")
    current_dd_duration = 0
    running_cum = Decimal("1")
    for r in period_returns:
        running_cum = running_cum * (Decimal("1") + r)
        if running_cum > peak:
            peak = running_cum
            current_dd_duration = 0
        else:
            dd = (peak - running_cum) / peak
            current_dd_duration += 1
            if dd > max_dd:
                max_dd = dd
                max_dd_duration = current_dd_duration

    # ── Risk-adjusted return metrics ──────────────────────────────────────
    mean_return = _safe_div(cumulative_return, Decimal(str(n)))
    sharpe = Decimal("0")
    if volatility > 0:
        sharpe = _safe_div(mean_return * _TRADING_DAYS_PER_YEAR, volatility)

    sortino = Decimal("0")
    if downside_vol > 0:
        sortino = _safe_div(mean_return * _TRADING_DAYS_PER_YEAR, downside_vol)

    calmar = _safe_div(cagr, max_dd) if max_dd > 0 else Decimal("0")

    # ── Market-relative metrics ───────────────────────────────────────────
    alpha = Decimal("0")
    beta = Decimal("0")
    r_squared = Decimal("0")
    information_ratio = Decimal("0")

    if benchmark_returns and len(benchmark_returns) == n:
        bench_mean = _safe_div(sum(benchmark_returns, Decimal("0")), Decimal(str(n)))
        bench_std = _std(benchmark_returns)

        # Beta: covariance(strategy, benchmark) / variance(benchmark)
        if bench_std > 0:
            cov = sum(
                float((period_returns[i] - mean_return) * (benchmark_returns[i] - bench_mean))
                for i in range(n)
            ) / n
            bench_var = sum(float((b - bench_mean) ** 2) for b in benchmark_returns) / n
            if bench_var > 0:
                beta = Decimal(str(cov / bench_var)).quantize(_QUANT)
                alpha = (mean_return - beta * bench_mean) * _TRADING_DAYS_PER_YEAR
                alpha = _quant(alpha)

            # R-squared: (correlation)^2
            if bench_std > 0 and volatility > 0:
                corr = Decimal(str(cov / (float(bench_std) * float(volatility)))).quantize(_QUANT)
                r_squared = (corr ** 2).quantize(_QUANT)

            # Information ratio: excess return / tracking error
            excess_returns = [
                period_returns[i] - benchmark_returns[i] for i in range(n)
            ]
            excess_mean = _safe_div(sum(excess_returns, Decimal("0")), Decimal(str(n)))
            tracking_error = _std(excess_returns) * Decimal(str(252.0 ** 0.5))
            if tracking_error > 0:
                information_ratio = _safe_div(excess_mean * _TRADING_DAYS_PER_YEAR, tracking_error)

    # ── Screening-specific metrics ────────────────────────────────────────
    screening = _screening_metrics(run_summaries, period_returns)
    avg_pass_rate = screening["avg_pass_rate"]
    avg_top_rank_stability = Decimal("0")
    avg_momentum_score = screening["avg_momentum_score"]
    avg_buy_setup_score = screening["avg_buy_setup_score"]
    false_positive_rate = screening["false_positive_rate"]
    false_negative_rate = screening["false_negative_rate"]

    # ── Monthly/yearly returns ────────────────────────────────────────────
    monthly_returns = _compute_period_returns(period_returns, 21)  # ~21 trading days/month
    yearly_returns = _compute_period_returns(period_returns, 252)

    # Rolling Sharpe (60-day windows)
    rolling_sharpe = []
    window = min(60, n)
    for i in range(n - window + 1):
        win_returns = period_returns[i : i + window]
        win_mean = _safe_div(sum(win_returns, Decimal("0")), Decimal(str(window)))
        win_std = _std(win_returns)
        if win_std > 0:
            rs = _safe_div(win_mean * _TRADING_DAYS_PER_YEAR, win_std)
        else:
            rs = Decimal("0")
        rolling_sharpe.append({"period": i, "sharpe": rs})

    return StrategyScorecard(
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        period_label=period_label,
        start_date=start_date,
        end_date=end_date,
        total_trading_days=n,
        total_runs=len(run_summaries),
        cagr=_quant(cagr),
        annual_return=_quant(annual_return),
        cumulative_return=_quant(cumulative_return),
        avg_holding_return=_quant(avg_holding_return),
        best_return=_quant(best_return),
        worst_return=_quant(worst_return),
        win_rate=_quant(win_rate),
        avg_winner=_quant(avg_winner),
        avg_loser=_quant(avg_loser),
        total_wins=total_wins,
        total_losses=total_losses,
        profit_factor=_quant(profit_factor),
        max_drawdown=_quant(max_dd),
        max_drawdown_duration=max_dd_duration,
        volatility=_quant(volatility),
        downside_volatility=_quant(downside_vol),
        sharpe_ratio=_quant(sharpe),
        sortino_ratio=_quant(sortino),
        calmar_ratio=_quant(calmar),
        information_ratio=_quant(information_ratio),
        alpha=_quant(alpha),
        beta=_quant(beta),
        r_squared=_quant(r_squared),
        avg_pass_rate=_quant(avg_pass_rate),
        avg_top_rank_stability=_quant(avg_top_rank_stability),
        avg_momentum_score=_quant(avg_momentum_score),
        avg_buy_setup_score=_quant(avg_buy_setup_score),
        false_positive_rate=_quant(false_positive_rate),
        false_negative_rate=_quant(false_negative_rate),
        monthly_returns=tuple(monthly_returns),
        yearly_returns=tuple(yearly_returns),
        rolling_sharpe=tuple(rolling_sharpe),
    )


def _compute_period_returns(
    daily_returns: list[Decimal], period_days: int
) -> list[dict[str, Any]]:
    """Aggregate daily returns into period returns (e.g. monthly, yearly)."""
    periods: list[dict[str, Any]] = []
    for i in range(0, len(daily_returns), period_days):
        chunk = daily_returns[i : i + period_days]
        if chunk:
            period_return = sum(chunk, Decimal("0"))
            periods.append({
                "period": i // period_days,
                "return": _quant(period_return),
                "days": len(chunk),
            })
    return periods


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4 — Rule Effectiveness Analysis
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_rule_effectiveness(
    rule_evaluations: list[dict[str, Any]],
    run_count: int,
    strategy_name: str,
    strategy_id: int,
) -> RuleEffectivenessReport:
    """Analyze the effectiveness of every rule across historical runs.

    Each evaluation must already carry its own realised forward return, joined
    upstream on ``(run_id, security_id)``. Two defects motivated that shape
    (2026-08-09 audit, §1.2.4):

    * the "return" was the run's *average momentum score* -- a 0-100 setup
      quality rating -- published as ``avg_return_when_passes``; and
    * it was matched to evaluations by **list index**, while
      ``period_returns`` held one entry per run and ``evals`` one per
      (rule x security x run). With one run, exactly one of 25 evaluations per
      rule received a value and the other 24 were silently dropped.

    When no evaluation carries a forward return, every return-derived field
    and every classification (``is_weak`` / ``is_redundant`` /
    ``is_high_value``) is ``None`` and ``measurability`` says why. Nothing is
    reported as zero that was never measured.

    Args:
        rule_evaluations: Dicts with rule_id, engine_id, passed, contribution,
            raw_value, run_date, and ``forward_return`` (``Decimal | None``).
        run_count: Number of distinct runs the evaluations came from.
        strategy_name: Name of the strategy.
        strategy_id: ID of the strategy.

    Returns:
        A RuleEffectivenessReport with per-rule statistics.
    """
    measurable = any(ev.get("forward_return") is not None for ev in rule_evaluations)
    measurability = (
        MEASURABLE
        if measurable
        else Measurability(
            forward_returns_available=False,
            reason=NO_RUNS if not rule_evaluations else NO_FORWARD_RETURNS,
        )
    )

    # Group evaluations by rule
    rule_groups: dict[str, list[dict[str, Any]]] = {}
    for ev in rule_evaluations:
        key = f"{ev.get('engine_id', '')}:{ev.get('rule_id', '')}"
        rule_groups.setdefault(key, []).append(ev)

    rules: list[RuleEffectiveness] = []
    dates: list[date] = []

    for key, evals in rule_groups.items():
        engine_id, rule_id = key.split(":", 1)
        n = len(evals)
        pass_count = sum(1 for e in evals if e.get("passed", False))
        fail_count = n - pass_count
        pass_rate = _safe_div(Decimal(str(pass_count)), Decimal(str(n)))

        # Per-evaluation returns, joined on (run_id, security_id) by the caller.
        with_return = [e for e in evals if e.get("forward_return") is not None]
        returns_when_passes = [
            e["forward_return"] for e in with_return if e.get("passed", False)
        ]
        returns_when_fails = [
            e["forward_return"] for e in with_return if not e.get("passed", False)
        ]

        avg_return_pass = _mean_or_none(returns_when_passes)
        avg_return_fail = _mean_or_none(returns_when_fails)

        # Contribution to profitable vs unprofitable outcomes, on the same join.
        contrib_success = [
            e.get("contribution", Decimal("0"))
            for e in with_return
            if e["forward_return"] > 0
        ]
        contrib_unsuccess = [
            e.get("contribution", Decimal("0"))
            for e in with_return
            if e["forward_return"] <= 0
        ]
        avg_contrib_success = _mean_or_none(contrib_success)
        avg_contrib_unsuccess = _mean_or_none(contrib_unsuccess)

        if avg_return_pass is not None and avg_return_fail is not None:
            return_delta = avg_return_pass - avg_return_fail
            significance = min(
                Decimal("1"),
                abs(return_delta)
                * Decimal("10")
                * Decimal(str(len(with_return) ** 0.5))
                / Decimal("100"),
            )
            is_weak = pass_rate < Decimal("0.3") and abs(return_delta) < Decimal("0.01")
            is_redundant = pass_rate > Decimal("0.95")
            is_high_value = (
                return_delta > Decimal("0.02")
                and Decimal("0.3") <= pass_rate <= Decimal("0.95")
            )
        else:
            # A rule evaluated on only one side of its own pass/fail split, or
            # with no matured returns at all, has no measurable delta. It is
            # not "weak" -- it is unmeasured. S6: no rule may be added,
            # removed or reweighted on the strength of a null.
            return_delta = None
            significance = None
            is_weak = is_redundant = is_high_value = None

        rules.append(
            RuleEffectiveness(
                rule_id=rule_id,
                engine_id=engine_id,
                rule_name=rule_id.replace("_", " ").title(),
                total_evaluations=n,
                pass_count=pass_count,
                fail_count=fail_count,
                pass_rate=_quant(pass_rate),
                contribution_to_successful=_quant_or_none(avg_contrib_success),
                contribution_to_unsuccessful=_quant_or_none(avg_contrib_unsuccess),
                avg_return_when_passes=_quant_or_none(avg_return_pass),
                avg_return_when_fails=_quant_or_none(avg_return_fail),
                return_delta=_quant_or_none(return_delta),
                significance_score=_quant_or_none(significance),
                is_weak=is_weak,
                is_redundant=is_redundant,
                is_high_value=is_high_value,
            )
        )

        for e in evals:
            rd = e.get("run_date")
            if isinstance(rd, date):
                dates.append(rd)

    # Most significant first; unmeasured rules sort last rather than as zeros.
    rules.sort(
        key=lambda r: (
            r.significance_score is None,
            -(r.significance_score or Decimal("0")),
            r.rule_id,
        )
    )

    weak_rules = tuple(r for r in rules if r.is_weak)
    redundant_rules = tuple(r for r in rules if r.is_redundant)
    high_value_rules = tuple(r for r in rules if r.is_high_value)

    date_range = (min(dates), max(dates)) if len(dates) >= 2 else None

    if not measurable:
        summary = (
            "Rule effectiveness is not measurable: no matured forward returns "
            "exist for these runs. Pass rates and contributions are shown; "
            "return-based verdicts are withheld."
        )
    else:
        summary_parts = []
        if high_value_rules:
            summary_parts.append(
                f"Found {len(high_value_rules)} high-value rules that consistently "
                f"contribute to positive outcomes."
            )
        if redundant_rules:
            summary_parts.append(
                f"Found {len(redundant_rules)} redundant rules (pass rate > 95%) "
                f"that rarely fail and may be candidates for removal."
            )
        if weak_rules:
            summary_parts.append(
                f"Found {len(weak_rules)} weak rules with low pass rate and "
                f"minimal return impact."
            )
        summary = (
            " ".join(summary_parts)
            if summary_parts
            else "All rules show meaningful contribution."
        )

    return RuleEffectivenessReport(
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        total_runs_analyzed=run_count,
        date_range=date_range,
        rules=tuple(rules),
        weak_rules=weak_rules,
        redundant_rules=redundant_rules,
        high_value_rules=high_value_rules,
        summary=summary,
        measurability=measurability,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5 — Engine Effectiveness Analysis
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_engine_effectiveness(
    engine_evaluations: list[dict[str, Any]],
    run_count: int,
    strategy_name: str,
    strategy_id: int,
) -> EngineEffectivenessReport:
    """Analyze the effectiveness of every engine across historical runs.

    Same contract as :func:`analyze_rule_effectiveness`: each evaluation
    carries its own realised forward return, joined upstream on
    ``(run_id, security_id)``. The former ``standalone_performance`` field --
    which reported the run's average momentum *score* as if it were a return
    (2026-08-09 audit §1.2.4/§2.3) -- is replaced by
    ``avg_forward_return_when_engine_scores_high``, which is either a real
    return or ``None``.

    Args:
        engine_evaluations: Dicts with engine_id, score, passed_gate,
            rules_passed, rules_failed, run_date, contribution_to_final and
            ``forward_return`` (``Decimal | None``).
        run_count: Number of distinct runs the evaluations came from.
        strategy_name: Name of the strategy.
        strategy_id: ID of the strategy.

    Returns:
        An EngineEffectivenessReport with per-engine statistics.
    """
    measurable = any(ev.get("forward_return") is not None for ev in engine_evaluations)
    measurability = (
        MEASURABLE
        if measurable
        else Measurability(
            forward_returns_available=False,
            reason=NO_RUNS if not engine_evaluations else NO_FORWARD_RETURNS,
        )
    )

    engine_groups: dict[str, list[dict[str, Any]]] = {}
    for ev in engine_evaluations:
        eid = ev.get("engine_id", "")
        engine_groups.setdefault(eid, []).append(ev)

    all_returns = [
        ev["forward_return"]
        for ev in engine_evaluations
        if ev.get("forward_return") is not None
    ]
    overall_avg_return = _mean_or_none(all_returns)

    engines: list[EngineEffectiveness] = []
    for engine_id, evals in engine_groups.items():
        n = len(evals)
        scores = [e.get("score", Decimal("0")) for e in evals]
        avg_score = _safe_div(sum(scores, Decimal("0")), Decimal(str(n)))

        avg_passed = _safe_div(
            Decimal(str(sum(e.get("rules_passed", 0) for e in evals))), Decimal(str(n))
        )
        avg_failed = _safe_div(
            Decimal(str(sum(e.get("rules_failed", 0) for e in evals))), Decimal(str(n))
        )

        pass_rates = []
        for e in evals:
            total = e.get("rules_passed", 0) + e.get("rules_failed", 0)
            if total > 0:
                pass_rates.append(Decimal(str(e.get("rules_passed", 0))) / Decimal(str(total)))
        avg_pass_rate = _mean_or_none(pass_rates) or Decimal("0")

        final_contributions = [e.get("contribution_to_final", Decimal("0")) for e in evals]
        avg_contrib = _mean_or_none(final_contributions) or Decimal("0")

        with_return = [e for e in evals if e.get("forward_return") is not None]

        # Directional agreement between this engine's score and the realised
        # return of the security it scored -- a genuine per-security join now,
        # not a run-indexed one.
        if with_return:
            correlated = sum(
                1
                for e in with_return
                if (e.get("score", Decimal("0")) > 0) == (e["forward_return"] > 0)
            )
            correlation = _safe_div(
                Decimal(str(correlated)), Decimal(str(len(with_return)))
            )
            high_score_returns = [
                e["forward_return"]
                for e in with_return
                if e.get("score", Decimal("0")) > 0
            ]
            avg_return_high = _mean_or_none(high_score_returns)
            improves = (
                avg_return_high > overall_avg_return
                if avg_return_high is not None and overall_avg_return is not None
                else None
            )
        else:
            correlation = None
            avg_return_high = None
            improves = None

        engines.append(
            EngineEffectiveness(
                engine_id=engine_id,
                engine_name=engine_id.replace("_", " ").title(),
                total_evaluations=n,
                avg_score=_quant(avg_score),
                avg_rules_passed=_quant(avg_passed),
                avg_rules_failed=_quant(avg_failed),
                avg_pass_rate=_quant(avg_pass_rate),
                contribution_to_final_score=_quant(avg_contrib),
                correlation_with_outcome=_quant_or_none(correlation),
                improves_performance=improves,
                avg_forward_return_when_engine_scores_high=_quant_or_none(avg_return_high),
            )
        )

    # Best/worst are return-based verdicts, so they exist only when measured.
    ranked = sorted(
        (e for e in engines if e.avg_forward_return_when_engine_scores_high is not None),
        key=lambda e: -(e.avg_forward_return_when_engine_scores_high or Decimal("0")),
    )
    best_engine = ranked[0].engine_id if ranked else ""
    worst_engine = ranked[-1].engine_id if ranked else ""
    recommended_exclusions = tuple(
        e.engine_id for e in engines if e.improves_performance is False
    )
    engines.sort(key=lambda e: e.engine_id)

    if not measurable:
        summary = (
            "Engine effectiveness is not measurable: no matured forward returns "
            "exist for these runs. Scores and pass rates are shown; "
            "return-based verdicts are withheld."
        )
    else:
        summary_parts = []
        if best_engine:
            summary_parts.append(
                f"Best performing engine: {best_engine} (avg forward return when "
                f"it scores above zero: "
                f"{ranked[0].avg_forward_return_when_engine_scores_high})."
            )
        if recommended_exclusions:
            summary_parts.append(
                f"Recommended exclusions: {', '.join(recommended_exclusions)} "
                f"(these engines do not measurably improve performance)."
            )
        summary = (
            " ".join(summary_parts)
            if summary_parts
            else "All engines contribute positively."
        )

    return EngineEffectivenessReport(
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        total_runs_analyzed=run_count,
        engines=tuple(engines),
        best_engine=best_engine,
        worst_engine=worst_engine,
        recommended_exclusions=recommended_exclusions,
        summary=summary,
        measurability=measurability,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 6 — Parameter Research
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_parameter_experiment(
    experiment_name: str,
    base_strategy_name: str,
    base_results: list[dict[str, Any]],
    variant_results: list[dict[str, Any]],
    variant_name: str,
    overrides: tuple[dict[str, Any], ...],
) -> ParameterExperimentReport:
    """Analyze the results of a parameter experiment.

    Args:
        experiment_name: Name of the experiment.
        base_strategy_name: Name of the base strategy.
        base_results: List of result dicts for the base configuration.
        variant_results: List of result dicts for the variant configuration.
        variant_name: Name of this variant.
        overrides: The parameter overrides applied.

    Returns:
        A ParameterExperimentReport comparing base vs variant.
    """
    # Compute base result
    base_momentum = [r.get("avg_momentum_score", Decimal("0")) for r in base_results]
    base_buy = [r.get("avg_buy_setup_score", Decimal("0")) for r in base_results]
    base_pass_rates = []
    for r in base_results:
        total = r.get("total_evaluated", 0)
        passed = r.get("total_passed", 0)
        if total > 0:
            base_pass_rates.append(Decimal(str(passed)) / Decimal(str(total)))

    base_result = ParameterExperimentResult(
        variant_name="base",
        overrides=(),
        run_count=len(base_results),
        avg_momentum_score=_safe_div(sum(base_momentum, Decimal("0")), Decimal(str(len(base_momentum)))) if base_momentum else Decimal("0"),
        avg_buy_setup_score=_safe_div(sum(base_buy, Decimal("0")), Decimal(str(len(base_buy)))) if base_buy else Decimal("0"),
        avg_pass_rate=_safe_div(sum(base_pass_rates, Decimal("0")), Decimal(str(len(base_pass_rates)))) if base_pass_rates else Decimal("0"),
    )

    # Compute variant result
    var_momentum = [r.get("avg_momentum_score", Decimal("0")) for r in variant_results]
    var_buy = [r.get("avg_buy_setup_score", Decimal("0")) for r in variant_results]
    var_pass_rates = []
    for r in variant_results:
        total = r.get("total_evaluated", 0)
        passed = r.get("total_passed", 0)
        if total > 0:
            var_pass_rates.append(Decimal(str(passed)) / Decimal(str(total)))

    var_result = ParameterExperimentResult(
        variant_name=variant_name,
        overrides=overrides,
        run_count=len(variant_results),
        avg_momentum_score=_safe_div(sum(var_momentum, Decimal("0")), Decimal(str(len(var_momentum)))) if var_momentum else Decimal("0"),
        avg_buy_setup_score=_safe_div(sum(var_buy, Decimal("0")), Decimal(str(len(var_buy)))) if var_buy else Decimal("0"),
        avg_pass_rate=_safe_div(sum(var_pass_rates, Decimal("0")), Decimal(str(len(var_pass_rates)))) if var_pass_rates else Decimal("0"),
    )

    # Determine best variant
    improvement = var_result.avg_momentum_score - base_result.avg_momentum_score
    best_variant = variant_name if improvement > 0 else None
    best_improvement = improvement if improvement > 0 else Decimal("0")

    # Parameter sensitivity (simplified)
    sensitivity: dict[str, Any] = {}
    for override in overrides:
        param_path = override.get("parameter_path", "")
        sensitivity[param_path] = {
            "old_value": override.get("old_value"),
            "new_value": override.get("new_value"),
            "impact": _quant(improvement),
        }

    summary = (
        f"Variant '{variant_name}' shows {'improvement' if improvement > 0 else 'degradation'} "
        f"of {_quant(abs(improvement))} in average momentum score "
        f"({'+' if improvement > 0 else ''}{_quant(improvement)})."
    )

    return ParameterExperimentReport(
        experiment_name=experiment_name,
        base_strategy_name=base_strategy_name,
        base_result=base_result,
        variants=(var_result,),
        best_variant=best_variant,
        best_improvement=_quant(best_improvement),
        parameter_sensitivity=sensitivity,
        summary=summary,
    )