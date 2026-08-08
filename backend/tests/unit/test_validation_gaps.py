"""Unit tests for RP-012 C1 (inferred corporate actions) and C2 (survivorship gaps)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from momentum25.domain.research.validation_gaps import (
    DEFAULT_GAP_SESSION_THRESHOLD,
    detect_gap_event,
    infer_action_event,
)


class TestInferAction:
    def test_no_action_near_unity(self) -> None:
        event = infer_action_event(
            symbol="X",
            session_date=date(2020, 1, 2),
            prev_close_reported=Decimal("100.00"),
            prior_session_close=Decimal("100.00"),
        )
        assert event is not None
        assert not event.flagged
        assert event.inferred_factor == Decimal("1")

    def test_split_flagged(self) -> None:
        # 10:1 split — reported prevclose is one-tenth of the actual prior close.
        event = infer_action_event(
            symbol="X",
            session_date=date(2020, 1, 2),
            prev_close_reported=Decimal("10"),
            prior_session_close=Decimal("100"),
        )
        assert event is not None
        assert event.flagged
        assert event.inferred_factor == Decimal("0.1")

    def test_none_when_missing_inputs(self) -> None:
        assert (
            infer_action_event(
                symbol="X",
                session_date=date(2020, 1, 2),
                prev_close_reported=None,
                prior_session_close=Decimal("100"),
            )
            is None
        )

    def test_none_when_prior_non_positive(self) -> None:
        assert (
            infer_action_event(
                symbol="X",
                session_date=date(2020, 1, 2),
                prev_close_reported=Decimal("100"),
                prior_session_close=Decimal("0"),
            )
            is None
        )


class TestGapDetection:
    def test_within_threshold_no_event(self) -> None:
        assert (
            detect_gap_event(
                symbol="X",
                last_seen_date=date(2020, 1, 1),
                current_date=date(2020, 1, 10),
                gap_sessions=DEFAULT_GAP_SESSION_THRESHOLD,
            )
            is None
        )

    def test_beyond_threshold_event(self) -> None:
        event = detect_gap_event(
            symbol="X",
            last_seen_date=date(2020, 1, 1),
            current_date=date(2020, 2, 1),
            gap_sessions=DEFAULT_GAP_SESSION_THRESHOLD + 1,
        )
        assert event is not None
        assert event.gap_sessions == DEFAULT_GAP_SESSION_THRESHOLD + 1
        assert event.last_seen_date == date(2020, 1, 1)
