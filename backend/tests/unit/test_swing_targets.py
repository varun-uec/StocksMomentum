"""Unit tests for swing target/stop planning and trade simulation (Phase 3.1/3.2/3.3).

Pure domain service, no I/O -- every case is hand-computable.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.research.swing_targets import (
    DEFAULT_ATR_STOP_MULTIPLE,
    DEFAULT_ATR_TARGET_MULTIPLE,
    TradeOutcome,
    TradeResult,
    aggregate_trade_results,
    compute_swing_target_plan,
    simulate_trade,
)


def _bar(day_offset: int, high: float, low: float, close: float) -> OHLCVBar:
    return OHLCVBar(
        date=date(2026, 1, 1) + timedelta(days=day_offset),
        open=Decimal(str(close)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=1_000_000,
    )


def test_uses_confirmed_swing_resistance_as_target_when_above_entry() -> None:
    """Reward is the real distance to a confirmed pivot, not a near-zero 20d-high artifact."""
    plan = compute_swing_target_plan(
        entry=Decimal("100"), atr14=Decimal("2"), swing_resistance=Decimal("112")
    )
    assert plan is not None
    assert plan.target_basis == "swing_resistance"
    assert plan.target == Decimal("112")
    assert plan.stop == Decimal("100") - Decimal("2") * DEFAULT_ATR_STOP_MULTIPLE  # 96
    assert plan.risk_amount == Decimal("4")
    assert plan.reward_amount == Decimal("12")
    assert plan.rr_ratio == Decimal("3")


def test_no_confirmed_resistance_falls_back_to_atr_multiple_not_zero() -> None:
    """This is the exact defect being fixed: a breakout stock at a new high has no
    resistance above it, so the old rule's reward collapsed to ~zero. The fallback
    must produce a real, non-trivial reward instead.
    """
    plan = compute_swing_target_plan(
        entry=Decimal("100"), atr14=Decimal("2"), swing_resistance=None
    )
    assert plan is not None
    assert plan.target_basis == "atr_multiple"
    assert plan.target == Decimal("100") + Decimal("2") * DEFAULT_ATR_TARGET_MULTIPLE  # 106
    assert plan.reward_amount == Decimal("6")
    # below the strategy's 2.0 min_ratio -- doesn't pass by default
    assert plan.rr_ratio == Decimal("1.5")


def test_resistance_below_or_at_entry_is_ignored_uses_fallback() -> None:
    """A stale/irrelevant resistance level below the current entry must not be used."""
    plan = compute_swing_target_plan(
        entry=Decimal("100"), atr14=Decimal("2"), swing_resistance=Decimal("95")
    )
    assert plan is not None
    assert plan.target_basis == "atr_multiple"


def test_missing_atr_falls_back_to_percentage_risk() -> None:
    plan = compute_swing_target_plan(entry=Decimal("100"), atr14=None, swing_resistance=None)
    assert plan is not None
    assert plan.risk_amount == Decimal("100") * Decimal("0.02")  # 2.0
    assert plan.stop == Decimal("98.00")
    # No ATR for the fallback target multiple either -> risk scaled by min RR ratio.
    assert plan.reward_amount == Decimal("2.0") * Decimal("2.0")  # 4.0
    assert plan.rr_ratio == Decimal("2")


def test_zero_atr_falls_back_like_missing_atr() -> None:
    plan_zero = compute_swing_target_plan(
        entry=Decimal("100"), atr14=Decimal("0"), swing_resistance=None
    )
    plan_none = compute_swing_target_plan(
        entry=Decimal("100"), atr14=None, swing_resistance=None
    )
    assert plan_zero is not None and plan_none is not None
    assert plan_zero.risk_amount == plan_none.risk_amount
    assert plan_zero.target == plan_none.target


def test_non_positive_entry_returns_none() -> None:
    zero = compute_swing_target_plan(entry=Decimal("0"), atr14=Decimal("2"), swing_resistance=None)
    negative = compute_swing_target_plan(
        entry=Decimal("-5"), atr14=Decimal("2"), swing_resistance=None
    )
    assert zero is None
    assert negative is None


def test_plan_is_internally_consistent() -> None:
    """rr_ratio always equals reward_amount / risk_amount, and stop < entry < target."""
    plan = compute_swing_target_plan(
        entry=Decimal("250"), atr14=Decimal("5.5"), swing_resistance=Decimal("270")
    )
    assert plan is not None
    assert plan.rr_ratio == plan.reward_amount / plan.risk_amount
    assert plan.stop < plan.entry < plan.target


# ── simulate_trade (Phase 3.3) ────────────────────────────────────────────────

# entry=100, atr=2 -> stop=96, no resistance -> target=100+2*3=106, risk=4, rr=1.5
_PLAN = compute_swing_target_plan(entry=Decimal("100"), atr14=Decimal("2"), swing_resistance=None)


def test_simulate_trade_target_hit_first() -> None:
    assert _PLAN is not None
    bars = [
        _bar(1, high=102, low=99, close=101),
        _bar(2, high=107, low=100, close=106.5),  # high crosses target=106
        _bar(3, high=110, low=105, close=108),  # would also hit, but already exited
    ]
    result = simulate_trade(_PLAN, bars, max_holding_days=20)
    assert result.outcome == TradeOutcome.TARGET_HIT
    assert result.exit_price == Decimal("106")
    assert result.days_held == 2
    assert result.r_multiple == _PLAN.rr_ratio  # 1.5


def test_simulate_trade_stop_hit_first() -> None:
    assert _PLAN is not None
    bars = [
        _bar(1, high=101, low=98, close=99),
        _bar(2, high=100, low=95, close=96),  # low crosses stop=96
    ]
    result = simulate_trade(_PLAN, bars, max_holding_days=20)
    assert result.outcome == TradeOutcome.STOP_HIT
    assert result.exit_price == Decimal("96")
    assert result.days_held == 2
    assert result.r_multiple == Decimal("-1")  # a full risk unit lost, by definition


def test_simulate_trade_both_touched_same_day_assumes_stop_first() -> None:
    """Conservative convention: without intrabar sequencing, assume the worse outcome."""
    assert _PLAN is not None
    bars = [_bar(1, high=110, low=90, close=100)]  # both stop (96) and target (106) in range
    result = simulate_trade(_PLAN, bars, max_holding_days=20)
    assert result.outcome == TradeOutcome.STOP_HIT


def test_simulate_trade_stop_fill_gaps_through_to_open_not_the_unreachable_stop_price() -> None:
    """Phase 3b.4: a stop order can't fill better than the first tradeable price.

    stop=96; the stock gaps down and opens at 93, well below the stop -- the
    realistic fill is the open (93), not the stop price it never traded at.
    """
    assert _PLAN is not None
    bar = OHLCVBar(
        date=date(2026, 1, 2), open=Decimal("93"), high=Decimal("94"),
        low=Decimal("90"), close=Decimal("91"), volume=1_000_000,
    )
    result = simulate_trade(_PLAN, [bar], max_holding_days=20)
    assert result.outcome == TradeOutcome.STOP_HIT
    assert result.exit_price == Decimal("93")
    assert result.r_multiple == (Decimal("93") - Decimal("100")) / Decimal("4")  # -1.75R


def test_simulate_trade_stop_fill_is_the_stop_price_when_no_gap() -> None:
    """No gap (open above stop) -> fill at the stop price itself, as before."""
    assert _PLAN is not None
    bars = [_bar(1, high=100, low=95, close=96)]  # open=close=96, matches the stop exactly
    result = simulate_trade(_PLAN, bars, max_holding_days=20)
    assert result.exit_price == Decimal("96")
    assert result.r_multiple == Decimal("-1")


def test_simulate_trade_time_exit_uses_last_close_not_a_guess() -> None:
    assert _PLAN is not None
    bars = [
        _bar(1, high=101, low=99, close=100.5),
        _bar(2, high=102, low=99.5, close=101.5),
    ]
    result = simulate_trade(_PLAN, bars, max_holding_days=2)
    assert result.outcome == TradeOutcome.TIME_EXIT
    assert result.exit_price == Decimal("101.5")
    assert result.days_held == 2
    assert result.r_multiple == (Decimal("101.5") - Decimal("100")) / Decimal("4")


def test_simulate_trade_no_bars_is_insufficient_data() -> None:
    assert _PLAN is not None
    result = simulate_trade(_PLAN, [], max_holding_days=20)
    assert result.outcome == TradeOutcome.INSUFFICIENT_DATA
    assert result.exit_price is None
    assert result.r_multiple is None


def test_simulate_trade_max_adverse_excursion_tracks_worst_intraday_dip() -> None:
    """A dip that doesn't trigger the stop must still be recorded as the MAE."""
    assert _PLAN is not None
    bars = [
        _bar(1, high=101, low=97, close=100),  # dips to 97 (worse than entry) but stop is 96
        _bar(2, high=107, low=99, close=106.5),  # then recovers and hits target
    ]
    result = simulate_trade(_PLAN, bars, max_holding_days=20)
    assert result.outcome == TradeOutcome.TARGET_HIT
    # worst excursion: (97-100)/4 = -0.75R
    assert result.max_adverse_excursion_r == Decimal("-0.75")


