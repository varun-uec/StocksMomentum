"""The portfolio ledger: imports and transactions, user-owned under row-level security."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from wickstreet.identity.infrastructure.tables import app_user, tenant
from wickstreet.persistence.database import metadata

portfolio_import = Table(
    "portfolio_import",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("tenant_id", Uuid, ForeignKey(tenant.c.id), nullable=False),
    Column("owner_id", Uuid, ForeignKey(app_user.c.id), nullable=False),
    # The file's hash only; the file itself is never kept.
    Column("file_sha256", Text, nullable=False),
    Column("period_from", Date),
    Column("period_to", Date),
    Column("cas_type", Text, nullable=False),
    Column("added", Integer, nullable=False),
    Column("duplicates", Integer, nullable=False),
    # Each scheme's closing balance and valuation as the statement filed them.
    Column("closings", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "owner_id", "file_sha256", name="uq_portfolio_import_file"),
)

portfolio_txn = Table(
    "portfolio_txn",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("tenant_id", Uuid, ForeignKey(tenant.c.id), nullable=False),
    Column("owner_id", Uuid, ForeignKey(app_user.c.id), nullable=False),
    Column(
        "import_id", Uuid, ForeignKey(portfolio_import.c.id, ondelete="CASCADE"), nullable=False
    ),
    # A hash of the line, so a statement that overlaps an earlier one adds nothing twice.
    Column("fingerprint", Text, nullable=False),
    Column("folio", Text, nullable=False),
    Column("amc", Text, nullable=False),
    Column("scheme", Text, nullable=False),
    Column("isin", Text),
    Column("amfi_code", Text),
    Column("day", Date, nullable=False),
    Column("kind", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("amount", Numeric),
    Column("units", Numeric),
    Column("nav", Numeric),
    Column("balance", Numeric),
    UniqueConstraint("tenant_id", "owner_id", "fingerprint", name="uq_portfolio_txn_line"),
    Index("ix_portfolio_txn_owner_day", "tenant_id", "owner_id", "day"),
)
