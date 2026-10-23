"""Identity tables. Both are tenant-scoped under row-level security (migration 0001)."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Table, Uuid, func

from wickstreet.persistence.database import metadata

tenant = Table(
    "tenant",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

app_user = Table(
    "app_user",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("tenant_id", Uuid, ForeignKey(tenant.c.id), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
