"""Daily alerts (FR-22, M15): the API contract, a firing, and chart-alert parity.

Parity (M15 exit): for every alert source, the values the evaluator reads equal
the chart API's values for the same bars and ``data_version``.
"""

from __future__ import annotations

import asyncio
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

from momentum25.application.use_cases.alerts import EvaluateAlerts
from momentum25.domain.entities.alert import Alert, AlertSource, SeriesPoint
from momentum25.infrastructure.config.strategy_loader import load_strategy_file
from momentum25.infrastructure.persistence.models import AlertModel, OHLCVDailyModel, SecurityModel
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.infrastructure.persistence.repositories.alerts import SqlAlertRepository
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


async def test_overlapping_evaluations_only_report_a_new_firing_once(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    security_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manual check and the scheduled job may evaluate one alert together."""
    created = await client.post("/api/v1/alerts", json=_alert())
    assert created.status_code == 201
    await _add_bars(db_session, security_id, _LATER, 300)

    original_inputs = EvaluateAlerts.inputs
    both_read = asyncio.Event()
    readers = 0

    async def wait_until_both_have_read(
        evaluator: EvaluateAlerts, alert: Alert
    ) -> tuple[list[SeriesPoint], str, Decimal]:
        nonlocal readers
        result = await original_inputs(evaluator, alert)
        readers += 1
        if readers == 2:
            both_read.set()
        await both_read.wait()
        return result

    monkeypatch.setattr(EvaluateAlerts, "inputs", wait_until_both_have_read)
    responses = await asyncio.gather(
        client.post("/api/v1/alerts/evaluate"),
        client.post("/api/v1/alerts/evaluate"),
    )
    assert all(response.status_code == 200 for response in responses)

    # Only the request whose conditional update changed active -> triggered
    # should report a new firing. The other request observes the one-shot win.
    assert sum(response.json()["fired"] for response in responses) == 1
    [alert] = (await client.get("/api/v1/alerts")).json()["alerts"]
    assert alert["status"] == "triggered"


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


async def test_edit_armed_rule_starts_new_window_and_rejects_stale_or_triggered_edits(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    initial = (await client.post("/api/v1/alerts", json=_alert(threshold="9999"))).json()
    await _add_bars(db_session, security_id, _LATER, 300)
    payload = _alert(threshold="0", expected_revision=initial["revision"])
    edited = await client.patch(f"/api/v1/alerts/{initial['id']}", json=payload)
    assert edited.status_code == 200
    assert edited.json()["revision"] == initial["revision"] + 1
    assert edited.json()["armed_after"] == _LATER[-1].isoformat()
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 0
    assert (await client.patch(f"/api/v1/alerts/{initial['id']}", json=payload)).status_code == 409
    assert (await client.patch("/api/v1/alerts/999999", json=payload)).status_code == 404

    # An immutable firing cannot be retroactively redefined by the editor.
    await db_session.execute(
        update(AlertModel).where(AlertModel.id == initial["id"]).values(armed_after=_HISTORY[-1])
    )
    await db_session.commit()
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1
    before = (await client.get("/api/v1/alerts")).json()["alerts"][0]
    rejected = await client.patch(
        f"/api/v1/alerts/{initial['id']}",
        json=_alert(threshold="900", expected_revision=before["revision"]),
    )
    assert rejected.status_code == 409
    assert (await client.get("/api/v1/alerts")).json()["alerts"][0] == before


async def test_an_inflight_old_evaluation_cannot_fire_a_newly_edited_rule(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    security_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = (await client.post("/api/v1/alerts", json=_alert())).json()
    await _add_bars(db_session, security_id, _LATER, 300)
    read = asyncio.Event()
    resume = asyncio.Event()
    original = EvaluateAlerts.inputs

    async def pause(
        evaluator: EvaluateAlerts, alert: Alert
    ) -> tuple[list[SeriesPoint], str, Decimal]:
        result = await original(evaluator, alert)
        read.set()
        await resume.wait()
        return result

    monkeypatch.setattr(EvaluateAlerts, "inputs", pause)
    pending = asyncio.create_task(client.post("/api/v1/alerts/evaluate"))
    await asyncio.wait_for(read.wait(), timeout=10)
    edited = await client.patch(
        f"/api/v1/alerts/{initial['id']}",
        json=_alert(threshold="9999", expected_revision=initial["revision"]),
    )
    resume.set()
    assert edited.status_code == 200
    assert (await asyncio.wait_for(pending, timeout=10)).json()["fired"] == 0
    assert (await client.get("/api/v1/alerts")).json()["alerts"][0]["status"] == "active"


async def _save_alert_drawing(
    client: httpx.AsyncClient, kind: str, prices: list[Decimal], *, revision: int | None = None
) -> httpx.Response:
    drawing = {
        "id": "monitor-level",
        "kind": kind,
        "color": "#456789",
        "points": [{"date": _HISTORY[-1].isoformat(), "price": str(price)} for price in prices],
        "hidden": True,
        "locked": True,
        "dash": "dashed",
    }
    headers = {"If-Match": f'"{revision}"'} if revision else {"If-None-Match": "*"}
    return await client.put("/api/v1/drawings/ALRT", json={"drawings": [drawing]}, headers=headers)


@pytest.mark.parametrize("kind", ["horizontal", "hline"])
async def test_drawing_rule_captures_saved_anchors_and_survives_edits_and_deletion(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int, kind: str
) -> None:
    level = (_close(299) + _close(300)) / 2
    assert _close(299) < level < _close(300)
    assert (await _save_alert_drawing(client, kind, [level])).status_code == 201
    created = await client.post(
        "/api/v1/alerts",
        json=_alert(condition="crosses_above", threshold="99999", drawing_id="monitor-level"),
    )
    assert created.status_code == 201
    row = created.json()
    assert row["drawing"]["revision"] == 1
    assert row["drawing"]["kind"] == kind
    assert Decimal(row["drawing"]["points"][0]["price"]) == level
    assert (
        await _save_alert_drawing(client, kind, [Decimal("99999")], revision=1)
    ).status_code == 200
    # Explicitly editing is the only way to pick up newly saved anchors.
    refreshed = await client.patch(
        f"/api/v1/alerts/{row['id']}",
        json=_alert(condition="crosses_above", drawing_id="monitor-level", expected_revision=1),
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["drawing"]["revision"] == 2
    assert Decimal(refreshed.json()["drawing"]["points"][0]["price"]) == Decimal("99999")

    # Restore a genuine crossing snapshot, then remove the live drawing.
    assert (await _save_alert_drawing(client, kind, [level], revision=2)).status_code == 200
    restored = await client.patch(
        f"/api/v1/alerts/{row['id']}",
        json=_alert(condition="crosses_above", drawing_id="monitor-level", expected_revision=2),
    )
    assert restored.status_code == 200
    removed = await client.put(
        "/api/v1/drawings/ALRT", json={"drawings": []}, headers={"If-Match": '"3"'}
    )
    assert removed.status_code == 200
    await _add_bars(db_session, security_id, _LATER, 300)
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1
    triggered = (await client.get("/api/v1/alerts")).json()["alerts"][0]
    assert triggered["triggered_on"] == _LATER[0].isoformat()
    assert triggered["drawing"]["revision"] == 3


async def test_rectangle_entry_is_backend_authoritative_and_ignores_visual_time_extent(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    lower = (_close(299) + _close(300)) / 2
    upper = _close(300) + Decimal("2")
    assert (await _save_alert_drawing(client, "rectangle", [upper, lower])).status_code == 201
    created = await client.post(
        "/api/v1/alerts", json=_alert(condition="enters_zone", drawing_id="monitor-level")
    )
    assert created.status_code == 201
    await _add_bars(db_session, security_id, _LATER, 300)
    checked = (await client.post("/api/v1/alerts/evaluate")).json()
    assert checked["fired"] == 1
    [triggered] = (await client.get("/api/v1/alerts")).json()["alerts"]
    assert triggered["triggered_on"] == _LATER[0].isoformat()
    assert Decimal(triggered["trigger_value"]) == _close(300)


async def test_each_drawing_anchor_uses_its_own_traded_price_adjustment(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    # One anchor precedes the bonus; the second was traded in the new basis.
    saved = await _save_alert_drawing(client, "rectangle", [Decimal("100"), Decimal("120")])
    assert saved.status_code == 201
    drawing_body = saved.json()["body"]
    drawing_body["drawings"][0]["points"][1]["date"] = _LATER[0].isoformat()
    assert (
        await client.put("/api/v1/drawings/ALRT", json=drawing_body, headers={"If-Match": '"1"'})
    ).status_code == 200
    created = await client.post(
        "/api/v1/alerts", json=_alert(condition="leaves_zone", drawing_id="monitor-level")
    )
    assert created.status_code == 201
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    await db_session.commit()
    # Later market history may use a different factor while snapshot stays traded.
    await _add_bars(db_session, security_id, _LATER, 300)
    alert = await SqlAlertRepository(db_session).get(created.json()["id"])
    assert alert is not None
    _, version, lower, upper = await evaluate_alerts_with(db_session).drawing_inputs(alert)
    assert (lower, upper) == (Decimal("50"), Decimal("120"))
    assert version
    assert [point.price for point in alert.drawing.points] == [Decimal("100"), Decimal("120")]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": "rsi14"},
        {"interval": "1W"},
        {"condition": "above"},
        {"condition": "enters_zone"},
    ],
)
async def test_unsupported_drawing_rules_are_rejected(
    client: httpx.AsyncClient, overrides: dict[str, Any]
) -> None:
    assert (await _save_alert_drawing(client, "horizontal", [Decimal("100")])).status_code == 201
    response = await client.post(
        "/api/v1/alerts",
        json=_alert(**{"condition": "crosses_above", "drawing_id": "monitor-level", **overrides}),
    )
    assert response.status_code == 422


async def test_a_missing_or_unsupported_drawing_cannot_be_armed(client: httpx.AsyncClient) -> None:
    payload = _alert(condition="crosses_above", drawing_id="monitor-level")
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 404
    assert (await _save_alert_drawing(client, "trendline", [Decimal("100")])).status_code == 201
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 422
    # A rectangle with one anchor or identical prices has no defensible zone.
    assert (
        await _save_alert_drawing(client, "rectangle", [Decimal("100")], revision=1)
    ).status_code == 200
    zone = _alert(condition="enters_zone", drawing_id="monitor-level")
    assert (await client.post("/api/v1/alerts", json=zone)).status_code == 422


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
        expected = [(b["date"], None if b[source] is None else Decimal(b[source])) for b in chart]
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


async def test_rearming_after_a_bonus_preserves_the_effective_price_level(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    created = (await client.post("/api/v1/alerts", json=_alert(threshold="90"))).json()
    await _add_bars(db_session, security_id, _LATER[:1], 300)
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    await db_session.commit()
    close = _close(301) / 2
    db_session.add(
        OHLCVDailyModel(
            security_id=security_id,
            date=_LATER[1],
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
    rearmed = (await client.post(f"/api/v1/alerts/{created['id']}/rearm")).json()
    assert rearmed["armed_after"] == _LATER[1].isoformat()
    assert Decimal(rearmed["threshold"]) == Decimal("45")
    # Repeating in the same basis must not apply the split a second time.
    again = (await client.post(f"/api/v1/alerts/{created['id']}/rearm")).json()
    assert Decimal(again["threshold"]) == Decimal("45")
    later_close = _close(302) / 2
    db_session.add(
        OHLCVDailyModel(
            security_id=security_id,
            date=_LATER[2],
            open=later_close,
            high=later_close,
            low=later_close,
            close=later_close,
            volume=200_000,
            adj_factor=Decimal("1"),
            adj_close=later_close,
        )
    )
    await db_session.commit()
    assert Decimal("45") < later_close < Decimal("90")
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1


@pytest.mark.parametrize(
    "source", ["atr14", "macd_line", "macd_signal", "macd_histogram", "rsi14", "adx14"]
)
async def test_rearm_rescales_only_price_scaled_studies(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int, source: str
) -> None:
    created = (
        await client.post("/api/v1/alerts", json=_alert(source=source, threshold="70"))
    ).json()
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    await db_session.commit()
    await _add_bars(db_session, security_id, _LATER, 300)
    response = await client.post(f"/api/v1/alerts/{created['id']}/rearm")
    assert response.status_code == 200
    expected = Decimal("70") if source in {"rsi14", "adx14"} else Decimal("35")
    assert Decimal(response.json()["threshold"]) == expected


async def test_drawing_capture_rejects_a_stale_saved_revision(
    client: httpx.AsyncClient,
) -> None:
    assert (await _save_alert_drawing(client, "horizontal", [Decimal("100")])).status_code == 201
    payload = _alert(
        condition="crosses_above", drawing_id="monitor-level", expected_drawing_revision=1
    )
    created = await client.post("/api/v1/alerts", json=payload)
    assert created.status_code == 201
    assert (
        await _save_alert_drawing(client, "horizontal", [Decimal("120")], revision=1)
    ).status_code == 200
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 409
    edited = await client.patch(
        f"/api/v1/alerts/{created.json()['id']}", json={**payload, "expected_revision": 1}
    )
    assert edited.status_code == 409
    current = (await client.get("/api/v1/alerts")).json()["alerts"][0]
    assert current["drawing"]["revision"] == 1
    assert Decimal(current["drawing"]["points"][0]["price"]) == Decimal("100")


async def test_rule_edit_rejects_a_stale_market_price_basis(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    before = (await client.get("/api/v1/securities/ALRT/ohlcv")).json()
    created = (await client.post("/api/v1/alerts", json=_alert(threshold="90"))).json()
    await _add_bars(db_session, security_id, _LATER, 300)
    payload = _alert(threshold="90", expected_data_version=before["data_version"])
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 409
    assert (
        await client.patch(
            f"/api/v1/alerts/{created['id']}", json={**payload, "expected_revision": 1}
        )
    ).status_code == 409
    current = (await client.get("/api/v1/securities/ALRT/ohlcv")).json()
    payload["expected_data_version"] = current["data_version"]
    assert (
        await client.patch(
            f"/api/v1/alerts/{created['id']}", json={**payload, "expected_revision": 1}
        )
    ).status_code == 200


async def test_rectangle_geometry_is_validated_after_each_anchor_is_adjusted(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    await db_session.commit()
    await _add_bars(db_session, security_id, _LATER, 300)
    saved = await _save_alert_drawing(client, "rectangle", [Decimal("100"), Decimal("100")])
    body = saved.json()["body"]
    body["drawings"][0]["points"][1]["date"] = _LATER[-1].isoformat()
    assert (
        await client.put("/api/v1/drawings/ALRT", json=body, headers={"If-Match": '"1"'})
    ).status_code == 200
    # Traded prices equal; adjusted bounds are 50 and 100, so this is a real zone.
    payload = _alert(condition="enters_zone", drawing_id="monitor-level")
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 201
    # Traded prices differ; adjusted bounds are both 50, so it is degenerate.
    body["drawings"][0]["points"][1]["price"] = "50"
    assert (
        await client.put("/api/v1/drawings/ALRT", json=body, headers={"If-Match": '"2"'})
    ).status_code == 200
    assert (await client.post("/api/v1/alerts", json=payload)).status_code == 422


async def test_an_edited_drawing_rule_replays_after_another_corporate_action(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    assert (await _save_alert_drawing(client, "horizontal", [Decimal("100")])).status_code == 201
    created = (
        await client.post(
            "/api/v1/alerts", json=_alert(condition="crosses_above", drawing_id="monitor-level")
        )
    ).json()
    # The first bonus changes the chart basis before the drawing is edited.
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=Decimal("0.5"))
    )
    close = _close(300) / 2
    db_session.add(
        OHLCVDailyModel(
            security_id=security_id,
            date=_LATER[0],
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
    new_level = (_close(300) + _close(301)) / 4
    drawing = {
        "id": "monitor-level",
        "kind": "horizontal",
        "color": "#456789",
        "points": [{"date": _LATER[0].isoformat(), "price": str(new_level)}],
    }
    assert (
        await client.put(
            "/api/v1/drawings/ALRT", json={"drawings": [drawing]}, headers={"If-Match": '"1"'}
        )
    ).status_code == 200
    refreshed = await client.patch(
        f"/api/v1/alerts/{created['id']}",
        json=_alert(
            condition="crosses_above",
            drawing_id="monitor-level",
            expected_revision=1,
            expected_drawing_revision=2,
        ),
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["armed_after"] == _LATER[0].isoformat()
    # A second bonus rescales the captured anchor without re-reading its drawing.
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .values(adj_factor=OHLCVDailyModel.adj_factor * Decimal("0.5"))
    )
    for i, day in enumerate(_LATER[1:3], start=301):
        value = _close(i) / 4
        db_session.add(
            OHLCVDailyModel(
                security_id=security_id,
                date=day,
                open=value,
                high=value,
                low=value,
                close=value,
                volume=400_000,
                adj_factor=Decimal("1"),
                adj_close=value,
            )
        )
    await db_session.commit()
    # A delayed job sees both later sessions but selects the first crossing.
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1
    [fired] = (await client.get("/api/v1/alerts")).json()["alerts"]
    assert fired["triggered_on"] == _LATER[1].isoformat()
    assert Decimal(fired["trigger_value"]) == (_close(301) / 4).quantize(Decimal("0.0001"))
    assert Decimal(fired["drawing"]["points"][0]["price"]) == new_level


async def _save_line(
    client: httpx.AsyncClient,
    kind: str,
    anchors: list[tuple[date, Decimal]],
    *,
    revision: int | None = None,
) -> httpx.Response:
    drawing = {
        "id": "monitor-line",
        "kind": kind,
        "color": "#456789",
        "points": [{"date": d.isoformat(), "price": str(p)} for d, p in anchors],
    }
    headers = {"If-Match": f'"{revision}"'} if revision else {"If-None-Match": "*"}
    return await client.put("/api/v1/drawings/ALRT", json={"drawings": [drawing]}, headers=headers)


async def test_a_sloped_ray_fires_on_its_first_close_cross_and_ignores_later_drawing_edits(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    """The ray rises 0.01 a session and meets session 299's close, so session 300 crosses it."""
    slope = Decimal("0.01")
    anchors = [(_HISTORY[-11], _close(299) - 10 * slope), (_HISTORY[-1], _close(299))]
    assert _close(300) > _close(299) + slope
    assert (await _save_line(client, "ray", anchors)).status_code == 201
    created = await client.post(
        "/api/v1/alerts",
        json=_alert(condition="crosses_above", drawing_id="monitor-line"),
    )
    assert created.status_code == 201
    row = created.json()
    assert (row["drawing"]["kind"], row["drawing"]["revision"]) == ("ray", 1)
    assert [Decimal(p["price"]) for p in row["drawing"]["points"]] == [p for _, p in anchors]

    # Snapshot freeze: moving the saved line far above price changes nothing.
    moved = [(d, p + 1000) for d, p in anchors]
    assert (await _save_line(client, "ray", moved, revision=1)).status_code == 200
    await _add_bars(db_session, security_id, _LATER, 300)
    assert (await client.post("/api/v1/alerts/evaluate")).json()["fired"] == 1
    [fired] = (await client.get("/api/v1/alerts")).json()["alerts"]
    assert fired["triggered_on"] == _LATER[0].isoformat()
    assert Decimal(fired["trigger_value"]) == _close(300)
    assert fired["drawing"]["revision"] == 1
    # Idempotent: a second evaluation finds nothing to do and changes nothing.
    again = (await client.post("/api/v1/alerts/evaluate")).json()
    assert (again["evaluated"], again["fired"]) == (0, 0)
    assert (await client.get("/api/v1/alerts")).json()["alerts"] == [fired]


async def test_a_trendline_ending_before_arming_never_fires(
    client: httpx.AsyncClient, db_session: AsyncSession, security_id: int
) -> None:
    anchors = [(_HISTORY[-11], Decimal("1")), (_HISTORY[-1], Decimal("2"))]
    assert (await _save_line(client, "trendline", anchors)).status_code == 201
    created = await client.post(
        "/api/v1/alerts", json=_alert(condition="crosses_below", drawing_id="monitor-line")
    )
    assert created.status_code == 201
    await _add_bars(db_session, security_id, _LATER, 300)
    assert (await client.post("/api/v1/alerts/evaluate")).json() == {
        "evaluated": 1,
        "fired": 0,
        "failed": [],
    }


@pytest.mark.parametrize(
    ("kind", "anchors", "condition"),
    [
        ("trendline", [(-1, "100"), (-1, "101")], "crosses_above"),  # one session
        ("ray", [(-1, "100"), (-5, "101")], "crosses_above"),  # points back in time
        ("extended", [(-5, "100"), (-1, "101")], "enters_zone"),  # lines need a crossing
        ("ray", [(-5, "100")], "crosses_above"),  # one anchor
    ],
)
async def test_invalid_line_rules_are_rejected(
    client: httpx.AsyncClient, kind: str, anchors: list[tuple[int, str]], condition: str
) -> None:
    points = [(_HISTORY[i], Decimal(p)) for i, p in anchors]
    assert (await _save_line(client, kind, points)).status_code == 201
    response = await client.post(
        "/api/v1/alerts", json=_alert(condition=condition, drawing_id="monitor-line")
    )
    assert response.status_code == 422
