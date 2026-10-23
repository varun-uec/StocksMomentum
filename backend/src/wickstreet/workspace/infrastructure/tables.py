"""The research record table, user-owned under row-level security (migration 0005)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from wickstreet.identity.infrastructure.tables import app_user, tenant
from wickstreet.persistence.database import metadata

research_record = Table(
    "research_record",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("tenant_id", Uuid, ForeignKey(tenant.c.id), nullable=False),
    Column("owner_id", Uuid, ForeignKey(app_user.c.id), nullable=False),
    Column("kind", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("body", JSONB, nullable=False),
    Column("schema_version", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("archived", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("kind IN ('watchlist', 'screen', 'note', 'brief', 'scenario')", name="kind"),
    Index("ix_research_record_owner_kind", "tenant_id", "owner_id", "kind"),
)
