"""The legacy run trigger must schedule the same pipeline as the explicit execute route."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.config.settings import get_settings
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

    repeated = await client.post(
        "/api/v1/runs",
        json={"strategy": "minervini_trend_template", "force": False},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["id"] == run["id"]
    assert scheduled == [("minervini_trend_template", False, run["id"])]


async def test_forced_run_is_rejected_before_creating_a_run_when_downloads_are_disabled(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED", "false")
    get_settings.cache_clear()

    for path, body in (
        ("/api/v1/runs", {"strategy": "minervini_trend_template", "force": True}),
        (
            "/api/v1/runs/execute",
            {
                "strategy": "minervini_trend_template",
                "force": True,
                "background": False,
            },
        ),
    ):
        response = await client.post(path, json=body)
        assert response.status_code == 409, response.text
        assert "Forced exchange downloads are disabled" in response.json()["detail"]
        runs = await client.get("/api/v1/runs")
        assert runs.status_code == 200
        assert runs.json()["total"] == 0
    get_settings.cache_clear()


@pytest.mark.parametrize("path", ["/api/v1/runs/{n}", "/api/v1/rankings/runs/{n}"])
async def test_a_run_id_beyond_64_bits_is_rejected_not_a_server_error(
    client: httpx.AsyncClient, path: str
) -> None:
    """R3-B-19: the driver overflowed on an id above 2**63 and the API answered 500."""
    response = await client.get(path.format(n=10**20))
    assert response.status_code == 422
