"""ISIN-first security resolution for the legacy-archive reconciliation path.

Pure, I/O-free identity resolution (ADR-009) used by the RP-012 Phase 2 legacy
overlap backfill. A legacy bhavcopy row carries the *period-correct* ticker
(the symbol as it stood on the session date) and, for the 2019+ schema, an
``ISIN``. Today's instrument master carries the *current* ticker, so a
symbol-string join silently drops any security whose ticker drifted between the
session date and now.

Resolution therefore prefers the stable ISIN identity and falls back to the
symbol string only when ISIN is absent or does not resolve — never guessing an
identity. Every outcome is classified into exactly one :class:`ResolutionPath`
so the reconciliation report can account for every legacy row (resolved by
ISIN / resolved by symbol fallback / unresolved by both) rather than only
reporting an improved aggregate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ResolutionPath(StrEnum):
    """How a legacy row was resolved to a ``security_id`` (stable, aggregatable)."""

    PERIOD_CORRECT = "period_correct_resolved"
    ISIN = "isin_resolved"
    SYMBOL_FALLBACK = "symbol_fallback_resolved"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class Resolution:
    """The outcome of resolving one legacy row's identity."""

    security_id: int | None
    path: ResolutionPath


def normalize_isin(isin: str | None) -> str | None:
    """Return an upper-cased, stripped ISIN, or ``None`` when blank/absent.

    Kept identical to the normalization applied when building ``isin_to_id`` so
    lookups are symmetric; a blank or whitespace-only cell is treated as absent
    rather than as an empty-string key.
    """
    if isin is None:
        return None
    cleaned = isin.strip().upper()
    return cleaned or None


def resolve_security(
    symbol: str,
    isin: str | None,
    symbol_to_id: Mapping[str, int],
    isin_to_id: Mapping[str, int],
) -> Resolution:
    """Resolve a legacy row to a ``security_id``, ISIN-first with symbol fallback.

    Order (RP-012 Phase 2 fast-follow):

    1. If a normalized ISIN is present and resolves in ``isin_to_id`` → ISIN.
    2. Otherwise, if the symbol resolves in ``symbol_to_id`` → symbol fallback.
    3. Otherwise → unresolved (``security_id`` is ``None``).

    Pure: the result is a deterministic function of the inputs alone.
    """
    normalized_isin = normalize_isin(isin)
    if normalized_isin is not None:
        by_isin = isin_to_id.get(normalized_isin)
        if by_isin is not None:
            return Resolution(by_isin, ResolutionPath.ISIN)

    by_symbol = symbol_to_id.get(symbol)
    if by_symbol is not None:
        return Resolution(by_symbol, ResolutionPath.SYMBOL_FALLBACK)

    return Resolution(None, ResolutionPath.UNRESOLVED)
