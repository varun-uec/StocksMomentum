"""Forward-return feature store (Objective 4, Research Feature Store).

Revision ID: 0002_forward_returns
Revises: 0001_initial
Create Date: 2026-07-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_forward_returns"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the forward_returns table."""
    op.create_table(
        "forward_returns",
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("screening_runs.id"), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("horizon_days", sa.Integer(), primary_key=True),
        sa.Column("forward_return", sa.Numeric(10, 4), nullable=False),
        sa.Column("forward_max_drawdown", sa.Numeric(10, 4), nullable=False),
        sa.Column("forward_volatility", sa.Numeric(10, 4), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop the forward_returns table."""
    op.drop_table("forward_returns")
