"""Research records: the user's watchlists, screens, notes, briefs and scenarios (W1).

User-owned, so tenant row-level security is enabled and forced, as in 0001.

Revision ID: 0005_research_records
Revises: 0004_reference_rates
Create Date: 2026-10-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_research_records"
down_revision: str | None = "0004_reference_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_S = "wickstreet"
_CURRENT_TENANT = "nullif(current_setting('wickstreet.tenant_id', true), '')::uuid"


def upgrade() -> None:
    """Create ``research_record``, its policy and the runtime grant."""
    op.create_table(
        "research_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('watchlist', 'screen', 'note', 'brief', 'scenario')",
            name="ck_research_record_kind",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], [f"{_S}.tenant.id"], name="fk_research_record_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], [f"{_S}.app_user.id"], name="fk_research_record_owner_id_app_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_research_record"),
        schema=_S,
    )
    op.create_index(
        "ix_research_record_owner_kind",
        "research_record",
        ["tenant_id", "owner_id", "kind"],
        schema=_S,
    )
    op.execute(f"ALTER TABLE {_S}.research_record ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_S}.research_record FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {_S}.research_record "
        f"USING (tenant_id = {_CURRENT_TENANT}) WITH CHECK (tenant_id = {_CURRENT_TENANT})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_S}.research_record TO wickstreet_app")


def downgrade() -> None:
    """Drop the table; its policy and grant go with it."""
    op.drop_table("research_record", schema=_S)
