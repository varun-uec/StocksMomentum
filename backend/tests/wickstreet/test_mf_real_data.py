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
from typing import Any

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


_NAVS = (
    "SELECT p.amfi_code, n.nav_date, n.nav::float8 FROM wickstreet.nav n "
    "JOIN wickstreet.plan_option p ON p.id = n.plan_option_id "
    "WHERE p.amfi_code = ANY(:codes) AND n.nav > 0 AND n.nav <> 'NaN' "
    "AND n.revision_id <= :r "
    "AND (n.superseded_revision IS NULL OR n.superseded_revision > :r)"
)


def _group(snapshot: Snapshot, key: tuple[str, str, str]) -> list[str]:
    return [
        r.amfi_code
        for r in snapshot.rows
        if (cell(r, "category"), cell(r, "plan"), cell(r, "option")) == key
        and cell(r, "status") != "no_nav"
    ]


async def _navs(real: Database, snapshot: Snapshot, codes: list[str]) -> Any:
    import pandas as pd

    async with real.engine.connect() as connection:
        rows = (
            await connection.execute(text(_NAVS), {"codes": codes, "r": snapshot.revision})
        ).all()
    navs = pd.DataFrame(rows, columns=["code", "day", "nav"])
    navs["day"] = pd.to_datetime(navs["day"])
    return navs.sort_values(["code", "day"])


async def _pandas_month_ends(real: Database, snapshot: Snapshot, codes: list[str]) -> Any:
    """Month-end NAV and 1Y return per fund, rebuilt with pandas from SQL rows."""
    import pandas as pd

    navs = await _navs(real, snapshot, codes)
    as_of = pd.Timestamp(snapshot.as_of)
    last_month = (as_of + pd.offsets.MonthEnd(0)).to_period("M")
    if as_of != as_of + pd.offsets.MonthEnd(0):
        last_month -= 1
    found = []
    for code, one in navs.groupby("code"):
        one = one.set_index("day")["nav"]
        for month, ends in one.groupby(one.index.to_period("M")):
            day = ends.index[-1]
            if month > last_month or (month.end_time.normalize() - day).days > 7:
                continue
            target = day - pd.DateOffset(months=12)
            before = one[one.index <= target]
            ret = (
                ends.iloc[-1] / before.iloc[-1] - 1
                if not before.empty and (target - before.index[-1]).days <= 7
                else float("nan")
            )
            found.append((str(code), month, ends.iloc[-1], ret))
    return pd.DataFrame(found, columns=["code", "month", "nav", "ret"])


async def test_v4_point_in_time_ranks_match_pandas(real: Database) -> None:
    """Month-end 1Y ranks rebuilt with pandas from SQL rows, funds that stopped included."""
    snapshot = await _snapshot(real)
    group = _group(snapshot, ("Equity Scheme - Flexi Cap Fund", "direct", "growth"))
    table = (await _pandas_month_ends(real, snapshot, group)).dropna(subset=["ret"])
    table["month"] = table["month"].astype(str)
    table["n"] = table.groupby("month")["ret"].transform("size")
    table = table[table["n"] >= 5].copy()
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


async def test_v4_backtest_matches_pandas(real: Database) -> None:
    """Top-5 by 1Y return against the median, rebuilt month by month with pandas."""
    import pandas as pd

    snapshot = await _snapshot(real)
    key = ("Equity Scheme - Flexi Cap Fund", "direct", "growth")
    table = await _pandas_month_ends(real, snapshot, _group(snapshot, key))
    by_month = {m: g.set_index("code") for m, g in table.groupby("month")}
    expected = {}
    for month, now in by_month.items():
        later = by_month.get(month + 1)
        if later is None:
            continue
        signal = now.dropna(subset=["ret"])
        common = now.index.intersection(later.index)
        returns = later.loc[common, "nav"] / now.loc[common, "nav"] - 1
        if len(signal) < 5 or len(returns) < 5:
            continue
        ranked = signal.reset_index().sort_values(["ret", "code"], ascending=[False, True])
        picks = [c for c in ranked["code"].head(5) if c in returns.index]
        if picks:
            expected[str(month)] = (picks, returns[picks].mean(), returns.median())
    _, result = await _research(real).backtest(*key, "ret_1y", 5, snapshot.revision)
    got = {m["signal_month"]: m for m in result["months"]}
    assert set(got) == set(expected)
    for month, (picks, strategy, median) in expected.items():
        assert got[month]["picks"] == picks, month
        assert got[month]["strategy"] == pytest.approx(strategy, rel=1e-12, abs=1e-15)
        assert got[month]["median"] == pytest.approx(median, rel=1e-12, abs=1e-15)
    growth = math.prod(1 + m["strategy"] for m in result["months"]) - 1
    assert result["summary"]["whole"]["strategy_growth"] == pytest.approx(growth, rel=1e-12)
    assert len(pd.Index(list(got))) >= 100


