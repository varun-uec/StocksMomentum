"""Ports of the MF data context."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from wickstreet.mf_data.domain.model import Anomaly, NavRecord, RawFile, SchemeRecord


class SourceLayoutError(Exception):
    """The source file is not in the layout the adapter knows; nothing is published."""


class SourceError(Exception):
    """The source could not be reached or refused the request after every retry."""


class SchemeSource(Protocol):
    """A supplier of a scheme master, converted to ``schemes-v1``."""

    name: str
    adapter_version: str

    async def scheme_master(self) -> RawFile:
        """Fetch the scheme master."""
        ...

    def parse_schemes(self, raw: RawFile) -> list[SchemeRecord]:
        """Convert the master to ``schemes-v1`` records, or raise :class:`SourceLayoutError`."""
        ...


class NavSource(SchemeSource, Protocol):
    """A supplier of one NAV file per date, and the scheme master."""

    async def nav_day(self, day: date) -> RawFile | None:
        """Fetch every NAV filed for ``day``; ``None`` when the source does not serve it."""
        ...

    def parse_nav(self, raw: RawFile) -> list[NavRecord]:
        """Convert a NAV file to ``nav-v1`` records, or raise :class:`SourceLayoutError`."""
        ...


class ArchiveSource(SchemeSource, Protocol):
    """A supplier of a whole NAV history in one file, and its scheme master."""

    async def archive(self) -> RawFile:
        """Fetch the archive."""
        ...

    def parse_archive(
        self, raw: RawFile, start: date, end: date
    ) -> Iterator[tuple[date, list[NavRecord]]]:
        """Yield the archive's NAVs in ``[start, end]`` one date at a time, in date order."""
        ...


class ReferenceSource(Protocol):
    """A supplier of one plan-option's NAV history, used to cross-check the store."""

    name: str
    adapter_version: str

    async def history(self, amfi_code: str) -> RawFile:
        """Fetch the history of one code."""
        ...

    def parse_history(self, raw: RawFile) -> dict[date, Decimal | None]:
        """Convert a history to NAVs by date, or raise :class:`SourceLayoutError`."""
        ...


class RawStore(Protocol):
    """Keeps every fetched file, outside the repository (ADR-022 §2.11)."""

    def save(self, source: str, dataset: str, period: date, raw: RawFile) -> str:
        """Store ``raw`` and return where it is."""
        ...

    def load(self, path: str) -> bytes:
        """Return the content stored at ``path``."""
        ...


@dataclass(frozen=True, slots=True)
class Run:
    """The durable record of one source, dataset and period (MF-10)."""

    id: int
    status: str
    raw_sha256: str | None


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a published revision came from (MF-9)."""

    url: str
    fetched_at_iso: str
    raw_sha256: str
    raw_path: str
    adapter_version: str
    contract: str
    retrieval_grant_id: int
    storage_grant_id: int


@dataclass(frozen=True, slots=True)
class StoredRaw:
    """A published revision's raw file, as recorded (MF-9)."""

    url: str
    fetched_at: datetime
    sha256: str
    path: str


@dataclass(frozen=True, slots=True)
class Published:
    """What one publication changed. ``revision`` is ``None`` when nothing changed.

    ``conflicts`` counts filled values that differ from a stored value they did not
    replace.
    """

    revision: int | None
    inserted: int
    superseded: int
    conflicts: int = 0


class MfStore(Protocol):
    """The MF database. Each ``publish_*`` call is one transaction (MF-6)."""

    def exclusive(self) -> AbstractAsyncContextManager[bool]:
        """Hold the ingestion lock; yields ``False`` when another runner holds it."""
        ...

    async def open_run(self, source: str, dataset: str, start: date, end: date) -> Run:
        """Return the period's run, creating it when it is new."""
        ...

    async def close_run(
        self, run_id: int, status: str, *, raw_sha256: str | None = None, error: str | None = None
    ) -> None:
        """Record a run outcome that published nothing."""
        ...

    async def previous_navs(self, day: date) -> Mapping[str, Decimal]:
        """Each code's latest positive current NAV in the month before ``day``."""
        ...

    async def publish_navs(
        self,
        run_id: int,
        records: Sequence[NavRecord],
        anomalies: Mapping[tuple[str, date], Anomaly],
        provenance: Provenance,
        *,
        fill_only: bool = False,
    ) -> Published:
        """Write changed NAVs as a new revision and move the pointer, atomically.

        ``anomalies`` is keyed by code and date. With ``fill_only`` a record is
        written only where no current value exists; it never supersedes one.
        """
        ...

    async def publish_schemes(
        self,
        run_id: int,
        snapshot: date,
        records: Sequence[SchemeRecord],
        provenance: Provenance,
        *,
        fill_only: bool = False,
    ) -> Published:
        """Write changed master attributes as a new revision, atomically.

        With ``fill_only`` only codes that have no master row yet are written.
        """
        ...

    async def last_nav_day(self) -> date | None:
        """The latest AMFI NAV date with a published or unchanged run."""
        ...

    async def run_status(self, source: str, dataset: str, day: date) -> str | None:
        """Status of the run for one single-date period, if it exists."""
        ...

    async def stored_raw(self, run_id: int) -> StoredRaw | None:
        """Where the run's last published revision came from, if it has one."""
        ...

    async def first_nav_day(self, source: str) -> date | None:
        """The earliest single-date NAV run of ``source`` that published or was unchanged."""
        ...

    async def current_navs(
        self, amfi_code: str, start: date, end: date
    ) -> dict[date, Decimal | None]:
        """One code's current NAVs in ``[start, end]``."""
        ...
