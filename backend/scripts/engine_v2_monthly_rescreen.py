"""Re-screen the in-sample monthly decisions under engine v2, then backfill forward returns.

Round 6 (owner authorisation 2026-10-21). Two steps, each idempotent and restartable:

``rescreen``  one NEW run per eligible month-end, made by the approved point-in-time
              path (``PointInTimeHistoricalScreening``) with the current engine
              (ENGINE_VERSION 2). Engine v1 runs are never read for write or changed.
              Completed runs are immutable, so the series is named in ``data_version``
              (``historical:<date>:pit:<manifest>:engine2-monthly``); ``stats`` carries
              ``engine_version``, ``indicator_version``, ``market_data_manifest``.
``backfill``  session-basis forward returns (R3-B-32) for those runs, one transaction
              per run. A horizon is written only when its exit session falls before the
              hold-out starts, so the sealed hold-out is never read. Existing rows of
              either basis are never rewritten.

Eligibility is the research window of ``EvaluationPolicy`` (ADR-014 §6): from the
warm-up to the last decision whose 120-session window closes before the hold-out.
Dates after that stay unscreened.

Usage: ``python scripts/engine_v2_monthly_rescreen.py plan|rescreen|backfill``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from monthly_forward_returns_backfill import (  # noqa: E402
    STRATEGY_NAME,
    WINDOW_END,
    WINDOW_START,
    month_end_targets,
    snap_to_trading_dates,
)
from sqlalchemy import func, select  # noqa: E402
from structlog import get_logger  # noqa: E402

from momentum25.application.use_cases.research.forward_returns_backfill import (  # noqa: E402
    DEFAULT_HORIZONS,
    ForwardReturnsBackfill,
)
from momentum25.domain.engine_version import (  # noqa: E402
    ENGINE_VERSION,
    INDICATOR_VERSION,
)
from momentum25.domain.entities.market_data import OHLCVBar  # noqa: E402
from momentum25.domain.research.strategy_evaluation import (  # noqa: E402
    EvaluationPolicy,
    exit_session,
    holdout_window,
    research_window,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl  # noqa: E402
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl  # noqa: E402
from momentum25.domain.strategy.bootstrap import register_builtin_engines  # noqa: E402
from momentum25.domain.strategy.engine_registry import engine_registry  # noqa: E402
from momentum25.domain.strategy.strategy_engine import StrategyEngine  # noqa: E402
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar  # noqa: E402
from momentum25.infrastructure.persistence.database import get_database  # noqa: E402
from momentum25.infrastructure.persistence.models import (  # noqa: E402
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    ScreeningRunModel,
)
from momentum25.infrastructure.persistence.point_in_time_screening import (  # noqa: E402
    PointInTimeHistoricalScreening,
)
from momentum25.infrastructure.persistence.repositories import (  # noqa: E402
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)

_logger = get_logger("engine_v2_monthly_rescreen")

SERIES = "engine2-monthly"
_MARK = f":{SERIES}"
_POLICY = EvaluationPolicy()


def horizons_before(
    sessions: list[date], run_date: date, holdout_start: date, horizons: tuple[int, ...]
) -> tuple[int, ...]:
    """The horizons whose exit session lies strictly before the hold-out starts."""
    out = []
    for h in horizons:
        exit_on = exit_session(sessions, run_date, h)
        if exit_on is not None and exit_on < holdout_start:
            out.append(h)
    return tuple(out)


class _BoundedOHLCV(SqlOHLCVRepository):
    """OHLCV reads that stop at ``cutoff``: the data end is the cutoff, never later."""

    def __init__(self, session: Any, cutoff: date) -> None:
        super().__init__(session)
        self._cutoff = cutoff

    async def latest_date(self) -> date | None:
        result = await self._session.execute(
            select(func.max(OHLCVDailyModel.date)).where(OHLCVDailyModel.date <= self._cutoff)
        )
        return result.scalar_one_or_none()

    async def get_bars_after(
        self, security_id: int, after_date: date, limit: int
    ) -> list[OHLCVBar]:
        """Bars after ``after_date`` up to the cutoff; the query never reads later rows."""
        rows = await self._session.scalars(
            select(OHLCVDailyModel)
            .where(
                OHLCVDailyModel.security_id == security_id,
                OHLCVDailyModel.date > after_date,
                OHLCVDailyModel.date <= self._cutoff,
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
                adj_factor=r.adj_factor,
                prev_close=r.prev_close,
                turnover_value=r.turnover_value,
            )
            for r in rows.all()
        ]


class _BoundedBenchmark:
    """Benchmark closes up to ``cutoff`` only; the query never touches later rows."""

    def __init__(self, session: Any, cutoff: date) -> None:
        self._session = session
        self._cutoff = cutoff

    async def get_close_series(self, index_code: str) -> dict[date, Decimal]:
        rows = await self._session.execute(
            select(BenchmarkIndexDailyModel.date, BenchmarkIndexDailyModel.close).where(
                BenchmarkIndexDailyModel.index_code == index_code,
                BenchmarkIndexDailyModel.date <= self._cutoff,
            )
        )
        return {r.date: r.close for r in rows.all()}


async def _context() -> dict[str, Any]:
    """Sessions, the research window, the hold-out start and the eligible month-ends."""
    async with get_database().session() as session:
        first, last = (
            await session.execute(
                select(func.min(OHLCVDailyModel.date), func.max(OHLCVDailyModel.date))
            )
        ).one()
        # Only dates up to the research window's end are needed to snap month-ends.
        bar_dates = list(
            (
                await session.scalars(
                    select(OHLCVDailyModel.date)
                    .where(OHLCVDailyModel.date >= WINDOW_START, OHLCVDailyModel.date <= WINDOW_END)
                    .distinct()
                    .order_by(OHLCVDailyModel.date)
                )
            ).all()
        )
    sessions = get_nse_trading_calendar().sessions_between(first, last)
    research = research_window(sessions, _POLICY)
    holdout = holdout_window(sessions, _POLICY)
    if research is None or holdout is None:
        raise SystemExit("no research window or hold-out: stop")
    grid = snap_to_trading_dates(month_end_targets(WINDOW_START, WINDOW_END), bar_dates)
    eligible = [d for d in grid if research[0] <= d <= research[1]]
    return {
        "sessions": sessions,
        "research": research,
        "holdout": holdout,
        "grid": grid,
        "eligible": eligible,
    }


async def _series_runs(session: Any, strategy_id: int) -> list[ScreeningRunModel]:
    rows = await session.scalars(
        select(ScreeningRunModel)
        .where(
            ScreeningRunModel.strategy_id == strategy_id,
            ScreeningRunModel.data_version.like(f"historical:%{_MARK}%"),
        )
        .order_by(ScreeningRunModel.run_date, ScreeningRunModel.id)
    )
    return list(rows.all())


async def rescreen(ctx: dict[str, Any]) -> dict[str, Any]:
    """Create the missing v2 runs, one session per date; tag any untagged run."""
    register_builtin_engines()
    done: list[dict[str, Any]] = []
    skipped: list[str] = []
    for day in ctx["eligible"]:
        async with get_database().session() as session:
            repo = SqlScreeningRunRepository(session)
            strategy = await SqlStrategyRepository(session).get_active(STRATEGY_NAME)
            if strategy is None or strategy.id is None:
                raise SystemExit("production strategy not found: stop")
            existing = [r for r in await _series_runs(session, strategy.id) if r.run_date == day]
            completed = [r for r in existing if r.status == "COMPLETED"]
            if completed:
                skipped.append(day.isoformat())
            else:
                use_case = PointInTimeHistoricalScreening(
                    session=session,
                    screening_run_repo=repo,
                    strategy_repo=SqlStrategyRepository(session),
                    strategy_engine=StrategyEngine(
                        engines=engine_registry,
                        scoring=ScoringEngineImpl(),
                        ranking=RankingEngineImpl(),
                    ),
                )
                # A retry after a FAILED attempt gets its own data_version.
                suffix = f"{_MARK}:a{len(existing)}" if existing else _MARK
                result = await use_case.execute(
                    strategy_name=STRATEGY_NAME, as_of_date=day, run_suffix=suffix
                )
                run_id = int(result["run_id"])
                done.append(
                    {
                        "date": day.isoformat(),
                        "run_id": run_id,
                        **{k: int(result[k]) for k in ("total_evaluated", "total_passed")},
                    }
                )
                _logger.info("rescreen_date_done", run_date=day.isoformat(), run_id=run_id)
    return {"created": done, "skipped_existing": skipped}


async def backfill(ctx: dict[str, Any]) -> dict[str, Any]:
    """Write session-basis forward returns for the v2 runs; one transaction per run."""
    holdout_start: date = ctx["holdout"][0]
    cutoff = max(s for s in ctx["sessions"] if s < holdout_start)
    calendar = get_nse_trading_calendar()
    summary: list[dict[str, Any]] = []
    async with get_database().session() as session:
        runs = [
            (r.id, r.run_date, r.stats or {})
            for r in await _series_runs(
                session,
                (await SqlStrategyRepository(session).get_active(STRATEGY_NAME)).id,  # type: ignore[union-attr]
            )
            if r.status == "COMPLETED"
        ]
    for run_id, run_date, stats in runs:
        if stats.get("engine_version") != ENGINE_VERSION or run_date not in ctx["eligible"]:
            raise SystemExit(f"run {run_id} is not an eligible engine-v{ENGINE_VERSION} run: stop")
        horizons = horizons_before(ctx["sessions"], run_date, holdout_start, DEFAULT_HORIZONS)
        async with get_database().session() as session:
            repo = SqlScreeningRunRepository(session)
            use_case = ForwardReturnsBackfill(
                screening_run_repo=repo,
                ohlcv_repo=_BoundedOHLCV(session, cutoff),
                benchmark_index_repo=_BoundedBenchmark(session, cutoff),
                horizons=horizons,
                calendar=calendar,
            )
            res = await use_case.execute(run_id)
        summary.append(
            {"run_id": run_id, "date": run_date.isoformat(), "horizons": list(horizons), **res}
        )
        _logger.info("backfill_run_done", run_id=run_id, **res)
    return {"cutoff": cutoff.isoformat(), "runs": summary}


async def main(command: str) -> None:
    """Run ``plan``, ``rescreen`` or ``backfill``."""
    ctx = await _context()
    plan = {
        "engine_version": ENGINE_VERSION,
        "indicator_version": INDICATOR_VERSION,
        "research_window": [d.isoformat() for d in ctx["research"]],
        "holdout": [d.isoformat() for d in ctx["holdout"]],
        "grid_size": len(ctx["grid"]),
        "eligible": [d.isoformat() for d in ctx["eligible"]],
    }
    if command == "plan":
        print(json.dumps(plan, indent=2))
    elif command == "rescreen":
        print(json.dumps({"plan": plan, **await rescreen(ctx)}, indent=2, default=str))
    elif command == "backfill":
        print(json.dumps({"plan": plan, **await backfill(ctx)}, indent=2, default=str))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else ""))
