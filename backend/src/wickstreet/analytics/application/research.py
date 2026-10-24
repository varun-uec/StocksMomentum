"""Compute snapshots and serve research reads over them (ADR-017 MF-11, MF-13).

Every read resolves one revision: the snapshot the caller pins, or the latest one.
Metrics, screens, fund detail, NAVs and comparisons all read at that revision. The
rights checks live here, not in HTTP, so every caller inherits them.
"""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from wickstreet.analytics.domain import backtest, calculators, views
from wickstreet.analytics.domain.calculators import Outcome
from wickstreet.analytics.domain.classify import (
    CAUTION,
    DIRECT,
    ETF,
    GROWTH,
    INDEX_FUND,
    NAV_EXCLUDING_PAYOUTS,
    REGULAR,
    UNCLASSIFIED,
    canonical_category,
    option_of,
    plan_of,
    sibling_categories,
)
from wickstreet.analytics.domain.enrichment import (
    FACT_FIELD_IDS,
    HORIZONS,
    IR_HORIZONS,
    PROXY_FIELDS,
    SSD_PROFILE,
    TER_DEFINITION_CHANGE,
    benchmark_key,
    change_points,
    choose_proxies,
    cost_ranks,
    fact_fields,
    facts_of,
    finite,
    idcw_fields,
    manager_starts,
    proxy_fields,
)
from wickstreet.analytics.domain.fields import (
    FIELDS,
    INDEX,
    attributes,
    ordered,
    registry_version,
)
from wickstreet.analytics.domain.fieldspec import Field
from wickstreet.analytics.domain.formulas import compile_formulas, with_formulas
from wickstreet.analytics.domain.holdings import (
    HOLDING_FIELD_IDS,
    cap_of,
    holding_fields,
)
from wickstreet.analytics.domain.holdings import changes as holding_changes
from wickstreet.analytics.domain.holdings import overlap as holdings_overlap
from wickstreet.analytics.domain.holdings import summary as holdings_summary
from wickstreet.analytics.domain.holdings import trend as holdings_trend
from wickstreet.analytics.domain.metrics import (
    ACTIVE,
    HISTORY_TOO_SHORT,
    MAX_GAP_DAYS,
    METHOD_VERSION,
    METRIC_FIELDS,
    NO_BENCHMARK,
    NO_NAV,
    NO_PEER_GROUP,
    NO_PROXY,
    NO_SCHEME,
    NOT_FILED,
    YEAR_DAYS,
    Missing,
    MonthEnds,
    RiskFree,
    Value,
    compute,
    last_complete_month,
    month_end_values,
    rebase,
    valid_series,
)
from wickstreet.analytics.domain.peers import (
    RANKED_INPUTS,
    SCORE_PARTS,
    PeerFund,
    Rank,
    absent_fields,
    add_group_fields,
    group_absence,
    monthly_ranks,
    transitions,
)
from wickstreet.analytics.domain.relations import (
    MAX_LISTED,
    PROXY,
    DailyNavs,
    daily_returns,
    near_duplicates,
    no_pair,
    pair_fields,
    pairs,
    proxy_index,
    regimes,
    window_return,
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
from wickstreet.analytics.domain.search import Standing, ranked
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
from wickstreet.mf_data.domain.model import TBILL_91
from wickstreet.mf_data.domain.reads import (
    FundRecord,
    FundSeries,
    History,
    Link,
    MfReader,
    NavPoint,
    Portfolio,
)

DEFAULT_COLUMNS = ("category", "plan", "option", "ret_1y", "cagr_3y", "cagr_5y", "vol_3y", "mdd_3y")
MAX_PAGE = 500
MAX_COMPARE = 5
MAX_SPARKLINES = 50
# Search ranks this many term matches; a broader query should add a term.
SEARCH_CANDIDATES = 500
# Funds computed between two turns of the event loop.
# ponytail: full GC passes over the snapshot's objects still stall the loop ~120 ms;
# run the compute in its own process if request latency during a compute matters.
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


def _group_fields(
    members: Sequence[tuple[int, PeerFund]], daily: Mapping[int, DailyNavs], last_month: int
) -> dict[int, list[tuple[int, float, int]]]:
    """Write one group's peer fields; return its near-duplicates."""
    add_group_fields([peer for _, peer in members], last_month)
    return near_duplicates([daily[pid] for pid, peer in members if peer.active and pid in daily])


def _in_proxy(fund: FundRecord) -> bool:
    """Whether the fund belongs to the regime proxy's category, plan and option."""
    return (
        canonical_category(fund.category) == PROXY["category"]
        and plan_of(fund) == PROXY["plan"]
        and option_of(fund) == PROXY["option"]
    )


def _proxy_candidate(values: Mapping[str, Value]) -> bool:
    """An index fund's direct growth plan, or an ETF, can stand in for its benchmark."""
    if values["fund_type"] == ETF:
        return True
    return (
        values["fund_type"] == INDEX_FUND
        and values["plan"] == DIRECT
        and (values["option"] == GROWTH)
    )


def _plus(a: Any, b: Any) -> float | None:
    return a + b if isinstance(a, float) and isinstance(b, float) else None


class ComputeSnapshot:
    """Compute the snapshot of the published revision once (MF-11)."""

    @staticmethod
    async def encode(history: History) -> Encoded:
        """Every fund's fields at the history's revision, encoded; stores nothing.

        Pass 1 computes each fund's own metrics from its stream and keeps the inputs of
        the cross-fund fields. Pass 2 sets sibling categories, the peer fields (groups
        hold every fund with a NAV, so past month-ends rank the funds alive then),
        direct–regular pairs, near-duplicates and the regime proxy. Pass 3 streams the
        rows through the encoder in plan-option order. The loop gets a turn every
        ``_YIELD_EVERY`` funds, so requests keep moving.
        """
        as_of = history.as_of.toordinal()
        risk_free = RiskFree.of(history.risk_free)
        records: list[FundRecord] = []
        own: list[tuple[tuple[Value, ...], dict[str, str]]] = []
        month_ends: dict[int, tuple[MonthEnds, dict[str, float]]] = {}
        daily: dict[int, DailyNavs] = {}
        proxy_days: dict[int, list[float]] = defaultdict(list)
        async for series in history.funds:
            fund = series.fund
            metrics = compute(series.points, as_of, risk_free)
            records.append(fund)
            own.append((tuple(metrics.values[n] for n in METRIC_FIELDS), metrics.anchors))
            if metrics.values["status"] != NO_NAV:
                month_ends[fund.plan_option_id] = (metrics.month_ends, metrics.then)
            if metrics.days:
                daily[fund.plan_option_id] = DailyNavs(
                    fund.plan_option_id, metrics.days, metrics.levels
                )
            if _in_proxy(fund):
                dates, navs, _, _ = valid_series(series.points)
                for day, value in daily_returns(dates, navs):
                    proxy_days[day].append(value)
            await _turn(len(records))
        siblings = sibling_categories(records)
        status_at, input_at = (
            METRIC_FIELDS.index("status"),
            [METRIC_FIELDS.index(n) for n in RANKED_INPUTS],
        )
        classes: list[dict[str, Value]] = []
        extra: dict[int, dict[str, Value]] = {}
        options: dict[int, str] = {}
        cost_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
        candidates: list[tuple[int, str, str, str, float | None, Value]] = []
        groups: dict[tuple[str, str, str], list[tuple[int, PeerFund]]] = defaultdict(list)
        grouped: dict[int, PeerFund] = {}
        pair_keys: dict[int, tuple[str, str, str, str]] = {}
        anchors_of: dict[int, dict[str, str]] = {}
        for fund, (metric_values, anchors) in zip(records, own, strict=True):
            values = attributes(fund, siblings.get(fund.plan_option_id))
            classes.append(values)
            status = str(metric_values[status_at])
            pid = fund.plan_option_id
            facts = facts_of(history.facts, pid, str(values["plan"]), str(values["fund_type"]))
            extra[pid] = fact_fields(facts, str(values["option"]), as_of)
            options[pid] = str(values["option"])
            anchors_of[pid] = anchors
            portfolio = history.facts.portfolios.get(facts.sd_id) if facts else None
            extra[pid] |= (
                holding_fields(portfolio, history.facts.caps)
                if facts is not None
                else dict.fromkeys(HOLDING_FIELD_IDS, Missing("NA", NO_SCHEME))
            )
            if status == ACTIVE and values["category"] != UNCLASSIFIED:
                key = (str(values["category"]), str(values["plan"]), str(values["option"]))
                cost_groups[key].append(pid)
            if facts is not None and status == ACTIVE and _proxy_candidate(values):
                filed = facts.get("tracking_benchmark", scheme_level=True)
                filed = filed or facts.get("benchmark", scheme_level=True)
                te = facts.get("tracking_error")
                # The proxy's tracking difference: its own return against the index,
                # both from one AMFI report.
                gap = extra[pid]["excess_3y"]
                if filed is not None and filed.txt and pid in daily:
                    name = fund.nav_name or fund.scheme_name or fund.amfi_code
                    candidates.append(
                        (pid, fund.amfi_code, name, filed.txt, te.num if te else None, gap)
                    )
            if status == ACTIVE:
                pair_keys[fund.plan_option_id] = (
                    fund.amc or "",
                    fund.scheme_name or "",
                    str(values["option"]),
                    str(values["plan"]),
                )
            if status != NO_NAV and values["category"] != UNCLASSIFIED:
                inputs = {n: metric_values[i] for n, i in zip(RANKED_INPUTS, input_at, strict=True)}
                ends, then = month_ends[fund.plan_option_id]
                peer = PeerFund(inputs, ends, then, status == ACTIVE)
                key = (str(values["category"]), str(values["plan"]), str(values["option"]))
                groups[key].append((fund.plan_option_id, peer))
                if peer.active:
                    grouped[fund.plan_option_id] = peer
            await _turn(len(classes))
        month_ends.clear()
        last_month = last_complete_month(as_of)
        near: dict[int, list[tuple[int, float, int]]] = {}
        for members in groups.values():
            # A large group takes a second or more; a thread keeps the loop turning.
            near |= await asyncio.to_thread(_group_fields, members, daily, last_month)
        cost_ranks(cost_groups, extra)
        proxies = choose_proxies(candidates)
        for done, (pid, values) in enumerate(extra.items()):
            bench = values["benchmark"]
            proxy = proxies.get(benchmark_key(bench)) if isinstance(bench, str) else None
            if proxy is None:
                reason = NO_PROXY if isinstance(bench, str) else NO_BENCHMARK
                values |= dict.fromkeys(PROXY_FIELDS, Missing("NA", reason))
                values["bench_proxy_gap_3y"] = Missing("NA", reason)
            else:
                values |= proxy_fields(daily.get(pid), daily[proxy.pid], risk_free)
                values["bench_proxy_gap_3y"] = proxy.gap_3y
            payouts = history.facts.distributions.get(pid, ())
            values |= idcw_fields(options[pid], payouts, daily.get(pid), as_of, anchors_of[pid])
            for name in FACT_FIELD_IDS:
                values.setdefault(name, Missing("NA", NO_PEER_GROUP))
            extra[pid] = finite(values)
            await _turn(done + 1)
        has_window = set(daily)
        daily.clear()
        partners = pairs(pair_keys)
        position = {fund.plan_option_id: i for i, fund in enumerate(records)}
        code = {fund.plan_option_id: fund.amfi_code for fund in records}
        levels = proxy_index(proxy_days)
        tables = {
            "pairs": {code[a]: code[b] for a, b in partners.items()},
            "near_duplicates": {
                code[pid]: [[code[q], c, n] for q, c, n in found[:MAX_LISTED]]
                for pid, found in near.items()
            },
            "regimes": regimes(levels),
            "proxy": PROXY
            | {"levels": [[date.fromordinal(d).isoformat(), level] for d, level in levels]},
            "benchmark_proxies": {
                key: {
                    "benchmark": p.benchmark,
                    "code": p.code,
                    "name": p.name,
                    "tracking_error": p.tracking_error,
                    "gap_3y": p.gap_3y
                    if isinstance(p.gap_3y, float) and math.isfinite(p.gap_3y)
                    else None,
                }
                for key, p in sorted(proxies.items())
            },
        }
        encoder = Encoder(METHOD_VERSION, history.revision, history.as_of, history.sources)
        for done, i in enumerate(
            sorted(range(len(records)), key=lambda i: records[i].plan_option_id)
        ):
            # A row's dicts are dropped once it is encoded: kept, they held every
            # field of every fund to the end (~250 MB at the compute's peak).
            fund, values = records[i], classes[i]
            classes[i] = {}
            pid = fund.plan_option_id
            metric_values, anchors = own[i]
            values |= dict(zip(METRIC_FIELDS, metric_values, strict=True))
            values |= extra.pop(pid)
            found = grouped.get(pid)
            if found is None:
                absent = group_absence(str(values["status"]), str(values["category"]), UNCLASSIFIED)
                absent = absent or Missing("NA", NO_PEER_GROUP)
                values |= absent_fields(absent) | {"near_duplicates": absent}
            else:
                values |= found.values
                values["near_duplicates"] = (
                    len(near.get(pid, []))
                    if pid in has_window
                    else Missing("NA", HISTORY_TOO_SHORT)
                )
            partner = partners.get(pid)
            if partner is None:
                values |= no_pair()
            else:
                mine = dict(zip(METRIC_FIELDS, metric_values, strict=True))
                theirs = dict(zip(METRIC_FIELDS, own[position[partner]][0], strict=True))
                direct, regular = (mine, theirs) if values["plan"] == DIRECT else (theirs, mine)
                values |= pair_fields(direct, regular)
            encoder.add(
                FundRow(
                    pid,
                    fund.amfi_code,
                    fund.nav_name or fund.scheme_name or fund.amfi_code,
                    ordered(values),
                    anchors,
                )
            )
            await _turn(done + 1)
        return encoder.finish(tables)

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
    # Mean of the pairwise correlations; ``None`` when any pair has none.
    average_correlation: float | None


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
SIP_TENORS = {"3y": 36, "5y": 60}
# ponytail: in-process cache of month-ends for the last 32 peer groups read; a snapshot
# never changes, so entries need no invalidation. Move it out of process for SaaS.
_GROUP_CACHE_SIZE = 32
# Recovery-time spreads are reported for falls at least this deep.
RECOVERY_DEPTHS = (-0.05, -0.10, -0.20)
PEER_KEY = ("category", "plan", "option")


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
        self._groups: dict[tuple[int, str, str, str], dict[str, MonthEnds]] = {}

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
        """The registry; snapshot values for an open enum, the value range for a number."""
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
            coverage = {
                "values": len(snapshot.rows) - sum(reasons.values()),
                "missing": dict(sorted(reasons.items())),
            }
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
                    "coverage": coverage,
                    **({"range": list(snapshot.ranges[f.id])} if f.id in snapshot.ranges else {}),
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
        found = await self._reader.search(query, SEARCH_CANDIDATES, snapshot.revision)
        standing = {
            f.amfi_code: Standing(
                (cell(row, "plan"), cell(row, "option")) == ("direct", "growth"),
                cell(row, "since_start") or "",
            )
            for f in found
            if (row := snapshot.by_code.get(f.amfi_code)) and cell(row, "status") == "active"
        }
        best = ranked(query, found, standing)[:limit]
        return envelope, [(f, snapshot.by_code.get(f.amfi_code)) for f in best]

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
        correlations: list[dict[str, Any]] = []
        for i, a in enumerate(codes):
            for b in codes[i + 1 :]:
                value, observations = correlation(windows.get(a, []), windows.get(b, []))
                correlations.append(
                    {"a": a, "b": b, "correlation": value, "observations": observations}
                )
        values = [c["correlation"] for c in correlations if c["correlation"] is not None]
        average = math.fsum(values) / len(values) if len(values) == len(correlations) else None
        return Comparison(envelope, start, rows, rebased, correlations, average)

    async def sparklines(
        self, codes: Sequence[str], revision: int | None = None
    ) -> tuple[Envelope, dict[str, list[tuple[str, float]]]]:
        """Month-end NAVs over 3 years for up to ``MAX_SPARKLINES`` funds; unknown codes drop."""
        if not 1 <= len(codes) <= MAX_SPARKLINES:
            raise FilterError("code", f"sparklines take 1 to {MAX_SPARKLINES} codes")
        snapshot, envelope = await self._pinned(revision)
        known = [c for c in dict.fromkeys(codes) if c in snapshot.by_code]
        found = await self._reader.series(known, snapshot.revision) if known else []
        return envelope, {s.fund.amfi_code: views.month_end_navs(s.points, 36) for s in found}

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

    # ---- method v4 views (doc 21)

    def _peer_rows(
        self, snapshot: Snapshot, category: str, plan: str, option: str
    ) -> list[FundRow]:
        """Every fund of one peer group with a NAV, including funds that stopped."""
        if category == UNCLASSIFIED:
            raise FilterError("category", "Unclassified funds have no peer group")
        found = [
            r
            for r in snapshot.rows
            if (cell(r, "category"), cell(r, "plan"), cell(r, "option")) == (category, plan, option)
            and cell(r, "status") != NO_NAV
        ]
        if not found:
            raise FilterError("category", "no fund in this category, plan and option")
        return found

    async def _month_ends(
        self, snapshot: Snapshot, category: str, plan: str, option: str
    ) -> dict[str, MonthEnds]:
        """Code -> month-ends of one peer group, read at the snapshot's revision."""
        key = (snapshot.id, category, plan, option)
        if key in self._groups:
            return self._groups[key]
        rows = self._peer_rows(snapshot, category, plan, option)
        found = await self._reader.series([r.amfi_code for r in rows], snapshot.revision)
        as_of = snapshot.as_of.toordinal()
        ends = {}
        for one in found:
            dates, navs, _, _ = valid_series(one.points)
            ends[one.fund.amfi_code] = month_end_values(dates, navs, as_of)
        self._groups[key] = dict(sorted(ends.items()))
        if len(self._groups) > _GROUP_CACHE_SIZE:
            del self._groups[next(iter(self._groups))]
        return self._groups[key]

    async def _group_ranks(
        self, snapshot: Snapshot, category: str, plan: str, option: str
    ) -> tuple[list[str], list[dict[int, Rank]], list[dict[int, Rank]]]:
        ends = await self._month_ends(snapshot, category, plan, option)
        members = [PeerFund({}, e, {}, False) for e in ends.values()]
        return list(ends), monthly_ranks(members, "ret_1y"), monthly_ranks(members, "cagr_3y")

    async def rank_history(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """The fund's point-in-time category rank at each month-end (1Y and 3Y)."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        key = [str(cell(row, k)) for k in PEER_KEY]
        codes, one, three = await self._group_ranks(snapshot, *key)
        i = codes.index(code)
        history = [
            {
                "month": _month(m),
                "ret_1y": _rank_json(one[i].get(m)),
                "cagr_3y": _rank_json(three[i].get(m)),
            }
            for m in sorted(one[i].keys() | three[i].keys())
        ]
        group = dict(zip(PEER_KEY, key, strict=True)) | {"funds_with_nav": len(codes)}
        return envelope, {"group": group, "history": history}

    async def transitions(
        self, category: str, plan: str, option: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Counts of 1Y-return quartile now and 12 month-ends later, over the group's history."""
        snapshot, envelope = await self._pinned(revision)
        codes, one, _ = await self._group_ranks(snapshot, category, plan, option)
        counts = transitions(one)
        shares = [[c / sum(row) if sum(row) else None for c in row] for row in counts]
        return envelope, {
            "group": {"category": category, "plan": plan, "option": option},
            "funds_with_nav": len(codes),
            "counts": counts,
            "shares": shares,
        }

    async def direct_regular(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """The fund's direct–regular pair and the observed gap between the plans."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        partner = snapshot.tables.get("pairs", {}).get(code)
        if partner is None:
            return envelope, {"pair": None, "reason": "no_pair"}
        other = self._row(snapshot, partner)
        direct, regular = (row, other) if cell(row, "plan") == DIRECT else (other, row)
        shown = ("ret_1y", "cagr_3y", "cagr_5y")
        return envelope, {
            "pair": {
                plan: {
                    "amfi_code": r.amfi_code,
                    "name": r.name,
                    **{f: cell(r, f) for f in shown},
                }
                for plan, r in (("direct", direct), ("regular", regular))
            },
            **{f: cell(row, f) for f in ("dr_gap_1y", "dr_gap_3y", "dr_wealth_10y")},
            "label": "Observed NAV gap between the plans; includes the TER difference; not TER.",
        }

    async def underwater(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """The underwater series, recovery-time spreads and the longest time under water."""
        envelope, row, series = await self._series(code, revision)
        episodes = views.drawdowns(series.points, len(series.points))
        return envelope, {
            "series": views.underwater(series.points),
            "recovery": [views.recovery_spread(episodes, d) for d in RECOVERY_DEPTHS],
            **{f: cell(row, f) for f in ("dd_now", "dd_now_days", "underwater_max_days")},
        }

    async def rolling_sip(
        self,
        code: str,
        tenor: str,
        amount: float,
        day: int,
        step_up: float,
        revision: int | None = None,
    ) -> tuple[Envelope, dict[str, Any]]:
        """The SIP outcome of every start month with a full tenor."""
        if tenor not in SIP_TENORS:
            raise FilterError("tenor", f"tenor is one of {', '.join(SIP_TENORS)}")
        envelope, _, series = await self._series(code, revision)
        starts = views.rolling_sip(
            series.points, envelope.as_of.toordinal(), SIP_TENORS[tenor], amount, day, step_up
        )
        known = [s for s in starts if s["xirr"] is not None]
        summary: dict[str, Any] = {"starts": len(starts)}
        if known:
            ordered_ = sorted(known, key=lambda s: (s["xirr"], s["start"]))
            summary |= {
                "worst": ordered_[0],
                "best": ordered_[-1],
                "median_xirr": ordered_[(len(ordered_) - 1) // 2]["xirr"],
                "positive_share": sum(1 for s in known if s["xirr"] > 0) / len(known),
                "worst_sip_drawdown": min(s["sip_drawdown"] for s in starts),
            }
        return envelope, {
            "tenor": tenor,
            "amount": amount,
            "day": day,
            "step_up": step_up,
            "summary": summary,
            "starts": starts,
        }

    async def frontier(
        self, category: str, plan: str, option: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Active peers on 3Y volatility and 3Y CAGR, with the non-dominated set marked."""
        snapshot, envelope = await self._pinned(revision)
        rows = [
            r
            for r in self._peer_rows(snapshot, category, plan, option)
            if cell(r, "status") == ACTIVE
            and cell(r, "vol_3y") is not None
            and cell(r, "cagr_3y") is not None
        ]
        points = [(r.amfi_code, float(cell(r, "vol_3y")), float(cell(r, "cagr_3y"))) for r in rows]
        best = views.frontier(points)
        return envelope, {
            "risk": "vol_3y",
            "return": "cagr_3y",
            "points": [
                {
                    "amfi_code": r.amfi_code,
                    "name": r.name,
                    "vol_3y": cell(r, "vol_3y"),
                    "cagr_3y": cell(r, "cagr_3y"),
                    "downside_dev_3y": cell(r, "downside_dev_3y"),
                    "frontier": r.amfi_code in best,
                }
                for r in rows
            ],
        }

    async def near_duplicates(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Peers whose daily returns move almost identically with this fund's."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        listed = snapshot.tables.get("near_duplicates", {}).get(code, [])
        return envelope, {
            "count": cell(row, "near_duplicates"),
            "state": state(row, "near_duplicates"),
            "listed": [
                {
                    "amfi_code": other,
                    "name": snapshot.by_code[other].name,
                    "correlation": value,
                    "common_days": days,
                }
                for other, value, days in listed
            ],
        }

    async def score(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Why the fund has its score: each part, its weight, and the data behind it."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        weight = 1 / len(SCORE_PARTS)
        parts = []
        for name in SCORE_PARTS:
            parts.append(
                {
                    "field": name,
                    "value": cell(row, name),
                    "state": state(row, name),
                    "category_percentile": cell(row, f"{name}_cat_pct"),
                    "percentile_state": state(row, f"{name}_cat_pct"),
                    "peers_ranked": cell(row, f"{name}_cat_count"),
                    "weight": weight,
                }
            )
        notes = []
        if (excluded := cell(row, "excluded_navs")) and excluded > 0:
            notes.append(f"{excluded} NAV rows were excluded (null, zero or negative).")
        if (jumps := cell(row, "jump_flags")) and jumps > 0:
            notes.append(f"{jumps} NAV moves over 25% were kept and flagged.")
        if cell(row, "category_basis") != "amfi":
            notes.append(f"Category basis: {cell(row, 'category_basis')}.")
        return envelope, {
            "score": cell(row, "score"),
            "state": state(row, "score"),
            "rank": cell(row, "score_cat_rank"),
            "peers_ranked": cell(row, "score_cat_count"),
            "formula": "Equal-weight mean of the category percentiles of the parts.",
            "parts": parts,
            "penalties": [],
            "data_quality": notes,
        }

    async def confidence(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """What limits the fund's numbers: history, gaps, flags, category, sources."""
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        found = await self._reader.series([code], snapshot.revision)
        dates, _, excluded, jumps = valid_series(found[0].points)
        gaps = [b - a for a, b in zip(dates, dates[1:], strict=False) if b - a > MAX_GAP_DAYS]
        navs = await self._reader.navs(code, date.min, snapshot.as_of, snapshot.revision)
        sources: dict[str, dict[str, Any]] = {}
        for point in navs:
            seen = sources.setdefault(
                point.source, {"rows": 0, "first": point.nav_date, "last": point.nav_date}
            )
            seen["rows"] += 1
            seen["last"] = point.nav_date
        notes = [
            "Categories are AMFI's current labels, applied to past dates.",
            "Ranks and consistency include funds that later stopped, where their label maps.",
        ]
        if cell(row, "return_basis") == NAV_EXCLUDING_PAYOUTS:
            notes.append(CAUTION)
        return envelope, {
            "status": cell(row, "status"),
            "first_nav": _iso(dates[0]) if dates else None,
            "last_nav": _iso(dates[-1]) if dates else None,
            "history_days": dates[-1] - dates[0] if dates else 0,
            "valid_navs": len(dates),
            "gaps_over_7_days": len(gaps),
            "longest_gap_days": max(gaps, default=0),
            "excluded_navs": excluded,
            "jump_flags": jumps,
            "category": cell(row, "category"),
            "category_basis": cell(row, "category_basis"),
            "sources": [
                {
                    "source": k,
                    "rows": v["rows"],
                    "first": v["first"].isoformat(),
                    "last": v["last"].isoformat(),
                }
                for k, v in sorted(sources.items(), key=lambda kv: kv[1]["first"])
            ],
            "notes": notes,
        }

    async def _scheme(self, code: str, revision: int | None) -> tuple[Envelope, FundRow, Any]:
        snapshot, envelope = await self._pinned(revision)
        row = self._row(snapshot, code)
        return envelope, row, await self._reader.scheme_profile(code, snapshot.revision)

    async def profile(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """AMFI's facts for one fund: costs, AUM, riskometer, managers, loads and their history."""
        envelope, row, scheme = await self._scheme(code, revision)
        if scheme is None:
            return envelope, {"scheme": None, "reason": NO_SCHEME}
        plan = str(cell(row, "plan"))
        by: dict[tuple[str, str], list[Any]] = defaultdict(list)
        for fact in scheme.facts:
            by[(fact.name, fact.plan)].append(fact)

        def text_of(name: str) -> dict[str, Any] | None:
            found = by.get((name, ""))
            return {"text": found[-1].txt, "as_of": found[-1].as_of.isoformat()} if found else None

        def numbers(name: str, plan_of: str) -> list[list[Any]]:
            points = [(f.as_of, f.num) for f in by.get((name, plan_of), []) if f.num is not None]
            return [[d.isoformat(), v] for d, v in change_points(points)]

        managers = by.get(("ssd:Fund_Manager_From_Date", ""))
        starts = manager_starts(managers[-1].txt or "") if managers else []
        riskometer_facts = by.get(("riskometer", ""), [])
        riskometer_as_of = max((fact.as_of for fact in riskometer_facts), default=None)
        ter_days = [f.as_of for f in by.get(("ter", plan), [])]
        notes = [
            "Figures are as AMFI publishes them. TER is % a year of daily net assets.",
        ]
        if ter_days and ter_days[0] < TER_DEFINITION_CHANGE <= ter_days[-1]:
            notes.append(
                "SEBI changed what the total TER includes from 1 April 2026; values before "
                "and after that date are not like for like."
            )
        return envelope, {
            "scheme": {"sd_id": scheme.sd_id, "name": scheme.scheme_name},
            "plan": plan,
            "summary": {f: cell(row, f) for f in FACT_FIELD_IDS if f not in PROXY_FIELDS},
            "states": {f: s for f in FACT_FIELD_IDS if (s := state(row, f)) is not None},
            "document": {key: text_of(name) for key, name in SSD_PROFILE.items()},
            "managers": [
                {
                    "name": name,
                    "since": since.isoformat(),
                    "years": round((envelope.as_of - since).days / YEAR_DAYS, 1),
                }
                for name, since in starts
            ],
            "ter": {p: numbers("ter", p) for p in (REGULAR, DIRECT)},
            "ter_base": {p: numbers("ter_base", p) for p in (REGULAR, DIRECT)},
            "aum_cr": numbers("aum_cr", ""),
            "riskometer": [
                [d.isoformat(), v]
                for d, v in change_points([(f.as_of, f.txt) for f in riskometer_facts])
            ],
            "riskometer_as_of": riskometer_as_of.isoformat() if riskometer_as_of else None,
            "idcw": [[d.isoformat(), v] for d, v in scheme.payouts],
            "source": "AMFI: TER, fund performance, scheme summary documents and IDCW history",
            "notes": notes,
        }

    async def benchmark(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """AMFI's returns against the Tier 1 benchmark, and statistics against the proxy."""
        envelope, row, scheme = await self._scheme(code, revision)
        snapshot, _ = await self._pinned(revision)
        if scheme is None:
            return envelope, {"scheme": None, "reason": NO_SCHEME}
        plan = str(cell(row, "plan"))
        by: dict[tuple[str, str], dict[date, float]] = defaultdict(dict)
        for fact in scheme.facts:
            if fact.num is not None:
                by[(fact.name, fact.plan)][fact.as_of] = fact.num
        days = sorted(by.get(("bench_ret_1y", ""), {}))
        history = [
            {
                "date": d.isoformat(),
                **{
                    f"{who}_{h}": by.get((f"{prefix}_{h}", key), {}).get(d)
                    for h in HORIZONS
                    for who, prefix, key in (("fund", "ret", plan), ("benchmark", "bench_ret", ""))
                },
            }
            for d in days
        ]
        bench = cell(row, "benchmark")
        proxy = (
            snapshot.tables.get("benchmark_proxies", {}).get(benchmark_key(bench))
            if isinstance(bench, str)
            else None
        )
        return envelope, {
            "scheme": {"sd_id": scheme.sd_id, "name": scheme.scheme_name},
            "plan": plan,
            "benchmark": bench,
            "riskometer_benchmark": next(
                (f.txt for f in reversed(scheme.facts) if f.name == "riskometer_benchmark"), None
            ),
            "official": {
                "as_of": cell(row, "perf_as_of"),
                "rows": [
                    {
                        "horizon": h,
                        "fund": _plus(cell(row, f"excess_{h}"), cell(row, f"bench_ret_{h}")),
                        "benchmark": cell(row, f"bench_ret_{h}"),
                        "excess": cell(row, f"excess_{h}"),
                        "information_ratio": cell(row, f"ir_{h}") if h in IR_HORIZONS else None,
                    }
                    for h in HORIZONS
                ],
                "history": history,
                "source": "AMFI fund performance: scheme and Tier 1 benchmark TRI returns",
            },
            "proxy": proxy,
            "proxy_stats": {f: cell(row, f) for f in (*PROXY_FIELDS, "bench_proxy_gap_3y")},
            "states": {
                f: s
                for f in (*PROXY_FIELDS, "bench_proxy_gap_3y", *(f"excess_{h}" for h in HORIZONS))
                if (s := state(row, f)) is not None
            },
            "tracking_error_filed": cell(row, "tracking_error"),
            "method": (
                "Returns over 1 year are a year, as AMFI computes them. Proxy statistics use "
                "daily NAVs of an index fund on the same benchmark over the last 3 years: it "
                "carries its own TER and tracking error, so it is not the index."
            ),
        }

    async def holdings(
        self, code: str, revision: int | None = None, as_of: date | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """One fund's disclosed portfolio: mix, concentration, lines, changes and trend."""
        snapshot, envelope = await self._pinned(revision)
        self._row(snapshot, code)
        found = await self._reader.scheme_portfolios(code, snapshot.revision)
        if found is None:
            return envelope, {"scheme": None, "reason": NO_SCHEME}
        scheme = {"sd_id": found.sd_id, "name": found.scheme_name}
        if not found.portfolios:
            return envelope, {"scheme": scheme, "reason": NOT_FILED, "dates": []}
        dates = [p.as_of for p in found.portfolios]
        at = (
            len(dates) - 1
            if as_of is None
            else max((i for i, d in enumerate(dates) if d <= as_of), default=-1)
        )
        if at < 0:
            raise FilterError("as_of", f"no portfolio on or before {as_of}")
        portfolio = found.portfolios[at]
        lines = sorted(portfolio.rows, key=lambda r: (-r.weight, r.name))
        return envelope, {
            "scheme": scheme,
            # Not ``as_of``: the envelope's ``as_of`` is the NAV data date.
            "portfolio_as_of": portfolio.as_of.isoformat(),
            "dates": [d.isoformat() for d in dates],
            "summary": holdings_summary(portfolio, found.caps),
            "lines": [
                {
                    "name": r.name,
                    "isin": r.isin,
                    "industry": r.industry,
                    "section": r.section,
                    "asset": r.asset,
                    "weight": r.weight,
                    "value": r.value,
                    "cap": cap_of(r.isin, portfolio.as_of, found.caps)
                    if r.asset == "equity"
                    else None,
                }
                for r in lines
            ],
            "changes": holding_changes(found.portfolios[at - 1], portfolio) if at > 0 else None,
            "previous_as_of": dates[at - 1].isoformat() if at > 0 else None,
            "trend": holdings_trend(found.portfolios, found.caps),
            "method": (
                "Weights are % of net assets as the AMC filed them. Market cap uses AMFI's list "
                "for the latest half-year ending on or before the portfolio date. Sector and "
                "market-cap shares are of the equity held."
            ),
        }

    async def overlap(
        self, codes: Sequence[str], revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """Shared securities between each pair of funds, from their latest disclosures."""
        if not 2 <= len(set(codes)) <= MAX_COMPARE:
            raise FilterError("code", f"overlap needs 2 to {MAX_COMPARE} distinct codes")
        snapshot, envelope = await self._pinned(revision)
        funds: list[tuple[str, str, Portfolio | None]] = []
        for code in dict.fromkeys(codes):
            row = self._row(snapshot, code)
            found = await self._reader.scheme_portfolios(code, snapshot.revision)
            funds.append(
                (code, row.name, found.portfolios[-1] if found and found.portfolios else None)
            )
        pairs = []
        for i, (code_a, _, a) in enumerate(funds):
            for code_b, _, b in funds[i + 1 :]:
                if a is None or b is None:
                    pairs.append({"a": code_a, "b": code_b, "reason": NOT_FILED})
                    continue
                result = holdings_overlap(a, b)
                result["common"] = result["common"][:25]
                pairs.append({"a": code_a, "b": code_b, **result})
        return envelope, {
            "funds": [
                {"code": code, "name": name, "as_of": p.as_of.isoformat() if p else None}
                for code, name, p in funds
            ],
            "pairs": pairs,
            "method": (
                "Overlap is the sum, over securities both funds hold, of the smaller weight. "
                "Securities match by ISIN; cash, TREPS and derivatives are left out. NAV "
                "correlation (Compare) says funds move together; this says they own the same."
            ),
        }

    async def held_funds(
        self, codes: Sequence[str]
    ) -> tuple[Envelope, dict[str, dict[str, Any]], Mapping[str, Sequence[tuple[date, str]]]]:
        """For a portfolio: each held code's snapshot cells, latest portfolio and direct TER."""
        snapshot, envelope = await self._pinned(None)
        pairs = snapshot.tables.get("pairs", {})
        found: dict[str, dict[str, Any]] = {}
        caps: Mapping[str, Sequence[tuple[date, str]]] = {}
        for code in dict.fromkeys(codes):
            row = snapshot.by_code.get(code)
            if row is None:
                continue
            cells = {
                f: cell(row, f)
                for f in ("category", "asset_class", "plan", "nav", "last_nav_date", "ter", "score")
            }
            partner = pairs.get(code) or next((r for r, d in pairs.items() if d == code), None)
            other = snapshot.by_code.get(partner) if partner else None
            direct = other if other is not None and cell(other, "plan") == DIRECT else None
            portfolios = await self._reader.scheme_portfolios(code, snapshot.revision)
            if portfolios is not None and portfolios.portfolios:
                caps = portfolios.caps
            found[code] = {
                "name": row.name,
                **cells,
                "direct_ter": cell(direct, "ter") if direct is not None else None,
                "holdings": portfolios.portfolios[-1]
                if portfolios and portfolios.portfolios
                else None,
            }
        return envelope, found, caps

    async def alternatives(self, code: str, count: int = 3) -> list[dict[str, Any]]:
        """Active direct growth funds in the code's category with a higher score than it."""
        snapshot, _ = await self._pinned(None)
        row = snapshot.by_code.get(code)
        if row is None:
            return []
        category, mine = cell(row, "category"), cell(row, "score")
        scheme = cell(row, "amc"), row.name.split(" - ")[0]
        better = [
            r
            for r in snapshot.rows
            if cell(r, "category") == category
            and cell(r, "status") == ACTIVE
            and cell(r, "plan") == DIRECT
            and cell(r, "option") == GROWTH
            and isinstance(cell(r, "score"), float)
            and (not isinstance(mine, float) or cell(r, "score") > mine)
            and (cell(r, "amc"), r.name.split(" - ")[0]) != scheme
        ]
        better.sort(key=lambda r: (-cell(r, "score"), r.amfi_code))
        return [
            {
                "code": r.amfi_code,
                "name": r.name,
                **{f: cell(r, f) for f in ("score", "ter", "cagr_3y", "excess_3y", "mdd_3y")},
            }
            for r in better[:count]
        ]

    async def risk_free(self, revision: int | None = None) -> tuple[Envelope, dict[str, Any]]:
        """The 91-day T-bill cut-off yields behind every risk-free value, with their source."""
        snapshot, envelope = await self._pinned(revision)
        points = await self._reader.rates(TBILL_91, snapshot.revision)
        return envelope, {
            "series": TBILL_91,
            "unit": "% a year",
            "points": [[day.isoformat(), value] for day, value in points],
            "method": "Each auction's yield is in force until the next auction and accrues "
            "yield ÷ 365 each calendar day.",
            "acknowledgement": "Source: Reserve Bank of India (Handbook of Statistics on the "
            "Indian Economy; Treasury Bills: Full Auction Result press releases).",
        }

    async def regimes(self, revision: int | None = None) -> tuple[Envelope, dict[str, Any]]:
        """The proxy's falls and recoveries, with its label and daily levels."""
        snapshot, envelope = await self._pinned(revision)
        return envelope, {
            "proxy": snapshot.tables.get("proxy", {}),
            "windows": snapshot.tables.get("regimes", []),
        }

    async def fund_regimes(
        self, code: str, revision: int | None = None
    ) -> tuple[Envelope, dict[str, Any]]:
        """The fund's return in each regime window, beside the proxy's."""
        envelope, _, series = await self._series(code, revision)
        snapshot, _ = await self._pinned(envelope.data_revision)
        dates, navs, _, _ = valid_series(series.points)
        windows = []
        for window in snapshot.tables.get("regimes", []):
            value = window_return(dates, navs, window["start"], window["end"])
            proxy = window["proxy_return"]
            found: dict[str, Any]
            if isinstance(value, Missing):
                found = {
                    "fund_return": None,
                    "state": {"state": value.state, "reason": value.reason},
                }
                found |= {"difference": None, "capture": None}
            else:
                fund_return = float(value)
                found = {
                    "fund_return": fund_return,
                    "state": None,
                    "difference": fund_return - proxy,
                    "capture": fund_return / proxy if proxy else None,
                }
            windows.append(window | found)
        return envelope, {
            "proxy_label": snapshot.tables.get("proxy", {}).get("label"),
            "windows": windows,
        }

    async def backtest(
        self,
        category: str,
        plan: str,
        option: str,
        signal: str,
        top: int,
        revision: int | None = None,
    ) -> tuple[Envelope, dict[str, Any]]:
        """A point-in-time top-``top`` strategy in one peer group against its median."""
        snapshot, envelope = await self._pinned(revision)
        ends = await self._month_ends(snapshot, category, plan, option)
        try:
            months = backtest.run(ends, signal, top)
        except backtest.BacktestError as error:
            raise FilterError("signal", str(error)) from error
        return envelope, {
            "strategy": {
                "category": category,
                "plan": plan,
                "option": option,
                "signal": signal,
                "top": top,
                "rebalance": "monthly",
                "weights": "equal",
                "returns": "NAV, net of TER, before tax",
                "benchmark": "median next-month return of the funds alive at both month-ends",
                "holdout_from": "2024-01",
            },
            "funds_with_nav": len(ends),
            "summary": backtest.summarise(months),
            "regimes_spanned": backtest.spanned(months, snapshot.tables.get("regimes", [])),
            "limits": list(backtest.LIMITS),
            "months": backtest.rows(months),
        }


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def _month(key: int) -> str:
    year, index = divmod(key, 12)
    return f"{year:04d}-{index + 1:02d}"


def _rank_json(rank: Rank | None) -> dict[str, Any] | None:
    if rank is None:
        return None
    return {"rank": rank.rank, "count": rank.count, "pct": rank.pct, "quartile": rank.quartile}


def cell(row: FundRow, field: str, index: Mapping[str, int] = INDEX) -> Any:
    """A field's value, or ``None`` when it is missing."""
    value = row.values[index[field]]
    return None if isinstance(value, Missing) else value


def state(row: FundRow, field: str, index: Mapping[str, int] = INDEX) -> dict[str, str] | None:
    """A missing field's state and reason, or ``None`` when it has a value."""
    value = row.values[index[field]]
    return {"state": value.state, "reason": value.reason} if isinstance(value, Missing) else None
