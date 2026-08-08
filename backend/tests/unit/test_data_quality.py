"""Unit tests for the data-quality domain checks (Objective 5)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.research.data_quality import (
    detect_duplicates,
    detect_gaps,
    detect_price_anomalies,
    detect_volume_anomalies,
    is_stale_as_of,
)


def _bar(
    d: date, close: str, high: str | None = None, low: str | None = None, volume: int = 1000
) -> OHLCVBar:
    c = Decimal(close)
    return OHLCVBar(
        date=d,
        open=c,
        high=Decimal(high) if high else c,
        low=Decimal(low) if low else c,
        close=c,
        volume=volume,
    )


class TestDetectGaps:
    def test_missing_weekday_is_flagged(self) -> None:
        # Mon 2024-01-01 present, Tue 2024-01-02 missing, Wed present.
        bar_dates = [date(2024, 1, 1), date(2024, 1, 3)]
        issues = detect_gaps(bar_dates, date(2024, 1, 1), date(2024, 1, 3))
        assert len(issues) == 1
        assert issues[0].issue_date == date(2024, 1, 2)

    def test_missing_weekend_is_not_flagged(self) -> None:
        # 2024-01-06/07 is a Sat/Sun -- not an expected trading day.
        bar_dates = [date(2024, 1, 5), date(2024, 1, 8)]
        issues = detect_gaps(bar_dates, date(2024, 1, 5), date(2024, 1, 8))
        assert issues == []

    def test_complete_range_yields_no_gaps(self) -> None:
        bar_dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        issues = detect_gaps(bar_dates, date(2024, 1, 1), date(2024, 1, 3))
        assert issues == []


class TestDetectDuplicates:
    def test_duplicate_date_is_flagged(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100"), _bar(date(2024, 1, 1), "101")]
        issues = detect_duplicates(bars)
        assert len(issues) == 1
        assert issues[0].issue_date == date(2024, 1, 1)

    def test_no_duplicates_yields_no_issues(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100"), _bar(date(2024, 1, 2), "101")]
        assert detect_duplicates(bars) == []


class TestDetectPriceAnomalies:
    def test_large_single_day_move_is_flagged(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100"), _bar(date(2024, 1, 2), "200")]
        issues = detect_price_anomalies(bars)
        assert any(
            i.issue_type == "price_anomaly" and i.issue_date == date(2024, 1, 2) for i in issues
        )

    def test_small_move_is_not_flagged(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100"), _bar(date(2024, 1, 2), "101")]
        assert detect_price_anomalies(bars) == []

    def test_close_outside_high_low_range_is_flagged(self) -> None:
        bad_bar = OHLCVBar(
            date=date(2024, 1, 1),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("110"),  # above high -- inconsistent
            volume=1000,
        )
        issues = detect_price_anomalies([bad_bar])
        assert len(issues) == 1
        assert "inconsistent" in issues[0].detail


class TestDetectVolumeAnomalies:
    def test_zero_volume_is_flagged(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100", volume=0)]
        issues = detect_volume_anomalies(bars)
        assert len(issues) == 1
        assert issues[0].issue_type == "volume_anomaly"

    def test_positive_volume_is_not_flagged(self) -> None:
        bars = [_bar(date(2024, 1, 1), "100", volume=1000)]
        assert detect_volume_anomalies(bars) == []


class TestIsStaleAsOf:
    def test_no_bars_is_stale(self) -> None:
        assert is_stale_as_of(date(2026, 6, 24), None) is True

    def test_bar_within_threshold_is_not_stale(self) -> None:
        assert is_stale_as_of(date(2026, 6, 24), date(2026, 6, 1)) is False

    def test_bar_beyond_threshold_is_stale(self) -> None:
        # Last bar over a year before as_of -- ingestion has stopped for
        # this security, not merely a recent gap.
        assert is_stale_as_of(date(2026, 6, 24), date(2024, 11, 13)) is True

    def test_bar_exactly_at_threshold_is_not_stale(self) -> None:
        assert is_stale_as_of(date(2024, 1, 31), date(2024, 1, 1), threshold_days=30) is False

    def test_custom_threshold_is_respected(self) -> None:
        assert is_stale_as_of(date(2024, 1, 15), date(2024, 1, 1), threshold_days=10) is True
