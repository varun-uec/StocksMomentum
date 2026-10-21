"""Make the migrated schema match the models (R3-B-15).

Eleven columns were nullable in the database but NOT NULL in the models.
Setting NOT NULL fails if a row holds NULL, which is the right outcome: no value
is invented. The development database held none in these columns on 2026-10-21.

The development database was also built by ``create_all`` once, so two indexes
differ from migration 0001. The steps below are idempotent: they leave a
migrated database as it is and bring the development one to the same shape.
``screening_results`` gets ``(run_id, rank)`` and loses the lone ``rank`` index.
``securities.symbol`` gets the unique constraint and a plain index.

Revision ID: 0024_schema_drift_reconcile
Revises: 0023_forward_return_basis
Create Date: 2026-10-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024_schema_drift_reconcile"
down_revision: str | None = "0023_forward_return_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("securities", "created_at"),
    ("securities", "updated_at"),
    ("strategies", "created_at"),
    ("survivorship_gap_event", "created_at"),
    ("corporate_action_inference_log", "created_at"),
    ("forward_returns", "computed_at"),
    ("corporate_actions", "security_id"),
    ("screening_runs", "strategy_id"),
    # History tables copy the column shape, so they follow their current table.
    ("corporate_actions_history", "security_id"),
    ("securities_history", "created_at"),
    ("securities_history", "updated_at"),
)


def upgrade() -> None:
    """Enforce NOT NULL where the models require it."""
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_screening_results_run_rank "
        "ON screening_results (run_id, rank)"
    )
    op.execute("DROP INDEX IF EXISTS ix_screening_results_rank")
    op.execute(
        """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'securities_symbol_key') THEN
        ALTER TABLE securities ADD CONSTRAINT securities_symbol_key UNIQUE (symbol);
    END IF;
END
$$"""
    )
    op.execute("DROP INDEX IF EXISTS ix_securities_symbol")
    op.execute("CREATE INDEX ix_securities_symbol ON securities (symbol)")


def downgrade() -> None:
    """Allow NULL again. The index changes stay: they are the shape of migration 0001."""
    for table, column in _COLUMNS:
        op.alter_column(table, column, nullable=True)
