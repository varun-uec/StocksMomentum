"""Tests that the daily screening job actually fires, not just registers (Phase 1.4).

``register_daily_job`` had zero callers before this phase: ``scheduler.start()``
always started an ``AsyncIOScheduler`` with an empty job store, so nothing ever
ran automatically. These tests exercise the real ``AsyncIOScheduler`` the
service wraps -- registering, starting, and waiting for an actual execution --
rather than only asserting that ``add_job`` was called.
"""

from __future__ import annotations

import asyncio

import pytest
from apscheduler.triggers.interval import IntervalTrigger

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.scheduler.scheduler import SchedulerService


def _settings(**overrides: object) -> Settings:
    return Settings(scheduler_enabled=True, **overrides)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_registered_job_actually_executes() -> None:
    """A job registered and started must run, not merely appear in the job store.

    ``register_daily_job`` builds a ``CronTrigger`` from ``schedule_cron``,
    whose minimum resolution is a minute -- too slow to wait out in a test.
    This exercises the same underlying ``AsyncIOScheduler`` instance with a
    sub-second ``IntervalTrigger`` instead, which is the part that actually
    proves execution (not just registration); the cron-string parsing itself
    is covered separately by ``settings.py``'s own validator.
    """
    calls = 0

    async def job() -> None:
        nonlocal calls
        calls += 1

    service = SchedulerService(_settings())
    service._scheduler.add_job(job, trigger=IntervalTrigger(seconds=0.2), id="test_job")
    service.start()
    try:
        await asyncio.sleep(0.7)
    finally:
        service.shutdown()

    assert calls >= 2


@pytest.mark.asyncio
async def test_job_count_reflects_registration_before_start() -> None:
    async def job() -> None:
        pass

    service = SchedulerService(_settings())
    assert service.get_job_count() == 0

    service.register_daily_job(job)
    assert service.get_job_count() == 1

    service.start()
    try:
        assert service.get_job_count() == 1
    finally:
        service.shutdown()


@pytest.mark.asyncio
async def test_disabled_scheduler_never_starts_even_if_registered() -> None:
    async def job() -> None:
        pass

    service = SchedulerService(Settings(scheduler_enabled=False))
    service.register_daily_job(job)
    service.start()
    try:
        assert service._scheduler.running is False
    finally:
        service.shutdown()
