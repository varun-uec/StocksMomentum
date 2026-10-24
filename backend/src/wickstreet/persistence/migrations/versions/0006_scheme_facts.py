"""Scheme facts from AMFI: TER, performance, summaries, tracking error (doc 21 E1, E3).

Shared reference data, revisioned like NAVs, so no row-level security (ADR-023 §2.6).
``scheme`` and ``scheme_isin`` hold AMFI's scheme ids and the ISIN join to
plan-options; ``scheme_fact`` holds each filed value from its date.

Revision ID: 0006_scheme_facts
Revises: 0005_research_records
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_scheme_facts"
down_revision: str | None = "0005_research_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def _revision_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["revision_id"], [f"{_S}.revision.id"], name=f"fk_{table}_revision_id_revision"
    )


def upgrade() -> None:
    """Create the three tables and runtime grants."""
    op.create_table(
        "scheme",
        sa.Column("sd_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("mf_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("sd_id", name="pk_scheme"),
        _revision_fk("scheme"),
        schema=_S,
    )
    op.create_table(
        "scheme_isin",
        sa.Column("isin", sa.Text(), nullable=False),
        sa.Column("sd_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("isin", name="pk_scheme_isin"),
        sa.ForeignKeyConstraint(
            ["sd_id"], [f"{_S}.scheme.sd_id"], name="fk_scheme_isin_sd_id_scheme"
        ),
        _revision_fk("scheme_isin"),
        schema=_S,
    )
    op.create_table(
        "scheme_fact",
        sa.Column("sd_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("num", sa.Numeric(), nullable=True),
        sa.Column("txt", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("plan IN ('', 'regular', 'direct')", name="ck_scheme_fact_plan"),
        sa.ForeignKeyConstraint(
            ["sd_id"], [f"{_S}.scheme.sd_id"], name="fk_scheme_fact_sd_id_scheme"
        ),
        _revision_fk("scheme_fact"),
        sa.PrimaryKeyConstraint(
            "sd_id", "name", "plan", "as_of", "revision_id", name="pk_scheme_fact"
        ),
        schema=_S,
    )
    op.create_index(
        "uq_scheme_fact_current",
        "scheme_fact",
        ["sd_id", "name", "plan", "as_of"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    for table in ("scheme", "scheme_isin", "scheme_fact"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_S}.{table} TO wickstreet_app")


def downgrade() -> None:
    """Drop the tables."""
    for table in ("scheme_fact", "scheme_isin", "scheme"):
        op.drop_table(table, schema=_S)
