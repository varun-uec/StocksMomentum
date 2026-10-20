"""Forward returns name their horizon basis (R3-B-32, IMPLEMENTATION_SPEC §10).

Adds ``horizon_basis`` to the primary key, plus ``exit_date`` and
``exit_stale_sessions``. Every existing row gets ``own_bars`` (h of the
security's own bars) and keeps its values; nothing is rewritten. New rows
carry ``sessions`` and sit beside the old ones. The column has no default, so
every writer must name its basis.

The downgrade refuses while any ``sessions`` row exists: dropping the key
column would otherwise make two bases collide. It never deletes rows.

Revision ID: 0023_forward_return_basis
Revises: 0022_security_identity_links
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_forward_return_basis"
down_revision: str | None = "0022_security_identity_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KEY = ["run_id", "security_id", "horizon_days"]


def upgrade() -> None:
    """Add the basis to the key and the exit columns."""
    op.add_column(
        "forward_returns",
        sa.Column("horizon_basis", sa.String(), nullable=False, server_default="own_bars"),
    )
    op.alter_column("forward_returns", "horizon_basis", server_default=None)
    op.create_check_constraint(
        "ck_forward_returns_horizon_basis",
        "forward_returns",
        "horizon_basis IN ('sessions', 'own_bars')",
    )
    op.drop_constraint("forward_returns_pkey", "forward_returns", type_="primary")
    op.create_primary_key("forward_returns_pkey", "forward_returns", [*_KEY, "horizon_basis"])
    op.add_column("forward_returns", sa.Column("exit_date", sa.Date()))
    op.add_column("forward_returns", sa.Column("exit_stale_sessions", sa.Integer()))


def downgrade() -> None:
    """Restore the old key, refusing while session-basis rows exist."""
    count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM forward_returns WHERE horizon_basis <> 'own_bars'")
    )
    if count:
        raise RuntimeError(f"{count} session-basis forward returns exist; refusing to downgrade")
    op.drop_column("forward_returns", "exit_stale_sessions")
    op.drop_column("forward_returns", "exit_date")
    op.drop_constraint("forward_returns_pkey", "forward_returns", type_="primary")
    op.create_primary_key("forward_returns_pkey", "forward_returns", _KEY)
    op.drop_constraint("ck_forward_returns_horizon_basis", "forward_returns")
    op.drop_column("forward_returns", "horizon_basis")
