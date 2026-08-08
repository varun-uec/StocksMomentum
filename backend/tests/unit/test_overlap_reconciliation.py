"""Unit tests for the RP-012 Gate 4a reconciliation tally (pure)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from momentum25.domain.research.overlap_reconciliation import (
    MISMATCH_CLOSE,
    MISMATCH_VOLUME,
    ReconciliationTally,
    compare_pair,
)


@dataclass(frozen=True)
class _Bar:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def _bar(close: str, volume: int = 100) -> _Bar:
    c = Decimal(close)
    return _Bar(open=c, high=c, low=c, close=c, volume=volume)


class TestComparePair:
    def test_exact_match(self) -> None:
        cmp = compare_pair("X", _bar("100.00"), _bar("100.00"))
        assert cmp.close_matches and cmp.volume_matches and cmp.ohl_matches

    def test_close_within_tolerance(self) -> None:
        cmp = compare_pair("X", _bar("100.00"), _bar("100.01"))
        assert cmp.close_matches

    def test_close_beyond_tolerance(self) -> None:
        cmp = compare_pair("X", _bar("100.00"), _bar("100.02"))
        assert not cmp.close_matches

    def test_volume_mismatch(self) -> None:
        cmp = compare_pair("X", _bar("100.00", 100), _bar("100.00", 101))
        assert not cmp.volume_matches


class TestTally:
    def test_perfect_window_passes(self) -> None:
        tally = ReconciliationTally()
        legacy = {"A": _bar("10"), "B": _bar("20")}
        current = {"A": _bar("10"), "B": _bar("20")}
        tally.add_date(legacy, current, "2020-01-01")
        assert tally.close_match_rate == Decimal("1")
        assert tally.volume_match_rate == Decimal("1")
        assert tally.coverage_match_rate == Decimal("1")
        assert tally.passes

    def test_close_mismatch_recorded_and_rate_drops(self) -> None:
        tally = ReconciliationTally()
        legacy = {f"S{i}": _bar("10") for i in range(1000)}
        current = dict(legacy)
        current["S0"] = _bar("999")
        tally.add_date(legacy, current, "2020-01-02")
        assert tally.close_matches == 999
        assert tally.close_match_rate == Decimal("999") / Decimal("1000")
        assert MISMATCH_CLOSE in tally.mismatch_examples
        # 99.9% target is exactly met at 999/1000.
        assert tally.close_match_rate >= Decimal("0.999")

    def test_coverage_gap_lowers_rate(self) -> None:
        tally = ReconciliationTally()
        legacy = {"A": _bar("10"), "B": _bar("20"), "C": _bar("30")}
        current = {"A": _bar("10"), "B": _bar("20")}  # C legacy-only
        tally.add_date(legacy, current, "2020-01-03")
        assert tally.legacy_only_occurrences == 1
        assert tally.coverage_match_rate == Decimal("2") / Decimal("3")

    def test_volume_mismatch_recorded(self) -> None:
        tally = ReconciliationTally()
        legacy = {"A": _bar("10", 100)}
        current = {"A": _bar("10", 200)}
        tally.add_date(legacy, current, "2020-01-04")
        assert tally.volume_matches == 0
        assert MISMATCH_VOLUME in tally.mismatch_examples

    def test_gate_uses_forward_not_union(self) -> None:
        # Every legacy symbol is present in current (forward = 1.0), but current
        # carries many extra symbols absent from legacy → union coverage is far
        # below 0.99. The forward estimator is now authoritative, so the gate
        # must PASS despite the low union.
        legacy = {f"L{i}": _bar("10") for i in range(100)}
        current = dict(legacy)
        current.update({f"X{i}": _bar("10") for i in range(100)})  # 100 current-only
        tally = ReconciliationTally()
        tally.add_date(legacy, current, "2020-01-05")
        assert tally.coverage_forward_rate == Decimal("1")
        assert tally.coverage_match_rate < Decimal("0.99")  # union is low
        assert tally.passes  # gated on forward, not union

    def test_gate_fails_when_forward_below_target(self) -> None:
        # Legacy symbols missing from current drag the forward estimator down.
        legacy = {f"L{i}": _bar("10") for i in range(100)}
        current = {f"L{i}": _bar("10") for i in range(90)}  # 10 legacy-only
        tally = ReconciliationTally()
        tally.add_date(legacy, current, "2020-01-06")
        assert tally.coverage_forward_rate == Decimal("90") / Decimal("100")
        assert not tally.passes

    def test_empty_tally_reports_zero_not_error(self) -> None:
        tally = ReconciliationTally()
        assert tally.close_match_rate == Decimal("0")
        assert not tally.passes
