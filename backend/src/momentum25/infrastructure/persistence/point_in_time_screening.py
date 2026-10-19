"""Historical screening adapter wired to the sealed point-in-time market view.

Older historical research routes used the live OHLCV repository and today's
cumulative adjustment factors. This adapter captures one data manifest, binds
the universe, bars, corporate actions and indicators to that revision, then
runs the same application screening use case.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.point_in_time import (
    PointInTimeIndicatorPipeline,
    PointInTimeOHLCVRepository,
    PointInTimeSecurityRepository,
    PointInTimeSource,
    current_revision,
)
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)


class PointInTimeHistoricalScreening:
    """Run and persist a historical screen against one immutable data revision."""

    def __init__(
        self,
        session: AsyncSession,
        screening_run_repo: Any,
        strategy_repo: Any,
        strategy_engine: StrategyEngine,
    ) -> None:
        """Bind the adapter to one request session and the established strategy engine."""
        self._session = session
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo
        self._strategy_engine = strategy_engine

    async def execute(
        self,
        strategy_name: str,
        as_of_date: date,
        symbol_filter: list[str] | None = None,
        run_suffix: str = "",
        enforce_listing_date_filter: bool = True,
    ) -> dict[str, Any]:
        """Capture a revision and run the application use case at that revision."""
        revision = await current_revision(self._session)
        manifest = await SqlDataManifestRepository(self._session).capture(revision)
        source = PointInTimeSource(self._session, as_of_date, revision)
        screening = HistoricalScreeningUseCase(
            security_repo=PointInTimeSecurityRepository(source),
            ohlcv_repo=PointInTimeOHLCVRepository(source),
            screening_run_repo=self._screening_run_repo,
            strategy_repo=self._strategy_repo,
            indicator_pipeline=PointInTimeIndicatorPipeline(self._session, source),
            strategy_engine=self._strategy_engine,
        )
        return await screening.execute(
            strategy_name=strategy_name,
            as_of_date=as_of_date,
            symbol_filter=symbol_filter,
            run_suffix=run_suffix,
            enforce_listing_date_filter=enforce_listing_date_filter,
            point_in_time_data_version=manifest.data_version,
            point_in_time_revision=revision,
        )
