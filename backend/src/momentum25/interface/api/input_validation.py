"""Input validation hardening for API endpoints.

Provides reusable validation functions and Pydantic-based sanitization
for common input patterns. This supplements FastAPI's built-in validation
with domain-specific checks.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from fastapi import HTTPException

# ── Symbol validation ────────────────────────────────────────────────────────

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,20}$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize a stock symbol.

    Args:
        symbol: The stock symbol to validate.

    Returns:
        The normalized (uppercase, stripped) symbol.

    Raises:
        HTTPException 422: If the symbol is invalid.
    """
    normalized = symbol.strip().upper()
    if not _SYMBOL_PATTERN.match(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid symbol format: '{symbol}'. "
            f"Symbols must be 1-20 uppercase alphanumeric characters.",
        )
    return normalized


# ── Date range validation ────────────────────────────────────────────────────

_MAX_DATE_RANGE_DAYS = 365 * 10  # 10 years


def validate_date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    """Validate and constrain a date range.

    Args:
        start_date: Inclusive start date. Defaults to 1 year ago.
        end_date: Inclusive end date. Defaults to today.

    Returns:
        A validated (start_date, end_date) tuple.

    Raises:
        HTTPException 422: If the date range is invalid.
    """
    now = datetime.now(UTC).date()
    if end_date is None:
        end_date = now
    if start_date is None:
        start_date = end_date.replace(year=end_date.year - 1)

    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail=f"start_date ({start_date}) must be before end_date ({end_date})",
        )

    if end_date > now:
        raise HTTPException(
            status_code=422,
            detail=f"end_date ({end_date}) cannot be in the future",
        )

    range_days = (end_date - start_date).days
    if range_days > _MAX_DATE_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range exceeds maximum of {_MAX_DATE_RANGE_DAYS} days "
            f"({range_days} requested)",
        )

    return start_date, end_date


# ── Pagination validation ────────────────────────────────────────────────────

_MAX_PAGE_SIZE = 1000
_DEFAULT_PAGE_SIZE = 50


def validate_pagination(page: int = 1, page_size: int = _DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    """Validate and normalize pagination parameters.

    Args:
        page: 1-based page number.
        page_size: Number of items per page.

    Returns:
        A validated (page, page_size) tuple.

    Raises:
        HTTPException 422: If pagination parameters are invalid.
    """
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail=f"page must be >= 1, got {page}",
        )

    if page_size < 1:
        raise HTTPException(
            status_code=422,
            detail=f"page_size must be >= 1, got {page_size}",
        )

    if page_size > _MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=422,
            detail=f"page_size must be <= {_MAX_PAGE_SIZE}, got {page_size}",
        )

    return page, page_size


# ── Strategy name validation ─────────────────────────────────────────────────

_STRATEGY_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-. ]{1,100}$")


def validate_strategy_name(name: str) -> str:
    """Validate a strategy name.

    Args:
        name: The strategy name to validate.

    Returns:
        The validated (stripped) strategy name.

    Raises:
        HTTPException 422: If the name is invalid.
    """
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="Strategy name cannot be empty")
    if not _STRATEGY_NAME_PATTERN.match(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy name format: '{name}'. "
            f"Strategy names can contain letters, numbers, hyphens, underscores, dots, and spaces.",
        )
    return normalized