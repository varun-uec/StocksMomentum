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

from sqlalchemy import TextClause, bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncResult

from platform_common.database import Database
from wickstreet.mf_data.domain.model import TBILL_91
from wickstreet.mf_data.domain.reads import (
    SEARCH_SYNONYMS,
    SERIES_FACTS,
    FactPoint,
    FactView,
    FundRecord,
    FundSeries,
    History,
    HoldingRow,
    Link,
    NavPoint,
    Portfolio,
    SchemeFactRow,
    SchemePortfolios,
    SchemeProfile,
    search_terms,
)
from wickstreet.mf_data.infrastructure.tables import compacted


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


# A plan-option joins its scheme through the ISINs or AMFI codes its scheme's SSD lists
# (doc 21 E1); failing that, by its master scheme name when one listed scheme has it.
_SCHEME_OF = (
    "SELECT DISTINCT ON (j.plan_option_id) j.plan_option_id, j.sd_id FROM ("
    "SELECT m.plan_option_id, i.sd_id, 0 AS via, m.effective_from "
    "FROM wickstreet.plan_option_master m JOIN wickstreet.scheme_isin i "
    f"ON i.isin IN (m.isin_growth, m.isin_reinvest) WHERE {_visible('m')} "
    "UNION ALL SELECT m.plan_option_id, n.sd_id, 1, m.effective_from "
    "FROM wickstreet.plan_option_master m JOIN ("
    f"SELECT {compacted('s.name')} AS k, min(s.sd_id) AS sd_id FROM wickstreet.scheme s "
    f"GROUP BY 1 HAVING count(*) = 1) n ON n.k = {compacted('m.scheme_name')} "
    f"WHERE {_visible('m')}) j "
    "ORDER BY j.plan_option_id, j.via, j.effective_from DESC, j.sd_id"
)
_FACT_DAY = "(f.as_of - DATE '0001-01-01') + 1"
_LATEST_FACTS = text(
    f"SELECT DISTINCT ON (f.sd_id, f.name, f.plan) f.sd_id, f.name, f.plan, {_FACT_DAY}, "
    f"f.num::float8, f.txt FROM wickstreet.scheme_fact f WHERE {_visible('f')} "
    "ORDER BY f.sd_id, f.name, f.plan, f.as_of DESC"
)
_SERIES_FACTS = text(
    f"SELECT f.sd_id, f.name, f.plan, {_FACT_DAY}, f.num::float8, f.txt "
    f"FROM wickstreet.scheme_fact f WHERE f.name = ANY(:names) AND {_visible('f')} "
    "ORDER BY f.sd_id, f.name, f.plan, f.as_of"
)


_HOLDING_COLUMNS = (
    "h.sd_id, h.as_of, h.name, h.isin, h.industry, h.section, h.asset, "
    "h.weight::float8, h.value::float8"
)
_LATEST_PORTFOLIOS = text(
    f"WITH v AS (SELECT * FROM wickstreet.holding h WHERE {_visible('h')}), "
    "latest AS (SELECT sd_id, max(as_of) AS as_of FROM v GROUP BY sd_id) "
    f"SELECT {_HOLDING_COLUMNS} FROM v h JOIN latest l USING (sd_id, as_of) "
    "ORDER BY h.sd_id, h.seq"
)
_DISTRIBUTIONS = text(
    "SELECT d.plan_option_id, (d.record_date - DATE '0001-01-01') + 1, d.per_unit::float8 "
    f"FROM wickstreet.distribution d WHERE {_visible('d')} ORDER BY d.plan_option_id, d.record_date"
)
_CAPS = text(
    f"SELECT c.isin, c.as_of, c.cap_class FROM wickstreet.security_class c WHERE {_visible('c')} "
    "ORDER BY c.isin, c.as_of"
)


async def _caps(connection: AsyncConnection, revision: int) -> dict[str, list[tuple[date, str]]]:
    caps: dict[str, list[tuple[date, str]]] = {}
    for isin, as_of, cap_class in await connection.execute(_CAPS, {"r": revision}):
        caps.setdefault(isin, []).append((as_of, cap_class))
    return caps


def _portfolios(rows: Any) -> dict[int, list[Portfolio]]:
    found: dict[int, list[Portfolio]] = {}
    for sd_id, as_of, name, isin, industry, section, asset, weight, value in rows:
        listed = found.setdefault(sd_id, [])
        if not listed or listed[-1].as_of != as_of:
            listed.append(Portfolio(as_of, []))
        listed[-1].rows.append(  # type: ignore[attr-defined]
            HoldingRow(name, isin, industry, section, asset, weight, value)
        )
    return found


async def _streamed(
    connection: AsyncConnection, sql: TextClause, params: dict[str, Any]
) -> AsyncIterator[tuple[Any, ...]]:
    found = await connection.stream(sql.execution_options(yield_per=_STREAM_BATCH), params)
    async for batch in found.partitions(_STREAM_BATCH):
        for row in batch:
            yield tuple(row)


