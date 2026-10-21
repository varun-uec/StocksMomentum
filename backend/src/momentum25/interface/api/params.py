"""Query and path parameters shared by several routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Path, Query

# Pins one saved strategy version (ADR-014 §9). Omitted: the strategy-file definition.
ConfigHash = Annotated[
    str | None,
    Query(
        pattern="^[a-f0-9]{64}$",
        description="Exact config version. Omit for the strategy-file definition.",
    ),
]

# A database id is a signed 64-bit integer. A larger path value would overflow the
# driver and answer 500; it answers 422 instead (R3-B-19).
EntityId = Annotated[int, Path(ge=1, le=2**63 - 1)]
