"""Watchlist: a single global list of tracked securities (Phase 6.9).

No ``user_id`` column: this codebase has no user/session concept, so inventing
a tenancy key here would be speculative. ``security_id`` is unique because the
list is a set — starring an already-starred symbol is idempotent, not a second
row.

Revision ID: 0007_watchlist
Revises: 0006_exchange_dimension
Create Date: 2026-08-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_watchlist"
down_revision: str | None = "0006_exchange_dimension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``watchlist_items`` table."""
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "security_id",
            sa.BigInteger(),
            sa.ForeignKey("securities.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop the ``watchlist_items`` table."""
    op.drop_table("watchlist_items")
