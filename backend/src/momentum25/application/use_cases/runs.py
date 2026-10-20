"""Run use cases: list, get, and trigger a screening refresh.

``TriggerRefresh`` creates a ``PENDING`` run row (lifecycle is real). Executing the
screening pipeline is implemented in M4; this phase establishes the trigger contract
and run lifecycle without computing scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

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

    async def execute(self, strategy_name: str, on_or_before: date | None = None) -> RunDTO | None:
        """Return the latest completed run for ``strategy_name``, or ``None``.

        With ``on_or_before`` (bar replay), the newest live or historical run dated
        that day or earlier, so a replayed chart never shows a later run.
        """
        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")
        run = (
            await self._runs.latest_completed(strategy.id)
            if on_or_before is None
            else await self._runs.latest_completed_on_or_before(strategy.id, on_or_before)
        )
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
        data_manifest_repo: Any | None = None,
    ) -> None:
        """Wire the use case with its repositories and the clock."""
        self._runs = runs
        self._strategies = strategies
        self._ohlcv = ohlcv
        self._clock = clock
        self._data_manifest_repo = data_manifest_repo

    async def execute(self, strategy_name: str, force: bool) -> TriggeredRun:
        """Create or return the exact run identity and indicate whether to schedule it.

        Resolves the strategy and current data version, then records a run in the
        ``PENDING`` state. The actual ingest+screen execution is wired in M4/M7.
        """
        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        latest = await self._ohlcv.latest_date()
        manifest = (
            await self._data_manifest_repo.capture()
            if self._data_manifest_repo is not None
            else None
        )
        data_version = (
            manifest.data_version
            if manifest is not None
            else latest.isoformat()
            if latest
            else "none"
        )
        run_date = latest or self._clock.today()
        find_by_identity = getattr(self._runs, "get_by_identity", None)
        if find_by_identity is not None:
            existing = await find_by_identity(
                strategy.id, run_date, data_version, strategy.config_hash
            )
            if existing is not None and existing.id is not None:
                if existing.status == RunStatus.FAILED:
                    existing.status = RunStatus.PENDING
                    existing.started_at = None
                    existing.finished_at = None
                    existing.error = None
                    await self._runs.update(existing)
                    session = getattr(self._runs, "_session", None)
                    if session is not None:
                        await session.commit()
                    return TriggeredRun(int(existing.id), True)
                return TriggeredRun(int(existing.id), False)

        run = ScreeningRun(
            strategy_id=strategy.id,
            run_date=run_date,
            data_version=data_version,
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.PENDING,
        )
        run_id = await self._runs.create(run)
        # A background task (run_screening_pipeline) picks this row up by id in
        # its own session immediately after this request returns -- it must be
        # committed here, not left for the request-scoped session's teardown
        # (which only closes, per _managed_session), or the row is invisible to
        # (and rolled back before) that background lookup.
        session = getattr(self._runs, "_session", None)
        if session is not None:
            await session.commit()
        return TriggeredRun(run_id, True)


@dataclass(frozen=True, slots=True)
class TriggeredRun:
    """A run identity plus whether this request owns a new background execution."""

    run_id: int
    should_execute: bool
