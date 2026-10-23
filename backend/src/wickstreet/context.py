"""The typed application context every MF read, write, job and agent turn carries.

The HTTP boundary derives it from the verified principal (A3 §9). It is the same
type in personal and SaaS mode (ADR-023 §2.2). A client-supplied tenant id is never
authorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Who is acting: a tenant and one of its users (UUIDs, ADR-023 U6)."""

    tenant_id: UUID
    user_id: UUID
