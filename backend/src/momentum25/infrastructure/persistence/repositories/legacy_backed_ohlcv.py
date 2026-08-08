"""Read-only OHLCV repository backed by the legacy archive (``legacy_ohlcv_daily``).

Exposes the subset of the :class:`OHLCVRepository` read surface the historical
screening / forward-return code paths depend on (``get_series``,
``get_bars_after``), reading from the legacy staging table instead of the live
``ohlcv_daily``. This lets the *existing* screening/scoring pipeline and
``ForwardReturnsBackfill`` be pointed at pre-2019 legacy prices unchanged.

The legacy archive carries raw prints only (no adjustment columns), so
``adj_close`` is surfaced as ``None`` — the downstream forward-return code already
falls back to the raw ``close`` when ``adj_close`` is absent, matching the live
table (whose ``adj_factor`` is 1 / whose ``adj_close`` equals ``close`` until the
Phase 1 adjustment engine runs).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.infrastructure.persistence.models import LegacyOHLCVDailyModel


def _to_bar(row: LegacyOHLCVDailyModel) -> OHLCVBar:
    """Map a legacy ORM row to a domain :class:`OHLCVBar` (raw prints, no adj)."""
    return OHLCVBar(
        date=row.date,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
        adj_close=None,
        prev_close=row.prev_close,
        turnover_value=row.turnover_value,
    )


class LegacyBackedOHLCVRepository:
    """Async SQLAlchemy read adapter over ``legacy_ohlcv_daily``."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def get_series(
        self, security_id: int, lookback_days: int, as_of: date
    ) -> OHLCVSeries:
        """Return the ascending series up to ``as_of`` (most recent ``lookback_days``)."""
        result = await self._session.execute(
            select(LegacyOHLCVDailyModel)
            .where(
                LegacyOHLCVDailyModel.security_id == security_id,
                LegacyOHLCVDailyModel.date <= as_of,
            )
            .order_by(LegacyOHLCVDailyModel.date.desc())
            .limit(lookback_days)
        )
        rows = list(reversed(result.scalars().all()))
        return OHLCVSeries(security_id=security_id, bars=tuple(_to_bar(r) for r in rows))

    async def get_bars_after(
        self, security_id: int, after_date: date, limit: int
    ) -> list[OHLCVBar]:
        """Return up to ``limit`` ascending bars strictly after ``after_date``."""
        result = await self._session.execute(
            select(LegacyOHLCVDailyModel)
            .where(
                LegacyOHLCVDailyModel.security_id == security_id,
                LegacyOHLCVDailyModel.date > after_date,
            )
            .order_by(LegacyOHLCVDailyModel.date)
            .limit(limit)
        )
        return [_to_bar(r) for r in result.scalars().all()]
