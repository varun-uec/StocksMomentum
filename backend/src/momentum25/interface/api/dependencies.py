"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.chart_patterns import DetectChartPatterns
from momentum25.application.use_cases.elliott_wave import GetElliottWaveAnalysis
from momentum25.application.use_cases.market_context import GetMarketContext
from momentum25.application.use_cases.rankings import GetRankings, GetStockExplanation
from momentum25.application.use_cases.research.refresh_corporate_actions import (
    RefreshCorporateActions,
)
from momentum25.application.use_cases.runs import (
    GetLatestRunForStrategy,
    GetRun,
    ListRuns,
    TriggerRefresh,
)
from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.application.use_cases.securities import GetSecurityOHLCV, SearchSecurities
from momentum25.application.use_cases.stocks import (
    GetIndicatorSeries,
    GetLiveStockAnalysis,
    GetStockHistory,
    RefreshGate,
)
from momentum25.application.use_cases.stocks import (
    GetStockExplanation as GetStockExplanationBySymbol,
)
from momentum25.application.use_cases.strategies import GetStrategy, ListStrategies
from momentum25.application.use_cases.watchlist import (
    AddToWatchlist,
    GetWatchlist,
    GetWatchlistDetail,
    RemoveFromWatchlist,
)
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlBenchmarkIndexRepository,
    SqlCorporateActionRepository,
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
    SqlWatchlistRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.infrastructure.providers.nse_client import NSEMarketDataClient
from momentum25.infrastructure.redis.client import get_redis_provider
from momentum25.infrastructure.system_clock import SystemClock


def get_live_refresh_gate() -> RefreshGate:
    """Return a Redis-backed refresh gate, or the no-cooldown fallback.

    Constructing :class:`RedisRefreshGate` never touches the network -- it
    only wraps the lazily-connected client -- so this is safe to call even
    when Redis is unreachable; failures surface per-call inside the gate,
    not here.
    """
    from momentum25.infrastructure.redis.refresh_gate import RedisRefreshGate

    return RedisRefreshGate(
        get_redis_provider().client,
        cooldown_seconds=get_settings().live_refresh_cooldown_seconds,
    )

# ── Repository providers ─────────────────────────────────────────────────


@asynccontextmanager
async def _managed_session() -> AsyncIterator[AsyncSession]:
    """Yield a session and ensure it is closed after the request."""
    session = get_database().new_session()
    try:
        yield session
    finally:
        await session.close()


async def get_security_repo() -> AsyncIterator[SqlSecurityRepository]:
    """Provide a security repository instance."""
    async with _managed_session() as session:
        yield SqlSecurityRepository(session)


async def get_ohlcv_repo() -> AsyncIterator[SqlOHLCVRepository]:
    """Provide an OHLCV repository instance."""
    async with _managed_session() as session:
        yield SqlOHLCVRepository(session)


async def get_watchlist_repo() -> AsyncIterator[SqlWatchlistRepository]:
    """Provide a watchlist repository instance."""
    async with _managed_session() as session:
        yield SqlWatchlistRepository(session)


async def get_screening_run_repository() -> AsyncIterator[SqlScreeningRunRepository]:
    """Provide a screening-run repository instance."""
    async with _managed_session() as session:
        yield SqlScreeningRunRepository(session)


async def get_strategy_repo() -> AsyncIterator[SqlStrategyRepository]:
    """Provide a strategy repository instance."""
    async with _managed_session() as session:
        yield SqlStrategyRepository(session)


# Backwards-compatible alias used by rankings providers.
get_security_repository = get_security_repo


# ── Use-case providers ───────────────────────────────────────────────────


async def get_get_rankings(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    security_repo: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetRankings]:
    """Provide a GetRankings use-case instance."""
    yield GetRankings(
        screening_run_repo=screening_run_repo,
        security_repo=security_repo,
        strategy_repo=strategy_repo,
    )


async def get_get_stock_explanation(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetStockExplanation]:
    """Provide a run/security-scoped GetStockExplanation use-case instance."""
    yield GetStockExplanation(
        screening_run_repo=screening_run_repo,
        explainability_builder=ExplainabilityBuilderImpl(),
        strategy_repo=strategies,
    )


async def get_stock_explanation(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    screening_run_repo: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetStockExplanationBySymbol]:
    """Provide a symbol-scoped stock explanation use-case instance."""
    yield GetStockExplanationBySymbol(
        securities=securities,
        screening_run_repo=screening_run_repo,
        explainability_builder=ExplainabilityBuilderImpl(),
        strategies=strategies,
    )


