"""Security repository — instrument master persistence."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, case, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.security import Security
from momentum25.domain.research.period_correct_resolution import SymbolInterval
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.models import SecurityModel


def _to_domain(row: SecurityModel) -> Security:
    """Map an ORM row to a domain :class:`Security`."""
    return Security(
        id=row.id,
        symbol=Symbol(row.symbol),
        name=row.name,
        isin=row.isin,
        sector=row.sector,
        industry=row.industry,
        exchange=row.exchange,
        listing_date=row.listing_date,
        is_active=row.is_active,
        tenant_id=row.tenant_id,
    )


class SqlSecurityRepository:
    """Async SQLAlchemy implementation of :class:`SecurityRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def upsert_many(self, securities: list[Security]) -> None:
        """Insert or update securities by symbol."""
        if not securities:
            return
        rows = [
            {
                "symbol": str(s.symbol),
                "name": s.name,
                "isin": s.isin,
                "sector": s.sector,
                "industry": s.industry,
                "exchange": s.exchange,
                "listing_date": s.listing_date,
                "is_active": s.is_active,
                "tenant_id": s.tenant_id,
            }
            for s in securities
        ]
        stmt = insert(SecurityModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[SecurityModel.symbol],
            set_={
                "name": stmt.excluded.name,
                "isin": stmt.excluded.isin,
                "sector": stmt.excluded.sector,
                "industry": stmt.excluded.industry,
                # COALESCE, not a blind overwrite: callers that don't know a
                # security's listing date (e.g. a bare placeholder built from
                # a symbol alone) must never clobber an already-known one.
                "listing_date": func.coalesce(
                    stmt.excluded.listing_date, SecurityModel.listing_date
                ),
                "is_active": stmt.excluded.is_active,
            },
        )
        await self._session.execute(stmt)

    async def list_active(self) -> list[Security]:
        """Return all active securities."""
        result = await self._session.execute(
            select(SecurityModel).where(SecurityModel.is_active.is_(True))
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def list_all(self) -> list[Security]:
        """Return every security, active *and* inactive.

        Used by the RP-012 legacy backfill so that historical/ghost securities
        (delisted, renamed-away, merged) remain resolvable: a legacy bar printed
        under an old ticker must attach to its own historical security row, not
        collapse onto whichever active successor currently holds that identity.
        Filtering to ``is_active`` here is exactly what caused chain-member bars
        to be misattributed to their active successor.
        """
        result = await self._session.execute(select(SecurityModel))
        return [_to_domain(row) for row in result.scalars().all()]

    async def rename_chain_intervals(self) -> dict[str, list[SymbolInterval]]:
        """Return ``symbol -> trading intervals`` for every ISIN-shared rename chain.

        A rename chain is a set of ≥2 securities sharing one ISIN (the corporate
        identity is preserved across a ticker change). Each member contributes
        its ``[listing_date, delisting_date]`` interval keyed by *its own* symbol,
        so :func:`resolve_period_correct` can attribute a period-correct legacy
        ticker to the security that actually held it on the bar's session date.

        Only chain members participate: 1:1-ISIN securities (the vast majority)
        are resolved by the existing ISIN-first / symbol-fallback path and are
        deliberately excluded here so their behaviour is unchanged.
        """
        result = await self._session.execute(
            text(
                """
                SELECT s.symbol, s.id, s.listing_date, s.delisting_date
                FROM securities s
                JOIN (
                    SELECT isin FROM securities
                    WHERE isin IS NOT NULL GROUP BY isin HAVING count(*) > 1
                ) c ON c.isin = s.isin
                WHERE s.listing_date IS NOT NULL
                ORDER BY s.symbol, s.listing_date
                """
            )
        )
        intervals: dict[str, list[SymbolInterval]] = {}
        for symbol, sec_id, listing, delisting in result.all():
            intervals.setdefault(symbol.upper(), []).append(
                SymbolInterval(security_id=sec_id, start=listing, end=delisting)
            )
        return intervals

    async def deactivate_symbols(self, symbols: list[str]) -> int:
        """Mark the given symbols inactive; touches only ``is_active``.

        Deliberately narrower than :meth:`upsert_many`: reconciling
        delisted/merged/renamed symbols out of the active set must not risk
        clobbering an existing security's real name/isin/sector with a bare
        placeholder just because the provider no longer lists it (a delisted
        company's last-known name is still worth keeping).
        """
        if not symbols:
            return 0
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(SecurityModel)
                .where(SecurityModel.symbol.in_(symbols))
                .values(is_active=False)
            ),
        )
        return result.rowcount or 0

    async def set_exchanges(self, exchange_by_symbol: dict[str, str]) -> int:
        """Set the listing ``exchange`` for the given symbols. Returns rows updated.

        Deliberately a separate statement rather than a field in
        :meth:`upsert_many`'s conflict update: every other caller constructs
        ``Security`` with the ``"NSE"`` default because it does not *know* the
        exchange, so including it in the daily upsert would demote every
        cross-listed security back to ``NSE`` on the next screening run. The
        cross-listing reconciliation is the single writer of this column.
        """
        updated = 0
        for symbol, exchange in exchange_by_symbol.items():
            result = cast(
                CursorResult[Any],
                await self._session.execute(
                    update(SecurityModel)
                    .where(SecurityModel.symbol == symbol.upper())
                    .values(exchange=exchange)
                ),
            )
            updated += result.rowcount or 0
        return updated

    async def backfill_isins(self, isin_by_security_id: dict[int, str]) -> int:
        """Populate ``isin`` for the given securities, only where it is NULL.

        Deliberately fill-only (``WHERE isin IS NULL``): this backfill recovers
        the ISIN of historical/inactive rows the ingestion never captured, and
        must never overwrite an ISIN already present. Returns the row count
        actually updated.
        """
        updated = 0
        for security_id, isin in isin_by_security_id.items():
            result = cast(
                CursorResult[Any],
                await self._session.execute(
                    update(SecurityModel)
                    .where(
                        SecurityModel.id == security_id,
                        SecurityModel.isin.is_(None),
                    )
                    .values(isin=isin)
                ),
            )
            updated += result.rowcount or 0
        return updated

    async def get(self, security_id: int) -> Security | None:
        """Return a security by id, or ``None``."""
        row = await self._session.get(SecurityModel, security_id)
        return _to_domain(row) if row else None

    async def get_by_symbol(self, symbol: str) -> Security | None:
        """Return a security by symbol, or ``None``."""
        result = await self._session.execute(
            select(SecurityModel).where(SecurityModel.symbol == symbol.upper())
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row else None

    async def search(self, query: str, limit: int) -> list[Security]:
        """Return active securities matching *query* on symbol or name.

        Ordered so a typeahead surfaces the obvious answer first: exact symbol,
        then symbol prefix, then anything else containing the term. Ties break on
        symbol so the result is deterministic for a given query.
        """
        term = query.strip().upper()
        if not term:
            return []
        like = f"%{term}%"
        rank = case(
            (SecurityModel.symbol == term, 0),
            (SecurityModel.symbol.like(f"{term}%"), 1),
            else_=2,
        )
        result = await self._session.execute(
            select(SecurityModel)
            .where(
                SecurityModel.is_active.is_(True),
                or_(
                    SecurityModel.symbol.like(like),
                    func.upper(SecurityModel.name).like(like),
                ),
            )
            .order_by(rank, SecurityModel.symbol)
            .limit(limit)
        )
        return [_to_domain(row) for row in result.scalars()]
