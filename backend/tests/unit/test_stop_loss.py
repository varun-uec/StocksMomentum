"""Unit tests for the standalone suggested-stop-loss domain function."""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.research.stop_loss import suggest_chandelier_stop, suggest_stop_loss


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


# ── Phase 6.5: trailing (chandelier) stop ─────────────────────────────────


def test_chandelier_stop_is_atr_multiple_below_the_highest_high() -> None:
    result = suggest_chandelier_stop(highest_high=Decimal("120"), atr14=Decimal("5"))
    assert result.level == Decimal("105")  # 120 - 3*5
    assert result.method == "3xATR-chandelier(22)"


def test_chandelier_multiple_and_lookback_are_config_driven() -> None:
    result = suggest_chandelier_stop(
        highest_high=Decimal("120"), atr14=Decimal("5"),
        atr_multiple=Decimal("2"), lookback=10,
    )
    assert result.level == Decimal("110")
    assert result.method == "2xATR-chandelier(10)"


def test_chandelier_ratchets_up_with_a_rising_high_and_never_down() -> None:
    atr = Decimal("5")
    early = suggest_chandelier_stop(highest_high=Decimal("120"), atr14=atr)
    later = suggest_chandelier_stop(highest_high=Decimal("140"), atr14=atr)
    assert later.level is not None
    assert early.level is not None
    assert later.level > early.level


def test_chandelier_requires_both_inputs() -> None:
    assert suggest_chandelier_stop(highest_high=None, atr14=Decimal("5")).level is None
    assert suggest_chandelier_stop(highest_high=Decimal("120"), atr14=None).level is None
    assert suggest_chandelier_stop(highest_high=None, atr14=None).method == "unavailable"