async def _fact_view(connection: AsyncConnection, revision: int) -> FactView:
    params = {"r": revision}
    scheme_of: dict[int, int] = {}
    for pid, sd_id in await connection.execute(text(_SCHEME_OF), params):
        scheme_of[pid] = sd_id
    # The fact queries stream: buffering the TER and AUM series (~670k rows) whole
    # cost ~180 MB at the compute's peak.
    latest: dict[int, dict[tuple[str, str], FactPoint]] = {}
    found = _streamed(connection, _LATEST_FACTS, params)
    async for sd_id, name, plan, day, num, txt in found:
        latest.setdefault(sd_id, {})[(name, plan)] = FactPoint(day, num, txt)
    series: dict[int, dict[tuple[str, str], list[FactPoint]]] = {}
    found = _streamed(connection, _SERIES_FACTS, params | {"names": list(SERIES_FACTS)})
    async for sd_id, name, plan, day, num, txt in found:
        series.setdefault(sd_id, {}).setdefault((name, plan), []).append(FactPoint(day, num, txt))
    distributions: dict[int, list[tuple[int, float]]] = {}
    for pid, day, rate in await connection.execute(_DISTRIBUTIONS, params):
        distributions.setdefault(pid, []).append((day, rate))
    latest_portfolios = await connection.execute(_LATEST_PORTFOLIOS, params)
    portfolios = {sd_id: found[-1] for sd_id, found in _portfolios(latest_portfolios).items()}
    caps = await _caps(connection, revision)
    return FactView(scheme_of, latest, series, portfolios, caps, distributions)


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
                facts = await _fact_view(connection, revision)
                found = await connection.execute(text(_funds_sql("TRUE")), {"r": revision})
                records = {row[0]: _record(row) for row in found}
                rows = await connection.stream(
                    text(_STREAM).execution_options(yield_per=_STREAM_BATCH)
                )
                yield History(revision, as_of, sources, _grouped(records, rows), risk_free, facts)

    async def search(self, query: str, limit: int, revision: int) -> list[FundRecord]:
        """Match an AMFI code or ISIN exactly, or every term of a name or AMC.

        A term matches the name or AMC with spaces and punctuation removed. Up to
        ``limit`` matches return, Direct Growth plans first; the caller ranks them.
        """
        words = search_terms(query)
        if not words:
            return []
        compact = (
            "regexp_replace(lower(coalesce(f.nav_name, '') || ' ' || coalesce(f.scheme_name, '') "
            "|| ' ' || coalesce(f.amc, '')), '[^a-z0-9]', '', 'g')"
        )
        bound: dict[str, str] = {}
        clauses = []
        for i, word in enumerate(words):
            options = (word, *SEARCH_SYNONYMS.get(word, ()))
            bound |= {f"t{i}_{j}": f"%{o}%" for j, o in enumerate(options)}
            clauses.append(" OR ".join(f"{compact} LIKE :t{i}_{j}" for j in range(len(options))))
        match = " AND ".join(f"({c})" for c in clauses)
        sql = text(
            f"SELECT * FROM ({_funds_sql('TRUE')}) f(id, amfi_code, amc, scheme_name, nav_name, "
            "scheme_type, category, plan, option, isin_growth, isin_reinvest, launch_date) "
            f"WHERE upper(f.amfi_code) = :q OR f.isin_growth = :q OR f.isin_reinvest = :q "
            f"OR ({match}) "
            # A missing ISIN or listing makes a test NULL, which DESC would sort first.
            "ORDER BY upper(f.amfi_code) = :q OR f.isin_growth = :q OR f.isin_reinvest = :q "
            "DESC NULLS LAST, "
            # Listings spell these "Direct Plan" and "Growth Option"; names mix cases.
            "(lower(f.plan) LIKE 'direct%' AND lower(f.option) LIKE 'growth%') DESC NULLS LAST, "
            "lower(f.nav_name), f.amfi_code "
            "LIMIT :limit"
        )
        rows = await self._rows(sql, r=revision, q=query.strip().upper(), limit=limit, **bound)
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

    async def scheme_profile(self, code: str, revision: int) -> SchemeProfile | None:
        """The scheme of one plan-option and every fact visible for it at ``revision``."""
        found = await self._rows(
            text(
                f"SELECT j.sd_id, s.name FROM ({_SCHEME_OF}) j "
                "JOIN wickstreet.scheme s ON s.sd_id = j.sd_id "
                "JOIN wickstreet.plan_option p ON p.id = j.plan_option_id WHERE p.amfi_code = :c"
            ),
            c=code,
            r=revision,
        )
        if not found:
            return None
        sd_id, name = found[0]
        rows = await self._rows(
            text(
                "SELECT f.name, f.plan, f.as_of, f.num::float8, f.txt "
                f"FROM wickstreet.scheme_fact f WHERE f.sd_id = :s AND {_visible('f')} "
                "ORDER BY f.name, f.plan, f.as_of"
            ),
            s=sd_id,
            r=revision,
        )
        payouts = await self._rows(
            text(
                "SELECT d.record_date, d.per_unit::float8 FROM wickstreet.distribution d "
                "JOIN wickstreet.plan_option p ON p.id = d.plan_option_id "
                f"WHERE p.amfi_code = :c AND {_visible('d')} ORDER BY d.record_date"
            ),
            c=code,
            r=revision,
        )
        return SchemeProfile(
            sd_id, name, [SchemeFactRow(*row) for row in rows], [(d, v) for d, v in payouts]
        )

    async def scheme_portfolios(self, code: str, revision: int) -> SchemePortfolios | None:
        """Every visible portfolio of the plan-option's scheme, oldest first."""
        profile = await self._rows(
            text(
                f"SELECT j.sd_id, s.name FROM ({_SCHEME_OF}) j "
                "JOIN wickstreet.scheme s ON s.sd_id = j.sd_id "
                "JOIN wickstreet.plan_option p ON p.id = j.plan_option_id WHERE p.amfi_code = :c"
            ),
            c=code,
            r=revision,
        )
        if not profile:
            return None
        sd_id, name = profile[0]
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    f"SELECT {_HOLDING_COLUMNS} FROM wickstreet.holding h "
                    f"WHERE h.sd_id = :s AND {_visible('h')} ORDER BY h.as_of, h.seq"
                ),
                {"s": sd_id, "r": revision},
            )
            found = _portfolios(rows).get(sd_id, [])
            caps = await _caps(connection, revision) if found else {}
        return SchemePortfolios(sd_id, name, found, caps)

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
