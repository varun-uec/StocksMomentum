"""HTTP middleware and problem responses shared by both applications (ADR-023 U2).

Request context (request and correlation ids, access log), security headers, the
body-size limit and the Host/Origin guard (ADR-012). Each application passes its
own error namespace and, for the request context, its own metrics hook.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from platform_common.log import get_logger

_logger = get_logger("api.access")
_PROBLEM_MEDIA_TYPE = "application/problem+json"

# Called once per request with method, path, status code and duration in seconds.
RequestObserver = Callable[[str, str, str, float], None]


def problem_response(
    status: int, title: str, detail: str | None, type_: str, instance: str
) -> JSONResponse:
    """Build an RFC-7807 ``application/problem+json`` response."""
    body = {"type": type_, "title": title, "status": status, "detail": detail, "instance": instance}
    return JSONResponse(status_code=status, content=body, media_type=_PROBLEM_MEDIA_TYPE)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request/correlation ids and observe each request.

    Logs request and response with latency, reports each request to ``observe``,
    and propagates tracing headers.
    """

    def __init__(self, app: Any, observe: RequestObserver | None = None) -> None:
        """Create the middleware; ``observe`` records metrics when given."""
        super().__init__(app)
        self._observe = observe

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Bind context, time the request, emit an access log, and report the request."""
        # Accept or generate request id and correlation id
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        correlation_id = request.headers.get("x-correlation-id", uuid.uuid4().hex[:16])

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

            if self._observe is not None:
                self._observe(method, path, status_code, elapsed_ms / 1000.0)

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


MAX_BODY_BYTES = 5 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Refuse a request body above ``MAX_BODY_BYTES`` (R3-B-23).

    The largest saved document (a workspace with its drawings) is far below the
    cap. A declared ``Content-Length`` above it gets ``413``. A body with no
    declared length (chunked) on a write gets ``411``, so the size is always known
    before the handler reads it.
    """

    def __init__(self, app: Any, *, error_namespace: str) -> None:
        """Create the limit; problem types read ``urn:<error_namespace>:error:<code>``."""
        super().__init__(app)
        self._urn = f"urn:{error_namespace}:error:"

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
                    type_=f"{self._urn}payload_too_large",
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
                type_=f"{self._urn}length_required",
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

    def __init__(
        self, app: Any, allowed_hosts: list[str], *, error_namespace: str, hosts_setting: str
    ) -> None:
        """Create the guard with the allowed host names (no ports).

        ``hosts_setting`` names the setting that extends the allowlist; the 421
        response tells the operator to use it.
        """
        super().__init__(app)
        self._allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self._urn = f"urn:{error_namespace}:error:"
        self._hosts_setting = hosts_setting

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
                f"This host name is not allowed. Add it to {self._hosts_setting} to serve it.",
                f"{self._urn}host_not_allowed",
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
                    f"{self._urn}origin_not_allowed",
                    request.url.path,
                )
        return await call_next(request)
