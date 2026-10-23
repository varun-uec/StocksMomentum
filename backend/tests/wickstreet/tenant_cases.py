"""One cross-tenant case per tenant-scoped MF table (OM-8).

``test_schema_rules`` fails while a tenant-scoped table has no case here, so every
new user-owned table arrives with its own denial tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from wickstreet.context import TenantContext


@dataclass(frozen=True)
class TenantCase:
    """How the generic tests find and forge rows of one table."""

    tenant_column: str
    # The key of the row this tenant owns.
    key: Callable[[TenantContext], dict[str, UUID]]
    # A new row that claims to belong to ``victim``.
    forged_row: Callable[[TenantContext], dict[str, UUID]]


CASES: dict[str, TenantCase] = {
    "tenant": TenantCase(
        tenant_column="id",
        key=lambda c: {"id": c.tenant_id},
        forged_row=lambda victim: {"id": uuid4()},
    ),
    "app_user": TenantCase(
        tenant_column="tenant_id",
        key=lambda c: {"id": c.user_id},
        forged_row=lambda victim: {"id": uuid4(), "tenant_id": victim.tenant_id},
    ),
}
