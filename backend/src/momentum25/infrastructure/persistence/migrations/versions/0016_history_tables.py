"""History tables for the evaluation inputs (ADR-014 §7, M14).

Adds ``revision_id``, ``recorded_at`` and ``provenance`` to each versioned
input table, creates ``<table>_history``, and installs the version-1 trigger
from ``infrastructure/persistence/history.py``. Existing rows get revision 0 and
no ``recorded_at``: they were stored before versioning. Additive and
reversible; the writers do not change.

Revision ID: 0016_history_tables
Revises: 0015_alerts
Create Date: 2026-10-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from momentum25.infrastructure.persistence.history import (
    FUNCTION,
    PROVENANCE,
    SEQUENCE,
    VERSIONED,
    ddl_v1,
    history_name,
)

revision: str = "0016_history_tables"
down_revision: str | None = "0015_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the version columns, the history tables and the triggers."""
    allowed = ", ".join(f"'{p}'" for p in PROVENANCE)
    for table, (_, provenance) in VERSIONED.items():
        op.add_column(
            table, sa.Column("revision_id", sa.BigInteger(), nullable=False, server_default="0")
        )
        op.add_column(table, sa.Column("recorded_at", sa.DateTime(timezone=True)))
        op.add_column(
            table, sa.Column("provenance", sa.String(), nullable=False, server_default=provenance)
        )
        op.create_check_constraint(f"ck_{table}_provenance", table, f"provenance IN ({allowed})")
        history = history_name(table)
        op.execute(f"CREATE TABLE {history} (LIKE {table})")
        op.add_column(history, sa.Column("superseded_revision", sa.BigInteger(), nullable=False))
        op.add_column(
            history, sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False)
        )
        op.add_column(history, sa.Column("operation", sa.String(1), nullable=False))
        op.create_index(f"ix_{history}_superseded_revision", history, ["superseded_revision"])
    for statement in ddl_v1():
        op.execute(statement)


def downgrade() -> None:
    """Remove the triggers, history tables and version columns."""
    for table in VERSIONED:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_versioned ON {table}")
        op.drop_table(history_name(table))
        op.drop_constraint(f"ck_{table}_provenance", table)
        for column in ("provenance", "recorded_at", "revision_id"):
            op.drop_column(table, column)
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}()")
    op.execute(f"DROP SEQUENCE IF EXISTS {SEQUENCE}")
