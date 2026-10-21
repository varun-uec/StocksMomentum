"""The reference equity universe (IMPLEMENTATION_SPEC §8, engine v2).

One definition, shared by the screener, RS ratings and the walk-forward
backtest. Strategy eligibility (price, turnover, history, staleness) and the
backtest brief's eligibility apply after it and never change it. Its version is
``REFERENCE_UNIVERSE_VERSION`` in ``domain/engine_version.py``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.instrument import is_equity

# A dual-listed company is one ``BOTH`` row that carries its NSE print
# (``domain/research/cross_listing.py`` rule 1). BSE-only names are not
# admitted (same module, rule 3).
REFERENCE_EXCHANGES = frozenset({"NSE", "BOTH"})


def in_reference_universe(
    exchange: str,
    isin: str | None,
    listing_date: date | None,
    delisting_date: date | None,
    on: date,
) -> bool:
    """Return whether a security belongs to the reference universe on ``on``.

    Point in time: listed on or before ``on`` (an unknown listing date is not
    evidence of a later listing) and not delisted by ``on``. Today's active
    flag is never an input.
    """
    return (
        str(exchange) in REFERENCE_EXCHANGES
        and is_equity(isin or None)
        and (listing_date is None or listing_date <= on)
        and (delisting_date is None or delisting_date > on)
    )


def reference_universe_exclusion(
    exchange: str,
    isin: str | None,
    listing_date: date | None,
    delisting_date: date | None,
    on: date,
) -> str | None:
    """Say in one sentence why a security is outside the reference universe, or ``None``.

    The tests are the ones of :func:`in_reference_universe`, in the same order.
    """
    if str(exchange) not in REFERENCE_EXCHANGES:
        return (
            f"it is listed on {exchange} only; the screening universe holds NSE and "
            "dual-listed equities"
        )
    if not is_equity(isin or None):
        return "it is a fund or ETF unit; the screening universe holds equities only"
    if listing_date is not None and listing_date > on:
        return f"it lists on {listing_date.isoformat()}, after {on.isoformat()}"
    if delisting_date is not None and delisting_date <= on:
        return f"it was delisted on {delisting_date.isoformat()}"
    return None


def reference_universe(securities: Iterable[Security], on: date) -> list[Security]:
    """The securities of ``securities`` in the reference universe on ``on``, in input order."""
    return [
        s
        for s in securities
        if in_reference_universe(s.exchange, s.isin, s.listing_date, s.delisting_date, on)
    ]
