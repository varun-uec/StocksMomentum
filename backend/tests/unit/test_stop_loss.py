"""Unit tests for the standalone suggested-stop-loss domain function."""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.research.stop_loss import suggest_stop_loss


def test_atr_based_stop_uses_configured_multiple() -> None:
    result = suggest_stop_loss(
        entry=Decimal("100"), atr14=Decimal("5"), swing_support=Decimal("90"),
        atr_multiple=Decimal("2"),
    )
    assert result.level == Decimal("90")  # 100 - 2*5
    assert result.method == "2xATR"


def test_atr_multiple_is_config_driven_not_hardcoded() -> None:
    result = suggest_stop_loss(
        entry=Decimal("100"), atr14=Decimal("5"), swing_support=None,
        atr_multiple=Decimal("3"),
    )
    assert result.level == Decimal("85")  # 100 - 3*5
    assert result.method == "3xATR"


def test_atr_unavailable_falls_back_to_swing_low() -> None:
    result = suggest_stop_loss(
        entry=Decimal("100"), atr14=None, swing_support=Decimal("92"),
    )
    assert result.level == Decimal("92")
    assert result.method == "swing-low"


def test_atr_unavailable_and_swing_low_above_entry_is_ignored() -> None:
    result = suggest_stop_loss(
        entry=Decimal("100"), atr14=None, swing_support=Decimal("105"),
    )
    assert result.level is None
    assert result.method == "unavailable"


def test_both_unavailable() -> None:
    result = suggest_stop_loss(entry=Decimal("100"), atr14=None, swing_support=None)
    assert result.level is None
    assert result.method == "unavailable"
