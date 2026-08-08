"""Integration tests for GET /health/data-freshness (Phase 1.5).

Before this endpoint, the only signal of data currency was a bare "latest
run" timestamp -- indistinguishable from a stale ingest without the reader
doing calendar arithmetic themselves. These tests prove the endpoint
actually classifies against a real NSE trading calendar, not weekday-only
guesswork.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import SqlOHLCVRepository
from momentum25.main import create_app


@pytest.mark.asyncio
async def test_no_data_reports_stale_with_zero_sessions_missed(db_session: AsyncSession) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/health/data-freshness")

    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "STALE"
    assert data["latest_bar_date"] is None


@pytest.mark.asyncio
async def test_latest_bar_far_in_the_past_reports_stale_with_missed_sessions(
    db_session: AsyncSession,
) -> None:
    sec = SecurityModel(symbol="FRESH1", name="Freshness Test Co", is_active=True)
    db_session.add(sec)
    await db_session.flush()
    await db_session.refresh(sec)

    calendar = get_nse_trading_calendar()
    today = date.today()
    # A bar from well over a month ago -- several real sessions have
    # definitely elapsed since, regardless of the exact holiday calendar.
    old_date = today - timedelta(days=45)
    while not calendar.is_session(old_date):
        old_date -= timedelta(days=1)

    repo = SqlOHLCVRepository(db_session)
    await repo.upsert_bars(
        sec.id,
        [
            OHLCVBar(
                date=old_date,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1_000_000,
                turnover_value=Decimal("100000000"),
            )
        ],
    )
    await db_session.commit()

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/health/data-freshness")

    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "STALE"
    assert data["latest_bar_date"] == old_date.isoformat()
    assert data["sessions_missed"] > 0
    assert data["calendar_source"].startswith("XBOM")


@pytest.mark.asyncio
async def test_response_includes_next_session(db_session: AsyncSession) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/health/data-freshness")

    data = response.json()
    assert data["next_session"] is not None
    next_session = date.fromisoformat(data["next_session"])
    assert next_session > date.today()
