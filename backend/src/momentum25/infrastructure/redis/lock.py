"""Distributed locking backed by Redis.

Used to serialize screening runs across processes/replicas (e.g. ensure a single
scheduled run executes when the worker is scaled out). The MVP runs single-host, but
the abstraction is provided so the future queue/worker split needs no new design.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol, runtime_checkable

import redis.asyncio as redis
from redis.exceptions import LockError


@runtime_checkable
class DistributedLock(Protocol):
    """Acquires a named, mutually-exclusive lock with a timeout."""

    @asynccontextmanager
    def acquire(self, name: str, *, timeout_seconds: int) -> AsyncIterator[bool]:
        """Yield whether the lock was acquired; release on exit."""
        ...


class RedisLockFactory:
    """Creates Redis-backed locks (thin wrapper over ``redis.asyncio`` locks)."""

    def __init__(self, client: redis.Redis, *, namespace: str = "m25:lock") -> None:
        """Bind the factory to a Redis client and key namespace."""
        self._client = client
        self._ns = namespace

    @asynccontextmanager
    async def acquire(
        self, name: str, *, timeout_seconds: int = 600
    ) -> AsyncIterator[bool]:
        """Acquire a non-blocking lock named ``name``.

        Yields ``True`` if acquired (and releases on exit), ``False`` otherwise.
        """
        lock = self._client.lock(f"{self._ns}:{name}", timeout=timeout_seconds, blocking=False)
        acquired = await lock.acquire()
        try:
            yield bool(acquired)
        finally:
            if acquired:
                with contextlib.suppress(LockError):
                    await lock.release()
