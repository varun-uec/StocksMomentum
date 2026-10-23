"""Identity tables under tenant row-level security (ADR-023 §2.6, U3, U6).

``tenant`` and ``app_user`` hold the principals. Each gets row-level security,
forced on the owner too. One policy compares the row's tenant with the
transaction's ``wickstreet.tenant_id`` setting; an unset or empty setting matches
no row. ``wickstreet_app`` gets DML on these tables only.

Revision ID: 0001_identity_tenancy
Revises:
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_identity_tenancy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_TENANT = "nullif(current_setting('wickstreet.tenant_id', true), '')::uuid"
# Table and the column that names its tenant.
_TENANT_SCOPED = (("tenant", "id"), ("app_user", "tenant_id"))


def upgrade() -> None:
    """Create the tables, their policies and the runtime grants."""
    op.create_table(
        "tenant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant"),
        schema="wickstreet",
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["wickstreet.tenant.id"], name="fk_app_user_tenant_id_tenant"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        schema="wickstreet",
    )
    for table, column in _TENANT_SCOPED:
        op.execute(f"ALTER TABLE wickstreet.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE wickstreet.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON wickstreet.{table} "
            f"USING ({column} = {_CURRENT_TENANT}) WITH CHECK ({column} = {_CURRENT_TENANT})"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON wickstreet.{table} TO wickstreet_app")


def downgrade() -> None:
    """Drop both tables; their policies and grants go with them."""
    op.drop_table("app_user", schema="wickstreet")
    op.drop_table("tenant", schema="wickstreet")
