"""Stored manifests: schema-2 capture ignores the build; legacy rows still load."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import DataManifestModel
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)


async def test_capture_under_two_builds_gives_one_data_version(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = SqlDataManifestRepository(db_session)
    monkeypatch.setattr(
        "momentum25.infrastructure.persistence.repositories.data_manifests.build_identity",
        lambda: "commit-a",
    )
    first = await repo.capture()
    monkeypatch.setattr(
        "momentum25.infrastructure.persistence.repositories.data_manifests.build_identity",
        lambda: None,  # a container without git
    )
    second = await repo.capture()
    await db_session.commit()

    assert first.data_version == second.data_version
    stored = await repo.get(first.data_version)
    assert stored is not None and stored.identity_schema == 3
    assert stored.engine_version is not None and stored.market_data_version is not None
    assert stored.build_id == "commit-a"  # the first build to record it


async def test_a_legacy_row_still_loads_under_its_stored_key(db_session: AsyncSession) -> None:
    body = {
        "revision": 133621,
        "git_commit": "5961b9c2f74bc41bf3ba5c33101fefc1eda3a6a3",
        "calendar_version": "exchange_calendars 4.13.2 XBOM",
        "indicator_version": 2,
        "rule_registry_version": "41cc5e4529c8",
    }
    db_session.add(DataManifestModel(data_version="8790a000bd4f", body=body))
    await db_session.commit()

    manifest = await SqlDataManifestRepository(db_session).get("8790a000bd4f")

    assert manifest is not None
    assert manifest.data_version == "8790a000bd4f"
    assert manifest.revision == 133621
    assert manifest.body() == body

