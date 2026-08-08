"""FastAPI dependency providers for the Research & Validation Platform.

Wires research use cases with their infrastructure collaborators (repositories,
pipelines, strategy engine) following the same pattern as `dependencies.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from momentum25.application.use_cases.research.comparison import StrategyComparisonUseCase
from momentum25.application.use_cases.research.contribution import ContributionAnalysisUseCase
from momentum25.application.use_cases.research.evaluation import EvaluateStrategyUseCase
from momentum25.application.use_cases.research.experiment import ExperimentUseCase
from momentum25.application.use_cases.research.historical_screening import HistoricalScreeningUseCase
from momentum25.application.use_cases.research.validation import (
    DeterminismVerificationUseCase,
    ValidateRunComparisonUseCase,
)
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import EngineRegistry, engine_registry
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.interface.api.dependencies import (
    get_ohlcv_repo,
    get_screening_run_repository,
    get_security_repo,
    get_strategy_repo,
)


# ── Historical Screening ────────────────────────────────────────────────


async def get_historical_screening_use_case(
    security_repo: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv_repo: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[HistoricalScreeningUseCase]:
    """Provide a HistoricalScreeningUseCase instance.

    Assembles the full vertical slice: repositories, indicator pipeline,
    and strategy engine — identical to the live screening pipeline.
    """
    register_builtin_engines()
    session = get_database().new_session()
    try:
        indicator_pipeline = IndicatorPipelineImpl(session)

        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=scoring_engine,
            ranking=ranking_engine,
        )

        yield HistoricalScreeningUseCase(
            security_repo=security_repo,
            ohlcv_repo=ohlcv_repo,
            screening_run_repo=screening_run_repo,
            strategy_repo=strategy_repo,
            indicator_pipeline=indicator_pipeline,
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
    security_repo: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv_repo: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[DeterminismVerificationUseCase]:
    """Provide a DeterminismVerificationUseCase instance.

    Assembles the full historical screening pipeline internally so the
    same screening can be run twice and the outputs compared to verify
    determinism.
    """
    register_builtin_engines()
    session = get_database().new_session()
    try:
        indicator_pipeline = IndicatorPipelineImpl(session)
        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=scoring_engine,
            ranking=ranking_engine,
        )
        historical_use_case = HistoricalScreeningUseCase(
            security_repo=security_repo,
            ohlcv_repo=ohlcv_repo,
            screening_run_repo=screening_run_repo,
            strategy_repo=strategy_repo,
            indicator_pipeline=indicator_pipeline,
            strategy_engine=strategy_engine,
        )
        yield DeterminismVerificationUseCase(
            historical_screening_use_case=historical_use_case,
        )
    finally:
        await session.close()


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
) -> AsyncIterator[ContributionAnalysisUseCase]:
    """Provide a ContributionAnalysisUseCase instance."""
    yield ContributionAnalysisUseCase(screening_run_repo=screening_run_repo)


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
    security_repo: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv_repo: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
    screening_run_repo: Annotated[
        SqlScreeningRunRepository, Depends(get_screening_run_repository)
    ],
    strategy_repo: Annotated[SqlStrategyRepository, Depends(get_strategy_repo)],
) -> AsyncIterator[ExperimentUseCase]:
    """Provide an ExperimentUseCase instance."""
    historical_use_case = await get_historical_screening_use_case(
        security_repo, ohlcv_repo, screening_run_repo, strategy_repo
    ).__anext__()
    yield ExperimentUseCase(
        strategy_repo=strategy_repo,
        screening_run_repo=screening_run_repo,
        historical_screening_use_case=historical_use_case,
    )