"""Screening orchestrator — coordinates the full daily screening lifecycle.

Consumes the existing infrastructure (BhavcopyProvider, IndicatorPipelineImpl,
StrategyEngine, repositories) and exposes a single high-level entry point:
:meth:`ScreeningOrchestrator.run_daily_screening`.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime
from decimal import Decimal
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
from momentum25.domain.research.liquidity_floor import (
    MIN_AVG_TURNOVER,
    MIN_CLOSE,
    MIN_PRIOR_SESSIONS,
    LiquidityDecision,
    evaluate_liquidity_eligibility,
)
from momentum25.domain.value_objects.results import SectorStats, StockScore, UniverseMembership
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.observability.research_metadata import get_git_commit
from momentum25.infrastructure.pipelines.indicator_pipeline import INDICATOR_VERSION

_logger = get_logger("screening_orchestrator")


async def build_evaluation_context(
    security: Security,
    indicators: Any,
    ohlcv_repo: Any,
    as_of: date,
    lookback_days: int = 275,
) -> EvaluationContext:
    """Build a complete :class:`EvaluationContext` for a single security.

    Shared by the daily orchestrator and the on-demand single-symbol lookup
    (Phase 1.1) so both evaluate through the identical assembly -- a context
    built one way for batch runs and another for live lookups would make the
    two paths silently disagree about the same rules.
    """
    if security.id is None:
        raise ValueError(f"Security {security.symbol} has no id")

    series = await ohlcv_repo.get_series(security.id, lookback_days=lookback_days, as_of=as_of)
    return EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=OHLCVSeries(security_id=0, bars=()),
        sector_stats=SectorStats(),
    )


class ScreeningOrchestrator:
    """Coordinates the daily screening pipeline with bounded concurrency."""

    def __init__(
        self,
        security_repo: Any,
        ohlcv_repo: Any,
        screening_run_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
        strategy: Strategy,
        strategy_repo: Any | None = None,
    ) -> None:
        """Wire the orchestrator with its collaborators."""
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._screening_run_repo = screening_run_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine
        self._strategy = strategy
        self._strategy_repo = strategy_repo
        self._semaphore = asyncio.Semaphore(10)

    async def run_daily_screening(
        self, trading_date: date, existing_run_id: int | None = None
    ) -> ScreeningRunSummary:
        """Execute the full daily screening lifecycle for *trading_date*.

        Args:
            trading_date: The date to screen.
            existing_run_id: If provided, updates this already-created run row
                (status RUNNING -> COMPLETED/FAILED) instead of creating a new
                one. Used by the background execution path (Phase 1.6), which
                returns a run id to the client before the pipeline finishes.

        Returns a :class:`ScreeningRunSummary` with counts and timing.
        """
        start = time.perf_counter()
        summary = ScreeningRunSummary(run_date=trading_date)

        # 1. Universe resolution
        securities = await self._security_repo.list_active()
        symbols = [s.symbol for s in securities]
        summary.total_evaluated = len(symbols)

        # 2. Data-freshness precondition.
        #
        # This orchestrator screens whatever is already persisted; ingestion is the
        # caller's responsibility (``ExecuteScreening`` upserts bars before
        # delegating here). Until Phase 0.2 this block called
        # ``fetch_eod(trading_date)`` and then *discarded* the result without ever
        # persisting it — a no-op that read as a working sync and would have
        # silently screened stale bars for any caller that trusted it. Rather than
        # duplicate ingestion here (this class holds no symbol→security_id map),
        # the precondition is now checked and disclosed explicitly. Per-security
        # staleness is still enforced downstream by ``is_stale_as_of``.
        latest = await self._ohlcv_repo.latest_date()
        if latest is None or latest < trading_date:
            _logger.warning(
                "screening_on_stale_data",
                requested_date=trading_date.isoformat(),
                latest_persisted=latest.isoformat() if latest else None,
                detail="no ingestion performed by the orchestrator; see ExecuteScreening",
            )

        # 3. Ensure strategy is persisted so the run has a valid strategy_id
        strategy_id = await self._ensure_strategy_id()

        # 4. Create (or adopt an existing PENDING) screening run
        if existing_run_id is not None:
            run = await self._screening_run_repo.get(existing_run_id)
            if run is None:
                raise ValueError(f"existing_run_id {existing_run_id} not found")
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(UTC)
            run.data_version = str(latest or trading_date)
            await self._screening_run_repo.update(run)
            run_id = existing_run_id
        else:
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
                "indicator_version": INDICATOR_VERSION,
                "universe_source": "declared_liquidity_floor",
                "total_skipped_ineligible_universe": (
                    summary.total_skipped_ineligible_universe
                ),
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

                    # Universe admission: the strategy's declared liquidity floor
                    # (``config.universe``, ADR-005). Phase 0.1 — before this, the
                    # declared floor was never enforced on the live path at all and
                    # the universe was instead an alphabetical truncation applied
                    # during ingestion. Evaluated through the same
                    # ``evaluate_liquidity_eligibility`` the research/historical
                    # path uses, so live and backtest admit on identical logic.
                    decision = self._evaluate_universe_admission(ctx.series, trading_date)
                    if not decision.eligible:
                        summary.total_skipped_ineligible_universe += 1
                        memberships.append(
                            UniverseMembership(
                                security_id=security.id,
                                eligible=False,
                                reason=decision.reason,
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


    def _evaluate_universe_admission(
        self, series: OHLCVSeries, trading_date: date
    ) -> LiquidityDecision:
        """Apply the strategy's declared liquidity floor to one security's series.

        Thresholds come from ``strategy.config.universe`` (ADR-005), defaulting to
        the research-fixed constants when a key is absent so behaviour is
        unchanged for any config that omits them. ``series`` is only ever EQ here:
        the bhavcopy provider filters ``series='EQ'`` at ingestion, so no non-EQ
        bar can reach this point.
        """
        universe_cfg = self._strategy.config.universe
        bars = series.bars
        if not bars or bars[-1].date != trading_date:
            return LiquidityDecision(False, "no_bar_on_trading_date", None)

        return evaluate_liquidity_eligibility(
            close=bars[-1].close,
            series="EQ",
            prior_session_count=len(bars) - 1,
            trailing_turnovers=[b.turnover_value for b in bars],
            min_close=Decimal(str(universe_cfg.get("min_price_inr", MIN_CLOSE))),
            min_avg_turnover=Decimal(
                str(universe_cfg.get("min_avg_turnover_inr", MIN_AVG_TURNOVER))
            ),
            min_prior_sessions=int(
                universe_cfg.get("min_history_days", MIN_PRIOR_SESSIONS)
            ),
        )

    async def _build_context(
        self,
        security: Security,
        indicators: Any,
        trading_date: date,
    ) -> EvaluationContext:
        """Build a complete evaluation context for a single security."""
        return await build_evaluation_context(security, indicators, self._ohlcv_repo, trading_date)

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
