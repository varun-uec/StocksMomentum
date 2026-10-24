"""PostgreSQL store for MF data (ADR-017 MF-5 to MF-11).

A publication is one transaction: a revision row, the changed facts, the pointer
and the run's outcome. Staged rows enter by COPY into a temporary table, then
set-based statements apply the revision rule:

- a new value inserts a row at R;
- a changed value inserts a row at R and sets ``superseded_revision = R`` on the old one;
- an unchanged value writes nothing. When nothing changes, the transaction is rolled
  back and the run is marked unchanged, so no empty revision exists.

A fill-only publication (an archive under the direct source) inserts new values
and counts, but never supersedes, values that differ from the stored ones.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from platform_common.database import Database
from wickstreet.mf_data.domain.model import (
    AMFI,
    ARCHIVE_TOLERANCE,
    NAV_CONTRACT,
    Anomaly,
    CapClass,
    Distribution,
    NavRecord,
    Portfolios,
    RatePoint,
    SchemeFacts,
    SchemeRecord,
    SchemeRef,
)
from wickstreet.mf_data.domain.ports import Provenance, Published, Run, StoredRaw
from wickstreet.mf_data.infrastructure.tables import compacted

# Key of the session-level advisory lock held by one ingestion runner (MF-10).
_LOCK_KEY = 2_000_100_017
# How far back the jump check looks for a previous NAV.
_PREVIOUS_WINDOW = timedelta(days=15)

_NAV_STAGE = (
    "amfi_code",
    "nav_date",
    "nav",
    "anomaly",
    "amc",
    "category",
    "nav_name",
    "plan",
    "option",
    "isin_growth",
    "isin_reinvest",
)
_MASTER_STAGE = (
    "amfi_code",
    "amc",
    "scheme_name",
    "scheme_type",
    "category",
    "nav_name",
    "min_amount",
    "launch_date",
    "closure_date",
    "isin_growth",
    "isin_reinvest",
)
_LISTING = ("amc", "category", "nav_name", "plan", "option", "isin_growth", "isin_reinvest")
_MASTER = _MASTER_STAGE[1:]


class _NothingChangedError(Exception):
    """Raised inside a publication to roll it back."""

    def __init__(self, conflicts: int = 0) -> None:
        super().__init__()
        self.conflicts = conflicts


def _row(columns: Sequence[str], alias: str) -> str:
    return "(" + ", ".join(f"{alias}.{c}" for c in columns) + ")"


class SqlMfStore:
    """The ``MfStore`` port on PostgreSQL, as the runtime role."""

    def __init__(self, database: Database) -> None:
        """Bind the store to the MF database."""
        self._database = database

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[bool]:
        """Hold a PostgreSQL advisory lock for the whole run sequence."""
        async with self._database.engine.connect() as connection:
            autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
            held = bool(
                await autocommit.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})
            )
            try:
                yield held
            finally:
                if held:
                    await autocommit.execute(
                        text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY}
                    )

    async def open_run(self, source: str, dataset: str, start: date, end: date) -> Run:
        """Return the period's run, creating it as ``pending``."""
        params = {"s": source, "d": dataset, "a": start, "b": end}
        async with self._database.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO wickstreet.ingestion_run "
                    "(source, dataset, period_start, period_end, status) "
                    "VALUES (:s, :d, :a, :b, 'pending') ON CONFLICT DO NOTHING"
                ),
                params,
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT id, status, raw_sha256 FROM wickstreet.ingestion_run WHERE "
                        "source = :s AND dataset = :d AND period_start = :a AND period_end = :b"
                    ),
                    params,
                )
            ).one()
        return Run(id=row.id, status=row.status, raw_sha256=row.raw_sha256)

    async def close_run(
        self, run_id: int, status: str, *, raw_sha256: str | None = None, error: str | None = None
    ) -> None:
        """Record an outcome that published nothing."""
        async with self._database.engine.begin() as connection:
            await self._finish(connection, run_id, status, raw_sha256=raw_sha256, error=error)

    async def _finish(
        self, connection: AsyncConnection, run_id: int, status: str, **values: Any
    ) -> None:
        values.setdefault("raw_sha256", None)
        values.setdefault("error", None)
        for key in ("revision_id", "rows", "inserted", "superseded", "anomalies", "conflicts"):
            values.setdefault(key, None)
        await connection.execute(
            text(
                "UPDATE wickstreet.ingestion_run SET status = :status, "
                "raw_sha256 = coalesce(:raw_sha256, raw_sha256), error = :error, "
                "revision_id = coalesce(:revision_id, revision_id), rows = :rows, "
                "inserted = :inserted, superseded = :superseded, anomalies = :anomalies, "
                "conflicts = :conflicts, "
                "attempts = attempts + 1, finished_at = now() WHERE id = :id"
            ),
            {"id": run_id, "status": status, **values},
        )

    async def previous_navs(self, day: date) -> Mapping[str, Decimal]:
        """Each code's latest positive current NAV in the 15 days before ``day``."""
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT DISTINCT ON (n.plan_option_id) p.amfi_code, n.nav "
                    "FROM wickstreet.nav n "
                    "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
                    "WHERE n.superseded_revision IS NULL AND n.nav_date < :day "
                    "AND n.nav_date >= :since AND n.nav > 0 "
                    "ORDER BY n.plan_option_id, n.nav_date DESC"
                ),
                {"day": day, "since": day - _PREVIOUS_WINDOW},
            )
            return dict(rows.all())

    async def last_nav_day(self) -> date | None:
        """The latest single-date NAV run that published or found its file unchanged."""
        async with self._database.engine.connect() as connection:
            result: date | None = await connection.scalar(
                text(
                    "SELECT max(period_end) FROM wickstreet.ingestion_run WHERE source = :s "
                    "AND dataset = :d AND period_start = period_end "
                    "AND status IN ('published', 'unchanged')"
                ),
                {"s": AMFI, "d": NAV_CONTRACT},
            )
        return result

    async def first_nav_day(self, source: str) -> date | None:
        """The earliest single-date NAV run of ``source`` that published or was unchanged."""
        async with self._database.engine.connect() as connection:
            result: date | None = await connection.scalar(
                text(
                    "SELECT min(period_start) FROM wickstreet.ingestion_run WHERE source = :s "
                    "AND dataset = :d AND period_start = period_end "
                    "AND status IN ('published', 'unchanged')"
                ),
                {"s": source, "d": NAV_CONTRACT},
            )
        return result

    async def current_navs(
        self, amfi_code: str, start: date, end: date
    ) -> dict[date, Decimal | None]:
        """One code's current NAVs in ``[start, end]``."""
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT n.nav_date, n.nav FROM wickstreet.nav n "
                    "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
                    "WHERE p.amfi_code = :code AND n.superseded_revision IS NULL "
                    "AND n.nav_date BETWEEN :a AND :b"
                ),
                {"code": amfi_code, "a": start, "b": end},
            )
            return dict(rows.all())

    async def sample_codes(self, count: int, start: date, end: date) -> list[str]:
        """A fixed pseudo-random sample of codes with current NAVs in ``[start, end]``."""
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT p.amfi_code FROM wickstreet.plan_option p WHERE EXISTS "
                    "(SELECT 1 FROM wickstreet.nav n WHERE n.plan_option_id = p.id "
                    "AND n.superseded_revision IS NULL AND n.nav_date BETWEEN :a AND :b) "
                    "ORDER BY md5(p.amfi_code) LIMIT :n"
                ),
                {"a": start, "b": end, "n": count},
            )
            return list(rows.scalars().all())

    async def stored_raw(self, run_id: int) -> StoredRaw | None:
        """Where the run's last published revision came from, if it has one."""
        async with self._database.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT v.url, v.fetched_at, v.raw_sha256, v.raw_path "
                        "FROM wickstreet.ingestion_run r "
                        "JOIN wickstreet.revision v ON v.id = r.revision_id WHERE r.id = :id"
                    ),
                    {"id": run_id},
                )
            ).first()
        if row is None:
            return None
        return StoredRaw(
            url=row.url, fetched_at=row.fetched_at, sha256=row.raw_sha256, path=row.raw_path
        )

    async def latest_raw(self, source: str, dataset: str) -> StoredRaw | None:
        """The kept file of the newest period of ``source`` that published, if any."""
        async with self._database.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT v.url, v.fetched_at, v.raw_sha256, v.raw_path "
                        "FROM wickstreet.ingestion_run r "
                        "JOIN wickstreet.revision v ON v.id = r.revision_id "
                        "WHERE r.source = :s AND r.dataset = :d "
                        "ORDER BY r.period_start DESC LIMIT 1"
                    ),
                    {"s": source, "d": dataset},
                )
            ).first()
        if row is None:
            return None
        return StoredRaw(
            url=row.url, fetched_at=row.fetched_at, sha256=row.raw_sha256, path=row.raw_path
        )

    async def run_status(
        self, source: str, dataset: str, day: date, end: date | None = None
    ) -> str | None:
        """Status of the run for the period ``day`` to ``end`` (default one date), if any."""
        async with self._database.engine.connect() as connection:
            result: str | None = await connection.scalar(
                text(
                    "SELECT status FROM wickstreet.ingestion_run "
                    "WHERE source = :s AND dataset = :d "
                    "AND period_start = :day AND period_end = :end"
                ),
                {"s": source, "d": dataset, "day": day, "end": end or day},
            )
        return result

    async def _revision(self, connection: AsyncConnection, run_id: int, p: Provenance) -> int:
        revision_id: int = await connection.scalar(
            text(
                "INSERT INTO wickstreet.revision (run_id, contract, url, fetched_at, raw_sha256, "
                "raw_path, adapter_version, retrieval_grant_id, storage_grant_id) VALUES "
                "(:run, :contract, :url, :fetched, :sha, :path, :adapter, :retrieval, :storage) "
                "RETURNING id"
            ),
            {
                "run": run_id,
                "contract": p.contract,
                "url": p.url,
                "fetched": datetime.fromisoformat(p.fetched_at_iso),
                "sha": p.raw_sha256,
                "path": p.raw_path,
                "adapter": p.adapter_version,
                "retrieval": p.retrieval_grant_id,
                "storage": p.storage_grant_id,
            },
        )
        return revision_id

    async def _stage(
        self,
        connection: AsyncConnection,
        name: str,
        ddl: str,
        columns: Sequence[str],
        rows: list[tuple[Any, ...]],
    ) -> None:
        await connection.execute(text(f"CREATE TEMPORARY TABLE {name} ({ddl}) ON COMMIT DROP"))
        raw = await connection.get_raw_connection()
        await raw.driver_connection.copy_records_to_table(  # type: ignore[union-attr]
            name, records=rows, columns=list(columns)
        )

    async def _upsert_plan_options(
        self, connection: AsyncConnection, stage: str, revision_id: int
    ) -> None:
        await connection.execute(
            text(
                "INSERT INTO wickstreet.plan_option (amfi_code, first_revision) "
                f"SELECT DISTINCT amfi_code, CAST(:r AS bigint) FROM {stage} "
                "ON CONFLICT (amfi_code) DO NOTHING"
            ),
            {"r": revision_id},
        )

    async def _attributes(
        self,
        connection: AsyncConnection,
        table: str,
        stage_rows: str,
        columns: Sequence[str],
        revision_id: int,
        params: Mapping[str, Any] | None = None,
    ) -> int:
        """Apply effective-dated attribute rows (MF-4); return how many rows changed.

        ``stage_rows`` selects ``plan_option_id``, ``effective_from`` and ``columns``.
        A different value on the same date supersedes the row; a different value on a
        later date starts a new row; an older date never rewrites later history.
        """
        names = ", ".join(columns)
        staged = ", ".join(f"s.{c}" for c in columns)
        superseded = await connection.execute(
            text(
                f"WITH s AS ({stage_rows}) UPDATE wickstreet.{table} t "
                "SET superseded_revision = :r FROM s WHERE t.plan_option_id = s.plan_option_id "
                "AND t.superseded_revision IS NULL AND t.effective_from = s.effective_from "
                f"AND {_row(columns, 't')} IS DISTINCT FROM {_row(columns, 's')}"
            ),
            {"r": revision_id, **(params or {})},
        )
        inserted = await connection.execute(
            text(
                f"WITH s AS ({stage_rows}), latest AS ("
                f"SELECT DISTINCT ON (plan_option_id) * FROM wickstreet.{table} "
                "WHERE superseded_revision IS NULL ORDER BY plan_option_id, effective_from DESC) "
                f"INSERT INTO wickstreet.{table} "
                f"(plan_option_id, effective_from, revision_id, {names}) "
                f"SELECT s.plan_option_id, s.effective_from, CAST(:r AS bigint), {staged} "
                "FROM s LEFT JOIN latest l ON l.plan_option_id = s.plan_option_id "
                "WHERE l.plan_option_id IS NULL OR (s.effective_from >= l.effective_from "
                f"AND {_row(columns, 'l')} IS DISTINCT FROM {_row(columns, 's')})"
            ),
            {"r": revision_id, **(params or {})},
        )
        return int(superseded.rowcount) + int(inserted.rowcount)

    async def _point(self, connection: AsyncConnection, revision_id: int) -> None:
        await connection.execute(
            text(
                "INSERT INTO wickstreet.publication (id, revision_id) VALUES (1, :r) "
                "ON CONFLICT (id) DO UPDATE SET revision_id = :r, published_at = now()"
            ),
            {"r": revision_id},
        )

    async def publish_navs(
        self,
        run_id: int,
        records: Sequence[NavRecord],
        anomalies: Mapping[tuple[str, date], Anomaly],
        provenance: Provenance,
        *,
        fill_only: bool = False,
    ) -> Published:
        """Publish NAV records as revision R, or mark the run unchanged."""
        rows = [
            (
                r.amfi_code,
                r.nav_date,
                r.nav,
                flag.value if (flag := anomalies.get((r.amfi_code, r.nav_date))) else None,
                r.amc,
                r.category,
                r.nav_name,
                r.plan,
                r.option,
                r.isin_growth,
                r.isin_reinvest,
            )
            for r in records
        ]
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "nav_stage",
                    "amfi_code text, nav_date date, nav numeric, anomaly text, amc text, "
                    "category text, nav_name text, plan text, option text, isin_growth text, "
                    "isin_reinvest text",
                    _NAV_STAGE,
                    rows,
                )
                await self._upsert_plan_options(connection, "nav_stage", revision_id)
                joined = (
                    "FROM nav_stage st JOIN wickstreet.plan_option p ON p.amfi_code = st.amfi_code"
                )
                listing = await self._attributes(
                    connection,
                    "plan_option_listing",
                    "SELECT p.id AS plan_option_id, st.nav_date AS effective_from, "
                    + ", ".join(f"st.{c}" for c in _LISTING)
                    + f" {joined} WHERE st.amc IS NOT NULL",
                    _LISTING,
                    revision_id,
                )
                superseded = conflicts = 0
                if fill_only:
                    conflicts = int(
                        await connection.scalar(
                            text(
                                f"SELECT count(*) {joined} JOIN wickstreet.nav n "
                                "ON n.plan_option_id = p.id AND n.nav_date = st.nav_date "
                                "AND n.superseded_revision IS NULL "
                                "WHERE (n.nav IS NULL) <> (st.nav IS NULL) "
                                "OR abs(n.nav - st.nav) > :tolerance"
                            ),
                            {"tolerance": ARCHIVE_TOLERANCE},
                        )
                        or 0
                    )
                else:
                    updated = await connection.execute(
                        text(
                            f"UPDATE wickstreet.nav n SET superseded_revision = :r {joined} "
                            "WHERE n.plan_option_id = p.id AND n.nav_date = st.nav_date "
                            "AND n.superseded_revision IS NULL AND n.nav IS DISTINCT FROM st.nav"
                        ),
                        {"r": revision_id},
                    )
                    superseded = int(updated.rowcount)
                inserted = await connection.execute(
                    text(
                        "INSERT INTO wickstreet.nav "
                        "(plan_option_id, nav_date, nav, anomaly, revision_id) "
                        "SELECT p.id, st.nav_date, st.nav, st.anomaly, CAST(:r AS bigint) "
                        f"{joined} "
                        "WHERE NOT EXISTS (SELECT 1 FROM wickstreet.nav n "
                        "WHERE n.plan_option_id = p.id AND n.nav_date = st.nav_date "
                        "AND n.superseded_revision IS NULL)"
                    ),
                    {"r": revision_id},
                )
                counts = (int(inserted.rowcount), superseded)
                if counts == (0, 0) and listing == 0:
                    raise _NothingChangedError(conflicts)
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=counts[0],
                    superseded=counts[1],
                    anomalies=len(anomalies),
                    conflicts=conflicts,
                )
        except _NothingChangedError as nothing:
            async with self._database.engine.begin() as connection:
                await self._finish(
                    connection,
                    run_id,
                    "unchanged",
                    raw_sha256=provenance.raw_sha256,
                    rows=len(rows),
                    conflicts=nothing.conflicts,
                )
            return Published(revision=None, inserted=0, superseded=0, conflicts=nothing.conflicts)
        return Published(
            revision=revision_id, inserted=counts[0], superseded=counts[1], conflicts=conflicts
        )

    async def publish_rates(
        self, run_id: int, records: Sequence[RatePoint], provenance: Provenance
    ) -> Published:
        """Publish rates as revision R, or mark the run unchanged."""
        rows = [(r.series, r.day, r.value) for r in records]
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "rate_stage",
                    "series text, effective_date date, value numeric",
                    ("series", "effective_date", "value"),
                    rows,
                )
                superseded = await connection.execute(
                    text(
                        "UPDATE wickstreet.rate_point t SET superseded_revision = :r "
                        "FROM rate_stage s WHERE t.series = s.series "
                        "AND t.effective_date = s.effective_date "
                        "AND t.superseded_revision IS NULL AND t.value <> s.value"
                    ),
                    {"r": revision_id},
                )
                inserted = await connection.execute(
                    text(
                        "INSERT INTO wickstreet.rate_point "
                        "(series, effective_date, value, revision_id) "
                        "SELECT s.series, s.effective_date, s.value, CAST(:r AS bigint) "
                        "FROM rate_stage s WHERE NOT EXISTS (SELECT 1 FROM wickstreet.rate_point t "
                        "WHERE t.series = s.series AND t.effective_date = s.effective_date "
                        "AND t.superseded_revision IS NULL)"
                    ),
                    {"r": revision_id},
                )
                if inserted.rowcount == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=int(inserted.rowcount),
                    superseded=int(superseded.rowcount),
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(int(revision_id), int(inserted.rowcount), int(superseded.rowcount))

    async def publish_schemes(
        self,
        run_id: int,
        snapshot: date,
        records: Sequence[SchemeRecord],
        provenance: Provenance,
        *,
        fill_only: bool = False,
    ) -> Published:
        """Publish the scheme master as revision R, or mark it unchanged."""
        rows = [
            (
                r.amfi_code,
                r.amc,
                r.scheme_name,
                r.scheme_type,
                r.category,
                r.nav_name,
                r.min_amount,
                r.launch_date,
                r.closure_date,
                r.isin_growth,
                r.isin_reinvest,
            )
            for r in records
        ]
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "master_stage",
                    "amfi_code text, amc text, scheme_name text, scheme_type text, category text, "
                    "nav_name text, min_amount text, launch_date date, closure_date date, "
                    "isin_growth text, isin_reinvest text",
                    _MASTER_STAGE,
                    rows,
                )
                await self._upsert_plan_options(connection, "master_stage", revision_id)
                changed = await self._attributes(
                    connection,
                    "plan_option_master",
                    "SELECT p.id AS plan_option_id, CAST(:snapshot AS date) AS effective_from, "
                    + ", ".join(f"st.{c}" for c in _MASTER)
                    + " FROM master_stage st JOIN wickstreet.plan_option p "
                    "ON p.amfi_code = st.amfi_code"
                    # ponytail: a filled code is never refreshed by its own source again;
                    # track the writing source per row if archive-only codes need updates.
                    + (
                        " WHERE NOT EXISTS (SELECT 1 FROM wickstreet.plan_option_master m "
                        "WHERE m.plan_option_id = p.id)"
                        if fill_only
                        else ""
                    ),
                    _MASTER,
                    revision_id,
                    {"snapshot": snapshot},
                )
                if changed == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=changed,
                    superseded=0,
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(revision=revision_id, inserted=changed, superseded=0)

    async def scheme_keys(self) -> tuple[list[SchemeRef], dict[int, str]]:
        """Every listed scheme, and each scheme's current SEBI code from its SSD."""
        async with self._database.engine.connect() as connection:
            schemes = [
                SchemeRef(r.sd_id, r.mf_id, r.name)
                for r in await connection.execute(
                    text("SELECT sd_id, mf_id, name FROM wickstreet.scheme ORDER BY sd_id")
                )
            ]
            codes = {
                r.sd_id: r.txt
                for r in await connection.execute(
                    text(
                        "SELECT DISTINCT ON (sd_id) sd_id, txt FROM wickstreet.scheme_fact "
                        "WHERE name = 'ssd:SEBI_Codes' AND superseded_revision IS NULL "
                        "ORDER BY sd_id, as_of DESC"
                    )
                )
            }
        return schemes, codes

    async def scheme_navs(self, day: date) -> dict[int, list[Decimal]]:
        """Each scheme's plan-option NAVs on ``day``, joined through the master ISINs."""
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT DISTINCT i.sd_id, n.nav FROM wickstreet.nav n "
                    "JOIN wickstreet.plan_option_master m ON m.plan_option_id = n.plan_option_id "
                    "AND m.superseded_revision IS NULL "
                    "JOIN wickstreet.scheme_isin i ON i.isin IN (m.isin_growth, m.isin_reinvest) "
                    "WHERE n.nav_date = :d AND n.superseded_revision IS NULL AND n.nav > 0"
                ),
                {"d": day},
            )
            found: dict[int, list[Decimal]] = {}
            for row in rows:
                found.setdefault(row.sd_id, []).append(row.nav)
        return found

    async def active_scheme_names(self, since: date) -> list[str]:
        """Master scheme names of plan-options with a current NAV on or after ``since``."""
        async with self._database.engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT DISTINCT m.scheme_name FROM wickstreet.plan_option_master m "
                    "WHERE m.superseded_revision IS NULL AND EXISTS (SELECT 1 FROM "
                    "wickstreet.nav n WHERE n.plan_option_id = m.plan_option_id "
                    "AND n.nav_date >= :d AND n.superseded_revision IS NULL)"
                ),
                {"d": since},
            )
            return [row.scheme_name for row in rows]

    async def latest_nav_day(self, on_or_before: date) -> date | None:
        """The latest business day on or before ``on_or_before`` with current NAVs.

        Liquid and overnight funds file NAVs on weekends and holidays too, so a day counts
        only when it has at least half the NAVs of the busiest day in the 10 days before.
        """
        async with self._database.engine.connect() as connection:
            found: date | None = await connection.scalar(
                text(
                    "WITH days AS (SELECT nav_date, count(*) AS n FROM wickstreet.nav "
                    "WHERE nav_date <= :d AND nav_date > :d - 10 "
                    "AND superseded_revision IS NULL GROUP BY nav_date) "
                    "SELECT max(nav_date) FROM days WHERE n * 2 >= (SELECT max(n) FROM days)"
                ),
                {"d": on_or_before},
            )
        return found

    async def publish_facts(
        self,
        run_id: int,
        found: SchemeFacts,
        provenance: Provenance,
        schemes: Sequence[SchemeRef] = (),
    ) -> Published:
        """Publish schemes, ISIN joins and facts as revision R, or mark the run unchanged.

        A fact with a different value for a stored key supersedes it. Scheme names and
        ISIN joins are kept as last listed.
        """
        facts = [(f.sd_id, f.name, f.plan, f.as_of, f.num, f.txt) for f in found.facts]
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                listed = await self._upsert_schemes(connection, schemes, found, revision_id)
                await self._stage(
                    connection,
                    "fact_stage",
                    "sd_id int, name text, plan text, as_of date, num numeric, txt text",
                    ("sd_id", "name", "plan", "as_of", "num", "txt"),
                    facts,
                )
                # A fact for a scheme no list has named yet waits for the next list.
                await connection.execute(
                    text(
                        "DELETE FROM fact_stage s WHERE NOT EXISTS "
                        "(SELECT 1 FROM wickstreet.scheme c WHERE c.sd_id = s.sd_id)"
                    )
                )
                key = (
                    "t.sd_id = s.sd_id AND t.name = s.name AND t.plan = s.plan "
                    "AND t.as_of = s.as_of AND t.superseded_revision IS NULL"
                )
                superseded = await connection.execute(
                    text(
                        f"UPDATE wickstreet.scheme_fact t SET superseded_revision = :r "
                        f"FROM fact_stage s WHERE {key} AND (t.num IS DISTINCT FROM s.num "
                        "OR t.txt IS DISTINCT FROM s.txt)"
                    ),
                    {"r": revision_id},
                )
                inserted = await connection.execute(
                    text(
                        "INSERT INTO wickstreet.scheme_fact "
                        "(sd_id, name, plan, as_of, num, txt, revision_id) "
                        "SELECT s.sd_id, s.name, s.plan, s.as_of, s.num, s.txt, "
                        "CAST(:r AS bigint) FROM fact_stage s WHERE NOT EXISTS "
                        f"(SELECT 1 FROM wickstreet.scheme_fact t WHERE {key})"
                    ),
                    {"r": revision_id},
                )
                if inserted.rowcount == 0 and listed == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(facts),
                    inserted=int(inserted.rowcount) + listed,
                    superseded=int(superseded.rowcount),
                    anomalies=found.unmatched,
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(
            int(revision_id), int(inserted.rowcount) + listed, int(superseded.rowcount)
        )

    async def _upsert_schemes(
        self,
        connection: AsyncConnection,
        schemes: Sequence[SchemeRef],
        found: SchemeFacts,
        revision_id: int,
    ) -> int:
        """Write new or renamed schemes and new or moved ISIN and code joins; return how many."""
        changed = 0
        if schemes:
            result = await connection.execute(
                text(
                    "INSERT INTO wickstreet.scheme (sd_id, mf_id, name, revision_id) "
                    "SELECT * FROM unnest(CAST(:ids AS int[]), CAST(:mfs AS int[]), "
                    "CAST(:names AS text[]), CAST(:rs AS bigint[])) "
                    "ON CONFLICT (sd_id) DO UPDATE SET mf_id = excluded.mf_id, "
                    "name = excluded.name, revision_id = excluded.revision_id "
                    "WHERE (scheme.mf_id, scheme.name) IS DISTINCT FROM "
                    "(excluded.mf_id, excluded.name)"
                ),
                {
                    "ids": [s.sd_id for s in schemes],
                    "mfs": [s.mf_id for s in schemes],
                    "names": [s.name for s in schemes],
                    "rs": [revision_id] * len(schemes),
                },
            )
            changed += int(result.rowcount)
        if found.isins:
            result = await connection.execute(
                text(
                    "INSERT INTO wickstreet.scheme_isin (isin, sd_id, revision_id) "
                    "SELECT i, s, CAST(:r AS bigint) FROM unnest(CAST(:isins AS text[]), "
                    "CAST(:ids AS int[])) AS u(i, s) "
                    "WHERE EXISTS (SELECT 1 FROM wickstreet.scheme c WHERE c.sd_id = u.s) "
                    "ON CONFLICT (isin) DO UPDATE SET sd_id = excluded.sd_id, "
                    "revision_id = excluded.revision_id "
                    "WHERE scheme_isin.sd_id IS DISTINCT FROM excluded.sd_id"
                ),
                {"isins": list(found.isins), "ids": list(found.isins.values()), "r": revision_id},
            )
            changed += int(result.rowcount)
        if found.codes:
            # A code the SSD lists joins through that plan-option's master ISINs. Where an
            # SSD lists the ISIN for another scheme, one of the two AMC filings is wrong:
            # the code's scheme wins only when the plan-option's name contains its name
            # and not the other scheme's.
            result = await connection.execute(
                text(
                    "INSERT INTO wickstreet.scheme_isin (isin, sd_id, revision_id) "
                    "SELECT DISTINCT ON (x.isin) x.isin, u.s, CAST(:r AS bigint) "
                    "FROM unnest(CAST(:codes AS text[]), CAST(:ids AS int[])) AS u(c, s) "
                    "JOIN wickstreet.plan_option p ON p.amfi_code = u.c "
                    "JOIN wickstreet.plan_option_master m ON m.plan_option_id = p.id "
                    "AND m.superseded_revision IS NULL "
                    "CROSS JOIN LATERAL (VALUES (m.isin_growth), (m.isin_reinvest)) AS x(isin) "
                    "WHERE x.isin IS NOT NULL "
                    "AND EXISTS (SELECT 1 FROM wickstreet.scheme c WHERE c.sd_id = u.s) "
                    "ORDER BY x.isin, u.s ON CONFLICT (isin) DO UPDATE "
                    "SET sd_id = excluded.sd_id, revision_id = excluded.revision_id "
                    "WHERE scheme_isin.sd_id <> excluded.sd_id AND EXISTS (SELECT 1 "
                    "FROM wickstreet.plan_option_master m "
                    "JOIN wickstreet.scheme a ON a.sd_id = excluded.sd_id "
                    "JOIN wickstreet.scheme b ON b.sd_id = scheme_isin.sd_id "
                    "WHERE m.superseded_revision IS NULL "
                    "AND excluded.isin IN (m.isin_growth, m.isin_reinvest) "
                    f"AND position({compacted('a.name')} in {compacted('m.nav_name')}) > 0 "
                    f"AND position({compacted('b.name')} in {compacted('m.nav_name')}) = 0)"
                ),
                {"codes": list(found.codes), "ids": list(found.codes.values()), "r": revision_id},
            )
            changed += int(result.rowcount)
        return changed

    async def publish_portfolios(
        self, run_id: int, found: Portfolios, provenance: Provenance
    ) -> Published:
        """Publish changed portfolios as revision R, or mark the run unchanged.

        A portfolio is one scheme on one date. When its filed lines differ in any way
        from the current ones, every current line is superseded and the new set inserted.
        """
        columns = (
            "sd_id",
            "as_of",
            "seq",
            "name",
            "isin",
            "industry",
            "section",
            "asset",
            "quantity",
            "value",
            "weight",
        )
        rows = [
            (h.sd_id, h.as_of, h.seq, h.name, h.isin, h.industry, h.section, h.asset)
            + (h.quantity, h.value, h.weight)
            for h in found.holdings
        ]
        listed = ", ".join(columns)
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "holding_stage",
                    "sd_id int, as_of date, seq int, name text, isin text, industry text, "
                    "section text, asset text, quantity numeric, value numeric, weight numeric",
                    columns,
                    rows,
                )
                current = (
                    f"SELECT {listed} FROM wickstreet.holding h WHERE h.superseded_revision "
                    "IS NULL AND (h.sd_id, h.as_of) IN (SELECT sd_id, as_of FROM holding_stage)"
                )
                await connection.execute(
                    text(
                        "CREATE TEMPORARY TABLE holding_changed ON COMMIT DROP AS "
                        f"SELECT DISTINCT sd_id, as_of FROM ((SELECT {listed} FROM holding_stage "
                        f"EXCEPT {current}) UNION ALL ({current} EXCEPT SELECT {listed} "
                        "FROM holding_stage)) d"
                    )
                )
                superseded = await connection.execute(
                    text(
                        "UPDATE wickstreet.holding h SET superseded_revision = :r "
                        "FROM holding_changed c WHERE h.sd_id = c.sd_id AND h.as_of = c.as_of "
                        "AND h.superseded_revision IS NULL"
                    ),
                    {"r": revision_id},
                )
                inserted = await connection.execute(
                    text(
                        f"INSERT INTO wickstreet.holding ({listed}, revision_id) "
                        f"SELECT {', '.join('s.' + c for c in columns)}, CAST(:r AS bigint) "
                        "FROM holding_stage s JOIN holding_changed c "
                        "ON c.sd_id = s.sd_id AND c.as_of = s.as_of"
                    ),
                    {"r": revision_id},
                )
                if inserted.rowcount == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=int(inserted.rowcount),
                    superseded=int(superseded.rowcount),
                    anomalies=len(found.unmatched),
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(int(revision_id), int(inserted.rowcount), int(superseded.rowcount))

    async def publish_market_caps(
        self, run_id: int, found: Sequence[CapClass], provenance: Provenance
    ) -> Published:
        """Publish AMFI's market-cap classes for one period as revision R."""
        rows = [(c.isin, c.as_of, c.name, c.market_cap_cr, c.cap_class) for c in found]
        key = "t.isin = s.isin AND t.as_of = s.as_of AND t.superseded_revision IS NULL"
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "cap_stage",
                    "isin text, as_of date, name text, market_cap_cr numeric, cap_class text",
                    ("isin", "as_of", "name", "market_cap_cr", "cap_class"),
                    rows,
                )
                await connection.execute(
                    text(
                        "DELETE FROM cap_stage a USING cap_stage b WHERE a.ctid > b.ctid "
                        "AND a.isin = b.isin AND a.as_of = b.as_of"
                    )
                )
                superseded = await connection.execute(
                    text(
                        f"UPDATE wickstreet.security_class t SET superseded_revision = :r "
                        f"FROM cap_stage s WHERE {key} AND (t.cap_class, t.market_cap_cr, t.name) "
                        "IS DISTINCT FROM (s.cap_class, s.market_cap_cr, s.name)"
                    ),
                    {"r": revision_id},
                )
                inserted = await connection.execute(
                    text(
                        "INSERT INTO wickstreet.security_class "
                        "(isin, as_of, name, market_cap_cr, cap_class, revision_id) "
                        "SELECT s.isin, s.as_of, s.name, s.market_cap_cr, s.cap_class, "
                        "CAST(:r AS bigint) FROM cap_stage s WHERE NOT EXISTS "
                        f"(SELECT 1 FROM wickstreet.security_class t WHERE {key})"
                    ),
                    {"r": revision_id},
                )
                if inserted.rowcount == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=int(inserted.rowcount),
                    superseded=int(superseded.rowcount),
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(int(revision_id), int(inserted.rowcount), int(superseded.rowcount))

    async def publish_distributions(
        self, run_id: int, found: Sequence[Distribution], provenance: Provenance
    ) -> Published:
        """Publish IDCW payouts as revision R; a payout of an unknown code is skipped."""
        rows = [(d.amfi_code, d.record_date, d.per_unit) for d in found]
        key = (
            "t.plan_option_id = s.plan_option_id AND t.record_date = s.record_date "
            "AND t.superseded_revision IS NULL"
        )
        try:
            async with self._database.engine.begin() as connection:
                revision_id = await self._revision(connection, run_id, provenance)
                await self._stage(
                    connection,
                    "idcw_stage",
                    "amfi_code text, record_date date, per_unit numeric",
                    ("amfi_code", "record_date", "per_unit"),
                    rows,
                )
                await connection.execute(
                    text(
                        "CREATE TEMPORARY TABLE idcw_keyed ON COMMIT DROP AS SELECT p.id AS "
                        "plan_option_id, s.record_date, s.per_unit FROM idcw_stage s "
                        "JOIN wickstreet.plan_option p ON p.amfi_code = s.amfi_code"
                    )
                )
                superseded = await connection.execute(
                    text(
                        f"UPDATE wickstreet.distribution t SET superseded_revision = :r "
                        f"FROM idcw_keyed s WHERE {key} AND t.per_unit <> s.per_unit"
                    ),
                    {"r": revision_id},
                )
                inserted = await connection.execute(
                    text(
                        "INSERT INTO wickstreet.distribution "
                        "(plan_option_id, record_date, per_unit, revision_id) "
                        "SELECT s.plan_option_id, s.record_date, s.per_unit, CAST(:r AS bigint) "
                        "FROM idcw_keyed s WHERE NOT EXISTS "
                        f"(SELECT 1 FROM wickstreet.distribution t WHERE {key})"
                    ),
                    {"r": revision_id},
                )
                if inserted.rowcount == 0:
                    raise _NothingChangedError
                await self._point(connection, revision_id)
                await self._finish(
                    connection,
                    run_id,
                    "published",
                    raw_sha256=provenance.raw_sha256,
                    revision_id=revision_id,
                    rows=len(rows),
                    inserted=int(inserted.rowcount),
                    superseded=int(superseded.rowcount),
                )
        except _NothingChangedError:
            await self.close_run(run_id, "unchanged", raw_sha256=provenance.raw_sha256)
            return Published(revision=None, inserted=0, superseded=0)
        return Published(int(revision_id), int(inserted.rowcount), int(superseded.rowcount))
