r"""Incident recovery — re-ingest the full live history window (2019-10-01 → present).

Rebuilds the tables the dev-database incident emptied, exclusively through the
already-shipped market-data adapters and persistence repositories — no new
source, no fabricated data, no recovery from ``legacy_ohlcv_daily_bak`` (which
is treated as unusable, per the recovery directive):

1. Universe: rebuilds ``securities`` from the live NSE instrument master
   (``BhavcopyProvider.fetch_instrument_master``), then restores the NSE/BSE
   exchange dimension via :class:`ReconcileCrossListings` (identity-only, never
   admits BSE-only names) on the last trading session.
2. Price history: replays every trading session in the live window through
   ``BhavcopyProvider.fetch_eod_full`` — the exact method (and routing) the
   daily pipeline's ``ExecuteScreening._fetch_eod_range`` uses — grouping bars
   per security and writing idempotent ``ON CONFLICT`` upserts via
   :class:`SqlOHLCVRepository`, so a re-run is safe and skipped days are only
   re-touched, never duplicated.
3. Benchmark: backfills ``benchmark_index_daily`` from ``fetch_benchmark`` for
   every trading session in the research backfill range (2015-01-01 → present).
4. Verification: runs the live screening pipeline via
   :class:`ScreeningOrchestrator` as-of the last trading session with an active
   strategy (``benchmark_c_trend_template_only``), so the fresh run exercises
   the trend-template gate and scoring engine against the restored data.
5. Report: prints table row counts for the verification checklist.

Safety:
- Refuses to run unless ``M25_DATABASE_URL`` resolves to the incident dev
  database (host port 55432 or any ``*_test`` suffix database). A stray run
  against the default 5432 docker-compose database cannot happen.
- The ``SINGLE`` test fixture and its stale demo run (the only rows left after
  the truncation) are removed first, with counts logged — the baseline table
  counts must not include a synthetic namesake.

Usage::

    M25_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:55432/momentum25 \\
        python scripts/reingest_history.py [START_ISO] [END_ISO]

Optional ``START_ISO``/``END_ISO`` bound the OHLCV replay window (defaults:
2019-10-01 → last trading session) — useful for a staged recovery or a smoke
test. Benchmark backfill and the verification run are unaffected by these.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from typing import Any

import httpx
from sqlalchemy import text

from momentum25.application.use_cases.research.reconcile_cross_listings import (
    ReconcileCrossListings,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlBenchmarkIndexRepository,
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider
from momentum25.infrastructure.providers.bse_bhavcopy import BSEBhavcopyProvider

# ── Window constants (Research Dataset v1.0 baseline) ──────────────────────
# The live window the daily pipeline covers: the current NSE provider starts
# 2019-09-30; the recovery directive re-fetches from 2019-10-01.
HISTORY_START: date = date(2019, 10, 1)
# The benchmark backfill range used by research (NIFTY500, since 2015-01-01).
BENCHMARK_START: date = date(2015, 1, 1)

# The active strategy whose trend-template engine the verification run executes.
VERIFY_STRATEGY = "benchmark_c_trend_template_only"


def _expect_dev_target() -> None:
    """Abort unless the configured DB is the incident-owned dev database.

    Guards against the default ``postgresql+asyncpg://…@localhost:5432/…`` in
    ``.env`` being accidentally used — recovery must go to ``55432``.
    """
    url = get_settings().database_url
    db_name = url.rsplit("/", 1)[-1]
    # URL shape: postgresql+asyncpg://user:pass@host:PORT/db
    port = url.rpartition(":")[2].partition("/")[0]
    if not db_name.endswith("_test") and port != "55432":
        raise SystemExit(
            f"Refusing to run recovery against non-dev target ({url}). "
            "Set M25_DATABASE_URL to the documented dev database (port 55432)."
        )
    print(f"[guard] target database: {db_name} @ {port}")


async def prune_synthetic_fixture(session: Any) -> dict[str, int]:
    """Remove the SINGLE test fixture left over from the truncation residue.

    Not part of market data: a synthetic 300-bar series (2024-01-01 →
    2024-10-26) under security id 1 with its stale completed run, results and
    memberships. Deleting it restores the baseline table counts (research
    dataset counting excluded this fixture by construction).
    """
    s_repo = SqlSecurityRepository(session)
    counts: dict[str, int] = {}

    fixtures = await s_repo.list_active()
    singles = [s for s in fixtures if str(s.symbol) == "SINGLE"]
    for security in singles:
        if security.id is None:
            continue
        sid = security.id
        fixt_runs = await session.execute(
            text(
                "SELECT id FROM screening_runs WHERE strategy_id IN "
                "(SELECT id FROM strategies WHERE name = 'single_symbol_strategy')"
            )
        )
        run_ids = [r[0] for r in fixt_runs.fetchall()]
        for table in ("rule_results", "screening_results", "universe_membership"):
            res = await session.execute(
                text(f"DELETE FROM {table} WHERE run_id = ANY(:ids)"), {"ids": run_ids}
            )
            counts[f"{table}_deleted"] = counts.get(f"{table}_deleted", 0) + res.rowcount or 0
        if run_ids:
            res = await session.execute(
                text("DELETE FROM screening_runs WHERE id = ANY(:ids)"), {"ids": run_ids}
            )
            counts["screening_runs_deleted"] = res.rowcount or 0
        res = await session.execute(
            text("DELETE FROM ohlcv_daily WHERE security_id = :sid"), {"sid": sid}
        )
        counts["ohlcv_daily_deleted"] = res.rowcount or 0
        res = await session.execute(
            text("DELETE FROM securities WHERE id = :sid"), {"sid": sid}
        )
        counts["securities_deleted"] = res.rowcount or 0
        print(json.dumps({"pruned_synthetic_fixture": counts}))
    return counts


async def rebuild_universe(session: Any) -> dict[str, Any]:
    """Rebuild ``securities`` from the NSE instrument master + exchange stamps."""
    provider = BhavcopyProvider(httpx.AsyncClient())
    security_repo = SqlSecurityRepository(session)
    master = await provider.fetch_instrument_master()
    print(f"instrument_master_symbols={len(master)}")

    securities = [
        Security(
            symbol=Symbol(inst.symbol),
            name=inst.name,
            isin=inst.isin,
            listing_date=inst.listing_date,
            is_active=True,
        )
        for inst in master
    ]
    await security_repo.upsert_many(securities)
    await session.commit()

    # Restore the NSE/BSE exchange dimension (identity-only; never admits
    # BSE-only names — see ReconcileCrossListings docstring).
    bse_provider = BSEBhavcopyProvider(httpx.AsyncClient())
    reconciler = ReconcileCrossListings(
        nse_provider=provider,
        bse_provider=bse_provider,
        security_repo=security_repo,
    )
    last = _last_session()
    cross = await reconciler.execute(as_of=last)
    print(f"cross_listing_reconcile: {sorted(cross.items())}")
    return {"master_size": len(master), "cross_listing": cross}


def _last_session() -> date:
    """Return the most recent trading session in [HISTORY_START, today]."""
    calendar = get_nse_trading_calendar()
    sessions = calendar.sessions_between(HISTORY_START, date.today())
    if not sessions:
        raise RuntimeError("No trading sessions in the live window")
    return sessions[-1]


async def reingest_ohlcv(session: Any, start: date, end: date | None = None) -> dict[str, int]:
    """Replay every live-window session through ``fetch_eod_full`` into ohlcv_daily."""
    provider = BhavcopyProvider(httpx.AsyncClient())
    security_repo = SqlSecurityRepository(session)
    ohlcv_repo = SqlOHLCVRepository(session)
    calendar = get_nse_trading_calendar()

    end_date = end or _last_session()
    sessions = calendar.sessions_between(start, end_date)
    active = await security_repo.list_active()
    symbol_ids = {str(s.symbol): s.id for s in active if s.id is not None}

    created_symbols: list[str] = []
    counts = {
        "sessions_total": len(sessions),
        "sessions_fetched": 0,
        "sessions_empty": 0,
        "symbols_ingested": 0,
        "bars_written": 0,
    }

    for session_date in sessions:
        bars = await provider.fetch_eod_full(session_date)
        counts["sessions_fetched"] += 1
        if not bars:
            counts["sessions_empty"] += 1
            continue
        pending: dict[int, list[OHLCVBar]] = {}
        for bar in bars:
            security_id = symbol_ids.get(bar.symbol)
            if security_id is None:
                # A symbol trading on this date that is no longer in today's
                # master (renamed/delisted within the window): register it, as
                # the daily pipeline did on the day it traded.
                security = Security(
                    symbol=Symbol(bar.symbol),
                    name=str(bar.symbol),
                    isin=bar.isin,
                    is_active=True,
                )
                await security_repo.upsert_many([security])
                registered = await security_repo.get_by_symbol(bar.symbol)
                security_id = registered.id if registered else None
                if security_id is None:
                    continue
                symbol_ids[bar.symbol] = security_id
                created_symbols.append(bar.symbol)
            pending.setdefault(security_id, []).append(
                OHLCVBar(
                    date=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    prev_close=bar.prev_close,
                    turnover_value=bar.turnover_value,
                )
            )
        await ohlcv_repo.upsert_bars_batch(pending)
        await session.commit()
        if counts["sessions_fetched"] % 50 == 0:
            print(
                f"progress: {counts['sessions_fetched']}/{counts['sessions_total']} "
                f"sessions, last={session_date.isoformat()}"
            )

    counts["symbols_ingested"] = len(symbol_ids)
    counts["bars_written"] = (await session.execute(
        text("SELECT count(*) FROM ohlcv_daily")
    )).scalar_one()
    counts["new_symbols_registered"] = len(created_symbols)
    return counts


async def backfill_benchmark(session: Any) -> dict[str, int]:
    """Backfill ``benchmark_index_daily`` for every session since 2015-01-01."""
    provider = BhavcopyProvider(httpx.AsyncClient())
    repo = SqlBenchmarkIndexRepository(session)
    calendar = get_nse_trading_calendar()
    index_code = get_settings().benchmark_index
    sessions = calendar.sessions_between(BENCHMARK_START, _last_session())

    existing = await repo.get_close_series(index_code)  # resume support
    fetched: list[Any] = []
    for session_date in sessions:
        if session_date in existing:
            continue
        bar = await provider.fetch_benchmark(index_code, session_date)
        if bar is not None:
            fetched.append(bar)
    if fetched:
        await repo.upsert_bars(index_code, fetched)
        await session.commit()
    return {
        "sessions_in_range": len(sessions),
        "rows_written": len(fetched),
        "rows_now": len(existing) + len(fetched),
    }


async def run_verification_screening(session: Any) -> dict[str, Any]:
    """Run the live trend-template screening as-of the last trading session."""
    from momentum25.application.use_cases.screening_orchestrator import (
        ScreeningOrchestrator,
    )
    from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
    from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
    from momentum25.domain.strategy.bootstrap import register_builtin_engines
    from momentum25.domain.strategy.engine_registry import engine_registry
    from momentum25.domain.strategy.strategy_engine import StrategyEngine
    from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

    register_builtin_engines()
    strategy_repo = SqlStrategyRepository(session)
    strategy = await strategy_repo.get_active(VERIFY_STRATEGY)
    if strategy is None:
        raise RuntimeError(f"Strategy not active: {VERIFY_STRATEGY}")

    strategy_engine = StrategyEngine(
        engines=engine_registry,
        scoring=ScoringEngineImpl(),
        ranking=RankingEngineImpl(),
    )
    orchestrator = ScreeningOrchestrator(
        security_repo=SqlSecurityRepository(session),
        ohlcv_repo=SqlOHLCVRepository(session),
        screening_run_repo=SqlScreeningRunRepository(session),
        indicator_pipeline=IndicatorPipelineImpl(session),
        strategy_engine=strategy_engine,
        strategy=strategy,
        strategy_repo=strategy_repo,
    )
    summary = await orchestrator.run_daily_screening(_last_session())
    print(
        f"screening: evaluated={summary.total_evaluated} passed={summary.total_passed} "
        f"failed={summary.total_failed} "
        f"skipped_insufficient={summary.total_skipped_insufficient_data}"
    )
    return {
        "run_date": _last_session().isoformat(),
        "evaluated": summary.total_evaluated,
        "passed": summary.total_passed,
        "failed": summary.total_failed,
        "skipped_insufficient": summary.total_skipped_insufficient_data,
    }


async def report_counts(session: Any) -> dict[str, int]:
    """Return the verification table's row counts."""
    tables = [
        "securities",
        "ohlcv_daily",
        "benchmark_index_daily",
        "screening_runs",
        "screening_results",
        "rule_results",
        "universe_membership",
        "watchlist_items",
        "legacy_ohlcv_daily",
    ]
    counts: dict[str, int] = {}
    for table in tables:
        rows = await session.execute(text(f"SELECT count(*) FROM {table}"))
        counts[table] = rows.scalar_one()
    return counts


