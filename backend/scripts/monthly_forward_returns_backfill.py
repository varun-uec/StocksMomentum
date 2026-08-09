"""Monthly historical screening + forward-return backfill over the live archive.

Populates ``forward_returns`` for the run series identified in
``docs/research/2026-08-09-momentum-selection-methodology-review.md`` §1.1: monthly
screening runs from 2020-10 through 2026-02, generated with the *frozen production
strategy* against the live ``ohlcv_daily`` archive.

Nothing about methodology is invented here. This is a driver only — it loops the
existing ``HistoricalScreeningUseCase`` and ``ForwardReturnsBackfill`` over a
month-end date grid. Scoring is the live ``StrategyEngine`` / ``ScoringEngineImpl``
/ ``RankingEngineImpl``, so runs generated here use the corrected ranking composite
(gate engines excluded from ``momentum_score`` / ``buy_setup_score``) by
construction; there is no second scoring path to drift from.

Window bounds are set by the data, not by choice: the start is bounded by the
252-day indicator warm-up over an archive beginning 2019-10-01, the end by the
120-day forward horizon needing to have fully elapsed before 2026-08-07 (the last
available bar). Horizons match ``ForwardReturnsBackfill.DEFAULT_HORIZONS``, of
which the walk-forward harness's decision horizon (120d) is one.

Every run is tagged ``historical:<date>:monthly-backfill`` (excluded from
product-facing queries by the existing ``historical:%`` filter) and carries a
``run_type=historical_backfill`` stat, so these rows can never be confused with
live production screening. Determinism: identical inputs → identical outputs. The
run is resumable — a date whose run already exists is skipped — so re-invocation
is safe.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from structlog import get_logger

from momentum25.application.use_cases.research.forward_returns_backfill import (
    DEFAULT_HORIZONS,
    ForwardReturnsBackfill,
)
from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import OHLCVDailyModel, ScreeningRunModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

_logger = get_logger("monthly_forward_returns_backfill")

# The frozen production strategy. ``get_active`` resolves this name to the
# highest version (version 3 = strategy_id=30), i.e. the live production config.
STRATEGY_NAME = "minervini_trend_template"

# Bounded below by the indicator warm-up over an archive starting 2019-10-01,
# above by the 120-day forward horizon needing to have elapsed.
#
# The warm-up is 277 sessions, not the 252 the methodology review assumed:
# ``IndicatorPipelineImpl._required_min_bars`` needs sma200 + the 22-day sma200
# slope window plus a buffer. The 277th session in ``ohlcv_daily`` is 2020-11-11,
# so 2020-10-30 (the review's first target) yields *zero* qualifiers -- every
# security is dropped as ``insufficient_history``. The first month-end that
# screens is therefore 2020-11-27, costing one run off the planned ~65.
WINDOW_START = date(2020, 11, 1)
WINDOW_END = date(2026, 2, 28)

_RUN_SUFFIX = ":monthly-backfill"


def month_end_targets(start: date, end: date) -> list[date]:
    """Return the last calendar day of each month in ``[start, end]``, ascending.

    Pure and deterministic. Each target is snapped to a real trading date by
    :func:`snap_to_trading_dates` before use.
    """
    out: list[date] = []
    year, month = start.year, start.month
    while True:
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        last_day = date(next_year, next_month, 1) - timedelta(days=1)
        if last_day > end:
            break
        if last_day >= start:
            out.append(last_day)
        year, month = next_year, next_month
    return out


def snap_to_trading_dates(targets: list[date], trading_dates: list[date]) -> list[date]:
    """Snap each target back to the latest trading date ``<= target``.

    ``trading_dates`` must be ascending. Targets with no prior trading date are
    dropped; duplicates (two targets snapping to the same session) collapse.
    Pure and deterministic.
    """
    out: list[date] = []
    seen: set[date] = set()
    for target in targets:
        candidates = [d for d in trading_dates if d <= target]
        if not candidates:
            continue
        snapped = candidates[-1]
        if snapped not in seen:
            seen.add(snapped)
            out.append(snapped)
    return out


async def _trading_dates(session: Any, start: date, end: date) -> list[date]:
    """Return the ascending distinct session dates present in ``ohlcv_daily``."""
    result = await session.execute(
        select(OHLCVDailyModel.date)
        .where(OHLCVDailyModel.date >= start, OHLCVDailyModel.date <= end)
        .distinct()
        .order_by(OHLCVDailyModel.date)
    )
    return list(result.scalars().all())


async def _existing_run_dates(session: Any) -> set[date]:
    """Return run dates already backfilled by this script (for resumability)."""
    result = await session.execute(
        select(ScreeningRunModel.run_date).where(
            ScreeningRunModel.data_version.like(f"historical:%{_RUN_SUFFIX}")
        )
    )
    return set(result.scalars().all())


async def _run_one_date(
    *,
    run_date: date,
    screening_use_case: HistoricalScreeningUseCase,
    forward_backfill: ForwardReturnsBackfill,
    screening_run_repo: SqlScreeningRunRepository,
) -> dict[str, int]:
    """Screen one date, tag the run, and backfill its forward returns."""
    result = await screening_use_case.execute(
        strategy_name=STRATEGY_NAME,
        as_of_date=run_date,
        run_suffix=_RUN_SUFFIX,
    )
    run_id = int(result["run_id"])

    run = await screening_run_repo.get(run_id)
    if run is not None:
        run.stats = {
            **(run.stats or {}),
            "run_type": "historical_backfill",
            "bar_source": "ohlcv_daily",
            "cadence": "monthly",
            "strategy_name": STRATEGY_NAME,
        }
        await screening_run_repo.update(run)
        await screening_run_repo._session.commit()  # noqa: SLF001

    fr = await forward_backfill.execute(run_id)
    return {
        "run_id": run_id,
        "evaluated": int(result["total_evaluated"]),
        "passed": int(result["total_passed"]),
        "securities_evaluated": int(fr["securities_evaluated"]),
        "forward_rows": int(fr["rows_written"]),
    }


async def main() -> None:
    """Generate the monthly run series and backfill forward returns over it."""
    register_builtin_engines()
    db = get_database()

    async with db.session() as session:
        trading_dates = await _trading_dates(session, WINDOW_START, WINDOW_END)
        existing = await _existing_run_dates(session)

    run_dates = snap_to_trading_dates(
        month_end_targets(WINDOW_START, WINDOW_END), trading_dates
    )

    summary: dict[str, Any] = {
        "planned_dates": len(run_dates),
        "screened_dates": 0,
        "skipped_existing": 0,
        "failed_dates": [],
        "forward_rows": 0,
        "first_date": run_dates[0].isoformat() if run_dates else None,
        "last_date": run_dates[-1].isoformat() if run_dates else None,
        "horizons": list(DEFAULT_HORIZONS),
    }

    for run_date in run_dates:
        if run_date in existing:
            summary["skipped_existing"] += 1
            continue
        # Each date gets its own unit-of-work session so a failure on one date
        # never poisons another (and commits stay bounded).
        try:
            async with db.session() as session:
                ohlcv_repo = SqlOHLCVRepository(session)
                screening_run_repo = SqlScreeningRunRepository(session)
                screening_use_case = HistoricalScreeningUseCase(
                    security_repo=SqlSecurityRepository(session),
                    ohlcv_repo=ohlcv_repo,
                    screening_run_repo=screening_run_repo,
                    strategy_repo=SqlStrategyRepository(session),
                    indicator_pipeline=IndicatorPipelineImpl(session),
                    strategy_engine=StrategyEngine(
                        engines=engine_registry,
                        scoring=ScoringEngineImpl(),
                        ranking=RankingEngineImpl(),
                    ),
                )
                forward_backfill = ForwardReturnsBackfill(
                    screening_run_repo=screening_run_repo,
                    ohlcv_repo=ohlcv_repo,
                    benchmark_index_repo=SqlBenchmarkIndexRepository(session),
                )
                res = await _run_one_date(
                    run_date=run_date,
                    screening_use_case=screening_use_case,
                    forward_backfill=forward_backfill,
                    screening_run_repo=screening_run_repo,
                )
            summary["screened_dates"] += 1
            summary["forward_rows"] += res["forward_rows"]
            _logger.info("backfill_date_done", run_date=run_date.isoformat(), **res)
        except Exception as exc:  # noqa: BLE001 — one bad date must not stop the series
            summary["failed_dates"].append({"date": run_date.isoformat(), "error": str(exc)})
            _logger.warning(
                "backfill_date_failed", run_date=run_date.isoformat(), error=str(exc)
            )

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
