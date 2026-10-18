"""User documents: the saved workspace and per-symbol drawings (ADR-013 §5).

One table for every kind of user document. Each row carries a ``revision`` that a
save must name, so concurrent windows cannot overwrite each other silently.
``tenant_id`` stays NULL on a single-owner instance; it is the SaaS seam (ADR-010).

Revision ID: 0014_user_documents
Revises: 0013_filter_column_indexes
Create Date: 2026-10-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014_user_documents"
down_revision: str | None = "0013_filter_column_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``user_documents`` table."""
    op.create_table(
        "user_documents",
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("body", JSONB(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("revision >= 1", name="ck_user_documents_revision"),
    )


def downgrade() -> None:
    """Drop the ``user_documents`` table."""
    op.drop_table("user_documents")
