"""Monthly portfolio disclosures and AMFI's market-cap list (doc 21 E4).

Shared reference data, revisioned like NAVs, so no row-level security (ADR-023 §2.6).

Revision ID: 0007_holdings
Revises: 0006_scheme_facts
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_holdings"
down_revision: str | None = "0006_scheme_facts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def _revision_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["revision_id"], [f"{_S}.revision.id"], name=f"fk_{table}_revision_id_revision"
    )


def upgrade() -> None:
    """Create ``holding`` and ``security_class`` and runtime grants."""
    op.create_table(
        "holding",
        sa.Column("sd_id", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("asset", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "asset IN ('equity', 'debt', 'cash', 'derivative', 'other')",
            name="ck_holding_asset",
        ),
        sa.ForeignKeyConstraint(["sd_id"], [f"{_S}.scheme.sd_id"], name="fk_holding_sd_id_scheme"),
        _revision_fk("holding"),
        sa.PrimaryKeyConstraint("sd_id", "as_of", "seq", "revision_id", name="pk_holding"),
        schema=_S,
    )
    op.create_index(
        "uq_holding_current",
        "holding",
        ["sd_id", "as_of", "seq"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    op.create_index("ix_holding_isin", "holding", ["isin"], schema=_S)
    op.create_table(
        "security_class",
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("market_cap_cr", sa.Numeric(), nullable=True),
        sa.Column("cap_class", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        _revision_fk("security_class"),
        sa.PrimaryKeyConstraint("isin", "as_of", "revision_id", name="pk_security_class"),
        schema=_S,
    )
    op.create_index(
        "uq_security_class_current",
        "security_class",
        ["isin", "as_of"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    for table in ("holding", "security_class"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_S}.{table} TO wickstreet_app")


def downgrade() -> None:
    """Drop the tables."""
    op.drop_table("security_class", schema=_S)
    op.drop_table("holding", schema=_S)
