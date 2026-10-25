"""MF ingestion on synthetic AMFI files, as the runtime role (ADR-017 MF-5 to MF-10, OM-4)."""

from __future__ import annotations

import gzip
import io
import time
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from platform_common.database import Database
from tests.wickstreet.amfi_files import master_file, nav_file
from tests.wickstreet.archive_files import (
    archive_file,
    mfapi_adapter,
    mfapi_file,
    snapshot_file,
    tigzig_adapter,
)
from tests.wickstreet.conftest import Urls
from tests.wickstreet.test_mf_facts import _xlsx
from tests.wickstreet.test_mf_holdings import HEADER
from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.data_rights.infrastructure.register import SqlRightsRegister, record_grants
from wickstreet.mf_data.application.facts import IngestFacts
from wickstreet.mf_data.application.ingest import (
    Backfill,
    CrossCheck,
    DailyRefresh,
    ImportArchive,
    IngestNavDay,
    IngestSchemeMaster,
    Outcome,
    Reparse,
)
from wickstreet.mf_data.application.portfolios import IngestPortfolios
from wickstreet.mf_data.domain.model import (
    AMFI,
    MFAPI,
    TIGZIG,
    Fact,
    Holding,
    NavRecord,
    Portfolios,
    RawFile,
    SchemeFacts,
    SchemeRef,
)
from wickstreet.mf_data.domain.ports import Provenance, SourceError
from wickstreet.mf_data.infrastructure.amc import manual_sources
from wickstreet.mf_data.infrastructure.amfi import parse_nav_file, parse_scheme_master
from wickstreet.mf_data.infrastructure.raw_store import FileRawStore
from wickstreet.mf_data.infrastructure.store import SqlMfStore
from wickstreet.mf_data.infrastructure.tigzig import ARCHIVE_URL

D1 = date(2026, 9, 1)


def day(n: int) -> date:
    return D1 + timedelta(days=n - 1)


class FakeSource:
    """Serves synthetic files; records every fetch."""

    name = AMFI
    adapter_version = "fake-1"

    def __init__(self, files: dict[date, bytes], master: bytes = master_file(["10001"])) -> None:
        self.files = files
        self.master = master
        self.fetches: list[object] = []

    async def nav_day(self, on: date) -> RawFile | None:
        self.fetches.append(on)
        content = self.files.get(on)
        return None if content is None else RawFile(f"fake://nav/{on}", datetime.now(UTC), content)

    async def scheme_master(self) -> RawFile:
        self.fetches.append("master")
        return RawFile("fake://master", datetime.now(UTC), self.master)

    def parse_nav(self, raw: RawFile) -> list[Any]:
        return parse_nav_file(raw.content)

    def parse_schemes(self, raw: RawFile) -> list[Any]:
        return parse_scheme_master(raw.content)


@dataclass
class Pipeline:
    store: SqlMfStore
    days: IngestNavDay
    master: IngestSchemeMaster
    backfill: Backfill
    source: FakeSource

    def refresh(self, lookback: int) -> DailyRefresh:
        return DailyRefresh(self.days, self.master, self.store, lookback)


@pytest.fixture
async def granted(mf_urls: Urls) -> AsyncIterator[None]:
    """The owner records retrieval and storage for AMFI in personal mode."""
    owner = Database(mf_urls.owner)
    await record_grants(
        owner,
        source=AMFI,
        mode="personal",
        uses=[Use.AUTOMATED_RETRIEVAL, Use.STORAGE],
        basis="test grant",
        granted_by="tests",
    )
    await owner.dispose()
    yield


def _pipeline(database: Database, raw_root: Path, source: FakeSource) -> Pipeline:
    store = SqlMfStore(database)
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    raw = FileRawStore(raw_root)
    days = IngestNavDay(source, store, raw, rights, Decimal("0.25"))
    master = IngestSchemeMaster(source, store, raw, rights)
    return Pipeline(store, days, master, Backfill(days, master, store, source, rights), source)


async def _rows(database: Database, sql: str, **params: Any) -> list[tuple[Any, ...]]:
    async with database.engine.connect() as connection:
        return [tuple(r) for r in (await connection.execute(text(sql), params)).all()]


async def _visible_at(database: Database, revision: int) -> dict[str, Decimal | None]:
    """NAVs visible at a revision: the MF-5 rule."""
    rows = await _rows(
        database,
        "SELECT p.amfi_code, n.nav FROM wickstreet.nav n "
        "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
        "WHERE n.revision_id <= :r "
        "AND (n.superseded_revision IS NULL OR n.superseded_revision > :r)",
        r=revision,
    )
    return dict(rows)


