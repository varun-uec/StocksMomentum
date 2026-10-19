"""FastAPI dependency providers for the Research & Validation Platform.

Wires research use cases with their infrastructure collaborators (repositories,
pipelines, strategy engine) following the same pattern as `dependencies.py`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Annotated

from fastapi import Depends

from momentum25.application.use_cases.research.comparison import StrategyComparisonUseCase
from momentum25.application.use_cases.research.contribution import ContributionAnalysisUseCase
from momentum25.application.use_cases.research.evaluation import EvaluateStrategyUseCase
from momentum25.application.use_cases.research.experiment import ExperimentUseCase
from momentum25.application.use_cases.research.validation import (
    DeterminismVerificationUseCase,
    ValidateRunComparisonUseCase,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.point_in_time_screening import (
    PointInTimeHistoricalScreening,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)
from momentum25.interface.api.dependencies import (
    get_screening_run_repository,
    get_strategy_repo,
)

# ── Historical Screening ────────────────────────────────────────────────


async def get_historical_screening_use_case() -> AsyncGenerator[
    PointInTimeHistoricalScreening, None
]:
    """Provide historical screening bound to one captured point-in-time revision."""
    register_builtin_engines()
    session = get_database().new_session()
    try:
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=ScoringEngineImpl(),
            ranking=RankingEngineImpl(),
        )
        yield PointInTimeHistoricalScreening(
            session=session,
            screening_run_repo=SqlScreeningRunRepository(session),
            strategy_repo=SqlStrategyRepository(session),
            strategy_engine=strategy_engine,
        )
    finally:
        await session.close()


# ── Run Comparison / Validation ─────────────────────────────────────────


async def get_validate_run_comparison_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
) -> AsyncIterator[ValidateRunComparisonUseCase]:
    """Provide a ValidateRunComparisonUseCase instance."""
    yield ValidateRunComparisonUseCase(screening_run_repo=screening_run_repo)


async def get_determinism_verification_use_case(
) -> AsyncIterator[DeterminismVerificationUseCase]:
    """Provide a DeterminismVerificationUseCase instance.

    Assembles the full historical screening pipeline internally so the
    same screening can be run twice and the outputs compared to verify
    determinism.
    """
    screening_provider = get_historical_screening_use_case()
    historical_screening = await anext(screening_provider)
    try:
        yield DeterminismVerificationUseCase(
            historical_screening_use_case=historical_screening,
        )
    finally:
        await screening_provider.aclose()


# ── Strategy Evaluation ─────────────────────────────────────────────────


async def get_strategy_evaluation_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[EvaluateStrategyUseCase]:
    """Provide an EvaluateStrategyUseCase instance."""
    yield EvaluateStrategyUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


# ── Contribution Analysis ───────────────────────────────────────────────


async def get_contribution_analysis_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[ContributionAnalysisUseCase]:
    """Provide a ContributionAnalysisUseCase instance."""
    yield ContributionAnalysisUseCase(
        screening_run_repo=screening_run_repo, strategy_repo=strategy_repo
    )


# ── Strategy Comparison ─────────────────────────────────────────────────


async def get_strategy_comparison_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[StrategyComparisonUseCase]:
    """Provide a StrategyComparisonUseCase instance."""
    yield StrategyComparisonUseCase(
        screening_run_repo=screening_run_repo,
        strategy_repo=strategy_repo,
    )


# ── Experiment Laboratory ───────────────────────────────────────────────


async def get_experiment_use_case(
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[ExperimentUseCase]:
    """Provide an ExperimentUseCase instance."""
    screening_provider = get_historical_screening_use_case()
    historical_use_case = await anext(screening_provider)
    try:
        yield ExperimentUseCase(
            strategy_repo=strategy_repo,
            screening_run_repo=screening_run_repo,
            historical_screening_use_case=historical_use_case,
        )
    finally:
        await screening_provider.aclose()