async def get_stock_history(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    screening_run_repo: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetStockHistory]:
    """Provide a stock-history use-case instance."""
    yield GetStockHistory(
        securities=securities, screening_run_repo=screening_run_repo, strategies=strategies
    )


async def get_list_runs(
    runs: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[ListRuns]:
    """Provide a ListRuns use-case instance."""
    yield ListRuns(runs=runs, strategies=strategies)


async def get_get_run(
    runs: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetRun]:
    """Provide a GetRun use-case instance."""
    yield GetRun(runs=runs, strategies=strategies)


async def get_get_latest_run_for_strategy(
    runs: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetLatestRunForStrategy]:
    """Provide a GetLatestRunForStrategy use-case instance."""
    yield GetLatestRunForStrategy(runs=runs, strategies=strategies)


async def get_trigger_refresh(
    runs: Annotated[SqlScreeningRunRepository, Depends(get_screening_run_repository)],
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
    ohlcv: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
) -> AsyncIterator[TriggerRefresh]:
    """Provide a TriggerRefresh use-case instance."""
    yield TriggerRefresh(
        runs=runs,
        strategies=strategies,
        ohlcv=ohlcv,
        clock=SystemClock(),
    )


async def get_list_strategies(
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[ListStrategies]:
    """Provide a ListStrategies use-case instance."""
    yield ListStrategies(strategies=strategies)


async def get_get_watchlist(
    watchlist: Annotated[SqlWatchlistRepository, Depends(get_watchlist_repo)],
) -> AsyncIterator[GetWatchlist]:
    """Provide a GetWatchlist use-case instance."""
    yield GetWatchlist(watchlist=watchlist)


async def get_add_to_watchlist(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    watchlist: Annotated[SqlWatchlistRepository, Depends(get_watchlist_repo)],
) -> AsyncIterator[AddToWatchlist]:
    """Provide an AddToWatchlist use-case instance."""
    yield AddToWatchlist(securities=securities, watchlist=watchlist)


async def get_remove_from_watchlist(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    watchlist: Annotated[SqlWatchlistRepository, Depends(get_watchlist_repo)],
) -> AsyncIterator[RemoveFromWatchlist]:
    """Provide a RemoveFromWatchlist use-case instance."""
    yield RemoveFromWatchlist(securities=securities, watchlist=watchlist)


async def get_get_watchlist_detail() -> AsyncIterator[GetWatchlistDetail]:
    """Provide a GetWatchlistDetail use-case instance.

    Assembles the same engines/indicator-pipeline slice as
    :func:`get_live_stock_analysis` for the out-of-run live evaluation path,
    plus a Redis-backed RS-rating cache (degrades to "no cache" on a Redis
    outage, matching :class:`RedisRefreshGate`).
    """
    from momentum25.infrastructure.redis.rs_rating_cache import RedisRsRatingCache

    register_builtin_engines()
    async with _shared_session() as session:
        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry, scoring=scoring_engine, ranking=ranking_engine
        )
        yield GetWatchlistDetail(
            watchlist=SqlWatchlistRepository(session),
            securities=SqlSecurityRepository(session),
            screening_run_repo=SqlScreeningRunRepository(session),
            strategies=SqlStrategyRepository(session),
            ohlcv_repo=SqlOHLCVRepository(session),
            indicator_pipeline=IndicatorPipelineImpl(session),
            strategy_engine=strategy_engine,
            rs_rating_cache=RedisRsRatingCache(get_redis_provider().client),
        )


async def get_elliott_wave_analysis(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
) -> AsyncIterator[GetElliottWaveAnalysis]:
    """Provide a GetElliottWaveAnalysis use-case instance."""
    yield GetElliottWaveAnalysis(securities=securities, ohlcv=ohlcv)


async def get_detect_chart_patterns(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
) -> AsyncIterator[DetectChartPatterns]:
    """Provide a DetectChartPatterns use-case instance."""
    yield DetectChartPatterns(securities=securities, ohlcv=ohlcv)


async def get_get_security_ohlcv(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
) -> AsyncIterator[GetSecurityOHLCV]:
    """Provide a GetSecurityOHLCV use-case instance."""
    yield GetSecurityOHLCV(securities=securities, ohlcv=ohlcv)


async def get_search_securities(
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
) -> AsyncIterator[SearchSecurities]:
    """Provide a SearchSecurities use-case instance."""
    yield SearchSecurities(securities=securities)


async def get_get_strategy(
    strategies: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[GetStrategy]:
    """Provide a GetStrategy use-case instance."""
    yield GetStrategy(strategies=strategies)


# ── Shared-session providers (for write use cases) ───────────────────────


@asynccontextmanager
async def _shared_session() -> AsyncIterator[AsyncSession]:
    """Yield a single session shared by multiple repositories in a write use case."""
    session = get_database().new_session()
    try:
        yield session
    finally:
        await session.close()


async def get_execute_screening() -> AsyncIterator[ExecuteScreening]:
    """Provide an ExecuteScreening use-case instance.

    Assembles the full vertical slice: BhavcopyProvider (ADR-003 MVP), repositories,
    indicator pipeline, and strategy engine.
    """
    register_builtin_engines()
    async with _shared_session() as session:
        import httpx

        from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

        market_data_provider = BhavcopyProvider(httpx.AsyncClient())
        security_repo = SqlSecurityRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)
        screening_run_repo = SqlScreeningRunRepository(session)
        indicator_pipeline = IndicatorPipelineImpl(session)

        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=scoring_engine,
            ranking=ranking_engine,
        )

        yield ExecuteScreening(
            market_data_provider=market_data_provider,
            security_repo=security_repo,
            ohlcv_repo=ohlcv_repo,
            screening_run_repo=screening_run_repo,
            indicator_pipeline=indicator_pipeline,
            strategy_engine=strategy_engine,
        )


