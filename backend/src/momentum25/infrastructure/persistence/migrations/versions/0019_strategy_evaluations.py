"""Strategy evaluations (ADR-014 §5–7, M14): the research namespace for the Studio.

One row per evaluation of a user strategy in one result class. A trigger keeps
a completed row final and never lets an Out-of-Sample Evaluation be deleted.
A unique index allows one Out-of-Sample Evaluation per family per window.

Revision ID: 0019_strategy_evaluations
Revises: 0018_strategy_families
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from momentum25.infrastructure.persistence.history import evaluation_guard_ddl

revision: str = "0019_strategy_evaluations"
down_revision: str | None = "0018_strategy_families"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``strategy_evaluations`` and its guard."""
    op.create_table(
        "strategy_evaluations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "family_id", sa.BigInteger(), sa.ForeignKey("strategy_families.id"), nullable=False
        ),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("result_class", sa.String(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column(
            "data_version",
            sa.String(12),
            sa.ForeignKey("data_manifests.data_version"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "result_class IN ('screening', 'in_sample', 'out_of_sample')",
            name="ck_strategy_evaluations_class",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_strategy_evaluations_status",
        ),
    )
    op.create_index("ix_strategy_evaluations_family_id", "strategy_evaluations", ["family_id"])
    op.create_index(
        "uq_strategy_evaluations_holdout",
        "strategy_evaluations",
        ["family_id", "window_start", "window_end"],
        unique=True,
        postgresql_where=sa.text("result_class = 'out_of_sample'"),
    )
    for statement in evaluation_guard_ddl():
        op.execute(statement)


def downgrade() -> None:
    """Drop ``strategy_evaluations`` and its guard."""
    op.drop_table("strategy_evaluations")
    op.execute("DROP FUNCTION IF EXISTS guard_evaluation()")
