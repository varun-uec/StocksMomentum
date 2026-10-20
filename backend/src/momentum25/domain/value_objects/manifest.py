"""The data-version manifest (ADR-014 §7, §10, §11): everything an evaluation's result depends on.

Two evaluations with the same manifest give identical results (ADR-009). The
short ``data_version`` shown in the UI is the hash of the manifest's identity,
and it is the run key.

Identity schema 3 keeps two blocks apart and hashes both:

- market: the data revision and the trading-calendar version, hashed alone as
  ``market_data_version``;
- engine: ``ENGINE_VERSION``, ``INDICATOR_VERSION``, the rule-registry
  fingerprint and ``REFERENCE_UNIVERSE_VERSION``, hashed alone as
  ``engine_identity``.

The strategy configuration has its own identity, ``config_hash``. The build
(``build_id``: a git commit or an image build id) is stored for tracing but is
never hashed, so a commit that changes no engine version keeps the same keys.

Stored bodies keep the rule they were written under. Schema 1 (before
2026-10-20) hashed the git commit too. Schema 2 hashed the market and engine
fields flat, with no engine version. Both still load under their stored keys;
they have no separate market or engine identity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

LEGACY_IDENTITY_SCHEMA = 1
FLAT_IDENTITY_SCHEMA = 2
IDENTITY_SCHEMA = 3


def _short_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class DataManifest:
    """The state of the inputs and the engine that read them.

    ``revision`` is the high-water revision of every versioned input table.
    One global sequence numbers them all, so one value rebuilds each table.
    ``engine_version`` and ``reference_universe_version`` are ``None`` only for
    bodies stored before schema 3.
    """

    revision: int
    indicator_version: int
    rule_registry_version: str
    calendar_version: str
    build_id: str | None = None
    identity_schema: int = IDENTITY_SCHEMA
    engine_version: int | None = None
    reference_universe_version: int | None = None

    def __post_init__(self) -> None:
        """A schema-3 manifest must name its engine."""
        if self.identity_schema >= IDENTITY_SCHEMA and (
            self.engine_version is None or self.reference_universe_version is None
        ):
            raise ValueError(
                "an identity-schema-3 manifest needs engine_version and reference_universe_version"
            )

    def market(self) -> dict[str, Any]:
        """The market-data block."""
        return {"revision": self.revision, "calendar_version": self.calendar_version}

    def engine(self) -> dict[str, Any]:
        """The engine block (schema 3)."""
        return {
            "engine_version": self.engine_version,
            "indicator_version": self.indicator_version,
            "rule_registry_version": self.rule_registry_version,
            "reference_universe_version": self.reference_universe_version,
        }

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
        if self.identity_schema == FLAT_IDENTITY_SCHEMA:
            return {
                "identity_schema": self.identity_schema,
                "revision": self.revision,
                "indicator_version": self.indicator_version,
                "rule_registry_version": self.rule_registry_version,
                "calendar_version": self.calendar_version,
            }
        return {
            "identity_schema": self.identity_schema,
            "market": self.market(),
            "engine": self.engine(),
        }

    def body(self) -> dict[str, Any]:
        """The canonical body that is stored: the identity plus the build id."""
        if self.identity_schema == LEGACY_IDENTITY_SCHEMA:
            return self.identity()
        return {**self.identity(), "build_id": self.build_id}

    @property
    def data_version(self) -> str:
        """The run key: the first 12 hex characters of the identity's SHA-256."""
        return _short_hash(self.identity())

    @property
    def market_data_version(self) -> str | None:
        """The market-data identity alone; ``None`` before schema 3."""
        return _short_hash(self.market()) if self.identity_schema >= IDENTITY_SCHEMA else None

    @property
    def engine_identity(self) -> str | None:
        """The engine identity alone; ``None`` before schema 3."""
        return _short_hash(self.engine()) if self.identity_schema >= IDENTITY_SCHEMA else None

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> DataManifest:
        """Rebuild a stored manifest of any identity schema."""
        schema = int(body.get("identity_schema", LEGACY_IDENTITY_SCHEMA))
        if schema >= IDENTITY_SCHEMA:
            market, engine = body["market"], body["engine"]
            return cls(
                revision=market["revision"],
                calendar_version=market["calendar_version"],
                indicator_version=engine["indicator_version"],
                rule_registry_version=engine["rule_registry_version"],
                engine_version=engine["engine_version"],
                reference_universe_version=engine["reference_universe_version"],
                build_id=body.get("build_id"),
                identity_schema=schema,
            )
        return cls(
            revision=body["revision"],
            indicator_version=body["indicator_version"],
            rule_registry_version=body["rule_registry_version"],
            calendar_version=body["calendar_version"],
            build_id=body.get("git_commit" if schema == LEGACY_IDENTITY_SCHEMA else "build_id"),
            identity_schema=schema,
        )
