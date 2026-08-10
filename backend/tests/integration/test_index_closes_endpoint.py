"""Integration tests for GET /indices/{index_code}/closes.

The analysis screen's benchmark-relative overlay asked
``/securities/NIFTY500/ohlcv`` and got a 404: NIFTY500 is an index, not a
security, and its closes live in ``benchmark_index_daily``. These tests
pin the endpoint that serves them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.ports.market_data import RawIndexBar
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)
from momentum25.main import create_app

_INDEX = "TESTIDX500"


async def _seed(session: AsyncSession) -> None:
    repo = SqlBenchmarkIndexRepository(session)
    await repo.upsert_bars(
        _INDEX,
        [
            RawIndexBar(index_code=_INDEX, date=date(2024, 1, 3), close=Decimal("20400")),
            RawIndexBar(index_code=_INDEX, date=date(2024, 1, 1), close=Decimal("20000")),
            RawIndexBar(index_code=_INDEX, date=date(2024, 1, 2), close=Decimal("20200")),
        ],
    )
    await session.commit()


@pytest.mark.asyncio
async def test_returns_full_series_oldest_first(db_session: AsyncSession) -> None:
    await _seed(db_session)

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/indices/{_INDEX}/closes")

    assert response.status_code == 200
    body = response.json()
    assert body["index_code"] == _INDEX
    assert [b["date"] for b in body["bars"]] == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert [b["close"] for b in body["bars"]] == ["20000.0000", "20200.0000", "20400.0000"]


@pytest.mark.asyncio
async def test_honours_from_and_to_range(db_session: AsyncSession) -> None:
    await _seed(db_session)

    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/indices/{_INDEX}/closes",
            params={"from": "2024-01-02", "to": "2024-01-02"},
        )

    assert response.status_code == 200
    assert [b["date"] for b in response.json()["bars"]] == ["2024-01-02"]


@pytest.mark.asyncio
async def test_lower_case_code_resolves(db_session: AsyncSession) -> None:
    await _seed(db_session)

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/indices/{_INDEX.lower()}/closes")

    assert response.status_code == 200
    assert response.json()["index_code"] == _INDEX


@pytest.mark.asyncio
async def test_unknown_index_is_404_not_an_empty_series(db_session: AsyncSession) -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/indices/NOSUCHINDEX/closes")

    assert response.status_code == 404
