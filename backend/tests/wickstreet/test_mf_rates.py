"""E2: RBI 91-day T-bill files, the rate store and risk-free metrics (method v5).

Fixtures are synthetic files laid out like RBI's; no RBI data is in the repository.
"""

from __future__ import annotations

import io
import math
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from platform_common.database import Database
from tests.wickstreet.conftest import Urls
from tests.wickstreet.test_mf_analytics import _compute, client, published  # noqa: F401
from tests.wickstreet.test_mf_ingestion import FakeSource
from tests.wickstreet.test_mf_slice3 import daily, o
from wickstreet.analytics.domain.metrics import (
    ANNUALISE_VOL,
    YEAR_DAYS,
    RiskFree,
    compute,
    months_back,
)
from wickstreet.data_rights.application.gate import RightsGate
from wickstreet.data_rights.domain.rights import RightsDeniedError, Use
from wickstreet.data_rights.infrastructure.register import SqlRightsRegister, record_grants
from wickstreet.mf_data.application.ingest import ImportRates
from wickstreet.mf_data.domain.model import RBI, TBILL_91, RatePoint, RawFile
from wickstreet.mf_data.domain.ports import SourceLayoutError
from wickstreet.mf_data.domain.validation import BlockingError, check_rates
from wickstreet.mf_data.infrastructure.raw_store import FileRawStore
from wickstreet.mf_data.infrastructure.rbi import RbiAdapter, parse_handbook, parse_release
from wickstreet.mf_data.infrastructure.reader import SqlMfReader
from wickstreet.mf_data.infrastructure.store import SqlMfStore

_SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _xlsx(rows: list[list[str | float]]) -> bytes:
    """A one-sheet workbook: strings shared, numbers inline, like RBI's files."""
    strings: list[str] = []
    cells = []
    for r, row in enumerate(rows, start=1):
        out = []
        for c, value in enumerate(row):
            ref = f"{chr(ord('B') + c)}{r}"
            if isinstance(value, str):
                strings.append(value)
                out.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                out.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{r}">{"".join(out)}</row>')
    shared = "".join(f"<si><t>{s}</t></si>" for s in strings)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{_SHEET}">{shared}</sst>')
        book.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{_SHEET}"><sheetData>{"".join(cells)}</sheetData></worksheet>',
        )
    return buffer.getvalue()


HANDBOOK = _xlsx(
    [
        ["TABLE 218 : AUCTIONS OF 91-DAY GOVERNMENT OF INDIA TREASURY BILLS"],
        [
            "Date of Auction",
            "Date of Issue",
            "Cut-off Price (₹)",
            "Implicit Yield at Cut-off Price",
        ],
        [1, 2, 3, 4],
        ["2025-26"],
        [45840, 45841, 98.68, 5.3699000000000003],
        ["08-Jul-2025", "09-Jul-2025", 98.67, 5.3872],
        ["Source : Reserve Bank of India."],
    ]
)


def _release(day: str, ytm: str) -> bytes:
    return f"""<html><body><h2>Treasury Bills: Full Auction Result</h2>
<p>Date : {day}</p><table>
<tr><td>Auction Results</td><td>91-Day</td><td>182-Day</td><td>364-Day</td></tr>
<tr><td>III.</td><td>Cut-off price (&#8377;) / Yield</td>
<td>98.5920</td><td>96.9</td><td>93.9</td></tr>
<tr><td>{ytm}</td><td>(YTM: 6.2896%)</td><td>(YTM: 6.4891%)</td></tr>
</table></body></html>""".encode()


def raw(content: bytes, url: str = "https://www.rbi.org.in/x") -> RawFile:
    return RawFile(url, datetime(2026, 10, 23, tzinfo=UTC), content)


# ---- parsing and checks


def test_handbook_rows_parse_serial_and_text_dates() -> None:
    assert parse_handbook(HANDBOOK) == [
        RatePoint(TBILL_91, date(2025, 7, 2), Decimal("5.3699")),
        RatePoint(TBILL_91, date(2025, 7, 8), Decimal("5.3872")),
    ]
    with pytest.raises(SourceLayoutError):
        parse_handbook(_xlsx([["Date of Auction", "Price"]]))


def test_release_gives_the_91_day_yield_or_nothing() -> None:
    assert RbiAdapter().parse_rates(raw(_release("Oct 14, 2026", "(YTM: 5.7281%)"))) == [
        RatePoint(TBILL_91, date(2026, 10, 14), Decimal("5.7281"))
    ]
    assert parse_release(_release("Oct 21, 2026", "-")) == []
    with pytest.raises(SourceLayoutError):
        parse_release(b"<html>Weekly Statistical Supplement</html>")


def test_check_rates_blocks_bad_values() -> None:
    point = RatePoint(TBILL_91, date(2026, 1, 7), Decimal("5.5"))
    assert check_rates([point, point]) == [point]
    with pytest.raises(BlockingError):
        check_rates([point, RatePoint(TBILL_91, point.day, Decimal("5.6"))])
    with pytest.raises(BlockingError):
        check_rates([RatePoint(TBILL_91, point.day, Decimal("0"))])
    with pytest.raises(BlockingError):
        check_rates([])


# ---- risk-free metrics