async def get_refresh_corporate_actions() -> AsyncIterator[RefreshCorporateActions]:
    """Provide a RefreshCorporateActions use-case instance.

    A periodic maintenance operation, not part of the daily screening
    request path -- see ``application.services.corporate_actions`` for why.
    """
    async with _shared_session() as session:
        import httpx

        from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

        yield RefreshCorporateActions(
            market_data_provider=BhavcopyProvider(httpx.AsyncClient()),
            security_repo=SqlSecurityRepository(session),
            corporate_action_repo=SqlCorporateActionRepository(session),
            ohlcv_repo=SqlOHLCVRepository(session),
        )


async def get_live_stock_analysis() -> AsyncIterator[GetLiveStockAnalysis]:
    """Provide a GetLiveStockAnalysis use-case instance (Phase 1.1).

    Assembles the same engines/indicator-pipeline slice as
    :func:`get_execute_screening`, plus the NSE historical-bar client for
    on-demand refresh and a Redis-backed refresh cooldown when Redis is
    reachable (degrades to no cooldown on a Redis outage, see
    ``application.use_cases.stocks.RefreshGate``).
    """
    register_builtin_engines()
    async with _shared_session() as session:
        security_repo = SqlSecurityRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)
        strategy_repo = SqlStrategyRepository(session)
        indicator_pipeline = IndicatorPipelineImpl(session)

        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=scoring_engine,
            ranking=ranking_engine,
        )

        yield GetLiveStockAnalysis(
            securities=security_repo,
            ohlcv_repo=ohlcv_repo,
            strategies=strategy_repo,
            indicator_pipeline=indicator_pipeline,
            strategy_engine=strategy_engine,
            explainability_builder=ExplainabilityBuilderImpl(),
            nse_client=NSEMarketDataClient(),
            refresh_gate=get_live_refresh_gate(),
            benchmark_repo=SqlBenchmarkIndexRepository(session),
        )


async def get_indicator_series() -> AsyncIterator[GetIndicatorSeries]:
    """Provide a GetIndicatorSeries use-case instance (Phase 9).

    The indicator series is a read-only convenience over the same
    :class:`IndicatorPipelineImpl` slice as the live stock analysis, so a chart
    sub-pane's last bar always matches the live endpoint's latest values.
    """
    async with _shared_session() as session:
        yield GetIndicatorSeries(
            securities=SqlSecurityRepository(session),
            strategies=SqlStrategyRepository(session),
            indicator_pipeline=IndicatorPipelineImpl(session),
        )


async def get_market_context() -> AsyncIterator[GetMarketContext]:
    """Provide a GetMarketContext use-case instance (Phase 6.6/6.7).

    All three repositories share one session: breadth and sector strength must
    describe the same snapshot of the universe.
    """
    async with _shared_session() as session:
        yield GetMarketContext(
            securities=SqlSecurityRepository(session),
            ohlcv_repo=SqlOHLCVRepository(session),
            benchmark_repo=SqlBenchmarkIndexRepository(session),
            benchmark_index=get_settings().benchmark_index,
        )
