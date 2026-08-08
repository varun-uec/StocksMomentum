"""Dependency providers for Strategy Validation & Alpha Research (Phase 6).

Wires the validation use cases with their infrastructure collaborators
(repositories, pipelines, strategy engine) for FastAPI dependency injection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.validation import (
    AlphaMeasurementUseCase,
    EngineEffectivenessUseCase,
    HistoricalValidationUseCase,
    ParameterResearchUseCase,
    RuleEffectivenessUseCase,
    StrategyScorecardUseCase,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

# ── Session management ────────────────────────────────────────────────────


@asynccontextmanager
async def _managed_session() -> AsyncIterator[AsyncSession]:
    """Yield a session and ensure it is closed after the request."""
    session = get_database().new_session()
    try:
        yield session
    finally:
        await session.close()


async def _managed_session_async() -> AsyncIterator[AsyncSession]:
    """Async generator wrapper around _managed_session for FastAPI Depends."""
    async with _managed_session() as session:
        yield session


# ── Repository providers ──────────────────────────────────────────────────


async def _get_screening_run_repo(
    session: Annotated[AsyncSession, Depends(_managed_session_async)],
) -> AsyncIterator[SqlScreeningRunRepository]:
    """Provide a screening run repository instance."""
    yield SqlScreeningRunRepository(session)


async def _get_strategy_repo(
    session: Annotated[AsyncSession, Depends(_managed_session_async)],
) -> AsyncIterator[SqlStrategyRepository]:
    """Provide a strategy repository instance."""
    yield SqlStrategyRepository(session)


async def _get_ohlcv_repo(
    session: Annotated[AsyncSession, Depends(_managed_session_async)],
) -> AsyncIterator[SqlOHLCVRepository]:
    """Provide an OHLCV repository instance."""
    yield SqlOHLCVRepository(session)


async def _get_security_repo(
    session: Annotated[AsyncSession, Depends(_managed_session_async)],
) -> AsyncIterator[SqlSecurityRepository]:
    """Provide a security repository instance."""
    yield SqlSecurityRepository(session)


# ── Infrastructure providers ──────────────────────────────────────────────


async def _get_indicator_pipeline(
    session: Annotated[AsyncSession, Depends(_managed_session_async)],
) -> AsyncIterator[IndicatorPipelineImpl]:
    """Provide an indicator pipeline bound to the current session."""
    yield IndicatorPipelineImpl(session)


async def _get_strategy_engine() -> AsyncIterator[StrategyEngine]:
    """Build the strategy engine with registered engines."""
    register_builtin_engines()
    scoring_engine = ScoringEngineImpl()
    ranking_engine = RankingEngineImpl()
    yield StrategyEngine(
        engines=engine_registry,
        scoring=scoring_engine,
        ranking=ranking_engine,
    )


# ── Use-case providers ────────────────────────────────────────────────────


async def get_historical_validation_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
    ohlcv_repo: Annotated[SqlOHLCVRepository, Depends(_get_ohlcv_repo)],
    security_repo: Annotated[SqlSecurityRepository, Depends(_get_security_repo)],
    indicator_pipeline: Annotated[
        IndicatorPipelineImpl, Depends(_get_indicator_pipeline)
    ],
    strategy_engine: Annotated[StrategyEngine, Depends(_get_strategy_engine)],
) -> AsyncIterator[HistoricalValidationUseCase]:
    """Create a HistoricalValidationUseCase with wired dependencies."""
    yield HistoricalValidationUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
        ohlcv_repo=ohlcv_repo,
        security_repo=security_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
    )


async def get_alpha_measurement_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
) -> AsyncIterator[AlphaMeasurementUseCase]:
    """Create an AlphaMeasurementUseCase with wired dependencies."""
    yield AlphaMeasurementUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


async def get_scorecard_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
) -> AsyncIterator[StrategyScorecardUseCase]:
    """Create a StrategyScorecardUseCase with wired dependencies."""
    yield StrategyScorecardUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


async def get_rule_effectiveness_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
) -> AsyncIterator[RuleEffectivenessUseCase]:
    """Create a RuleEffectivenessUseCase with wired dependencies."""
    yield RuleEffectivenessUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


async def get_engine_effectiveness_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
) -> AsyncIterator[EngineEffectivenessUseCase]:
    """Create an EngineEffectivenessUseCase with wired dependencies."""
    yield EngineEffectivenessUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


async def get_parameter_research_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(_get_screening_run_repo)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(_get_strategy_repo)],
    indicator_pipeline: Annotated[
        IndicatorPipelineImpl, Depends(_get_indicator_pipeline)
    ],
    strategy_engine: Annotated[StrategyEngine, Depends(_get_strategy_engine)],
    ohlcv_repo: Annotated[SqlOHLCVRepository, Depends(_get_ohlcv_repo)],
    security_repo: Annotated[SqlSecurityRepository, Depends(_get_security_repo)],
) -> AsyncIterator[ParameterResearchUseCase]:
    """Create a ParameterResearchUseCase with wired dependencies."""
    yield ParameterResearchUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
        ohlcv_repo=ohlcv_repo,
        security_repo=security_repo,
    )