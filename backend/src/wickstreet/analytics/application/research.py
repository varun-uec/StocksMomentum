"""Compute snapshots and serve research reads over them (ADR-017 MF-11, MF-13).

Every read resolves one revision: the snapshot the caller pins, or the latest one.
Metrics, screens, fund detail, NAVs and comparisons all read at that revision. The
rights checks live here, not in HTTP, so every caller inherits them.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from wickstreet.analytics.domain import calculators, views
from wickstreet.analytics.domain.calculators import Outcome
from wickstreet.analytics.domain.classify import (
    CAUTION,
    NAV_EXCLUDING_PAYOUTS,
    UNCLASSIFIED,
    sibling_categories,
)
from wickstreet.analytics.domain.fields import (
    FIELDS,
    INDEX,
    Field,
    attributes,
    ordered,
    registry_version,
)
from wickstreet.analytics.domain.formulas import compile_formulas, with_formulas
from wickstreet.analytics.domain.metrics import (
    ACTIVE,
    METHOD_VERSION,
    METRIC_FIELDS,
    NO_PEER_GROUP,
    Missing,
    Value,
    compute,
    rebase,
)
from wickstreet.analytics.domain.peers import (
    RANKED_INPUTS,
    PeerFund,
    absent_fields,
    add_group_fields,
    group_absence,
)
from wickstreet.analytics.domain.screening import (
    REGISTRY,
    Columns,
    FilterError,
    Group,
    decode_cursor,
    encode_cursor,
    excluded_for_missing,
    fingerprint,
    parse_filter,
    parse_sort,
    relaxations,
    resolve,
    screen,
)
from wickstreet.analytics.domain.snapshot import (
    Encoded,
    Encoder,
    FundRow,
    Snapshot,
    SnapshotStore,
)
from wickstreet.analytics.domain.tax import (
    GRANDFATHER_BEFORE,
    TAX_CLASSES,
    TaxResult,
    capital_gains_tax,
    tax_class_of,
)
from wickstreet.analytics.domain.views import correlation
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import Use
from wickstreet.mf_data.domain.reads import (
    FundRecord,
    FundSeries,
    History,
    Link,
    MfReader,
    NavPoint,
)

DEFAULT_COLUMNS = ("category", "plan", "option", "ret_1y", "cagr_3y", "cagr_5y", "vol_3y", "mdd_3y")
MAX_PAGE = 500
MAX_COMPARE = 5
# Funds computed between two turns of the event loop.
_YIELD_EVERY = 256


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


async def _turn(count: int) -> None:
    """Give the event loop a turn every ``_YIELD_EVERY`` funds; much of the work has no I/O."""
    if count % _YIELD_EVERY == 0:
        await asyncio.sleep(0)


class ComputeSnapshot:
    """Compute the snapshot of the published revision once (MF-11)."""

    @staticmethod
    async def encode(history: History) -> Encoded:
        """Every fund's fields at the history's revision, encoded; stores nothing.

        Pass 1 computes each fund's own metrics from its stream. Pass 2 sets sibling
        categories and the cross-fund fields (ranks, consistency, score). Pass 3
        streams the rows through the encoder in plan-option order. The loop gets a
        turn every ``_YIELD_EVERY`` funds, so requests keep moving.
        """
        as_of = history.as_of.toordinal()
        records: list[FundRecord] = []
        own: list[tuple[tuple[Value, ...], dict[str, str]]] = []
        # Month-end rolling 3Y of active funds only; no other fund joins a group.
        monthly: dict[int, tuple[Sequence[int], Sequence[float]]] = {}
        async for series in history.funds:
            metrics = compute(series.points, as_of)
            records.append(series.fund)
            own.append((tuple(metrics.values[n] for n in METRIC_FIELDS), metrics.anchors))
            if metrics.values["status"] == ACTIVE:
                monthly[series.fund.plan_option_id] = (metrics.month_ends, metrics.rolling_3y)
            await _turn(len(records))
        siblings = sibling_categories(records)
        status_at, input_at = (
            METRIC_FIELDS.index("status"),
            [METRIC_FIELDS.index(n) for n in RANKED_INPUTS],
        )
        classes: list[dict[str, Value]] = []
        groups: dict[tuple[str, str, str], list[PeerFund]] = defaultdict(list)
        grouped: dict[int, PeerFund] = {}
        for fund, (metric_values, _) in zip(records, own, strict=True):
            values = attributes(fund, siblings.get(fund.plan_option_id))
            classes.append(values)
            status = str(metric_values[status_at])
            if group_absence(status, str(values["category"]), UNCLASSIFIED) is None:
                month_ends, rolling_3y = monthly[fund.plan_option_id]
                inputs = {n: metric_values[i] for n, i in zip(RANKED_INPUTS, input_at, strict=True)}
                peer = PeerFund(inputs, month_ends, rolling_3y)
                groups[
                    (str(values["category"]), str(values["plan"]), str(values["option"]))
                ].append(peer)
                grouped[fund.plan_option_id] = peer
            await _turn(len(classes))
        monthly.clear()
        for members in groups.values():
            add_group_fields(members)
            await asyncio.sleep(0)
        encoder = Encoder(METHOD_VERSION, history.revision, history.as_of, history.sources)
        for done, i in enumerate(
            sorted(range(len(records)), key=lambda i: records[i].plan_option_id)
        ):
            fund, values = records[i], classes[i]
            metric_values, anchors = own[i]
            values |= dict(zip(METRIC_FIELDS, metric_values, strict=True))
            found = grouped.get(fund.plan_option_id)
            if found is None:
                absent = group_absence(str(values["status"]), str(values["category"]), UNCLASSIFIED)
                values |= absent_fields(absent or Missing("NA", NO_PEER_GROUP))
            else:
                values |= found.values
            encoder.add(
                FundRow(
                    fund.plan_option_id,
                    fund.amfi_code,
                    fund.nav_name or fund.scheme_name or fund.amfi_code,
                    ordered(values),
                    anchors,
                )
            )
            await _turn(done + 1)
        return encoder.finish()

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
    # Name -> expression; each name can be filtered, sorted and shown like a field.
    formulas: Mapping[str, str] = field(default_factory=dict)


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
    # The filter with percentile thresholds bound, for per-row explanations.
    where: Group | None
    # When nothing matches: how many would match without each top-level part.
    relaxations: list[dict[str, Any]]
    # Field id -> position in the rows' values, formulas included.
    index: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FundDetail:
    """A plan-option's attributes at the revision, its metrics row and its links."""

    envelope: Envelope
    fund: FundRecord
    row: FundRow
    links: list[Link]


