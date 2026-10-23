"""Compute snapshots and serve research reads over them (ADR-017 MF-11, MF-13).

Every read resolves one revision: the snapshot the caller pins, or the latest one.
Metrics, screens, fund detail, NAVs and comparisons all read at that revision. The
rights checks live here, not in HTTP, so every caller inherits them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from wickstreet.analytics.domain.fields import BY_ID, FIELDS, INDEX, registry_version, row_values
from wickstreet.analytics.domain.metrics import METHOD_VERSION, Missing, compute, rebase
from wickstreet.analytics.domain.screening import (
    FilterError,
    decode_cursor,
    encode_cursor,
    excluded_for_missing,
    fingerprint,
    parse_filter,
    parse_sort,
    screen,
)
from wickstreet.analytics.domain.snapshot import (
    Encoded,
    FundRow,
    Snapshot,
    SnapshotStore,
    encode,
)
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import Use
from wickstreet.mf_data.domain.reads import FundRecord, History, Link, MfReader, NavPoint

DEFAULT_COLUMNS = ("category", "plan", "option", "ret_1y", "cagr_3y", "cagr_5y", "vol_3y", "mdd_3y")
MAX_PAGE = 500
MAX_COMPARE = 5


class NoSnapshotError(LookupError):
    """No snapshot exists for the requested revision and method version."""


class UnknownFundError(LookupError):
    """No plan-option has this AMFI code at the revision."""


@dataclass(frozen=True, slots=True)
class ComputeOutcome:
    """What one compute call did: ``computed``, ``current`` or ``nothing_published``."""

    status: str
    revision: int | None
    snapshot_id: int | None = None
    funds: int = 0


class ComputeSnapshot:
    """Compute the snapshot of the published revision once (MF-11)."""

    @staticmethod
    async def encode(history: History) -> Encoded:
        """Every fund's fields at the history's revision, encoded; stores nothing."""
        as_of = history.as_of.toordinal()
        rows: list[FundRow] = []
        async for series in history.funds:
            fund = series.fund
            metrics = compute(series.points, as_of)
            rows.append(
                FundRow(
                    fund.plan_option_id,
                    fund.amfi_code,
                    fund.nav_name or fund.scheme_name or fund.amfi_code,
                    row_values(fund, metrics),
                    metrics.anchors,
                )
            )
        return encode(METHOD_VERSION, history.revision, history.as_of, history.sources, rows)

    def __init__(self, reader: MfReader, snapshots: SnapshotStore, rights: RightsGate) -> None:
        """Compute over ``reader`` into ``snapshots``, under ``rights``."""
        self._reader = reader
        self._snapshots = snapshots
        self._rights = rights

    async def execute(self) -> ComputeOutcome:
        """No-op when the published revision already has a snapshot."""
        pointer = await self._reader.pointer()
        if pointer is None:
            return ComputeOutcome("nothing_published", None)
        if await self._snapshots.exists(pointer, METHOD_VERSION):
            return ComputeOutcome("current", pointer)
        async with self._reader.history() as history:
            grants = [await self._rights.require(s, Use.DERIVED_METRICS) for s in history.sources]
            encoded = await self.encode(history)
        snapshot_id = await self._snapshots.insert(
            history.revision,
            METHOD_VERSION,
            history.as_of,
            history.sources,
            [g.id for g in grants],
            encoded,
        )
        status = "computed" if snapshot_id is not None else "current"
        return ComputeOutcome(status, history.revision, snapshot_id, encoded.funds)


@dataclass(frozen=True, slots=True)
class Envelope:
    """What every research response carries. ``latest_revision`` is live, not pinned."""

    data_revision: int
    latest_revision: int | None
    method_version: int
    as_of: date
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScreenRequest:
    """A screen as the caller sent it."""

    filter: Any = None
    sort: Sequence[Any] = ()
    columns: Sequence[str] | None = None
    size: int = 50
    after: str | None = None
    data_revision: int | None = None


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """One page of a screen."""

    envelope: Envelope
    total: int
    matched: int
    excluded_missing: list[dict[str, Any]]
    columns: tuple[str, ...]
    rows: list[FundRow]
    next: str | None


@dataclass(frozen=True, slots=True)
class FundDetail:
    """A plan-option's attributes at the revision, its metrics row and its links."""

    envelope: Envelope
    fund: FundRecord
    row: FundRow
    links: list[Link]


@dataclass(frozen=True, slots=True)
class Comparison:
    """Metrics of a few funds and their NAVs rebased to 100 at a common start."""

    envelope: Envelope
    start: date
    rows: list[FundRow]
    series: dict[str, list[tuple[str, float]]]


def _columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    chosen = tuple(columns) if columns is not None else DEFAULT_COLUMNS
    for i, column in enumerate(chosen):
        if column not in BY_ID:
            raise FilterError(f"columns[{i}]", f"unknown field {column!r}")
    return chosen


