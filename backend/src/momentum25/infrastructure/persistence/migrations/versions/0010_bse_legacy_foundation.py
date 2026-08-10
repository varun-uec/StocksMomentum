"""BSE legacy staging tables (RP-014): pre-UDiFF bars + SC_CODE identity junction.

Adds the BSE-sourced staging table (kept separate from the NSE-anchored
``legacy_ohlcv_daily`` so the historical screening surface never mixes venue
sources) and the insert-only ``SC_CODE`` → ISIN identity junction the pre-UDiFF
bars (which carry no ISIN) resolve through.

Revision ID: 0010_bse_legacy_foundation
Revises: 0009_strategy_kind
Create Date: 2026-08-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_bse_legacy_foundation"
down_revision: str | None = "0009_strategy_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the BSE legacy staging table and the SC_CODE identity junction."""
    op.create_table(
        "bse_legacy_ohlcv_daily",
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
        "bse_scrip_junction",
        sa.Column("sc_code", sa.String(), primary_key=True),
        sa.Column("isin", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
    )


def downgrade() -> None:
    """Drop the RP-014 staging table and identity junction."""
    op.drop_table("bse_scrip_junction")
    op.drop_table("bse_legacy_ohlcv_daily")