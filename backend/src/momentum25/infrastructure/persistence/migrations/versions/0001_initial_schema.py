"""Initial schema — all tables from IMPLEMENTATION_SPEC §4.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all tables."""
    op.create_table(
        "securities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("isin", sa.String()),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sector", sa.String()),
        sa.Column("industry", sa.String()),
        sa.Column("exchange", sa.String(), nullable=False, server_default="NSE"),
        sa.Column("listing_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tenant_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_securities_symbol", "securities", ["symbol"])

    op.create_table(
        "ohlcv_daily",
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("adj_close", sa.Numeric(18, 4)),
        sa.Column("adj_factor", sa.Numeric(18, 8), nullable=False, server_default="1"),
    )

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id")),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("ratio", sa.Numeric(18, 8)),
        sa.Column("raw", postgresql.JSONB()),
        sa.UniqueConstraint("security_id", "ex_date", "type"),
    )

    op.create_table(
        "benchmark_index_daily",
        sa.Column("index_code", sa.String(), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
    )

    op.create_table(
        "strategies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version"),
    )
    op.create_index("ix_strategies_name", "strategies", ["name"])

    op.create_table(
        "screening_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.BigInteger(), sa.ForeignKey("strategies.id")),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("data_version", sa.String(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("stats", postgresql.JSONB()),
        sa.UniqueConstraint("strategy_id", "run_date", "data_version", "config_hash"),
    )
    op.create_index("ix_screening_runs_status", "screening_runs", ["status"])

    op.create_table(
        "universe_membership",
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("screening_runs.id"), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text()),
    )

    op.create_table(
        "screening_results",
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("screening_runs.id"), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("rank", sa.Integer()),
        sa.Column("momentum_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("buy_setup_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("hard_filters_passed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_screening_results_run_rank", "screening_results", ["run_id", "rank"])

    op.create_table(
        "rule_results",
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("screening_runs.id"), primary_key=True),
        sa.Column("security_id", sa.BigInteger(), sa.ForeignKey("securities.id"), primary_key=True),
        sa.Column("rule_id", sa.String(), primary_key=True),
        sa.Column("engine_id", sa.String(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("raw_value", sa.Numeric(18, 6)),
        sa.Column("threshold", sa.Numeric(18, 6)),
        sa.Column("operator", sa.String(), nullable=False),
        sa.Column("weight", sa.Numeric(10, 4), nullable=False),
        sa.Column("contribution", sa.Numeric(10, 4), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    """Drop all tables."""
    for table in (
        "rule_results",
        "screening_results",
        "universe_membership",
        "screening_runs",
        "strategies",
        "benchmark_index_daily",
        "corporate_actions",
        "ohlcv_daily",
        "securities",
    ):
        op.drop_table(table)
