"""Strategy evaluation rules (ADR-014 §5–6): windows, outcomes and their statistics.

Pure and I/O-free. The use case screens each decision session with the real
strategy engine, then hands the ranks and forward returns to these functions.

The method follows the house validation protocol (2026-08-10 ranking report):
one figure per decision session, a Newey-West standard error for the
overlapping forward windows, and a Bonferroni adjustment for the number of
families tested on the same hold-out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import NormalDist, StatisticsError, correlation, fmean
from typing import Literal

ResultClass = Literal["screening", "in_sample", "out_of_sample"]

# The fixed labels every response and screen uses (ADR-014 §5).
LABELS: dict[ResultClass, str] = {
    "screening": "Screening Result",
    "in_sample": "Historical Research — In-Sample",
    "out_of_sample": "Out-of-Sample Evaluation",
}
NOT_EVIDENCE = "Not evidence of future returns."
INSUFFICIENT = "unavailable: insufficient data"
INCOMPLETE_PROVENANCE = "Incomplete historical provenance"


@dataclass(frozen=True, slots=True)
class EvaluationPolicy:
    """The evaluation constants. The system sets them; users cannot.

    - Hold-out windows are 36-month blocks on a grid that starts at
      ``anchor``, so a new window opens only when 36 new months mature.
      2020 is the first year whose universe is broad (1,600+ names) and has a
      full year of history behind it.
    - ``horizon`` is the longest forward return in use, in sessions.
    - A decision with fewer than ``min_qualified`` names has no Rank IC.
    - A metric needs ``min_decisions`` usable decisions, or it is
      unavailable. Below that the normal approximation is not safe.
    - ``plausible_ic`` and ``plausible_excess`` are the smallest effects worth
      finding. A test that cannot detect them at ``power`` is underpowered.
    """

    horizon: int = 120
    # Sessions of history the indicator pipeline needs before a first decision.
    warmup: int = 277
    step: int = 5
    holdout_months: int = 36
    anchor: date = date(2020, 1, 1)
    min_qualified: int = 10
    min_decisions: int = 30
    alpha: float = 0.05
    power: float = 0.80
    plausible_ic: float = 0.03
    plausible_excess: float = 0.02
    max_reconstructed_share: float = 0.5

    @property
    def lag(self) -> int:
        """Newey-West lag: how many later decisions share part of a forward window."""
        return max(0, math.ceil(self.horizon / self.step) - 1)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def exit_session(sessions: list[date], decision: date, horizon: int) -> date | None:
    """The session ``horizon`` sessions after ``decision``, or None if not reached yet."""
    later = [s for s in sessions if s > decision]
    return later[horizon - 1] if len(later) >= horizon else None


def holdout_window(sessions: list[date], policy: EvaluationPolicy) -> tuple[date, date] | None:
    """The latest grid block whose last decision's forward window has matured.

    ``sessions`` run from the first to the last stored session. A block counts
    only if the data covers all of it. Returns its first and last session, or
    None if no block has matured.
    """
    if not sessions:
        return None
    window = None
    k = 0
    while True:
        start = _add_months(policy.anchor, k * policy.holdout_months)
        end = _add_months(start, policy.holdout_months) - timedelta(days=1)
        inside = [s for s in sessions if start <= s <= end]
        if not inside or sessions[0] > start or sessions[-1] <= end:
            break  # the data does not cover the whole block
        if exit_session(sessions, inside[-1], policy.horizon) is None:
            break
        window = (inside[0], inside[-1])
        k += 1
    return window


def research_end(sessions: list[date], holdout_start: date, horizon: int) -> date | None:
    """The last research decision whose forward window closes before the hold-out."""
    before = [s for s in sessions if s < holdout_start]
    return before[-horizon - 1] if len(before) > horizon else None


def research_window(sessions: list[date], policy: EvaluationPolicy) -> tuple[date, date] | None:
    """The in-sample window: from the warm-up to the gap before the hold-out.

    Before any block has matured, the boundary is the first grid block in the
    data, so research never reads a block that will later become a hold-out.
    """
    if len(sessions) <= policy.warmup:
        return None
    holdout = holdout_window(sessions, policy)
    if holdout is not None:
        boundary = holdout[0]
    else:
        k = 0
        while _add_months(policy.anchor, k * policy.holdout_months) < sessions[0]:
            k += 1
        boundary = _add_months(policy.anchor, k * policy.holdout_months)
    start = sessions[policy.warmup]
    end = research_end(sessions, boundary, policy.horizon)
    return (start, end) if end is not None and start <= end else None


def decision_sessions(sessions: list[date], start: date, end: date, step: int) -> list[date]:
    """Every ``step``-th session from ``start`` to ``end``, inclusive."""
    return [s for s in sessions if start <= s <= end][::step]


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    """What one decision session selected and what followed it."""

    decision: date
    qualified: int
    top_n: int
    top_n_excess: float | None
    qualified_excess: float | None
    rank_ic: float | None


def decision_outcome(
    decision: date,
    ranked: list[tuple[int, float]],
    top_n: int,
    min_qualified: int,
) -> DecisionOutcome:
    """Summarise one decision from ``(rank, forward excess return)`` per qualified name.

    Names without a forward return are left out by the caller. Rank IC is the
    Spearman correlation of ``-rank`` with the excess return, so a positive IC
    means better-ranked names did better.
    """
    top = [r for rank, r in ranked if rank <= top_n]
    rank_ic = None
    if len(ranked) >= min_qualified:
        try:
            rank_ic = correlation(
                [-rank for rank, _ in ranked], [r for _, r in ranked], method="ranked"
            )
        except StatisticsError:  # every return equal: no ordering to measure
            rank_ic = None
    return DecisionOutcome(
        decision=decision,
        qualified=len(ranked),
        top_n=len(top),
        top_n_excess=fmean(top) if top else None,
        qualified_excess=fmean(r for _, r in ranked) if ranked else None,
        rank_ic=rank_ic,
    )


def newey_west_se(values: list[float], lag: int) -> float:
    """The standard error of the mean, robust to autocorrelation up to ``lag`` (Bartlett)."""
    n = len(values)
    mean = fmean(values)
    dev = [v - mean for v in values]

    def gamma(j: int) -> float:
        return sum(dev[t] * dev[t - j] for t in range(j, n)) / n

    variance = gamma(0) + 2 * sum(
        (1 - j / (lag + 1)) * gamma(j) for j in range(1, min(lag, n - 1) + 1)
    )
    return math.sqrt(max(variance, 0.0) / n)


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """One metric across decisions: estimate, interval, test and power."""

    n: int
    mean: float
    se: float
    t: float
    p: float
    p_adjusted: float
    ci_low: float
    ci_high: float
    minimum_detectable: float
    plausible: float
    powered: bool


def summarize(
    values: list[float | None],
    policy: EvaluationPolicy,
    plausible: float,
    tests: int = 1,
) -> MetricSummary | None:
    """Summarise a per-decision metric; None when fewer than ``min_decisions`` exist.

    ``tests`` is the Bonferroni factor: the number of families tested on the
    window, this one included. The interval is the unadjusted 95% interval.
    The minimum detectable effect uses the adjusted level and ``policy.power``.
    """
    usable = [v for v in values if v is not None]
    if len(usable) < policy.min_decisions:
        return None
    mean = fmean(usable)
    se = newey_west_se(usable, policy.lag)
    z = NormalDist()
    t = mean / se if se > 0 else 0.0
    p = 2 * (1 - z.cdf(abs(t)))
    half = z.inv_cdf(1 - policy.alpha / 2) * se
    detectable = (z.inv_cdf(1 - policy.alpha / (2 * tests)) + z.inv_cdf(policy.power)) * se
    return MetricSummary(
        n=len(usable),
        mean=mean,
        se=se,
        t=t,
        p=p,
        p_adjusted=min(1.0, p * tests),
        ci_low=mean - half,
        ci_high=mean + half,
        minimum_detectable=detectable,
        plausible=plausible,
        powered=detectable <= plausible,
    )


def power_statement(summary: MetricSummary | None, metric: str, power: float) -> str:
    """One plain sentence on what the sample can detect."""
    if summary is None:
        return f"{metric}: {INSUFFICIENT}."
    if summary.powered:
        return (
            f"{metric}: the sample can detect an effect of {summary.minimum_detectable:.4f} "
            f"or larger at {power:.0%} power."
        )
    return (
        f"{metric}: underpowered. The smallest effect the sample can detect is "
        f"{summary.minimum_detectable:.4f}; a plausible effect is {summary.plausible:.4f}."
    )
