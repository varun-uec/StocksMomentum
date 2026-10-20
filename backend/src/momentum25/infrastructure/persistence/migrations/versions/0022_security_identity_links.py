"""Verified security identity links, versioned (R3-B-31, IMPLEMENTATION_SPEC §4).

Creates ``security_identity_links`` empty, its history table and the version-1
trigger (``history.ddl_v2``). A link is part of the market-data revision like
every other input row. Additive and reversible; no existing row changes.

Revision ID: 0022_security_identity_links
Revises: 0021_alert_drawing_snapshots
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from momentum25.infrastructure.persistence.history import PROVENANCE, ddl_v2, history_name

revision: str = "0022_security_identity_links"
down_revision: str | None = "0021_alert_drawing_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "security_identity_links"


def upgrade() -> None:
    """Create the table, its history table and its trigger."""
    allowed = ", ".join(f"'{p}'" for p in PROVENANCE)
    op.create_table(
        _TABLE,
        sa.Column(
            "predecessor_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True
        ),
        sa.Column(
            "successor_id",
            sa.BigInteger(),
            sa.ForeignKey("securities.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Numeric(20, 10), nullable=False, server_default="1"),
        sa.Column("evidence_source", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
        sa.Column("provenance", sa.String(), nullable=False, server_default="published"),
        sa.CheckConstraint("predecessor_id <> successor_id", name="ck_identity_links_distinct"),
        sa.CheckConstraint("ratio > 0", name="ck_identity_links_ratio"),
        sa.CheckConstraint(f"provenance IN ({allowed})", name=f"ck_{_TABLE}_provenance"),
    )
    op.create_index(f"ix_{_TABLE}_revision_id", _TABLE, ["revision_id"])
    history = history_name(_TABLE)
    op.execute(f"CREATE TABLE {history} (LIKE {_TABLE})")
    op.add_column(history, sa.Column("superseded_revision", sa.BigInteger(), nullable=False))
    op.add_column(history, sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False))
    op.add_column(history, sa.Column("operation", sa.String(1), nullable=False))
    op.create_index(f"ix_{history}_superseded_revision", history, ["superseded_revision"])
    for statement in ddl_v2():
        op.execute(statement)


def downgrade() -> None:
    """Drop the trigger, the history table and the table."""
    op.execute(f"DROP TRIGGER IF EXISTS {_TABLE}_versioned ON {_TABLE}")
    op.drop_table(history_name(_TABLE))
    op.drop_table(_TABLE)