def test_risk_free_accrues_the_yield_each_day() -> None:
    rf = RiskFree.of([(o("2024-01-01"), 7.3), (o("2024-07-01"), 3.65)])
    start, middle, end = o("2024-01-01"), o("2024-07-01"), o("2024-08-01")
    expected = (1 + 0.073 / 365) ** (middle - start) * (1 + 0.0365 / 365) ** (end - middle) - 1
    assert rf.growth_between(start, end) == pytest.approx(expected, rel=1e-12)
    annual = rf.annualised(start, end)
    assert annual == pytest.approx((1 + expected) ** (YEAR_DAYS / (end - start)) - 1, rel=1e-12)
    assert rf.annualised(o("2023-12-01"), end).reason == "no_risk_free"  # type: ignore[union-attr]
    # The last auction is more than 35 days before the window end: stale.
    assert not rf.covers(start, o("2024-09-01"))


def test_sharpe_and_sortino_use_the_risk_free_return() -> None:
    first = o("2021-06-01")
    navs = [100 * (1.0004 if k % 3 else 0.9995) ** k for k in range(1200)]
    points = daily("2021-06-01", navs)
    as_of = first + 1199
    rf = RiskFree.of([(first + 30 * k, 6.0 + 0.1 * (k % 5)) for k in range(40)])
    v = compute(points, as_of, rf).values
    assert v["sharpe_3y"] == pytest.approx((v["cagr_3y"] - v["rf_3y"]) / v["vol_3y"], rel=1e-12)
    assert v["sharpe_1y"] == pytest.approx((v["ret_1y"] - v["rf_1y"]) / v["vol_1y"], rel=1e-12)
    # Daily NAVs with no gap: the 3Y start anchor is the date 36 months back.
    anchor = months_back(as_of, 36) - first
    below = [
        min(navs[k] / navs[k - 1] - 1 - rf.growth_between(first + k - 1, first + k), 0.0) ** 2
        for k in range(anchor + 1, 1200)
    ]
    deviation = math.sqrt(math.fsum(below) / len(below)) * ANNUALISE_VOL
    assert v["sortino_3y"] == pytest.approx((v["cagr_3y"] - v["rf_3y"]) / deviation, rel=1e-12)


# ---- import, store and API


async def _rbi_grants(urls: Urls, uses: list[Use]) -> None:
    owner = Database(urls.owner)
    await record_grants(
        owner, source=RBI, mode="personal", uses=uses, basis="test grant", granted_by="tests"
    )
    await owner.dispose()


def _importer(database: Database, raw_dir: Path) -> ImportRates:
    rights = RightsGate(SqlRightsRegister(database, "personal"))
    return ImportRates(RbiAdapter(), SqlMfStore(database), FileRawStore(raw_dir), rights)


async def test_import_needs_storage_and_records_no_retrieval(
    mf_urls: Urls, app_database: Database, tmp_path: Path
) -> None:
    importer = _importer(app_database, tmp_path)
    with pytest.raises(RightsDeniedError):
        await importer.execute(raw(HANDBOOK))
    await _rbi_grants(mf_urls, [Use.STORAGE])
    first = await importer.execute(raw(HANDBOOK))
    assert (first.status, first.rows, first.inserted) == ("published", 2, 2)
    assert (await importer.execute(raw(HANDBOOK))).status == "unchanged"
    async with app_database.engine.connect() as connection:
        grant = await connection.scalar(
            text("SELECT retrieval_grant_id FROM wickstreet.revision WHERE id = :r"),
            {"r": first.revision},
        )
    assert grant is None
    corrected = _release("Jul 08, 2025", "(YTM: 5.3900%)")
    second = await importer.execute(raw(corrected))
    assert (second.status, second.superseded) == ("published", 1)
    reader = SqlMfReader(app_database)
    revision = await reader.pointer()
    assert revision == second.revision
    assert await reader.rates(TBILL_91, revision) == [
        (date(2025, 7, 2), 5.3699),
        (date(2025, 7, 8), 5.39),
    ]
    assert await reader.rates(TBILL_91, first.revision) == [
        (date(2025, 7, 2), 5.3699),
        (date(2025, 7, 8), 5.3872),
    ]


async def test_rates_reach_the_snapshot_and_the_api(
    published: FakeSource,  # noqa: F811
    mf_urls: Urls,
    app_database: Database,
    tmp_path: Path,
    client: TestClient,  # noqa: F811
) -> None:
    await _rbi_grants(mf_urls, [Use.STORAGE, Use.DISPLAY, Use.DERIVED_METRICS])
    outcome = await _importer(app_database, tmp_path).execute(raw(HANDBOOK))
    assert outcome.status == "published"
    async with SqlMfReader(app_database).history() as history:
        assert [round(v, 4) for _, v in history.risk_free] == [5.3699, 5.3872]
        assert RBI in history.sources
    await _compute(app_database).execute()
    body = client.get("/risk-free").json()
    assert body["points"] == [["2025-07-02", 5.3699], ["2025-07-08", 5.3872]]
    assert "Reserve Bank of India" in body["acknowledgement"]
    assert RBI in body["sources"]
    metrics = client.get("/funds/10001/metrics").json()
    # The 1Y window ends on 2026-10-22, over 35 days after the last auction: stale.
    assert metrics["states"]["rf_1y"] == {"state": "NA", "reason": "no_risk_free"}
    assert metrics["states"]["sharpe_1y"] == {"state": "NA", "reason": "no_risk_free"}
