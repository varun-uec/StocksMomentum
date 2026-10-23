"""HTTP middleware.

Correlation ID propagation, access logging, metrics, rate limiting, security
headers, and the Host/Origin guard.

Binds a per-request id and correlation ID into the structlog context so all logs
emitted while handling a request are correlated (NFR-10). Also records Prometheus
HTTP metrics, enforces rate limits, and sets security headers.

The request context, security headers, body-size limit and Host/Origin guard live
in ``platform_common.http`` (ADR-023 U2); this module binds Momentum25's error
namespace, setting name and metrics to them.
"""

from __future__ import annotations

import math
import time
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from momentum25.infrastructure.logging.setup import get_logger
from momentum25.infrastructure.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)
from platform_common import http as platform_http
from platform_common.http import MAX_BODY_BYTES, SecurityHeadersMiddleware, host_name

__all__ = [
    "MAX_BODY_BYTES",
    "BodySizeLimitMiddleware",
    "HostOriginGuardMiddleware",
    "RateLimitMiddleware",
    "RequestContextMiddleware",
    "SecurityHeadersMiddleware",
    "host_name",
]

_logger = get_logger("api.access")
_ERROR_NAMESPACE = "momentum25"


def _record_metrics(method: str, path: str, status_code: str, seconds: float) -> None:
    http_requests_total.labels(method=method, path=path, status_code=status_code).inc()
    http_request_duration_seconds.labels(method=method, path=path).observe(seconds)


class RequestContextMiddleware(platform_http.RequestContextMiddleware):
    """Request context that records Momentum25's Prometheus HTTP metrics."""

    def __init__(self, app: Any) -> None:
        """Create the middleware with the Momentum25 metrics hook."""
        super().__init__(app, observe=_record_metrics)


class BodySizeLimitMiddleware(platform_http.BodySizeLimitMiddleware):
    """Body-size limit with Momentum25 problem types."""

    def __init__(self, app: Any) -> None:
        """Create the limit in the ``momentum25`` error namespace."""
        super().__init__(app, error_namespace=_ERROR_NAMESPACE)


class HostOriginGuardMiddleware(platform_http.HostOriginGuardMiddleware):
    """Host/Origin guard (ADR-012) with Momentum25 problem types and setting name."""

    def __init__(self, app: Any, allowed_hosts: list[str]) -> None:
        """Create the guard; ``M25_ALLOWED_HOSTS`` extends the allowlist."""
        super().__init__(
            app,
            allowed_hosts,
            error_namespace=_ERROR_NAMESPACE,
            hosts_setting="M25_ALLOWED_HOSTS",
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-process rate limiter.

    Uses a sliding window counter stored in memory. For distributed rate limiting,
    swap for a Redis-backed implementation.

    ``M25_RATE_LIMIT_MAX_REQUESTS``: max requests per client IP and window
    (default 1200). ``M25_RATE_LIMIT_WINDOW_SECONDS``: window in seconds
    (default 60). A refused request gets ``429`` with ``Retry-After`` and a
    problem body that states the same number of seconds.
    """

    def __init__(
        self,
        app: Any,
        max_requests: int = 1200,
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
        # Limit API calls only: health checks and the web app's static files
        # (one page load fetches many) are not API traffic.
        path = request.url.path
        if not path.startswith("/api/") or path.startswith("/api/v1/health"):
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

        window = self._requests.get(client_ip, [])
        if len(window) >= self._max_requests:
            # The oldest request in the window leaves it first; then one fits.
            retry_after = max(1, math.ceil(window[0] + self._window_seconds - now))
            _logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
                retry_after_seconds=retry_after,
            )
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                media_type="application/problem+json",
                headers={"Retry-After": str(retry_after)},
                content={
                    "type": "urn:momentum25:error:rate_limit_exceeded",
                    "title": "rate_limit_exceeded",
                    "status": 429,
                    "detail": f"Too many requests. Retry in {retry_after} s.",
                    "instance": request.url.path,
                    "retry_after_seconds": retry_after,
                },
            )

        self._requests.setdefault(client_ip, []).append(now)
        return await call_next(request)
