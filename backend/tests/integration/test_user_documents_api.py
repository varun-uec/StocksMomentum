"""Contract tests for saved workspaces and drawings (ADR-013 §5).

One test per row of the precondition table, plus validation, a concurrent-write
race, and the 412 body that lets a client recover without a second request.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.database import get_database
from momentum25.main import create_app

DRAWINGS = "/api/v1/drawings/RELIANCE"
WORKSPACE = "/api/v1/workspaces/default"


def _drawing(drawing_id: str = "d1", price: float = 101.5) -> dict[str, Any]:
    return {
        "id": drawing_id,
        "kind": "trendline",
        "points": [{"date": "2026-08-03", "price": price}, {"date": "2026-08-07", "price": 104.0}],
        "color": "#6366f1",
    }


def _stored(drawing: dict[str, Any]) -> dict[str, Any]:
    """A drawing as the server returns it: style defaults filled."""
    return {"width": 2, "text": None, "hidden": False, "locked": False, "dash": "solid", **drawing}


def _workspace(range_: str = "1Y") -> dict[str, Any]:
    return {
        "active_chart_id": "main",
        "charts": {
            "main": {
                "symbol": "RELIANCE",
                "range": range_,
                "mas": [50, 200],
                "panes": ["rsi"],
                "indicators": [
                    {"uid": "sma-a1", "id": "sma", "params": {"period": 20}},
                    {"uid": "st-b2", "id": "supertrend", "params": {"atrPeriod": 10, "mult": 3}},
                    {"uid": "av-c3", "id": "avwap", "params": {"anchor": ""}},
                ],
            }
        },
    }


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    # One event loop for the app and the database engine (see conftest.db_engine).
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    # The race test opens several pooled connections on this loop. Close them, so a
    # later test that runs the app on another loop (sync TestClient) never reuses one.
    await get_database().engine.dispose()


async def _create(client: httpx.AsyncClient) -> httpx.Response:
    return await client.put(
        DRAWINGS, json={"drawings": [_drawing()]}, headers={"If-None-Match": "*"}
    )


async def test_get_missing_document_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get(DRAWINGS)).status_code == 404


async def test_create_then_read_round_trips_with_etag(client: httpx.AsyncClient) -> None:
    created = await _create(client)
    assert created.status_code == 201
    assert created.headers["etag"] == '"1"'
    read = await client.get(DRAWINGS)
    assert read.status_code == 200
    assert read.headers["etag"] == '"1"'
    assert read.json()["revision"] == 1
    assert read.json()["body"] == {"price_basis": "traded", "drawings": [_stored(_drawing())]}


async def test_create_when_present_is_412_and_keeps_the_server_copy(
    client: httpx.AsyncClient,
) -> None:
    await _create(client)
    again = await client.put(DRAWINGS, json={"drawings": []}, headers={"If-None-Match": "*"})
    assert again.status_code == 412
    assert again.json()["current"]["body"]["drawings"] == [_stored(_drawing())]
    assert (await client.get(DRAWINGS)).json()["body"]["drawings"] == [_stored(_drawing())]


async def test_matching_if_match_saves_and_bumps_revision(client: httpx.AsyncClient) -> None:
    await _create(client)
    saved = await client.put(
        DRAWINGS, json={"drawings": [_drawing(price=99.0)]}, headers={"If-Match": '"1"'}
    )
    assert saved.status_code == 200
    assert saved.headers["etag"] == '"2"'
    assert saved.json()["body"]["drawings"][0]["points"][0]["price"] == 99.0


async def test_weak_etag_form_is_accepted(client: httpx.AsyncClient) -> None:
    await _create(client)
    saved = await client.put(DRAWINGS, json={"drawings": []}, headers={"If-Match": 'W/"1"'})
    assert saved.status_code == 200


async def test_stale_if_match_is_412_with_the_current_document(client: httpx.AsyncClient) -> None:
    await _create(client)
    await client.put(
        DRAWINGS, json={"drawings": [_drawing(price=1.0)]}, headers={"If-Match": '"1"'}
    )
    stale = await client.put(DRAWINGS, json={"drawings": []}, headers={"If-Match": '"1"'})
    assert stale.status_code == 412
    assert stale.headers["content-type"] == "application/problem+json"
    assert stale.headers["etag"] == '"2"'
    body = stale.json()
    assert body["type"] == "urn:momentum25:error:revision_mismatch"
    assert body["current"]["revision"] == 2
    assert body["current"]["body"]["drawings"][0]["points"][0]["price"] == 1.0


@pytest.mark.parametrize("if_match", ['"x"', "garbage", '"0"'])
async def test_malformed_or_impossible_if_match_never_matches(
    client: httpx.AsyncClient, if_match: str
) -> None:
    await _create(client)
    assert (
        await client.put(DRAWINGS, json={"drawings": []}, headers={"If-Match": if_match})
    ).status_code == 412


async def test_if_match_on_a_missing_document_is_412_with_no_current(
    client: httpx.AsyncClient,
) -> None:
    response = await client.put(DRAWINGS, json={"drawings": []}, headers={"If-Match": '"1"'})
    assert response.status_code == 412
    assert response.json()["current"] is None


async def test_save_without_any_precondition_is_428(client: httpx.AsyncClient) -> None:
    assert (await client.put(DRAWINGS, json={"drawings": []})).status_code == 428
    await _create(client)
    assert (await client.put(DRAWINGS, json={"drawings": []})).status_code == 428


async def test_workspace_round_trip(client: httpx.AsyncClient) -> None:
    created = await client.put(WORKSPACE, json=_workspace(), headers={"If-None-Match": "*"})
    assert created.status_code == 201
    read = (await client.get(WORKSPACE)).json()
    assert read["body"]["charts"]["main"]["range"] == "1Y"
    assert read["body"]["charts"]["main"]["show_signals"] is True
    saved = await client.put(WORKSPACE, json=_workspace("MAX"), headers={"If-Match": '"1"'})
    assert saved.json()["body"]["charts"]["main"]["range"] == "MAX"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (DRAWINGS, {"drawings": [], "extra": 1}),
        (DRAWINGS, {"drawings": [{**_drawing(), "kind": "Bad Kind"}]}),
        (DRAWINGS, {"drawings": [{**_drawing(), "color": "red"}]}),
        (DRAWINGS, {"drawings": [{**_drawing(), "points": []}]}),
        (DRAWINGS, {"drawings": [_drawing(str(i)) for i in range(1001)]}),
        (
            WORKSPACE,
            {**_workspace(), "charts": {"main": {**_workspace()["charts"]["main"], "range": "5Y"}}},
        ),
        (WORKSPACE, {**_workspace(), "charts": {"bad id!": _workspace()["charts"]["main"]}}),
    ],
)
async def test_invalid_bodies_are_rejected_not_trimmed(
    client: httpx.AsyncClient, path: str, body: dict[str, Any]
) -> None:
    assert (await client.put(path, json=body, headers={"If-None-Match": "*"})).status_code == 422


@pytest.mark.parametrize(
    "path", ["/api/v1/drawings/reliance", "/api/v1/drawings/A%20B", "/api/v1/workspaces/a.b"]
)
async def test_invalid_keys_are_rejected(client: httpx.AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 422


async def test_two_writers_on_one_revision_exactly_one_wins(client: httpx.AsyncClient) -> None:
    await client.put(DRAWINGS, json={"drawings": []}, headers={"If-None-Match": "*"})
    writes = [
        client.put(DRAWINGS, json={"drawings": [_drawing(str(i))]}, headers={"If-Match": '"1"'})
        for i in range(5)
    ]
    statuses = sorted(r.status_code for r in await asyncio.gather(*writes))
    final = (await client.get(DRAWINGS)).json()
    assert statuses == [200, 412, 412, 412, 412]
    assert final["revision"] == 2


async def test_drawings_record_their_price_basis(client: httpx.AsyncClient) -> None:
    """Saved drawing prices are traded prices; the document says so (ADR-013 §5)."""
    created = await client.put(
        DRAWINGS, json={"drawings": [_drawing()]}, headers={"If-None-Match": "*"}
    )
    assert created.status_code == 201
    assert created.json()["body"]["price_basis"] == "traded"
    read = await client.get(DRAWINGS)
    assert read.json()["body"]["price_basis"] == "traded"
    assert read.json()["body"]["drawings"][0]["points"][0]["price"] == 101.5  # stored as sent


async def test_drawings_in_any_other_price_basis_are_rejected(client: httpx.AsyncClient) -> None:
    res = await client.put(
        DRAWINGS,
        json={"price_basis": "adjusted", "drawings": [_drawing()]},
        headers={"If-None-Match": "*"},
    )
    assert res.status_code == 422


async def test_workspace_side_panel_defaults_and_rejects_unknown_tabs(
    client: httpx.AsyncClient,
) -> None:
    created = await client.put(WORKSPACE, json={"charts": {}}, headers={"If-None-Match": "*"})
    assert created.json()["body"]["right_panel"] == "watchlist"
    bad = await client.put(
        WORKSPACE, json={"charts": {}, "right_panel": "orders"}, headers={"If-Match": '"1"'}
    )
    assert bad.status_code == 422


@pytest.mark.parametrize(
    "extra", [{"width": 0}, {"width": 5}, {"text": "x" * 201}, {"kind": "Not-A-Kind"}]
)
async def test_drawing_style_out_of_bounds_is_rejected(
    client: httpx.AsyncClient, extra: dict[str, Any]
) -> None:
    res = await client.put(
        DRAWINGS, json={"drawings": [{**_drawing(), **extra}]}, headers={"If-None-Match": "*"}
    )
    assert res.status_code == 422


async def test_a_text_note_keeps_its_text_and_width(client: httpx.AsyncClient) -> None:
    note = {
        **_drawing(),
        "kind": "text",
        "points": [_drawing()["points"][0]],
        "width": 3,
        "text": "Base",
    }
    await client.put(DRAWINGS, json={"drawings": [note]}, headers={"If-None-Match": "*"})
    saved = (await client.get(DRAWINGS)).json()["body"]["drawings"][0]
    assert (saved["kind"], saved["width"], saved["text"]) == ("text", 3, "Base")


async def test_drawing_and_study_presentation_survives_document_round_trip(
    client: httpx.AsyncClient,
) -> None:
    drawing = {**_drawing(), "locked": True, "hidden": True, "dash": "dotted"}
    created = await client.put(
        DRAWINGS, json={"drawings": [drawing]}, headers={"If-None-Match": "*"}
    )
    assert created.status_code == 201
    assert created.json()["body"]["drawings"] == [_stored(drawing)]
    workspace = _workspace()
    workspace["charts"]["main"]["indicators"][0].update(color="#123456", hidden=True)
    saved = await client.put(WORKSPACE, json=workspace, headers={"If-None-Match": "*"})
    assert saved.status_code == 201
    indicators = saved.json()["body"]["charts"]["main"]["indicators"]
    assert (indicators[0]["color"], indicators[0]["hidden"]) == ("#123456", True)
    assert (indicators[1]["color"], indicators[1]["hidden"]) == (None, False)
    bad_dash = await client.put(
        DRAWINGS, json={"drawings": [{**drawing, "dash": "wavy"}]}, headers={"If-Match": '"1"'}
    )
    assert bad_dash.status_code == 422


async def test_a_chart_keeps_its_compare_symbols_within_bounds(client: httpx.AsyncClient) -> None:
    created = await client.put(WORKSPACE, json=_workspace(), headers={"If-None-Match": "*"})
    assert created.json()["body"]["charts"]["main"]["compare"] == []
    chart = {**_workspace()["charts"]["main"], "compare": ["TCS", "INFY"]}
    saved = await client.put(
        WORKSPACE, json={"charts": {"main": chart}}, headers={"If-Match": '"1"'}
    )
    assert saved.json()["body"]["charts"]["main"]["compare"] == ["TCS", "INFY"]
    for bad in (["A", "B", "C", "D", "E"], ["tcs"]):
        res = await client.put(
            WORKSPACE,
            json={"charts": {"main": {**chart, "compare": bad}}},
            headers={"If-Match": '"2"'},
        )
        assert res.status_code == 422


async def test_the_layout_and_its_sync_flags_default_and_validate(
    client: httpx.AsyncClient,
) -> None:
    created = await client.put(WORKSPACE, json={"charts": {}}, headers={"If-None-Match": "*"})
    body = created.json()["body"]
    assert (body["layout"], body["sync"]) == (
        "1x1",
        {"symbol": False, "interval": False, "crosshair": True},
    )
    grid = {"charts": {}, "layout": "4x4", "sync": {"symbol": True}}
    saved = await client.put(WORKSPACE, json=grid, headers={"If-Match": '"1"'})
    assert saved.json()["body"]["sync"] == {"symbol": True, "interval": False, "crosshair": True}
    for bad in ({"layout": "5x5"}, {"sync": {"drawings": True}}):
        res = await client.put(WORKSPACE, json={"charts": {}, **bad}, headers={"If-Match": '"2"'})
        assert res.status_code == 422
