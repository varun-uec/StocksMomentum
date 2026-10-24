"""The read contract MF data publishes to other contexts (ADR-017 MF-5, MF-11).

Analytics reads plan-options and NAV history through :class:`MfReader` only. Every
read names the revision it reads at, so a screen, its metrics and its chart come
from the same data while a refresh publishes.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

# Common words investors type for a fund whose AMFI name says something else.
SEARCH_SYNONYMS = {"bluechip": ("largecap",), "elss": ("taxsaver",), "taxsaver": ("elss",)}


def compact(text: str) -> str:
    """``"Small-Cap Fund"`` → ``"smallcapfund"``: the form search terms match."""
    return "".join(search_terms(text))


def search_terms(query: str) -> list[str]:
    """``"SBI Small-cap"`` → ``["sbi", "small", "cap"]``.

    A term matches a fund whose name or AMC contains it, or one of its
    ``SEARCH_SYNONYMS``, once spaces and punctuation are removed, so ``smallcap``
    finds "Small Cap".
    """
    return re.findall(r"[a-z0-9]+", query.lower())


@dataclass(frozen=True, slots=True)
class FundRecord:
    """A plan-option and its attributes at one revision.

    ``plan`` and ``option`` are the columns of AMFI's NAV file, when it has them.
    """

    plan_option_id: int
    amfi_code: str
    amc: str | None
    scheme_name: str | None
    nav_name: str | None
    scheme_type: str | None
    category: str | None
    plan: str | None
    option: str | None
    isin_growth: str | None
    isin_reinvest: str | None
    launch_date: date | None


@dataclass(frozen=True, slots=True)
class FundSeries:
    """One plan-option and its NAV history in date order.

    Each point is (date ordinal, NAV as float or ``None``, anomaly flag or ``None``).
    Ordinals keep the metric loop cheap over 22M points.
    """

    fund: FundRecord
    points: Sequence[tuple[int, float | None, str | None]]


@dataclass(frozen=True, slots=True)
class FactPoint:
    """One filed scheme fact (doc 21 E1, E3): a number or a text, in force from ``day``."""

    day: int
    num: float | None
    txt: str | None


# Facts read as a series in the snapshot pass; every other fact is read at its latest.
SERIES_FACTS = ("ter", "aum_cr")


@dataclass(frozen=True, slots=True)
class HoldingRow:
    """One filed line of a portfolio; ``weight`` is a fraction of net assets."""

    name: str
    isin: str | None
    industry: str | None
    section: str
    asset: str
    weight: float
    value: float | None = None


@dataclass(frozen=True, slots=True)
class Portfolio:
    """One scheme's portfolio on one disclosure date."""

    as_of: date
    rows: Sequence[HoldingRow]


@dataclass(frozen=True, slots=True)
class FactView:
    """Scheme facts at one revision, joined to plan-options through their ISINs.

    ``latest`` and ``series`` are keyed by scheme id, then by (fact name, plan), where
    plan is ``""`` for the whole scheme, else ``"regular"`` or ``"direct"``.
    """

    scheme_of: Mapping[int, int] = field(default_factory=dict)
    latest: Mapping[int, Mapping[tuple[str, str], FactPoint]] = field(default_factory=dict)
    series: Mapping[int, Mapping[tuple[str, str], Sequence[FactPoint]]] = field(
        default_factory=dict
    )
    # Each scheme's latest portfolio, and each ISIN's market-cap classes by period end.
    portfolios: Mapping[int, Portfolio] = field(default_factory=dict)
    caps: Mapping[str, Sequence[tuple[date, str]]] = field(default_factory=dict)
    # Each plan-option's IDCW payouts as (record-date ordinal, ₹ per unit), in date order.
    distributions: Mapping[int, Sequence[tuple[int, float]]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SchemeFactRow:
    """One visible fact of one scheme, for a fund's profile."""

    name: str
    plan: str
    as_of: date
    num: float | None
    txt: str | None


@dataclass(frozen=True, slots=True)
class SchemeProfile:
    """A plan-option's AMFI scheme and every fact visible for it at a revision."""

    sd_id: int
    scheme_name: str
    facts: Sequence[SchemeFactRow]
    # This plan-option's IDCW payouts as (record date, ₹ per unit), oldest first.
    payouts: Sequence[tuple[date, float]] = ()


@dataclass(frozen=True, slots=True)
class SchemePortfolios:
    """Every visible portfolio of a plan-option's scheme, oldest first, and the cap classes."""

    sd_id: int
    scheme_name: str
    portfolios: Sequence[Portfolio]
    caps: Mapping[str, Sequence[tuple[date, str]]]


@dataclass(frozen=True, slots=True)
class History:
    """Every plan-option's series at ``revision``, streamed one fund at a time."""

    revision: int
    as_of: date
    sources: tuple[str, ...]
    funds: AsyncIterator[FundSeries]
    # The 91-day T-bill yield as (date ordinal, % a year), in date order; empty if none.
    risk_free: Sequence[tuple[int, float]] = ()
    facts: FactView = field(default_factory=FactView)


@dataclass(frozen=True, slots=True)
class NavPoint:
    """One NAV as filed, with the source and revision it came from."""

    nav_date: date
    nav: str | None
    anomaly: str | None
    source: str
    revision: int


@dataclass(frozen=True, slots=True)
class Link:
    """A curated link between two plan-options (MF-3); never inferred."""

    from_code: str
    to_code: str
    kind: str
    effective_date: date
    evidence: str


class MfReader(Protocol):
    """Port: read MF data at an explicit revision."""

    async def pointer(self) -> int | None:
        """Return the published revision, or ``None`` before the first publish."""
        ...

    def history(self) -> AbstractAsyncContextManager[History]:
        """Open one consistent read of every series at the published revision."""
        ...

    async def sources(self, revision: int) -> tuple[str, ...]:
        """Return the sources whose revisions are visible at ``revision``."""
        ...

    async def search(self, query: str, limit: int, revision: int) -> list[FundRecord]:
        """Find plan-options by name, AMFI code or ISIN."""
        ...

    async def fund(self, code: str, revision: int) -> FundRecord | None:
        """Return one plan-option by AMFI code."""
        ...

    async def navs(self, code: str, start: date, end: date, revision: int) -> list[NavPoint]:
        """Return the NAVs of one plan-option in ``[start, end]``."""
        ...

    async def series(self, codes: Sequence[str], revision: int) -> list[FundSeries]:
        """Return the full series of a few plan-options."""
        ...

    async def links(self, code: str) -> list[Link]:
        """Return the curated links from or to one plan-option."""
        ...

    async def rates(self, series: str, revision: int) -> list[tuple[date, float]]:
        """Return one rate series at ``revision``, in date order."""
        ...

    async def scheme_profile(self, code: str, revision: int) -> SchemeProfile | None:
        """Return the scheme a plan-option belongs to and every fact visible for it."""
        ...

    async def scheme_portfolios(self, code: str, revision: int) -> SchemePortfolios | None:
        """Return every visible portfolio of the plan-option's scheme."""
        ...