def test_simulate_trade_only_considers_bars_within_max_holding_days() -> None:
    assert _PLAN is not None
    bars = [
        _bar(1, high=101, low=99, close=100),
        _bar(2, high=101, low=99, close=100),
        _bar(3, high=200, low=99, close=150),  # would hit target, but outside the window
    ]
    result = simulate_trade(_PLAN, bars, max_holding_days=2)
    assert result.outcome == TradeOutcome.TIME_EXIT
    assert result.days_held == 2


# ── aggregate_trade_results (Phase 3.3) ───────────────────────────────────────


def test_aggregate_hit_rate_excludes_time_exits() -> None:
    """hit_rate is target_hits / (target_hits + stop_hits) -- time-exits don't count either way."""
    results = [
        TradeResult(TradeOutcome.TARGET_HIT, Decimal("106"), 5, Decimal("1.5"), Decimal("-0.1")),
        TradeResult(TradeOutcome.TARGET_HIT, Decimal("106"), 3, Decimal("1.5"), Decimal("0")),
        TradeResult(TradeOutcome.STOP_HIT, Decimal("96"), 2, Decimal("-1"), Decimal("-1")),
        TradeResult(TradeOutcome.TIME_EXIT, Decimal("101"), 20, Decimal("0.25"), Decimal("-0.3")),
    ]
    report = aggregate_trade_results(results)
    assert report.total_trades == 4
    assert report.target_hits == 2
    assert report.stop_hits == 1
    assert report.time_exits == 1
    assert report.hit_rate == Decimal("2") / Decimal("3")  # 2 of 3 *decided* trades


