"""Domain events and the event-publisher port (extension point for alerts/webhooks)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for domain events."""


@dataclass(frozen=True, slots=True)
class RunCompleted(DomainEvent):
    """Emitted when a screening run finishes successfully."""

    run_id: int
    strategy_name: str
    run_date: date


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes domain events. The MVP uses a no-op/logging implementation."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to any subscribers."""
        ...
