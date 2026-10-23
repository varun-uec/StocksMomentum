"""W1: research records persist, refuse unseen overwrites and stay with their owner."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings


@pytest.fixture
def client(mf_settings: WickstreetSettings) -> Iterator[TestClient]:
    """The MF app in personal mode; its lifespan registers the personal principal."""
    with TestClient(create_app(mf_settings), base_url="http://localhost") as test_client:
        yield test_client


def _create(client: TestClient, **body: object) -> dict[str, object]:
    response = client.post("/workspace/records", json={"kind": "watchlist", "name": "Core", **body})
    assert response.status_code == 201, response.text
    assert response.headers["ETag"] == '"1"'
    return dict(response.json())


def test_a_record_round_trips_and_lists_by_kind(client: TestClient) -> None:
    saved = _create(client, body={"codes": ["122639"]})
    _create(client, kind="note", name="  Why PPFAS  ", body={"text": "Low churn."})

    assert client.get(f"/workspace/records/{saved['id']}").json() == saved
    watchlists = client.get("/workspace/records", params={"kind": "watchlist"}).json()
    assert [r["name"] for r in watchlists] == ["Core"]
    notes = client.get("/workspace/records", params={"kind": "note"}).json()
    assert notes[0]["name"] == "Why PPFAS"


def test_a_change_needs_the_version_it_read(client: TestClient) -> None:
    saved = _create(client)
    url = f"/workspace/records/{saved['id']}"
    edit = {"name": "Core", "body": {"codes": ["122639", "120503"]}}

    assert client.put(url, json=edit).status_code == 428
    first = client.put(url, json=edit, headers={"If-Match": '"1"'})
    assert first.status_code == 200
    assert (first.json()["version"], first.headers["ETag"]) == (2, '"2"')

    # A second window still holds version 1: its save must not overwrite version 2.
    stale = client.put(url, json={"name": "Other", "body": {}}, headers={"If-Match": '"1"'})
    assert stale.status_code == 412
    assert "version 2" in stale.json()["detail"]
    assert client.get(url).json()["body"] == {"codes": ["122639", "120503"]}


def test_archive_hides_a_record_until_it_is_restored(client: TestClient) -> None:
    saved = _create(client)
    url = f"/workspace/records/{saved['id']}"
    client.put(url, json={"name": "Core", "archived": True}, headers={"If-Match": '"1"'})

    assert client.get("/workspace/records").json() == []
    assert [r["id"] for r in client.get("/workspace/records?archived=true").json()] == [saved["id"]]
    client.put(url, json={"name": "Core", "archived": False}, headers={"If-Match": '"2"'})
    assert len(client.get("/workspace/records").json()) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "portfolio", "name": "x"},
        {"kind": "note", "name": "   "},
        {"kind": "note", "name": "x" * 121},
        {"kind": "note", "name": "x", "body": {"text": "x" * 300_000}},
        {"kind": "note", "name": "x", "schema_version": 0},
    ],
)
def test_an_invalid_record_is_refused(client: TestClient, body: dict[str, object]) -> None:
    response = client.post("/workspace/records", json=body)
    assert response.status_code == 422
    assert client.get("/workspace/records").json() == []


def test_an_unknown_record_is_not_found(client: TestClient) -> None:
    missing = "/workspace/records/00000000-0000-0000-0000-000000000000"
    assert client.get(missing).status_code == 404
    assert client.put(missing, json={"name": "x"}, headers={"If-Match": '"1"'}).status_code == 404
