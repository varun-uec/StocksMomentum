"""OHLCV repository — daily price series persistence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, bindparam, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.infrastructure.persistence.models import OHLCVDailyModel


class SqlOHLCVRepository:
    """Async SQLAlchemy implementation of :class:`OHLCVRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def upsert_bars(self, security_id: int, bars: list[OHLCVBar]) -> int:
        """Insert or update bars; return the number written."""
        if not bars:
            return 0
        return await self.upsert_bars_batch({security_id: bars})

    async def upsert_bars_batch(
        self, bars_by_security: dict[int, list[OHLCVBar]]
    ) -> int:
        """Insert or update bars for many securities in one statement.

        The re-ingest recovery path replays ~1,700 sessions of ~2,400 symbols;
        calling :meth:`upsert_bars` per (session, security) would be millions of
        round trips. This method flattens everything into a single ``INSERT …
        ON CONFLICT DO UPDATE`` statement with identical conflict semantics
        (``adj_close`` re-derived from the incoming raw close and the stored
        ``adj_factor``, never from the incoming ``adj_close``).
        """
        rows: list[dict[str, object]] = []
        for security_id, bars in bars_by_security.items():
            rows.extend(
                {
                    "security_id": security_id,
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "adj_close": b.adj_close,
                    "prev_close": b.prev_close,
                    "turnover_value": b.turnover_value,
                }
                for b in bars
            )
        if not rows:
            return 0
        stmt = insert(OHLCVDailyModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[OHLCVDailyModel.security_id, OHLCVDailyModel.date],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                # Re-derive from the incoming raw close and the *stored*
                # adj_factor rather than taking the incoming adj_close.
                #
                # Providers do not report an adjusted close, so every ingested
                # bar carries ``adj_close=None``. Writing that straight through
                # (the prior behaviour) wiped the adjusted close computed by
                # ``update_adjustment_factors`` on every re-ingestion of an
                # already-adjusted bar, while leaving ``adj_factor`` untouched —
                # leaving the two columns describing different prices. Forward
                # returns read ``adj_close`` (falling back to raw ``close``) and
                # the indicator pipeline reads ``adj_factor``, so a desynced row
                # made research and screening silently disagree about the same
                # split. Deriving it here keeps the invariant
                # ``adj_close == close * adj_factor`` true after any ingestion.
                "adj_close": stmt.excluded.close * OHLCVDailyModel.__table__.c.adj_factor,
                "prev_close": stmt.excluded.prev_close,
                "turnover_value": stmt.excluded.turnover_value,
            },
        )
        await self._session.execute(stmt)
        return len(rows)

    async def get_series(
        self, security_id: int, lookback_days: int, as_of: date
    ) -> OHLCVSeries:
        """Return the ascending price series up to ``as_of`` (most recent ``lookback_days``)."""
        result = await self._session.execute(
            select(OHLCVDailyModel)
            .where(
                OHLCVDailyModel.security_id == security_id,
                OHLCVDailyModel.date <= as_of,
            )
            .order_by(OHLCVDailyModel.date.desc())
            .limit(lookback_days)
        )
        rows = list(reversed(result.scalars().all()))
        bars = tuple(
            OHLCVBar(
                date=r.date,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
                adj_close=r.adj_close,
                prev_close=r.prev_close,
                turnover_value=r.turnover_value,
            )
            for r in rows
        )
        return OHLCVSeries(security_id=security_id, bars=bars)

    async def bars_by_security_on(self, on_date: date) -> dict[int, OHLCVBar]:
        """Return every current-provider bar on ``on_date`` keyed by ``security_id``.

        Read-only accessor used by RP-012 overlap reconciliation to join the live
        ``ohlcv_daily`` against the legacy staging table on ``(security_id, date)``.
        """
        result = await self._session.execute(
            select(OHLCVDailyModel).where(OHLCVDailyModel.date == on_date)
        )
        return {
            r.security_id: OHLCVBar(
                date=r.date,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
                adj_close=r.adj_close,
                prev_close=r.prev_close,
                turnover_value=r.turnover_value,
            )
            for r in result.scalars().all()
        }

    async def closes_between(
        self, start: date, end: date
    ) -> dict[int, list[tuple[date, Decimal]]]:
        """Return every close in ``[start, end]``, grouped by security, ascending by date."""
        result = await self._session.execute(
            select(
                OHLCVDailyModel.security_id,
                OHLCVDailyModel.date,
                OHLCVDailyModel.close,
            )
            .where(OHLCVDailyModel.date >= start, OHLCVDailyModel.date <= end)
            .order_by(OHLCVDailyModel.security_id, OHLCVDailyModel.date)
        )
        grouped: dict[int, list[tuple[date, Decimal]]] = {}
        for security_id, bar_date, close in result.all():
            grouped.setdefault(security_id, []).append((bar_date, close))
        return grouped

    async def latest_date(self) -> date | None:
        """Return the most recent stored bar date, or ``None``."""
        result = await self._session.execute(select(func.max(OHLCVDailyModel.date)))
        return result.scalar_one_or_none()

    async def list_distinct_dates(self, start: date, end: date) -> list[date]:
        """Return every distinct bar date in ``[start, end]``, ascending."""
        result = await self._session.execute(
            select(OHLCVDailyModel.date)
            .where(OHLCVDailyModel.date >= start, OHLCVDailyModel.date <= end)
            .distinct()
            .order_by(OHLCVDailyModel.date)
        )
        return list(result.scalars().all())

    async def get_bars_after(
        self, security_id: int, after_date: date, limit: int
    ) -> list[OHLCVBar]:
        """Return up to ``limit`` ascending bars strictly after ``after_date``."""
        result = await self._session.execute(
            select(OHLCVDailyModel)
            .where(
                OHLCVDailyModel.security_id == security_id,
                OHLCVDailyModel.date > after_date,
            )
            .order_by(OHLCVDailyModel.date)
            .limit(limit)
        )
        return [
            OHLCVBar(
                date=r.date,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
                adj_close=r.adj_close,
                prev_close=r.prev_close,
                turnover_value=r.turnover_value,
            )
            for r in result.scalars().all()
        ]

    async def update_adjustment_factors(
        self, security_id: int, factors: dict[date, Decimal]
    ) -> int:
        """Persist a computed backward-adjustment factor per bar date.

        ``adj_close`` is derived from the stored raw ``close`` in the same
        UPDATE (``close * factor``), so the two columns are always consistent
        and no read-modify-write race is possible.
        """
        if not factors:
            return 0
        # Uses the Core ``Table`` (not ``update(OHLCVDailyModel)``) so this is
        # a plain executemany-style bulk UPDATE, not subject to the ORM's
        # bulk-by-primary-key semantics (which require dict keys to match
        # column names exactly and reject additional WHERE criteria).
        table = cast(Table, OHLCVDailyModel.__table__)
        stmt = (
            update(table)
            .where(
                table.c.security_id == bindparam("sec_id"),
                table.c.date == bindparam("bar_date"),
            )
            .values(
                adj_factor=bindparam("factor"),
                adj_close=table.c.close * bindparam("factor"),
            )
        )
        params = [
            {"sec_id": security_id, "bar_date": d, "factor": factor}
            for d, factor in factors.items()
        ]
        await self._session.execute(stmt, params)
        return len(params)
