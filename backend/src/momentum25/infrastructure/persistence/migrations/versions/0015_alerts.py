"""Daily alerts (FR-22, M15): a condition on one value of a symbol's chart series.

An alert fires once, on the first complete bar after ``armed_after`` that meets
its condition. The firing bar, its value and the data version are kept on the
row. ``tenant_id`` stays NULL on a single-owner instance (ADR-010).

Revision ID: 0015_alerts
Revises: 0014_user_documents
Create Date: 2026-10-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_alerts"
down_revision: str | None = "0014_user_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``alerts`` table."""
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("interval", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("armed_after", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("triggered_on", sa.Date(), nullable=True),
        sa.Column("trigger_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("data_version", sa.String(), nullable=True),
        sa.Column("seen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'triggered')", name="ck_alerts_status"),
        sa.CheckConstraint(
            "(status = 'active') = (triggered_on IS NULL)", name="ck_alerts_triggered_on"
        ),
    )
    op.create_index("ix_alerts_status", "alerts", ["status"])


def downgrade() -> None:
    """Drop the ``alerts`` table."""
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_table("alerts")
