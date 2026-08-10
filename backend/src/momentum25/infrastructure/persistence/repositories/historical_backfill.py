"""Repositories for the RP-012 / RP-014 legacy backfills.

Three cohesive persistence adapters:

* :class:`SqlLegacyOHLCVRepository` — staging-table bars (``legacy_ohlcv_daily``
  for NSE legacy archive prints, ``bse_legacy_ohlcv_daily`` for BSE's pre-UDiFF
  prints), kept distinct from the live ``ohlcv_daily`` so the two sources
  coexist for Gate 4a reconciliation without corrupting production data. The
  model class is a constructor argument: the NSE and BSE staging tables share
  the identical raw-bar shape, so one repository serves both with zero
  duplicated logic.
* :class:`SqlHistoricalUniverseRepository` — insert-only writes to the immutable
  ``historical_universe`` and membership reads for Gate 4d calibration;
* :class:`SqlValidationGapLogRepository` — insert-only C1/C2 validation-gap logs;
* :class:`SqlBSEScripJunctionRepository` — insert-only writes to the learned
  BSE ``SC_CODE`` → ISIN junction and identity reads for RP-014 resolution.

All writes are idempotent (``ON CONFLICT DO NOTHING`` on natural keys) so a
re-run of a partially-completed backfill never raises against the immutability
trigger or a unique constraint.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, bindparam, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.research.validation_gaps import (
    InferredActionEvent,
    SurvivorshipGapEvent,
)
from momentum25.domain.value_objects.results import UniverseMembership
from momentum25.infrastructure.persistence.models import (
    BSELegacyOHLCVDailyModel,
    BSEScripJunctionModel,
    CorporateActionInferenceLogModel,
    HistoricalUniverseModel,
    LegacyOHLCVDailyModel,
    OHLCVDailyModel,
    SurvivorshipGapEventModel,
)

_LegacyModel = LegacyOHLCVDailyModel | BSELegacyOHLCVDailyModel


def _bar_from_row(row: _LegacyModel | OHLCVDailyModel) -> OHLCVBar:
    """Map a persisted OHLCV row to the domain bar."""
    return OHLCVBar(
        date=row.date,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
        adj_close=row.adj_close,
        prev_close=row.prev_close,
        turnover_value=row.turnover_value,
    )


class SqlLegacyOHLCVRepository:
    """Persistence for legacy-sourced bars on a staging table.

    ``model_cls`` selects the staging table: ``LegacyOHLCVDailyModel`` (NSE
    legacy archive) by default, ``BSELegacyOHLCVDailyModel`` for RP-014's
    BSE pre-UDiFF range. Both tables share the identical raw-bar shape.
    """

    def __init__(
        self,
        session: AsyncSession,
        model_cls: type[_LegacyModel] = LegacyOHLCVDailyModel,
    ) -> None:
        """Bind the repository to a unit-of-work session and staging model."""
        self._session = session
        self._model: type[_LegacyModel] = model_cls

    async def upsert_bars(self, security_id: int, bars: list[OHLCVBar]) -> int:
        """Insert or update legacy bars for a security; return rows written."""
        if not bars:
            return 0
        rows = [
            {
                "security_id": security_id,
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "prev_close": b.prev_close,
                "turnover_value": b.turnover_value,
            }
            for b in bars
        ]
        stmt = insert(self._model).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[self._model.security_id, self._model.date],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                # Re-derive from the incoming raw close and the *stored*
                # adj_factor, never from an incoming adj_close. Providers do
                # not report an adjusted close, so re-ingesting a bar would
                # otherwise wipe the adj_close that update_adjustment_factors
                # wrote and leave the two columns describing different prices.
                # Keeps ``adj_close == close * adj_factor`` true after any
                # ingestion, matching the live ``ohlcv_daily`` upsert.
                "adj_close": stmt.excluded.close
                * cast("Table", self._model.__table__).c.adj_factor,
                "prev_close": stmt.excluded.prev_close,
                "turnover_value": stmt.excluded.turnover_value,
            },
        )
        await self._session.execute(stmt)
        return len(rows)

    async def upsert_day(self, items: list[tuple[int, OHLCVBar]]) -> int:
        """Bulk insert/update one trading day's legacy bars in a single statement.

        ``items`` is ``(security_id, bar)`` for every symbol on the day. This is
        the hot path for the ~4,000-7,000-day backfills: one INSERT …
        ON CONFLICT per day rather than one per bar.
        """
        if not items:
            return 0
        rows = [
            {
                "security_id": security_id,
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "prev_close": b.prev_close,
                "turnover_value": b.turnover_value,
            }
            for security_id, b in items
        ]
        stmt = insert(self._model).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[self._model.security_id, self._model.date],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                # Re-derive from the incoming raw close and the *stored*
                # adj_factor, never from an incoming adj_close. Providers do
                # not report an adjusted close, so re-ingesting a bar would
                # otherwise wipe the adj_close that update_adjustment_factors
                # wrote and leave the two columns describing different prices.
                # Keeps ``adj_close == close * adj_factor`` true after any
                # ingestion, matching the live ``ohlcv_daily`` upsert.
                "adj_close": stmt.excluded.close
                * cast("Table", self._model.__table__).c.adj_factor,
                "prev_close": stmt.excluded.prev_close,
                "turnover_value": stmt.excluded.turnover_value,
            },
        )
        await self._session.execute(stmt)
        return len(rows)

    async def bars_by_security_on(self, on_date: date) -> dict[int, OHLCVBar]:
        """Return every legacy bar on ``on_date`` keyed by ``security_id``."""
        result = await self._session.execute(
            select(self._model).where(self._model.date == on_date)
        )
        rows = cast("list[_LegacyModel]", result.scalars().all())
        return {row.security_id: _bar_from_row(row) for row in rows}

    async def trailing_bars(
        self, security_id: int, as_of: date, limit: int
    ) -> list[OHLCVBar]:
        """Return up to ``limit`` legacy bars on or before ``as_of``, ascending by date."""
        result = await self._session.execute(
            select(self._model)
            .where(
                self._model.security_id == security_id,
                self._model.date <= as_of,
            )
            .order_by(self._model.date.desc())
            .limit(limit)
        )
        rows = cast("list[_LegacyModel]", result.scalars().all())
        return [_bar_from_row(row) for row in reversed(rows)]

    async def distinct_security_ids(self, start: date, end: date) -> list[int]:
        """Return every ``security_id`` with a legacy bar in ``[start, end]``, ascending."""
        result = await self._session.execute(
            select(self._model.security_id)
            .where(self._model.date >= start, self._model.date <= end)
            .distinct()
            .order_by(self._model.security_id)
        )
        return list(result.scalars().all())

    async def bars_for_security(
        self, security_id: int, start: date, end: date
    ) -> list[OHLCVBar]:
        """Return a security's full legacy series in ``[start, end]``, ascending by date."""
        result = await self._session.execute(
            select(self._model)
            .where(
                self._model.security_id == security_id,
                self._model.date >= start,
                self._model.date <= end,
            )
            .order_by(self._model.date)
        )
        rows = cast("list[_LegacyModel]", result.scalars().all())
        return [_bar_from_row(row) for row in rows]

    async def prior_session_count(self, security_id: int, before: date) -> int:
        """Count legacy sessions strictly before ``before`` for a security."""
        result = await self._session.execute(
            select(func.count())
            .select_from(self._model)
            .where(
                self._model.security_id == security_id,
                self._model.date < before,
            )
        )
        return int(result.scalar_one())

    async def update_adjustment_factors(
        self, security_id: int, factors: dict[date, Decimal]
    ) -> int:
        """Persist a computed backward-adjustment factor per legacy bar date.

        Identical semantics to the live ``SqlOHLCVRepository`` method:
        ``adj_close`` is derived from the stored raw ``close`` in the same
        UPDATE (``close * factor``), so the two columns stay consistent and no
        read-modify-write race is possible.
        """
        if not factors:
            return 0
        table = cast("Table", self._model.__table__)
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

    async def distinct_dates(self, start: date, end: date) -> list[date]:
        """Return every distinct legacy bar date in ``[start, end]``, ascending."""
        result = await self._session.execute(
            select(self._model.date)
            .where(self._model.date >= start, self._model.date <= end)
            .distinct()
            .order_by(self._model.date)
        )
        return list(result.scalars().all())


