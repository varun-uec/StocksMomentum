"""HTTP middleware.

Correlation ID propagation, access logging, metrics, rate limiting, security
headers, and the Host/Origin guard.

Binds a per-request id and correlation ID into the structlog context so all logs
emitted while handling a request are correlated (NFR-10). Also records Prometheus
HTTP metrics, enforces rate limits, and sets security headers.
"""

from __future__ import annotations

import math
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
from momentum25.interface.api.errors import problem_response

_logger = get_logger("api.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request/correlation ids and observe each request.

    Logs request and response with latency, records metrics, and propagates
    tracing headers.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Bind context, time the request, emit an access log, and record metrics."""
        # Accept or generate request id and correlation id
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        correlation_id = request.headers.get("x-correlation-id", generate_correlation_id())

        structlog.contextvars.bind_contextvars(request_id=request_id, correlation_id=correlation_id)
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
            http_requests_total.labels(method=method, path=path, status_code=status_code).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(
                elapsed_ms / 1000.0
            )

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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
        )
        return response


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


MAX_BODY_BYTES = 5 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Refuse a request body above ``MAX_BODY_BYTES`` (R3-B-23).

    The largest saved document (a workspace with its drawings) is far below the
    cap. A declared ``Content-Length`` above it gets ``413``. A body with no
    declared length (chunked) on a write gets ``411``, so the size is always known
    before the handler reads it.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check the declared body size."""
        declared = request.headers.get("content-length")
        if declared is not None:
            if not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
                return problem_response(
                    status=413,
                    title="payload_too_large",
                    detail=f"Request body exceeds {MAX_BODY_BYTES} bytes.",
                    type_="urn:momentum25:error:payload_too_large",
                    instance=request.url.path,
                )
        elif (
            request.method not in ("GET", "HEAD", "OPTIONS", "DELETE")
            and "chunked" in request.headers.get("transfer-encoding", "").lower()
        ):
            return problem_response(
                status=411,
                title="length_required",
                detail="Send a Content-Length header.",
                type_="urn:momentum25:error:length_required",
                instance=request.url.path,
            )
        return await call_next(request)


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def host_name(authority: str) -> str:
    """Return the host part of ``host[:port]``, keeping IPv6 brackets."""
    if authority.startswith("["):
        return authority[: authority.find("]") + 1].lower()
    return authority.split(":", 1)[0].lower()


class HostOriginGuardMiddleware(BaseHTTPMiddleware):
    """Reject requests from the wrong host or from another site (ADR-012).

    Defence in depth for a no-login instance; it does not replace authentication.

    - ``Host`` not in the allowlist -> ``421``. This blocks DNS rebinding.
    - A state-changing request whose ``Origin`` is not this request's own origin
      (including ``Origin: null``) -> ``403``. This blocks cross-site request forgery.
    - A state-changing request with no ``Origin`` passes: browsers always send
      ``Origin`` on cross-origin writes, so only non-browser clients omit it.
    """

    def __init__(self, app: Any, allowed_hosts: list[str]) -> None:
        """Create the guard with the allowed host names (no ports)."""
        super().__init__(app)
        self._allowed_hosts = frozenset(h.lower() for h in allowed_hosts)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Apply the Host rule to every request and the Origin rule to writes."""
        host = request.headers.get("host", "")
        if host_name(host) not in self._allowed_hosts:
            _logger.warning("host_rejected", host=host, path=request.url.path)
            return problem_response(
                421,
                "Misdirected request",
                "This host name is not allowed. Add it to M25_ALLOWED_HOSTS to serve it.",
                "urn:momentum25:error:host_not_allowed",
                request.url.path,
            )

        origin = request.headers.get("origin")
        if request.method not in _SAFE_METHODS and origin is not None:
            scheme, _, authority = origin.partition("://")
            same_origin = scheme in ("http", "https") and authority.lower() == host.lower()
            if not authority or not same_origin:
                _logger.warning("origin_rejected", origin=origin, path=request.url.path)
                return problem_response(
                    403,
                    "Cross-origin request rejected",
                    "State-changing requests must come from this app's own origin.",
                    "urn:momentum25:error:origin_not_allowed",
                    request.url.path,
                )
        return await call_next(request)
