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
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

DEFAULT_ATR_STOP_MULTIPLE = Decimal("2")


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