async def main(start: date, end: date | None, ohlcv_only: bool) -> None:
    """Run the full re-ingest and print the verification report."""
    db = get_database()
    async with db.session() as session:
        pruned = await prune_synthetic_fixture(session)
        universe = await rebuild_universe(session)
        history = await reingest_ohlcv(session, start, end)
        if ohlcv_only:
            counts = await report_counts(session)
            report = {"pruned": pruned, "universe": universe, "history": history,
                      "final_counts": counts}
            print("=== RECOVERY REPORT (OHLCV STAGE) ===")
            print(json.dumps(report, indent=2, default=str))
            return
        benchmark = await backfill_benchmark(session)
        screening = await run_verification_screening(session)
        counts = await report_counts(session)

    report = {
        "pruned": pruned,
        "universe": universe,
        "history": history,
        "benchmark": benchmark,
        "screening": screening,
        "final_counts": counts,
    }
    print("=== RECOVERY REPORT ===")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    _expect_dev_target()
    parser = argparse.ArgumentParser(description="Re-ingest live history (recovery).")
    parser.add_argument("start", nargs="?", type=date.fromisoformat, default=HISTORY_START)
    parser.add_argument("end", nargs="?", type=date.fromisoformat, default=None)
    parser.add_argument("--ohlcv-only", action="store_true",
                        help="re-ingest OHLCV only; skip benchmark + verification run")
    args = parser.parse_args()
    asyncio.run(main(args.start, args.end, args.ohlcv_only))