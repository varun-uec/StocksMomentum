"""Daily alerts (FR-22, M15): the API contract, a firing, and chart-alert parity.

Parity (M15 exit): for every alert source, the values the evaluator reads equal
the chart API's values for the same bars and ``data_version``.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.alert import Alert, AlertSource
from momentum25.infrastructure.config.strategy_loader import load_strategy_file
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import OHLCVDailyModel, SecurityModel
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.interface.api.dependencies import evaluate_alerts_with
from momentum25.main import create_app

_STRATEGY = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)


def _weekdays_until(last: date, count: int) -> list[date]:
    days: list[date] = []
    day = last
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days[::-1]


# 300 sessions to a week ago, then 5 more the alert can fire on.
_TODAY = date.today()
_ALL = _weekdays_until(_TODAY - timedelta(days=1), 305)
_HISTORY, _LATER = _ALL[:300], _ALL[300:]


def _close(i: int) -> Decimal:
    return Decimal(str(round(100 + 10 * math.sin(i / 7) + i * 0.05, 2)))


async def _add_bars(session: AsyncSession, security_id: int, days: list[date], start: int) -> None:
    for i, day in enumerate(days, start=start):
        close = _close(i)
        session.add(
            OHLCVDailyModel(
                security_id=security_id,
                date=day,
                open=close,
                high=close * Decimal("1.01"),
                low=close * Decimal("0.99"),
                close=close,
                volume=100_000,
                adj_factor=Decimal("1"),
                adj_close=close,
            )
        )
    await session.commit()


@pytest.fixture
async def security_id(db_session: AsyncSession) -> int:
    await SqlStrategyRepository(db_session).upsert(load_strategy_file(_STRATEGY))
    security = SecurityModel(symbol="ALRT", name="Alert Test Ltd", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await _add_bars(db_session, security.id, _HISTORY, 0)
    return security.id


@pytest.fixture
async def client(security_id: int) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await get_database().engine.dispose()


def _alert(**overrides: Any) -> dict[str, Any]:
    body = {"symbol": "ALRT", "source": "close", "condition": "above", "threshold": "0"}
    return {**body, **overrides}


async def test_an_alert_watches_bars_after_the_last_session_and_fires_once(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    created = await client.post("/api/v1/alerts", json=_alert())
    assert created.status_code == 201
    alert = created.json()
    assert (alert["status"], alert["armed_after"], alert["interval"]) == (
        "active",
        _HISTORY[-1].isoformat(),
        "1D",
    )

    nothing = (await client.post("/api/v1/alerts/evaluate")).json()
    assert nothing == {"evaluated": 1, "fired": 0, "failed": []}  # no bar after armed_after yet

    await _add_bars(db_session, security_id, _LATER, 300)
    fired = (await client.post("/api/v1/alerts/evaluate")).json()
    assert fired == {"evaluated": 1, "fired": 1, "failed": []}
    listed = (await client.get("/api/v1/alerts")).json()
    [row] = listed["alerts"]
    prices = (await client.get("/api/v1/securities/ALRT/ohlcv")).json()
    assert row["status"] == "triggered"
    assert row["triggered_on"] == _LATER[0].isoformat()  # the first bar after armed_after
    assert Decimal(row["trigger_value"]) == Decimal(prices["bars"][300]["close"])
    assert row["data_version"] == prices["data_version"]
    assert listed["unseen"] == 1

    again = (await client.post("/api/v1/alerts/evaluate")).json()
    assert again["evaluated"] == 0  # a fired alert is not checked again

    assert (await client.post("/api/v1/alerts/seen")).status_code == 204
    assert (await client.get("/api/v1/alerts")).json()["unseen"] == 0

    rearmed = (await client.post(f"/api/v1/alerts/{row['id']}/rearm")).json()
    assert (rearmed["status"], rearmed["armed_after"], rearmed["triggered_on"]) == (
        "active",
        _LATER[-1].isoformat(),
        None,
    )
    assert (await client.delete(f"/api/v1/alerts/{row['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/alerts/{row['id']}")).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        _alert(source="vwap"),
        _alert(condition="near"),
        _alert(interval="1H"),
        _alert(threshold="NaN"),
        _alert(threshold="1.23456"),
        _alert(symbol="alrt"),
        {**_alert(), "repeat": True},
    ],
)
async def test_invalid_alerts_are_rejected(client: httpx.AsyncClient, body: dict[str, Any]) -> None:
    assert (await client.post("/api/v1/alerts", json=body)).status_code == 422


async def test_an_unknown_symbol_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/alerts", json=_alert(symbol="NOPE"))).status_code == 404


@pytest.mark.parametrize("interval", ["1D", "1W", "1M"])
async def test_the_alert_reads_the_charts_own_values(
    client: httpx.AsyncClient, db_session: AsyncSession, interval: str
) -> None:
    """Parity: every source, value for value, with the chart API's data version."""
    prices = (
        await client.get("/api/v1/securities/ALRT/ohlcv", params={"interval": interval})
    ).json()
    indicators = (
        await client.get("/api/v1/stocks/ALRT/indicators/series", params={"interval": interval})
    ).json()
    evaluator = evaluate_alerts_with(db_session)
    for source in get_args(AlertSource):
        alert = Alert(
            symbol="ALRT",
            source=source,
            interval=interval,  # type: ignore[arg-type]
            condition="above",
            threshold=Decimal("0"),
            armed_after=_HISTORY[0],
        )
        points, version, _ = await evaluator.inputs(alert)
        chart = prices["bars"] if source == "close" else indicators["bars"]
        expected = [
            (b["date"], None if b[source] is None else Decimal(b[source])) for b in chart
        ]
        assert [(p.date.isoformat(), p.value) for p in points] == expected, source
        assert version == prices["data_version"] == indicators["data_version"]
        # The comparison must not pass on empty series. 300 sessions make 14
        # monthly bars: too few for the indicators to warm up, so there only
        # close is checked.
        if interval != "1M" or source == "close":
            assert any(p.value is not None for p in points), source


async def test_a_bonus_after_arming_rescales_a_price_threshold(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    """A 1:1 bonus halves every earlier adjusted bar; a price alert must not fire on it.

    ``below`` at 90 is set while closes run about 100-125. After the bonus the
    later bars trade near half that. On the chart nothing fell, so nothing fires.
    """
    created = await client.post("/api/v1/alerts", json=_alert(condition="below", threshold="90"))
    rsi = await client.post(
        "/api/v1/alerts", json=_alert(source="rsi14", condition="above", threshold="100")
    )
    # Fires only if rescaled: just under twice the lowest post-bonus close, so
    # half of it sits under every later bar, while the raw value sits far above.
    lowest_later = min(_close(i) / 2 for i in range(300, 305))
    rescaled = await client.post(
        "/api/v1/alerts",
        json=_alert(condition="above", threshold=str(lowest_later * 2 - Decimal("1"))),
    )
    assert created.status_code == rsi.status_code == rescaled.status_code == 201
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    await db_session.commit()
    for i, day in enumerate(_LATER, start=300):
        close = _close(i) / 2
        db_session.add(
            OHLCVDailyModel(
                security_id=security_id,
                date=day,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=200_000,
                adj_factor=Decimal("1"),
                adj_close=close,
            )
        )
    await db_session.commit()
    result = (await client.post("/api/v1/alerts/evaluate")).json()
    fired = [a for a in (await client.get("/api/v1/alerts")).json()["alerts"] if a["triggered_on"]]
    assert result["fired"] == 1
    assert [a["id"] for a in fired] == [rescaled.json()["id"]]
