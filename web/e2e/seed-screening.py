"""Create a completed screening snapshot from the synthetic E2E bars only.

This uses the screening domain directly; it does not call the NSE provider.
Run after migrations and ``db.py seed`` and before starting the API server.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.config.strategy_loader import load_strategies_dir
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

# The production strategy, plus one benchmark so the legacy strategy
# comparison has two stored runs on the same date.
FIXTURE_STRATEGIES = ("minervini_trend_template", "benchmark_a_pure_momentum")


async def main() -> None:
    """Run the fixture strategies against the seeded synthetic bars."""
    settings = get_settings()
    register_builtin_engines()
    async with get_database().session() as session:
        strategy_repo = SqlStrategyRepository(session)
        for strategy in load_strategies_dir(Path(settings.strategy_dir)):
            await strategy_repo.upsert(strategy)

        ohlcv_repo = SqlOHLCVRepository(session)
        as_of = await ohlcv_repo.latest_date()
        if as_of is None:
            raise RuntimeError("synthetic E2E bars were not seeded")
        manifest = await SqlDataManifestRepository(session).capture()

        for name in FIXTURE_STRATEGIES:
            strategy = await strategy_repo.get_active(name)
            if strategy is None:
                raise RuntimeError(f"the fixture strategy {name} was not loaded")
            run_repo = SqlScreeningRunRepository(session)
            previous = await run_repo.latest_completed(strategy.id)
            if previous is not None:
                if (
                    previous.run_date == as_of
                    and previous.data_version == manifest.data_version
                    and previous.config_hash == strategy.config_hash
                ):
                    print(f"synthetic screening snapshot already present: {name} run_id={previous.id}")
                    continue
                raise RuntimeError(
                    "E2E database contains a non-fixture screening run; refusing to seed over it"
                )

            orchestrator = ScreeningOrchestrator(
                security_repo=SqlSecurityRepository(session),
                ohlcv_repo=ohlcv_repo,
                screening_run_repo=run_repo,
                indicator_pipeline=IndicatorPipelineImpl(session),
                strategy_engine=StrategyEngine(
                    engines=engine_registry,
                    scoring=ScoringEngineImpl(),
                    ranking=RankingEngineImpl(),
                ),
                strategy=strategy,
                strategy_repo=strategy_repo,
                calendar=get_nse_trading_calendar(),
            )
            summary = await orchestrator.run_daily_screening(as_of, data_manifest=manifest)
            print(
                f"seeded synthetic screening snapshot for {name} on {as_of}: "
                f"evaluated={summary.total_evaluated}, passed={summary.total_passed}"
            )


if __name__ == "__main__":
    asyncio.run(main())
