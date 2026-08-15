"""Suggested stop-loss level: a risk-management figure, not a trade plan.

This is deliberately isolated from ``swing_targets.py`` -- it makes no
reward/target claim and carries no R-multiple or RR ratio. It answers one
question only: "if you're already in this position, where is a defensible
level to cap further downside?" It is not a prediction of where the price
is going.

Two methods, in priority order:

1. ATR-based: ``entry - k * ATR(14)``, k config-driven (``atr_multiple``).
2. Fallback when ATR14 is unavailable: the last confirmed swing-low
   (Phase 2.3 fractal support level), if it sits below entry.

If neither is available, no level can be defensibly computed.

:func:`suggest_chandelier_stop` (Phase 6.5) is the trailing variant of the same
idea and carries the same limits: it ratchets the cap up as the highest high
since entry rises, and never implies a target, a reward, or that the position
should be held.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from momentum25.domain.engines.risk import DEFAULT_ATR_STOP_MULTIPLE

# Chandelier exit defaults per Chuck LeBeau's original formulation: 3x ATR below
# the highest high of the trailing 22 sessions (~one month of trading).
DEFAULT_CHANDELIER_MULTIPLE = Decimal("3")
DEFAULT_CHANDELIER_LOOKBACK = 22


@dataclass(frozen=True, slots=True)
class StopLossSuggestion:
    """A defensible downside-cap level and the method used to derive it."""

    level: Decimal | None
    method: str  # e.g. "2xATR", "swing-low", "unavailable"


def suggest_stop_loss(
    entry: Decimal,
    atr14: Decimal | None,
    swing_support: Decimal | None,
    *,
    atr_multiple: Decimal = DEFAULT_ATR_STOP_MULTIPLE,
) -> StopLossSuggestion:
    """Suggest a stop-loss level to cap downside on an existing position.

    Not a target, not a reward figure -- see module docstring.
    """
    if atr14 is not None:
        return StopLossSuggestion(entry - atr_multiple * atr14, f"{atr_multiple}xATR")
    if swing_support is not None and swing_support < entry:
        return StopLossSuggestion(swing_support, "swing-low")
    return StopLossSuggestion(None, "unavailable")


def suggest_chandelier_stop(
    highest_high: Decimal | None,
    atr14: Decimal | None,
    *,
    atr_multiple: Decimal = DEFAULT_CHANDELIER_MULTIPLE,
    lookback: int = DEFAULT_CHANDELIER_LOOKBACK,
) -> StopLossSuggestion:
    """Suggest a trailing (chandelier) stop: ``highest_high - k * ATR(14)``.

    Anchored to the highest high of the trailing ``lookback`` sessions rather
    than to entry, so the level ratchets *up* with the trend and never down --
    that ratchet is the only difference from :func:`suggest_stop_loss`. It is
    still a downside cap and nothing else: no target, no reward estimate, no
    R-multiple, and no claim about where the price is going.

    Returns an ``unavailable`` suggestion when either input is missing; a
    chandelier level cannot be defensibly computed without both.
    """
    if highest_high is None or atr14 is None:
        return StopLossSuggestion(None, "unavailable")
    return StopLossSuggestion(
        highest_high - atr_multiple * atr14, f"{atr_multiple}xATR-chandelier({lookback})"
    )
