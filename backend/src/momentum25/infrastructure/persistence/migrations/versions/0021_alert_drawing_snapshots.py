"""Version armed rules and capture bounded drawing-linked EOD alerts.

Revision ID: 0021_alert_drawing_snapshots
Revises: 0020_committed_revision_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0021_alert_drawing_snapshots"
down_revision: str | None = "0020_committed_revision_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("drawing", JSONB(), nullable=True))
    op.add_column(
        "alerts", sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    op.drop_column("alerts", "revision")
    op.drop_column("alerts", "drawing")
