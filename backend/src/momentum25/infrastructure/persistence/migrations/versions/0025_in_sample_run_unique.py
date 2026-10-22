"""One In-Sample run per family, config, window and data version (ADR-014 section 12).

Two identical variant handoffs that race could each insert a run. This partial
unique index makes the database refuse the second. The development database held
no evaluations and no duplicate run identities on 2026-10-22. If a database holds
duplicates, the index fails to build and no row is changed or deleted. The
downgrade drops the index only.

Revision ID: 0025_in_sample_run_unique
Revises: 0024_schema_drift_reconcile
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_in_sample_run_unique"
down_revision: str | None = "0024_schema_drift_reconcile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the unique index."""
    op.create_index(
        "uq_strategy_evaluations_in_sample",
        "strategy_evaluations",
        ["family_id", "config_hash", "window_start", "window_end", "data_version"],
        unique=True,
        postgresql_where=sa.text("result_class = 'in_sample'"),
    )


def downgrade() -> None:
    """Drop the index; no row changes."""
    op.drop_index("uq_strategy_evaluations_in_sample", table_name="strategy_evaluations")
