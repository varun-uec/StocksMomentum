"""Adjustment columns on both legacy staging tables (RP-014 follow-up).

The legacy tables held raw prints only. A split or bonus therefore showed as a
fake single-day gap: RELIANCE's 1:1 bonus (ex-date 2017-09-07) read as a
-50.3% move. Add the same two adjustment columns the live ``ohlcv_daily``
carries, so legacy and live share identical adjustment semantics
(``adj_close == close * adj_factor``).

``adj_factor`` takes a server default of 1 so the existing 12.1M legacy rows
become "unadjusted" rather than null. ``adj_close`` stays nullable and is
filled by the adjustment pass; readers fall back to raw ``close`` while it is
null, matching the live table.

Revision ID: 0011_legacy_adjustment_columns
Revises: 0010_bse_legacy_foundation
Create Date: 2026-08-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_legacy_adjustment_columns"
down_revision: str | None = "0010_bse_legacy_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("legacy_ohlcv_daily", "bse_legacy_ohlcv_daily")


def upgrade() -> None:
    """Add ``adj_factor`` and ``adj_close`` to both legacy staging tables."""
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "adj_factor",
                sa.Numeric(18, 8),
                nullable=False,
                server_default="1",
            ),
        )
        op.add_column(table, sa.Column("adj_close", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    """Drop the adjustment columns from both legacy staging tables."""
    for table in _TABLES:
        op.drop_column(table, "adj_close")
        op.drop_column(table, "adj_factor")
