"""Forward-return feature computation (Objective 4, Research Feature Store).

Computes a security's realized forward return, max drawdown, and volatility
over a fixed horizon following its rank date. Pure and I/O-free: callers
supply the already-fetched closing-price path; this module only does
arithmetic (ADR-009 determinism contract). A run's forward return is not
knowable at run time -- it can only be computed once ``horizon_days`` worth
of bars exist after the run date, so this is always invoked from a separate
backfill step, never inline with scoring/ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import pstdev


@dataclass(frozen=True, slots=True)
class ForwardReturn:
    """A security's realized forward performance over one horizon, from one run.

    ``forward_mfe``/``forward_mae`` are entry-anchored (the best/worst point
    reached relative to the entry price at any time during the window) --
    distinct from ``forward_max_drawdown``, which is peak-to-trough against a
    rolling peak. ``benchmark_return``/``excess_return`` are ``None`` when no
    benchmark close is available for the entry or exit date (never a guessed
    value).
    """

    security_id: int
    horizon_days: int
    forward_return: Decimal
    forward_max_drawdown: Decimal
    forward_volatility: Decimal
    forward_mfe: Decimal
    forward_mae: Decimal
    benchmark_return: Decimal | None = None
    excess_return: Decimal | None = None


def compute_forward_return(
    security_id: int,
    horizon_days: int,
    entry_close: Decimal,
    forward_closes: list[Decimal],
    benchmark_entry_close: Decimal | None = None,
    benchmark_exit_close: Decimal | None = None,
) -> ForwardReturn | None:
    """Compute one horizon's forward metrics from a close-price path.

    ``forward_closes`` must be the ascending-by-date closes strictly after
    the entry bar. Returns ``None`` if fewer than ``horizon_days`` bars are
    available (the horizon hasn't elapsed yet) or ``entry_close`` is not
    positive -- callers must not extrapolate a partial window, since a
    forward return computed from an incomplete horizon is not the metric it
    claims to be.

    ``benchmark_entry_close``/``benchmark_exit_close``, if supplied, produce
    ``benchmark_return``/``excess_return``; omitted (both ``None``) when the
    caller has no benchmark close for one of the two dates.
    """
    if entry_close <= 0 or len(forward_closes) < horizon_days:
        return None

    window = forward_closes[:horizon_days]
    horizon_close = window[-1]
    forward_return = (horizon_close / entry_close) - 1

    path = [entry_close, *window]
    peak = path[0]
    max_drawdown = Decimal("0")
    for price in path[1:]:
        peak = max(peak, price)
        if peak > 0:
            drawdown = (price - peak) / peak
            max_drawdown = min(max_drawdown, drawdown)

    excursions = [(price - entry_close) / entry_close for price in window]
    mfe = max(excursions) if excursions else Decimal("0")
    mae = min(excursions) if excursions else Decimal("0")

    daily_returns = [
        float(path[i] / path[i - 1] - 1) for i in range(1, len(path)) if path[i - 1] != 0
    ]
    volatility = Decimal(str(pstdev(daily_returns))) if len(daily_returns) > 1 else Decimal("0")

    benchmark_return = None
    excess_return = None
    if (
        benchmark_entry_close is not None
        and benchmark_exit_close is not None
        and benchmark_entry_close > 0
    ):
        benchmark_return = (benchmark_exit_close / benchmark_entry_close) - 1
        excess_return = forward_return - benchmark_return

    return ForwardReturn(
        security_id=security_id,
        horizon_days=horizon_days,
        forward_return=forward_return,
        forward_max_drawdown=max_drawdown,
        forward_volatility=volatility,
        forward_mfe=mfe,
        forward_mae=mae,
        benchmark_return=benchmark_return,
        excess_return=excess_return,
    )


# Fixed, round-number thresholds (not fit to any specific dataset) for
# Alpha Discovery Program tier classification -- deliberately independent of
# this dataset's own return distribution to avoid classifying "winners" by
# construction (a percentile-based scheme would always find a top 20%).
PERFORMANCE_TIERS: tuple[tuple[str, Decimal], ...] = (
    ("exceptional_winner", Decimal("0.50")),
    ("strong_performer", Decimal("0.20")),
    ("average_performer", Decimal("0")),
    ("underperformer", Decimal("-0.15")),
    ("failure", Decimal("-1")),
)


def classify_performance_tier(forward_return: Decimal) -> str:
    """Classify a forward return into one of 5 fixed performance tiers.

    Boundaries: exceptional_winner >=50%, strong_performer >=20%,
    average_performer >=0%, underperformer >=-15%, else failure. Fixed
    thresholds rather than sample percentiles, so the classification means
    the same thing regardless of which historical window is being analyzed.
    """
    for tier_name, threshold in PERFORMANCE_TIERS:
        if forward_return >= threshold:
            return tier_name
    return "failure"
