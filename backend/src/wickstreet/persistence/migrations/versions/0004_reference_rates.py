"""Reference rates: the 91-day T-bill yield and other series (doc 21 E2).

Shared reference data, revisioned like NAVs, so no row-level security (ADR-023
§2.6). ``revision.retrieval_grant_id`` becomes nullable: an imported file, such as
an RBI table a person downloaded, was not retrieved by Wickstreet.

Revision ID: 0004_reference_rates
Revises: 0003_mf_analytics
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_reference_rates"
down_revision: str | None = "0003_mf_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def upgrade() -> None:
    """Create ``rate_point`` and relax the retrieval grant."""
    op.create_table(
        "rate_point",
        sa.Column("series", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["revision_id"], [f"{_S}.revision.id"], name="fk_rate_point_revision_id_revision"
        ),
        sa.PrimaryKeyConstraint("series", "effective_date", "revision_id", name="pk_rate_point"),
        schema=_S,
    )
    op.create_index(
        "uq_rate_point_current",
        "rate_point",
        ["series", "effective_date"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    op.alter_column("revision", "retrieval_grant_id", nullable=True, schema=_S)
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_S}.rate_point TO wickstreet_app")


def downgrade() -> None:
    """Drop ``rate_point``; fails if an imported revision has no retrieval grant."""
    op.alter_column("revision", "retrieval_grant_id", nullable=False, schema=_S)
    op.drop_table("rate_point", schema=_S)
