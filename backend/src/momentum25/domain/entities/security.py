"""The ``Security`` entity — an instrument in the tradable universe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from momentum25.domain.value_objects.types import Symbol


@dataclass(frozen=True, slots=True)
class Security:
    """An equity instrument (NSE in the MVP).

    ``id`` is ``None`` for not-yet-persisted instances. ``tenant_id`` is the SaaS
    multi-tenancy extension point (NULL in the MVP, see ADR-010).
    """

    symbol: Symbol
    name: str
    id: int | None = None
    isin: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str = "NSE"
    listing_date: date | None = None
    is_active: bool = True
    tenant_id: int | None = None
