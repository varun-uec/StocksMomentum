"""R3-B-17: the ``data_version`` token of a historical run does not read the clock."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)


class _Runs:
    def __init__(self, total: int) -> None:
        self.total = total
        self.kwargs: dict[str, Any] = {}

    async def list_runs(self, **kwargs: Any) -> tuple[list[Any], int]:
        self.kwargs = kwargs
        return [], self.total


class _Strategies:
    async def get_active(self, name: str) -> Any:
        return SimpleNamespace(id=8)


def _use_case(runs: _Runs) -> HistoricalScreeningUseCase:
    return HistoricalScreeningUseCase(
        security_repo=None,
        ohlcv_repo=None,
        screening_run_repo=runs,
        strategy_repo=_Strategies(),
        indicator_pipeline=None,
        strategy_engine=None,
        calendar=None,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_sequence_is_stored_run_count_plus_one_and_repeats_for_the_same_state() -> None:
    runs = _Runs(total=20)
    use_case = _use_case(runs)
    assert await use_case.next_sequence("minervini_trend_template") == 21
    assert await use_case.next_sequence("minervini_trend_template") == 21
    assert runs.kwargs["strategy_id"] == 8
    assert runs.kwargs["exclude_historical"] is False
