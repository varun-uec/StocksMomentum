"""Cross-listing support: index the ISIN reconciliation key (Phase 5.1).

``securities.exchange`` already exists (0001, ``server_default='NSE'``); this
revision does not recreate it. What was missing is an index on ``isin``, which
is now the reconciliation key between the NSE and BSE instrument masters and is
already scanned per-run by the rename-chain query in ``SqlSecurityRepository``.

The index is deliberately **not** unique: securities sharing one ISIN is a valid
and load-bearing state in this schema (RP-012 rename chains keep one row per
historical ticker), so a unique constraint would break historical resolution.

Revision ID: 0006_exchange_dimension
Revises: 0005_overlap_backfill
Create Date: 2026-08-08
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_exchange_dimension"
down_revision: str | None = "0005_overlap_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the (non-unique) ISIN index used for cross-listing reconciliation."""
    op.create_index("ix_securities_isin", "securities", ["isin"])


def downgrade() -> None:
    """Drop the ISIN index."""
    op.drop_index("ix_securities_isin", table_name="securities")
