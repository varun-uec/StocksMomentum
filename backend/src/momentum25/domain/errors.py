"""Domain and application error hierarchy.

These exceptions are transport-agnostic. The API layer maps them to RFC-7807
problem+json responses (see ``interface/api/errors.py``). Domain *data* problems
(e.g. insufficient history) are **not** exceptions — they are represented as failed
``RuleResult`` values with explanations (see ``IMPLEMENTATION_SPEC.md`` §13).
"""

from __future__ import annotations


class Momentum25Error(Exception):
    """Base class for all application-defined errors."""

    code: str = "momentum25_error"
    http_status: int = 500


class DomainError(Momentum25Error):
    """A violated domain invariant or programming error in the pure core."""

    code = "domain_error"
    http_status = 500


class NotFoundError(Momentum25Error):
    """A requested resource does not exist."""

    code = "not_found"
    http_status = 404


class ConflictError(Momentum25Error):
    """The request conflicts with current state (e.g. duplicate run)."""

    code = "conflict"
    http_status = 409


class ValidationError(Momentum25Error):
    """Input failed validation beyond what the schema enforces."""

    code = "validation_error"
    http_status = 422


class ProviderUnavailableError(Momentum25Error):
    """An external data provider could not be reached or returned an error."""

    code = "provider_unavailable"
    http_status = 503


class StrategyNotFoundError(NotFoundError):
    """The named strategy is not registered."""

    code = "strategy_not_found"


class RunAlreadyExistsError(ConflictError):
    """A completed run already exists for the same (strategy, data, config)."""

    code = "run_already_exists"


class NoEligibleUniverseError(DomainError):
    """No securities passed the universe eligibility filters."""

    code = "no_eligible_universe"
    http_status = 422
