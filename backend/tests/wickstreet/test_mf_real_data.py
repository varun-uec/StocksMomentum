"""The MF metric method on the real MF store: opt-in, read-only (ADR-017 MF-11).

Skipped unless ``WICKSTREET_REAL_DATA_URL`` names the runtime login of a database
with a published revision and its snapshot. CI never sets it: tests use synthetic
data only (ADR-022 §2.11). It writes nothing.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import resource
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy import text

from platform_common.database import Database
from wickstreet.analytics.application.research import Research, cell
from wickstreet.analytics.domain.fields import FIELDS
from wickstreet.analytics.domain.metrics import METHOD_VERSION, REASONS, Missing
from wickstreet.analytics.domain.snapshot import Snapshot, payload_sha256
from wickstreet.analytics.domain.views import correlation
from wickstreet.analytics.infrastructure.snapshots import SqlSnapshotStore
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.infrastructure.register import SqlRightsRegister
from wickstreet.mf_data.infrastructure.reader import SqlMfReader

URL = os.environ.get("WICKSTREET_REAL_DATA_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="WICKSTREET_REAL_DATA_URL is not set")
SAMPLE = 50
# Targets on the 22.27M-row store (Slice 2 plan).
COMPUTE_SECONDS, PEAK_RSS_MB = 300, 1024


@pytest.fixture
async def real() -> AsyncIterator[Database]:
    assert URL is not None
    database = Database(URL)
    yield database
    await database.dispose()


async def _snapshot(database: Database) -> Snapshot:
    snapshot = await SqlSnapshotStore(database).find(None, METHOD_VERSION)
    assert snapshot is not None, "run `wickstreet mf metrics` first"
    return snapshot


def _sample(snapshot: Snapshot) -> list[str]:
    """A fixed sample of active funds: the lowest md5 of each AMFI code."""
    active = [r.amfi_code for r in snapshot.rows if cell(r, "active") is True]
    return sorted(active, key=lambda c: hashlib.md5(c.encode()).hexdigest())[:SAMPLE]  # noqa: S324


_ANCHOR = (
    "SELECT n.nav_date, n.nav::float8 FROM wickstreet.nav n "
    "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
    "WHERE p.amfi_code = :code AND n.nav > 0 AND n.nav <> 'NaN' AND n.nav_date <= :day "
    "AND n.revision_id <= :r AND (n.superseded_revision IS NULL OR n.superseded_revision > :r) "
    "ORDER BY n.nav_date DESC LIMIT 1"
)


async def test_sampled_returns_match_independent_sql_anchors(real: Database) -> None:
    snapshot = await _snapshot(real)
    checked = 0
    async with real.engine.connect() as connection:
        for code in _sample(snapshot):
            row = snapshot.by_code[code]
            end = (
                await connection.execute(
                    text(_ANCHOR), {"code": code, "day": snapshot.as_of, "r": snapshot.revision}
                )
            ).one()
            for field, months, annualised in (
                ("ret_1y", 12, False),
                ("cagr_3y", 36, True),
                ("cagr_5y", 60, True),
            ):
                target = await connection.scalar(
                    text(f"SELECT (CAST(:d AS date) - interval '{months} months')::date"),
                    {"d": snapshot.as_of},
                )
                start = (
                    await connection.execute(
                        text(_ANCHOR), {"code": code, "day": target, "r": snapshot.revision}
                    )
                ).first()
                value = cell(row, field)
                if start is None or (target - start[0]).days > 7:
                    assert value is None, (code, field)
                    continue
                days = (end[0] - start[0]).days
                expected = (
                    (end[1] / start[1]) ** (365.25 / days) - 1
                    if annualised
                    else end[1] / start[1] - 1
                )
                assert value == pytest.approx(expected, rel=1e-12, abs=1e-15), (code, field)
                assert row.anchors[field] == start[0].isoformat()
                checked += 1
    assert checked >= SAMPLE


async def test_every_value_is_in_range(real: Database) -> None:
    snapshot = await _snapshot(real)
    for row in snapshot.rows:
        values = dict(zip((f.id for f in FIELDS), row.values, strict=True))
        for name, value in values.items():
            if isinstance(value, Missing):
                assert value.reason in REASONS, (row.amfi_code, name)
            elif isinstance(value, float):
                assert math.isfinite(value), (row.amfi_code, name)
        for name in ("mdd_1y", "mdd_3y", "mdd_since"):
            if isinstance(value := values[name], float):
                assert -1 <= value <= 0, (row.amfi_code, name)
        for name in ("vol_1y", "vol_3y"):
            if isinstance(value := values[name], float):
                assert value >= 0, (row.amfi_code, name)
        for name, value in values.items():
            if name.endswith("_cat_pct") or name == "score":
                assert isinstance(value, Missing) or 0 <= value <= 100, (row.amfi_code, name)
            elif name.endswith("_cat_rank") and not isinstance(value, Missing):
                assert 1 <= value <= values[name.replace("_rank", "_count")], (row.amfi_code, name)
            elif name.endswith("_cat_quartile"):
                assert isinstance(value, Missing) or value in (1, 2, 3, 4), (row.amfi_code, name)
        if isinstance(values["consistency_3y"], float):
            assert 0 <= values["consistency_3y"] <= 1
        if isinstance(values["var95_3y"], float):
            assert values["cvar95_3y"] <= values["var95_3y"]
            assert values["downside_dev_3y"] >= 0
        for prefix in ("dd_3y", "dd_since"):
            peak, trough, recovery = (
                values[f"{prefix}_{s}"] for s in ("peak", "trough", "recovery")
            )
            if isinstance(peak, str):
                assert peak < trough and (not isinstance(recovery, str) or trough < recovery)
        assert values["status"] in ("active", "historical", "no_nav")
        for window in ("rolling_1y", "rolling_3y", "rolling_5y"):
            low, mid, high = (values[f"{window}_{s}"] for s in ("min", "median", "max"))
            if isinstance(mid, float):
                assert low <= mid <= high, (row.amfi_code, window)
                assert 0 <= values[f"{window}_positive_share"] <= 1


async def test_a_pinned_read_matches_its_snapshot(real: Database) -> None:
    snapshot = await _snapshot(real)
    reader = SqlMfReader(real)
    for code in _sample(snapshot)[:5]:
        navs = await reader.navs(code, date.min, snapshot.as_of, snapshot.revision)
        valid = [n for n in navs if n.nav is not None and float(n.nav) > 0]
        assert float(valid[-1].nav or 0) == cell(snapshot.by_code[code], "nav")
        assert valid[-1].nav_date.isoformat() == cell(snapshot.by_code[code], "last_nav_date")


_RECOMPUTE = """
import asyncio, sys
from platform_common.database import Database
from wickstreet.analytics.application.research import ComputeSnapshot
from wickstreet.mf_data.infrastructure.reader import SqlMfReader

