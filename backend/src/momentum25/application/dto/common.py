"""Shared DTOs: pagination envelope and RFC-7807 problem details."""

from __future__ import annotations

from pydantic import BaseModel


class Page[T](BaseModel):
    """A paginated collection envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ProblemDetail(BaseModel):
    """RFC-7807 ``application/problem+json`` body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
