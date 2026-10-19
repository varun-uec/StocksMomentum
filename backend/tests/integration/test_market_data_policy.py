"""Public market-data policy is opt-in and disabled refreshes never call providers."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from momentum25.infrastructure.config.settings import get_settings
from momentum25.main import create_app


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED", "false")
    get_settings.cache_clear()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    get_settings.cache_clear()


async def test_download_policy_defaults_off_and_rejects_exchange_refreshes(
    client: httpx.AsyncClient,
) -> None:
    policy = await client.get("/api/v1/market-data/status")
    assert policy.status_code == 200
    assert policy.json() == {
        "direct_exchange_downloads_enabled": False,
        "authorized_csv_import_supported": True,
    }

    refresh = await client.post("/api/v1/market-data/refresh", json={"exchanges": ["NSE"]})
    assert refresh.status_code == 409
    assert "disabled" in refresh.json()["detail"]

    corporate_actions = await client.post("/api/v1/research/corporate-actions/refresh")
    assert corporate_actions.status_code == 409
    assert "disabled" in corporate_actions.json()["detail"]

    live_refresh = await client.get("/api/v1/stocks/RELIANCE/live?refresh=true")
    assert live_refresh.status_code == 409
    assert "disabled" in live_refresh.json()["detail"]
