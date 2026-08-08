"""Unit tests for the per-security Data Confidence Score (Alpha Discovery Program, Priority 1)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.research.data_quality import compute_data_confidence_score


def _weekday_bars(start: date, count: int) -> list[OHLCVBar]:
    """Generate ``count`` consecutive weekday bars starting at ``start``."""
    bars = []
    d = start
    while len(bars) < count:
        if d.weekday() < 5:
            bars.append(
                OHLCVBar(
                    date=d, open=Decimal("100"), high=Decimal("101"),
                    low=Decimal("99"), close=Decimal("100"), volume=1000,
                )
            )
        d += timedelta(days=1)
    return bars


class TestComputeDataConfidenceScore:
    def test_complete_coverage_with_no_issues_is_high_confidence(self) -> None:
        start = date(2024, 1, 1)
        end = start + timedelta(days=13)  # 2 full weeks
        bars = _weekday_bars(start, expected_weekdays_in_range(start, end))
        score = compute_data_confidence_score(1, bars, start, end)
        assert score.coverage_ratio == Decimal("1")
        assert score.confidence_level == "high"
        assert score.score == Decimal("100")

    def test_no_bars_at_all_is_low_confidence(self) -> None:
        start = date(2024, 1, 1)
        end = start + timedelta(days=13)
        score = compute_data_confidence_score(1, [], start, end)
        assert score.coverage_ratio == Decimal("0")
        assert score.confidence_level == "low"
        assert score.score == Decimal("0")

    def test_partial_coverage_lands_in_medium_or_low(self) -> None:
        start = date(2024, 1, 1)
        end = start + timedelta(days=27)  # 4 weeks
        full_count = expected_weekdays_in_range(start, end)
        half_bars = _weekday_bars(start, full_count // 2)
        score = compute_data_confidence_score(1, half_bars, start, end)
        assert score.confidence_level in ("medium", "low")
        assert score.score < Decimal("100")

    def test_duplicates_and_anomalies_reduce_score_below_full_coverage(self) -> None:
        start = date(2024, 1, 1)
        end = start + timedelta(days=13)
        full_count = expected_weekdays_in_range(start, end)
        bars = _weekday_bars(start, full_count)
        # Duplicate the first bar's date and inject a price anomaly.
        dirty_bars = [
            bars[0],
            *bars,
            OHLCVBar(
                date=bars[-1].date + timedelta(days=1),
                open=Decimal("100"), high=Decimal("50"),
                low=Decimal("100"), close=Decimal("100"), volume=1000,
            ),
        ]
        clean_score = compute_data_confidence_score(1, bars, start, end)
        dirty_score = compute_data_confidence_score(1, dirty_bars, start, end)
        assert dirty_score.duplicate_count == 1
        assert dirty_score.score < clean_score.score

    def test_deterministic_for_identical_inputs(self) -> None:
        start = date(2024, 1, 1)
        end = start + timedelta(days=13)
        bars = _weekday_bars(start, expected_weekdays_in_range(start, end))
        score_a = compute_data_confidence_score(1, bars, start, end)
        score_b = compute_data_confidence_score(1, bars, start, end)
        assert score_a == score_b


def expected_weekdays_in_range(start: date, end: date) -> int:
    return sum(
        1
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    )
