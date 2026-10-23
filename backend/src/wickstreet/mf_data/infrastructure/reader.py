"""The MF read adapter: plan-options and NAVs at an explicit revision (MF-5, MF-11).

``history`` reads every series in one repeatable-read transaction. A publish writes
its rows and moves the pointer in one transaction, so in that snapshot the current
rows are exactly the rows visible at the pointer. The rows stream through a
server-side cursor in (plan-option, date) order and are grouped one fund at a time,
so memory holds one series, not 22M rows. Every other read applies the MF-5 rule
at the revision it is given.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncResult

from platform_common.database import Database
from wickstreet.mf_data.domain.model import TBILL_91
from wickstreet.mf_data.domain.reads import FundRecord, FundSeries, History, Link, NavPoint


class NothingPublishedError(RuntimeError):
    """No revision is published yet."""


def _visible(alias: str) -> str:
    return (
        f"{alias}.revision_id <= :r AND "
        f"({alias}.superseded_revision IS NULL OR {alias}.superseded_revision > :r)"
    )


def _latest(table: str, columns: str, scope: str) -> str:
    return (
        f"SELECT DISTINCT ON (plan_option_id) plan_option_id, {columns} "
        f"FROM wickstreet.{table} a WHERE {_visible('a')} AND {scope} "
        "ORDER BY plan_option_id, effective_from DESC, id DESC"
    )


def _funds_sql(scope: str) -> str:
    """Each plan-option with its latest master and listing attributes at :r.

    ``scope`` restricts plan_option_id; the master is AMFI's record, the listing a
    fallback and the source of the plan and option columns.
    """
    master = _latest(
        "plan_option_master",
        "amc, scheme_name, nav_name, scheme_type, category, isin_growth, isin_reinvest, "
        "launch_date",
        scope,
    )
    listing = _latest(
        "plan_option_listing",
        "amc, category, nav_name, plan, option, isin_growth, isin_reinvest",
        scope,
    )
    return (
        f"WITH m AS ({master}), l AS ({listing}) "
        "SELECT p.id, p.amfi_code, coalesce(m.amc, l.amc), m.scheme_name, "
        "coalesce(m.nav_name, l.nav_name), m.scheme_type, coalesce(m.category, l.category), "
        "l.plan, l.option, coalesce(m.isin_growth, l.isin_growth), "
        "coalesce(m.isin_reinvest, l.isin_reinvest), m.launch_date "
        "FROM wickstreet.plan_option p "
        "LEFT JOIN m ON m.plan_option_id = p.id LEFT JOIN l ON l.plan_option_id = p.id "
        f"WHERE p.first_revision <= :r AND {scope.replace('plan_option_id', 'p.id')}"
    )


_BY_CODES = "plan_option_id IN (SELECT id FROM wickstreet.plan_option WHERE amfi_code IN :codes)"
# Date ordinals as in Python: 0001-01-01 is 1.
_ORDINAL = "(n.nav_date - DATE '0001-01-01') + 1"
_STREAM = (
    f"SELECT n.plan_option_id, {_ORDINAL}, n.nav::float8, n.anomaly FROM wickstreet.nav n "
    "WHERE n.superseded_revision IS NULL ORDER BY n.plan_option_id, n.nav_date"
)
_STREAM_BATCH = 20_000
_RATES = text(
    "SELECT effective_date, value::float8 FROM wickstreet.rate_point t "
    f"WHERE series = :s AND {_visible('t')} ORDER BY effective_date"
)


def _record(row: Sequence[Any]) -> FundRecord:
    return FundRecord(*row)


async def _grouped(
    records: dict[int, FundRecord], rows: AsyncResult[Any]
) -> AsyncIterator[FundSeries]:
    """One series per plan-option; plan-options without NAVs come last, empty."""
    current: int | None = None
    points: list[tuple[int, float | None, str | None]] = []
    async for batch in rows.partitions(_STREAM_BATCH):
        for plan_option_id, day, nav, anomaly in map(tuple, batch):
            if plan_option_id != current:
                if current is not None:
                    yield FundSeries(records.pop(current), points)
                current, points = plan_option_id, []
            points.append((day, nav, anomaly))
    if current is not None:
        yield FundSeries(records.pop(current), points)
    for plan_option_id in sorted(records):
        yield FundSeries(records[plan_option_id], ())


class SqlMfReader:
    """Reads MF data as the runtime role; never writes."""

    def __init__(self, database: Database) -> None:
        """Read through ``database``."""
        self._database = database

    async def _rows(self, sql: Any, **params: Any) -> list[Sequence[Any]]:
        async with self._database.engine.connect() as connection:
            return list((await connection.execute(sql, params)).all())

    async def pointer(self) -> int | None:
        """Return the published revision."""
        rows = await self._rows(text("SELECT revision_id FROM wickstreet.publication"))
        return int(rows[0][0]) if rows else None

    @staticmethod
    async def _sources(connection: AsyncConnection, revision: int) -> tuple[str, ...]:
        rows = await connection.execute(
            text(
                "SELECT DISTINCT r.source FROM wickstreet.revision v "
                "JOIN wickstreet.ingestion_run r ON r.id = v.run_id WHERE v.id <= :r ORDER BY 1"
            ),
            {"r": revision},
        )
        return tuple(row[0] for row in rows)

    async def sources(self, revision: int) -> tuple[str, ...]:
        """Return the sources of every revision up to ``revision``."""
        async with self._database.engine.connect() as connection:
            return await self._sources(connection, revision)

    @asynccontextmanager
    async def history(self) -> AsyncIterator[History]:
        """Open one consistent, read-only pass over every series at the pointer."""
        async with self._database.engine.connect() as base:
            connection = await base.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
            async with connection.begin():
                revision = await connection.scalar(
                    text("SELECT revision_id FROM wickstreet.publication")
                )
                if revision is None:
                    raise NothingPublishedError("No MF revision is published yet.")
                as_of = await connection.scalar(
                    text(
                        "SELECT max(nav_date) FROM wickstreet.nav WHERE superseded_revision IS NULL"
                    )
                )
                sources = await self._sources(connection, revision)
                risk_free = [
                    (day.toordinal(), value)
                    for day, value in await connection.execute(
                        _RATES, {"s": TBILL_91, "r": revision}
                    )
                ]
                found = await connection.execute(text(_funds_sql("TRUE")), {"r": revision})
                records = {row[0]: _record(row) for row in found}
                rows = await connection.stream(
                    text(_STREAM).execution_options(yield_per=_STREAM_BATCH)
                )
                yield History(revision, as_of, sources, _grouped(records, rows), risk_free)

    async def search(self, query: str, limit: int, revision: int) -> list[FundRecord]:
        """Match an AMFI code or ISIN exactly, or a name by substring."""
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql = text(
            f"SELECT * FROM ({_funds_sql('TRUE')}) f(id, amfi_code, amc, scheme_name, nav_name, "
            "scheme_type, category, plan, option, isin_growth, isin_reinvest, launch_date) "
            "WHERE f.amfi_code = :q OR f.isin_growth = :q OR f.isin_reinvest = :q "
            "OR f.nav_name ILIKE :like OR f.scheme_name ILIKE :like "
            "ORDER BY f.amfi_code = :q DESC, f.nav_name, f.amfi_code LIMIT :limit"
        )
        rows = await self._rows(sql, r=revision, q=query, like=like, limit=limit)
        return [_record(row) for row in rows]

    async def _funds(self, codes: Sequence[str], revision: int) -> list[FundRecord]:
        sql = text(_funds_sql(_BY_CODES)).bindparams(bindparam("codes", expanding=True))
        rows = await self._rows(sql, r=revision, codes=list(codes))
        return [_record(row) for row in rows]

    async def fund(self, code: str, revision: int) -> FundRecord | None:
        """Return one plan-option by AMFI code."""
        found = await self._funds([code], revision)
        return found[0] if found else None

    async def navs(self, code: str, start: date, end: date, revision: int) -> list[NavPoint]:
        """NAVs as filed in ``[start, end]``, each with its source and revision."""
        rows = await self._rows(
            text(
                "SELECT n.nav_date, n.nav::text, n.anomaly, r.source, n.revision_id "
                "FROM wickstreet.nav n JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
                "JOIN wickstreet.revision v ON v.id = n.revision_id "
                "JOIN wickstreet.ingestion_run r ON r.id = v.run_id "
                f"WHERE p.amfi_code = :code AND n.nav_date BETWEEN :start AND :end "
                f"AND {_visible('n')} ORDER BY n.nav_date"
            ),
            code=code,
            start=start,
            end=end,
            r=revision,
        )
        return [NavPoint(*row) for row in rows]

    async def series(self, codes: Sequence[str], revision: int) -> list[FundSeries]:
        """Full series of a few plan-options, in the order of ``codes``."""
        records = {f.amfi_code: f for f in await self._funds(codes, revision)}
        # Keyed on plan_option_id so the planner walks pk_nav, already in order; a filter
        # on amfi_code through the join made it scan the whole table.
        sql = text(
            f"SELECT n.plan_option_id, {_ORDINAL}, n.nav::float8, n.anomaly "
            "FROM wickstreet.nav n "
            f"WHERE n.plan_option_id = ANY(:ids) AND {_visible('n')} "
            "ORDER BY n.plan_option_id, n.nav_date"
        )
        ids = {f.plan_option_id: f.amfi_code for f in records.values()}
        points: dict[str, list[tuple[int, float | None, str | None]]] = {c: [] for c in records}
        for pid, day, nav, anomaly in await self._rows(sql, ids=list(ids), r=revision):
            points[ids[pid]].append((day, nav, anomaly))
        return [FundSeries(records[c], points[c]) for c in codes if c in records]

    async def rates(self, series: str, revision: int) -> list[tuple[date, float]]:
        """One rate series at ``revision``, in date order."""
        return [(day, value) for day, value in await self._rows(_RATES, s=series, r=revision)]

    async def links(self, code: str) -> list[Link]:
        """Curated links from or to one plan-option."""
        rows = await self._rows(
            text(
                "SELECT f.amfi_code, t.amfi_code, k.kind, k.effective_date, k.evidence "
                "FROM wickstreet.plan_option_link k "
                "JOIN wickstreet.plan_option f ON f.id = k.from_plan_option_id "
                "JOIN wickstreet.plan_option t ON t.id = k.to_plan_option_id "
                "WHERE f.amfi_code = :code OR t.amfi_code = :code "
                "ORDER BY k.effective_date, f.amfi_code, t.amfi_code, k.kind"
            ),
            code=code,
        )
        return [Link(*row) for row in rows]


async def record_link(
    database: Database,
    *,
    from_code: str,
    to_code: str,
    kind: str,
    effective_date: date,
    evidence: str,
    recorded_by: str,
) -> bool:
    """Record a link with the owner login; ``False`` when it is already recorded."""
    async with database.engine.begin() as connection:
        result = await connection.execute(
            text(
                "INSERT INTO wickstreet.plan_option_link (from_plan_option_id, "
                "to_plan_option_id, kind, effective_date, evidence, recorded_by) "
                "SELECT f.id, t.id, :kind, :effective_date, :evidence, :recorded_by "
                "FROM wickstreet.plan_option f, wickstreet.plan_option t "
                "WHERE f.amfi_code = :from_code AND t.amfi_code = :to_code "
                "ON CONFLICT DO NOTHING RETURNING id"
            ),
            {
                "from_code": from_code,
                "to_code": to_code,
                "kind": kind,
                "effective_date": effective_date,
                "evidence": evidence,
                "recorded_by": recorded_by,
            },
        )
        return result.first() is not None
