"""Unit tests for the forward-return domain function (Objective 4)."""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.research.forward_returns import (
    classify_performance_tier,
    compute_forward_return,
)


def _closes(*values: str) -> list[Decimal]:
    return [Decimal(v) for v in values]


class TestComputeForwardReturn:
    def test_simple_uptrend_return(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=3,
            entry_close=Decimal("100"),
            forward_closes=_closes("105", "110", "120"),
        )
        assert fr is not None
        assert fr.security_id == 1
        assert fr.horizon_days == 3
        assert fr.forward_return == Decimal("0.20")  # (120/100) - 1

    def test_insufficient_forward_bars_returns_none(self) -> None:
        # Only 2 bars available for a 5-day horizon -- the horizon hasn't
        # elapsed yet, so this must not extrapolate a partial window.
        fr = compute_forward_return(
            security_id=1,
            horizon_days=5,
            entry_close=Decimal("100"),
            forward_closes=_closes("105", "110"),
        )
        assert fr is None

    def test_non_positive_entry_close_returns_none(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=1,
            entry_close=Decimal("0"),
            forward_closes=_closes("100"),
        )
        assert fr is None

    def test_max_drawdown_captures_the_worst_dip_in_the_path(self) -> None:
        # Path: 100 -> 90 (dip) -> 130 (recovers and exceeds entry).
        fr = compute_forward_return(
            security_id=1,
            horizon_days=2,
            entry_close=Decimal("100"),
            forward_closes=_closes("90", "130"),
        )
        assert fr is not None
        assert fr.forward_max_drawdown == Decimal("-0.1")  # (90-100)/100
        assert fr.forward_return == Decimal("0.30")  # (130/100) - 1

    def test_extra_forward_closes_beyond_horizon_are_ignored(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=2,
            entry_close=Decimal("100"),
            forward_closes=_closes("110", "120", "999"),
        )
        assert fr is not None
        assert fr.forward_return == Decimal("0.20")  # uses only the first 2 bars

    def test_volatility_is_zero_for_a_flat_path(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=3,
            entry_close=Decimal("100"),
            forward_closes=_closes("100", "100", "100"),
        )
        assert fr is not None
        assert fr.forward_volatility == Decimal("0")

    def test_mfe_and_mae_are_entry_anchored_not_rolling_peak(self) -> None:
        # Path: 100 -> 150 (best point, +50%) -> 80 (worst point, -20%) -> 120 (end, +20%).
        # MFE/MAE look at every point in the window relative to entry, unlike
        # forward_max_drawdown which resets its peak as new highs are made.
        fr = compute_forward_return(
            security_id=1,
            horizon_days=3,
            entry_close=Decimal("100"),
            forward_closes=_closes("150", "80", "120"),
        )
        assert fr is not None
        assert fr.forward_mfe == Decimal("0.50")  # (150-100)/100
        assert fr.forward_mae == Decimal("-0.20")  # (80-100)/100
        assert fr.forward_return == Decimal("0.20")  # (120-100)/100

    def test_benchmark_return_and_excess_return_computed_when_supplied(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=2,
            entry_close=Decimal("100"),
            forward_closes=_closes("110", "115"),
            benchmark_entry_close=Decimal("1000"),
            benchmark_exit_close=Decimal("1050"),
        )
        assert fr is not None
        assert fr.forward_return == Decimal("0.15")  # (115/100) - 1
        assert fr.benchmark_return == Decimal("0.05")  # (1050/1000) - 1
        assert fr.excess_return == Decimal("0.10")  # 0.15 - 0.05

    def test_benchmark_fields_are_none_when_not_supplied(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=1,
            entry_close=Decimal("100"),
            forward_closes=_closes("110"),
        )
        assert fr is not None
        assert fr.benchmark_return is None
        assert fr.excess_return is None

    def test_benchmark_fields_are_none_when_benchmark_entry_close_is_zero(self) -> None:
        fr = compute_forward_return(
            security_id=1,
            horizon_days=1,
            entry_close=Decimal("100"),
            forward_closes=_closes("110"),
            benchmark_entry_close=Decimal("0"),
            benchmark_exit_close=Decimal("1050"),
        )
        assert fr is not None
        assert fr.benchmark_return is None
        assert fr.excess_return is None


class TestClassifyPerformanceTier:
    def test_exceptional_winner(self) -> None:
        assert classify_performance_tier(Decimal("0.75")) == "exceptional_winner"
        assert classify_performance_tier(Decimal("0.50")) == "exceptional_winner"  # boundary

    def test_strong_performer(self) -> None:
        assert classify_performance_tier(Decimal("0.35")) == "strong_performer"
        assert classify_performance_tier(Decimal("0.20")) == "strong_performer"  # boundary

    def test_average_performer(self) -> None:
        assert classify_performance_tier(Decimal("0.10")) == "average_performer"
        assert classify_performance_tier(Decimal("0")) == "average_performer"  # boundary

    def test_underperformer(self) -> None:
        assert classify_performance_tier(Decimal("-0.05")) == "underperformer"
        assert classify_performance_tier(Decimal("-0.15")) == "underperformer"  # boundary

    def test_failure(self) -> None:
        assert classify_performance_tier(Decimal("-0.16")) == "failure"
        assert classify_performance_tier(Decimal("-0.90")) == "failure"
