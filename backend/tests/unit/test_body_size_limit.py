"""R3-B-23: a request body above the cap is refused before the handler runs."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from momentum25.interface.api.middleware import MAX_BODY_BYTES, BodySizeLimitMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware)

    @app.put("/thing")
    async def write() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_body_at_the_cap_passes() -> None:
    assert _client().put("/thing", content=b"x" * MAX_BODY_BYTES).status_code == 200


def test_body_over_the_cap_is_413() -> None:
    response = _client().put("/thing", content=b"x" * (MAX_BODY_BYTES + 1))
    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"


def test_write_with_no_declared_length_is_411() -> None:
    def chunks() -> Iterator[bytes]:
        yield b"{}"

    assert _client().put("/thing", content=chunks()).status_code == 411
