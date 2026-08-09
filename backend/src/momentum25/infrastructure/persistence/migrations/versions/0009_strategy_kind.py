"""Strategy ``kind`` field: production vs research (strategy lifecycle).

Strategies are now classified structurally: ``kind`` marks research-only
definitions (benchmarks and experiments) so the dashboard selector can exclude
them without a hardcoded name list. The column carries a server default of
``production``; the one-time backfill reclassifies the six research files
(``benchmark_*`` and ``experimental_rs80``).

Revision ID: 0009_strategy_kind
Revises: 0008_security_search_trgm
Create Date: 2026-08-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_strategy_kind"
down_revision: str | None = "0008_security_search_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the ``kind`` column and reclassify the research strategies."""
    op.add_column(
        "strategies",
        sa.Column("kind", sa.String(), nullable=False, server_default="production"),
    )
    op.execute(
        "UPDATE strategies SET kind='research' "
        "WHERE name LIKE 'benchmark_%' OR name='experimental_rs80'"
    )


def downgrade() -> None:
    """Drop the ``kind`` column."""
    op.drop_column("strategies", "kind")