@dataclass(frozen=True, slots=True)
class Comparison:
    """Metrics of a few funds, their NAVs rebased to 100 at a common start, and correlations."""

    envelope: Envelope
    start: date
    rows: list[FundRow]
    series: dict[str, list[tuple[str, float]]]
    correlations: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Simulated:
    """A calculator's result with its tax estimate."""

    envelope: Envelope
    outcome: Outcome
    tax: TaxResult
    tax_class: str | None
    cautions: list[str]


SIMULATIONS = ("sip", "lumpsum", "swp", "stp")
ROLLING_WINDOWS = {"1y": 12, "3y": 36, "5y": 60}


def _columns(columns: Sequence[str] | None, known: Columns) -> tuple[str, ...]:
    chosen = tuple(columns) if columns is not None else DEFAULT_COLUMNS
    for i, column in enumerate(chosen):
        if column not in known:
            raise FilterError(f"columns[{i}]", f"unknown field {column!r}")
    return chosen


class Research:
    """Screens and fund reads at one pinned revision, gated on ``display``."""

    def __init__(self, reader: MfReader, snapshots: SnapshotStore, rights: RightsGate) -> None:
        """Read through ``reader`` and ``snapshots``, under ``rights``."""
        self._reader = reader
        self._snapshots = snapshots
        self._rights = rights

    async def warm(self) -> None:
        """Decode the latest snapshot now, so the first request after a compute does not wait."""
        await self._snapshots.find(None, METHOD_VERSION)

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
            reasons = snapshot.missing[f.id]
            available = sum(reasons.values()) < len(snapshot.rows)
            listed.append(
                {
                    "id": f.id,
                    "label": f.label,
                    "group": f.group,
                    "type": f.type,
                    "unit": f.unit,
                    "description": f.description,
                    **({"values": list(values)} if values is not None else {}),
                    "available": available,
                    **(
                        {}
                        if available
                        else {"reason": min(reasons, key=lambda k: (-reasons[k], k))}
                    ),
                }
            )
        return envelope, registry_version(), listed

    async def screen(self, request: ScreenRequest) -> ScreenResult:
        """Evaluate a screen; a cursor keeps its pages on the snapshot it started on."""
        # Validate everything before any read; formula positions are set after the read.
        known: Columns = dict(REGISTRY) | {
            name: (Field(name, name, "Formula", "number", None, request.formulas[name]), -1)
            for name in compile_formulas(request.formulas)
        }
        where = parse_filter(request.filter, known)
        sort = parse_sort(list(request.sort), known)
        columns = _columns(request.columns, known)
        if not 1 <= request.size <= MAX_PAGE:
            raise FilterError("page.size", f"size is 1 to {MAX_PAGE}")
        request_id = fingerprint(request.filter, list(request.sort), dict(request.formulas))
        revision, offset = request.data_revision, 0
        if request.after is not None:
            revision, offset = decode_cursor(request.after, request_id)
            if request.data_revision not in (None, revision):
                raise FilterError("page.after", "cursor does not match this request")
        snapshot, envelope = await self._pinned(revision)
        rows, known, formula_missing = with_formulas(snapshot.rows, request.formulas)
        # Parse again against the real formula positions.
        where = resolve(parse_filter(request.filter, known), rows)
        sort = parse_sort(list(request.sort), known)
        matched = screen(rows, where, sort)
        end = offset + request.size
        return ScreenResult(
            envelope=envelope,
            total=len(rows),
            matched=len(matched),
            excluded_missing=excluded_for_missing(snapshot.missing | formula_missing, where),
            columns=columns,
            rows=matched[offset:end],
            next=encode_cursor(snapshot.revision, request_id, end) if end < len(matched) else None,
            where=where,
            relaxations=relaxations(rows, where) if not matched else [],
            index={name: position for name, (_, position) in known.items()},
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
        since = start.toordinal()
        windows = {s.fund.amfi_code: [p for p in s.points if p[0] >= since] for s in series}
        correlations = []
        for i, a in enumerate(codes):
            for b in codes[i + 1 :]:
                value, observations = correlation(windows.get(a, []), windows.get(b, []))
                correlations.append(
                    {"a": a, "b": b, "correlation": value, "observations": observations}
                )
        return Comparison(envelope, start, rows, rebased, correlations)

    async def _series(
        self, code: str, revision: int | None
    ) -> tuple[Envelope, FundRow, FundSeries]:
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        found = await self._reader.series([code], snapshot.revision)
        return envelope, row, found[0]

    async def annual(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Calendar-year, financial-year and monthly returns."""
        envelope, _, series = await self._series(code, revision)
        return envelope, views.annual(series.points, envelope.as_of.toordinal())

    async def rolling(
        self, code: str, window: str, revision: int | None = None
    ) -> tuple[Envelope, list[tuple[str, float]]]:
        """Annualised rolling returns of one window length."""
        if window not in ROLLING_WINDOWS:
            raise FilterError("window", f"window is one of {', '.join(ROLLING_WINDOWS)}")
        envelope, _, series = await self._series(code, revision)
        return envelope, views.rolling_series(series.points, ROLLING_WINDOWS[window])

    async def drawdowns(
        self, code: str, top: int, revision: int | None = None
    ) -> tuple[Envelope, list[dict[str, Any]]]:
        """The deepest falls in the stored history."""
        envelope, _, series = await self._series(code, revision)
        return envelope, views.drawdowns(series.points, top)

    async def simulate(
        self,
        kind: str,
        codes: Sequence[str],
        params: Mapping[str, Any],
        tax_class: str | None = None,
        slab_rate: float | None = None,
        revision: int | None = None,
    ) -> Simulated:
        """Run a calculator over real NAVs and estimate the tax on its redemptions.

        SIP and lump sum are taxed as if every unit were redeemed on the valuation date.
        """
        if kind not in SIMULATIONS:
            raise FilterError("kind", f"kind is one of {', '.join(SIMULATIONS)}")
        if tax_class is not None and tax_class not in TAX_CLASSES:
            raise FilterError("tax_class", f"tax_class is one of {', '.join(TAX_CLASSES)}")
        if slab_rate is not None and not 0 <= slab_rate <= 1:
            raise FilterError("slab_rate", "slab_rate is a fraction from 0 to 1")
        envelope, row, series = await self._series(codes[0], revision)
        points = series.points
        if kind == "sip":
            outcome = calculators.sip(points, **params)
        elif kind == "lumpsum":
            outcome = calculators.lumpsum(points, **params)
        elif kind == "swp":
            outcome = calculators.swp(points, **params)
        else:
            if len(codes) != 2:
                raise FilterError("codes", "stp needs a source and a target code")
            _, _, target = await self._series(codes[1], revision)
            outcome = calculators.stp(points, target.points, **params)
        sales = outcome.sales
        chosen = tax_class or tax_class_of(
            str(cell(row, "category")), str(cell(row, "asset_class"))
        )
        series_2018 = calculators.Series.of(points)
        at = series_2018.on_or_before(GRANDFATHER_BEFORE - 1)
        nav_2018 = series_2018.navs[at] if at is not None else None
        tax = capital_gains_tax(sales, chosen, slab_rate, nav_2018)
        cautions = [
            "Past NAVs only; the simulation does not forecast returns.",
            "Exit loads, surcharge and securities transaction tax are not modelled.",
        ]
        if cell(row, "return_basis") == NAV_EXCLUDING_PAYOUTS:
            cautions.append(CAUTION)
        return Simulated(envelope, outcome, tax, chosen, cautions)


def cell(row: FundRow, field: str, index: Mapping[str, int] = INDEX) -> Any:
    """A field's value, or ``None`` when it is missing."""
    value = row.values[index[field]]
    return None if isinstance(value, Missing) else value


def state(row: FundRow, field: str, index: Mapping[str, int] = INDEX) -> dict[str, str] | None:
    """A missing field's state and reason, or ``None`` when it has a value."""
    value = row.values[index[field]]
    return {"state": value.state, "reason": value.reason} if isinstance(value, Missing) else None
