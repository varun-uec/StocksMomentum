"""Golden Dataset — permanent regression scenarios for stock-selection quality.

Each scenario below is a real, verified (symbol, run_date) observation from the
platform's own screening history, frozen as a constant rather than re-queried
live: a "golden" dataset must be stable so that a methodology change is judged
against a fixed reference, not a moving one.

Provenance: pulled from ``forward_returns``/``screening_results`` for the
production strategy (``minervini_trend_template``, strategy_id=30) after the
2026-07-02 data-integrity fixes (exclude_historical default, momentum-score-
as-return bug, stale-OHLCV-data screening bug). Each candidate's underlying
OHLCV series was manually inspected for continuity around its run_date to
rule out data-quality artifacts (e.g. KAUSHALYA and VERTOZ were rejected as
candidates: both have multi-month trading gaps that inflate their forward
returns into implausible territory -- exactly the kind of anomaly this suite
exists to keep out of the golden set). No forward return here is fabricated
or estimated -- each is the platform's own measured 120-trading-day forward
return, computed by the forward-returns feature store from real OHLCV bars.

Every future methodology change (rule/threshold/weight edit, ranking formula
change, engine ablation) must not silently reclassify these frozen
observations into a different performance tier without a deliberate,
reviewed decision -- that is what this suite guards against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.domain.research.forward_returns import classify_performance_tier


@dataclass(frozen=True, slots=True)
class GoldenObservation:
    """A frozen, real, verified (symbol, run_date) outcome with its expected tier."""

    label: str
    symbol: str
    run_date: date
    was_qualified: bool
    rank: int | None
    forward_return_120d: Decimal
    expected_tier: str


GOLDEN_OBSERVATIONS: tuple[GoldenObservation, ...] = (
    GoldenObservation(
        label="exceptional_winner",
        symbol="CGPOWER",
        run_date=date(2021, 2, 9),
        was_qualified=True,
        rank=1,
        forward_return_120d=Decimal("2.6077"),
        expected_tier="exceptional_winner",
    ),
    GoldenObservation(
        label="failure",
        symbol="DANGEE",
        run_date=date(2022, 6, 21),
        was_qualified=True,
        rank=3,
        forward_return_120d=Decimal("-0.9508"),
        expected_tier="failure",
    ),
    GoldenObservation(
        label="missed_winner",
        symbol="KIOCL",
        run_date=date(2020, 12, 9),
        was_qualified=False,
        rank=None,
        forward_return_120d=Decimal("1.4996"),
        expected_tier="exceptional_winner",
    ),
)


def test_golden_observations_are_internally_consistent() -> None:
    """A sanity check on the fixture itself: qualified/rank must agree."""
    for obs in GOLDEN_OBSERVATIONS:
        assert obs.was_qualified == (obs.rank is not None), obs.label


def test_golden_observations_classify_into_expected_tier() -> None:
    """The domain classifier must place each frozen, real observation in its known tier.

    This is the core regression guard: if a future change to
    ``PERFORMANCE_TIERS`` or ``classify_performance_tier`` silently moves
    these real, previously-verified outcomes into a different tier, this
    test fails and the change must be deliberately reviewed.
    """
    for obs in GOLDEN_OBSERVATIONS:
        actual_tier = classify_performance_tier(obs.forward_return_120d)
        assert actual_tier == obs.expected_tier, (
            f"{obs.label} ({obs.symbol} {obs.run_date}): expected tier "
            f"'{obs.expected_tier}' for forward_return={obs.forward_return_120d}, "
            f"got '{actual_tier}'"
        )


def test_missed_winner_was_not_qualified_despite_strong_forward_return() -> None:
    """The missed-winner scenario documents a real, known gap: KIOCL was not
    qualified by the strategy on 2020-12-09, yet went on to return +150% over
    the next 120 trading days. This is not asserted as a bug -- a screen
    trades recall for precision by design -- but it must remain a visible,
    tracked case rather than silently disappear if a future change alters
    what "qualified" means for this exact historical scenario.
    """
    missed = next(o for o in GOLDEN_OBSERVATIONS if o.label == "missed_winner")
    assert missed.was_qualified is False
    assert classify_performance_tier(missed.forward_return_120d) == "exceptional_winner"
