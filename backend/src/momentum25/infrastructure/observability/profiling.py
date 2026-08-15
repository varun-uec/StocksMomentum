"""Performance profiling hooks.

Provides a context manager and decorator for tracing slow operations
without external dependencies. Integrates with the structured logging
system to emit profiling events.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("profiling")

_SLOW_THRESHOLD_MS = 500  # Log warning when operation exceeds this


class ProfileSpan:
    """A profiling span that records elapsed time on exit.

    Use as a context manager::

        with ProfileSpan("indicator_pipeline", symbol="RELIANCE") as span:
            result = pipeline.compute(bars)
    """

    def __init__(
        self,
        operation: str,
        slow_threshold_ms: int = _SLOW_THRESHOLD_MS,
        **context: Any,
    ) -> None:
        """Start a profiling span.

        Args:
            operation: Name of the operation being profiled.
            slow_threshold_ms: Log at warning level if duration exceeds this.
            **context: Additional key-value pairs to include in the log event.
        """
        self._operation = operation
        self._slow_threshold_ms = slow_threshold_ms
        self._context = context
        self._start: float | None = None

    def __enter__(self) -> ProfileSpan:
        """Start the timer."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_details: Any) -> None:
        """Stop the timer and log the span if it exceeded the slow threshold."""
        if self._start is None:
            return
        elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
        if elapsed_ms > self._slow_threshold_ms:
            _logger.warning(
                "profile_span",
                operation=self._operation,
                duration_ms=elapsed_ms,
                slow=True,
                **self._context,
            )
        else:
            _logger.debug(
                "profile_span",
                operation=self._operation,
                duration_ms=elapsed_ms,
                slow=False,
                **self._context,
            )


F = TypeVar("F", bound=Callable[..., Any])


def trace(
    operation: str | None = None,
    slow_threshold_ms: int = _SLOW_THRESHOLD_MS,
) -> Callable[[F], F]:
    """Decorator that wraps a function with a profiling span.

    The operation name defaults to the fully-qualified function name.

    Args:
        operation: Explicit operation name (defaults to ``module.func_name``).
        slow_threshold_ms: Threshold in ms before a warning is emitted.

    Returns:
        A decorator that profiles the wrapped function.
    """

    def decorator(func: F) -> F:
        op_name = operation or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with ProfileSpan(op_name, slow_threshold_ms=slow_threshold_ms):
                return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator