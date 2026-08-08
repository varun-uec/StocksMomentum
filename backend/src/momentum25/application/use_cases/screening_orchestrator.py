"""Screening orchestrator — coordinates the full daily screening lifecycle.

Consumes the existing infrastructure (BhavcopyProvider, IndicatorPipelineImpl,
StrategyEngine, repositories) and exposes a single high-level entry point:
:meth:`ScreeningOrchestrator.run_daily_screening`.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime
from typing import Any

from structlog import get_logger

from momentum25.application.dto.runs import ScreeningRunSummary
from momentum25.application.services.rs_ratings import compute_universe_rs_ratings
from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.research.data_quality import is_stale_as_of
from momentum25.domain.value_objects.results import SectorStats, StockScore, UniverseMembership
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.observability.research_metadata import get_git_commit

_logger = get_logger("screening_orchestrator")


class ScreeningOrchestrator:
    """Coordinates the daily screening pipeline with bounded concurrency."""

    def __init__(
        self,
        security_repo: Any,
        ohlcv_repo: Any,
        screening_run_repo: Any,
        market_data_provider: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
        strategy: Strategy,
        strategy_repo: Any | None = None,
    ) -> None:
        """Wire the orchestrator with its collaborators."""
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._screening_run_repo = screening_run_repo
        self._market_data_provider = market_data_provider
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine
        self._strategy = strategy
        self._strategy_repo = strategy_repo
        self._semaphore = asyncio.Semaphore(10)

    async def run_daily_screening(self, trading_date: date) -> ScreeningRunSummary:
        """Execute the full daily screening lifecycle for *trading_date*.

        Returns a :class:`ScreeningRunSummary` with counts and timing.
        """
        start = time.perf_counter()
        summary = ScreeningRunSummary(run_date=trading_date)

        # 1. Universe resolution
        securities = await self._security_repo.list_active()
        symbols = [s.symbol for s in securities]
        summary.total_evaluated = len(symbols)

        # 2. Data sync — ensure OHLCV bars for trading_date exist
        latest = await self._ohlcv_repo.latest_date()
        if latest is None or latest < trading_date:
            _logger.info("data_sync_required", date=trading_date.isoformat())
            raw_bars = await self._market_data_provider.fetch_eod(trading_date)
            if raw_bars:
                _logger.info("data_synced", bars=len(raw_bars))

        # 3. Ensure strategy is persisted so the run has a valid strategy_id
        strategy_id = await self._ensure_strategy_id()

        # 4. Create the screening run
        run = ScreeningRun(
            strategy_id=strategy_id,
            run_date=trading_date,
            data_version=str(latest or trading_date),
            config_hash=self._strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        run_id = await self._screening_run_repo.create(run)
        run.id = run_id

        try:
            # 5. Concurrent processing with throttled semaphore
            scores, memberships = await self._evaluate_universe(securities, trading_date, summary)

            # 6. Rank the scored universe
            rankings = self._strategy_engine.rank(scores, self._strategy)

            # 7. Persist scores, rankings, and rule results
            await self._screening_run_repo.save_results(run_id, scores, rankings)
            await self._screening_run_repo.save_universe_membership(run_id, memberships)

            # 8. Mark run completed
            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.now(UTC)
            run.stats = {
                "total_evaluated": summary.total_evaluated,
                "total_passed": summary.total_passed,
                "total_skipped": summary.total_skipped_insufficient_data,
                "total_failed": summary.total_failed,
                "git_commit": get_git_commit(),
            }
            await self._screening_run_repo.update(run)

            # 9. Commit the unit of work so cross-session reads (e.g. API tests) see results
            await self._commit()
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.now(UTC)
            run.error = str(exc)
            await self._screening_run_repo.update(run)
            await self._commit()
            raise

        summary.duration_seconds = round(time.perf_counter() - start, 3)
        _logger.info(
            "screening_completed",
            date=trading_date.isoformat(),
            run_id=run_id,
            passed=summary.total_passed,
            skipped=summary.total_skipped_insufficient_data,
            failed=summary.total_failed,
            duration=summary.duration_seconds,
        )
        return summary

    async def _ensure_strategy_id(self) -> int:
        """Return a persisted strategy id, creating one if necessary."""
        if self._strategy.id is not None:
            return self._strategy.id

        if self._strategy_repo is not None:
            strategy_id = int(await self._strategy_repo.upsert(self._strategy))
        else:
            # Fallback: build a transient strategy repository from the same session.
            from momentum25.infrastructure.persistence.repositories.strategy import (
                SqlStrategyRepository,
            )

            strategy_repo = SqlStrategyRepository(self._screening_run_repo._session)
            strategy_id = int(await strategy_repo.upsert(self._strategy))

        # Mutate the frozen Strategy in-place so external references see the id.
        object.__setattr__(self._strategy, "id", strategy_id)
        return strategy_id

    async def _evaluate_universe(
        self,
        securities: list[Security],
        trading_date: date,
        summary: ScreeningRunSummary,
    ) -> tuple[list[StockScore], list[UniverseMembership]]:
        """Evaluate every security and return its StockScores and eligibility records."""
        security_by_symbol = {str(s.symbol): s for s in securities}
        scores: list[StockScore] = []
        memberships: list[UniverseMembership] = []

        # Pre-compute universe-relative RS ratings (1-99 percentile) since the
        # indicator pipeline leaves rs_rating as None (real RS pipeline deferred).
        rs_ratings = await compute_universe_rs_ratings(
            securities,
            self._ohlcv_repo,
            trading_date,
            self._strategy.config.indicators.get("rs_return_weights"),
        )

        async def _process(symbol: str) -> None:
            async with self._semaphore:
                security = security_by_symbol[symbol]
                if security.id is None:
                    return
                try:
                    indicators = await self._indicator_pipeline.compute(
                        symbol, trading_date, self._strategy.config.indicators
                    )
                    if indicators.sma200 is None:
                        summary.total_skipped_insufficient_data += 1
                        memberships.append(
                            UniverseMembership(
                                security_id=security.id,
                                eligible=False,
                                reason="insufficient_history",
                            )
                        )
                        return

                    ctx = await self._build_context(security, indicators, trading_date)
                    latest_bar = ctx.series.bars[-1].date if ctx.series.bars else None
                    if is_stale_as_of(trading_date, latest_bar):
                        # Data ingestion has fallen behind or stopped for this
                        # security -- scoring it would reuse a months-old close
                        # as if it reflected trading_date (see data_quality.py
                        # for why this must be excluded rather than silently
                        # scored).
                        summary.total_skipped_stale_data += 1
                        memberships.append(
                            UniverseMembership(
                                security_id=security.id, eligible=False, reason="stale_data"
                            )
                        )
                        return

                    # Inject universe-relative RS rating
                    rs_rating = rs_ratings.get(symbol)
                    if rs_rating is not None:
                        object.__setattr__(indicators, "rs_rating", rs_rating)

                    score = self._strategy_engine.score_security(ctx, self._strategy)
                    scores.append(score)
                    memberships.append(
                        UniverseMembership(security_id=security.id, eligible=True)
                    )

                    if score.hard_filters_passed:
                        summary.total_passed += 1
                    else:
                        summary.total_failed += 1
                except Exception as exc:
                    _logger.error(
                        "symbol_screening_failed", symbol=symbol, error=str(exc)
                    )
                    summary.errors.append(f"{symbol}: {exc}")
                    summary.total_failed += 1
                    memberships.append(
                        UniverseMembership(
                            security_id=security.id, eligible=False, reason=f"error: {exc}"
                        )
                    )

        await asyncio.gather(*(_process(sym) for sym in security_by_symbol))
        return scores, memberships


    async def _build_context(
        self,
        security: Security,
        indicators: Any,
        trading_date: date,
    ) -> EvaluationContext:
        """Build a complete evaluation context for a single security."""
        if security.id is None:
            raise ValueError(f"Security {security.symbol} has no id")

        series = await self._ohlcv_repo.get_series(
            security.id, lookback_days=275, as_of=trading_date
        )
        return EvaluationContext(
            security=security,
            series=series,
            indicators=indicators,
            benchmark=OHLCVSeries(security_id=0, bars=()),
            sector_stats=SectorStats(),
        )

    async def _commit(self) -> None:
        """Commit the current unit of work if the repository exposes a session."""
        session = getattr(self._screening_run_repo, "_session", None)
        if session is not None:
            await session.commit()


def _build_context(security: Any, indicators: Any) -> Any:
    """Build a minimal evaluation context for strategy engine.

    Kept for backwards compatibility with callers that do not supply an
    OHLCV repository; the orchestrator now uses the async
    :meth:`ScreeningOrchestrator._build_context` which loads the real series.
    """
    from momentum25.domain.engines.base import EvaluationContext
    from momentum25.domain.entities.market_data import OHLCVSeries
    from momentum25.domain.value_objects.results import SectorStats

    series = OHLCVSeries(security_id=security.id or 0, bars=())
    return EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=OHLCVSeries(security_id=0, bars=()),
        sector_stats=SectorStats(),
    )
