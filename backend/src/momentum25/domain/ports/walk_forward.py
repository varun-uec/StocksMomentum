"""Ports the walk-forward runner drives.

These are the seam between the frozen backtest math (``domain/backtest/``) and
real, point-in-time historical data.

Each port carries an explicit ``as_of`` decision date. The contract every
implementation must honour is the single rule of ``handoff/brief.md`` §9: no
information dated on or after the decision date may influence that rebalance.
The runner does not trust a provider to obey this — it re-checks the date on
every price it receives (see ``application/use_cases/walk_forward.py``).

Implementations live in ``infrastructure/`` (real, DB/NSE-backed) or in tests
(deterministic fakes). None live here: this module is pure abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from momentum25.domain.backtest.eligibility import EligibilityFacts


@dataclass(frozen=True, slots=True)
class PricePoint:
    """An adjusted close together with the exact session date it came from.

    ``as_of`` enforcement depends on the caller being able to see *which*
    session a price is from, not just its value. A provider that returns a
    price without its date makes look-ahead undetectable.
    """

    security_id: int
    session_date: date
    adj_close: Decimal


@runtime_checkable
class PriceHistoryProvider(Protocol):
    """Point-in-time adjusted-close prices, corporate-action adjusted."""

    def price_on_or_before(
        self, security_id: int, target: date, as_of: date
    ) -> PricePoint | None:
        """Return the adjusted close on the latest session ``<= target``.

        The returned ``session_date`` must be ``<= as_of``. A provider must
        never reach past ``as_of`` even if ``target`` is later. Returns
        ``None`` when the security has no session on or before ``target``
        within the ``as_of`` horizon (e.g. not yet listed).
        """
        ...


@runtime_checkable
class EligibilityFactsProvider(Protocol):
    """Point-in-time universe as of a decision date.

    Answers who was a Nifty 500 constituent as of a date, with their listing
    age and surveillance status on that date.

    This is the survivorship-critical port. For a historical decision date it
    must return the constituents *as they were then* — including names later
    delisted, acquired, or dropped from the index — not today's list applied
    backward. If it can only answer with the current constituent list,
    checklist item 8 (survivorship) cannot pass.
    """

    def facts_as_of(self, decision_date: date) -> list[EligibilityFacts]:
        """Return one ``EligibilityFacts`` per candidate security as of the date."""
        ...


@runtime_checkable
class BenchmarkProvider(Protocol):
    """Benchmark index level (brief §8: Nifty 500 TRI) — reporting only."""

    def level_on_or_before(self, target: date, as_of: date) -> Decimal | None:
        """Return the benchmark level on the latest session ``<= target``.

        Same ``as_of`` discipline as :class:`PriceHistoryProvider`, though the
        benchmark never feeds selection — it is used only to report relative
        performance after the fact.
        """
        ...