class SqlHistoricalUniverseRepository:
    """Insert-only persistence for the immutable ``historical_universe``."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def insert_memberships(
        self, as_of: date, memberships: list[UniverseMembership]
    ) -> int:
        """Insert point-in-time eligibility rows; existing rows are left untouched.

        ``ON CONFLICT DO NOTHING`` keeps a re-run idempotent and never attempts
        an UPDATE (which the immutability trigger would reject).
        """
        if not memberships:
            return 0
        rows = [
            {
                "as_of_date": as_of,
                "security_id": m.security_id,
                "eligible": m.eligible,
                "reason": m.reason,
            }
            for m in memberships
        ]
        stmt = insert(HistoricalUniverseModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[HistoricalUniverseModel.as_of_date, HistoricalUniverseModel.security_id]
        )
        await self._session.execute(stmt)
        return len(rows)

    async def insert_dated_memberships(
        self, rows_in: list[tuple[date, UniverseMembership]]
    ) -> int:
        """Bulk-insert ``(as_of_date, membership)`` rows spanning many dates; idempotent."""
        if not rows_in:
            return 0
        rows = [
            {
                "as_of_date": as_of,
                "security_id": m.security_id,
                "eligible": m.eligible,
                "reason": m.reason,
            }
            for as_of, m in rows_in
        ]
        stmt = insert(HistoricalUniverseModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[HistoricalUniverseModel.as_of_date, HistoricalUniverseModel.security_id]
        )
        await self._session.execute(stmt)
        return len(rows)

    async def eligible_members(self, as_of: date) -> set[int]:
        """Return the set of ``security_id`` marked eligible on ``as_of``."""
        result = await self._session.execute(
            select(HistoricalUniverseModel.security_id).where(
                HistoricalUniverseModel.as_of_date == as_of,
                HistoricalUniverseModel.eligible.is_(True),
            )
        )
        return set(result.scalars().all())

    async def member_count(self, as_of: date, eligible_only: bool = True) -> int:
        """Return the number of (eligible) members recorded on ``as_of``."""
        stmt = select(func.count()).select_from(HistoricalUniverseModel).where(
            HistoricalUniverseModel.as_of_date == as_of
        )
        if eligible_only:
            stmt = stmt.where(HistoricalUniverseModel.eligible.is_(True))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())


class SqlValidationGapLogRepository:
    """Insert-only persistence for C1/C2 validation-gap logs."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def log_inferred_actions(
        self, security_id: int, events: list[InferredActionEvent]
    ) -> int:
        """Insert PREVCLOSE-inferred corporate-action events (C1); idempotent."""
        return await self.log_inferred_actions_bulk([(security_id, e) for e in events])

    async def log_inferred_actions_bulk(
        self, items: list[tuple[int, InferredActionEvent]]
    ) -> int:
        """Bulk-insert C1 events for many securities in one statement; idempotent."""
        if not items:
            return 0
        rows = [
            {
                "security_id": security_id,
                "session_date": e.session_date,
                "prev_close_reported": e.prev_close_reported,
                "prior_session_close": e.prior_session_close,
                "inferred_factor": e.inferred_factor,
                "flagged": e.flagged,
            }
            for security_id, e in items
        ]
        stmt = insert(CorporateActionInferenceLogModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["security_id", "session_date"])
        await self._session.execute(stmt)
        return len(rows)

    async def log_gap_events(
        self, security_id: int, events: list[SurvivorshipGapEvent]
    ) -> int:
        """Insert survivorship/gap events (C2); idempotent."""
        return await self.log_gap_events_bulk([(security_id, e) for e in events])

    async def log_gap_events_bulk(
        self, items: list[tuple[int, SurvivorshipGapEvent]]
    ) -> int:
        """Bulk-insert C2 events for many securities in one statement; idempotent."""
        if not items:
            return 0
        rows = [
            {
                "security_id": security_id,
                "last_seen_date": e.last_seen_date,
                "detected_on_date": e.detected_on_date,
                "gap_sessions": e.gap_sessions,
            }
            for security_id, e in items
        ]
        stmt = insert(SurvivorshipGapEventModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["security_id", "last_seen_date", "detected_on_date"]
        )
        await self._session.execute(stmt)
        return len(rows)

    async def flagged_inference_count(self) -> int:
        """Return the number of flagged (out-of-band) inferred-action rows."""
        result = await self._session.execute(
            select(func.count())
            .select_from(CorporateActionInferenceLogModel)
            .where(CorporateActionInferenceLogModel.flagged.is_(True))
        )
        return int(result.scalar_one())

    async def gap_event_count(self) -> int:
        """Return the total number of recorded survivorship/gap events."""
        result = await self._session.execute(
            select(func.count()).select_from(SurvivorshipGapEventModel)
        )
        return int(result.scalar_one())


