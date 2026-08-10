"""Unit tests for corporate-action price adjustment (Objective 1, Phase 1).

Covers the pure domain function that compounds backward-adjustment factors
and the conservative free-text parser that resolves a price ratio from NSE's
corporate-action ``subject`` field. Both are deterministic, I/O-free, and
golden-test-covered per ADR-009.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.entities.market_data import compute_adjustment_factors
from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.infrastructure.providers.bhavcopy import _parse_corporate_action_ratio


def _action(ex_date: date, ratio: Decimal | None, action_type: str = "bonus") -> RawCorporateAction:
    return RawCorporateAction(
        symbol="TEST",
        ex_date=ex_date,
        action_type=action_type,
        ratio=ratio,
        raw_subject="test",
    )


class TestComputeAdjustmentFactors:
    """Golden tests for domain.entities.market_data.compute_adjustment_factors."""

    def test_no_actions_yields_factor_one_for_every_bar(self) -> None:
        dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
        factors = compute_adjustment_factors(dates, [])
        assert factors == {d: Decimal("1") for d in dates}

    def test_bonus_adjusts_only_bars_before_ex_date(self) -> None:
        # A 1:1 bonus (ratio 0.5) with ex-date 2026-01-02: bars strictly
        # before the ex-date are halved; the ex-date bar and later are
        # already at the post-bonus price (factor 1).
        dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
        action = _action(date(2026, 1, 2), Decimal("0.5"))
        factors = compute_adjustment_factors(dates, [action])
        assert factors[date(2026, 1, 1)] == Decimal("0.5")
        assert factors[date(2026, 1, 2)] == Decimal("1")
        assert factors[date(2026, 1, 3)] == Decimal("1")

    def test_multiple_actions_compound_multiplicatively(self) -> None:
        # Two bonuses: a 1:1 (ratio 0.5) on 2026-01-05, and an earlier 1:4
        # (ratio 0.8) on 2026-01-10. A bar before both ex-dates carries the
        # product of both ratios.
        dates = [date(2026, 1, 1)]
        actions = [
            _action(date(2026, 1, 5), Decimal("0.5")),
            _action(date(2026, 1, 10), Decimal("0.8")),
        ]
        factors = compute_adjustment_factors(dates, actions)
        assert factors[date(2026, 1, 1)] == Decimal("0.5") * Decimal("0.8")

    def test_unparseable_action_ratio_none_is_skipped_not_guessed(self) -> None:
        # A dividend or unrecognized action (ratio=None) must never
        # contribute to the factor -- it is disclosed but not adjusted.
        dates = [date(2026, 1, 1), date(2026, 1, 3)]
        action = _action(date(2026, 1, 2), None, action_type="dividend")
        factors = compute_adjustment_factors(dates, [action])
        assert factors == {date(2026, 1, 1): Decimal("1"), date(2026, 1, 3): Decimal("1")}


class TestParseCorporateActionRatio:
    """Golden tests for the conservative NSE subject-line parser."""

    def test_bonus_one_for_one(self) -> None:
        action_type, ratio = _parse_corporate_action_ratio("Bonus 1:1")
        assert action_type == "bonus"
        assert ratio == Decimal("1") / Decimal("2")

    def test_bonus_one_for_four(self) -> None:
        action_type, ratio = _parse_corporate_action_ratio("Bonus Issue Bonus 1:4")
        assert action_type == "bonus"
        assert ratio == Decimal("4") / Decimal("5")

    def test_face_value_split(self) -> None:
        action_type, ratio = _parse_corporate_action_ratio(
            "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
        )
        assert action_type == "split"
        assert ratio == Decimal("2") / Decimal("10")

    def test_face_value_split_to_singular_re(self) -> None:
        # NSE writes the singular rupee as "Re 1", not "Rs 1". The pattern must
        # accept it, or the most common split of all is silently unadjusted.
        action_type, ratio = _parse_corporate_action_ratio(
            "Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per Share"
        )
        assert action_type == "split"
        assert ratio == Decimal("1") / Decimal("5")

    def test_combined_bonus_and_split_legs_compound(self) -> None:
        # TITAN, ex-date 2011-06-23. The bonus leg alone (0.5) left a -89%
        # step in the adjusted series; the true factor is 0.5 * 0.1 = 0.05,
        # matching the observed close move 4292.45 -> 228.90.
        action_type, ratio = _parse_corporate_action_ratio(
            "Bonus 1:1 / Face Value Split From Rs.10/- To Re.1/-"
        )
        assert action_type == "bonus"
        assert ratio == Decimal("0.05")

    def test_unusable_split_leg_voids_the_whole_ratio(self) -> None:
        # Adjusting by the bonus leg alone would corrupt every earlier bar.
        action_type, ratio = _parse_corporate_action_ratio(
            "Bonus 1:1 / Face Value Split From Rs 0/- To Re 1/-"
        )
        assert action_type == "bonus"
        assert ratio is None

    def test_unrecognized_subject_returns_ratio_none(self) -> None:
        action_type, ratio = _parse_corporate_action_ratio("Interim Dividend - Rs 5 Per Share")
        assert action_type == "other"
        assert ratio is None

    def test_rights_issue_not_guessed(self) -> None:
        # Rights issues have a price-dilution effect too, but this parser
        # deliberately does not attempt to resolve one -- disclosed as
        # ratio=None rather than guessed.
        action_type, ratio = _parse_corporate_action_ratio("Rights 1:3 @ Rs 100")
        assert action_type == "other"
        assert ratio is None
