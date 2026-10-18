"""Tests for :class:`HostOriginGuardMiddleware` — one test per row of the ADR-012 table."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from momentum25.interface.api.middleware import HostOriginGuardMiddleware, host_name


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(HostOriginGuardMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.get("/thing")
    async def read() -> dict[str, bool]:
        return {"ok": True}

    @app.put("/thing")
    async def write() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app, base_url="http://localhost:8000")


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_unlisted_host_is_misdirected(method: str) -> None:
    response = _client().request(method, "/thing", headers={"Host": "evil.example:8000"})
    assert response.status_code == 421
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize(
    "host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000", "LOCALHOST:9000"]
)
def test_listed_hosts_pass_on_any_port(host: str) -> None:
    assert _client().get("/thing", headers={"Host": host}).status_code == 200


def test_same_origin_write_passes() -> None:
    response = _client().put("/thing", headers={"Origin": "http://localhost:8000"})
    assert response.status_code == 200


def test_write_from_the_same_host_on_another_port_is_cross_origin() -> None:
    response = _client().put("/thing", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "file://", "localhost:8000"])
def test_foreign_or_opaque_origin_write_is_forbidden(origin: str) -> None:
    response = _client().put("/thing", headers={"Origin": origin})
    assert response.status_code == 403
    assert response.json()["type"] == "urn:momentum25:error:origin_not_allowed"


def test_write_without_origin_passes_for_non_browser_clients() -> None:
    # curl, scripts and generated API clients send no Origin header.
    assert _client().put("/thing").status_code == 200


def test_reads_ignore_origin() -> None:
    response = _client().get("/thing", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200


def test_host_name_strips_the_port_and_keeps_ipv6_brackets() -> None:
    assert host_name("Localhost:8000") == "localhost"
    assert host_name("[::1]:8000") == "[::1]"
    assert host_name("127.0.0.1") == "127.0.0.1"
    assert host_name("") == ""
