"""The data-version manifest (ADR-014 §7): everything an evaluation's result depends on.

Two evaluations with the same manifest give identical results (ADR-009). The
short ``data_version`` shown in the UI is the hash of the manifest's identity.

The identity has two parts:

- market data: the data revision and the trading-calendar version;
- engine: the indicator version and the rule-registry version. Results change
  when these change, so they stay in the identity.

The strategy configuration has its own identity, ``config_hash``. The build
(``build_id``: a git commit or an image build id) is stored for tracing but is
not hashed, so a commit that changes no engine version keeps the same
``data_version``.

Identity schema 1 (legacy, before 2026-10-20) hashed the git commit too. Stored
schema-1 bodies keep that rule, so their stored ``data_version`` keys still load.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

LEGACY_IDENTITY_SCHEMA = 1
IDENTITY_SCHEMA = 2


@dataclass(frozen=True, slots=True)
class DataManifest:
    """The state of the inputs and the engine that read them.

    ``revision`` is the high-water revision of every versioned input table.
    One global sequence numbers them all, so one value rebuilds each table.
    """

    revision: int
    indicator_version: int
    rule_registry_version: str
    calendar_version: str
    build_id: str | None = None
    identity_schema: int = IDENTITY_SCHEMA

    def identity(self) -> dict[str, Any]:
        """The fields the ``data_version`` hashes."""
        if self.identity_schema == LEGACY_IDENTITY_SCHEMA:
            return {
                "revision": self.revision,
                "indicator_version": self.indicator_version,
                "rule_registry_version": self.rule_registry_version,
                "git_commit": self.build_id,
                "calendar_version": self.calendar_version,
            }
        return {
            "identity_schema": self.identity_schema,
            "revision": self.revision,
            "indicator_version": self.indicator_version,
            "rule_registry_version": self.rule_registry_version,
            "calendar_version": self.calendar_version,
        }

    def body(self) -> dict[str, Any]:
        """The canonical body that is stored: the identity plus the build id."""
        if self.identity_schema == LEGACY_IDENTITY_SCHEMA:
            return self.identity()
        return {**self.identity(), "build_id": self.build_id}

    @property
    def data_version(self) -> str:
        """The first 12 hex characters of the identity's SHA-256."""
        canonical = json.dumps(self.identity(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> DataManifest:
        """Rebuild a stored manifest of either identity schema."""
        schema = int(body.get("identity_schema", LEGACY_IDENTITY_SCHEMA))
        return cls(
            revision=body["revision"],
            indicator_version=body["indicator_version"],
            rule_registry_version=body["rule_registry_version"],
            calendar_version=body["calendar_version"],
            build_id=body.get("git_commit" if schema == LEGACY_IDENTITY_SCHEMA else "build_id"),
            identity_schema=schema,
        )
