"""Integration tests for DataConfidenceReport (Alpha Discovery Program, Priority 1)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.data_confidence_report import (
    DataConfidenceReport,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository


async def _seed_security(session: AsyncSession, symbol: str) -> int:
    model = SecurityModel(symbol=symbol, name=f"{symbol} Ltd", is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model.id


@pytest.mark.asyncio
async def test_report_distinguishes_complete_from_sparse_security(
    db_session: AsyncSession,
) -> None:
    """A security with full weekday coverage must score higher than a sparse one."""
    complete_id = await _seed_security(db_session, "COMPLETE")
    sparse_id = await _seed_security(db_session, "SPARSE")

    start = date(2024, 1, 1)
    end = date(2024, 1, 12)  # two full weeks

    ohlcv_repo = SqlOHLCVRepository(db_session)

    complete_bars = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            complete_bars.append(
                OHLCVBar(
                    date=d, open=Decimal("100"), high=Decimal("101"),
                    low=Decimal("99"), close=Decimal("100"), volume=1000,
                )
            )
        d += timedelta(days=1)
    await ohlcv_repo.upsert_bars(complete_id, complete_bars)

    sparse_bars = [complete_bars[0], complete_bars[1]]  # only 2 of ~8 weekdays
    await ohlcv_repo.upsert_bars(sparse_id, sparse_bars)
    await db_session.commit()

    report = DataConfidenceReport(ohlcv_repo=ohlcv_repo)
    scores = await report.execute([complete_id, sparse_id], start, end)

    assert scores[complete_id].confidence_level == "high"
    assert scores[sparse_id].score < scores[complete_id].score
    assert scores[sparse_id].confidence_level in ("medium", "low")
