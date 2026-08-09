"""Trigram indexes for security symbol/name search (Objective 4).

``SqlSecurityRepository.search`` runs ``symbol LIKE '%term%'`` and
``upper(name) LIKE '%term%'`` on every keystroke of the nav typeahead. The
existing ``symbol`` btree index (0001) can't serve a leading-wildcard LIKE,
and ``name`` has no index at all -- both legs were full table scans. GIN
trigram indexes serve both patterns.

Revision ID: 0008_security_search_trgm
Revises: 0007_watchlist
Create Date: 2026-08-09
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_security_search_trgm"
down_revision: str | None = "0007_watchlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pg_trgm and index symbol/name for substring search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_securities_symbol_trgm ON securities "
        "USING gin (symbol gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_securities_name_trgm ON securities "
        "USING gin (upper(name) gin_trgm_ops)"
    )


def downgrade() -> None:
    """Drop the trigram indexes."""
    op.execute("DROP INDEX IF EXISTS ix_securities_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_securities_symbol_trgm")
