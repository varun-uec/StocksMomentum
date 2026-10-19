"""Screening lifecycle recovery against the dedicated isolated test database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)


@pytest.mark.asyncio
async def test_restart_fails_only_unfinished_screening_rows(db_session: AsyncSession) -> None:
    strategy = Strategy(
        name="restart_recovery_strategy",
        version=1,
        config_hash="restart-config-v1",
        config=StrategyConfig(
            name="restart_recovery_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    strategy_id = await SqlStrategyRepository(db_session).upsert(strategy)
    runs = SqlScreeningRunRepository(db_session)

    async def create(status: RunStatus, data_version: str) -> int:
        return await runs.create(
            ScreeningRun(
                strategy_id=strategy_id,
                run_date=date(2025, 1, 2),
                data_version=data_version,
                config_hash=strategy.config_hash,
                trigger=RunTrigger.MANUAL,
                status=status,
                stats={"fixture": True} if status == RunStatus.COMPLETED else {},
            )
        )

    pending_id = await create(RunStatus.PENDING, "pending-fixture")
    running_id = await create(RunStatus.RUNNING, "running-fixture")
    completed_id = await create(RunStatus.COMPLETED, "completed-fixture")
    await db_session.commit()

    assert await runs.interrupt_unfinished() == 2
    pending = await runs.get(pending_id)
    running = await runs.get(running_id)
    completed = await runs.get(completed_id)
    assert pending is not None and pending.status == RunStatus.FAILED
    assert running is not None and running.status == RunStatus.FAILED
    assert pending.error == running.error
    assert "restart" in (pending.error or "").lower()
    assert pending.finished_at is not None and running.finished_at is not None
    assert completed is not None and completed.status == RunStatus.COMPLETED
    assert completed.stats == {"fixture": True}
    assert await runs.interrupt_unfinished() == 0


@pytest.mark.asyncio
async def test_application_startup_recovers_interrupted_screening_rows(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real startup lifespan marks work left unfinished by a process exit."""
    from momentum25.main import create_app, lifespan

    strategy = Strategy(
        name="startup_recovery_strategy",
        version=1,
        config_hash="startup-recovery-v1",
        config=StrategyConfig(
            name="startup_recovery_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    strategy_id = await SqlStrategyRepository(db_session).upsert(strategy)
    runs = SqlScreeningRunRepository(db_session)
    pending_id = await runs.create(
        ScreeningRun(
            strategy_id=strategy_id,
            run_date=date(2025, 1, 3),
            data_version="restart-pending-fixture",
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.PENDING,
        )
    )
    running_id = await runs.create(
        ScreeningRun(
            strategy_id=strategy_id,
            run_date=date(2025, 1, 3),
            data_version="restart-running-fixture",
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.RUNNING,
        )
    )
    await db_session.commit()

    async def no_op_shutdown(_scheduler: object) -> None:
        return None

    monkeypatch.setattr("momentum25.main._shutdown", no_op_shutdown)
    app = create_app()
    async with lifespan(app):
        pass

    pending = await runs.get(pending_id)
    running = await runs.get(running_id)
    assert pending is not None and pending.status == RunStatus.FAILED
    assert running is not None and running.status == RunStatus.FAILED
    assert pending.finished_at is not None and running.finished_at is not None
    assert "restart" in (pending.error or "").lower()


@pytest.mark.asyncio
async def test_completed_screening_snapshot_rejects_mutation(db_session: AsyncSession) -> None:
    strategy = Strategy(
        name="immutable_recovery_strategy",
        version=1,
        config_hash="immutable-config-v1",
        config=StrategyConfig(
            name="immutable_recovery_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    strategy_id = await SqlStrategyRepository(db_session).upsert(strategy)
    runs = SqlScreeningRunRepository(db_session)
    run_id = await runs.create(
        ScreeningRun(
            strategy_id=strategy_id,
            run_date=date(2025, 1, 2),
            data_version="immutable-fixture",
            config_hash=strategy.config_hash,
            trigger=RunTrigger.MANUAL,
            status=RunStatus.COMPLETED,
            stats={"retained": 7},
        )
    )
    await db_session.commit()

    run = await runs.get(run_id)
    assert run is not None
    run.stats = {"retained": 0}
    with pytest.raises(ValueError, match="immutable"):
        await runs.update(run)


@pytest.mark.asyncio
async def test_database_connection_loss_rolls_back_a_mid_write_transaction(
    db_session: AsyncSession,
) -> None:
    """Terminate the isolated backend mid-write and prove no partial row survives."""
    pid = await db_session.scalar(text("SELECT pg_backend_pid()"))
    assert pid is not None
    db_session.add(
        SecurityModel(
            symbol="INTERRUPTED_TXN",
            name="Interrupted transaction fixture",
            exchange="NSE",
            is_active=True,
        )
    )
    await db_session.flush()

    async with get_database().engine.connect() as interruptor:
        terminated = await interruptor.scalar(
            text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
        )
    assert terminated is True
    with pytest.raises(DBAPIError):
        await db_session.commit()
    await db_session.invalidate()

    async with get_database().session() as verify:
        surviving = await verify.scalar(
            select(func.count())
            .select_from(SecurityModel)
            .where(SecurityModel.symbol == "INTERRUPTED_TXN")
        )
    assert surviving == 0
