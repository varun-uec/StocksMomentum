"""Data-version manifests (ADR-014 §7, M14): the inputs and code behind an evaluation.

Each row is one manifest. Its primary key is the 12-hex hash of its body, so
storing the same manifest twice keeps one row.

Revision ID: 0017_data_manifests
Revises: 0016_history_tables
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0017_data_manifests"
down_revision: str | None = "0016_history_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``data_manifests`` table."""
    op.create_table(
        "data_manifests",
        sa.Column("data_version", sa.String(12), primary_key=True),
        sa.Column("body", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop the ``data_manifests`` table."""
    op.drop_table("data_manifests")
