"""Event publisher adapter(s).

The MVP ships a logging publisher. Future alert/webhook integrations subscribe here
without changing the screening workflow (extension point, ADD §6).
"""

from __future__ import annotations

from dataclasses import asdict

from momentum25.domain.ports.events import DomainEvent
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("events")


class LoggingEventPublisher:
    """A no-op :class:`EventPublisher` that logs published events."""

    async def publish(self, event: DomainEvent) -> None:
        """Log the domain event as a structured record."""
        _logger.info("domain_event", event_type=type(event).__name__, **asdict(event))
