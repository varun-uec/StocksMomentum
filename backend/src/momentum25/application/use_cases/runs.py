"""Run use cases: list, get, and trigger a screening refresh.

``TriggerRefresh`` creates a ``PENDING`` run row (lifecycle is real). Executing the
screening pipeline is implemented in M4; this phase establishes the trigger contract
and run lifecycle without computing scores.
"""

from __future__ import annotations

from momentum25.application.dto.runs import RunDTO
from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.errors import NotFoundError, StrategyNotFoundError
from momentum25.domain.ports.clock import Clock
from momentum25.domain.ports.repositories import (
    OHLCVRepository,
    ScreeningRunRepository,
    StrategyRepository,
)
from momentum25.domain.value_objects.types import RunStatus, RunTrigger


def _to_dto(run: ScreeningRun, strategy_name: str) -> RunDTO:
    return RunDTO(
        id=run.id or 0,
        status=run.status.value,
        run_date=run.run_date,
        trigger=run.trigger.value,
        strategy=strategy_name,
        data_version=run.data_version,
        config_hash=run.config_hash,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=run.stats or None,
        error=run.error,
    )


class ListRuns:
    """Return a page of screening runs."""

    def __init__(self, runs: ScreeningRunRepository, strategies: StrategyRepository) -> None:
        """Wire the use case with run and strategy repositories."""
        self._runs = runs
        self._strategies = strategies

    async def execute(
        self, status: str | None, limit: int, offset: int
    ) -> tuple[list[RunDTO], int]:
        """Return runs and total count, resolving strategy names."""
        runs, total = await self._runs.list_runs(status, limit, offset)
        by_id = {s.id: s.name for s in await self._strategies.list()}
        return [_to_dto(r, by_id.get(r.strategy_id, "unknown")) for r in runs], total


class GetRun:
    """Return a single run by id."""

    def __init__(self, runs: ScreeningRunRepository, strategies: StrategyRepository) -> None:
        """Wire the use case with run and strategy repositories."""
        self._runs = runs
        self._strategies = strategies

    async def execute(self, run_id: int) -> RunDTO:
        """Return the run or raise :class:`NotFoundError`."""
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"Run not found: {run_id}")
        by_id = {s.id: s.name for s in await self._strategies.list()}
        return _to_dto(run, by_id.get(run.strategy_id, "unknown"))


class GetLatestRunForStrategy:
    """Return the most recent completed run for a named strategy (e.g. a Momentum Horizon)."""

    def __init__(self, runs: ScreeningRunRepository, strategies: StrategyRepository) -> None:
        """Wire the use case with run and strategy repositories."""
        self._runs = runs
        self._strategies = strategies

    async def execute(self, strategy_name: str) -> RunDTO | None:
        """Return the latest completed run for ``strategy_name``, or ``None``."""
        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")
        run = await self._runs.latest_completed(strategy.id)
        if run is None:
            return None
        return _to_dto(run, strategy_name)


class TriggerRefresh:
    """Create a new screening run for a strategy (execution deferred to M4)."""

    def __init__(
        self,
        runs: ScreeningRunRepository,
        strategies: StrategyRepository,
        ohlcv: OHLCVRepository,
        clock: Clock,
    ) -> None:
        """Wire the use case with its repositories and the clock."""
        self._runs = runs
        self._strategies = strategies
        self._ohlcv = ohlcv
        self._clock = clock

    async def execute(self, strategy_name: str, force: bool) -> int:
        """Create a PENDING run and return its id.

        Resolves the strategy and current data version, then records a run in the
        ``PENDING`` state. The actual ingest+screen execution is wired in M4/M7.
        """
        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        latest = await self._ohlcv.latest_date()
        data_version = latest.isoformat() if latest else "none"

        run = ScreeningRun(
            strategy_id=strategy.id,
            run_date=self._clock.today(),
            data_version=data_version,
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.PENDING,
        )
        return await self._runs.create(run)
