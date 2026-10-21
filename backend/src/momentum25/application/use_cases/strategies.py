"""Strategy read use cases."""

from __future__ import annotations

from momentum25.application.dto.strategies import StrategyDetailDTO, StrategySummaryDTO
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import StrategyNotFoundError
from momentum25.domain.ports.repositories import StrategyRepository
from momentum25.domain.strategy.config_codec import raw_from_config


def _summary(s: Strategy) -> StrategySummaryDTO:
    return StrategySummaryDTO(
        id=s.id or 0,
        name=s.name,
        version=s.version,
        is_active=s.is_active,
        kind=s.kind,
        config_hash=s.config_hash,
        description=s.config.description,
    )


class ListStrategies:
    """Return all registered strategies."""

    def __init__(self, strategies: StrategyRepository) -> None:
        """Wire the use case with the strategy repository."""
        self._strategies = strategies

    async def execute(
        self, with_runs: bool = False, workspace: bool = False
    ) -> list[StrategySummaryDTO]:
        """Return strategy summaries.

        In the workspace, ``with_runs=True`` restricts versions to those with
        completed live runs. The unfiltered workspace list also exposes saved
        versions without a run so the UI can show an actionable empty state.
        """
        if workspace:
            strategies = await self._strategies.list_for_workspace(
                include_users=True, with_runs=with_runs
            )
        else:
            strategies = (
                await self._strategies.list_with_completed_runs()
                if with_runs
                else await self._strategies.list()
            )
        return [_summary(s) for s in strategies]


class GetStrategy:
    """Return a single strategy with its full configuration."""

    def __init__(self, strategies: StrategyRepository) -> None:
        """Wire the use case with the strategy repository."""
        self._strategies = strategies

    async def execute(self, name: str) -> StrategyDetailDTO:
        """Return the active strategy named ``name`` or raise if missing."""
        strategy = await self._strategies.get_active(name)
        if strategy is None:
            raise StrategyNotFoundError(f"Strategy not found: {name}")
        return StrategyDetailDTO(
            **_summary(strategy).model_dump(),
            config=raw_from_config(strategy.config),
        )
