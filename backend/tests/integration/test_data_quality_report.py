"""Integration tests for DataQualityReport (Objective 5, Data Quality Framework)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.data_quality_report import DataQualityReport
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories.corporate_actions import (
    SqlCorporateActionRepository,
)
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository


async def _seed_security(session: AsyncSession, symbol: str) -> int:
    model = SecurityModel(symbol=symbol, name=f"{symbol} Ltd", is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model.id


@pytest.mark.asyncio
async def test_price_jump_explained_by_corporate_action_is_not_unexplained(
    db_session: AsyncSession,
) -> None:
    """A large move on a real corporate-action ex-date must not be reported as unexplained."""
    security_id = await _seed_security(db_session, "BONUSCO")
    ohlcv_repo = SqlOHLCVRepository(db_session)
    action_repo = SqlCorporateActionRepository(db_session)

    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=date(2024, 1, 1), open=Decimal("400"), high=Decimal("400"),
                low=Decimal("400"), close=Decimal("400"), volume=1000,
            ),
            OHLCVBar(
                date=date(2024, 1, 2), open=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"), volume=1000,
            ),
        ],
    )
    await action_repo.save_many(
        security_id,
        [
            RawCorporateAction(
                symbol="BONUSCO",
                ex_date=date(2024, 1, 2),
                action_type="bonus",
                ratio=Decimal("0.25"),
                raw_subject="Bonus 1:3",
            )
        ],
    )
    await db_session.commit()

    report = DataQualityReport(ohlcv_repo=ohlcv_repo, corporate_action_repo=action_repo)
    result = await report.execute(security_id, date(2024, 1, 1), date(2024, 1, 2))

    assert result["price_anomalies_total"] == 1
    assert result["price_anomalies_explained_by_corporate_action"] == 1
    assert result["unexplained_price_anomalies"] == []


@pytest.mark.asyncio
async def test_price_jump_without_corporate_action_is_unexplained(
    db_session: AsyncSession,
) -> None:
    """A large move with no matching corporate action must be reported as unexplained."""
    security_id = await _seed_security(db_session, "GLITCHCO")
    ohlcv_repo = SqlOHLCVRepository(db_session)
    action_repo = SqlCorporateActionRepository(db_session)

    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=date(2024, 1, 1), open=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"), volume=1000,
            ),
            OHLCVBar(
                date=date(2024, 1, 2), open=Decimal("500"), high=Decimal("500"),
                low=Decimal("500"), close=Decimal("500"), volume=1000,
            ),
        ],
    )
    await db_session.commit()

    report = DataQualityReport(ohlcv_repo=ohlcv_repo, corporate_action_repo=action_repo)
    result = await report.execute(security_id, date(2024, 1, 1), date(2024, 1, 2))

    assert result["price_anomalies_total"] == 1
    assert len(result["unexplained_price_anomalies"]) == 1
