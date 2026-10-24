"""MF research routes: the screener, fund reads and comparison (ADR-018, doc 06).

Every response carries ``data_revision``, ``latest_revision``, ``method_version``,
``as_of`` and ``sources``. Pass ``data_revision`` to pin a read to an older snapshot.
The same request at the same revision gives the same bytes, except
``latest_revision``, which follows the live pointer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from wickstreet.analytics.application.research import (
    Envelope,
    Research,
    ScreenRequest,
    cell,
    state,
)
from wickstreet.analytics.domain import classify
from wickstreet.analytics.domain.calculators import SimulationError
from wickstreet.analytics.domain.fields import FIELDS, INDEX
from wickstreet.analytics.domain.metrics import Missing
from wickstreet.analytics.domain.presets import PRESETS
from wickstreet.analytics.domain.screening import Group, explain
from wickstreet.analytics.domain.snapshot import FundRow
from wickstreet.dependencies import Context

router = APIRouter(tags=["mf-research"])


def _research(request: Request) -> Research:
    research: Research = request.app.state.research
    return research


ResearchDep = Annotated[Research, Depends(_research)]
Revision = Annotated[int | None, Query(description="Pin the read to this snapshot revision.")]


def _envelope(envelope: Envelope) -> dict[str, Any]:
    return {
        "data_revision": envelope.data_revision,
        "latest_revision": envelope.latest_revision,
        "method_version": envelope.method_version,
        "as_of": envelope.as_of.isoformat(),
        "sources": list(envelope.sources),
    }


def _row(row: FundRow, columns: Any, index: Mapping[str, int] = INDEX) -> dict[str, Any]:
    states = {c: s for c in columns if (s := state(row, c, index)) is not None}
    out = {
        "plan_option_id": row.plan_option_id,
        "amfi_code": row.amfi_code,
        "name": row.name,
        "values": {c: cell(row, c, index) for c in columns},
        "states": states,
    }
    if cell(row, "return_basis") == classify.NAV_EXCLUDING_PAYOUTS:
        out["caution"] = classify.CAUTION
    return out


def _metrics(row: FundRow) -> dict[str, Any]:
    out = _row(row, [f.id for f in FIELDS])
    out["anchors"] = row.anchors
    since = cell(row, "since_start")
    out["since_label"] = f"since {since}, first stored valid NAV, not inception" if since else None
    return out


class PageIn(BaseModel):
    """Which page of a screen."""

    size: int = 50
    after: str | None = None


class ScreenIn(BaseModel):
    """``POST /screener/run`` body (doc 06 §4)."""

    filter: Any = None
    sort: list[Any] = Field(default_factory=list)
    columns: list[str] | None = None
    page: PageIn = Field(default_factory=PageIn)
    data_revision: int | None = None
    formulas: dict[str, str] = Field(default_factory=dict)


@router.get("/screener/fields")
async def screener_fields(
    _: Context, research: ResearchDep, data_revision: Revision = None
) -> dict[str, Any]:
    """The field registry, generated from the metric definitions."""
    envelope, version, fields = await research.fields(data_revision)
    return {**_envelope(envelope), "registry_version": version, "fields": fields}


def _conditions(where: Group | None, row: FundRow) -> list[dict[str, Any]]:
    return [
        {"path": path, "passed": passed}
        | (
            {"value": None, "state": {"state": value.state, "reason": value.reason}}
            if isinstance(value, Missing)
            else {"value": value}
        )
        for path, passed, value in explain(where, row.values)
    ]


@router.post("/screener/run")
async def screener_run(_: Context, research: ResearchDep, body: ScreenIn) -> dict[str, Any]:
    """Evaluate a filter tree over the pinned snapshot."""
    result = await research.screen(
        ScreenRequest(
            filter=body.filter,
            sort=body.sort,
            columns=body.columns,
            size=body.page.size,
            after=body.page.after,
            data_revision=body.data_revision,
            formulas=body.formulas,
        )
    )
    return {
        **_envelope(result.envelope),
        "total": result.total,
        "matched": result.matched,
        "excluded_missing": result.excluded_missing,
        "columns": list(result.columns),
        "rows": [
            _row(r, result.columns, result.index) | {"conditions": _conditions(result.where, r)}
            for r in result.rows
        ],
        "relaxations": result.relaxations,
        "next": result.next,
    }


@router.get("/funds")
async def funds_search(
    _: Context,
    research: ResearchDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Plan-options by name, AMFI code or ISIN, including those without NAVs."""
    envelope, found = await research.search(q, limit, data_revision)
    return {
        **_envelope(envelope),
        "funds": [
            {
                "amfi_code": fund.amfi_code,
                "name": fund.nav_name,
                "amc": fund.amc,
                "category": None if row is None else cell(row, "category"),
                "plan": None if row is None else cell(row, "plan"),
                "option": None if row is None else cell(row, "option"),
                "nav_available": row is not None and cell(row, "nav") is not None,
                "status": None if row is None else cell(row, "status"),
                "last_nav_date": None if row is None else cell(row, "last_nav_date"),
            }
            for fund, row in found
        ],
    }


