"""The chart endpoint adjusts stored prices exactly once (ADR-013 §4).

GOLDIAM's 1:3 bonus went ex on 2026-07-10, so earlier bars carry
``adj_factor`` 0.75. The stored rows below are the real prints. On the adjusted
basis the close rose from 315.3750 to 378.0000 that day (+19.86%), which
published prices confirm (owner review, 2026-10-18).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import OHLCVDailyModel, SecurityModel
from momentum25.main import create_app

_ROWS = [  # date, raw close, adj_factor, volume
    (date(2026, 7, 9), Decimal("420.5000"), Decimal("0.75"), 300_000),
    (date(2026, 7, 10), Decimal("378.0000"), Decimal("1"), 900_000),
]


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    security = SecurityModel(symbol="GOLDIAM", name="Goldiam International Limited", is_active=True)
    db_session.add(security)
    await db_session.flush()
    for day, close, factor, volume in _ROWS:
        db_session.add(
            OHLCVDailyModel(
                security_id=security.id,
                date=day,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=volume,
                adj_factor=factor,
                adj_close=close * factor,
            )
        )
    await db_session.commit()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await get_database().engine.dispose()


async def test_the_bonus_day_shows_the_adjusted_rise(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/securities/GOLDIAM/ohlcv", params={"to": "2026-07-10"})
    assert res.status_code == 200
    bars = res.json()["bars"]
    closes = [Decimal(b["close"]) for b in bars]
    assert closes == [Decimal("315.3750"), Decimal("378.0000")]
    assert round(closes[1] / closes[0] - 1, 4) == Decimal("0.1986")
    assert [b["volume"] for b in bars] == [400_000, 900_000]


async def test_prices_are_adjusted_once_not_twice(client: httpx.AsyncClient) -> None:
    """The chart close equals the stored ``adj_close``, not ``adj_close`` × factor again."""
    res = await client.get("/api/v1/securities/GOLDIAM/ohlcv", params={"to": "2026-07-10"})
    first = res.json()["bars"][0]
    assert Decimal(first["close"]) == _ROWS[0][1] * _ROWS[0][2]  # 315.375, not 236.53
    assert Decimal(first["open"]) == Decimal("315.3750")


async def test_the_schedule_names_the_bonus(client: httpx.AsyncClient) -> None:
    res = await client.get(
        "/api/v1/securities/GOLDIAM/ohlcv", params={"from": "2026-07-10", "to": "2026-07-10"}
    )
    body = res.json()
    assert [b["date"] for b in body["bars"]] == ["2026-07-10"]
    assert [(s["until"], Decimal(s["factor"])) for s in body["adjustments"]] == [
        ("2026-07-09", Decimal("0.75")),
        ("2026-07-10", Decimal("1")),
    ]
