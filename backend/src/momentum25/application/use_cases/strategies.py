"""Strategy read use cases."""

from __future__ import annotations

from momentum25.application.dto.strategies import StrategyDetailDTO, StrategySummaryDTO
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import StrategyNotFoundError
from momentum25.domain.ports.repositories import StrategyRepository
from momentum25.infrastructure.config.strategy_loader import raw_from_config


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

    async def execute(self, with_runs: bool = False) -> list[StrategySummaryDTO]:
        """Return strategy summaries.

        ``with_runs=True`` restricts the list to strategies with at least one
        completed live run -- the set that can back a strategy selector
        without ever presenting an option that renders an empty dashboard.
        """
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
