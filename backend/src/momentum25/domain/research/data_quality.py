"""Data-quality validation (Objective 5, Data Quality Framework).

Pure, I/O-free checks over an already-fetched OHLCV bar series: gaps against
the expected trading calendar, duplicate dates, and price/volume anomalies.

Known limitation, disclosed rather than hidden: NSE does not publish a free
machine-readable holiday calendar (not in ``nsemine``, no other verified
source), so the "expected trading calendar" is approximated as weekdays
only. A genuine NSE holiday will surface as a false-positive gap here --
callers presenting this report should say so, not present gap counts as
ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar

# A single-day close-to-close move beyond this threshold with no
# corresponding corporate action is flagged as a price anomaly.
DEFAULT_MAX_DAILY_MOVE_PCT = Decimal("50")

# A security whose most recent available bar is older than this, relative to
# the date being screened, is treated as stale rather than evaluated: scoring
# it would silently reuse a months-old close as if it reflected the screening
# date, which can produce nonsensical indicator values (e.g. an "acceleration"
# rule comparing two windows that both sit far in the past) and misrepresent
# a security whose data ingestion has fallen behind or stopped as an eligible,
# rankable pick.
DEFAULT_STALE_DATA_THRESHOLD_DAYS = 30


def is_stale_as_of(
    as_of_date: date,
    latest_bar_date: date | None,
    threshold_days: int = DEFAULT_STALE_DATA_THRESHOLD_DAYS,
) -> bool:
    """Return whether a security's most recent bar is too old to screen ``as_of_date``.

    ``latest_bar_date`` is the newest bar on or before ``as_of_date`` (not
    today's wall-clock date), so this is correct for both live and historical
    replay: a security is stale relative to the point in time being screened,
    not relative to now.
    """
    if latest_bar_date is None:
        return True
    return (as_of_date - latest_bar_date).days > threshold_days


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """A single detected data-quality issue for one security."""

    issue_type: str  # "gap" | "duplicate" | "price_anomaly" | "volume_anomaly"
    issue_date: date
    detail: str


def detect_gaps(bar_dates: list[date], start: date, end: date) -> list[DataQualityIssue]:
    """Return expected-weekday dates in ``[start, end]`` missing from ``bar_dates``.

    Approximates the trading calendar as all weekdays (Mon-Fri) -- see the
    module-level holiday-calendar limitation above.
    """
    present = set(bar_dates)
    issues: list[DataQualityIssue] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in present:
            issues.append(
                DataQualityIssue(
                    issue_type="gap",
                    issue_date=current,
                    detail="No bar for expected trading weekday",
                )
            )
        current += timedelta(days=1)
    return issues


def detect_duplicates(bars: list[OHLCVBar]) -> list[DataQualityIssue]:
    """Return an issue for every bar date that appears more than once."""
    seen: set[date] = set()
    issues: list[DataQualityIssue] = []
    for bar in bars:
        if bar.date in seen:
            issues.append(
                DataQualityIssue(
                    issue_type="duplicate",
                    issue_date=bar.date,
                    detail="Duplicate bar for this date",
                )
            )
        seen.add(bar.date)
    return issues


def detect_price_anomalies(
    bars: list[OHLCVBar], max_daily_move_pct: Decimal = DEFAULT_MAX_DAILY_MOVE_PCT
) -> list[DataQualityIssue]:
    """Flag internally-inconsistent OHLC rows and outsized single-day moves.

    A large flagged move is not necessarily an error -- a real stock split or
    bonus produces one too. Callers must cross-reference against persisted
    corporate actions before treating a flag as a genuine data defect (see
    ``application.use_cases.research.data_quality_report``).
    """
    issues: list[DataQualityIssue] = []
    for bar in bars:
        if bar.high < bar.low or bar.close > bar.high or bar.close < bar.low:
            issues.append(
                DataQualityIssue(
                    issue_type="price_anomaly",
                    issue_date=bar.date,
                    detail=(
                        "OHLC internally inconsistent (close outside "
                        "[low, high], or high < low)"
                    ),
                )
            )
    for prev_bar, bar in zip(bars, bars[1:], strict=False):
        if prev_bar.close <= 0:
            continue
        move_pct = abs((bar.close - prev_bar.close) / prev_bar.close) * 100
        if move_pct > max_daily_move_pct:
            issues.append(
                DataQualityIssue(
                    issue_type="price_anomaly",
                    issue_date=bar.date,
                    detail=f"{move_pct:.1f}% single-day close-to-close move",
                )
            )
    return issues


def detect_volume_anomalies(bars: list[OHLCVBar]) -> list[DataQualityIssue]:
    """Flag zero or negative volume on a bar."""
    issues: list[DataQualityIssue] = []
    for bar in bars:
        if bar.volume < 0:
            issues.append(
                DataQualityIssue(
                    issue_type="volume_anomaly", issue_date=bar.date, detail="Negative volume"
                )
            )
        elif bar.volume == 0:
            issues.append(
                DataQualityIssue(
                    issue_type="volume_anomaly",
                    issue_date=bar.date,
                    detail="Zero volume on an expected trading day",
                )
            )
    return issues


# Score-band boundaries for DataConfidenceScore.confidence_level.
_HIGH_CONFIDENCE_MIN = Decimal("80")
_MEDIUM_CONFIDENCE_MIN = Decimal("50")

# Penalty weights: each gap/duplicate/anomaly deducts from the coverage-based
# score, capped so a handful of issues on an otherwise-complete series don't
# swamp the coverage signal, but a systemically dirty series is still pushed
# into "low" regardless of raw coverage.
_MAX_GAP_PENALTY = Decimal("30")
_MAX_DUPLICATE_PENALTY = Decimal("15")
_MAX_ANOMALY_PENALTY = Decimal("25")


@dataclass(frozen=True, slots=True)
class DataConfidenceScore:
    """A security's data-quality confidence, 0-100, for one coverage window.

    Deterministic and reproducible: the same bars over the same window
    always yield the same score (ADR-009). ``confidence_level`` is the
    coarse band callers should gate research conclusions on -- "low"-
    confidence securities should be excluded from, or clearly flagged in,
    any statistical finding.
    """

    security_id: int
    score: Decimal
    confidence_level: str  # "high" | "medium" | "low"
    expected_trading_days: int
    actual_bar_count: int
    coverage_ratio: Decimal
    gap_count: int
    duplicate_count: int
    price_anomaly_count: int
    volume_anomaly_count: int


def compute_data_confidence_score(
    security_id: int, bars: list[OHLCVBar], coverage_start: date, coverage_end: date
) -> DataConfidenceScore:
    """Compute a security's data confidence score over ``[coverage_start, coverage_end]``.

    Combines coverage (actual bars vs. expected weekday trading days) with
    the existing gap/duplicate/anomaly detectors -- reuses those functions
    rather than duplicating their logic.
    """
    bar_dates = [b.date for b in bars]
    expected_days = sum(
        1
        for i in range((coverage_end - coverage_start).days + 1)
        if (coverage_start + timedelta(days=i)).weekday() < 5
    )
    coverage_ratio = (
        min(Decimal(len(bars)) / Decimal(expected_days), Decimal("1"))
        if expected_days > 0
        else Decimal("0")
    )

    gap_count = len(detect_gaps(bar_dates, coverage_start, coverage_end))
    duplicate_count = len(detect_duplicates(bars))
    price_anomaly_count = len(detect_price_anomalies(bars))
    volume_anomaly_count = len(detect_volume_anomalies(bars))

    gap_penalty = min(_MAX_GAP_PENALTY, Decimal(gap_count) * Decimal("0.5"))
    duplicate_penalty = min(_MAX_DUPLICATE_PENALTY, Decimal(duplicate_count) * Decimal("5"))
    anomaly_penalty = min(
        _MAX_ANOMALY_PENALTY, Decimal(price_anomaly_count + volume_anomaly_count) * Decimal("1")
    )

    score = max(
        Decimal("0"),
        coverage_ratio * Decimal("100") - gap_penalty - duplicate_penalty - anomaly_penalty,
    )

    if score >= _HIGH_CONFIDENCE_MIN:
        confidence_level = "high"
    elif score >= _MEDIUM_CONFIDENCE_MIN:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return DataConfidenceScore(
        security_id=security_id,
        score=score,
        confidence_level=confidence_level,
        expected_trading_days=expected_days,
        actual_bar_count=len(bars),
        coverage_ratio=coverage_ratio,
        gap_count=gap_count,
        duplicate_count=duplicate_count,
        price_anomaly_count=price_anomaly_count,
        volume_anomaly_count=volume_anomaly_count,
    )
