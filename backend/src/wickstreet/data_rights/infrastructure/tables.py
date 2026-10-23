"""The rights register table: shared reference data, not tenant-owned (ADR-023 §2.6)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Identity, Index, Table, Text, func, text

from wickstreet.persistence.database import metadata

rights_grant = Table(
    "rights_grant",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("source", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("use", Text, nullable=False),
    # Why the use is allowed, in words; copied into every run's provenance.
    Column("basis", Text, nullable=False),
    Column("granted_by", Text, nullable=False),
    Column("granted_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("revoked_at", DateTime(timezone=True)),
    Index(
        "uq_rights_grant_active",
        "source",
        "mode",
        "use",
        unique=True,
        postgresql_where=text("revoked_at IS NULL"),
    ),
)