def test_aggregate_avg_r_includes_time_exits() -> None:
    results = [
        TradeResult(TradeOutcome.TARGET_HIT, Decimal("106"), 5, Decimal("1.5"), Decimal("0")),
        TradeResult(TradeOutcome.STOP_HIT, Decimal("96"), 2, Decimal("-1"), Decimal("-1")),
        TradeResult(TradeOutcome.TIME_EXIT, Decimal("101"), 20, Decimal("0.5"), Decimal("-0.2")),
    ]
    report = aggregate_trade_results(results)
    assert report.avg_r_multiple == (Decimal("1.5") + Decimal("-1") + Decimal("0.5")) / 3


def test_aggregate_insufficient_data_excluded_from_all_stats() -> None:
    results = [
        TradeResult(TradeOutcome.TARGET_HIT, Decimal("106"), 5, Decimal("1.5"), Decimal("0")),
        TradeResult(TradeOutcome.INSUFFICIENT_DATA, None, None, None, None),
    ]
    report = aggregate_trade_results(results)
    assert report.total_trades == 2
    assert report.insufficient_data == 1
    assert report.hit_rate == Decimal("1")  # 1/1 decided trades
    assert report.avg_r_multiple == Decimal("1.5")


def test_aggregate_empty_results_reports_none_not_a_crash() -> None:
    report = aggregate_trade_results([])
    assert report.total_trades == 0
    assert report.hit_rate is None
    assert report.avg_r_multiple is None
    assert report.avg_max_adverse_excursion_r is None


def test_aggregate_worst_mae_is_the_minimum_not_the_average() -> None:
    results = [
        TradeResult(TradeOutcome.TARGET_HIT, Decimal("106"), 5, Decimal("1.5"), Decimal("-0.2")),
        TradeResult(TradeOutcome.STOP_HIT, Decimal("96"), 2, Decimal("-1"), Decimal("-1.0")),
    ]
    report = aggregate_trade_results(results)
    assert report.worst_max_adverse_excursion_r == Decimal("-1.0")
    assert report.avg_max_adverse_excursion_r == Decimal("-0.6")
