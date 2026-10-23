"""MF data foundation and rights register (ADR-017 MF-2 to MF-11, ADR-023 §2.3).

Shared reference data, not tenant-owned, so no row-level security (ADR-023 §2.6).
``wickstreet_app`` reads and appends MF data and updates run records and the
pointer. It only reads ``rights_grant``: grants are written with the owner login.

Revision ID: 0002_mf_data_foundation
Revises: 0001_identity_tenancy
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_mf_data_foundation"
down_revision: str | None = "0001_identity_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"
_MF_TABLES = (
    "ingestion_run",
    "revision",
    "publication",
    "plan_option",
    "nav",
    "plan_option_listing",
    "plan_option_master",
)


def upgrade() -> None:
    """Create the tables, indexes and runtime grants."""
    op.create_table(
        "rights_grant",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("use", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.Text(), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_rights_grant"),
        schema=_S,
    )
    op.create_index(
        "uq_rights_grant_active",
        "rights_grant",
        ["source", "mode", "use"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("dataset", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("raw_sha256", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.BigInteger(), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("inserted", sa.Integer(), nullable=True),
        sa.Column("superseded", sa.Integer(), nullable=True),
        sa.Column("anomalies", sa.Integer(), nullable=True),
        sa.Column("conflicts", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_run"),
        sa.UniqueConstraint(
            "source", "dataset", "period_start", "period_end", name="uq_ingestion_run_period"
        ),
        schema=_S,
    )
    op.create_table(
        "revision",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("contract", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_sha256", sa.Text(), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("retrieval_grant_id", sa.BigInteger(), nullable=False),
        sa.Column("storage_grant_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], [f"{_S}.ingestion_run.id"], name="fk_revision_run_id_ingestion_run"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_revision"),
        schema=_S,
    )
    op.create_table(
        "publication",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name="ck_publication_single_row"),
        sa.ForeignKeyConstraint(
            ["revision_id"], [f"{_S}.revision.id"], name="fk_publication_revision_id_revision"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_publication"),
        schema=_S,
    )
    op.create_table(
        "plan_option",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("amfi_code", sa.Text(), nullable=False),
        sa.Column("first_revision", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["first_revision"],
            [f"{_S}.revision.id"],
            name="fk_plan_option_first_revision_revision",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plan_option"),
        sa.UniqueConstraint("amfi_code", name="uq_plan_option_amfi_code"),
        schema=_S,
    )
    op.create_table(
        "nav",
        sa.Column("plan_option_id", sa.Integer(), nullable=False),
        sa.Column("nav_date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(), nullable=True),
        sa.Column("anomaly", sa.Text(), nullable=True),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_option_id"],
            [f"{_S}.plan_option.id"],
            name="fk_nav_plan_option_id_plan_option",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"], [f"{_S}.revision.id"], name="fk_nav_revision_id_revision"
        ),
        sa.PrimaryKeyConstraint("plan_option_id", "nav_date", "revision_id", name="pk_nav"),
        schema=_S,
    )
    op.create_index(
        "uq_nav_current",
        "nav",
        ["nav_date", "plan_option_id"],
        unique=True,
        schema=_S,
        postgresql_where=sa.text("superseded_revision IS NULL"),
    )
    for table, extra in (
        (
            "plan_option_listing",
            [
                sa.Column("amc", sa.Text(), nullable=False),
                sa.Column("category", sa.Text(), nullable=False),
                sa.Column("nav_name", sa.Text(), nullable=False),
                sa.Column("plan", sa.Text(), nullable=True),
                sa.Column("option", sa.Text(), nullable=True),
                sa.Column("isin_growth", sa.Text(), nullable=True),
                sa.Column("isin_reinvest", sa.Text(), nullable=True),
            ],
        ),
        (
            "plan_option_master",
            [
                sa.Column("amc", sa.Text(), nullable=False),
                sa.Column("scheme_name", sa.Text(), nullable=False),
                sa.Column("scheme_type", sa.Text(), nullable=False),
                sa.Column("category", sa.Text(), nullable=False),
                sa.Column("nav_name", sa.Text(), nullable=False),
                sa.Column("min_amount", sa.Text(), nullable=True),
                sa.Column("launch_date", sa.Date(), nullable=True),
                sa.Column("closure_date", sa.Date(), nullable=True),
                sa.Column("isin_growth", sa.Text(), nullable=True),
                sa.Column("isin_reinvest", sa.Text(), nullable=True),
            ],
        ),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
            sa.Column("plan_option_id", sa.Integer(), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("revision_id", sa.BigInteger(), nullable=False),
            sa.Column("superseded_revision", sa.BigInteger(), nullable=True),
            *extra,
            sa.ForeignKeyConstraint(
                ["plan_option_id"],
                [f"{_S}.plan_option.id"],
                name=f"fk_{table}_plan_option_id_plan_option",
            ),
            sa.ForeignKeyConstraint(
                ["revision_id"], [f"{_S}.revision.id"], name=f"fk_{table}_revision_id_revision"
            ),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            schema=_S,
        )
        op.create_index(
            f"ix_{table}_plan_option_id", table, ["plan_option_id", "effective_from"], schema=_S
        )
    for table in _MF_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_S}.{table} TO wickstreet_app")
    op.execute(f"GRANT SELECT ON {_S}.rights_grant TO wickstreet_app")


def downgrade() -> None:
    """Drop the tables; their grants go with them."""
    for table in ("plan_option_master", "plan_option_listing", "nav", "plan_option"):
        op.drop_table(table, schema=_S)
    op.drop_table("publication", schema=_S)
    op.drop_table("revision", schema=_S)
    op.drop_table("ingestion_run", schema=_S)
    op.drop_table("rights_grant", schema=_S)
