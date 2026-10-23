"""The read contract MF data publishes to other contexts (ADR-017 MF-5, MF-11).

Analytics reads plan-options and NAV history through :class:`MfReader` only. Every
read names the revision it reads at, so a screen, its metrics and its chart come
from the same data while a refresh publishes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import date
from typing import Protocol


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
class History:
    """Every plan-option's series at ``revision``, streamed one fund at a time."""

    revision: int
    as_of: date
    sources: tuple[str, ...]
    funds: AsyncIterator[FundSeries]


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
