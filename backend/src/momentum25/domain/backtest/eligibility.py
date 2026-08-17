"""Universe eligibility — brief §1.

Known limitation: T2T-segment and ASM/surveillance status are not backed by
any data source in this codebase today (verified: no ingestion adapter for
either exists in infrastructure/). ``EligibilityFacts`` models both fields
so the rule is correct once that data exists; until then, callers that don't
have the data must pass ``is_t2t=False, is_under_surveillance=False``
explicitly and are responsible for documenting that gap at the call site.
This module does not fabricate or default-assume clean status silently for
data it never received.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_LISTING_DAYS = 252  # ~12 months of trading days


@dataclass(frozen=True, slots=True)
class EligibilityFacts:
    """Point-in-time facts needed to decide eligibility for one security."""

    security_id: int
    listing_days_as_of_decision_date: int
    is_t2t: bool
    is_under_surveillance: bool
    in_nifty_500: bool


def is_eligible(facts: EligibilityFacts) -> bool:
    """Apply brief §1: Nifty 500 membership, >=12mo history, no T2T/ASM."""
    return (
        facts.in_nifty_500
        and facts.listing_days_as_of_decision_date >= _MIN_LISTING_DAYS
        and not facts.is_t2t
        and not facts.is_under_surveillance
    )
