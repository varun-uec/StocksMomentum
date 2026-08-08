"""Overlap-window backfill staging + validation-gap logs (RP-012 Phase 2).

Adds the legacy-sourced staging table (kept separate from the live
``ohlcv_daily`` so both sources coexist for Gate 4a reconciliation) and the two
insert-only validation-gap logs (C1 PREVCLOSE-inferred corporate-action factors,
C2 survivorship/gap events).

Revision ID: 0005_overlap_backfill
Revises: 0004_historical_data_foundation
Create Date: 2026-07-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_overlap_backfill"
down_revision: str | None = "0004_historical_data_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the legacy staging table and the two validation-gap logs."""
    op.create_table(
        "legacy_ohlcv_daily",
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("prev_close", sa.Numeric(18, 4), nullable=True),
        sa.Column("turnover_value", sa.Numeric(20, 4), nullable=True),
    )

    op.create_table(
        "corporate_action_inference_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("prev_close_reported", sa.Numeric(18, 4), nullable=False),
        sa.Column("prior_session_close", sa.Numeric(18, 4), nullable=False),
        sa.Column("inferred_factor", sa.Numeric(18, 8), nullable=False),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("security_id", "session_date"),
    )

    op.create_table(
        "survivorship_gap_event",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), nullable=False),
        sa.Column("last_seen_date", sa.Date(), nullable=False),
        sa.Column("detected_on_date", sa.Date(), nullable=False),
        sa.Column("gap_sessions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("security_id", "last_seen_date", "detected_on_date"),
    )


def downgrade() -> None:
    """Drop the Phase 2 staging table and validation-gap logs."""
    op.drop_table("survivorship_gap_event")
    op.drop_table("corporate_action_inference_log")
    op.drop_table("legacy_ohlcv_daily")
