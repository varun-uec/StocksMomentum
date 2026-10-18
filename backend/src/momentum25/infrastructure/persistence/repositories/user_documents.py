"""User-document repository: optimistic concurrency in single statements (ADR-013 §5)."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.user_document import DocumentKind, UserDocument
from momentum25.domain.errors import RevisionMismatchError
from momentum25.infrastructure.persistence.models import UserDocumentModel


def _to_entity(row: UserDocumentModel) -> UserDocument:
    return UserDocument(
        # Only this repository writes the column, always with a DocumentKind.
        kind=cast(DocumentKind, row.kind),
        key=row.key,
        body=row.body,
        schema_version=row.schema_version,
        revision=row.revision,
        updated_at=row.updated_at,
    )


class SqlUserDocumentRepository:
    """Async SQLAlchemy implementation of :class:`UserDocumentRepository`.

    Each write is one statement whose WHERE clause carries the precondition, so
    the check and the write are atomic: there is no read-then-write race.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def get(self, kind: DocumentKind, key: str) -> UserDocument | None:
        """Return the document, or ``None`` if it was never saved."""
        row = await self._session.get(UserDocumentModel, (kind, key))
        return _to_entity(row) if row is not None else None

    async def create(
        self, kind: DocumentKind, key: str, body: dict[str, Any], schema_version: int
    ) -> UserDocument:
        """Insert at revision 1; ``ON CONFLICT DO NOTHING`` makes an existing row a mismatch."""
        stmt = (
            insert(UserDocumentModel)
            .values(kind=kind, key=key, body=body, schema_version=schema_version, revision=1)
            .on_conflict_do_nothing(index_elements=[UserDocumentModel.kind, UserDocumentModel.key])
            .returning(UserDocumentModel)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            await self._session.rollback()
            raise RevisionMismatchError(f"{kind} {key!r} already exists")
        await self._session.commit()
        return _to_entity(row)

    async def replace(
        self,
        kind: DocumentKind,
        key: str,
        body: dict[str, Any],
        schema_version: int,
        expected_revision: int,
    ) -> UserDocument:
        """Update only if the stored revision still equals ``expected_revision``."""
        stmt = (
            update(UserDocumentModel)
            .where(
                UserDocumentModel.kind == kind,
                UserDocumentModel.key == key,
                UserDocumentModel.revision == expected_revision,
            )
            .values(
                body=body,
                schema_version=schema_version,
                revision=UserDocumentModel.revision + 1,
                updated_at=func.now(),
            )
            .returning(UserDocumentModel)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            await self._session.rollback()
            raise RevisionMismatchError(f"{kind} {key!r} is not at revision {expected_revision}")
        await self._session.commit()
        return _to_entity(row)
