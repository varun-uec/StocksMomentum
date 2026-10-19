"""The legacy run trigger must schedule the same pipeline as the explicit execute route."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.config.strategy_loader import load_strategy_file
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.main import create_app

_STRATEGY_FILE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """Provide the built-in strategy and an in-process API client."""
    await SqlStrategyRepository(db_session).upsert(load_strategy_file(_STRATEGY_FILE))
    await db_session.commit()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await get_database().engine.dispose()


async def test_post_runs_schedules_execution_without_calling_a_market_provider(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending row gets a pipeline task; the test stub makes no external request."""
    scheduled: list[tuple[str, bool, int | None]] = []

    async def record_pipeline(
        strategy_name: str,
        *,
        force: bool = False,
        run_id: int | None = None,
        target_symbols: list[str] | None = None,
        market_data_provider: object | None = None,
    ) -> int:
        scheduled.append((strategy_name, force, run_id))
        return run_id or 0

    monkeypatch.setattr(
        "momentum25.interface.api.routers.runs.run_screening_pipeline", record_pipeline
    )

    response = await client.post(
        "/api/v1/runs",
        json={"strategy": "minervini_trend_template", "force": False},
    )

    assert response.status_code == 202, response.text
    run = response.json()
    assert run["status"] == "PENDING"
    assert scheduled == [("minervini_trend_template", False, run["id"])]
