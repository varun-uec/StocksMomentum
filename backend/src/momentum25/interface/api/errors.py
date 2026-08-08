"""Exception handlers mapping domain/app errors to RFC-7807 problem+json."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from momentum25.application.dto.common import ProblemDetail
from momentum25.domain.errors import Momentum25Error
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("api.errors")
_PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem(
    status: int, title: str, detail: str | None, type_: str, instance: str
) -> JSONResponse:
    body = ProblemDetail(type=type_, title=title, status=status, detail=detail, instance=instance)
    return JSONResponse(
        status_code=status, content=body.model_dump(), media_type=_PROBLEM_MEDIA_TYPE
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all application exception handlers on ``app``."""

    @app.exception_handler(Momentum25Error)
    async def _handle_domain(request: Request, exc: Momentum25Error) -> JSONResponse:
        return _problem(
            status=exc.http_status,
            title=exc.code,
            detail=str(exc),
            type_=f"urn:momentum25:error:{exc.code}",
            instance=str(request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem(
            status=422,
            title="validation_error",
            detail=str(exc.errors()),
            type_="urn:momentum25:error:validation_error",
            instance=str(request.url.path),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        _logger.error("unhandled_exception", error=str(exc), path=str(request.url.path))
        return _problem(
            status=500,
            title="internal_error",
            detail="An unexpected error occurred.",
            type_="urn:momentum25:error:internal_error",
            instance=str(request.url.path),
        )
