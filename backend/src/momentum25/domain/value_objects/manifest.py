"""The data-version manifest (ADR-014 §7): everything an evaluation's result depends on.

Two evaluations with the same manifest give identical results (ADR-009). The
short ``data_version`` shown in the UI is the hash of its canonical body.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DataManifest:
    """The state of the inputs and the code that read them.

    ``revision`` is the high-water revision of every versioned input table.
    One global sequence numbers them all, so one value rebuilds each table.
    """

    revision: int
    indicator_version: int
    rule_registry_version: str
    git_commit: str | None
    calendar_version: str

    def body(self) -> dict[str, Any]:
        """The canonical body that is stored and hashed."""
        return asdict(self)

    @property
    def data_version(self) -> str:
        """The first 12 hex characters of the body's SHA-256."""
        canonical = json.dumps(self.body(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> DataManifest:
        """Rebuild a stored manifest."""
        return cls(**body)
