"""PostgreSQL ledger. Every query names the caller's tenant and owner; RLS applies it again."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from wickstreet.context import TenantContext
from wickstreet.portfolio.domain.model import Closing, ImportRecord, Statement, Transaction
from wickstreet.portfolio.infrastructure.tables import portfolio_import as i
from wickstreet.portfolio.infrastructure.tables import portfolio_txn as t


def fingerprint(x: Transaction) -> str:
    """One line's identity: folio, scheme, date, kind, amount, units and running balance."""
    parts = (x.folio, x.isin or x.scheme, x.day.isoformat(), x.kind, x.amount, x.units, x.balance)
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _closing_json(c: Closing) -> dict[str, Any]:
    return {
        k: (v.isoformat() if isinstance(v, date) else str(v) if isinstance(v, Decimal) else v)
        for k, v in asdict(c).items()
    }


def _dec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _closing(row: dict[str, Any]) -> Closing:
    dec = _dec
    return Closing(
        row["folio"],
        row["scheme"],
        row["isin"],
        row["amfi_code"],
        Decimal(row["units"]),
        dec(row["value"]),
        dec(row["nav"]),
        date.fromisoformat(row["valued_on"]) if row["valued_on"] else None,
        dec(row["cost"]),
    )


def _mine(table: Any, context: TenantContext) -> tuple[Any, ...]:
    return (table.c.tenant_id == context.tenant_id, table.c.owner_id == context.user_id)


class SqlLedger:
    """The ``Ledger`` port over a tenant-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the ledger to the unit of work's session."""
        self._session = session

    def _record(self, row: Any) -> ImportRecord:
        return ImportRecord(
            row.id,
            row.file_sha256,
            row.period_from,
            row.period_to,
            row.cas_type,
            row.added,
            row.duplicates,
            [_closing(c) for c in row.closings],
            row.created_at.isoformat(),
        )

    async def imports(self, context: TenantContext) -> list[ImportRecord]:
        """Every committed import, newest first."""
        rows = await self._session.execute(
            select(i).where(*_mine(i, context)).order_by(i.c.created_at.desc(), i.c.id)
        )
        return [self._record(r) for r in rows]

    async def find(self, context: TenantContext, file_sha256: str) -> ImportRecord | None:
        """The import of this exact file, if committed."""
        row = (
            await self._session.execute(
                select(i).where(*_mine(i, context), i.c.file_sha256 == file_sha256)
            )
        ).first()
        return self._record(row) if row else None

    async def commit(self, context: TenantContext, statement: Statement) -> ImportRecord:
        """Store the statement as one import; lines already held are skipped."""
        import_id = uuid4()
        owner = {"tenant_id": context.tenant_id, "owner_id": context.user_id}
        await self._session.execute(
            i.insert().values(
                id=import_id,
                file_sha256=statement.file_sha256,
                period_from=statement.period_from,
                period_to=statement.period_to,
                cas_type=statement.cas_type,
                added=0,
                duplicates=0,
                closings=[_closing_json(c) for c in statement.closings],
                **owner,
            )
        )
        rows = [
            {
                "id": uuid4(),
                "import_id": import_id,
                "fingerprint": fingerprint(x),
                **owner,
                **asdict(x),
            }
            for x in statement.transactions
        ]
        added = 0
        if rows:
            result: CursorResult[Any] = await self._session.execute(  # type: ignore[assignment]
                insert(t).values(rows).on_conflict_do_nothing(constraint="uq_portfolio_txn_line")
            )
            added = int(result.rowcount or 0)
        duplicates = len(rows) - added
        await self._session.execute(
            i.update().where(i.c.id == import_id).values(added=added, duplicates=duplicates)
        )
        found = await self.find(context, statement.file_sha256)
        assert found is not None
        return found

    async def undo(self, context: TenantContext, import_id: UUID) -> bool:
        """Remove one import; its transactions go with it (ON DELETE CASCADE)."""
        result: CursorResult[Any] = await self._session.execute(  # type: ignore[assignment]
            delete(i).where(*_mine(i, context), i.c.id == import_id)
        )
        return bool(result.rowcount)

    async def transactions(self, context: TenantContext) -> list[Transaction]:
        """Every transaction held, in date order."""
        columns = [t.c[name] for name in Transaction.__dataclass_fields__]
        rows = await self._session.execute(
            select(*columns).where(*_mine(t, context)).order_by(t.c.day, t.c.folio, t.c.id)
        )
        return [Transaction(*row) for row in rows]

    async def count(self, context: TenantContext) -> int:
        """How many transactions are held."""
        found = await self._session.scalar(
            select(func.count()).select_from(t).where(*_mine(t, context))
        )
        return int(found or 0)
