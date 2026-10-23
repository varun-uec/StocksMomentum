"""U1: one host serves both apps and runs both lifespans; MF routes stay under /api/v1/mf."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from apphost.main import MF_PREFIX, create_host
from momentum25.main import create_app as create_momentum25_app
from wickstreet.app import UnsupportedModeError
from wickstreet.app import create_app as create_wickstreet_app
from wickstreet.config import WickstreetSettings
from wickstreet.identity.infrastructure.local import PERSONAL_CONTEXT
from wickstreet.persistence.database import UnsafeDatabaseRoleError


async def test_the_host_serves_both_apps_after_both_startups(
    db_session: AsyncSession, mf_settings: WickstreetSettings
) -> None:
    momentum25 = create_momentum25_app()
    host = create_host(momentum25, create_wickstreet_app(mf_settings))
    with TestClient(host, base_url="http://localhost") as client:
        # Momentum25's lifespan ran: without the host it would not (mounted apps get none).
        assert momentum25.state.engines_registered > 0
        assert momentum25.state.scheduler is not None
        assert client.get("/api/v1/health/live").status_code == 200

        # The MF lifespan ran: it registered the personal principal that /me verifies.
        me = client.get(f"{MF_PREFIX}/me")
        assert me.status_code == 200
        assert me.json() == {
            "tenant_id": str(PERSONAL_CONTEXT.tenant_id),
            "user_id": str(PERSONAL_CONTEXT.user_id),
        }

        mf_paths = client.get(f"{MF_PREFIX}/openapi.json").json()["paths"]
        momentum25_paths = client.get("/openapi.json").json()["paths"]
    assert "/me" in mf_paths
    assert not [path for path in momentum25_paths if path.startswith(MF_PREFIX)]


async def test_the_host_does_not_start_when_the_mf_app_cannot(
    db_session: AsyncSession, mf_settings: WickstreetSettings
) -> None:
    unsafe = mf_settings.model_copy(update={"database_url": mf_settings.migration_database_url})
    host = create_host(create_momentum25_app(), create_wickstreet_app(unsafe))
    with pytest.raises(UnsafeDatabaseRoleError), TestClient(host, base_url="http://localhost"):
        pass


def test_saas_mode_refuses_to_start_without_its_identity_adapter() -> None:
    with pytest.raises(UnsupportedModeError, match="OIDC"):
        create_wickstreet_app(WickstreetSettings(mode="saas"))
