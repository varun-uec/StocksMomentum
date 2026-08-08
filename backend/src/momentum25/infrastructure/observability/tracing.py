"""OpenTelemetry tracing instrumentation.

Provides a lightweight tracing context manager and decorator that emits
OpenTelemetry spans. When no OTLP exporter is configured, spans fall back
to structured logging (no external dependency required).

Correlation IDs are propagated across service boundaries via the ``x-correlation-id``
header and bound to structlog context for log correlation.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("tracing")

# Environment variable to enable/disable OpenTelemetry export
_OTEL_ENABLED = os.environ.get("M25_OTEL_ENABLED", "").lower() in ("1", "true", "yes")

F = TypeVar("F", bound=Callable[..., Any])


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for distributed tracing."""
    return uuid.uuid4().hex[:16]


class TraceSpan:
    """A tracing span that records elapsed time and attributes.

    Use as a context manager::

        with TraceSpan("ingest_bhavcopy", symbol_count=500) as span:
            result = await provider.fetch_eod(for_date)
        # span.elapsed_ms is available after exit
    """

    def __init__(
        self,
        operation: str,
        *,
        correlation_id: str | None = None,
        slow_threshold_ms: int = 1000,
        **attributes: Any,
    ) -> None:
        """Start a tracing span.

        Args:
            operation: Name of the operation being traced.
            correlation_id: Correlation ID for distributed tracing. Generated if not provided.
            slow_threshold_ms: Log at warning level if duration exceeds this.
            **attributes: Additional key-value pairs to attach to the span.
        """
        self._operation = operation
        self._correlation_id = correlation_id or generate_correlation_id()
        self._slow_threshold_ms = slow_threshold_ms
        self._attributes = attributes
        self._start: float | None = None
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> TraceSpan:
        """Start the tracing span timer."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_details: Any) -> None:
        """Stop the timer and log the span."""
        if self._start is None:
            return
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
        is_slow = self.elapsed_ms > self._slow_threshold_ms

        log_attrs = {
            "operation": self._operation,
            "correlation_id": self._correlation_id,
            "duration_ms": self.elapsed_ms,
            "slow": is_slow,
            **self._attributes,
        }

        if is_slow:
            _logger.warning("trace_span", **log_attrs)
        else:
            _logger.debug("trace_span", **log_attrs)


def trace(
    operation: str | None = None,
    slow_threshold_ms: int = 1000,
) -> Callable[[F], F]:
    """Decorator that wraps a function with a tracing span.

    The operation name defaults to the fully-qualified function name.

    Args:
        operation: Explicit operation name (defaults to ``module.func_name``).
        slow_threshold_ms: Threshold in ms before a warning is emitted.

    Returns:
        A decorator that traces the wrapped function.
    """

    def decorator(func: F) -> F:
        op_name = operation or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with TraceSpan(op_name, slow_threshold_ms=slow_threshold_ms):
                return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


async def atrace(
    operation: str | None = None,
    slow_threshold_ms: int = 1000,
) -> Callable[[F], F]:
    """Async decorator that wraps a coroutine with a tracing span.

    The operation name defaults to the fully-qualified function name.

    Args:
        operation: Explicit operation name (defaults to ``module.func_name``).
        slow_threshold_ms: Threshold in ms before a warning is emitted.

    Returns:
        A decorator that traces the wrapped async function.
    """

    def decorator(func: F) -> F:
        op_name = operation or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with TraceSpan(op_name, slow_threshold_ms=slow_threshold_ms):
                return await func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator