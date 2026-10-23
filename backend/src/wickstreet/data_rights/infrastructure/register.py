"""PostgreSQL rights register.

The runtime role only reads it. Grants are written with the owner login, by the
``wickstreet rights`` commands, so the app cannot widen its own rights.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Row, func, insert, select, update

from platform_common.database import Database
from wickstreet.data_rights.domain.rights import Grant, Use
from wickstreet.data_rights.infrastructure.tables import rights_grant


class SqlRightsRegister:
    """Reads the active grants of one operating mode."""

    def __init__(self, database: Database, mode: str) -> None:
        """Bind the register to a database and the mode the app runs in."""
        self._database = database
        self._mode = mode

    async def grant_for(self, source: str, use: Use) -> Grant | None:
        """Return the active grant, or ``None``."""
        async with self._database.session() as session:
            row = (
                await session.execute(
                    select(rights_grant.c.id, rights_grant.c.basis).where(
                        rights_grant.c.source == source,
                        rights_grant.c.mode == self._mode,
                        rights_grant.c.use == use.value,
                        rights_grant.c.revoked_at.is_(None),
                    )
                )
            ).first()
        return None if row is None else Grant(id=row.id, source=source, use=use, basis=row.basis)


async def record_grants(
    database: Database, *, source: str, mode: str, uses: Sequence[Use], basis: str, granted_by: str
) -> list[int]:
    """Record each use not already granted; return the ids of the new grants."""
    created: list[int] = []
    async with database.session() as session:
        for use in uses:
            active = await session.scalar(
                select(rights_grant.c.id).where(
                    rights_grant.c.source == source,
                    rights_grant.c.mode == mode,
                    rights_grant.c.use == use.value,
                    rights_grant.c.revoked_at.is_(None),
                )
            )
            if active is None:
                new_id = await session.scalar(
                    insert(rights_grant)
                    .values(
                        source=source, mode=mode, use=use.value, basis=basis, granted_by=granted_by
                    )
                    .returning(rights_grant.c.id)
                )
                created.append(int(new_id))
    return created


async def revoke_grants(database: Database, *, source: str, mode: str, uses: Sequence[Use]) -> int:
    """Revoke the active grants for these uses; return how many were revoked."""
    async with database.session() as session:
        result = await session.execute(
            update(rights_grant)
            .where(
                rights_grant.c.source == source,
                rights_grant.c.mode == mode,
                rights_grant.c.use.in_([u.value for u in uses]),
                rights_grant.c.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )
    return int(result.rowcount)  # type: ignore[attr-defined]


async def list_grants(database: Database) -> Sequence[Row[tuple[object, ...]]]:
    """Return every grant, active and revoked, oldest first."""
    async with database.session() as session:
        return (await session.execute(select(rights_grant).order_by(rights_grant.c.id))).all()
