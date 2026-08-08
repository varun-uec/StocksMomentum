"""Extend forward_returns with MFE/MAE and benchmark-relative return (Alpha Discovery Program).

Revision ID: 0003_forward_returns_extended
Revises: 0002_forward_returns
Create Date: 2026-07-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_forward_returns_extended"
down_revision: str | None = "0002_forward_returns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add MFE/MAE and benchmark-relative return columns to forward_returns."""
    op.add_column(
        "forward_returns",
        sa.Column("forward_mfe", sa.Numeric(10, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "forward_returns",
        sa.Column("forward_mae", sa.Numeric(10, 4), nullable=False, server_default="0"),
    )
    op.add_column("forward_returns", sa.Column("benchmark_return", sa.Numeric(10, 4)))
    op.add_column("forward_returns", sa.Column("excess_return", sa.Numeric(10, 4)))


def downgrade() -> None:
    """Drop the added columns."""
    op.drop_column("forward_returns", "excess_return")
    op.drop_column("forward_returns", "benchmark_return")
    op.drop_column("forward_returns", "forward_mae")
    op.drop_column("forward_returns", "forward_mfe")
