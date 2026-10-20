"""User-document use cases: read, and save with a precondition (ADR-013 §5)."""

from __future__ import annotations

from typing import Any

from momentum25.domain.entities.user_document import DocumentKind, UserDocument
from momentum25.domain.errors import NotFoundError, PreconditionRequiredError
from momentum25.domain.ports.repositories import UserDocumentRepository

# ponytail: one version per kind and no upgrade path yet. When v2 exists, add a
# pure `upgrade(kind, version, body)` applied on read, with a golden test per version.
SCHEMA_VERSION: dict[DocumentKind, int] = {"workspace": 1, "symbol_drawings": 1, "saved_screens": 1}


class GetUserDocument:
    """Return a stored document.

    A document that was never saved is not an error to the client: it reads
    as revision 0 with no body (ADR-013 §5), so a first page load is a 200.
    """

    def __init__(self, documents: UserDocumentRepository) -> None:
        """Wire the use case with its repository."""
        self._documents = documents

    async def execute(self, kind: DocumentKind, key: str) -> UserDocument:
        """Return the document, or raise :class:`NotFoundError` if it was never saved."""
        document = await self._documents.get(kind, key)
        if document is None:
            raise NotFoundError(f"No saved {kind} for {key!r}")
        return document

    async def find(self, kind: DocumentKind, key: str) -> UserDocument | None:
        """Return the document, or ``None`` if it was never saved (revision 0)."""
        return await self._documents.get(kind, key)


class SaveUserDocument:
    """Store a document only if the caller names the state it builds on."""

    def __init__(self, documents: UserDocumentRepository) -> None:
        """Wire the use case with its repository."""
        self._documents = documents

    async def execute(
        self,
        kind: DocumentKind,
        key: str,
        body: dict[str, Any],
        *,
        expected_revision: int | None,
        create_only: bool,
    ) -> UserDocument:
        """Create (``create_only``) or replace (``expected_revision``) the document.

        A save that names neither precondition is refused: the caller must say
        whether it creates a new document or edits a revision it has seen.
        ``If-Match`` revision 0 names the never-saved state, so it creates the
        document, and conflicts if another client created it first.
        """
        version = SCHEMA_VERSION[kind]
        if create_only or expected_revision == 0:
            return await self._documents.create(kind, key, body, version)
        if expected_revision is None:
            raise PreconditionRequiredError(
                "Send If-Match with the revision you edited, or If-None-Match: * to create."
            )
        return await self._documents.replace(kind, key, body, version, expected_revision)
