"""Drop the superseded ``legacy_ohlcv_daily_bak`` snapshot.

``legacy_ohlcv_daily_bak`` held 1,731,889 rows from the pre-backfill run. That
run mis-attributed bars to the wrong ``security_id``: it put AAVAS at a close
of 145.85 (the real close is 1596.10) and J&K Bank at 453.85 (the real close
is 33.45).

Measured on the overlap with the live ``ohlcv_daily``:

* ``legacy_ohlcv_daily`` agrees on 1,872,379 of 1,872,379 closes (100.000%).
* ``legacy_ohlcv_daily_bak`` agrees on 59 of 801,552 closes (0.007%).

The snapshot is superseded and wrong, and no code reads it. Drop it.

The downgrade recreates the empty table. The rows are not recoverable, and
they should not be: re-run ``scripts/rp012_phase3_backfill.py`` to rebuild the
legacy archive from source.

Revision ID: 0012_drop_legacy_ohlcv_bak
Revises: 0011_legacy_adjustment_columns
Create Date: 2026-08-10
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_drop_legacy_ohlcv_bak"
down_revision: str | None = "0011_legacy_adjustment_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the superseded pre-backfill snapshot table."""
    op.execute("DROP TABLE IF EXISTS legacy_ohlcv_daily_bak")


def downgrade() -> None:
    """Recreate the snapshot table, empty. Its rows are not recoverable."""
    op.create_table(
        "legacy_ohlcv_daily_bak",
        sa.Column("security_id", sa.BigInteger(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("open", sa.Numeric(18, 4), nullable=True),
        sa.Column("high", sa.Numeric(18, 4), nullable=True),
        sa.Column("low", sa.Numeric(18, 4), nullable=True),
        sa.Column("close", sa.Numeric(18, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("prev_close", sa.Numeric(18, 4), nullable=True),
        sa.Column("turnover_value", sa.Numeric(20, 4), nullable=True),
    )
