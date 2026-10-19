"""Strategy families and user strategies (ADR-014 §3–4, M14).

A family records a hypothesis and its root config, and a trigger refuses any
later change to it. A user strategy is a ``strategies`` row of kind ``user``.
It names its family and the config it was derived from.

Revision ID: 0018_strategy_families
Revises: 0017_data_manifests
Create Date: 2026-10-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from momentum25.infrastructure.persistence.history import append_only_ddl

revision: str = "0018_strategy_families"
down_revision: str | None = "0017_data_manifests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``strategy_families`` and link user strategies to it."""
    op.create_table(
        "strategy_families",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("hypothesis_key", sa.Text(), nullable=False, unique=True),
        sa.Column("root_config_hash", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for statement in append_only_ddl(("strategy_families",)):
        op.execute(statement)
    op.add_column(
        "strategies",
        sa.Column(
            "family_id", sa.BigInteger(), sa.ForeignKey("strategy_families.id"), nullable=True
        ),
    )
    op.add_column("strategies", sa.Column("parent_config_hash", sa.String(), nullable=True))
    op.create_index("ix_strategies_family_id", "strategies", ["family_id"])
    op.create_check_constraint(
        "ck_strategies_family", "strategies", "(kind = 'user') = (family_id IS NOT NULL)"
    )
    op.create_index(
        "uq_strategies_user_config_hash",
        "strategies",
        ["config_hash"],
        unique=True,
        postgresql_where=sa.text("kind = 'user'"),
    )


def downgrade() -> None:
    """Remove user strategies' links and the families table."""
    op.drop_index("uq_strategies_user_config_hash", table_name="strategies")
    op.drop_constraint("ck_strategies_family", "strategies", type_="check")
    op.drop_index("ix_strategies_family_id", table_name="strategies")
    op.drop_column("strategies", "parent_config_hash")
    op.drop_column("strategies", "family_id")
    op.drop_table("strategy_families")
    op.execute("DROP FUNCTION IF EXISTS refuse_change()")
