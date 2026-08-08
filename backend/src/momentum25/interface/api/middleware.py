"""HTTP middleware: correlation ID propagation, access logging, metrics, rate limiting, and security headers.

Binds a per-request id and correlation ID into the structlog context so all logs
emitted while handling a request are correlated (NFR-10). Also records Prometheus
HTTP metrics, enforces rate limits, and sets security headers.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from momentum25.infrastructure.logging.setup import get_logger
from momentum25.infrastructure.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)
from momentum25.infrastructure.observability.tracing import generate_correlation_id

_logger = get_logger("api.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds request id and correlation ID, logs request/response with latency,
    records metrics, and propagates tracing headers."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Bind context, time the request, emit an access log, and record metrics."""
        # Accept or generate request id and correlation id
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        correlation_id = request.headers.get(
            "x-correlation-id", generate_correlation_id()
        )

        structlog.contextvars.bind_contextvars(
            request_id=request_id, correlation_id=correlation_id
        )
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except BaseException:
            status_code = "500"
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            path = request.url.path
            method = request.method

            # Record Prometheus metrics
            http_requests_total.labels(
                method=method, path=path, status_code=status_code
            ).inc()
            http_request_duration_seconds.labels(
                method=method, path=path
            ).observe(elapsed_ms / 1000.0)

            _logger.info(
                "http_request",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=elapsed_ms,
            )
            structlog.contextvars.clear_contextvars()

        # Propagate tracing headers
        if response is not None:
            response.headers["x-request-id"] = request_id
            response.headers["x-correlation-id"] = correlation_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security-related HTTP headers to every response.

    Implements recommended headers from OWASP Secure Headers Project.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-process rate limiter.

    Uses a sliding window counter stored in memory. For distributed rate limiting,
    swap for a Redis-backed implementation.

    ``M25_RATE_LIMIT``: max requests per window (default 200).
    ``M25_RATE_LIMIT_WINDOW``: window size in seconds (default 60).
    """

    def __init__(
        self,
        app: Any,
        max_requests: int = 200,
        window_seconds: int = 60,
    ) -> None:
        """Create the rate limiter middleware.

        Args:
            app: The ASGI application.
            max_requests: Maximum requests allowed per window.
            window_seconds: Sliding window duration in seconds.
        """
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._last_sweep = time.time()

    def _cleanup(self, client_ip: str, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - self._window_seconds
        timestamps = self._requests.get(client_ip, [])
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

    def _sweep_idle_clients(self, now: float) -> None:
        """Evict IPs with no requests in the current window.

        ``_cleanup`` only prunes the *current* request's IP, so a distinct IP
        that never comes back would otherwise stay in ``_requests`` forever --
        an unbounded-growth memory leak under scan/probe traffic. Runs at most
        once per window.
        """
        if now - self._last_sweep < self._window_seconds:
            return
        self._last_sweep = now
        cutoff = now - self._window_seconds
        stale = [ip for ip, ts in self._requests.items() if not ts or max(ts) <= cutoff]
        for ip in stale:
            del self._requests[ip]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Enforce rate limit for the client IP."""
        # Skip rate limiting for health/metrics endpoints
        if request.url.path.startswith(("/api/v1/health", "/metrics", "/docs", "/openapi")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Wall-clock, not perf_counter: this window is compared against a
        # fixed number of seconds and (via _sweep_idle_clients) against
        # itself across dispatch calls, so it must mean the same thing on
        # every call -- perf_counter's origin is arbitrary per-process and
        # is not meant for that kind of persisted comparison.
        now = time.time()
        self._sweep_idle_clients(now)
        self._cleanup(client_ip, now)

        if len(self._requests.get(client_ip, [])) >= self._max_requests:
            _logger.warning(
                "rate_limit_exceeded", client_ip=client_ip, path=request.url.path
            )
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={
                    "title": "rate_limit_exceeded",
                    "status": 429,
                    "detail": "Too many requests. Please try again later.",
                },
            )

        self._requests.setdefault(client_ip, []).append(now)
        return await call_next(request)
