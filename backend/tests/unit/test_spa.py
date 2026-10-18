"""Tests for serving the built web app from the API origin (ADR-013)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from momentum25.interface.api.spa import mount_spa


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "icon.svg").write_text("<svg/>")
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, bool]:
        return {"pong": True}

    mount_spa(app, tmp_path)
    return TestClient(app)


def test_client_routes_fall_back_to_index(client: TestClient) -> None:
    for path in ("/", "/chart/RELIANCE", "/stock/TCS/analysis?strategy=x"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.text == "<div id=root></div>"
        assert response.headers["cache-control"] == "no-cache"


def test_static_files_are_served(client: TestClient) -> None:
    assert client.get("/assets/index-abc.js").text == "console.log(1)"
    assert client.get("/icon.svg").text == "<svg/>"


def test_api_routes_win_and_api_misses_stay_404(client: TestClient) -> None:
    assert client.get("/api/v1/ping").json() == {"pong": True}
    assert client.get("/api/v1/nope").status_code == 404
    assert client.get("/openapi.json").status_code in (200, 404)
    assert client.get("/docs/unknown").status_code == 404


def test_paths_outside_the_build_are_never_served(client: TestClient) -> None:
    response = client.get("/..%2F..%2Fetc%2Fpasswd")
    assert response.text == "<div id=root></div>"


def test_missing_build_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="index.html"):
        mount_spa(FastAPI(), tmp_path)
