"""Evaluation market data (ADR-014 §7): every read at one data revision, point in time.

Each decision gets its own :class:`PointInTimeSource`, so the screen sees only
what the decision could. Forward returns are read from a source bound to the
exit session: entry and exit closes then share one adjustment, and a split
between them cannot fake a return. The benchmark, the sessions and the
provenance come from the same revision.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.ports.trading_calendar import TradingCalendar
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.universe import reference_universe
from momentum25.domain.value_objects.results import Ranking, StockScore
from momentum25.infrastructure.persistence.history import VERSIONED
from momentum25.infrastructure.persistence.point_in_time import (
    PointInTimeIndicatorPipeline,
    PointInTimeOHLCVRepository,
    PointInTimeSecurityRepository,
    PointInTimeSource,
    visible,
)

# Bars read back from the exit to find the entry close. Covers the horizon plus
# sessions a halted name did not trade.
_EXIT_LOOKBACK_SLACK = 60


class PointInTimeMarket:
    """:class:`EvaluationMarket` at data revision ``revision``."""

    def __init__(
        self, session: AsyncSession, revision: int, calendar: TradingCalendar, horizon: int
    ) -> None:
        """Bind to a session, a revision, the trading calendar and the forward horizon."""
        self._session = session
        self._revision = revision
        self._calendar = calendar
        self._horizon = horizon
        self._engine = StrategyEngine(
            engines=engine_registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
        )

    async def sessions(self) -> list[date]:
        """Trading sessions from the first to the last stored bar."""
        bars = visible("ohlcv_daily", self._revision)
        first, last = (
            await self._session.execute(select(func.min(bars.c.date), func.max(bars.c.date)))
        ).one()
        return [] if first is None else self._calendar.sessions_between(first, last)

    async def screen(
        self, strategy: Strategy, decision: date
    ) -> tuple[list[StockScore], list[Ranking], dict[int, str]]:
        """Score and rank the decision's universe with the live strategy engine."""
        source = PointInTimeSource(self._session, decision, self._revision)
        universe = reference_universe(
            await PointInTimeSecurityRepository(source).list_all(), decision
        )
        screening = HistoricalScreeningUseCase(
            security_repo=None,
            ohlcv_repo=PointInTimeOHLCVRepository(source),
            screening_run_repo=None,
            strategy_repo=None,
            indicator_pipeline=PointInTimeIndicatorPipeline(self._session, source),
            strategy_engine=self._engine,
            calendar=self._calendar,
        )
        scores, rankings, _ = await screening.screen(strategy, decision, universe)
        return scores, rankings, {s.id: str(s.symbol) for s in universe if s.id is not None}

    async def forward_excess(
        self, security_ids: list[int], decision: date, exit_on: date, benchmark: str
    ) -> dict[int, float]:
        """Each name's return from the decision close to the exit, less the benchmark's."""
        bench_entry = await self._close(benchmark, decision)
        bench_exit = await self._close(benchmark, exit_on)
        if bench_entry is None or bench_exit is None or bench_entry <= 0:
            return {}
        bench = bench_exit / bench_entry - 1
        source = PointInTimeSource(self._session, exit_on, self._revision)
        excess: dict[int, float] = {}
        for security_id in security_ids:
            bars = await source.bars(security_id, exit_on, self._horizon + _EXIT_LOOKBACK_SLACK)
            # Point-in-time bars always carry adj_close; the decision saw the last entry.
            entry = [b.adj_close for b in bars if b.date <= decision and b.adj_close]
            later = [b.adj_close for b in bars if b.date > decision and b.adj_close]
            if not entry or entry[-1] <= 0:
                continue
            last = later[-1] if later else entry[-1]
            excess[security_id] = float(last / entry[-1] - 1 - bench)
        return excess

    async def _close(self, code: str, on: date) -> Decimal | None:
        b = visible("benchmark_index_daily", self._revision)
        return await self._session.scalar(
            select(b.c.close)
            .where(b.c.index_code == code, b.c.date <= on)
            .order_by(b.c.date.desc())
            .limit(1)
        )

    async def benchmark_path(self, code: str, start: date, end: date) -> list[Decimal]:
        """The benchmark's closes from ``start`` to ``end``."""
        b = visible("benchmark_index_daily", self._revision)
        rows = await self._session.scalars(
            select(b.c.close)
            .where(b.c.index_code == code, b.c.date >= start, b.c.date <= end)
            .order_by(b.c.date)
        )
        return list(rows)

    async def incomplete_months(self, start: date, end: date) -> list[str]:
        """Months (``YYYY-MM``) with any ``reconstructed`` input row."""
        months = []
        for table, (described, _) in VERSIONED.items():
            t = visible(table, self._revision)
            if described is None:  # securities: the listing and delisting dates
                columns = [t.c.listing_date, t.c.delisting_date]
            else:
                columns = [t.c[described]]
            for column in columns:
                months.append(
                    select(func.to_char(column, literal("YYYY-MM")).label("month")).where(
                        t.c.provenance == "reconstructed", column >= start, column <= end
                    )
                )
        found = union_all(*months).subquery()
        rows = await self._session.scalars(select(found.c.month).distinct().order_by(found.c.month))
        return list(rows)
