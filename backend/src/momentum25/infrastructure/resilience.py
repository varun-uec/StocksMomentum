"""Resilience patterns: circuit breaker, retry policies, and timeout handling.

Provides production-grade resilience for external service calls (NSE bhavcopy, Redis,
database) using the tenacity library. Circuit breakers prevent cascading failures when
downstream services are unavailable.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("resilience")

P = ParamSpec("P")
R = TypeVar("R")


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker rejects a call."""


class ServiceTimeoutError(Exception):
    """Raised when an operation exceeds its configured timeout."""


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Failing — reject requests immediately
    HALF_OPEN = auto()  # Testing if service has recovered


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Prevents cascading failures by failing fast when a service is unhealthy.
    After ``recovery_timeout`` seconds, transitions to half-open to probe recovery.

    Usage::

        breaker = CircuitBreaker("nse_bhavcopy")
        async with breaker:
            result = await provider.fetch_eod(for_date)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """Create a circuit breaker.

        Args:
            name: Circuit breaker name (used in logs and metrics).
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout: Seconds to wait before transitioning to half-open.
            half_open_max_calls: Max calls allowed in half-open state.
        """
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0

    async def __aenter__(self) -> CircuitBreaker:
        """Check if the circuit is open before allowing the call."""
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                _logger.info(
                    "circuit_half_open", circuit=self.name, recovery_timeout=self._recovery_timeout
                )
            else:
                _logger.warning(
                    "circuit_open_rejected", circuit=self.name, failure_count=self._failure_count
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Rejected after {self._failure_count} consecutive failures."
                )

        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self._half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is half-open and at capacity."
                )
            self._half_open_calls += 1

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Record success or failure and update circuit state."""
        if exc_type is None:
            self._failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                _logger.info("circuit_closed", circuit=self.name, state="recovered")
        else:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self.state = CircuitState.OPEN
                _logger.warning(
                    "circuit_opened",
                    circuit=self.name,
                    failure_count=self._failure_count,
                    threshold=self._failure_threshold,
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        _logger.info("circuit_reset", circuit=self.name)


# ── Timeout handling ─────────────────────────────────────────────────────────


async def with_timeout(
    coro: Awaitable[R],
    timeout_seconds: float,
    operation: str = "unknown",
) -> R:
    """Execute a coroutine with a timeout.

    Args:
        coro: The coroutine to execute.
        timeout_seconds: Maximum execution time in seconds.
        operation: Operation name for logging.

    Returns:
        The coroutine result.

    Raises:
        ServiceTimeoutError: If the coroutine exceeds the timeout.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        _logger.error("operation_timeout", operation=operation, timeout_seconds=timeout_seconds)
        raise ServiceTimeoutError(
            f"Operation '{operation}' timed out after {timeout_seconds}s"
        ) from None


# ── Retry decorator with circuit breaker awareness ──────────────────────────


def resilient(
    operation: str,
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
    circuit_breaker: CircuitBreaker | None = None,
    timeout_seconds: float | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator that adds retry, circuit breaker, and timeout to an async function.

    Args:
        operation: Human-readable operation name.
        max_attempts: Maximum retry attempts.
        min_wait: Minimum wait between retries (exponential backoff).
        max_wait: Maximum wait between retries.
        circuit_breaker: Optional circuit breaker to use.
        timeout_seconds: Optional timeout per attempt.

    Returns:
        A decorator wrapping the async function with resilience patterns.
    """
    from tenacity import (
        AsyncRetrying,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            retryer = AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(
                    (ServiceTimeoutError, ConnectionError, OSError)
                ),
                reraise=True,
            )

            async for attempt in retryer:
                with attempt:
                    if circuit_breaker is not None:
                        async with circuit_breaker:
                            coro = func(*args, **kwargs)
                            if timeout_seconds is not None:
                                return await with_timeout(
                                    coro, timeout_seconds, operation=operation
                                )
                            return await coro
                    else:
                        coro = func(*args, **kwargs)
                        if timeout_seconds is not None:
                            return await with_timeout(
                                coro, timeout_seconds, operation=operation
                            )
                        return await coro

            raise RuntimeError(f"Unexpected: retryer exhausted for '{operation}'")

        return cast(Callable[P, Awaitable[R]], wrapper)

    return decorator