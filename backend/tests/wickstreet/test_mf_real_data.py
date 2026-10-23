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
from wickstreet.analytics.application.research import cell
from wickstreet.analytics.domain.fields import FIELDS
from wickstreet.analytics.domain.metrics import METHOD_VERSION, REASONS, Missing
from wickstreet.analytics.domain.snapshot import Snapshot, payload_sha256
from wickstreet.analytics.infrastructure.snapshots import SqlSnapshotStore
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
