"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
from momentum25.application.use_cases.stocks import (
    GetStockExplanation as GetStockExplanationBySymbol,
)
from momentum25.application.use_cases.stocks import GetStockHistory
from momentum25.application.use_cases.strategies import GetStrategy, ListStrategies
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlCorporateActionRepository,
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.infrastructure.system_clock import SystemClock

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
) -> AsyncIterator[GetRankings]:
    """Provide a GetRankings use-case instance."""
    yield GetRankings(
        screening_run_repo=screening_run_repo,
        security_repo=security_repo,
    )


async def get_get_stock_explanation(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
) -> AsyncIterator[GetStockExplanation]:
    """Provide a run/security-scoped GetStockExplanation use-case instance."""
    yield GetStockExplanation(
        screening_run_repo=screening_run_repo,
        explainability_builder=ExplainabilityBuilderImpl(),
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