@router.get("/funds/sparklines")
async def fund_sparklines(
    _: Context,
    research: ResearchDep,
    code: Annotated[list[str], Query()],
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Month-end NAVs over the last 3 years for 1 to 50 funds, for small trend lines."""
    envelope, series = await research.sparklines(code, data_revision)
    return {
        **_envelope(envelope),
        "series": {c: [[d, v] for d, v in points] for c, points in series.items()},
    }


@router.get("/funds/{code}")
async def fund_detail(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Attributes, classification and curated links of one plan-option."""
    detail = await research.fund(code, data_revision)
    fund = asdict(detail.fund)
    fund["launch_date"] = None if detail.fund.launch_date is None else str(detail.fund.launch_date)
    classification = (
        "category",
        "source_category",
        "asset_class",
        "plan",
        "option",
        "return_basis",
        "active",
        "last_nav_date",
        "since_start",
    )
    return {
        **_envelope(detail.envelope),
        "fund": fund,
        "classification": {c: cell(detail.row, c) for c in classification},
        "links": [
            {**asdict(link), "effective_date": link.effective_date.isoformat()}
            for link in detail.links
        ],
    }


@router.get("/funds/{code}/metrics")
async def fund_metrics(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Every metric of one fund, its states and the start date of each trailing return."""
    envelope, row = await research.metrics(code, data_revision)
    return {**_envelope(envelope), **_metrics(row)}


@router.get("/funds/{code}/navs")
async def fund_navs(
    _: Context,
    research: ResearchDep,
    code: str,
    start: date = date.min,
    end: date = date.max,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """NAVs as filed, each with its source and revision."""
    envelope, navs = await research.navs(code, start, end, data_revision)
    return {
        **_envelope(envelope),
        "amfi_code": code,
        "navs": [
            {
                "date": p.nav_date.isoformat(),
                "nav": p.nav,
                "anomaly": p.anomaly,
                "source": p.source,
                "revision": p.revision,
            }
            for p in navs
        ],
    }


@router.get("/compare")
async def compare(
    _: Context,
    research: ResearchDep,
    code: Annotated[list[str], Query()],
    start: date | None = None,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Metrics of 2 to 5 funds and their NAVs rebased to 100 at ``start``."""
    result = await research.compare(code, start, data_revision)
    return {
        **_envelope(result.envelope),
        "start": result.start.isoformat(),
        "funds": [_metrics(r) for r in result.rows],
        "series": {c: [[d, v] for d, v in points] for c, points in result.series.items()},
        "correlations": result.correlations,
        "average_correlation": result.average_correlation,
    }


@router.get("/screener/presets")
async def screener_presets(_: Context) -> dict[str, Any]:
    """Prebuilt screens; run one by posting its filter, sort and columns."""
    return {"presets": [asdict(preset) for preset in PRESETS]}


@router.get("/funds/{code}/annual")
async def fund_annual(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Calendar-year and financial-year returns, partial ends labelled, and monthly returns."""
    envelope, table = await research.annual(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **table}


@router.get("/funds/{code}/rolling")
async def fund_rolling(
    _: Context,
    research: ResearchDep,
    code: str,
    window: str = "3y",
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Annualised rolling returns by window end date (1y, 3y or 5y)."""
    envelope, points = await research.rolling(code, window, data_revision)
    return {**_envelope(envelope), "amfi_code": code, "window": window, "points": points}


@router.get("/funds/{code}/drawdowns")
async def fund_drawdowns(
    _: Context,
    research: ResearchDep,
    code: str,
    top: Annotated[int, Query(ge=1, le=20)] = 5,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """The deepest falls from a peak, with trough and recovery dates."""
    envelope, episodes = await research.drawdowns(code, top, data_revision)
    return {**_envelope(envelope), "amfi_code": code, "drawdowns": episodes}


class CalculatorIn(BaseModel):
    """A simulation over a fund's real NAVs.

    ``amount`` is the monthly instalment (sip) or the initial investment (lumpsum, swp,
    stp); ``instalment`` is the monthly withdrawal (swp) or transfer (stp).
    """

    code: str
    target: str | None = None
    amount: float
    instalment: float | None = None
    day: int = 1
    start: date
    end: date
    step_up: float = 0.0
    tax_class: str | None = None
    slab_rate: float | None = None
    data_revision: int | None = None


def _params(kind: str, body: CalculatorIn) -> dict[str, Any]:
    window = {"start": body.start, "end": body.end}
    if kind == "sip":
        return {"amount": body.amount, "day": body.day, "step_up": body.step_up, **window}
    if kind == "lumpsum":
        return {"amount": body.amount, **window}
    if body.instalment is None:
        raise SimulationError(f"{kind} needs an instalment")
    if kind == "swp":
        return {"amount": body.amount, "withdrawal": body.instalment, "day": body.day, **window}
    return {"amount": body.amount, "transfer": body.instalment, "day": body.day, **window}


@router.post("/calculators/{kind}")
async def calculator(
    _: Context, research: ResearchDep, kind: str, body: CalculatorIn
) -> dict[str, Any]:
    """SIP, lump sum, SWP or STP over real NAVs, with XIRR and a capital-gains estimate."""
    codes = [body.code] + ([body.target] if body.target else [])
    result = await research.simulate(
        kind, codes, _params(kind, body), body.tax_class, body.slab_rate, body.data_revision
    )
    tax = result.tax
    return {
        **_envelope(result.envelope),
        "kind": kind,
        "codes": codes,
        "summary": result.outcome.summary,
        "timeline": result.outcome.timeline,
        "tax": {
            "rules": tax.rules,
            "tax_class": result.tax_class,
            "total": tax.total,
            "years": tax.years,
            "sales_not_modelled": tax.not_modelled,
            "reason": tax.reason,
        },
        "cautions": result.cautions,
    }


# ---- method v4 (doc 21)

Category = Annotated[str, Query(description="Canonical category, as in the registry.")]
Plan = Annotated[str, Query(description="direct or regular.")]
Option = Annotated[str, Query(description="growth, idcw, bonus or unknown.")]


@router.get("/funds/{code}/rank-history")
async def fund_rank_history(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Point-in-time category rank of the 1Y return and 3Y CAGR at each month-end."""
    envelope, body = await research.rank_history(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/peers/transitions")
async def peer_transitions(
    _: Context,
    research: ResearchDep,
    category: Category,
    plan: Plan,
    option: Option,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """How often a 1Y-return quartile led to each quartile 12 month-ends later."""
    envelope, body = await research.transitions(category, plan, option, data_revision)
    return {**_envelope(envelope), **body}


@router.get("/peers/frontier")
async def peer_frontier(
    _: Context,
    research: ResearchDep,
    category: Category,
    plan: Plan,
    option: Option,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Active peers on 3Y volatility and 3Y CAGR; ``frontier`` marks the non-dominated."""
    envelope, body = await research.frontier(category, plan, option, data_revision)
    return {**_envelope(envelope), **body}


class BacktestIn(BaseModel):
    """``POST /backtests``: a top-N strategy in one peer group (doc 21 M14)."""

    category: str
    plan: str
    option: str
    signal: str = "ret_1y"
    top: int = 5
    data_revision: int | None = None


@router.post("/backtests")
async def run_backtest(_: Context, research: ResearchDep, body: BacktestIn) -> dict[str, Any]:
    """Monthly point-in-time selection against the group median, in-sample and hold-out."""
    envelope, result = await research.backtest(
        body.category, body.plan, body.option, body.signal, body.top, body.data_revision
    )
    return {**_envelope(envelope), **result}


@router.get("/funds/{code}/direct-regular")
async def fund_direct_regular(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """The other plan of the same scheme and option, and the observed gap."""
    envelope, body = await research.direct_regular(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/underwater")
async def fund_underwater(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Fall from the running peak at each NAV, and recovery-time spreads."""
    envelope, body = await research.underwater(code, data_revision)
    body["series"] = [[d, v] for d, v in body["series"]]
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/rolling-sip")
async def fund_rolling_sip(
    _: Context,
    research: ResearchDep,
    code: str,
    tenor: str = "3y",
    amount: Annotated[float, Query(gt=0)] = 10_000.0,
    day: Annotated[int, Query(ge=1, le=31)] = 1,
    step_up: Annotated[float, Query(ge=0, le=1)] = 0.0,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """A SIP started in every month with a full tenor: XIRR, best, worst and drawdown."""
    envelope, body = await research.rolling_sip(code, tenor, amount, day, step_up, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/near-duplicates")
async def fund_near_duplicates(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """Peers whose daily returns over 3Y correlate at 0.95 or more."""
    envelope, body = await research.near_duplicates(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/score")
async def fund_score(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """The score's parts, weights, peer counts, missing reasons and data-quality notes."""
    envelope, body = await research.score(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/confidence")
async def fund_confidence(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """What limits the fund's numbers: history, gaps, flags, category basis, sources."""
    envelope, body = await research.confidence(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/risk-free")
async def risk_free(
    _: Context, research: ResearchDep, data_revision: Revision = None
) -> dict[str, Any]:
    """The RBI 91-day T-bill cut-off yields used as the risk-free rate."""
    envelope, body = await research.risk_free(data_revision)
    return {**_envelope(envelope), **body}


@router.get("/regimes")
async def market_regimes(
    _: Context, research: ResearchDep, data_revision: Revision = None
) -> dict[str, Any]:
    """Falls and recoveries of the labelled NAV-built proxy; not an official index."""
    envelope, body = await research.regimes(data_revision)
    return {**_envelope(envelope), **body}


@router.get("/funds/{code}/regimes")
async def fund_regimes(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """The fund's return in each regime window beside the proxy's."""
    envelope, body = await research.fund_regimes(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/profile")
async def fund_profile(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """AMFI's fund facts: TER, AUM, riskometer, managers, exit load, minimums and history."""
    envelope, body = await research.profile(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/benchmark")
async def fund_benchmark(
    _: Context, research: ResearchDep, code: str, data_revision: Revision = None
) -> dict[str, Any]:
    """AMFI's returns against the Tier 1 benchmark, and statistics against a labelled proxy."""
    envelope, body = await research.benchmark(code, data_revision)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/funds/{code}/holdings")
async def fund_holdings(
    _: Context,
    research: ResearchDep,
    code: str,
    as_of: Annotated[date | None, Query(description="Latest portfolio on or before.")] = None,
    data_revision: Revision = None,
) -> dict[str, Any]:
    """The fund's disclosed portfolio: mix, concentration, lines, changes and trend."""
    envelope, body = await research.holdings(code, data_revision, as_of)
    return {**_envelope(envelope), "amfi_code": code, **body}


@router.get("/holdings/overlap")
async def holdings_overlap(
    _: Context,
    research: ResearchDep,
    code: Annotated[list[str], Query(description="2 to 5 AMFI codes.")],
    data_revision: Revision = None,
) -> dict[str, Any]:
    """Shared securities and weighted overlap between each pair of funds."""
    envelope, body = await research.overlap(code, data_revision)
    return {**_envelope(envelope), **body}
