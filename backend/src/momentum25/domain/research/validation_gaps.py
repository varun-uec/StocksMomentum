"""Validation-gap detection (RP-012 research conditions C1 / C2).

Two pure, I/O-free detectors whose *mechanism* must exist and be tested before
Phase 3's deep 1994–2019 backfill, even though the short 2019–2024 overlap
window is expected to trigger few or none of them:

* **C1 — PREVCLOSE-inferred corporate-action factor.** The legacy bhavcopy
  reports ``PREVCLOSE``, which NSE already adjusts for a corporate action on
  its ex-date. Dividing the reported ``PREVCLOSE`` by the *actual* prior-session
  close therefore yields an implied price-adjustment factor. A factor materially
  different from 1.0 signals an inferred split/bonus/adjustment that must be
  reconciled against NSE's corporate-actions API (once re-probed). We never
  *apply* an inferred factor to price history here — inference is logged for
  later reconciliation, never silently trusted (mirrors the adapter's rule that
  a guessed ratio is worse than a disclosed gap).

* **C2 — survivorship / gap detection.** When a security that was trading stops
  appearing in the daily EQ set for longer than a session-count threshold, a gap
  event is recorded (security, last-seen date, gap length). This does not by
  itself classify a delisting — the short overlap window rarely warrants that —
  but the logging mechanism is exercised now so Phase 3 can rely on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# C1: an inferred factor outside this symmetric band around 1.0 is "large"
# enough to warrant later reconciliation. A 5% band comfortably ignores the
# ordinary tick-level rounding between PREVCLOSE and the prior close while
# catching every real split/bonus (which move the factor by tens of percent).
INFERRED_FACTOR_LOW: Decimal = Decimal("0.95")
INFERRED_FACTOR_HIGH: Decimal = Decimal("1.05")

# C2: a security absent for more than this many consecutive expected sessions
# is flagged as a gap event (not necessarily a delisting).
DEFAULT_GAP_SESSION_THRESHOLD: int = 5


@dataclass(frozen=True, slots=True)
class InferredActionEvent:
    """A PREVCLOSE-inferred corporate-action adjustment factor for one session."""

    symbol: str
    session_date: date
    prev_close_reported: Decimal
    prior_session_close: Decimal
    inferred_factor: Decimal
    flagged: bool


@dataclass(frozen=True, slots=True)
class SurvivorshipGapEvent:
    """A detected trading gap for a security (C2)."""

    symbol: str
    last_seen_date: date
    detected_on_date: date
    gap_sessions: int


def infer_action_event(
    *,
    symbol: str,
    session_date: date,
    prev_close_reported: Decimal | None,
    prior_session_close: Decimal | None,
) -> InferredActionEvent | None:
    """Infer a corporate-action factor from a session's reported PREVCLOSE.

    Returns ``None`` — never a fabricated factor — when either input is missing
    or the prior close is non-positive (an inference would be meaningless). The
    returned event's ``flagged`` marks whether the inferred factor falls outside
    the tolerance band and therefore needs reconciliation.
    """
    if prev_close_reported is None or prior_session_close is None:
        return None
    if prior_session_close <= 0:
        return None
    factor = prev_close_reported / prior_session_close
    flagged = factor < INFERRED_FACTOR_LOW or factor > INFERRED_FACTOR_HIGH
    return InferredActionEvent(
        symbol=symbol,
        session_date=session_date,
        prev_close_reported=prev_close_reported,
        prior_session_close=prior_session_close,
        inferred_factor=factor,
        flagged=flagged,
    )


def detect_gap_event(
    *,
    symbol: str,
    last_seen_date: date,
    current_date: date,
    gap_sessions: int,
    threshold: int = DEFAULT_GAP_SESSION_THRESHOLD,
) -> SurvivorshipGapEvent | None:
    """Return a gap event when a security's absence exceeds ``threshold`` sessions.

    ``gap_sessions`` is the number of expected trading sessions that elapsed
    between ``last_seen_date`` and ``current_date`` in which the security did not
    appear. Returns ``None`` when the gap is within tolerance (an ordinary
    non-trading stretch such as a suspension of a few sessions).
    """
    if gap_sessions <= threshold:
        return None
    return SurvivorshipGapEvent(
        symbol=symbol,
        last_seen_date=last_seen_date,
        detected_on_date=current_date,
        gap_sessions=gap_sessions,
    )
