"""OM-2 and U8: personal mode is reachable from the owner's machine only.

Three rules: outside a container the bind address is loopback; under Compose the
published address is loopback; the Host/Origin guard stays on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings, get_settings

_COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "[::1]", "localhost"])
def test_personal_mode_accepts_a_loopback_bind(host: str) -> None:
    assert WickstreetSettings(bind_host=host).bind_host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "wickstreet.example"])
def test_personal_mode_refuses_any_other_bind(host: str) -> None:
    with pytest.raises(ValidationError, match="loopback only"):
        WickstreetSettings(bind_host=host)


def test_in_a_container_the_published_address_must_be_loopback() -> None:
    settings = WickstreetSettings(
        bind_host="0.0.0.0", in_container=True, published_bind="127.0.0.1"
    )
    assert settings.bind_host == "0.0.0.0"
    for published in ("0.0.0.0", "192.168.1.5", None):
        with pytest.raises(ValidationError, match="loopback only"):
            WickstreetSettings(bind_host="0.0.0.0", in_container=True, published_bind=published)


def test_saas_mode_has_no_loopback_rule() -> None:
    assert WickstreetSettings(mode="saas", bind_host="0.0.0.0").bind_host == "0.0.0.0"


def test_launcher_refuses_before_opening_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    import apphost.__main__ as launcher

    started: list[str] = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *a, **k: started.append("run"))
    monkeypatch.setenv("WICKSTREET_BIND_HOST", "0.0.0.0")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError, match="loopback only"):
            launcher.main()
    finally:
        get_settings.cache_clear()
    assert started == []


def test_compose_publishes_loopback_and_tells_the_app() -> None:
    api = yaml.safe_load(_COMPOSE.read_text())["services"]["api"]
    assert api["ports"] == ["${APP_BIND:-127.0.0.1}:${API_PORT:-8000}:8000"]
    environment = api["environment"]
    assert environment["WICKSTREET_IN_CONTAINER"] == "true"
    # The app validates the same value Docker publishes on.
    assert environment["WICKSTREET_PUBLISHED_BIND"] == "${APP_BIND:-127.0.0.1}"


def test_host_guard_rejects_a_foreign_host_name() -> None:
    client = TestClient(create_app(WickstreetSettings()), base_url="http://localhost")
    response = client.get("/me", headers={"Host": "192.168.1.5:8000"})
    assert response.status_code == 421
    assert response.json()["type"] == "urn:wickstreet:error:host_not_allowed"
    assert "WICKSTREET_ALLOWED_HOSTS" in response.json()["detail"]
