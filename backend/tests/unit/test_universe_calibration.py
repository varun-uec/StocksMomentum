"""Unit tests for RP-012 Gate 4d calibration metrics (pure)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.research.universe_calibration import (
    calibrate_date,
    direction_of_miss,
)


class TestCalibrateDate:
    def test_perfect_overlap(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), {1, 2, 3, 4}, {1, 2, 3, 4})
        assert cal.coverage == Decimal("1")
        assert cal.count_ratio == Decimal("1")
        assert cal.coverage_passes and cal.count_ratio_passes

    def test_coverage_below_target(self) -> None:
        # Production {1..10}; reconstructed only contains 8 of them → 80% coverage.
        cal = calibrate_date(date(2020, 1, 1), set(range(1, 11)), set(range(1, 9)))
        assert cal.coverage == Decimal("8") / Decimal("10")
        assert not cal.coverage_passes

    def test_over_inclusive_direction(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), {1, 2}, {1, 2, 3, 4, 5})
        assert direction_of_miss(cal) == "over_inclusive"

    def test_precision_complements_recall(self) -> None:
        # Production {1..4}; reconstructed {1,2,3,5,6}: overlap=3.
        # recall = 3/4, precision = 3/5. count_ratio 5/4 masks both misses.
        cal = calibrate_date(date(2020, 1, 1), {1, 2, 3, 4}, {1, 2, 3, 5, 6})
        assert cal.coverage == Decimal("3") / Decimal("4")
        assert cal.precision == Decimal("3") / Decimal("5")

    def test_precision_none_when_reconstructed_empty(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), {1, 2}, set())
        assert cal.precision is None

    def test_under_inclusive_direction(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), set(range(1, 11)), {1, 2})
        assert direction_of_miss(cal) == "under_inclusive"

    def test_within_tolerance_direction(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), set(range(1, 101)), set(range(1, 96)))
        assert direction_of_miss(cal) == "within_tolerance"

    def test_empty_production_incomputable(self) -> None:
        cal = calibrate_date(date(2020, 1, 1), set(), {1, 2})
        assert cal.coverage is None
        assert direction_of_miss(cal) == "incomputable"
