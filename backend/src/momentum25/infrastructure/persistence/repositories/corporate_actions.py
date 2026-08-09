"""Corporate-action repository — persistence for splits/bonuses/rights.

Actions are upserted keyed on (security_id, ex_date, type) so re-fetching the
same disclosure window is idempotent (ADR-006 append-only intent: existing
rows are refreshed in place only because a corporate action's disclosed text
never legitimately changes after the fact -- there is no historical revision
to preserve, unlike screening results).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.infrastructure.persistence.models import CorporateActionModel


class SqlCorporateActionRepository:
    """Async SQLAlchemy implementation of :class:`CorporateActionRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def save_many(self, security_id: int, actions: list[RawCorporateAction]) -> int:
        """Insert or update corporate actions for a security; return rows written."""
        if not actions:
            return 0
        # NSE publishes the same (ex_date, type) more than once for a symbol
        # (e.g. two dividend legs on one ex-date). Postgres rejects a whole
        # multi-row ON CONFLICT statement containing duplicate conflict keys
        # ("cannot affect row a second time"), which previously failed the
        # entire security's refresh -- 2918 of 3235 securities never got their
        # adjustment factors written. Collapse duplicates here, last wins,
        # matching the upsert's own last-write-wins semantics.
        deduped: dict[tuple[object, str], dict[str, object]] = {}
        for a in actions:
            deduped[(a.ex_date, a.action_type)] = {
                "security_id": security_id,
                "ex_date": a.ex_date,
                "type": a.action_type,
                "ratio": a.ratio,
                "raw": {"subject": a.raw_subject, "symbol": a.symbol},
            }
        rows = list(deduped.values())
        stmt = insert(CorporateActionModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                CorporateActionModel.security_id,
                CorporateActionModel.ex_date,
                CorporateActionModel.type,
            ],
            set_={"ratio": stmt.excluded.ratio, "raw": stmt.excluded.raw},
        )
        await self._session.execute(stmt)
        return len(rows)

    async def list_for_security(self, security_id: int) -> list[RawCorporateAction]:
        """Return all persisted corporate actions for a security, ascending by ex_date."""
        result = await self._session.execute(
            select(CorporateActionModel)
            .where(CorporateActionModel.security_id == security_id)
            .order_by(CorporateActionModel.ex_date)
        )
        rows = result.scalars().all()
        return [
            RawCorporateAction(
                symbol=(r.raw or {}).get("symbol", "") if r.raw else "",
                ex_date=r.ex_date,
                action_type=r.type,
                ratio=r.ratio,
                raw_subject=(r.raw or {}).get("subject", "") if r.raw else "",
            )
            for r in rows
        ]
