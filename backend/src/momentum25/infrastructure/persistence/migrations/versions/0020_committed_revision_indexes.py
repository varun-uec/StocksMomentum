"""Index committed market-data revisions for deterministic manifest capture.

Revision ID: 0020_committed_revision_indexes
Revises: 0019_strategy_evaluations
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020_committed_revision_indexes"
down_revision: str | None = "0019_strategy_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "securities",
    "ohlcv_daily",
    "corporate_actions",
    "benchmark_index_daily",
    "historical_universe",
)


def upgrade() -> None:
    """Index the current row-version high-water marks."""
    for table in _TABLES:
        op.create_index(f"ix_{table}_revision_id", table, ["revision_id"])


def downgrade() -> None:
    """Drop indexes added by this migration."""
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_revision_id", table_name=table)
