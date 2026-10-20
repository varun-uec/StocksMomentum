"""The data-version manifest (ADR-014 §7): market data + engine identity, build excluded."""

from __future__ import annotations

from dataclasses import replace

import pytest

from momentum25.domain.strategy.rule_schemas import registry_version
from momentum25.domain.value_objects.manifest import DataManifest
from momentum25.infrastructure.observability import research_metadata

MANIFEST = DataManifest(
    revision=42,
    indicator_version=2,
    rule_registry_version=registry_version(),
    calendar_version="exchange_calendars 4.13.2 XBOM",
    build_id="abc1234",
)


def test_the_data_version_is_deterministic_and_round_trips() -> None:
    assert len(MANIFEST.data_version) == 12
    restored = DataManifest.from_body(MANIFEST.body())
    assert restored == MANIFEST
    assert restored.data_version == MANIFEST.data_version


def test_the_build_is_stored_but_does_not_change_the_data_version() -> None:
    # R3-U-09 / R3-B-12: each commit (or a container without git) gave a new
    # data_version, and so a new run, for identical data and engine.
    other_commit = replace(MANIFEST, build_id="def5678")
    no_git = replace(MANIFEST, build_id=None)
    assert other_commit.data_version == no_git.data_version == MANIFEST.data_version
    assert MANIFEST.body()["build_id"] == "abc1234"


def test_data_revision_engine_versions_and_calendar_change_the_data_version() -> None:
    changed = [
        replace(MANIFEST, revision=43),
        replace(MANIFEST, indicator_version=3),
        replace(MANIFEST, rule_registry_version="0" * 12),
        replace(MANIFEST, calendar_version="exchange_calendars 4.14.0 XBOM"),
    ]
    versions = {m.data_version for m in changed} | {MANIFEST.data_version}
    assert len(versions) == len(changed) + 1


def test_a_stored_legacy_body_keeps_its_stored_key() -> None:
    # Run 149's manifest as stored in the development database before schema 2.
    legacy_body = {
        "revision": 133621,
        "git_commit": "5961b9c2f74bc41bf3ba5c33101fefc1eda3a6a3",
        "calendar_version": "exchange_calendars 4.13.2 XBOM",
        "indicator_version": 2,
        "rule_registry_version": "41cc5e4529c8",
    }
    legacy = DataManifest.from_body(legacy_body)
    assert legacy.data_version == "8790a000bd4f"
    assert legacy.body() == legacy_body
    assert legacy.revision == 133621
    # The same inputs under schema 2 hash differently: a new identity, never a rewrite.
    assert replace(legacy, identity_schema=2).data_version != "8790a000bd4f"


def test_the_rule_registry_fingerprint_is_stable() -> None:
    assert registry_version() == registry_version()


def test_build_identity_is_resolved_once_and_prefers_the_image_build_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fake_git() -> str | None:
        calls.append(1)
        return None

    monkeypatch.setattr(research_metadata, "get_git_commit", fake_git)
    monkeypatch.setattr(
        "momentum25.infrastructure.config.settings.get_settings",
        lambda: type("S", (), {"build_id": None})(),
    )
    research_metadata.build_identity.cache_clear()
    try:
        # No git (as in the container): a stable None, and git is asked once.
        assert research_metadata.build_identity() is None
        assert research_metadata.build_identity() is None
        assert calls == [1]

        research_metadata.build_identity.cache_clear()
        monkeypatch.setattr(
            "momentum25.infrastructure.config.settings.get_settings",
            lambda: type("S", (), {"build_id": "img-20261020"})(),
        )
        assert research_metadata.build_identity() == "img-20261020"
        assert calls == [1]
    finally:
        research_metadata.build_identity.cache_clear()