async def test_without_a_grant_nothing_is_fetched(app_database: Database, tmp_path: Path) -> None:
    """OM-4: the gate is closed, so the adapter is never called."""
    source = FakeSource({day(1): nav_file(day(1), {"10001": "10"})})
    pipeline = _pipeline(app_database, tmp_path, source)
    with pytest.raises(RightsDeniedError):
        await pipeline.days.execute(day(1))
    assert source.fetches == []
    assert await _rows(app_database, "SELECT status FROM wickstreet.ingestion_run") == [("denied",)]


async def test_a_day_publishes_one_revision_with_its_provenance(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    source = FakeSource({day(1): nav_file(day(1), {"10001": "10.5000", "10002": "20"})})
    outcome = await _pipeline(app_database, tmp_path, source).days.execute(day(1))
    assert (outcome.status, outcome.inserted, outcome.superseded) == ("published", 2, 0)
    assert await _rows(app_database, "SELECT revision_id FROM wickstreet.publication") == [
        (outcome.revision,)
    ]
    assert await _visible_at(app_database, outcome.revision or 0) == {
        "10001": Decimal("10.5000"),
        "10002": Decimal("20"),
    }
    ((path, sha, retrieval, storage),) = await _rows(
        app_database,
        "SELECT raw_path, raw_sha256, retrieval_grant_id, storage_grant_id "
        "FROM wickstreet.revision",
    )
    assert Path(path).is_file() and len(sha) == 64 and retrieval != storage


async def test_an_unchanged_file_writes_no_revision(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    pipeline = _pipeline(
        app_database, tmp_path, FakeSource({day(1): nav_file(day(1), {"10001": "10"})})
    )
    await pipeline.days.execute(day(1))
    again = await pipeline.days.execute(day(1), refetch=True)
    skipped = await pipeline.days.execute(day(1))
    assert (again.status, skipped.status) == ("unchanged", "skipped")
    assert await _rows(app_database, "SELECT count(*) FROM wickstreet.revision") == [(1,)]


async def test_a_correction_supersedes_the_old_value_and_keeps_it(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    source = FakeSource({day(1): nav_file(day(1), {"10001": "10", "10002": "20"})})
    pipeline = _pipeline(app_database, tmp_path, source)
    first = await pipeline.days.execute(day(1))
    source.files[day(1)] = nav_file(day(1), {"10001": "10.0000", "10002": "21"})
    second = await pipeline.days.execute(day(1), refetch=True)
    assert (second.status, second.inserted, second.superseded) == ("published", 1, 1)
    assert await _visible_at(app_database, first.revision or 0) == {
        "10001": Decimal("10"),
        "10002": Decimal("20"),
    }
    assert (await _visible_at(app_database, second.revision or 0))["10002"] == Decimal("21")
    assert await _rows(app_database, "SELECT count(*) FROM wickstreet.nav") == [(3,)]


async def test_a_blocked_file_publishes_nothing(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    content = nav_file(day(1), {"10001": "10"}) + b"10001;X;Direct Plan;Growth;;;11;01-Sep-2026\r\n"
    outcome = await _pipeline(app_database, tmp_path, FakeSource({day(1): content})).days.execute(
        day(1)
    )
    assert outcome.status == "failed" and "different values" in (outcome.error or "")
    for table in ("nav", "revision", "publication", "plan_option"):
        assert await _rows(app_database, f"SELECT count(*) FROM wickstreet.{table}") == [(0,)]


async def test_anomalies_are_stored_as_filed_with_a_flag(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    source = FakeSource(
        {
            day(1): nav_file(day(1), {"10001": "10", "10002": "5"}),
            day(2): nav_file(day(2), {"10001": "20", "10002": "0", "10003": "N.A."}),
        }
    )
    pipeline = _pipeline(app_database, tmp_path, source)
    await pipeline.days.execute(day(1))
    outcome = await pipeline.days.execute(day(2))
    assert outcome.anomalies == 3
    assert await _rows(
        app_database,
        "SELECT p.amfi_code, n.nav, n.anomaly FROM wickstreet.nav n "
        "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
        "WHERE n.nav_date = :d ORDER BY 1",
        d=day(2),
    ) == [
        ("10001", Decimal("20"), "nav_jump"),
        ("10002", Decimal("0"), "nav_zero"),
        ("10003", None, "nav_missing"),
    ]


async def test_attributes_are_effective_dated(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    source = FakeSource(
        {
            day(1): nav_file(day(1), {"10001": "10"}, names={"10001": "Old Name"}),
            day(2): nav_file(day(2), {"10001": "10"}, names={"10001": "New Name"}),
        }
    )
    pipeline = _pipeline(app_database, tmp_path, source)
    await pipeline.days.execute(day(1))
    await pipeline.days.execute(day(2))
    source.files[day(1)] = source.files[day(1)] + b"\r\n"  # re-read: same rows, new hash
    assert (await pipeline.days.execute(day(1), refetch=True)).status == "unchanged"
    assert await _rows(
        app_database,
        "SELECT effective_from, nav_name FROM wickstreet.plan_option_listing "
        "WHERE superseded_revision IS NULL ORDER BY effective_from",
    ) == [(day(1), "Old Name"), (day(2), "New Name")]


async def test_the_backfill_records_the_unserved_range_and_resumes(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    files = {day(n): nav_file(day(n), {"10001": str(10 + n)}) for n in (4, 5, 6)}
    pipeline = _pipeline(app_database, tmp_path, FakeSource(files))
    summary = await pipeline.backfill.execute(day(1), day(6), today=day(7))
    assert summary.first_served == day(4)
    assert summary.statuses == {"published": 4}  # the master and three dates
    assert await _rows(
        app_database,
        "SELECT period_start, period_end FROM wickstreet.ingestion_run "
        "WHERE status = 'unavailable'",
    ) == [(day(1), day(3))]
    again = await pipeline.backfill.execute(day(1), day(6), today=day(7))
    assert again.statuses == {"skipped": 4}
    assert await _rows(app_database, "SELECT count(*) FROM wickstreet.revision") == [(4,)]


async def test_the_daily_refresh_starts_after_the_last_stored_date(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    files = {day(n): nav_file(day(n), {"10001": str(10 + n)}) for n in range(1, 7)}
    pipeline = _pipeline(app_database, tmp_path, FakeSource(files))
    await pipeline.days.execute(day(1))
    await pipeline.days.execute(day(2))
    pipeline.source.fetches.clear()
    summary = await pipeline.refresh(lookback=2).execute(today=day(6))
    assert pipeline.source.fetches == ["master", day(3), day(4), day(5)]
    assert summary.statuses == {"published": 4}
    assert await _rows(
        app_database,
        "SELECT status FROM wickstreet.ingestion_run WHERE dataset = 'daily-refresh'",
    ) == [("completed",)]


async def test_one_runner_at_a_time(app_database: Database) -> None:
    store = SqlMfStore(app_database)
    async with store.exclusive() as first, store.exclusive() as second:
        assert (first, second) == (True, False)
    async with store.exclusive() as later:
        assert later


async def test_the_runtime_role_cannot_grant_itself_rights(app_database: Database) -> None:
    with pytest.raises(DBAPIError, match="permission denied"):
        await record_grants(
            app_database,
            source=AMFI,
            mode="personal",
            uses=[Use.STORAGE],
            basis="self-granted",
            granted_by="app",
        )


async def test_the_app_schedules_the_refresh_and_catches_up(
    mf_settings: WickstreetSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[date] = []

    class Stub:
        class store:  # noqa: N801
            @staticmethod
            async def run_status(*args: object) -> str | None:
                return None

        class refresh:  # noqa: N801
            @staticmethod
            async def execute(today: date) -> Any:
                calls.append(today)
                raise RuntimeError("stub refresh")

        @staticmethod
        async def aclose() -> None:
            return None

    monkeypatch.setattr("wickstreet.app.build_ingestion", lambda settings, database: Stub)
    computed: list[bool] = []

    class Analytics:
        class compute:  # noqa: N801
            @staticmethod
            async def execute() -> Any:
                computed.append(True)
                return SimpleNamespace(status="current", revision=None)

        class research:  # noqa: N801
            @staticmethod
            async def warm() -> None:
                return None

    monkeypatch.setattr("wickstreet.app.build_analytics", lambda settings, database: Analytics)
    monkeypatch.setattr("wickstreet.app.refresh_due", lambda now, completed_today: True)
    settings = mf_settings.model_copy(update={"refresh_enabled": True})
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        deadline = time.monotonic() + 3
        while not computed and time.monotonic() < deadline:
            client.get("/me")
            time.sleep(0.05)
    assert len(calls) == 1  # a failed refresh is logged; the app keeps serving
    assert computed == [True]  # the snapshot step still runs after it


async def _grant(urls: Urls, source: str) -> None:
    owner = Database(urls.owner)
    await record_grants(
        owner,
        source=source,
        mode="personal",
        uses=[Use.AUTOMATED_RETRIEVAL, Use.STORAGE],
        basis="test grant",
        granted_by="tests",
    )
    await owner.dispose()


async def test_the_archive_is_the_record_before_the_cutoff_and_a_fill_after(
    app_database: Database, mf_urls: Urls, tmp_path: Path, granted: None
) -> None:
    """ADR-023 U11: AMFI wins from its first date; the archive fills gaps and counts conflicts."""
    await _grant(mf_urls, TIGZIG)
    amfi = _pipeline(
        app_database,
        tmp_path,
        FakeSource(
            {day(5): nav_file(day(5), {"10001": "10", "10002": "20"})},
            master=master_file(["10001", "10002"]),
        ),
    )
    await amfi.master.execute(day(11))
    await amfi.days.execute(day(5))
    store, raw = SqlMfStore(app_database), FileRawStore(tmp_path)
    assert await store.first_nav_day(AMFI) == day(5)
    rows = [("10001", day(3), "9.0000"), ("10001", day(4), "9.5000")]
    rows += [("10001", day(5), "10.0000"), ("10002", day(5), "21.0000")]
    rows += [("10003", day(5), "30.0000"), ("10001", day(12), "11.0000")]
    rows += [("10004", day(3), "10.0000"), ("10004", day(4), "20.0000")]
    source = tigzig_adapter(
        tmp_path / "work", archive_file(rows), snapshot_file(["10001", "10003"])
    )
    rights = RightsGate(SqlRightsRegister(app_database, "personal"))
    master = IngestSchemeMaster(source, store, raw, rights, fill_only=True)
    importer = ImportArchive(source, store, raw, rights, master, Decimal("0.25"))
    outcomes: list[Outcome] = []
    await importer.execute(day(1), day(10), day(5), day(11), outcomes.append)

    assert [(o.period, o.status, o.inserted, o.anomalies, o.conflicts) for o in outcomes] == [
        (day(11), "published", 1, 0, 0),  # the snapshot adds 10003 only
        (day(1), "published", 4, 1, 0),  # the record before the cutoff
        (day(5), "published", 1, 0, 1),  # fills 10003; 10002 differs and is kept
    ]
    assert dict(
        await _rows(
            app_database,
            "SELECT p.amfi_code, n.nav FROM wickstreet.nav n JOIN wickstreet.plan_option p "
            "ON p.id = n.plan_option_id WHERE n.nav_date = :d AND n.superseded_revision IS NULL",
            d=day(5),
        )
    ) == {"10001": Decimal("10"), "10002": Decimal("20"), "10003": Decimal("30.0000")}
    assert await _rows(
        app_database,
        "SELECT p.amfi_code, n.anomaly FROM wickstreet.nav n JOIN wickstreet.plan_option p "
        "ON p.id = n.plan_option_id WHERE n.anomaly IS NOT NULL",
    ) == [("10004", "nav_jump")]
    assert await _rows(
        app_database,
        "SELECT r.period_start, r.period_end, v.url FROM wickstreet.ingestion_run r "
        "JOIN wickstreet.revision v ON v.run_id = r.id "
        "WHERE r.source = 'tigzig' AND r.dataset = 'nav-v1' ORDER BY 1",
    ) == [(day(1), day(4), ARCHIVE_URL), (day(5), day(10), ARCHIVE_URL)]
    assert await _rows(
        app_database,
        "SELECT p.amfi_code, m.amc FROM wickstreet.plan_option_master m "
        "JOIN wickstreet.plan_option p ON p.id = m.plan_option_id ORDER BY 1",
    ) == [
        ("10001", "Example AMC Limited"),
        ("10002", "Example AMC Limited"),
        ("10003", "Example AMC"),
    ]
    again = await importer.execute(day(1), day(10), day(5), day(11))
    assert again.statuses == {"skipped": 3}

    # AMFI corrects 10002 to the archive's value: the same archive now has no conflict.
    amfi.source.files[day(5)] = nav_file(day(5), {"10001": "10", "10002": "21"})
    await amfi.days.execute(day(5), refetch=True)
    rechecked: list[Outcome] = []
    await importer.execute(day(1), day(10), day(5), day(11), rechecked.append, refetch=True)
    assert [(o.period, o.status, o.rows, o.conflicts) for o in rechecked[1:]] == [
        (day(1), "unchanged", 0, 0),  # same file, record month: not re-read
        (day(5), "unchanged", 3, 0),  # fill month: rechecked against the store
    ]


async def test_the_cross_check_measures_the_store_and_publishes_nothing(
    app_database: Database, mf_urls: Urls, tmp_path: Path, granted: None
) -> None:
    await _grant(mf_urls, MFAPI)
    files = {day(1): nav_file(day(1), {"10001": "10"}), day(2): nav_file(day(2), {"10001": "11"})}
    amfi = _pipeline(app_database, tmp_path, FakeSource(files))
    await amfi.days.execute(day(1))
    await amfi.days.execute(day(2))
    store = SqlMfStore(app_database)
    assert await store.sample_codes(5, day(1), day(10)) == ["10001"]
    reference = mfapi_adapter(
        {"10001": mfapi_file({day(1): "10.00001", day(2): "11.5", day(3): "12"})}
    )
    check = CrossCheck(
        reference,
        store,
        FileRawStore(tmp_path),
        RightsGate(SqlRightsRegister(app_database, "personal")),
    )
    before = await _rows(app_database, "SELECT count(*) FROM wickstreet.revision")
    (result,) = await check.execute(["10001"], day(1), day(10), day(11))
    assert (result.matched, result.differing, result.reference_only, result.stored_only) == (
        1,
        1,
        1,
        0,
    )
    assert await _rows(app_database, "SELECT count(*) FROM wickstreet.revision") == before


class OldParser(FakeSource):
    """The adapter before the fix: a NAV written with a bare point is not a number."""

    adapter_version = "fake-0"

    def parse_nav(self, raw: RawFile) -> list[Any]:
        records: list[NavRecord] = parse_nav_file(raw.content)
        return [replace(r, nav=None) if r.amfi_code == "10002" else r for r in records]


async def test_a_reparse_corrects_stored_values_from_the_kept_raw_file(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    """A parser fix becomes a new revision; the old value stays as history (MF-5, MF-9)."""
    files = {day(1): nav_file(day(1), {"10001": "10", "10002": "222."})}
    old = _pipeline(app_database, tmp_path, OldParser(files))
    first = await old.days.execute(day(1))
    fixed = FakeSource({})  # the network is never used
    pipeline = _pipeline(app_database, tmp_path, fixed)
    summary = await Reparse(pipeline.days, pipeline.store).execute(day(1), day(2))
    assert dict(summary.statuses) == {"published": 1, "skipped": 1}  # day 2 has no run
    assert fixed.fetches == []
    assert await _visible_at(app_database, first.revision or 0) == {
        "10001": Decimal("10"),
        "10002": None,
    }
    latest = await _rows(app_database, "SELECT max(id) FROM wickstreet.revision")
    assert await _visible_at(app_database, latest[0][0]) == {
        "10001": Decimal("10"),
        "10002": Decimal("222"),
    }
    assert await _rows(
        app_database, "SELECT adapter_version FROM wickstreet.revision ORDER BY id"
    ) == [("fake-0",), ("fake-1",)]
    assert await _rows(
        app_database,
        "SELECT count(*) FROM wickstreet.ingestion_run WHERE period_start = :d",
        d=day(2),
    ) == [(0,)]


async def test_a_reparse_refuses_a_raw_file_that_does_not_match_its_hash(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    files = {day(1): nav_file(day(1), {"10001": "10"})}
    pipeline = _pipeline(app_database, tmp_path, FakeSource(files))
    await pipeline.days.execute(day(1))
    ((path,),) = await _rows(app_database, "SELECT raw_path FROM wickstreet.revision")
    Path(path).write_bytes(gzip.compress(b"tampered"))
    outcome = await pipeline.days.reparse(day(1))
    assert outcome.status == "failed" and "SHA-256" in (outcome.error or "")


async def test_ssd_codes_join_plans_and_settle_a_wrongly_listed_isin(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    """An SSD's AMFI codes join through the master's ISINs. A listed ISIN that points at
    another scheme moves only when the plan's name names the code's scheme."""
    source = FakeSource({}, master=master_file(["10001", "10002"]))
    pipeline = _pipeline(app_database, tmp_path, source)
    await pipeline.master.execute(day(1))
    store = pipeline.store
    run = await store.open_run(AMFI, "ssd", day(1), day(1))
    [(grant,)] = await _rows(
        app_database, "SELECT min(id) FROM wickstreet.rights_grant WHERE use = 'storage'"
    )
    provenance = Provenance(
        "fake://ssd", "2026-09-01T00:00:00+00:00", "0" * 64, "x", "f", "c", None, grant
    )
    schemes = [SchemeRef(1, 1, "Example Fund 10001"), SchemeRef(2, 1, "Example Fund 10002")]
    found = SchemeFacts(
        [],
        isins={"INF000X10001": 2, "INF000X10002": 2},  # the first is filed under the wrong scheme
        codes={"10001": 1, "10002": 1},  # the second is filed under the wrong scheme
    )
    assert (await store.publish_facts(run.id, found, provenance, schemes)).revision is not None
    assert dict(await _rows(app_database, "SELECT isin, sd_id FROM wickstreet.scheme_isin")) == {
        "INF000X10001": 1,  # moved: "Example Fund 10001 - Direct Plan - Growth" names scheme 1
        "INF000Y10001": 1,  # joined by code
        "INF000X10002": 2,  # kept: the plan's name does not name scheme 1
        "INF000Y10002": 1,  # joined by code; nothing listed it
    }


async def test_an_isin_two_ssds_list_joins_the_scheme_its_plan_name_names(
    app_database: Database, tmp_path: Path, granted: None
) -> None:
    """AMFI can serve one SSD under two scheme ids. The plan's NAV name settles the
    ISIN, whatever order the documents came in; a tie leaves the join as it was."""
    source = FakeSource({}, master=master_file(["10001", "10002"]))
    pipeline = _pipeline(app_database, tmp_path, source)
    await pipeline.master.execute(day(1))
    store = pipeline.store
    [(grant,)] = await _rows(
        app_database, "SELECT min(id) FROM wickstreet.rights_grant WHERE use = 'storage'"
    )
    provenance = Provenance(
        "fake://ssd", "2026-09-01T00:00:00+00:00", "0" * 64, "x", "f", "c", None, grant
    )
    schemes = [
        SchemeRef(1, 1, "Example Fund 10001"),
        SchemeRef(3, 1, "Master Equity Plan Unit Scheme"),
        SchemeRef(4, 1, "Example Fund"),
    ]
    run = await store.open_run(AMFI, "ssd", day(1), day(1))
    wrong = SchemeFacts([], isins={"INF000X10001": 3, "INF000X10002": 3, "INF000Y10001": 3})
    assert (await store.publish_facts(run.id, wrong, provenance, schemes)).revision is not None
    run = await store.open_run(AMFI, "ssd", day(2), day(2))
    contested = SchemeFacts(
        [],
        contested={"INF000X10001": (1, 3), "INF000X10002": (3, 4), "INF000Y10001": (1, 4)},
    )
    assert (await store.publish_facts(run.id, contested, provenance, schemes)).revision is not None
    assert dict(await _rows(app_database, "SELECT isin, sd_id FROM wickstreet.scheme_isin")) == {
        "INF000X10001": 1,  # "Example Fund 10001 - Direct Plan - Growth" names 1, not 3
        "INF000X10002": 4,  # "Example Fund 10002 - …" names 4 ("Example Fund"), not 3
        "INF000Y10001": 3,  # it names both 1 and 4: a tie keeps the join as it was
    }


class FakeAmc:
    """One AMC file a month; the parser's asset kind stands for the parser version."""

    name = "fakeamc"
    adapter_version = "fake-1"
    layout_verified = True

    def __init__(self) -> None:
        self.kind = "other"
        self.fetches = 0
        self.codes: list[dict[str, int]] = []

    async def portfolio(self, month_end: date) -> RawFile | None:
        self.fetches += 1
        return RawFile("fake://amc/2026-09", datetime.now(UTC), b"one file")

    def sheet_codes(self, raw: RawFile, names: Any) -> dict[str, int]:
        return {"S1": 1}

    def parse_portfolios(
        self, raw: RawFile, names: Any, fallback: date | None, codes: Any = None
    ) -> Portfolios:
        self.codes.append(dict(codes or {}))
        line = Holding(
            1,
            D1,
            0,
            "Axis Bank Limited Oct26",
            None,
            "Stock Futures",
            "ARBITRAGE",
            self.kind,
            None,
            None,
            Decimal("-0.5"),
        )
        return Portfolios([line], [])


async def test_a_portfolio_reparse_supersedes_lines_from_the_kept_file(
    app_database: Database, mf_urls: Urls, tmp_path: Path
) -> None:
    owner = Database(mf_urls.owner)
    await record_grants(
        owner,
        source="fakeamc",
        mode="personal",
        uses=[Use.AUTOMATED_RETRIEVAL, Use.STORAGE],
        basis="test",
        granted_by="tests",
    )
    await owner.dispose()
    store = SqlMfStore(app_database)
    run = await store.open_run(AMFI, "scheme-list", D1, D1)
    [(grant,)] = await _rows(app_database, "SELECT min(id) FROM wickstreet.rights_grant")
    provenance = Provenance(
        "fake://list", "2026-09-01T00:00:00+00:00", "1" * 64, "x", "f", "c", None, grant
    )
    await store.publish_facts(
        run.id, SchemeFacts([]), provenance, [SchemeRef(1, 1, "Example Fund")]
    )
    amc = FakeAmc()
    ingest = IngestPortfolios(
        {"fakeamc": amc},
        store,
        FileRawStore(tmp_path),
        RightsGate(SqlRightsRegister(app_database, "personal")),
    )
    assert (await ingest.month("fakeamc", D1)).status == "published"
    amc.kind = "derivative"  # the parser fix
    assert (await ingest.month("fakeamc", D1, refetch=True)).status == "unchanged"
    fixed = await ingest.reparse("fakeamc", D1)
    assert (fixed.status, fixed.superseded, amc.fetches) == ("published", 1, 2)
    # The first parse had no kept file to learn sheet codes from; the reparse had one.
    assert amc.codes == [{}, {"S1": 1}]
    assert await _rows(
        app_database,
        "SELECT asset, superseded_revision IS NULL FROM wickstreet.holding ORDER BY revision_id",
    ) == [("other", False), ("derivative", True)]
    assert (await ingest.reparse("fakeamc", D1 + timedelta(days=31))).status == "skipped"


def _example_month(first: float, second: float, scheme: str = "Example Fund") -> bytes:
    """One month of ``scheme``: two equity lines, as fractions of net assets."""
    return _xlsx(
        [
            ["", scheme],
            ["", "Portfolio as on September 30, 2026"],
            HEADER,
            ["", "EQUITY & EQUITY RELATED"],
            [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 600, first],
            [2, "ICICI Bank Limited", "INE090A01021", "Banks", 100, 400, second],
            ["", "Grand Total", "", "", "", 1000, first + second],
        ]
    )


async def test_a_manual_amc_imports_under_storage_alone_and_refuses_what_it_cannot_trust(
    app_database: Database, mf_urls: Urls, tmp_path: Path
) -> None:
    owner = Database(mf_urls.owner)
    await record_grants(
        owner,
        source="kotak",
        mode="personal",
        uses=[Use.STORAGE],
        basis="test",
        granted_by="tests",
    )
    await owner.dispose()
    store = SqlMfStore(app_database)
    run = await store.open_run(AMFI, "scheme-list", D1, D1)
    [(grant,)] = await _rows(app_database, "SELECT min(id) FROM wickstreet.rights_grant")
    provenance = Provenance(
        "fake://list", "2026-09-01T00:00:00+00:00", "1" * 64, "x", "f", "c", None, grant
    )
    await store.publish_facts(
        run.id,
        SchemeFacts([]),
        provenance,
        [SchemeRef(1, 1, "Example Fund"), SchemeRef(2, 1, "Second Fund")],
    )
    ingest = IngestPortfolios(
        manual_sources(),
        store,
        FileRawStore(tmp_path),
        RightsGate(SqlRightsRegister(app_database, "personal")),
    )
    month = date(2026, 9, 30)

    def downloaded(content: bytes) -> RawFile:
        return RawFile("https://amc.example/sep.xlsx", datetime.now(UTC), content)

    # An unverified layout stores no portfolio that does not reconcile.
    half = await ingest.import_file("kotak", downloaded(_example_month(0.3, 0.2)), month)
    assert half.status == "failed" and "none of its 1 portfolios" in (half.error or "")
    empty = await ingest.import_file("kotak", downloaded(_xlsx([["", "Notes"]])), month)
    assert empty.status == "failed" and "No sheet has an ISIN" in (empty.error or "")
    stranger = _example_month(0.6, 0.4, "Unknown Fund")
    unjoined = await ingest.import_file("kotak", downloaded(stranger), month)
    assert unjoined.status == "failed" and "joined no scheme: Unknown Fund" in (
        unjoined.error or ""
    )
    pdf = await ingest.import_file("kotak", downloaded(b"%PDF-1.7"), month)
    assert pdf.status == "failed" and "Not an XLS, XLSX, CSV or ZIP" in (pdf.error or "")
    cut = await ingest.import_file("kotak", downloaded(_example_month(0.6, 0.4)[:300]), month)
    assert cut.status == "failed" and "cannot be read as a workbook" in (cut.error or "")
    assert await _rows(app_database, "SELECT count(*) FROM wickstreet.holding") == [(0,)]

    # Of two portfolios, the one that reconciles is stored and the other is listed.
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w") as files:
        files.writestr("a.xlsx", _example_month(0.6, 0.4))
        files.writestr("b.xlsx", _example_month(0.3, 0.2, "Second Fund"))
    month_file = downloaded(bundle.getvalue())
    first = await ingest.import_file("kotak", month_file, month)
    assert (first.status, first.rows, first.anomalies) == ("published", 2, 1)
    assert "scheme 2 on 2026-09-30 sums to 50.00%; held back" in (first.error or "")
    assert await _rows(app_database, "SELECT DISTINCT sd_id FROM wickstreet.holding") == [(1,)]
    again = await ingest.import_file("kotak", month_file, month)
    assert again.status == "unchanged"
    # A reparse needs no retrieval grant, and its revision records none.
    assert (await ingest.reparse("kotak", month)).status == "unchanged"
    assert await _rows(
        app_database,
        "SELECT count(*), count(v.retrieval_grant_id) FROM wickstreet.revision v "
        "JOIN wickstreet.ingestion_run r ON r.id = v.run_id WHERE r.source = 'kotak'",
    ) == [(1, 0)]
    unknown = await ingest.import_file("nosuchamc", downloaded(b""), month)
    assert unknown.status == "failed" and "Known: 360one" in (unknown.error or "")
    assert "kotak" in (unknown.error or "")
    with pytest.raises(RightsDeniedError):  # no retrieval grant, so nothing is fetched
        await ingest.month("kotak", date(2026, 8, 31))


async def test_a_manual_amc_never_fetches() -> None:
    sources = manual_sources()
    assert set(sources) == {
        "kotak",
        "hdfc",
        "edelweiss",
        "absl",
        "wealthco",
        "hsbc",
        "franklin",
        "jio",
        "axis",
        "bandhan",
        "mahindra",
        "iti",
        "jm",
        "canara",
        "union",
        "boi",
        "bajaj",
        "360one",
        "shriram",
        "navi",
        "zerodha",
    }
    assert not any(s.layout_verified for s in sources.values())
    for name, source in sources.items():
        with pytest.raises(SourceError, match=f"{name} is manual import only"):
            await source.portfolio(date(2026, 9, 30))


class FakeFacts:
    """A tracking-error file whose join improves between two parses (a join fix)."""

    name = "fakefacts"
    adapter_version = "fake-1"

    def __init__(self) -> None:
        self.names_seen: list[int] = []
        self.fetches = 0

    async def tracking_error(self, day: date) -> RawFile:
        self.fetches += 1
        return RawFile("fake://te", datetime.now(UTC), b"one file")

    async def ter_month(self, month: date) -> RawFile:
        self.fetches += 1
        return RawFile("fake://ter", datetime.now(UTC), b"one month")

    def parse_ter(self, raw: RawFile, codes: Any, names: Any) -> SchemeFacts:
        self.names_seen.append(len(names))
        return SchemeFacts([Fact(1, "ter", "direct", D1, num=Decimal(len(self.names_seen)))])

    def parse_tracking_error(self, raw: RawFile, day: date, names: Any) -> SchemeFacts:
        self.names_seen.append(len(names))
        value = Decimal("0.05") if len(self.names_seen) == 1 else Decimal("0.04")
        return SchemeFacts([Fact(1, "tracking_error", "direct", day, num=value)])


async def test_a_facts_reparse_supersedes_from_the_kept_file_and_fetches_nothing(
    app_database: Database, mf_urls: Urls, tmp_path: Path
) -> None:
    owner = Database(mf_urls.owner)
    await record_grants(
        owner,
        source="fakefacts",
        mode="personal",
        uses=[Use.AUTOMATED_RETRIEVAL, Use.STORAGE],
        basis="test",
        granted_by="tests",
    )
    await owner.dispose()
    store = SqlMfStore(app_database)
    run = await store.open_run(AMFI, "scheme-list", D1, D1)
    [(grant,)] = await _rows(app_database, "SELECT min(id) FROM wickstreet.rights_grant")
    provenance = Provenance(
        "fake://list", "2026-09-01T00:00:00+00:00", "1" * 64, "x", "f", "c", None, grant
    )
    await store.publish_facts(
        run.id, SchemeFacts([]), provenance, [SchemeRef(1, 1, "Example Fund")]
    )
    source = FakeFacts()
    facts = IngestFacts(
        source,
        store,
        FileRawStore(tmp_path),
        RightsGate(SqlRightsRegister(app_database, "personal")),
    )
    assert (await facts.tracking_error(D1)).status == "published"
    fixed = await facts.tracking_error(D1, reparse=True)
    assert (fixed.status, fixed.superseded, source.fetches) == ("published", 1, 1)
    assert await _rows(
        app_database,
        "SELECT num, superseded_revision IS NULL FROM wickstreet.scheme_fact ORDER BY revision_id",
    ) == [(Decimal("0.05"), False), (Decimal("0.04"), True)]
    assert (await facts.tracking_error(day(9), reparse=True)).status == "skipped"
    # A month-long period (TER) reparses too.
    assert (await facts.ter(D1)).status == "published"
    month = await facts.ter(D1, reparse=True)
    assert (month.status, month.superseded, source.fetches) == ("published", 1, 2)
    assert await store.run_status("fakefacts", "tracking-error-day", day(9)) is None
