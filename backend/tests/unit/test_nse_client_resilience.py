"""Tests for NSE outbound throttling/retry (Phase 1.3).

``fetch_historical_bars`` must retry a transient failure instead of giving up
on the first error (the previous implementation had no retry on this path at
all), and must still degrade to an empty list -- never raise -- after
exhausting retries, so a single bad symbol cannot fail a batch job.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from momentum25.infrastructure.providers import nse_client as nse_client_module
from momentum25.infrastructure.providers.nse_client import NSEMarketDataClient
from momentum25.infrastructure.resilience import CircuitBreaker


@pytest.fixture(autouse=True)
def _reset_breaker() -> None:
    """Each test gets a closed circuit breaker (module state is process-global)."""
    nse_client_module._historical_breaker.reset()
    nse_client_module._last_dispatch_time = 0.0


@pytest.mark.asyncio
async def test_transient_failure_is_retried_and_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky(**kwargs: object) -> pd.DataFrame:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("simulated NSE hiccup")
        return pd.DataFrame(
            {
                "datetime": [pd.Timestamp("2026-01-05")],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

    monkeypatch.setattr(
        nse_client_module.historical, "get_stock_historical_data", flaky
    )
    monkeypatch.setattr(
        nse_client_module, "_fetch_historical_dataframe",
        nse_client_module.resilient(
            "nse_historical_fetch_test",
            max_attempts=3,
            min_wait=0.01,
            max_wait=0.02,
            circuit_breaker=nse_client_module._historical_breaker,
        )(nse_client_module._fetch_historical_dataframe.__wrapped__),
    )

    client = NSEMarketDataClient()
    bars = await client.fetch_historical_bars("RELIANCE", date(2026, 1, 1), date(2026, 1, 5))

    assert calls["n"] == 3
    assert len(bars) == 1
    assert bars[0].close == pytest.approx(100.5)


@pytest.mark.asyncio
async def test_persistent_failure_degrades_to_empty_list_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def always_fails(**kwargs: object) -> pd.DataFrame:
        raise ConnectionError("NSE is down")

    monkeypatch.setattr(
        nse_client_module.historical, "get_stock_historical_data", always_fails
    )
    monkeypatch.setattr(
        nse_client_module, "_fetch_historical_dataframe",
        nse_client_module.resilient(
            "nse_historical_fetch_test",
            max_attempts=2,
            min_wait=0.01,
            max_wait=0.02,
            circuit_breaker=CircuitBreaker("nse_historical_test_isolated"),
        )(nse_client_module._fetch_historical_dataframe.__wrapped__),
    )

    client = NSEMarketDataClient()
    bars = await client.fetch_historical_bars("RELIANCE", date(2026, 1, 1), date(2026, 1, 5))

    assert bars == []