def _newton_xirr(flows: list[tuple[int, float]]) -> float:
    """XIRR by Newton's method from 10%; a different algorithm from the code's bisection."""
    first = flows[0][0]
    rate = 0.1
    for _ in range(100):
        f = sum(a / (1 + rate) ** ((d - first) / 365) for d, a in flows)
        df = sum(-(d - first) / 365 * a / (1 + rate) ** ((d - first) / 365 + 1) for d, a in flows)
        step = f / df
        rate -= step
        if abs(step) < 1e-14:
            break
    return rate


async def test_v4_rolling_sip_matches_an_independent_simulation(real: Database) -> None:
    import pandas as pd

    snapshot = await _snapshot(real)
    research = _research(real)
    long_lived = [
        c
        for c in _sample(snapshot)
        if (cell(snapshot.by_code[c], "since_start") or "9999") <= "2018-01-01"
    ][:3]
    assert long_lived
    for code in long_lived:
        _, body = await research.rolling_sip(code, "3y", 10_000.0, 1, 0.05, snapshot.revision)
        starts = body["starts"]
        navs = (await _navs(real, snapshot, [code])).set_index("day")["nav"]
        for start in (starts[0], starts[len(starts) // 2], starts[-1]):
            begin = pd.Timestamp(start["start"])
            end = begin + pd.DateOffset(months=36) - pd.Timedelta(days=1)
            units = invested = 0.0
            flows, lowest = [], 0.0
            for n in range(36):
                due = begin + pd.DateOffset(months=n)
                traded = navs[navs.index >= due]
                if traded.empty or traded.index[0] > end:
                    break
                day, nav = traded.index[0], traded.iloc[0]
                paid = 10_000.0 * 1.05 ** (n // 12)
                duty = 0.00005 if day >= pd.Timestamp("2020-07-01") else 0.0
                units += paid * (1 - duty) / nav
                invested += paid
                flows.append((day.toordinal(), -paid))
                lowest = min(lowest, units * nav / invested - 1)
            valued = navs[navs.index <= end]
            value = units * valued.iloc[-1]
            flows.append((valued.index[-1].toordinal(), value))
            assert start["invested"] == pytest.approx(invested, rel=1e-12), (code, start)
            assert start["value"] == pytest.approx(value, rel=1e-12), (code, start)
            assert start["sip_drawdown"] == pytest.approx(lowest, rel=1e-12, abs=1e-15)
            assert start["xirr"] == pytest.approx(_newton_xirr(sorted(flows)), abs=1e-9)


async def test_v4_regime_proxy_matches_pandas(real: Database) -> None:
    """The proxy's levels and windows, rebuilt with pandas from SQL rows."""
    import pandas as pd

    snapshot = await _snapshot(real)
    proxy = snapshot.tables["proxy"]
    codes = [
        r.amfi_code
        for r in snapshot.rows
        if cell(r, "category") == proxy["category"]
        and cell(r, "category_basis") == "amfi"
        and cell(r, "plan") == proxy["plan"]
        and cell(r, "option") == proxy["option"]
        and cell(r, "status") != "no_nav"
    ]
    navs = await _navs(real, snapshot, codes)
    navs["prev_day"] = navs.groupby("code")["day"].shift()
    navs["ret"] = navs["nav"] / navs.groupby("code")["nav"].shift() - 1
    navs = navs[(navs["day"] - navs["prev_day"]).dt.days <= 7]
    daily = navs.groupby("day")["ret"].agg(["median", "size"])
    daily = daily[daily["size"] >= 5]
    levels = 100 * (1 + daily["median"]).cumprod()
    stored = pd.Series(
        [v for _, v in proxy["levels"]], index=pd.to_datetime([d for d, _ in proxy["levels"]])
    )
    assert list(stored.index) == list(levels.index)
    assert stored.to_numpy() == pytest.approx(levels.to_numpy(), rel=1e-9)
    falls = []
    peak_day, peak, trough_day, trough = levels.index[0], levels.iloc[0], None, None
    for day, level in levels.iloc[1:].items():
        if level >= peak:
            if trough is not None and trough / peak - 1 <= -0.10:
                falls.append((peak_day, trough_day, trough / peak - 1))
            peak_day, peak, trough_day, trough = day, level, None, None
        elif trough is None or level < trough:
            trough_day, trough = day, level
    if trough is not None and trough / peak - 1 <= -0.10:
        falls.append((peak_day, trough_day, trough / peak - 1))
    windows = [w for w in snapshot.tables["regimes"] if w["kind"] != "recovery"]
    assert [(w["start"], w["end"]) for w in windows] == [
        (a.date().isoformat(), b.date().isoformat()) for a, b, _ in falls
    ]
    assert [w["proxy_return"] for w in windows] == pytest.approx([d for _, _, d in falls])
    for window in windows:
        assert window["kind"] == ("crash" if window["proxy_return"] <= -0.20 else "correction")


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


async def test_v5_risk_free_and_sharpe_match_pandas(real: Database) -> None:
    """rf_3y from SQL rates, forward-filled over calendar days with pandas; then Sharpe 3Y."""
    import pandas as pd

    snapshot = await _snapshot(real)
    async with real.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT effective_date, value::float8 FROM wickstreet.rate_point "
                    "WHERE series = 'tbill_91d_cutoff_yield' AND revision_id <= :r "
                    "AND (superseded_revision IS NULL OR superseded_revision > :r)"
                ),
                {"r": snapshot.revision},
            )
        ).all()
    rates = pd.Series({pd.Timestamp(d): v for d, v in rows}).sort_index()
    checked = 0
    for code in _sample(snapshot):
        row = snapshot.by_code[code]
        if cell(row, "rf_3y") is None:
            continue
        start = pd.Timestamp(row.anchors["cagr_3y"])
        end = pd.Timestamp(cell(row, "last_nav_date"))
        days = pd.date_range(start, end - pd.Timedelta(days=1), freq="D")
        daily = rates.reindex(rates.index.union(days)).ffill().loc[days]
        growth = (1 + daily / 100 / 365).prod()
        expected = growth ** (365.25 / (end - start).days) - 1
        assert cell(row, "rf_3y") == pytest.approx(expected, rel=1e-9), code
        sharpe = (cell(row, "cagr_3y") - expected) / cell(row, "vol_3y")
        assert cell(row, "sharpe_3y") == pytest.approx(sharpe, rel=1e-9), code
        checked += 1
    assert checked >= 30


