"""IDCW payouts per plan-option, as AMFI lists them (doc 21 E5).

Shared reference data, revisioned like NAVs, so no row-level security (ADR-023 §2.6).

Revision ID: 0009_distributions
Revises: 0008_portfolio_ledger
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_distributions"
down_revision: str | None = "0008_portfolio_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def upgrade() -> None:
    """Create ``distribution`` and its runtime grant."""
    op.create_table(
        "distribution",
        sa.Column("plan_option_id", sa.Integer(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("per_unit", sa.Numeric(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_option_id"],
            [f"{_S}.plan_option.id"],
            name="fk_distribution_plan_option_id_plan_option",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"], [f"{_S}.revision.id"], name="fk_distribution_revision_id_revision"
        ),
        sa.PrimaryKeyConstraint(
            "plan_option_id", "record_date", "revision_id", name="pk_distribution"
        ),
        schema=_S,
    )
    op.create_index(
        "uq_distribution_current",
        "distribution",
        ["plan_option_id", "record_date"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_S}.distribution TO wickstreet_app")


def downgrade() -> None:
    """Drop the table."""
    op.drop_table("distribution", schema=_S)
