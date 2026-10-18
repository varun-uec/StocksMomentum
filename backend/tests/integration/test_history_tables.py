"""System-versioned inputs (ADR-014 §7, M14): every change keeps the version it replaced."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import (
    HISTORY_TABLES,
    HistoricalUniverseModel,
    OHLCVDailyModel,
    SecurityModel,
)

OLD_SESSION = date(2024, 3, 1)


async def _security(session: AsyncSession) -> int:
    security = SecurityModel(symbol="HIST", name="History Ltd")
    session.add(security)
    await session.flush()
    return security.id


def _bar(security_id: int, day: date, close: str) -> dict[str, Any]:
    price = Decimal(close)
    return {
        "security_id": security_id,
        "date": day,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 1000,
        "adj_factor": Decimal("1"),
    }


async def _upsert(session: AsyncSession, row: dict[str, Any]) -> None:
    stmt = insert(OHLCVDailyModel).values(row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[OHLCVDailyModel.security_id, OHLCVDailyModel.date],
        set_={"close": stmt.excluded.close, "open": stmt.excluded.open},
    )
    await session.execute(stmt)
    await session.commit()


async def _row(session: AsyncSession, security_id: int, day: date) -> OHLCVDailyModel:
    session.expire_all()
    return (
        await session.execute(
            select(OHLCVDailyModel).where(
                OHLCVDailyModel.security_id == security_id, OHLCVDailyModel.date == day
            )
        )
    ).scalar_one()


async def _history(session: AsyncSession) -> list[Any]:
    table = HISTORY_TABLES["ohlcv_daily"]
    return list((await session.execute(select(table).order_by(table.c.superseded_revision))).all())


async def test_an_insert_is_stamped_and_an_unchanged_upsert_records_nothing(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session)
    await _upsert(db_session, _bar(sid, OLD_SESSION, "100"))
    first = await _row(db_session, sid, OLD_SESSION)
    stamp = (first.revision_id, first.recorded_at)
    assert stamp[0] > 0 and stamp[1] is not None
    assert first.provenance == "published"  # stored long after its session

    await _upsert(db_session, _bar(sid, OLD_SESSION, "100"))
    again = await _row(db_session, sid, OLD_SESSION)
    assert (again.revision_id, again.recorded_at) == stamp
    assert await _history(db_session) == []


async def test_a_correction_keeps_the_version_it_replaced(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await _upsert(db_session, _bar(sid, OLD_SESSION, "100"))
    before = (await _row(db_session, sid, OLD_SESSION)).revision_id
    await _upsert(db_session, _bar(sid, OLD_SESSION, "101.5"))
    after = await _row(db_session, sid, OLD_SESSION)

    [old] = await _history(db_session)
    assert old.close == Decimal("100") and old.revision_id == before
    assert old.superseded_revision == after.revision_id > before
    assert old.operation == "U"
    assert after.close == Decimal("101.5")


async def test_a_delete_keeps_the_last_version(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await _upsert(db_session, _bar(sid, OLD_SESSION, "100"))
    await db_session.execute(delete(OHLCVDailyModel).where(OHLCVDailyModel.security_id == sid))
    await db_session.commit()
    [gone] = await _history(db_session)
    assert (gone.operation, gone.close) == ("D", Decimal("100"))


async def test_a_bar_stored_with_its_session_is_recorded(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    today = (
        await db_session.execute(text("SELECT (now() AT TIME ZONE 'Asia/Kolkata')::date"))
    ).scalar_one()
    await _upsert(db_session, _bar(sid, today - timedelta(days=1), "100"))
    assert (await _row(db_session, sid, today - timedelta(days=1))).provenance == "recorded"


async def test_rebuilt_universe_rows_are_reconstructed(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    db_session.add(HistoricalUniverseModel(as_of_date=OLD_SESSION, security_id=sid, eligible=True))
    await db_session.commit()
    row = (await db_session.execute(select(HistoricalUniverseModel))).scalar_one()
    assert row.provenance == "reconstructed" and row.revision_id > 0


async def test_an_instrument_change_is_versioned(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await db_session.execute(
        update(SecurityModel).where(SecurityModel.id == sid).values(delisting_date=OLD_SESSION)
    )
    await db_session.commit()
    table = HISTORY_TABLES["securities"]
    [old] = (await db_session.execute(select(table))).all()
    assert old.delisting_date is None and old.operation == "U"