# ---- fund search (audit F-04)

SEARCH_EXPECTED = {
    "parag": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
    "ppfas": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
    "sbi smallcap": "SBI Small Cap Fund - Direct Plan - Growth",
    "hdfc midcap": "HDFC Mid Cap Fund - Growth Option - Direct Plan",
    "axis bluechip": "Axis Large Cap Fund - Direct Plan - Growth",
    "quant small": "quant Small Cap Fund - Growth Option - Direct Plan",
    "motilal midcap": "Motilal Oswal Midcap Fund-Direct Plan-Growth Option",
    "kotak flexi": "Kotak Flexi Cap Fund - Growth - Direct",
    "uti nifty 50": "UTI Nifty 50 Index Fund - Growth Option- Direct",
    "122639": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
}


async def test_search_finds_the_fund_a_beginner_means_in_the_top_3(real: Database) -> None:
    research = _research(real)
    for query, expected in SEARCH_EXPECTED.items():
        _, found = await research.search(query, 3)
        assert expected in [f.nav_name for f, _ in found], query
    _, found = await research.search("parag", 1)
    assert found[0][0].nav_name == SEARCH_EXPECTED["parag"]
    # Independent audit A-07: a broad AMC query opens on current Direct Growth plans,
    # not on closed series whose missing listing sorted them first.
    _, found = await research.search("nippon india", 8)
    rows = [row for _, row in found if row is not None]
    assert all(cell(row, "status") == "active" for row in rows)
    assert (cell(rows[0], "plan"), cell(rows[0], "option")) == ("direct", "growth")
