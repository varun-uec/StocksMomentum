"""Domain ports — the interfaces that the infrastructure layer implements.

Ports invert dependencies (ADR-001): the pure core declares what it needs; adapters
provide it. All repository ports are async to match the SQLAlchemy async stack.
"""

from momentum25.domain.ports.clock import Clock
from momentum25.domain.ports.events import DomainEvent, EventPublisher, RunCompleted
from momentum25.domain.ports.market_data import (
    MarketDataProvider,
    RawBar,
    RawCorporateAction,
    RawIndexBar,
    RawInstrument,
)
from momentum25.domain.ports.repositories import (
    BenchmarkIndexRepository,
    CorporateActionRepository,
    OHLCVRepository,
    ScreeningRunRepository,
    SecurityRepository,
    StrategyRepository,
)

__all__ = [
    "BenchmarkIndexRepository",
    "Clock",
    "CorporateActionRepository",
    "DomainEvent",
    "EventPublisher",
    "MarketDataProvider",
    "OHLCVRepository",
    "RawBar",
    "RawCorporateAction",
    "RawIndexBar",
    "RawInstrument",
    "RunCompleted",
    "ScreeningRunRepository",
    "SecurityRepository",
    "StrategyRepository",
]
