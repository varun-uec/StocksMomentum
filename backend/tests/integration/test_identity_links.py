"""Verified identity links in Postgres (R3-B-31): import, versioning, stitching.

Synthetic securities only, on the isolated test database.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import (
    OHLCVDailyModel,
    SecurityIdentityLinkModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.point_in_time import (
    PointInTimeOHLCVRepository,
    PointInTimeSource,
    current_revision,
)
from momentum25.infrastructure.persistence.repositories import SqlOHLCVRepository
from momentum25.infrastructure.persistence.repositories.identity_links import (
    import_identity_links,
    load_identity_links,
    read_import_file,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

DAYS = [date(2023, 6, 1) + timedelta(days=i) for i in range(40)]
DAYS = [d for d in DAYS if d.weekday() < 5]
RENAME = date(2023, 6, 19)
OWN = sum(d >= RENAME for d in DAYS)  # the successor's own bars
ALL = len(DAYS)
SHA = "ab" * 32
HEADER = "predecessor_id,successor_id,effective_date,ratio,evidence_source,evidence_reference\n"


async def _pair(session: AsyncSession) -> tuple[int, int]:
    """OLD trades before the rename at 200; NEW trades from it at 100 (1:2)."""
    ids = []
    for symbol, isin in (("OLD", None), ("NEW", "INE000000NEW")):
        security = SecurityModel(symbol=symbol, name=symbol, isin=isin)
        session.add(security)
        await session.flush()
        ids.append(security.id)
    old, new = ids
    for day in DAYS:
        sid, raw = (old, Decimal(200)) if day < RENAME else (new, Decimal(100))
        session.add(
            OHLCVDailyModel(
                security_id=sid,
                date=day,
                open=raw,
                high=raw,
                low=raw,
                close=raw,
                volume=1000,
                adj_factor=Decimal(1),
                adj_close=raw,
            )
        )
    await session.commit()
    return old, new


def _file(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "links.csv"
    path.write_text(HEADER + rows)
    return path


async def test_an_imported_link_is_versioned_and_continues_the_successor_history(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    old, new = await _pair(db_session)
    before = await current_revision(db_session)
    links = read_import_file(
        _file(tmp_path, f"{old},{new},{RENAME},2,NSE symbol change,circular X sha256 {SHA}\n")
    )
    assert await import_identity_links(db_session, links) == 1
    await db_session.commit()
    after = await current_revision(db_session)
    assert after > before  # a link is part of the market-data revision

    series = await SqlOHLCVRepository(db_session).get_series(new, ALL, DAYS[-1])
    assert [b.date for b in series.bars] == DAYS
    assert [b.close * b.adj_factor for b in series.bars] == [Decimal(100)] * ALL

    pipeline = IndicatorPipelineImpl(db_session)
    bars = await pipeline._fetch_bars("NEW", DAYS[-1], ALL)
    assert bars is not None and len(bars) == ALL

    # Point in time: the link is invisible at the revision before the import.
    for revision, expected in ((before, OWN), (after, ALL)):
        source = PointInTimeSource(db_session, DAYS[-1], revision)
        pit = await PointInTimeOHLCVRepository(source).get_series(new, ALL, DAYS[-1])
        assert len(pit.bars) == expected


async def test_a_link_the_bars_contradict_is_not_applied(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    old, new = await _pair(db_session)
    late = RENAME + timedelta(days=3)  # NEW already traded before this date
    links = read_import_file(_file(tmp_path, f"{old},{new},{late},1,NSE,doc {SHA}\n"))
    await import_identity_links(db_session, links)
    await db_session.commit()
    assert len(await load_identity_links(db_session)) == 0
    series = await SqlOHLCVRepository(db_session).get_series(new, ALL, DAYS[-1])
    assert len(series.bars) == OWN  # its own bars only


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("1,2,2023-06-19,1,NSE,circular X without a hash\n", "SHA-256"),
        ("1,2,2023-06-19,1,,doc " + SHA + "\n", "evidence is required"),
        ("1,1,2023-06-19,1,NSE,doc " + SHA + "\n", "linked to itself"),
        ("1,2,19-06-2023,1,NSE,doc " + SHA + "\n", "line 2"),
    ],
)
def test_a_bad_import_file_is_refused_whole(tmp_path: Path, row: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_import_file(_file(tmp_path, row))


async def test_unknown_security_ids_are_refused_and_nothing_is_written(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    links = read_import_file(_file(tmp_path, f"999998,999999,{RENAME},1,NSE,doc {SHA}\n"))
    with pytest.raises(ValueError, match="unknown security ids"):
        await import_identity_links(db_session, links)
    count = await db_session.scalar(select(func.count()).select_from(SecurityIdentityLinkModel))
    assert count == 0
