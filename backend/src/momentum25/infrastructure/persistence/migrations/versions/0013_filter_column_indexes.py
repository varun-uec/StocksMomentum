"""Index the filter/join columns that composite primary keys do not lead with.

Every table below is keyed on a composite primary key whose *first* column is
the run or security, so Postgres can serve a lookup by that leading column from
the primary-key index but must scan for the trailing one. The 2026-08-15
functional audit measured the result: ``/market/context`` at 1.54 s (a date
range over ``ohlcv_daily``, whose key leads with ``security_id``) and
``/validation/dashboard`` at 41.55 s (per-run aggregates over
``screening_results`` and ``forward_returns``).

Indexed here:

* ``ohlcv_daily(date)`` -- breadth and universe closes read a date range.
* ``benchmark_index_daily(date)`` -- same, for index closes.
* ``corporate_actions(security_id)`` -- adjustment refresh reads per security.
* ``screening_results(security_id)`` -- score history reads per security.
* ``forward_returns(security_id)`` -- validation joins per security.
* ``universe_membership(run_id)`` -- already the key's leading column, so it is
  *not* indexed again here; the same is true of ``rule_results(run_id)``.

``screening_runs.status`` also gains a CHECK constraint. The column is written
only from :class:`RunStatus`, but nothing in the database enforced that, so a
bad writer could persist a status the application cannot map back.

Revision ID: 0013_filter_column_indexes
Revises: 0012_drop_legacy_ohlcv_bak
Create Date: 2026-08-15
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_filter_column_indexes"
down_revision: str | None = "0012_drop_legacy_ohlcv_bak"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_ohlcv_daily_date", "ohlcv_daily", "date"),
    ("ix_benchmark_index_daily_date", "benchmark_index_daily", "date"),
    ("ix_corporate_actions_security_id", "corporate_actions", "security_id"),
    ("ix_screening_results_security_id", "screening_results", "security_id"),
    ("ix_forward_returns_security_id", "forward_returns", "security_id"),
)

# Mirrors momentum25.domain.value_objects.types.RunStatus.
_RUN_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def upgrade() -> None:
    """Add the filter-column indexes and the run-status CHECK constraint."""
    for name, table, column in _INDEXES:
        op.create_index(name, table, [column])

    values = ", ".join(f"'{s}'" for s in _RUN_STATUSES)
    op.create_check_constraint(
        "ck_screening_runs_status", "screening_runs", f"status IN ({values})"
    )


def downgrade() -> None:
    """Drop the CHECK constraint and the filter-column indexes."""
    op.drop_constraint("ck_screening_runs_status", "screening_runs", type_="check")
    for name, table, _column in _INDEXES:
        op.drop_index(name, table_name=table)
