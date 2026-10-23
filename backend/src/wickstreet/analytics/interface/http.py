"""MF research routes: the screener, fund reads and comparison (ADR-018, doc 06).

Every response carries ``data_revision``, ``latest_revision``, ``method_version``,
``as_of`` and ``sources``. Pass ``data_revision`` to pin a read to an older snapshot.
The same request at the same revision gives the same bytes, except
``latest_revision``, which follows the live pointer.
"""

from __future__ import annotations

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
from wickstreet.analytics.domain.fields import FIELDS
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


def _row(row: FundRow, columns: Any) -> dict[str, Any]:
    states = {c: s for c in columns if (s := state(row, c)) is not None}
    out = {
        "plan_option_id": row.plan_option_id,
        "amfi_code": row.amfi_code,
        "name": row.name,
        "values": {c: cell(row, c) for c in columns},
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


@router.get("/screener/fields")
async def screener_fields(
    _: Context, research: ResearchDep, data_revision: Revision = None
) -> dict[str, Any]:
    """The field registry, generated from the metric definitions."""
    envelope, version, fields = await research.fields(data_revision)
    return {**_envelope(envelope), "registry_version": version, "fields": fields}


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
        )
    )
    return {
        **_envelope(result.envelope),
        "total": result.total,
        "matched": result.matched,
        "excluded_missing": result.excluded_missing,
        "columns": list(result.columns),
        "rows": [_row(r, result.columns) for r in result.rows],
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
            }
            for fund, row in found
        ],
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
    }
