"""Gate 4a — overlap reconciliation of legacy vs current-provider bars.

Pure, I/O-free comparison logic (ADR-009). For every trading date in the
RP-012 overlap window (2019-09-30 → ~2024-07-05) the caller joins the legacy
archive's EQ bars against the current provider's EQ bars on ``(symbol, date)``
and feeds them here. This module computes the three research-specified
pass criteria and, crucially, classifies every mismatch so it can be *explained*
rather than waved through:

* (a) raw close match ≥ 99.9% of joined pairs within ₹0.01;
* (b) symbol-coverage overlap ≥ 99% between the legacy EQ set and the current
  EQ set per date;
* (c) volume match ≥ 99% exact on ``TOTTRDQTY``.

The comparison is on **raw, pre-adjustment** O/H/L/C and volume — both sources
report unadjusted EOD prints for a session, so a genuine data match must hold
before any corporate-action adjustment is applied.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

# Research-specified tolerances / gate thresholds (RP-012 Phase 2 §2).
CLOSE_TOLERANCE: Decimal = Decimal("0.01")
CLOSE_MATCH_TARGET: Decimal = Decimal("0.999")
# Coverage gate criterion (RP-012): research decided the FORWARD estimator
# (fraction of legacy EQ symbol-occurrences also present in the current set,
# i.e. scoped to securities present in both providers reachable from the legacy
# side) is authoritative, target ≥0.99. Union/reverse are retired as pass/fail
# criteria but still reported for transparency and trend-tracking.
COVERAGE_MATCH_TARGET: Decimal = Decimal("0.99")
VOLUME_MATCH_TARGET: Decimal = Decimal("0.99")

# Mismatch classification codes (stable, aggregatable).
MISMATCH_CLOSE = "close_diff_gt_tolerance"
MISMATCH_VOLUME = "volume_diff"
MISMATCH_OHL = "ohl_diff_gt_tolerance"


class BarLike(Protocol):
    """The minimal shape both legacy and current bars satisfy for reconciliation."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class PairComparison:
    """The comparison outcome for one ``(symbol, date)`` present in both sources."""

    symbol: str
    close_matches: bool
    volume_matches: bool
    ohl_matches: bool
    legacy_close: Decimal
    current_close: Decimal
    legacy_volume: int
    current_volume: int


def compare_pair(symbol: str, legacy: BarLike, current: BarLike) -> PairComparison:
    """Compare one legacy vs current bar for a symbol on a single date (pure)."""
    close_matches = abs(legacy.close - current.close) <= CLOSE_TOLERANCE
    volume_matches = legacy.volume == current.volume
    ohl_matches = (
        abs(legacy.open - current.open) <= CLOSE_TOLERANCE
        and abs(legacy.high - current.high) <= CLOSE_TOLERANCE
        and abs(legacy.low - current.low) <= CLOSE_TOLERANCE
    )
    return PairComparison(
        symbol=symbol,
        close_matches=close_matches,
        volume_matches=volume_matches,
        ohl_matches=ohl_matches,
        legacy_close=legacy.close,
        current_close=current.close,
        legacy_volume=legacy.volume,
        current_volume=current.volume,
    )


