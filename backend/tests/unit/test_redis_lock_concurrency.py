"""Concurrency test for :class:`RedisLockFactory` against a real Redis (Phase 1.4).

``RedisLockFactory`` existed with zero callers before this phase, written for
exactly the "don't double-run the daily job when scaled out" case
(``lock.py``'s own docstring). This proves it actually serializes concurrent
acquires against a real Redis rather than only against a mock.
"""

from __future__ import annotations

import asyncio

import pytest
import redis.asyncio as redis

from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.redis.lock import RedisLockFactory


async def _redis_available() -> bool:
    try:
        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_concurrent_daily_job_invocations_execute_pipeline_once() -> None:
    if not await _redis_available():
        pytest.skip("Redis is not reachable at the configured M25_REDIS_URL")

    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    factory = RedisLockFactory(client, namespace="m25:test:lock")
    lock_name = "concurrency_test"
    await client.delete(f"m25:test:lock:{lock_name}")

    execution_count = 0

    async def guarded_pipeline_run() -> None:
        nonlocal execution_count
        async with factory.acquire(lock_name, timeout_seconds=5) as acquired:
            if not acquired:
                return
            await asyncio.sleep(0.2)  # simulate the pipeline doing work
            execution_count += 1

    await asyncio.gather(*(guarded_pipeline_run() for _ in range(5)))

    assert execution_count == 1
    await client.aclose()
