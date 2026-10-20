"""Forward-return feature computation (Objective 4, Research Feature Store).

Computes a security's realized forward return, max drawdown, and volatility
over a fixed horizon of NSE sessions following its rank date
(IMPLEMENTATION_SPEC §10, "Research forward returns", R3-B-32). Pure and
I/O-free: callers supply the bars and the sessions; this module only does
arithmetic (ADR-009 determinism contract). A run's forward return is not
knowable at run time -- it can only be computed once market data reaches the
exit session, so this is always invoked from a separate backfill step, never
inline with scoring/ranking.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import pstdev

# ``sessions``: h NSE sessions after the run date. ``own_bars``: h of the
# security's own bars, the rule before engine v2. Stored rows keep their basis
# and no reader mixes the two.
HORIZON_BASIS = "sessions"
LEGACY_HORIZON_BASIS = "own_bars"


@dataclass(frozen=True, slots=True)
class ForwardReturn:
    """A security's realized forward performance over one horizon, from one run.

    ``forward_mfe``/``forward_mae`` are entry-anchored (the best/worst point
    reached relative to the entry price at any time during the window) --
    distinct from ``forward_max_drawdown``, which is peak-to-trough against a
    rolling peak. ``benchmark_return``/``excess_return`` are ``None`` when no
    benchmark close is available for the entry or exit date (never a guessed
    value). ``exit_stale_sessions`` counts the sessions between the exit bar
    and the exit session (0 = a bar on it); ``None`` on legacy rows.
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
    horizon_basis: str = HORIZON_BASIS
    exit_date: date | None = None
    exit_stale_sessions: int | None = None


def compute_forward_return(
    security_id: int,
    horizon_days: int,
    entry_close: Decimal,
    forward_bars: Sequence[tuple[date, Decimal]],
    sessions: Sequence[date],
    benchmark_entry_close: Decimal | None = None,
    benchmark_exit_close: Decimal | None = None,
) -> ForwardReturn | None:
    """Compute one horizon's forward metrics, ``horizon_days`` NSE sessions long.

    ``sessions`` are the NSE sessions after the run date that market data has
    reached, ascending. ``forward_bars`` are the security's ``(date, adjusted
    close)`` bars after the run date, ascending. The exit session E is the
    h-th session; the exit price is the close of the last bar on or before E,
    or the entry close when there is none. A security that stopped trading
    keeps its row: ``exit_stale_sessions`` says how stale its exit is. Path
    metrics use the bars dated on or before E.

    Returns ``None`` if fewer than ``horizon_days`` sessions have elapsed or
    ``entry_close`` is not positive -- a partial window is never extrapolated.
    ``benchmark_exit_close`` is the benchmark's close on or before E.
    """
    if entry_close <= 0 or len(sessions) < horizon_days:
        return None

    window_sessions = sessions[:horizon_days]
    exit_session = window_sessions[-1]
    window = [(day, close) for day, close in forward_bars if day <= exit_session]
    if window:
        stale = horizon_days - bisect_right(window_sessions, window[-1][0])
        horizon_close = window[-1][1]
    else:
        stale, horizon_close = horizon_days, entry_close
    closes = [close for _, close in window]
    forward_return = (horizon_close / entry_close) - 1

    path = [entry_close, *closes]
    peak = path[0]
    max_drawdown = Decimal("0")
    for price in path[1:]:
        peak = max(peak, price)
        if peak > 0:
            drawdown = (price - peak) / peak
            max_drawdown = min(max_drawdown, drawdown)

    excursions = [(price - entry_close) / entry_close for price in closes]
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
        horizon_basis=HORIZON_BASIS,
        exit_date=exit_session,
        exit_stale_sessions=stale,
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
