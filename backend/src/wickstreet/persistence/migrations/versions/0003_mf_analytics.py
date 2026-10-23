"""MF analytics: metric snapshots and curated plan-option links (ADR-017 MF-3, MF-11).

Shared reference data, so no row-level security (ADR-023 §2.6). ``wickstreet_app``
reads and inserts snapshots; it only reads links, which the owner login writes.

Revision ID: 0003_mf_analytics
Revises: 0002_mf_data_foundation
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_mf_analytics"
down_revision: str | None = "0002_mf_data_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def upgrade() -> None:
    """Create the tables and runtime grants."""
    op.create_table(
        "metric_snapshot",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("method_version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("funds", sa.Integer(), nullable=False),
        sa.Column("sources", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("grant_ids", postgresql.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metric_snapshot"),
        sa.UniqueConstraint("revision_id", "method_version", name="uq_metric_snapshot_revision"),
        schema=_S,
    )
    op.create_table(
        "plan_option_link",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("from_plan_option_id", sa.Integer(), nullable=False),
        sa.Column("to_plan_option_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('merger', 'code_change', 'segregated_portfolio')",
            name="ck_plan_option_link_kind",
        ),
        sa.ForeignKeyConstraint(
            ["from_plan_option_id"],
            [f"{_S}.plan_option.id"],
            name="fk_plan_option_link_from_plan_option_id_plan_option",
        ),
        sa.ForeignKeyConstraint(
            ["to_plan_option_id"],
            [f"{_S}.plan_option.id"],
            name="fk_plan_option_link_to_plan_option_id_plan_option",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plan_option_link"),
        sa.UniqueConstraint(
            "from_plan_option_id", "to_plan_option_id", "kind", name="uq_plan_option_link"
        ),
        schema=_S,
    )
    op.execute(f"GRANT SELECT, INSERT ON {_S}.metric_snapshot TO wickstreet_app")
    op.execute(f"GRANT SELECT ON {_S}.plan_option_link TO wickstreet_app")


def downgrade() -> None:
    """Drop the tables; their grants go with them."""
    op.drop_table("plan_option_link", schema=_S)
    op.drop_table("metric_snapshot", schema=_S)
