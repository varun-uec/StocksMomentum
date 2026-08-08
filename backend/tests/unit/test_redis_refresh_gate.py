"""Tests for :class:`RedisRefreshGate` (Phase 1.3).

A Redis outage must degrade to "no cooldown", never break the live lookup
endpoint -- every call is wrapped so a broken client cannot raise out of
``should_refresh``/``mark_refreshed``.
"""

from __future__ import annotations

import pytest

from momentum25.infrastructure.redis.refresh_gate import RedisRefreshGate


class _FailingRedisClient:
    async def exists(self, key: str) -> int:
        raise ConnectionError("redis is down")

    async def set(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("redis is down")


class _WorkingRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_should_refresh_degrades_to_true_on_redis_failure() -> None:
    gate = RedisRefreshGate(_FailingRedisClient(), cooldown_seconds=300)
    assert await gate.should_refresh("RELIANCE") is True


@pytest.mark.asyncio
async def test_mark_refreshed_does_not_raise_on_redis_failure() -> None:
    gate = RedisRefreshGate(_FailingRedisClient(), cooldown_seconds=300)
    await gate.mark_refreshed("RELIANCE")  # must not raise


@pytest.mark.asyncio
async def test_cooldown_blocks_refresh_until_marked_key_expires() -> None:
    client = _WorkingRedisClient()
    gate = RedisRefreshGate(client, cooldown_seconds=300)

    assert await gate.should_refresh("RELIANCE") is True
    await gate.mark_refreshed("RELIANCE")
    assert await gate.should_refresh("RELIANCE") is False
    assert await gate.should_refresh("TCS") is True  # different symbol, own key
