"""Unit tests for RP-012 §3 period-correct-split symbol resolution."""

from __future__ import annotations

from datetime import date

from momentum25.domain.research.period_correct_resolution import (
    PeriodResolutionOutcome,
    SymbolInterval,
    resolve_period_correct,
)


def _chain() -> dict[str, list[SymbolInterval]]:
    """A reused ticker 'X': security 1 until 2020-06-30, security 2 from 2020-08-01."""
    return {
        "X": [
            SymbolInterval(security_id=1, start=date(2010, 1, 1), end=date(2020, 6, 30)),
            SymbolInterval(security_id=2, start=date(2020, 8, 1), end=None),
        ]
    }


def test_contained_resolves_to_period_correct_security() -> None:
    """A date inside the predecessor interval resolves to the predecessor, not the successor."""
    res = resolve_period_correct("X", date(2015, 5, 5), _chain())
    assert res.security_id == 1
    assert res.outcome is PeriodResolutionOutcome.CONTAINED

    res2 = resolve_period_correct("X", date(2022, 5, 5), _chain())
    assert res2.security_id == 2
    assert res2.outcome is PeriodResolutionOutcome.CONTAINED


def test_handoff_gap_resolves_to_nearest_boundary() -> None:
    """A date in the zero-interval handoff gap resolves to the nearest boundary."""
    # 2020-07-05 is 5 days after security 1's end, 27 days before security 2's start.
    res = resolve_period_correct("X", date(2020, 7, 5), _chain())
    assert res.outcome is PeriodResolutionOutcome.BOUNDARY_GAP
    assert res.security_id == 1


def test_overlap_is_a_data_integrity_defect() -> None:
    """Two intervals containing the same date return OVERLAP with no id."""
    intervals = {
        "X": [
            SymbolInterval(1, date(2010, 1, 1), date(2021, 1, 1)),
            SymbolInterval(2, date(2020, 1, 1), None),
        ]
    }
    res = resolve_period_correct("X", date(2020, 6, 1), intervals)
    assert res.security_id is None
    assert res.outcome is PeriodResolutionOutcome.OVERLAP


def test_unknown_symbol() -> None:
    """A symbol with no intervals resolves to UNKNOWN_SYMBOL."""
    res = resolve_period_correct("Y", date(2020, 1, 1), _chain())
    assert res.security_id is None
    assert res.outcome is PeriodResolutionOutcome.UNKNOWN_SYMBOL
