"""Historical liquidity-floor eligibility (RP-012 Phase 2 §3).

Pure, I/O-free implementation of the research-specified point-in-time universe
admission rule. A security is admitted to the reconstructed ``historical_universe``
for a given ``as_of`` date iff **all** of:

* ``avg_tottrdval50 >= ₹10,000,000`` — arithmetic mean of the trailing 50
  sessions' **real** ``turnover_value`` (``TOTTRDVAL``), never the production
  estimate of ``avg_volume50 × latest_close``;
* ``close >= ₹20``;
* ``series == 'EQ'``;
* ``>= 252`` prior sessions of history.

The rule is a deterministic function of its inputs (ADR-009): identical inputs
produce an identical decision and an identical, explainable reason string. Any
missing real turnover in the trailing window makes the security ineligible with
a disclosed reason rather than silently substituting a guessed or estimated
turnover — the whole point of Phase 2 is to gate on *real* turnover.

Research owns the calibration of the thresholds themselves; engineering only
implements them exactly and reports the empirical calibration (Gate 4d). The
thresholds are therefore module constants, not tunable configuration, so no
code path can quietly drift them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

# Research-specified thresholds (RP-012 Phase 2 §3). Fixed, not configurable.
MIN_AVG_TURNOVER: Decimal = Decimal("10000000")  # ₹1 crore average daily turnover
MIN_CLOSE: Decimal = Decimal("20")
TURNOVER_WINDOW: int = 50
MIN_PRIOR_SESSIONS: int = 252
EQ_SERIES: str = "EQ"

# Eligibility reason codes (stable identifiers, safe to persist and aggregate).
REASON_ELIGIBLE = "eligible"
REASON_SERIES_NOT_EQ = "series_not_eq"
REASON_INSUFFICIENT_HISTORY = "insufficient_history"
REASON_INSUFFICIENT_TURNOVER_DATA = "insufficient_turnover_data"
REASON_CLOSE_BELOW_FLOOR = "close_below_floor"
REASON_BELOW_LIQUIDITY_FLOOR = "below_liquidity_floor"


@dataclass(frozen=True, slots=True)
class LiquidityDecision:
    """The outcome of the liquidity-floor rule for one (security, date).

    ``avg_tottrdval50`` is populated whenever it could be computed from a full
    window of real turnover values (even if the security is ultimately
    ineligible on another gate), so the calibration report can inspect the
    distribution; it is ``None`` only when the window itself was incomputable.
    """

    eligible: bool
    reason: str
    avg_tottrdval50: Decimal | None


def compute_avg_tottrdval50(
    trailing_turnovers: Sequence[Decimal | None],
    window: int = TURNOVER_WINDOW,
) -> Decimal | None:
    """Return the arithmetic mean of the trailing ``window`` real turnovers.

    ``trailing_turnovers`` is the sequence of ``turnover_value`` for the most
    recent sessions up to and including ``as_of`` (ascending or descending order
    is irrelevant to a mean). Returns ``None`` — never a guessed value — when
    fewer than ``window`` sessions are supplied or any of the last ``window``
    carries no real turnover (``None``): a real average cannot be formed from a
    missing measurement.
    """
    if window <= 0:
        return None
    if len(trailing_turnovers) < window:
        return None
    recent = list(trailing_turnovers)[-window:]
    present = [value for value in recent if value is not None]
    if len(present) < window:
        return None
    total = sum(present, Decimal("0"))
    return total / Decimal(window)


def evaluate_liquidity_eligibility(
    *,
    close: Decimal,
    series: str,
    prior_session_count: int,
    trailing_turnovers: Sequence[Decimal | None],
) -> LiquidityDecision:
    """Evaluate the point-in-time liquidity-floor rule for one security/date.

    Args:
        close: The session's raw close on ``as_of``.
        series: The NSE series code (only ``'EQ'`` is admissible).
        prior_session_count: Number of trading sessions strictly before
            ``as_of`` for which this security has stored bars (the history
            depth requirement is on *prior* sessions, independent of the
            trailing-turnover window).
        trailing_turnovers: The trailing sessions' real ``turnover_value`` up to
            and including ``as_of`` (see :func:`compute_avg_tottrdval50`).

    Returns:
        A :class:`LiquidityDecision`. Every gate is evaluated so the eligibility
        flag is the strict AND of all conditions; ``reason`` reports the first
        failing gate in a fixed, deterministic order for explainability.
    """
    avg = compute_avg_tottrdval50(trailing_turnovers)

    if series.strip().upper() != EQ_SERIES:
        return LiquidityDecision(False, REASON_SERIES_NOT_EQ, avg)
    if prior_session_count < MIN_PRIOR_SESSIONS:
        return LiquidityDecision(False, REASON_INSUFFICIENT_HISTORY, avg)
    if avg is None:
        return LiquidityDecision(False, REASON_INSUFFICIENT_TURNOVER_DATA, None)
    if close < MIN_CLOSE:
        return LiquidityDecision(False, REASON_CLOSE_BELOW_FLOOR, avg)
    if avg < MIN_AVG_TURNOVER:
        return LiquidityDecision(False, REASON_BELOW_LIQUIDITY_FLOOR, avg)
    return LiquidityDecision(True, REASON_ELIGIBLE, avg)