@dataclass(slots=True)
class ReconciliationTally:
    """Accumulates reconciliation counts across every date in the window.

    Mutable by design — a single instance is folded over the window one date at
    a time — but every derived rate is a pure function of the accumulated
    counts, so the final report is deterministic given the same inputs.
    """

    joined_pairs: int = 0
    close_matches: int = 0
    volume_matches: int = 0
    ohl_matches: int = 0

    legacy_symbol_occurrences: int = 0
    current_symbol_occurrences: int = 0
    overlap_symbol_occurrences: int = 0
    legacy_only_occurrences: int = 0
    current_only_occurrences: int = 0

    dates_processed: int = 0
    mismatch_examples: dict[str, list[str]] = field(default_factory=dict)

    _example_cap: int = 20

    def add_date(
        self,
        legacy_bars: Mapping[str, BarLike],
        current_bars: Mapping[str, BarLike],
        date_label: str = "",
    ) -> None:
        """Fold one trading date's legacy/current EQ bars into the tally."""
        self.dates_processed += 1
        legacy_symbols = set(legacy_bars)
        current_symbols = set(current_bars)
        overlap = legacy_symbols & current_symbols

        self.legacy_symbol_occurrences += len(legacy_symbols)
        self.current_symbol_occurrences += len(current_symbols)
        self.overlap_symbol_occurrences += len(overlap)
        self.legacy_only_occurrences += len(legacy_symbols - current_symbols)
        self.current_only_occurrences += len(current_symbols - legacy_symbols)

        for symbol in sorted(overlap):
            comparison = compare_pair(symbol, legacy_bars[symbol], current_bars[symbol])
            self.joined_pairs += 1
            if comparison.close_matches:
                self.close_matches += 1
            else:
                self._record_example(MISMATCH_CLOSE, symbol, date_label, comparison)
            if comparison.volume_matches:
                self.volume_matches += 1
            else:
                self._record_example(MISMATCH_VOLUME, symbol, date_label, comparison)
            if comparison.ohl_matches:
                self.ohl_matches += 1
            elif comparison.close_matches:
                # Only note an OHL-only mismatch when close agreed — otherwise it
                # is already captured under the close mismatch class.
                self._record_example(MISMATCH_OHL, symbol, date_label, comparison)

    def _record_example(
        self, mismatch_class: str, symbol: str, date_label: str, comparison: PairComparison
    ) -> None:
        bucket = self.mismatch_examples.setdefault(mismatch_class, [])
        if len(bucket) < self._example_cap:
            bucket.append(
                f"{date_label}:{symbol} "
                f"legacy_close={comparison.legacy_close} current_close={comparison.current_close} "
                f"legacy_vol={comparison.legacy_volume} current_vol={comparison.current_volume}"
            )

    # ── Derived rates (pure functions of the counts) ──────────────────────

    @property
    def close_match_rate(self) -> Decimal:
        """Fraction of joined pairs whose raw close agreed within tolerance."""
        return _ratio(self.close_matches, self.joined_pairs)

    @property
    def volume_match_rate(self) -> Decimal:
        """Fraction of joined pairs whose raw volume matched exactly."""
        return _ratio(self.volume_matches, self.joined_pairs)

    @property
    def coverage_match_rate(self) -> Decimal:
        """Symbol-coverage overlap as a fraction of the union of EQ symbols.

        The **union** estimator (RP-012 Phase 2 §2 gate criterion). Research has
        not yet pinned which of the three estimators is authoritative; the gate
        continues to use this one while all three are reported transparently.
        """
        union = (
            self.overlap_symbol_occurrences
            + self.legacy_only_occurrences
            + self.current_only_occurrences
        )
        return _ratio(self.overlap_symbol_occurrences, union)

    @property
    def coverage_forward_rate(self) -> Decimal:
        """Fraction of legacy EQ symbol-occurrences also present in the current set."""
        return _ratio(self.overlap_symbol_occurrences, self.legacy_symbol_occurrences)

    @property
    def coverage_reverse_rate(self) -> Decimal:
        """Fraction of current EQ symbol-occurrences also present in the legacy set."""
        return _ratio(self.overlap_symbol_occurrences, self.current_symbol_occurrences)

    @property
    def passes(self) -> bool:
        """Whether all three research pass criteria are met.

        Coverage now uses the FORWARD estimator (research-decided authoritative
        criterion); union/reverse are reported but no longer gate.
        """
        return (
            self.close_match_rate >= CLOSE_MATCH_TARGET
            and self.coverage_forward_rate >= COVERAGE_MATCH_TARGET
            and self.volume_match_rate >= VOLUME_MATCH_TARGET
        )

    def to_report(self) -> dict[str, object]:
        """Return a serializable summary of the reconciliation outcome."""
        return {
            "dates_processed": self.dates_processed,
            "joined_pairs": self.joined_pairs,
            "close_match_rate": str(self.close_match_rate),
            "close_match_target": str(CLOSE_MATCH_TARGET),
            "close_match_passes": self.close_match_rate >= CLOSE_MATCH_TARGET,
            "volume_match_rate": str(self.volume_match_rate),
            "volume_match_target": str(VOLUME_MATCH_TARGET),
            "volume_match_passes": self.volume_match_rate >= VOLUME_MATCH_TARGET,
            # Authoritative coverage criterion: forward estimator.
            "coverage_match_rate": str(self.coverage_forward_rate),
            "coverage_match_target": str(COVERAGE_MATCH_TARGET),
            "coverage_match_passes": self.coverage_forward_rate >= COVERAGE_MATCH_TARGET,
            "coverage_estimator": "forward_legacy_in_current",
            "coverage_estimators": {
                "forward_legacy_in_current": str(self.coverage_forward_rate),
                "union": str(self.coverage_match_rate),
                "reverse_current_in_legacy": str(self.coverage_reverse_rate),
                "note": (
                    "forward is the authoritative gate criterion (research-decided); "
                    "union/reverse reported for transparency and trend-tracking only."
                ),
            },
            "overlap_symbol_occurrences": self.overlap_symbol_occurrences,
            "legacy_symbol_occurrences": self.legacy_symbol_occurrences,
            "current_symbol_occurrences": self.current_symbol_occurrences,
            "legacy_only_occurrences": self.legacy_only_occurrences,
            "current_only_occurrences": self.current_only_occurrences,
            "mismatch_examples": self.mismatch_examples,
            "gate_passes": self.passes,
        }


def _ratio(numerator: int, denominator: int) -> Decimal:
    """Return ``numerator/denominator`` as a Decimal, or ``0`` when empty."""
    if denominator <= 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def reconcile_window(
    dates: Iterable[tuple[str, Mapping[str, BarLike], Mapping[str, BarLike]]],
) -> ReconciliationTally:
    """Fold an iterable of ``(date_label, legacy_bars, current_bars)`` into a tally."""
    tally = ReconciliationTally()
    for date_label, legacy_bars, current_bars in dates:
        tally.add_date(legacy_bars, current_bars, date_label)
    return tally
