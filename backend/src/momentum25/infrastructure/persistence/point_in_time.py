"""Point-in-time market data (ADR-014 §7): inputs exactly as one decision saw them.

A :class:`PointInTimeSource` is bound to a decision session D and a data
revision R (the manifest's high-water mark). It serves:

- bars dated on or before D, as stored at revision R;
- adjustment factors computed from the corporate actions stored at R with an
  ex-date on or before D, never from the stored cumulative ``adj_factor``
  (which knows every later split);
- the universe listed by D and not delisted by D, from ``securities`` at R,
  never from ``is_active``.

Any read past D raises :class:`LookAheadError`. The adapters below give the
historical screening path the same interfaces it uses live, so evaluation runs
the real ``StrategyEngine`` on point-in-time inputs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Subquery, Table, select, text, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import (
    OHLCVBar,
    OHLCVSeries,
    compute_adjustment_factors,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.errors import LookAheadError
from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.history import SEQUENCE
from momentum25.infrastructure.persistence.models import HISTORY_TABLES, Base
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


async def current_revision(session: AsyncSession) -> int:
    """The highest data revision stored so far (0 before any versioned write)."""
    row = (await session.execute(text(f"SELECT last_value, is_called FROM {SEQUENCE}"))).one()
    return int(row.last_value) if row.is_called else 0


def visible(table_name: str, revision: int) -> Subquery:
    """Every row version of ``table_name`` as it stood at ``revision``.

    A version is visible when it was stored at or before the revision and not
    yet superseded: a current row, or a history row superseded later.
    """
    current: Table = Base.metadata.tables[table_name]
    history = HISTORY_TABLES[table_name]
    columns = [c.name for c in current.columns]
    return union_all(
        select(*(current.c[n] for n in columns)).where(current.c.revision_id <= revision),
        select(*(history.c[n] for n in columns)).where(
            history.c.revision_id <= revision, history.c.superseded_revision > revision
        ),
    ).subquery(f"{table_name}_at")


class PointInTimeSource:
    """Market data as decision session ``decision`` saw it, at data ``revision``."""

    def __init__(self, session: AsyncSession, decision: date, revision: int) -> None:
        """Bind to one decision and one data revision."""
        self._session = session
        self.decision = decision
        self.revision = revision
        self._ids: dict[str, int] | None = None

    def guard(self, as_of: date) -> None:
        """Refuse any read dated after the decision session."""
        if as_of > self.decision:
            raise LookAheadError(
                f"Read as of {as_of} after the decision session {self.decision}"
            )

    async def universe(self) -> list[Security]:
        """Securities listed on or before the decision and not delisted by then."""
        s = visible("securities", self.revision)
        rows = (
            await self._session.execute(
                select(s)
                .where(
                    (s.c.listing_date.is_(None)) | (s.c.listing_date <= self.decision),
                    (s.c.delisting_date.is_(None)) | (s.c.delisting_date > self.decision),
                )
                .order_by(s.c.symbol)
            )
        ).all()
        return [
            Security(
                symbol=Symbol(row.symbol),
                name=row.name,
                id=row.id,
                isin=row.isin,
                sector=row.sector,
                industry=row.industry,
                exchange=row.exchange,
                listing_date=row.listing_date,
                is_active=True,  # listed at the decision; today's flag is never read
                tenant_id=row.tenant_id,
            )
            for row in rows
        ]

    async def security_id(self, symbol: str) -> int | None:
        """Return the id of a symbol in the decision's universe."""
        if self._ids is None:
            self._ids = {str(s.symbol): s.id for s in await self.universe() if s.id is not None}
        return self._ids.get(symbol)

    async def bars(self, security_id: int, as_of: date, limit: int) -> list[OHLCVBar]:
        """The last ``limit`` bars dated on or before ``as_of``, adjusted as of the decision."""
        self.guard(as_of)
        b = visible("ohlcv_daily", self.revision)
        rows = (
            await self._session.execute(
                select(b)
                .where(b.c.security_id == security_id, b.c.date <= as_of)
                .order_by(b.c.date.desc())
                .limit(limit)
            )
        ).all()
        rows = list(reversed(rows))
        if any(row.date > self.decision for row in rows):  # the query cannot, but prove it
            raise LookAheadError(f"Bar after {self.decision} for security {security_id}")
        factors = compute_adjustment_factors(
            [row.date for row in rows], await self._actions(security_id)
        )
        return [
            OHLCVBar(
                date=row.date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                prev_close=row.prev_close,
                turnover_value=row.turnover_value,
                adj_factor=factors[row.date],
                adj_close=(row.close * factors[row.date]).quantize(Decimal("0.0001")),
            )
            for row in rows
        ]

    async def _actions(self, security_id: int) -> list[RawCorporateAction]:
        """Corporate actions known at the revision with an ex-date by the decision."""
        a = visible("corporate_actions", self.revision)
        rows = (
            await self._session.execute(
                select(a).where(a.c.security_id == security_id, a.c.ex_date <= self.decision)
            )
        ).all()
        return [
            RawCorporateAction(
                symbol="",
                ex_date=row.ex_date,
                action_type=row.type,
                ratio=row.ratio,
                raw_subject="",
            )
            for row in rows
        ]


class PointInTimeSecurityRepository:
    """The security reads historical screening makes, answered as of the decision."""

    def __init__(self, source: PointInTimeSource) -> None:
        """Bind to a point-in-time source."""
        self._source = source

    async def list_active(self) -> list[Security]:
        """The universe at the decision (listed, not delisted), not today's active list."""
        return await self._source.universe()


class PointInTimeOHLCVRepository:
    """The bar reads historical screening and RS ratings make, as of the decision."""

    def __init__(self, source: PointInTimeSource) -> None:
        """Bind to a point-in-time source."""
        self._source = source

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        """Bars as the decision saw them; raises if ``as_of`` is after it."""
        bars = await self._source.bars(security_id, as_of, lookback_days)
        return OHLCVSeries(security_id=security_id, bars=tuple(bars))


class PointInTimeIndicatorPipeline(IndicatorPipelineImpl):
    """The live indicator formulas, fed with point-in-time bars."""

    def __init__(self, session: AsyncSession, source: PointInTimeSource) -> None:
        """Bind to the session and a point-in-time source."""
        super().__init__(session)
        self._source = source

    async def _fetch_bars(
        self, symbol: str, reference_date: date, min_bars: int
    ) -> list[Any] | None:
        self._source.guard(reference_date)
        security_id = await self._source.security_id(symbol)
        if security_id is None:
            return None
        bars = await self._source.bars(security_id, reference_date, min_bars)
        return bars or None
