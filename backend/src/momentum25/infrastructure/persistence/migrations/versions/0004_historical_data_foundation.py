"""Historical Data Foundation (RP-012 D3) — legacy bhavcopy fields, delisting
metadata, and the immutable historical_universe table.

Revision ID: 0004_historical_data_foundation
Revises: 0003_forward_returns_extended
Create Date: 2026-07-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_historical_data_foundation"
down_revision: str | None = "0003_forward_returns_extended"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The immutable historical_universe contract (RP-012 §2): rows are insert-only.
# Enforced at the database layer so no application path can mutate an already
# written point-in-time eligibility record.
_IMMUTABLE_GUARD_FN = """
CREATE OR REPLACE FUNCTION historical_universe_reject_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'historical_universe is immutable: % not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    """Add legacy OHLCV fields, delisting metadata, and historical_universe."""
    # ── ohlcv_daily: legacy bhavcopy columns (RP-012 §1.2 / §2.2) ──────────
    op.add_column("ohlcv_daily", sa.Column("prev_close", sa.Numeric(18, 4), nullable=True))
    op.add_column("ohlcv_daily", sa.Column("turnover_value", sa.Numeric(20, 4), nullable=True))

    # ── securities: delisting / termination metadata ──────────────────────
    op.add_column("securities", sa.Column("delisting_date", sa.Date(), nullable=True))
    op.add_column("securities", sa.Column("last_trade_date", sa.Date(), nullable=True))
    op.add_column("securities", sa.Column("termination_reason", sa.Text(), nullable=True))

    # ── historical_universe: immutable point-in-time eligibility ──────────
    op.create_table(
        "historical_universe",
        sa.Column("as_of_date", sa.Date(), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), primary_key=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text()),
    )
    op.execute(_IMMUTABLE_GUARD_FN)
    op.execute(
        "CREATE TRIGGER historical_universe_no_update_delete "
        "BEFORE UPDATE OR DELETE ON historical_universe "
        "FOR EACH ROW EXECUTE FUNCTION historical_universe_reject_mutation();"
    )


def downgrade() -> None:
    """Reverse all changes."""
    op.execute(
        "DROP TRIGGER IF EXISTS historical_universe_no_update_delete ON historical_universe;"
    )
    op.execute("DROP FUNCTION IF EXISTS historical_universe_reject_mutation();")
    op.drop_table("historical_universe")
    op.drop_column("securities", "termination_reason")
    op.drop_column("securities", "last_trade_date")
    op.drop_column("securities", "delisting_date")
    op.drop_column("ohlcv_daily", "turnover_value")
    op.drop_column("ohlcv_daily", "prev_close")
