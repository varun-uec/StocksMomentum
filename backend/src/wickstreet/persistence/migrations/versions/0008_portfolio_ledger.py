"""Portfolio ledger: CAS imports and their transactions, user-owned under RLS (Slice 6).

Only a statement's hash is kept, never the file or its password.

Revision ID: 0008_portfolio_ledger
Revises: 0007_holdings
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_portfolio_ledger"
down_revision: str | None = "0007_holdings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"
_CURRENT_TENANT = "nullif(current_setting('wickstreet.tenant_id', true), '')::uuid"


def _owned(table: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["tenant_id"], [f"{_S}.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], [f"{_S}.app_user.id"], name=f"fk_{table}_owner_id_app_user"
        ),
    ]


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE {_S}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_S}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {_S}.{table} "
        f"USING (tenant_id = {_CURRENT_TENANT}) WITH CHECK (tenant_id = {_CURRENT_TENANT})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_S}.{table} TO wickstreet_app")


def upgrade() -> None:
    """Create the ledger tables with forced row-level security."""
    op.create_table(
        "portfolio_import",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("file_sha256", sa.Text(), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("cas_type", sa.Text(), nullable=False),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("closings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_owned("portfolio_import"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_import"),
        sa.UniqueConstraint(
            "tenant_id", "owner_id", "file_sha256", name="uq_portfolio_import_file"
        ),
        schema=_S,
    )
    op.create_table(
        "portfolio_txn",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("folio", sa.Text(), nullable=False),
        sa.Column("amc", sa.Text(), nullable=False),
        sa.Column("scheme", sa.Text(), nullable=False),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.Column("amfi_code", sa.Text(), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("units", sa.Numeric(), nullable=True),
        sa.Column("nav", sa.Numeric(), nullable=True),
        sa.Column("balance", sa.Numeric(), nullable=True),
        *_owned("portfolio_txn"),
        sa.ForeignKeyConstraint(
            ["import_id"],
            [f"{_S}.portfolio_import.id"],
            name="fk_portfolio_txn_import_id_portfolio_import",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_txn"),
        sa.UniqueConstraint("tenant_id", "owner_id", "fingerprint", name="uq_portfolio_txn_line"),
        schema=_S,
    )
    op.create_index(
        "ix_portfolio_txn_owner_day", "portfolio_txn", ["tenant_id", "owner_id", "day"], schema=_S
    )
    _protect("portfolio_import")
    _protect("portfolio_txn")


def downgrade() -> None:
    """Drop the tables; their policies and grants go with them."""
    op.drop_table("portfolio_txn", schema=_S)
    op.drop_table("portfolio_import", schema=_S)
