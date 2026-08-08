"""Historical Screening — execute the complete screening pipeline for any past date.

Priority 1 of Phase 4. Uses historical market data only, recreates indicator values
exactly as they would have existed on that date, and stores immutable snapshots.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.application.services.rs_ratings import compute_universe_rs_ratings
from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.research.data_quality import is_stale_as_of
from momentum25.domain.value_objects.results import SectorStats, UniverseMembership
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.observability.research_metadata import get_git_commit

_logger = get_logger("historical_screening")


class HistoricalScreeningUseCase:
    """Execute the full screening pipeline for a historical trading date.

    The use case:
        1. Resolves the strategy and universe.
        2. Loads historical OHLCV data as of the target date (no future data).
        3. Computes indicators using only data available on that date.
        4. Runs the strategy engine (engines → scoring → ranking).
        5. Persists an immutable snapshot of the results.
        6. Returns the run ID and summary.

    Every result is reproducible: identical inputs produce identical outputs.
    """

    def __init__(
        self,
        security_repo: Any,
        ohlcv_repo: Any,
        screening_run_repo: Any,
        strategy_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
    ) -> None:
        """Wire the use case with its collaborators.

        Args:
            security_repo: Repository for securities.
            ohlcv_repo: Repository for OHLCV bars.
            screening_run_repo: Repository for screening runs and results.
            strategy_repo: Repository for strategy definitions.
            indicator_pipeline: The indicator computation pipeline.
            strategy_engine: The strategy orchestrator (engines → scoring → ranking).
        """
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine

    async def execute(
        self,
        strategy_name: str,
        as_of_date: date,
        symbol_filter: list[str] | None = None,
        run_suffix: str = "",
        enforce_listing_date_filter: bool = True,
    ) -> dict[str, Any]:
        """Execute a historical screening run.

        Args:
            strategy_name: Name of the strategy to use.
            as_of_date: The historical trading date to screen as of.
            symbol_filter: Optional list of symbols to restrict the universe.
            run_suffix: Optional uniqueness suffix for ``data_version`` (e.g. to
                re-run the same date without violating the run's unique constraint).
            enforce_listing_date_filter: When ``True`` (default, live behaviour)
                the universe excludes securities whose ``securities.listing_date``
                is after ``as_of_date`` — the only point-in-time guard available
                against a not-yet-listed name entering an older backtest. Callers
                that have *already* established point-in-time membership by a
                stronger, evidence-based rule (e.g. the pre-2019 legacy backfill,
                whose reconstructed universe requires real bars dated ≤ the run
                date) pass ``False`` so a provider-coverage-start ``listing_date``
                (which is not the true IPO date) does not wrongly drop names that
                demonstrably traded on that date.

        Returns:
            A dict with keys: run_id, run_date, total_evaluated, total_passed,
            total_failed, duration_seconds.

        Raises:
            ValueError: If the strategy is not found.
        """
        _logger.info(
            "historical_screening_started",
            strategy=strategy_name,
            as_of=as_of_date.isoformat(),
        )

        # 1. Resolve the strategy
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            msg = f"Strategy not found: {strategy_name}"
            raise ValueError(msg)

        # 2. Resolve the universe
        # Excludes securities not yet listed as of the historical date --
        # using today's full active list regardless of ``as_of_date`` would
        # let a stock listed in 2025 appear in a 2020 backtest (look-ahead /
        # survivorship bias). This is a partial mitigation only: it cannot
        # exclude securities that were later delisted or dropped from the
        # index, since no historical index-constituent history exists (see
        # docs/research -- nsemine has no historical-constituents endpoint).
        # The residual bias is recorded in ``run.stats`` below.
        all_securities = await self._security_repo.list_active()
        if enforce_listing_date_filter:
            securities = [
                s
                for s in all_securities
                if s.listing_date is None or s.listing_date <= as_of_date
            ]
        else:
            securities = list(all_securities)
        excluded_unlisted = len(all_securities) - len(securities)
        listed_ids = {s.id for s in securities}
        not_yet_listed_memberships = [
            UniverseMembership(security_id=s.id, eligible=False, reason="not_yet_listed")
            for s in all_securities
            if s.id is not None and s.id not in listed_ids
        ]
        if symbol_filter:
            securities = [s for s in securities if str(s.symbol) in symbol_filter]

        if not securities:
            raise ValueError("No securities to screen")

        # 3. Create the screening run
        import time
        unique_suffix = run_suffix or f":{int(time.time())}"
        run = ScreeningRun(
            strategy_id=strategy.id or 0,
            run_date=as_of_date,
            data_version=f"historical:{as_of_date.isoformat()}{unique_suffix}",
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.RUNNING,
        )
        run_id = await self._screening_run_repo.create(run)
        run.id = run_id

        try:
            # 4. Evaluate each security
            scores, memberships = await self._evaluate_universe(
                securities, strategy, as_of_date
            )

            # 5. Rank
            rankings = self._strategy_engine.rank(scores, strategy)

            # 6. Persist
            await self._screening_run_repo.save_results(run_id, scores, rankings)
            await self._screening_run_repo.save_universe_membership(
                run_id, memberships + not_yet_listed_memberships
            )

            # 7. Mark completed
            run.status = RunStatus.COMPLETED
            run.stats = {
                "total_evaluated": len(securities),
                "total_passed": sum(1 for s in scores if s.hard_filters_passed),
                "total_failed": sum(1 for s in scores if not s.hard_filters_passed),
                "historical": True,
                "as_of_date": as_of_date.isoformat(),
                "excluded_not_yet_listed": excluded_unlisted,
                "excluded_stale_data": sum(1 for m in memberships if m.reason == "stale_data"),
                "survivorship_bias_disclosure": (
                    "Universe excludes securities not yet listed as of as_of_date, "
                    "but cannot exclude securities later delisted or dropped from "
                    "the index (no historical index-constituent history is "
                    "available). Results may still overstate historical "
                    "performance for older dates."
                ),
                "git_commit": get_git_commit(),
            }
            await self._screening_run_repo.update(run)
            await self._commit()

            _logger.info(
                "historical_screening_completed",
                run_id=run_id,
                evaluated=len(securities),
                passed=run.stats["total_passed"],
            )

            return {
                "run_id": run_id,
                "run_date": as_of_date,
                "total_evaluated": len(securities),
                "total_passed": run.stats["total_passed"],
                "total_failed": run.stats["total_failed"],
            }

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)
            await self._screening_run_repo.update(run)
            await self._commit()
            raise

    async def _evaluate_universe(
        self,
        securities: list[Security],
        strategy: Strategy,
        as_of_date: date,
    ) -> tuple[list[Any], list[UniverseMembership]]:
        """Evaluate every security in the universe as of the historical date."""
        scores: list[Any] = []
        memberships: list[UniverseMembership] = []
        security_by_symbol = {str(s.symbol): s for s in securities}

        # Same universe-relative RS computation the live daily orchestrator uses --
        # without this, rs_rating stays None for every stock and tt_rs_rating_min
        # (part of the mandatory Trend Template gate) fails for the entire universe.
        rs_ratings = await compute_universe_rs_ratings(
            securities,
            self._ohlcv_repo,
            as_of_date,
            strategy.config.indicators.get("rs_return_weights"),
        )

        for symbol, security in security_by_symbol.items():
            if security.id is None:
                continue
            try:
                # Compute indicators using only data available on as_of_date
                indicators = await self._indicator_pipeline.compute(
                    symbol, as_of_date, strategy.config.indicators
                )
                if indicators.sma200 is None:
                    # Insufficient history — skip
                    memberships.append(
                        UniverseMembership(
                            security_id=security.id,
                            eligible=False,
                            reason="insufficient_history",
                        )
                    )
                    continue

                ctx = await self._build_context(security, indicators, as_of_date)
                latest_bar = ctx.series.bars[-1].date if ctx.series.bars else None
                if is_stale_as_of(as_of_date, latest_bar):
                    # Data ingestion has fallen behind or stopped for this
                    # security -- scoring it would reuse a months-old close
                    # as if it reflected as_of_date (see data_quality.py for
                    # why this must be excluded rather than silently scored).
                    memberships.append(
                        UniverseMembership(
                            security_id=security.id, eligible=False, reason="stale_data"
                        )
                    )
                    continue

                rs_rating = rs_ratings.get(symbol)
                if rs_rating is not None:
                    object.__setattr__(indicators, "rs_rating", rs_rating)

                score = self._strategy_engine.score_security(ctx, strategy)
                scores.append(score)
                memberships.append(UniverseMembership(security_id=security.id, eligible=True))

            except Exception as exc:
                _logger.warning(
                    "historical_screening_symbol_failed",
                    symbol=symbol,
                    error=str(exc),
                )
                memberships.append(
                    UniverseMembership(
                        security_id=security.id, eligible=False, reason=f"error: {exc}"
                    )
                )

        return scores, memberships

    async def _build_context(
        self,
        security: Security,
        indicators: Any,
        as_of_date: date,
    ) -> EvaluationContext:
        """Build a complete evaluation context for a single security."""
        if security.id is None:
            raise ValueError(f"Security {security.symbol} has no id")

        series = await self._ohlcv_repo.get_series(
            security.id, lookback_days=275, as_of=as_of_date
        )
        return EvaluationContext(
            security=security,
            series=series,
            indicators=indicators,
            benchmark=OHLCVSeries(security_id=0, bars=()),
            sector_stats=SectorStats(),
        )

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._screening_run_repo, "_session", None)
        if session is not None:
            await session.commit()