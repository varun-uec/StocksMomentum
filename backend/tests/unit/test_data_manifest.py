"""The data-version manifest (ADR-014 §7, M14): one hash for inputs and code."""

from __future__ import annotations

from dataclasses import replace

from momentum25.domain.strategy.rule_schemas import registry_version
from momentum25.domain.value_objects.manifest import DataManifest

MANIFEST = DataManifest(
    revision=42,
    indicator_version=2,
    rule_registry_version=registry_version(),
    git_commit="abc1234",
    calendar_version="exchange_calendars 4.13.2 XBOM",
)


def test_the_data_version_is_deterministic_and_round_trips() -> None:
    assert len(MANIFEST.data_version) == 12
    assert DataManifest.from_body(MANIFEST.body()).data_version == MANIFEST.data_version


def test_every_part_of_the_manifest_changes_the_data_version() -> None:
    changed = [
        replace(MANIFEST, revision=43),
        replace(MANIFEST, indicator_version=3),
        replace(MANIFEST, rule_registry_version="0" * 12),
        replace(MANIFEST, git_commit="def5678"),
        replace(MANIFEST, calendar_version="exchange_calendars 4.14.0 XBOM"),
    ]
    versions = {m.data_version for m in changed} | {MANIFEST.data_version}
    assert len(versions) == len(changed) + 1


def test_the_rule_registry_fingerprint_is_stable() -> None:
    assert registry_version() == registry_version()
