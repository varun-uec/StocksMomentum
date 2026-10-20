"""Query parameters shared by several routers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

# Pins one saved strategy version (ADR-014 §9). Omitted: the strategy-file definition.
ConfigHash = Annotated[
    str | None,
    Query(
        pattern="^[a-f0-9]{64}$",
        description="Exact config version. Omit for the strategy-file definition.",
    ),
]