async def main():
    database = Database(sys.argv[1])
    async with SqlMfReader(database).history() as history:
        encoded = await ComputeSnapshot.encode(history)
    await database.dispose()
    print(history.revision, encoded.sha256)

asyncio.run(main())
"""


async def test_recomputing_gives_the_stored_bytes_within_the_targets(real: Database) -> None:
    """Determinism on real data, in a child process so its memory peak is its own.

    Skipped when the pointer moved past the stored snapshot.
    """
    snapshot = await _snapshot(real)
    async with real.engine.connect() as connection:
        stored = await connection.scalar(
            text("SELECT payload FROM wickstreet.metric_snapshot WHERE id = :id"),
            {"id": snapshot.id},
        )
    started = time.perf_counter()
    child = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", _RECOMPUTE, URL],
        capture_output=True,
        text=True,
        check=True,
    )
    seconds = time.perf_counter() - started
    revision, sha256 = child.stdout.split()
    if int(revision) != snapshot.revision:
        pytest.skip("a newer revision is published; run `wickstreet mf metrics` first")
    assert sha256 == payload_sha256(stored)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_mb = peak / 2**20 if sys.platform == "darwin" else peak / 2**10
    print(f"recompute {seconds:.1f}s, peak RSS {peak_mb:.0f} MB")
    assert seconds <= COMPUTE_SECONDS
    assert peak_mb <= PEAK_RSS_MB


# ---- method v4 (doc 21), checked by separate code paths


def _research(database: Database) -> Research:
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    return Research(SqlMfReader(database), SqlSnapshotStore(database), rights)


async def test_v4_current_drawdown_matches_sql(real: Database) -> None:
    snapshot = await _snapshot(real)
    query = text(
        "SELECT max(n.nav::float8) FROM wickstreet.nav n "
        "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
        "WHERE p.amfi_code = :code AND n.nav > 0 AND n.nav <> 'NaN' "
        "AND n.revision_id <= :r AND (n.superseded_revision IS NULL OR n.superseded_revision > :r)"
    )
    async with real.engine.connect() as connection:
        for code in _sample(snapshot):
            row = snapshot.by_code[code]
            peak = await connection.scalar(query, {"code": code, "r": snapshot.revision})
            assert cell(row, "dd_now") == pytest.approx(cell(row, "nav") / peak - 1, rel=1e-9)


async def test_v4_point_in_time_ranks_match_pandas(real: Database) -> None:
    """Month-end 1Y ranks rebuilt with pandas from SQL rows, funds that stopped included."""
    import pandas as pd

    snapshot = await _snapshot(real)
    key = ("Equity Scheme - Flexi Cap Fund", "direct", "growth")
    group = [
        r.amfi_code
        for r in snapshot.rows
        if (cell(r, "category"), cell(r, "plan"), cell(r, "option")) == key
        and cell(r, "status") != "no_nav"
    ]
    async with real.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT p.amfi_code, n.nav_date, n.nav::float8 FROM wickstreet.nav n "
                    "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
                    "WHERE p.amfi_code = ANY(:codes) AND n.nav > 0 AND n.nav <> 'NaN' "
                    "AND n.revision_id <= :r "
                    "AND (n.superseded_revision IS NULL OR n.superseded_revision > :r)"
                ),
                {"codes": group, "r": snapshot.revision},
            )
        ).all()
    navs = pd.DataFrame(rows, columns=["code", "day", "nav"])
    navs["day"] = pd.to_datetime(navs["day"])
    as_of = pd.Timestamp(snapshot.as_of)
    last_month = (as_of + pd.offsets.MonthEnd(0)).to_period("M")
    if as_of != as_of + pd.offsets.MonthEnd(0):
        last_month -= 1
    values: dict[tuple[str, str], float] = {}
    for code, one in navs.groupby("code"):
        one = one.sort_values("day").set_index("day")["nav"]
        for month, ends in one.groupby(one.index.to_period("M")):
            day = ends.index[-1]
            if month > last_month or (month.end_time.normalize() - day).days > 7:
                continue
            target = day - pd.DateOffset(months=12)
            before = one[one.index <= target]
            if before.empty or (target - before.index[-1]).days > 7:
                continue
            values[(str(code), str(month))] = ends.iloc[-1] / before.iloc[-1] - 1
    table = pd.Series(values).rename_axis(["code", "month"]).reset_index(name="ret")
    table["n"] = table.groupby("month")["ret"].transform("size")
    table = table[table["n"] >= 5]
    table["pct"] = (
        100 * (table.groupby("month")["ret"].rank(method="average") - 1) / (table["n"] - 1)
    )
    expected = table.set_index(["code", "month"])["pct"]
    active = sorted(
        (c for c in group if cell(snapshot.by_code[c], "status") == "active"),
        key=lambda c: hashlib.md5(c.encode()).hexdigest(),  # noqa: S324
    )[:3]
    research = _research(real)
    checked = 0
    for code in active:
        _, body = await research.rank_history(code, snapshot.revision)
        for month in body["history"]:
            if month["ret_1y"] is not None:
                assert month["ret_1y"]["pct"] == pytest.approx(
                    expected[(code, month["month"])], abs=1e-9
                ), (code, month["month"])
                checked += 1
        ours = {m["month"] for m in body["history"] if m["ret_1y"] is not None}
        assert ours == {m for c, m in expected.index if c == code}
    assert checked >= 100


async def test_v4_near_duplicates_agree_with_the_compare_correlation(real: Database) -> None:
    snapshot = await _snapshot(real)
    reader = SqlMfReader(real)
    listed = sorted(snapshot.tables["near_duplicates"].items())[:10]
    for code, found in listed:
        other, value, _ = found[0]
        start = max(
            date.fromisoformat(snapshot.by_code[c].anchors["cagr_3y"]).toordinal()
            for c in (code, other)
        )
        series = {
            s.fund.amfi_code: s.points
            for s in await reader.series([code, other], snapshot.revision)
        }
        expected, _ = correlation(
            [p for p in series[code] if p[0] >= start],
            [p for p in series[other] if p[0] >= start],
        )
        assert value == pytest.approx(expected, rel=1e-12), (code, other)


async def test_v4_pair_gaps_and_ranges(real: Database) -> None:
    snapshot = await _snapshot(real)
    for code, other in snapshot.tables["pairs"].items():
        row, partner = snapshot.by_code[code], snapshot.by_code[other]
        assert snapshot.tables["pairs"][other] == code
        assert {cell(row, "plan"), cell(partner, "plan")} == {"direct", "regular"}
        direct, regular = (row, partner) if cell(row, "plan") == "direct" else (partner, row)
        gap = cell(row, "dr_gap_3y")
        if gap is not None:
            assert gap == cell(direct, "cagr_3y") - cell(regular, "cagr_3y")
    for row in snapshot.rows:
        for name in ("q1_share_3y", "consistency_3y"):
            value = cell(row, name)
            assert value is None or 0 <= value <= 1, (row.amfi_code, name)
        dd = cell(row, "dd_now")
        assert dd is None or -1 < dd <= 0
        quarter = cell(row, "quartile_change_1y")
        assert quarter is None or -3 <= quarter <= 3