class Research:
    """Screens and fund reads at one pinned revision, gated on ``display``."""

    def __init__(self, reader: MfReader, snapshots: SnapshotStore, rights: RightsGate) -> None:
        """Read through ``reader`` and ``snapshots``, under ``rights``."""
        self._reader = reader
        self._snapshots = snapshots
        self._rights = rights

    async def _pinned(self, revision: int | None) -> tuple[Snapshot, Envelope]:
        snapshot = await self._snapshots.find(revision, METHOD_VERSION)
        if snapshot is None:
            pinned = "any revision" if revision is None else f"revision {revision}"
            raise NoSnapshotError(f"No method v{METHOD_VERSION} snapshot for {pinned}.")
        for source in snapshot.sources:
            await self._rights.require(source, Use.DISPLAY)
        envelope = Envelope(
            snapshot.revision,
            await self._reader.pointer(),
            snapshot.method_version,
            snapshot.as_of,
            snapshot.sources,
        )
        return snapshot, envelope

    @staticmethod
    def _row(snapshot: Snapshot, code: str) -> FundRow:
        row = snapshot.by_code.get(code)
        if row is None:
            raise UnknownFundError(f"No plan-option {code!r} at revision {snapshot.revision}.")
        return row

    async def fields(
        self, revision: int | None = None
    ) -> tuple[Envelope, str, list[dict[str, Any]]]:
        """The registry; an enum without fixed members lists the snapshot's values."""
        snapshot, envelope = await self._pinned(revision)
        listed = []
        for f in FIELDS:
            values = f.values
            if f.type == "enum" and values is None:
                index = INDEX[f.id]
                values = tuple(
                    sorted(
                        {v for r in snapshot.rows if isinstance(v := r.values[index], str) and v}
                    )
                )
            listed.append(
                {
                    "id": f.id,
                    "label": f.label,
                    "group": f.group,
                    "type": f.type,
                    "unit": f.unit,
                    "description": f.description,
                    **({"values": list(values)} if values is not None else {}),
                }
            )
        return envelope, registry_version(), listed

    async def screen(self, request: ScreenRequest) -> ScreenResult:
        """Evaluate a screen; a cursor keeps its pages on the snapshot it started on."""
        where = parse_filter(request.filter)
        sort = parse_sort(list(request.sort))
        columns = _columns(request.columns)
        if not 1 <= request.size <= MAX_PAGE:
            raise FilterError("page.size", f"size is 1 to {MAX_PAGE}")
        request_id = fingerprint(request.filter, list(request.sort))
        revision, offset = request.data_revision, 0
        if request.after is not None:
            revision, offset = decode_cursor(request.after, request_id)
            if request.data_revision not in (None, revision):
                raise FilterError("page.after", "cursor does not match this request")
        snapshot, envelope = await self._pinned(revision)
        matched = screen(snapshot.rows, where, sort)
        end = offset + request.size
        return ScreenResult(
            envelope=envelope,
            total=len(snapshot.rows),
            matched=len(matched),
            excluded_missing=excluded_for_missing(snapshot, where),
            columns=columns,
            rows=matched[offset:end],
            next=encode_cursor(snapshot.revision, request_id, end) if end < len(matched) else None,
        )

    async def search(
        self, query: str, limit: int, revision: int | None = None
    ) -> tuple[Envelope, list[tuple[FundRecord, FundRow | None]]]:
        """Plan-options by name, code or ISIN, with or without NAV history."""
        snapshot, envelope = await self._pinned(revision)
        found = await self._reader.search(query, limit, snapshot.revision)
        return envelope, [(f, snapshot.by_code.get(f.amfi_code)) for f in found]

    async def fund(self, code: str, revision: int | None = None) -> FundDetail:
        """One plan-option's attributes, metrics row and curated links."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        fund = await self._reader.fund(code, snapshot.revision)
        if fund is None:
            raise UnknownFundError(f"No plan-option {code!r} at revision {snapshot.revision}.")
        return FundDetail(envelope, fund, row, await self._reader.links(code))

    async def metrics(self, code: str, revision: int | None = None) -> tuple[Envelope, FundRow]:
        """Every field of one fund and its trailing anchors."""
        snapshot, envelope = await self._pinned(revision)
        return envelope, self._row(snapshot, code)

    async def navs(
        self, code: str, start: date, end: date, revision: int | None = None
    ) -> tuple[Envelope, list[NavPoint]]:
        """NAVs as filed at the pinned revision, with provenance."""
        snapshot, envelope = await self._pinned(revision)
        self._row(snapshot, code)
        return envelope, await self._reader.navs(code, start, end, snapshot.revision)

    async def compare(
        self, codes: Sequence[str], start: date | None, revision: int | None = None
    ) -> Comparison:
        """2 to 5 funds; ``start`` defaults to the latest first valid NAV among them."""
        if not 2 <= len(codes) <= MAX_COMPARE or len(set(codes)) != len(codes):
            raise FilterError("code", f"compare needs 2 to {MAX_COMPARE} distinct codes")
        snapshot, envelope = await self._pinned(revision)
        rows = [self._row(snapshot, code) for code in codes]
        if start is None:
            firsts = [r.values[INDEX["since_start"]] for r in rows]
            known = [date.fromisoformat(f) for f in firsts if isinstance(f, str)]
            start = max(known) if known else snapshot.as_of
        series = await self._reader.series(codes, snapshot.revision)
        rebased = {s.fund.amfi_code: rebase(s.points, start.toordinal()) for s in series}
        return Comparison(envelope, start, rows, rebased)


def cell(row: FundRow, field: str) -> Any:
    """A field's value, or ``None`` when it is missing."""
    value = row.values[INDEX[field]]
    return None if isinstance(value, Missing) else value


def state(row: FundRow, field: str) -> dict[str, str] | None:
    """A missing field's state and reason, or ``None`` when it has a value."""
    value = row.values[INDEX[field]]
    return {"state": value.state, "reason": value.reason} if isinstance(value, Missing) else None
