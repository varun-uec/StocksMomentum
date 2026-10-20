"""A second run with an existing identity is a conflict, not an unhandled error."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.errors import RunAlreadyExistsError
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.config.strategy_loader import load_strategy_file
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)

_STRATEGY_FILE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)


def _run(strategy_id: int) -> ScreeningRun:
    return ScreeningRun(
        strategy_id=strategy_id,
        run_date=date(2026, 10, 19),
        data_version="abc123def456",
        config_hash="f" * 64,
        trigger=RunTrigger.MANUAL,
        status=RunStatus.PENDING,
    )


async def test_duplicate_identity_raises_conflict_and_keeps_the_first_run(
    db_session: AsyncSession,
) -> None:
    # Regression R3-B: two concurrent POST /runs/execute both passed the
    # identity check; the loser's INSERT hit the unique constraint and the API
    # answered 500. The repository now raises RunAlreadyExistsError (409).
    strategy_id = int(
        await SqlStrategyRepository(db_session).upsert(load_strategy_file(_STRATEGY_FILE))
    )
    runs = SqlScreeningRunRepository(db_session)
    first = await runs.create(_run(strategy_id))
    await db_session.commit()

    with pytest.raises(RunAlreadyExistsError):
        await runs.create(_run(strategy_id))

    kept = await runs.get(first)
    assert kept is not None and kept.status == RunStatus.PENDING
