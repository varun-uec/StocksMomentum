"""MF analytics on synthetic AMFI files, as the runtime role (ADR-017 MF-3, MF-11, MF-13)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from platform_common.database import Database
from tests.wickstreet.amfi_files import master_file, nav_file
from tests.wickstreet.conftest import Urls
from tests.wickstreet.test_mf_ingestion import FakeSource
from wickstreet import cli
from wickstreet.analytics.application.research import ComputeSnapshot, cell
from wickstreet.analytics.domain.metrics import METHOD_VERSION
from wickstreet.analytics.infrastructure.snapshots import SqlSnapshotStore, retire_snapshot
from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.data_rights.infrastructure.register import (
    SqlRightsRegister,
    record_grants,
    revoke_grants,
)
from wickstreet.identity.infrastructure.local import PERSONAL_CONTEXT
from wickstreet.mf_data.application.ingest import IngestNavDay, IngestSchemeMaster, Summary
from wickstreet.mf_data.domain.model import AMFI
from wickstreet.mf_data.infrastructure.raw_store import FileRawStore
from wickstreet.mf_data.infrastructure.reader import SqlMfReader, record_link
from wickstreet.mf_data.infrastructure.store import SqlMfStore
from wickstreet.wiring import Ingestion

YEAR_AGO, DAY_BEFORE, AS_OF = date(2025, 10, 22), date(2026, 10, 21), date(2026, 10, 22)
CODES = ["10001", "10002", "10003"]
FILES = {
    YEAR_AGO: nav_file(YEAR_AGO, {"10001": "10.0000", "10002": "20.0000"}),
    DAY_BEFORE: nav_file(DAY_BEFORE, {"10001": "11.5000", "10002": "21.0000"}),
    AS_OF: nav_file(AS_OF, {"10001": "12.0000", "10002": "22.0000"}),
}
USES = [Use.AUTOMATED_RETRIEVAL, Use.STORAGE, Use.DERIVED_METRICS, Use.DISPLAY]


async def _grant(urls: Urls, uses: list[Use]) -> None:
    owner = Database(urls.owner)
    await record_grants(
        owner, source=AMFI, mode="personal", uses=uses, basis="test grant", granted_by="tests"
    )
    await owner.dispose()


async def _revoke(urls: Urls, uses: list[Use]) -> None:
    owner = Database(urls.owner)
    await revoke_grants(owner, source=AMFI, mode="personal", uses=uses)
    await owner.dispose()


def _days(database: Database, raw: Path, source: FakeSource) -> IngestNavDay:
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    return IngestNavDay(source, SqlMfStore(database), FileRawStore(raw), rights, Decimal("0.25"))


async def _publish(database: Database, raw: Path, source: FakeSource) -> None:
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    store = SqlMfStore(database)
    await IngestSchemeMaster(source, store, FileRawStore(raw), rights).execute(AS_OF)
    days = _days(database, raw, source)
    for day in sorted(FILES):
        await days.execute(day)


def _compute(database: Database) -> ComputeSnapshot:
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    return ComputeSnapshot(SqlMfReader(database), SqlSnapshotStore(database), rights)


@pytest.fixture
async def published(mf_urls: Urls, app_database: Database, tmp_path: Path) -> FakeSource:
    await _grant(mf_urls, USES)
    source = FakeSource(dict(FILES), master=master_file(CODES))
    await _publish(app_database, tmp_path, source)
    return source


@pytest.fixture
def client(mf_settings: WickstreetSettings) -> Iterator[TestClient]:
    app = create_app(mf_settings)

    async def authenticate(request: object) -> Any:
        return PERSONAL_CONTEXT

    app.state.authenticate = authenticate
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


SCREEN = {
    "filter": {"all": [{"field": "ret_1y", "op": ">", "value": 0.05}]},
    "sort": [{"field": "ret_1y", "dir": "desc"}],
    "columns": ["ret_1y", "plan", "category"],
}


async def test_compute_runs_once_per_revision(
    published: FakeSource, app_database: Database
) -> None:
    compute = _compute(app_database)
    first = await compute.execute()
    assert first.status == "computed"
    assert first.funds == 3
    assert (await compute.execute()).status == "current"
    snapshot = await SqlSnapshotStore(app_database).find(None, METHOD_VERSION)
    assert snapshot is not None
    assert snapshot.revision == first.revision
    assert snapshot.as_of == AS_OF
    assert cell(snapshot.by_code["10001"], "ret_1y") == pytest.approx(0.2, rel=1e-12)


async def test_no_snapshot_without_derived_metrics(
    mf_urls: Urls, app_database: Database, tmp_path: Path
) -> None:
    await _grant(mf_urls, [Use.AUTOMATED_RETRIEVAL, Use.STORAGE])
    await _publish(app_database, tmp_path, FakeSource(dict(FILES), master=master_file(CODES)))
    with pytest.raises(RightsDeniedError):
        await _compute(app_database).execute()
    assert await SqlSnapshotStore(app_database).find(None, METHOD_VERSION) is None


async def test_the_api_reads_one_pinned_snapshot(
    published: FakeSource, app_database: Database, tmp_path: Path, client: TestClient
) -> None:
    old = await _compute(app_database).execute()

    fields = client.get("/screener/fields").json()
    assert fields["data_revision"] == old.revision
    assert fields["method_version"] == METHOD_VERSION
    assert {"ret_1y", "cagr_3y", "mdd_since"} <= {f["id"] for f in fields["fields"]}
    assert next(f for f in fields["fields"] if f["id"] == "amc")["values"] == [
        "Example AMC Limited"
    ]

    run = client.post("/screener/run", json=SCREEN)
    assert run.status_code == 200
    body = run.json()
    assert body["total"] == 3
    assert body["matched"] == 2
    assert [r["amfi_code"] for r in body["rows"]] == ["10001", "10002"]
    assert body["rows"][0]["values"]["ret_1y"] == pytest.approx(0.2, rel=1e-12)
    assert body["rows"][0]["values"]["plan"] == "direct"
    assert body["excluded_missing"] == [
        {"path": "all[0]", "field": "ret_1y", "count": 1, "reasons": {"no_nav": 1}}
    ]
    assert client.post("/screener/run", json=SCREEN).content == run.content
    assert body["rows"][0]["conditions"] == [
        {"path": "all[0]", "passed": True, "value": pytest.approx(0.2, rel=1e-12)}
    ]
    assert body["relaxations"] == []
    fields_by_id = {f["id"]: f for f in fields["fields"]}
    assert fields_by_id["ret_1y"]["available"] is True
    assert fields_by_id["cagr_10y"] == fields_by_id["cagr_10y"] | {
        "available": False,
        "reason": "history_too_short",
    }
    nothing = client.post(
        "/screener/run",
        json={
            "filter": {
                "all": [
                    {"field": "ret_1y", "op": ">", "value": 9},
                    {"field": "plan", "op": "in", "value": ["direct"]},
                ]
            }
        },
    ).json()
    assert nothing["matched"] == 0
    assert nothing["relaxations"] == [
        {"path": "all[0]", "matched": 3},
        {"path": "all[1]", "matched": 0},
    ]

    page = client.post("/screener/run", json=SCREEN | {"page": {"size": 1}}).json()
    assert page["next"] is not None

    # A correction publishes a new revision and a new snapshot.
    published.files[AS_OF] = nav_file(AS_OF, {"10001": "13.0000", "10002": "22.0000"})
    await _days(app_database, tmp_path, published).execute(AS_OF, refetch=True)
    new = await _compute(app_database).execute()
    assert new.status == "computed"
    assert new.revision is not None and old.revision is not None
    assert new.revision > old.revision

    latest = client.get("/funds/10001/metrics").json()
    assert latest["data_revision"] == new.revision
    assert latest["values"]["ret_1y"] == pytest.approx(0.3, rel=1e-12)
    pinned = client.get(f"/funds/10001/metrics?data_revision={old.revision}").json()
    assert pinned["data_revision"] == old.revision
    assert pinned["latest_revision"] == new.revision
    assert pinned["values"]["ret_1y"] == pytest.approx(0.2, rel=1e-12)
    assert pinned["anchors"]["ret_1y"] == "2025-10-22"
    assert pinned["since_label"] == "since 2025-10-22, first stored valid NAV, not inception"

    old_navs = client.get(f"/funds/10001/navs?data_revision={old.revision}").json()["navs"]
    new_navs = client.get("/funds/10001/navs").json()["navs"]
    assert [n["nav"] for n in old_navs] == ["10.0000", "11.5000", "12.0000"]
    assert new_navs[-1] == {
        "date": "2026-10-22",
        "nav": "13.0000",
        "anomaly": None,
        "source": AMFI,
        "revision": new.revision,
    }

    # The cursor stays on the snapshot it started on, and only on its own request.
    second = client.post(
        "/screener/run", json=SCREEN | {"page": {"size": 1, "after": page["next"]}}
    ).json()
    assert second["data_revision"] == old.revision
    assert [r["amfi_code"] for r in second["rows"]] == ["10002"]
    reused = client.post(
        "/screener/run",
        json=SCREEN | {"sort": [{"field": "ret_1y"}], "page": {"after": page["next"]}},
    )
    assert reused.status_code == 422
    assert reused.json()["type"] == "urn:wickstreet:error:invalid-cursor"


async def test_a_retired_snapshot_is_kept_but_never_served(
    published: FakeSource, app_database: Database, mf_urls: Urls, client: TestClient
) -> None:
    first = await _compute(app_database).execute()
    assert first.snapshot_id is not None
    assert client.get("/funds/10001/metrics").status_code == 200

    owner = Database(mf_urls.owner)
    try:
        assert await retire_snapshot(owner, first.snapshot_id, by="tests", reason="stale code")
        assert not await retire_snapshot(owner, first.snapshot_id, by="tests", reason="again")
        with pytest.raises(DBAPIError, match="permission denied"):
            await retire_snapshot(app_database, first.snapshot_id, by="app", reason="no")

        store = SqlSnapshotStore(app_database)
        assert await store.find(None, METHOD_VERSION) is None
        assert await store.find(first.revision, METHOD_VERSION) is None
        pinned = client.get(f"/funds/10001/metrics?data_revision={first.revision}")
        assert pinned.status_code == 404
        assert pinned.json()["type"] == "urn:wickstreet:error:no-snapshot"

        # The same revision computes again; the retired row stays for audit.
        again = await _compute(app_database).execute()
        assert again.status == "computed"
        assert again.revision == first.revision
        assert again.snapshot_id != first.snapshot_id
        assert client.get("/funds/10001/metrics").json()["data_revision"] == first.revision
        async with owner.engine.connect() as connection:
            audit = (
                await connection.execute(
                    text(
                        "SELECT retired_by, retired_reason, retired_at IS NOT NULL "
                        "FROM wickstreet.metric_snapshot WHERE id = :id"
                    ),
                    {"id": first.snapshot_id},
                )
            ).one()
        assert tuple(audit) == ("tests", "stale code", True)
    finally:
        await owner.dispose()


async def test_fund_reads_search_compare_and_errors(
    published: FakeSource, app_database: Database, mf_urls: Urls, client: TestClient
) -> None:
    await _compute(app_database).execute()
    owner = Database(mf_urls.owner)
    assert await record_link(
        owner,
        from_code="10001",
        to_code="10002",
        kind="merger",
        effective_date=date(2026, 1, 1),
        evidence="test notice",
        recorded_by="tests",
    )
    await owner.dispose()

    found = client.get("/funds?q=Example Fund 1000").json()["funds"]
    assert [f["amfi_code"] for f in found] == CODES
    assert [f["nav_available"] for f in found] == [True, True, False]
    assert client.get("/funds?q=10003").json()["funds"][0]["amfi_code"] == "10003"

    detail = client.get("/funds/10001").json()
    assert detail["classification"]["category"] == "Equity Scheme - Large Cap Fund"
    assert detail["classification"]["option"] == "growth"
    assert detail["links"][0]["to_code"] == "10002"

    empty = client.get("/funds/10003/metrics").json()
    assert empty["values"]["ret_1y"] is None
    assert empty["states"]["ret_1y"] == {"state": "NA", "reason": "no_nav"}

    compared = client.get("/compare?code=10001&code=10002").json()
    assert compared["start"] == "2025-10-22"
    assert compared["series"]["10001"][0] == ["2025-10-22", 100.0]
    assert compared["series"]["10001"][-1] == ["2026-10-22", pytest.approx(120.0)]

    assert client.get("/funds/99999/metrics").status_code == 404
    assert client.get("/compare?code=10001").status_code == 422
    bad = client.post("/screener/run", json={"filter": {"all": [{"field": "x", "op": ">"}]}})
    assert bad.status_code == 422
    assert bad.headers["content-type"] == "application/problem+json"

    await _revoke(mf_urls, [Use.DISPLAY])
    denied = client.get("/funds/10001/metrics")
    assert denied.status_code == 403
    assert denied.json()["type"] == "urn:wickstreet:error:rights-denied"


async def test_every_cli_publish_path_computes_the_snapshot(
    published: FakeSource, mf_settings: WickstreetSettings, tmp_path: Path, app_database: Database
) -> None:
    published.files[AS_OF] = nav_file(AS_OF, {"10001": "12.5000", "10002": "22.0000"})

    async def work(ingestion: Ingestion) -> Summary:
        database = Database(mf_settings.database_url)
        summary = Summary()
        try:
            summary.add(await _days(database, tmp_path, published).execute(AS_OF, refetch=True))
        finally:
            await database.dispose()
        return summary

    await asyncio.to_thread(cli._ingest, mf_settings, work)  # noqa: SLF001
    snapshot = await SqlSnapshotStore(app_database).find(None, METHOD_VERSION)
    assert snapshot is not None
    assert snapshot.revision == await SqlMfReader(app_database).pointer()


async def test_slice3_views_presets_formulas_and_calculators(
    published: FakeSource, app_database: Database, client: TestClient
) -> None:
    await _compute(app_database).execute()

    metrics = client.get("/funds/10001/metrics").json()
    assert metrics["values"]["status"] == "active"
    assert metrics["values"]["category_basis"] == "amfi"
    assert metrics["states"]["score"] == {"state": "NA", "reason": "history_too_short"}
    assert metrics["states"]["ret_1y_cat_rank"] == {"state": "NA", "reason": "too_few_peers"}

    presets = client.get("/screener/presets").json()["presets"]
    assert len(presets) == 6
    for preset in presets:
        run = client.post(
            "/screener/run",
            json={"filter": preset["filter"], "sort": preset["sort"], "columns": preset["columns"]},
        )
        assert run.status_code == 200, preset["id"]

    formula = client.post(
        "/screener/run",
        json={
            "formulas": {"double": "ret_1y * 2"},
            "filter": {"field": "double", "op": ">", "value": 0.3},
            "columns": ["double"],
        },
    ).json()
    assert [r["amfi_code"] for r in formula["rows"]] == ["10001"]
    assert formula["rows"][0]["values"]["double"] == pytest.approx(0.4, rel=1e-12)
    bad = client.post("/screener/run", json={"formulas": {"x": "__import__('os')"}})
    assert bad.status_code == 422

    annual = client.get("/funds/10001/annual").json()
    assert annual["calendar"] == [{"period": "2026", "return": pytest.approx(0.2), "partial": True}]
    rolling = client.get("/funds/10001/rolling?window=1y").json()
    assert rolling["points"] == [["2026-10-22", pytest.approx(0.2, rel=1e-3)]]
    assert client.get("/funds/10001/rolling?window=2y").status_code == 422
    assert client.get("/funds/10001/drawdowns").json()["drawdowns"] == []

    lump = client.post(
        "/calculators/lumpsum",
        json={"code": "10001", "amount": 1000, "start": "2025-10-22", "end": "2026-10-22"},
    ).json()
    value = 1000 * (1 - 0.00005) * 12 / 10
    assert lump["summary"]["value"] == pytest.approx(value)
    assert lump["tax"]["tax_class"] == "equity"
    assert lump["tax"]["total"] == pytest.approx((value - 1000) * 0.2 * 1.04)
    assert client.post("/calculators/nope", json=lump | {"code": "10001"}).status_code == 422
    swp = client.post(
        "/calculators/swp",
        json={"code": "10001", "amount": 1000, "start": "2025-10-22", "end": "2026-10-22"},
    )
    assert swp.status_code == 422
    assert swp.json()["type"] == "urn:wickstreet:error:invalid-simulation"

    compared = client.get("/compare?code=10001&code=10002").json()
    assert compared["correlations"] == [
        {"a": "10001", "b": "10002", "correlation": None, "observations": 2}
    ]


async def test_v4_views_answer_through_the_api(
    published: FakeSource, app_database: Database, client: TestClient
) -> None:
    await _compute(app_database).execute()
    group = "category=Equity Scheme - Large Cap Fund&plan=direct&option=growth"

    fields = {f["id"]: f for f in client.get("/screener/fields").json()["fields"]}
    assert fields["fund_type"]["coverage"]["values"] == 3
    assert fields["dr_gap_3y"]["coverage"]["missing"] == {"no_pair": 3}

    history = client.get("/funds/10001/rank-history").json()
    assert history["group"]["funds_with_nav"] == 2
    assert history["history"] == []  # three NAVs make no complete ranked month-end
    assert client.get(f"/peers/transitions?{group}").json()["counts"] == [[0] * 4] * 4
    assert client.get(f"/peers/frontier?{group}").json()["points"] == []
    unclassified = "category=Unclassified&plan=direct&option=growth"
    assert client.get(f"/peers/frontier?{unclassified}").status_code == 422

    run = client.post(
        "/backtests",
        json={"category": "Equity Scheme - Large Cap Fund", "plan": "direct", "option": "growth"},
    ).json()
    assert run["summary"]["whole"] == {"months": 0}
    assert len(run["limits"]) == 4
    bad = client.post(
        "/backtests",
        json={
            "category": "Equity Scheme - Large Cap Fund",
            "plan": "direct",
            "option": "growth",
            "signal": "score",
        },
    )
    assert bad.status_code == 422

    assert client.get("/funds/10001/direct-regular").json()["pair"] is None
    underwater = client.get("/funds/10001/underwater").json()
    assert underwater["series"][-1] == ["2026-10-22", 0.0]
    assert underwater["dd_now"] == 0.0
    sip = client.get("/funds/10001/rolling-sip?tenor=3y").json()
    assert sip["summary"] == {"starts": 0}
    assert client.get("/funds/10001/rolling-sip?tenor=2y").status_code == 422
    assert client.get("/funds/10001/near-duplicates").json()["listed"] == []
    score = client.get("/funds/10001/score").json()
    assert [p["field"] for p in score["parts"]] == ["consistency_3y", "ret_risk_3y", "mdd_3y"]
    assert score["penalties"] == []
    confidence = client.get("/funds/10001/confidence").json()
    assert confidence["valid_navs"] == 3
    assert confidence["sources"][0]["rows"] == 3
    assert client.get("/regimes").json()["windows"] == []
    assert client.get("/funds/10001/regimes").json()["windows"] == []
    compared = client.get("/compare?code=10001&code=10002").json()
    assert compared["average_correlation"] is None
