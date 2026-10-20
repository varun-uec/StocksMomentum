"""Resolve the exact strategy version that validation and research evidence uses."""

from __future__ import annotations

from typing import Any

from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import StrategyNotFoundError


async def resolve_evidence_strategy(
    strategy_repo: Any, strategy_name: str, config_hash: str | None
) -> Strategy:
    """Return the strategy row whose runs are the evidence.

    Without ``config_hash``: the active strategy-file definition (``get_active``),
    the behaviour before user strategies existed. With it: that exact active
    production or user version (``get_for_workspace``, ADR-014 §9). Callers
    filter runs by this row's id and config hash, so two versions of one name
    never share evidence.
    """
    strategy = (
        await strategy_repo.get_for_workspace(strategy_name, config_hash)
        if config_hash is not None
        else await strategy_repo.get_active(strategy_name)
    )
    if strategy is None:
        detail = f" with config_hash {config_hash}" if config_hash else ""
        raise StrategyNotFoundError(f"Strategy not found: {strategy_name}{detail}")
    return strategy  # type: ignore[no-any-return]