class SqlBSEScripJunctionRepository:
    """Insert-only persistence for the learned BSE ``SC_CODE`` → ISIN junction (RP-014)."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def insert_many(
        self, items: list[tuple[str, str, str, date]]
    ) -> int:
        """Insert ``(sc_code, isin, name, observed_on)`` rows; first observation wins.

        ``ON CONFLICT DO NOTHING`` on ``sc_code`` keeps a re-run idempotent and
        preserves the first session that disclosed each scrip's ISIN — the
        junction is immutable once learned, exactly like ``historical_universe``.
        Returns the number of rows actually inserted (``RETURNING`` counts only
        rows the statement really added, so the backfill summary measures the
        learned junction, not the rows offered to it).
        """
        if not items:
            return 0
        rows = [
            {"sc_code": sc, "isin": isin, "name": name, "observed_on": observed_on}
            for sc, isin, name, observed_on in items
        ]
        stmt = insert(BSEScripJunctionModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[BSEScripJunctionModel.sc_code]
        )
        returning = stmt.returning(BSEScripJunctionModel.sc_code)
        result = await self._session.execute(returning)
        return len(result.all())

    async def sc_code_to_isin(self) -> dict[str, str]:
        """Return the full learned junction as ``{sc_code: isin}``."""
        result = await self._session.execute(select(BSEScripJunctionModel))
        return {row.sc_code: row.isin for row in result.scalars().all()}
