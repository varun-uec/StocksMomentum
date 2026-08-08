"""Universe calibration metrics (RP-012 Phase 2 Gate 4d).

Pure, I/O-free comparison of a reconstructed ``historical_universe`` membership
against the actual production qualified/eligible universe on matched dates. The
two research targets:

* **coverage** — % of production-universe securities also present in the
  reconstructed universe, target ≥ 90%;
* **count ratio** — reconstructed count / production count, target within ±15%.

Engineering only computes and reports these numbers. It does NOT adjust the
liquidity floor ``L`` to hit a target — recalibration is a research decision
they explicitly reserved (see the module constants in ``liquidity_floor``).
"""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

COVERAGE_TARGET: Decimal = Decimal("0.90")
COUNT_RATIO_LOW: Decimal = Decimal("0.85")
COUNT_RATIO_HIGH: Decimal = Decimal("1.15")


@dataclass(frozen=True, slots=True)
class DateCalibration:
    """Calibration outcome for a single matched date."""

    as_of: date
    production_count: int
    reconstructed_count: int
    overlap_count: int
    coverage: Decimal | None
    count_ratio: Decimal | None

    @property
    def precision(self) -> Decimal | None:
        """Fraction of the reconstructed set also in production (overlap/reconstructed).

        ``coverage`` is containment *recall* (overlap/production); this is the
        complementary *precision*. Together they form the corrected P/R
        diagnostic — a count_ratio near 1.0 can mask poor precision and recall
        that offset each other (false positives cancelling false negatives).
        """
        if self.reconstructed_count <= 0:
            return None
        return Decimal(self.overlap_count) / Decimal(self.reconstructed_count)

    @property
    def coverage_passes(self) -> bool:
        """Whether coverage meets the ≥90% target (``False`` when incomputable)."""
        return self.coverage is not None and self.coverage >= COVERAGE_TARGET

    @property
    def count_ratio_passes(self) -> bool:
        """Whether the count ratio sits within the ±15% band (``False`` when incomputable)."""
        return (
            self.count_ratio is not None
            and COUNT_RATIO_LOW <= self.count_ratio <= COUNT_RATIO_HIGH
        )

    def to_dict(self) -> dict[str, object]:
        """Return a serializable summary for the report."""
        return {
            "as_of": self.as_of.isoformat(),
            "production_count": self.production_count,
            "reconstructed_count": self.reconstructed_count,
            "overlap_count": self.overlap_count,
            "coverage_recall": None if self.coverage is None else str(self.coverage),
            "precision": None if self.precision is None else str(self.precision),
            "coverage_passes": self.coverage_passes,
            "count_ratio": None if self.count_ratio is None else str(self.count_ratio),
            "count_ratio_passes": self.count_ratio_passes,
        }


def calibrate_date(
    as_of: date, production_set: Set[int], reconstructed_set: Set[int]
) -> DateCalibration:
    """Compute the calibration metrics for one matched date (pure)."""
    production_count = len(production_set)
    reconstructed_count = len(reconstructed_set)
    overlap = len(set(production_set) & set(reconstructed_set))
    coverage = (
        Decimal(overlap) / Decimal(production_count) if production_count > 0 else None
    )
    count_ratio = (
        Decimal(reconstructed_count) / Decimal(production_count)
        if production_count > 0
        else None
    )
    return DateCalibration(
        as_of=as_of,
        production_count=production_count,
        reconstructed_count=reconstructed_count,
        overlap_count=overlap,
        coverage=coverage,
        count_ratio=count_ratio,
    )


def direction_of_miss(calibration: DateCalibration) -> str:
    """Describe whether the reconstructed universe is over- or under-inclusive.

    Returns a stable label research can act on: ``"over_inclusive"``,
    ``"under_inclusive"``, or ``"within_tolerance"``. Never adjusts ``L``.
    """
    if calibration.count_ratio is None:
        return "incomputable"
    if calibration.count_ratio > COUNT_RATIO_HIGH:
        return "over_inclusive"
    if calibration.count_ratio < COUNT_RATIO_LOW:
        return "under_inclusive"
    return "within_tolerance"
