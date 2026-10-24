"""Retire a metric snapshot from serving and keep it for audit (MF-11).

A retired snapshot keeps its row and payload. Reads never select it, and the same
revision and method version can be computed again. Only the owner login retires.

Revision ID: 0010_snapshot_retirement
Revises: 0009_distributions
Create Date: 2026-10-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_snapshot_retirement"
down_revision: str | None = "0009_distributions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"


def upgrade() -> None:
    """Add the retirement columns; one serving snapshot per revision and method version."""
    op.add_column("metric_snapshot", sa.Column("retired_at", sa.DateTime(timezone=True)), schema=_S)
    op.add_column("metric_snapshot", sa.Column("retired_by", sa.Text()), schema=_S)
    op.add_column("metric_snapshot", sa.Column("retired_reason", sa.Text()), schema=_S)
    op.create_check_constraint(
        op.f("ck_metric_snapshot_retired"),
        "metric_snapshot",
        "(retired_at IS NULL) = (retired_by IS NULL) "
        "AND (retired_at IS NULL) = (retired_reason IS NULL)",
        schema=_S,
    )
    op.drop_constraint("uq_metric_snapshot_revision", "metric_snapshot", schema=_S)
    op.create_index(
        "uq_metric_snapshot_revision",
        "metric_snapshot",
        ["revision_id", "method_version"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("retired_at IS NULL"),
    )


def downgrade() -> None:
    """Drop the columns; fails if a retired snapshot was recomputed."""
    op.drop_index("uq_metric_snapshot_revision", "metric_snapshot", schema=_S)
    op.create_unique_constraint(
        "uq_metric_snapshot_revision",
        "metric_snapshot",
        ["revision_id", "method_version"],
        schema=_S,
    )
    op.drop_constraint(op.f("ck_metric_snapshot_retired"), "metric_snapshot", schema=_S)
    for column in ("retired_reason", "retired_by", "retired_at"):
        op.drop_column("metric_snapshot", column, schema=_S)
