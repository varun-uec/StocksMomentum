"""Swing entry/stop/target planning (Phase 3.1/3.2).

Pure, I/O-free: given already-computed indicator values (entry price, ATR,
nearest confirmed swing resistance), returns a deterministic stop/target plan
and its risk-reward ratio. Kept separate from both scoring
(``domain.engines.risk``) and backtesting
(``application.use_cases.research.swing_target_backtest``) so the placement
rule itself is independently testable and reusable by both -- neither folded
into the scoring engine nor entangled with I/O.

Replaces the reward leg of the previous ``risk_rr`` rule, which computed
reward as ``max(high, last 20 bars) - close``. Because that maximum always
includes the signal bar itself, any stock making a new 20-day high on the
signal date -- exactly the breakout population this system selects -- had
reward collapse to near zero, failing the rule almost by construction for its
own target population (see ``docs/research/2026-07-02-alpha-discovery-program-report.md``:
13.5% pass rate, -2.30% correlation with forward return). Reward is now the
distance to the nearest *confirmed* swing high above price (Phase 2.3), with
a documented ATR-multiple fallback for the common case where a breakout stock
has no confirmed resistance above it at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from momentum25.domain.engines.risk import (
    DEFAULT_ATR_STOP_MULTIPLE as DEFAULT_ATR_STOP_MULTIPLE,
)
from momentum25.domain.engines.risk import (
    DEFAULT_FALLBACK_RISK_PCT as DEFAULT_FALLBACK_RISK_PCT,
)
from momentum25.domain.entities.market_data import OHLCVBar

# Stop multiple matches the existing risk engine's own convention (``risk.py``:
# stop distance = ``atr14 * 2``, unchanged by this fix). Target multiple is a
# separate, independent, commonly-published swing-trading convention (roughly
# a 1.5:1 payoff before evidence of open room to run) -- deliberately NOT
# derived from the strategy's configured ``min_ratio`` threshold. Tying the
# fallback multiple to the pass/fail threshold would make the no-resistance
# case pass by construction every time ATR is available, which defeats the
# point of a risk-reward *gate*: absent a confirmed pivot showing real room
# above price, the plan should have to earn a pass, not default to one.
DEFAULT_ATR_TARGET_MULTIPLE = Decimal("3")
DEFAULT_MIN_RR_RATIO = Decimal("2.0")  # used only for the no-ATR-at-all fallback below


@dataclass(frozen=True, slots=True)
class SwingTargetPlan:
    """A deterministic entry/stop/target plan and its risk-reward ratio."""

    entry: Decimal
    stop: Decimal
    target: Decimal
    risk_amount: Decimal
    reward_amount: Decimal
    rr_ratio: Decimal
    target_basis: str  # "swing_resistance" | "atr_multiple"


def compute_swing_target_plan(
    entry: Decimal,
    atr14: Decimal | None,
    swing_resistance: Decimal | None,
    *,
    atr_stop_multiple: Decimal = DEFAULT_ATR_STOP_MULTIPLE,
    atr_target_multiple: Decimal = DEFAULT_ATR_TARGET_MULTIPLE,
    fallback_risk_pct: Decimal = DEFAULT_FALLBACK_RISK_PCT,
) -> SwingTargetPlan | None:
    """Compute a stop/target plan for a long entry at ``entry``.

    Risk leg: ``atr14 * atr_stop_multiple`` below entry, falling back to
    ``entry * fallback_risk_pct`` when ATR is unavailable (mirrors the
    existing risk engine's own fallback).

    Reward leg: the distance to ``swing_resistance`` when it is a real,
    confirmed pivot above ``entry``; otherwise ``atr14 * atr_target_multiple``
    (or the risk amount scaled by the min RR ratio, if ATR is also
    unavailable) -- never a value that can collapse to zero purely because
    the stock is at a new high.

    Returns:
        ``None`` if ``entry`` is not positive or the computed risk amount is
        not positive (no valid plan can be formed).
    """
    if entry <= 0:
        return None

    risk_amount = (
        atr14 * atr_stop_multiple
        if atr14 is not None and atr14 > 0
        else entry * fallback_risk_pct
    )
    if risk_amount <= 0:
        return None
    stop = entry - risk_amount

    if swing_resistance is not None and swing_resistance > entry:
        target = swing_resistance
        target_basis = "swing_resistance"
    else:
        target = entry + (
            atr14 * atr_target_multiple
            if atr14 is not None and atr14 > 0
            else risk_amount * DEFAULT_MIN_RR_RATIO
        )
        target_basis = "atr_multiple"

    reward_amount = target - entry
    rr_ratio = reward_amount / risk_amount

    return SwingTargetPlan(
        entry=entry,
        stop=stop,
        target=target,
        risk_amount=risk_amount,
        reward_amount=reward_amount,
        rr_ratio=rr_ratio,
        target_basis=target_basis,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Trade simulation (Phase 3.3) — walks forward bars to see which of target/stop
# is touched first. Pure: the caller fetches and adjusts the bars; this module
# only compares prices already provided.
# ═══════════════════════════════════════════════════════════════════════════════


class TradeOutcome(StrEnum):
    """How a simulated trade ended."""

    TARGET_HIT = "TARGET_HIT"
    STOP_HIT = "STOP_HIT"
    TIME_EXIT = "TIME_EXIT"  # neither touched within the holding window
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # no forward bars available at all


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Outcome of simulating one :class:`SwingTargetPlan` against forward bars."""

    outcome: TradeOutcome
    exit_price: Decimal | None
    days_held: int | None
    r_multiple: Decimal | None  # realized P&L in units of risk_amount
    max_adverse_excursion_r: Decimal | None  # worst intraday drawdown reached, in R


def simulate_trade(
    plan: SwingTargetPlan,
    forward_bars: list[OHLCVBar],
    max_holding_days: int,
) -> TradeResult:
    """Walk ``forward_bars`` day by day to see whether target or stop is touched first.

    ``forward_bars`` must already be in the same price basis as ``plan`` (i.e.
    corporate-action-adjusted the same way the entry/ATR/swing-resistance that
    produced ``plan`` were) and ordered ascending by date, starting the day
    after entry.

    On a day where both ``low <= stop`` and ``high >= target`` are true, the
    stop is assumed to trigger first -- a standard, deliberately conservative
    backtesting convention given only daily OHLC (no intrabar sequencing is
    available to know which was actually touched first).

    Stop fills model gap-through: if the bar's ``open`` is already below
    ``plan.stop`` (the stock gapped down through the stop overnight), the
    fill is the ``open``, not the unreachable stop price -- a stop order
    cannot fill better than the first price it can trade at. This was
    flagged as missing in the Phase 3 report, where the optimistic
    fill-at-exact-stop assumption overstated results (Phase 3b.4).

    A holding-period timeout (neither level touched within
    ``max_holding_days``) exits at the last available close within that
    window, not a guessed future price.
    """
    if not forward_bars:
        return TradeResult(TradeOutcome.INSUFFICIENT_DATA, None, None, None, None)

    window = forward_bars[:max_holding_days]
    worst_r = Decimal("0")

    for i, bar in enumerate(window, start=1):
        excursion_r = (bar.low - plan.entry) / plan.risk_amount
        worst_r = min(worst_r, excursion_r)

        if bar.low <= plan.stop:
            fill = min(plan.stop, bar.open)  # gap-through: can't fill better than the open
            return TradeResult(
                TradeOutcome.STOP_HIT,
                fill,
                i,
                (fill - plan.entry) / plan.risk_amount,
                min(worst_r, (fill - plan.entry) / plan.risk_amount),
            )
        if bar.high >= plan.target:
            return TradeResult(
                TradeOutcome.TARGET_HIT, plan.target, i, plan.rr_ratio, worst_r
            )

    last = window[-1]
    return TradeResult(
        TradeOutcome.TIME_EXIT,
        last.close,
        len(window),
        (last.close - plan.entry) / plan.risk_amount,
        worst_r,
    )


@dataclass(frozen=True, slots=True)
class SwingTargetBacktestReport:
    """Aggregate statistics over a set of simulated trades (Phase 3.3).

    ``hit_rate`` covers only trades with a clean, unambiguous outcome
    (target or stop actually touched) -- ``time_exits`` are reported
    separately rather than folded into either side of a win/loss ratio,
    since "never reached either level within the holding window" is not the
    same claim as "lost". ``avg_r_multiple`` is computed over every decided
    trade (target/stop/time-exit), which is what a realistic expectancy
    figure needs to include.
    """

    total_trades: int
    target_hits: int
    stop_hits: int
    time_exits: int
    insufficient_data: int
    hit_rate: Decimal | None
    avg_r_multiple: Decimal | None
    avg_max_adverse_excursion_r: Decimal | None
    worst_max_adverse_excursion_r: Decimal | None


def aggregate_trade_results(results: list[TradeResult]) -> SwingTargetBacktestReport:
    """Compute hit-rate/avg-R/MAE statistics over a list of simulated trades."""
    target_hits = sum(1 for r in results if r.outcome == TradeOutcome.TARGET_HIT)
    stop_hits = sum(1 for r in results if r.outcome == TradeOutcome.STOP_HIT)
    time_exits = sum(1 for r in results if r.outcome == TradeOutcome.TIME_EXIT)
    insufficient = sum(1 for r in results if r.outcome == TradeOutcome.INSUFFICIENT_DATA)

    decided_count = target_hits + stop_hits
    hit_rate = (
        Decimal(target_hits) / Decimal(decided_count) if decided_count > 0 else None
    )

    r_values = [r.r_multiple for r in results if r.r_multiple is not None]
    avg_r = sum(r_values, Decimal("0")) / len(r_values) if r_values else None

    mae_values = [
        r.max_adverse_excursion_r for r in results if r.max_adverse_excursion_r is not None
    ]
    avg_mae = sum(mae_values, Decimal("0")) / len(mae_values) if mae_values else None
    worst_mae = min(mae_values) if mae_values else None

    return SwingTargetBacktestReport(
        total_trades=len(results),
        target_hits=target_hits,
        stop_hits=stop_hits,
        time_exits=time_exits,
        insufficient_data=insufficient,
        hit_rate=hit_rate,
        avg_r_multiple=avg_r,
        avg_max_adverse_excursion_r=avg_mae,
        worst_max_adverse_excursion_r=worst_mae,
    )
