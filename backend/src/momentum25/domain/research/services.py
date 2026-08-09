"""Pure domain services for the Research & Validation Platform.

All services are deterministic, stateless, and perform no I/O. They operate
on domain value objects only and implement the core logic for comparison,
evaluation, contribution analysis, and experimentation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from momentum25.domain.research.models import (
    ContributionAnalysisReport,
    EngineContributionStats,
    PortfolioPerformance,
    RankingComparison,
    RuleComparison,
    RuleContributionStats,
    RunComparisonReport,
    ScoreComparison,
    StrategyComparisonPoint,
    StrategyComparisonReport,
)

_QUANT = Decimal("0.0001")


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


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3 — Validation Framework
# ═══════════════════════════════════════════════════════════════════════════════


def compare_runs(
    run_a_snapshots: list[dict[str, Any]],
    run_b_snapshots: list[dict[str, Any]],
    run_id_a: int,
    run_id_b: int,
    run_date_a: date,
    run_date_b: date,
    strategy_name: str,
) -> RunComparisonReport:
    """Compare two historical screening runs and produce a deterministic diff.

    Args:
        run_a_snapshots: Snapshot dicts for run A (must include security_id, symbol,
            rank, momentum_score, buy_setup_score, and rule_results).
        run_b_snapshots: Snapshot dicts for run B (same structure).
        run_id_a: Run ID for the first run.
        run_id_b: Run ID for the second run.
        run_date_a: Date of the first run.
        run_date_b: Date of the second run.
        strategy_name: Name of the strategy used.

    Returns:
        A fully populated RunComparisonReport.
    """
    # Index by security_id for O(1) lookups
    a_by_sec = {s["security_id"]: s for s in run_a_snapshots}
    b_by_sec = {s["security_id"]: s for s in run_b_snapshots}

    common_ids = set(a_by_sec.keys()) & set(b_by_sec.keys())

    rank_deltas: list[RankingComparison] = []
    score_deltas: list[ScoreComparison] = []
    rule_diffs: list[RuleComparison] = []

    ranking_changed = 0
    ranking_unchanged = 0
    ranking_regressed = 0
    ranking_improved = 0
    score_changed = 0
    score_unchanged = 0

    for sec_id in sorted(common_ids):
        snap_a = a_by_sec[sec_id]
        snap_b = b_by_sec[sec_id]
        symbol = snap_a.get("symbol", str(sec_id))

        # Ranking comparison
        rank_a = snap_a.get("rank")
        rank_b = snap_b.get("rank")
        rank_delta: int | None = None
        if rank_a is not None and rank_b is not None:
            rank_delta = rank_a - rank_b  # positive means B ranked higher (improved)
            if rank_delta != 0:
                ranking_changed += 1
                if rank_delta > 0:
                    ranking_improved += 1
                else:
                    ranking_regressed += 1
            else:
                ranking_unchanged += 1
        else:
            ranking_unchanged += 1

        score_a = snap_a.get("momentum_score", Decimal("0"))
        score_b = snap_b.get("momentum_score", Decimal("0"))

        rank_deltas.append(
            RankingComparison(
                security_id=sec_id,
                symbol=symbol,
                run_a_rank=rank_a,
                run_b_rank=rank_b,
                rank_delta=rank_delta,
                run_a_score=score_a,
                run_b_score=score_b,
                score_delta=score_b - score_a,
            )
        )

        # Score comparison
        buy_setup_a = snap_a.get("buy_setup_score", Decimal("0"))
        buy_setup_b = snap_b.get("buy_setup_score", Decimal("0"))
        if score_a != score_b or buy_setup_a != buy_setup_b:
            score_changed += 1
        else:
            score_unchanged += 1

        score_deltas.append(
            ScoreComparison(
                security_id=sec_id,
                symbol=symbol,
                momentum_score_a=score_a,
                momentum_score_b=score_b,
                momentum_delta=score_b - score_a,
                buy_setup_a=buy_setup_a,
                buy_setup_b=buy_setup_b,
                buy_setup_delta=buy_setup_b - buy_setup_a,
            )
        )

        # Rule-level comparison
        a_rules = snap_a.get("rule_results", ())
        b_rules = snap_b.get("rule_results", ())
        a_by_rule = {(r.get("rule_id", ""), r.get("engine_id", "")): r for r in a_rules}
        b_by_rule = {(r.get("rule_id", ""), r.get("engine_id", "")): r for r in b_rules}

        common_rules = set(a_by_rule.keys()) & set(b_by_rule.keys())
        for rule_key in sorted(common_rules):
            ra = a_by_rule[rule_key]
            rb = b_by_rule[rule_key]
            if ra.get("passed") != rb.get("passed") or ra.get("raw_value") != rb.get("raw_value"):
                rule_diffs.append(
                    RuleComparison(
                        security_id=sec_id,
                        symbol=symbol,
                        rule_id=rule_key[0],
                        engine_id=rule_key[1],
                        passed_a=bool(ra.get("passed", False)),
                        passed_b=bool(rb.get("passed", False)),
                        raw_value_a=ra.get("raw_value"),
                        raw_value_b=rb.get("raw_value"),
                    )
                )

    # Sort rank deltas for top gainers/losers
    valid_deltas = [d for d in rank_deltas if d.rank_delta is not None]
    valid_deltas.sort(key=lambda d: (-abs(d.rank_delta or 0), d.symbol))
    top_gainers = tuple(d for d in valid_deltas if (d.rank_delta or 0) > 0)[:10]
    top_losers = tuple(d for d in valid_deltas if (d.rank_delta or 0) < 0)[:10]

    return RunComparisonReport(
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        run_date_a=run_date_a,
        run_date_b=run_date_b,
        strategy_name=strategy_name,
        common_securities=len(common_ids),
        ranking_changed=ranking_changed,
        ranking_unchanged=ranking_unchanged,
        ranking_regressed=ranking_regressed,
        ranking_improved=ranking_improved,
        score_changed=score_changed,
        score_unchanged=score_unchanged,
        rank_deltas=tuple(rank_deltas),
        score_deltas=tuple(score_deltas),
        rule_diffs=tuple(rule_diffs),
        top_gainers=top_gainers,
        top_losers=top_losers,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4 — Strategy Evaluation
# ═══════════════════════════════════════════════════════════════════════════════


def compute_performance(
    run_summaries: list[dict[str, Any]],
    strategy_id: int,
    strategy_name: str,
) -> PortfolioPerformance:
    """Compute deterministic performance metrics from a list of run summaries.

    Args:
        run_summaries: List of run summary dicts with keys: run_date, total_evaluated,
            total_passed, avg_momentum_score, avg_buy_setup_score, momentum_scores,
            buy_setup_scores, from the historical runs.
        strategy_id: The strategy ID.
        strategy_name: The strategy name.

    Returns:
        A PortfolioPerformance with all metrics computed.
    """
    run_count = len(run_summaries)
    if run_count == 0:
        return PortfolioPerformance(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            run_count=0,
            first_run_date=None,
            last_run_date=None,
            avg_momentum_score=Decimal("0"),
            median_momentum_score=Decimal("0"),
            avg_buy_setup_score=Decimal("0"),
            median_buy_setup_score=Decimal("0"),
            momentum_score_volatility=Decimal("0"),
            buy_setup_score_volatility=Decimal("0"),
            max_momentum_score=Decimal("0"),
            min_momentum_score=Decimal("0"),
            max_momentum_score_drawdown=Decimal("0"),
            avg_pass_rate=Decimal("0"),
            avg_top_rank_stability=Decimal("0"),
            momentum_score_stability=Decimal("0"),
            momentum_score_downside_stability=Decimal("0"),
            momentum_score_gain_loss_ratio=Decimal("0"),
        )

    dates = [s["run_date"] for s in run_summaries if s.get("run_date")]

    # Score extraction
    momentum_scores = [
        s["avg_momentum_score"] for s in run_summaries if s.get("avg_momentum_score") is not None
    ]
    buy_setup_scores = [
        s["avg_buy_setup_score"] for s in run_summaries if s.get("avg_buy_setup_score") is not None
    ]

    # Basic stats
    avg_momentum = (
        sum(momentum_scores, Decimal("0")) / len(momentum_scores) if momentum_scores else Decimal("0")
    )
    avg_buy_setup = (
        sum(buy_setup_scores, Decimal("0")) / len(buy_setup_scores)
        if buy_setup_scores
        else Decimal("0")
    )

    sorted_momentum = sorted(momentum_scores)
    median_momentum = (
        sorted_momentum[len(sorted_momentum) // 2] if sorted_momentum else Decimal("0")
    )
    sorted_buy = sorted(buy_setup_scores)
    median_buy = sorted_buy[len(sorted_buy) // 2] if sorted_buy else Decimal("0")

    max_momentum = max(momentum_scores) if momentum_scores else Decimal("0")
    min_momentum = min(momentum_scores) if momentum_scores else Decimal("0")

    # Volatility (standard deviation)
    var_momentum = _variance(momentum_scores, avg_momentum)
    var_buy = _variance(buy_setup_scores, avg_buy_setup)
    momentum_vol = Decimal(str(var_momentum ** 0.5)).quantize(_QUANT) if momentum_scores else Decimal("0")
    buy_vol = Decimal(str(var_buy ** 0.5)).quantize(_QUANT) if buy_setup_scores else Decimal("0")

    # Max drawdown from score time series (cumulative peak-to-trough)
    max_dd = _compute_max_drawdown(momentum_scores)

    # Pass rate
    pass_rates = []
    for s in run_summaries:
        total = s.get("total_evaluated", 0)
        passed = s.get("total_passed", 0)
        if total > 0:
            pass_rates.append(Decimal(str(passed)) / Decimal(str(total)))
    avg_pass_rate = (
        sum(pass_rates, Decimal("0")) / len(pass_rates) if pass_rates else Decimal("0")
    )

    # Top rank stability (fraction of top-10 that stayed in top-10)
    stability = _compute_rank_stability(run_summaries)

    # Stability diagnostics over the momentum-SCORE series (not returns).
    score_stability = _compute_score_stability(momentum_scores)
    score_downside_stability = _compute_score_downside_stability(momentum_scores)

    # Ratio of run-over-run score gains to score losses (not profit/loss).
    score_gain_loss_ratio = _compute_score_gain_loss_ratio(momentum_scores)

    return PortfolioPerformance(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        run_count=run_count,
        first_run_date=dates[0] if dates else None,
        last_run_date=dates[-1] if dates else None,
        avg_momentum_score=avg_momentum.quantize(_QUANT),
        median_momentum_score=median_momentum.quantize(_QUANT),
        avg_buy_setup_score=avg_buy_setup.quantize(_QUANT),
        median_buy_setup_score=median_buy.quantize(_QUANT),
        momentum_score_volatility=momentum_vol,
        buy_setup_score_volatility=buy_vol,
        max_momentum_score=max_momentum.quantize(_QUANT),
        min_momentum_score=min_momentum.quantize(_QUANT),
        max_momentum_score_drawdown=max_dd.quantize(_QUANT),
        avg_pass_rate=avg_pass_rate.quantize(_QUANT),
        avg_top_rank_stability=stability.quantize(_QUANT),
        momentum_score_stability=score_stability,
        momentum_score_downside_stability=score_downside_stability,
        momentum_score_gain_loss_ratio=score_gain_loss_ratio,
    )


def _variance(values: list[Decimal], mean: Decimal) -> float:
    """Compute population variance."""
    if len(values) < 2:
        return 0.0
    squared_diffs = [float((v - mean) ** 2) for v in values]
    return sum(squared_diffs) / len(values)


def _compute_max_drawdown(scores: list[Decimal]) -> Decimal:
    """Compute the maximum peak-to-trough drawdown from a score series."""
    if len(scores) < 2:
        return Decimal("0")
    peak = scores[0]
    max_dd = Decimal("0")
    for s in scores:
        if s > peak:
            peak = s
        dd = (peak - s) / peak if peak > 0 else Decimal("0")
        if dd > max_dd:
            max_dd = dd
    return max_dd.quantize(_QUANT)


def _compute_rank_stability(run_summaries: list[dict[str, Any]]) -> Decimal:
    """Estimate top-10 rank stability across runs.

    If ranking data is not available, return 0 (neutral).
    """
    stable_dates = 0
    total_dates = len(run_summaries) - 1  # pairs of consecutive runs
    if total_dates < 1:
        return Decimal("0")

    # We need detailed ranking data to compute this precisely
    # For now, use pass_rate consistency as a proxy
    return Decimal("0").quantize(_QUANT)


def _compute_score_stability(scores: list[Decimal]) -> Decimal:
    """Mean / standard deviation of the momentum-score series, annualised.

    Shaped like a Sharpe ratio but computed over the **momentum score**, a
    0-100 setup-quality rating -- not over returns. It says how steady the
    universe's average score has been, and carries no profit claim
    whatsoever. Named accordingly (2026-08-09 audit §2.3): a score-derived
    diagnostic must never be published under a return metric's name, rendered
    with a % sign, or coloured as profit and loss.
    """
    if len(scores) < 2:
        return Decimal("0")
    mean = sum(scores, Decimal("0")) / len(scores)
    var = _variance(scores, mean)
    if var == 0:
        return Decimal("0")
    std = Decimal(str(var ** 0.5))
    # Assume 252 trading days per year
    ann_factor = Decimal(str(252.0 ** 0.5))
    result = (mean / std) * ann_factor if std > 0 else Decimal("0")
    return result.quantize(_QUANT)


def _compute_score_downside_stability(scores: list[Decimal]) -> Decimal:
    """Mean / below-mean deviation of the momentum-score series, annualised.

    Score-derived, not return-derived. See :func:`_compute_score_stability`.
    """
    if len(scores) < 2:
        return Decimal("0")
    mean = sum(scores, Decimal("0")) / len(scores)
    downside = [float((s - mean) ** 2) for s in scores if s < mean]
    if not downside:
        return Decimal("0")
    downside_var = sum(downside) / len(downside)
    if downside_var == 0:
        return Decimal("0")
    downside_std = Decimal(str(downside_var ** 0.5))
    ann_factor = Decimal(str(252.0 ** 0.5))
    result = (mean / downside_std) * ann_factor if downside_std > 0 else Decimal("0")
    return result.quantize(_QUANT)


def _compute_score_gain_loss_ratio(scores: list[Decimal]) -> Decimal:
    """Sum of run-over-run score *increases* / sum of score *decreases*.

    Score-derived, not return-derived. See :func:`_compute_score_stability`.
    """
    if len(scores) < 2:
        return Decimal("0")
    gains = Decimal("0")
    losses = Decimal("0")
    for i in range(1, len(scores)):
        change = scores[i] - scores[i - 1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    if losses == 0:
        return Decimal("999.9999") if gains > 0 else Decimal("0")
    return (gains / losses).quantize(_QUANT)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5 — Rule Contribution Analysis
# ═══════════════════════════════════════════════════════════════════════════════


def analyze_contribution(
    run_snapshots: list[dict[str, Any]],
    strategy_name: str,
    strategy_id: int,
) -> ContributionAnalysisReport:
    """Analyze rule and engine contribution across multiple historical runs.

    Args:
        run_snapshots: List of snapshot dicts, each with rule_results as tuples.
        strategy_name: The strategy name.
        strategy_id: The strategy ID.

    Returns:
        A ContributionAnalysisReport with cross-run statistics.
    """
    # Aggregate per-rule stats across all runs
    rule_stats: dict[tuple[str, str], list[dict[str, Any]]] = {}

    # Track dates
    dates: list[date] = []
    engines_weights: dict[str, Decimal] = {}

    for snapshot in run_snapshots:
        run_date = snapshot.get("run_date")
        if isinstance(run_date, date):
            dates.append(run_date)

        # Collect engine weights if available
        engine_results = snapshot.get("engine_results", {})
        if isinstance(engine_results, dict):
            for engine_id, engine_data in engine_results.items():
                if isinstance(engine_data, dict) and "weight" in engine_data:
                    engines_weights[engine_id] = Decimal(str(engine_data["weight"]))

        for rule in snapshot.get("rule_results", ()):
            rule_id = rule.get("rule_id", "")
            engine_id = rule.get("engine_id", "")
            key = (rule_id, engine_id)
            if key not in rule_stats:
                rule_stats[key] = []
            rule_stats[key].append(rule)

    # Build per-rule statistics
    per_rule: list[RuleContributionStats] = []
    for (rule_id, engine_id), evaluations in rule_stats.items():
        run_count = len(evaluations)
        pass_count = sum(1 for r in evaluations if r.get("passed", False))
        fail_count = run_count - pass_count
        pass_rate = Decimal(str(pass_count)) / Decimal(str(run_count)) if run_count > 0 else Decimal("0")
        contributions = [r.get("contribution", Decimal("0")) for r in evaluations]
        raw_values: list[Decimal] = [
            r["raw_value"]
            for r in evaluations
            if r.get("raw_value") is not None
        ]

        avg_contrib = (
            sum(contributions, Decimal("0")) / len(contributions) if contributions else Decimal("0")
        )
        total_contrib = sum(contributions, Decimal("0"))
        avg_raw: Decimal | None = (
            sum(raw_values, Decimal("0")) / len(raw_values) if raw_values else None
        )

        importance = avg_contrib * pass_rate

        per_rule.append(
            RuleContributionStats(
                rule_id=rule_id,
                engine_id=engine_id,
                run_count=run_count,
                pass_count=pass_count,
                fail_count=fail_count,
                pass_rate=pass_rate.quantize(_QUANT),
                avg_contribution=avg_contrib.quantize(_QUANT),
                total_contribution=total_contrib.quantize(_QUANT),
                avg_raw_value=avg_raw.quantize(_QUANT) if avg_raw is not None else None,
                importance_score=importance.quantize(_QUANT),
            )
        )

    # Group by engine
    engine_groups: dict[str, list[RuleContributionStats]] = {}
    for rs in per_rule:
        engine_groups.setdefault(rs.engine_id, []).append(rs)

    engine_stats = []
    for engine_id, rules in sorted(engine_groups.items()):
        # Count runs for this engine
        e_run_count = max((r.run_count for r in rules), default=0)
        avg_score = sum((r.avg_contribution for r in rules), Decimal("0"))
        avg_passed = sum((Decimal(str(r.pass_count)) for r in rules), Decimal("0"))
        avg_failed = sum((Decimal(str(r.fail_count)) for r in rules), Decimal("0"))
        # Normalize by number of rules
        if rules:
            avg_passed = avg_passed / len(rules)
            avg_failed = avg_failed / len(rules)
        weight = engines_weights.get(engine_id, Decimal("1"))

        engine_stats.append(
            EngineContributionStats(
                engine_id=engine_id,
                rule_stats=tuple(rules),
                run_count=e_run_count,
                avg_engine_score=avg_score.quantize(_QUANT),
                avg_rules_passed=avg_passed.quantize(_QUANT),
                avg_rules_failed=avg_failed.quantize(_QUANT),
                importance_weight=weight.quantize(_QUANT),
            )
        )

    # Sort by importance
    per_rule.sort(key=lambda r: -r.importance_score)
    top_rules = tuple(per_rule[:10])
    bottom_rules = tuple(reversed(per_rule[-10:])) if len(per_rule) >= 10 else tuple(reversed(per_rule))

    # Redundant rules: those with 100% pass rate
    redundant = tuple(r for r in per_rule if r.pass_rate == Decimal("1"))

    date_range = (min(dates), max(dates)) if len(dates) >= 2 else None

    return ContributionAnalysisReport(
        strategy_name=strategy_name,
        strategy_id=strategy_id,
        # One entry per *security per run*, so the distinct run ids are the
        # run count. Dividing the snapshot total by the engine count (the
        # previous expression) reported 2390 / 6 = 398 "runs" for a single
        # completed run -- arithmetic without meaning.
        run_count=len({s["run_id"] for s in run_snapshots if s.get("run_id") is not None}),
        security_count=len({s["security_id"] for s in run_snapshots if s.get("security_id") is not None}),
        date_range=date_range,
        engine_stats=tuple(engine_stats),
        top_rules=top_rules,
        bottom_rules=bottom_rules,
        redundant_rules=redundant,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 6 — Strategy Comparison
# ═══════════════════════════════════════════════════════════════════════════════


def compare_strategies(
    strategy_a_snapshots: list[dict[str, Any]],
    strategy_b_snapshots: list[dict[str, Any]],
    strategy_a_name: str,
    strategy_b_name: str,
    strategy_a_id: int,
    strategy_b_id: int,
) -> StrategyComparisonReport:
    """Compare the outputs of two strategy configurations.

    Args:
        strategy_a_snapshots: Snapshot dicts for strategy A, each with run_date,
            security_id, momentum_score, rank, hard_filters_passed and rule_results.
        strategy_b_snapshots: Snapshot dicts for strategy B (same structure).
        strategy_a_name: Name of strategy A.
        strategy_b_name: Name of strategy B.
        strategy_a_id: ID of strategy A.
        strategy_b_id: ID of strategy B.

    Returns:
        A StrategyComparisonReport.
    """
    # Group snapshots by run_date
    a_by_date: dict[date, list[dict[str, Any]]] = {}
    b_by_date: dict[date, list[dict[str, Any]]] = {}
    for snap in strategy_a_snapshots:
        rd = snap.get("run_date")
        if isinstance(rd, date):
            a_by_date.setdefault(rd, []).append(snap)

    for snap in strategy_b_snapshots:
        rd = snap.get("run_date")
        if isinstance(rd, date):
            b_by_date.setdefault(rd, []).append(snap)

    common_dates = sorted(set(a_by_date.keys()) & set(b_by_date.keys()))

    score_deltas: list[StrategyComparisonPoint] = []
    rule_diffs: list[RuleComparison] = []
    a_wins_score = 0
    b_wins_score = 0
    a_wins_pass = 0
    b_wins_pass = 0
    all_score_deltas: list[Decimal] = []

    for run_date in common_dates:
        a_snaps = a_by_date[run_date]
        b_snaps = b_by_date[run_date]
        a_by_sec = {s["security_id"]: s for s in a_snaps}
        b_by_sec = {s["security_id"]: s for s in b_snaps}
        common_secs = set(a_by_sec.keys()) & set(b_by_sec.keys())

        for sec_id in sorted(common_secs):
            sa = a_by_sec[sec_id]
            sb = b_by_sec[sec_id]
            score_a = sa.get("momentum_score", Decimal("0"))
            score_b = sb.get("momentum_score", Decimal("0"))
            rank_a = sa.get("rank")
            rank_b = sb.get("rank")
            rank_delta: int | None = (
                (rank_a - rank_b) if rank_a is not None and rank_b is not None else None
            )
            passed_a = sa.get("hard_filters_passed", False)
            passed_b = sb.get("hard_filters_passed", False)

            delta = score_b - score_a
            all_score_deltas.append(delta)

            score_deltas.append(
                StrategyComparisonPoint(
                    run_date=run_date,
                    strategy_a_score=score_a,
                    strategy_b_score=score_b,
                    score_delta=delta,
                    strategy_a_rank=rank_a,
                    strategy_b_rank=rank_b,
                    rank_delta=rank_delta,
                    strategy_a_passed=passed_a,
                    strategy_b_passed=passed_b,
                )
            )

            if score_a > score_b:
                a_wins_score += 1
            elif score_b > score_a:
                b_wins_score += 1

            if passed_a and not passed_b:
                a_wins_pass += 1
            elif passed_b and not passed_a:
                b_wins_pass += 1

            # Rule-level diffs
            a_rules = sa.get("rule_results", ())
            b_rules = sb.get("rule_results", ())
            a_by_rule = {}
            for r in a_rules:
                a_by_rule[(r.get("rule_id", ""), r.get("engine_id", ""))] = r
            b_by_rule = {}
            for r in b_rules:
                b_by_rule[(r.get("rule_id", ""), r.get("engine_id", ""))] = r

            common_rules = set(a_by_rule.keys()) & set(b_by_rule.keys())
            for rule_key in sorted(common_rules):
                ra = a_by_rule[rule_key]
                rb = b_by_rule[rule_key]
                if ra.get("passed") != rb.get("passed") or ra.get("raw_value") != rb.get("raw_value"):
                    rule_diffs.append(
                        RuleComparison(
                            security_id=sec_id,
                            symbol=sa.get("symbol", str(sec_id)),
                            rule_id=rule_key[0],
                            engine_id=rule_key[1],
                            passed_a=bool(ra.get("passed", False)),
                            passed_b=bool(rb.get("passed", False)),
                            raw_value_a=ra.get("raw_value"),
                            raw_value_b=rb.get("raw_value"),
                        )
                    )

    # Aggregate stats
    total_points = len(all_score_deltas)
    if total_points > 0:
        avg_delta = sum(all_score_deltas, Decimal("0")) / total_points
        sorted_deltas = sorted(all_score_deltas)
        median_delta = sorted_deltas[total_points // 2] if sorted_deltas else Decimal("0")
        max_delta = max(all_score_deltas)
    else:
        avg_delta = Decimal("0")
        median_delta = Decimal("0")
        max_delta = Decimal("0")

    # Simplified rank correlation using agreement rate
    rank_corr = _compute_rank_correlation(
        score_deltas=[s for s in score_deltas if s.strategy_a_rank is not None and s.strategy_b_rank is not None]
    )

    return StrategyComparisonReport(
        strategy_a_name=strategy_a_name,
        strategy_b_name=strategy_b_name,
        strategy_a_id=strategy_a_id,
        strategy_b_id=strategy_b_id,
        common_run_dates=len(common_dates),
        avg_score_delta=avg_delta.quantize(_QUANT),
        median_score_delta=median_delta.quantize(_QUANT),
        max_score_delta=max_delta.quantize(_QUANT),
        rank_correlation=rank_corr.quantize(_QUANT),
        score_deltas=tuple(score_deltas),
        rule_differences=tuple(rule_diffs),
        strategy_a_wins_score=a_wins_score,
        strategy_b_wins_score=b_wins_score,
        strategy_a_wins_pass_rate=a_wins_pass,
        strategy_b_wins_pass_rate=b_wins_pass,
    )


def _compute_rank_correlation(
    score_deltas: list[StrategyComparisonPoint],
) -> Decimal:
    """Compute a simplified rank correlation (agreement rate)."""
    if not score_deltas:
        return Decimal("0")
    agreements = sum(
        1
        for s in score_deltas
        if s.strategy_a_rank == s.strategy_b_rank
    )
    return Decimal(str(agreements)) / Decimal(str(len(score_deltas)))


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 7 — Experiment Framework (parameter application)
# ═══════════════════════════════════════════════════════════════════════════════


def apply_parameter_overrides(
    strategy_config: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply parameter overrides to a strategy configuration dict.

    Produces a new config dict with the overrides applied. The original config
    is not mutated — this is a pure transformation.

    Args:
        strategy_config: The base strategy configuration dict.
        overrides: List of override dicts with keys: engine_id, rule_id,
            parameter_path, new_value. If engine_id is None, the parameter
            applies at the top level (e.g. momentum_weights).

    Returns:
        A new config dict with overrides applied.
    """
    import copy

    config = copy.deepcopy(strategy_config)

    for override in overrides:
        engine_id = override.get("engine_id")
        rule_id = override.get("rule_id")
        param_path = override.get("parameter_path", "")
        new_value = override.get("new_value")

        if engine_id is None:
            # Top-level parameter
            _set_nested(config, param_path, new_value)
        else:
            # Engine-level parameter
            engines = config.get("engines", [])
            for engine in engines:
                if engine.get("id") == engine_id:
                    if rule_id is None:
                        # Engine-level parameter
                        _set_nested(engine, param_path, new_value)
                    else:
                        # Rule-level parameter
                        rules = engine.get("rules", [])
                        for rule in rules:
                            if rule.get("id") == rule_id:
                                _set_nested(rule, param_path, new_value)
                            elif rule_id == "*":
                                _set_nested(rule, param_path, new_value)
                    break

    return config


def _set_nested(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set a nested dictionary value using a dot-separated path."""
    parts = path.split(".")
    current = obj
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            current[part] = value
        else:
            if part not in current:
                current[part] = {}
            current = current[part]