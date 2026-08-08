"""Unit tests for the pure market-context analytics (Phase 6.2/6.6/6.7)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.analytics.market_context import (
    BREADTH_52W_WINDOW,
    compute_market_breadth,
    compute_sector_relative_strength,
    relative_strength_vs_index,
)

_START = date(2024, 1, 1)


def _dated(values: list[Decimal]) -> dict[date, Decimal]:
    """Map a close series onto consecutive dates starting at ``_START``."""
    return {_START + timedelta(days=i): v for i, v in enumerate(values)}


def _flat_then(last: Decimal, length: int, base: Decimal = Decimal("100")) -> list[Decimal]:
    """A series of ``length`` closes: all ``base`` except the final ``last``."""
    return [base] * (length - 1) + [last]


# ── 6.2 relative strength vs index ────────────────────────────────────────


def test_excess_return_is_stock_minus_index_over_each_period() -> None:
    # 300 sessions: stock doubles over the last 22, index is flat.
    stock = _dated([Decimal("100")] * 279 + [Decimal("200")] * 21)
    index = _dated([Decimal("50")] * 300)

    points = {p.period: p for p in relative_strength_vs_index(stock, index)}

    one_month = points["1m"]
    assert one_month.stock_return_pct == Decimal("100.0000")
    assert one_month.index_return_pct == Decimal("0.0000")
    assert one_month.excess_return_pct == Decimal("100.0000")


def test_periods_without_enough_common_history_are_none_not_zero() -> None:
    stock = _dated([Decimal("100")] * 30)
    index = _dated([Decimal("50")] * 30)

    points = {p.period: p for p in relative_strength_vs_index(stock, index)}

    assert points["1m"].excess_return_pct == Decimal("0.0000")  # 22 sessions: measurable
    for period in ("3m", "6m", "12m"):
        assert points[period].stock_return_pct is None
        assert points[period].excess_return_pct is None


def test_both_legs_are_measured_over_the_same_common_sessions() -> None:
    """The index must not be measured over sessions the stock does not have.

    The index alone has 300 closes -- enough for a 12-month figure -- but the two
    series only overlap on 30 dates. Reporting a 12m index return here (against a
    stock 12m of ``None``) would put a real number next to a missing one and
    invite the reader to difference them.
    """
    full_index = _dated([Decimal("50")] * 279 + [Decimal("90")] * 21)
    stock = {d: Decimal("100") for d in sorted(full_index)[-30:]}

    points = {p.period: p for p in relative_strength_vs_index(stock, full_index)}

    assert points["1m"].index_return_pct is not None  # 22 common sessions
    for period in ("3m", "6m", "12m"):
        assert points[period].index_return_pct is None
        assert points[period].stock_return_pct is None


# ── 6.6 market breadth ────────────────────────────────────────────────────


def test_breadth_counts_above_and_below_each_average() -> None:
    universe = {
        # 252 closes, last one clearly above/below the flat 100 average.
        "UP": _flat_then(Decimal("120"), BREADTH_52W_WINDOW),
        "DOWN": _flat_then(Decimal("80"), BREADTH_52W_WINDOW),
    }

    breadth = compute_market_breadth(date(2026, 1, 1), universe)

    assert breadth.evaluated == 2
    assert breadth.above_sma50 == 1
    assert breadth.above_sma50_of == 2
    assert breadth.pct_above_sma50 == Decimal("50.0000")
    assert breadth.above_sma200 == 1
    assert breadth.pct_above_sma200 == Decimal("50.0000")


def test_short_history_is_excluded_from_the_long_average_denominator() -> None:
    """A 100-bar security can be measured against SMA50 but not SMA200."""
    universe = {
        "LONG": _flat_then(Decimal("120"), BREADTH_52W_WINDOW),
        "SHORT": _flat_then(Decimal("120"), 100),
    }

    breadth = compute_market_breadth(date(2026, 1, 1), universe)

    assert breadth.above_sma50_of == 2
    assert breadth.above_sma200_of == 1  # SHORT is excluded, not counted as a failure
    assert breadth.pct_above_sma200 == Decimal("100.0000")


def test_new_52w_high_and_low_counts() -> None:
    universe = {
        "HIGH": [Decimal(str(100 + i)) for i in range(BREADTH_52W_WINDOW)],
        "LOW": [Decimal(str(400 - i)) for i in range(BREADTH_52W_WINDOW)],
        "MIDDLE": _flat_then(Decimal("100"), BREADTH_52W_WINDOW, base=Decimal("100")),
        "TOO_SHORT": _flat_then(Decimal("100"), 50),
    }

    breadth = compute_market_breadth(date(2026, 1, 1), universe)

    assert breadth.new_52w_highs == 2  # HIGH, and flat MIDDLE ties its own max
    assert breadth.new_52w_lows == 2  # LOW, and flat MIDDLE ties its own min
    assert breadth.high_low_of == 3  # TOO_SHORT cannot be evaluated


def test_empty_universe_reports_none_rather_than_zero_percent() -> None:
    breadth = compute_market_breadth(date(2026, 1, 1), {})

    assert breadth.evaluated == 0
    assert breadth.pct_above_sma50 is None
    assert breadth.pct_above_sma200 is None


# ── 6.7 sector relative strength ──────────────────────────────────────────


def _excess(**periods: str | None) -> dict[str, Decimal | None]:
    return {k: (None if v is None else Decimal(v)) for k, v in periods.items()}


def test_sector_means_are_equal_weighted_and_ranked_by_3m() -> None:
    excess_by_symbol = {
        "A": _excess(**{"1m": "1", "3m": "10"}),
        "B": _excess(**{"1m": "3", "3m": "20"}),
        "C": _excess(**{"1m": "5", "3m": "5"}),
    }
    sectors = {"A": "IT", "B": "IT", "C": "Pharma"}

    result = compute_sector_relative_strength(excess_by_symbol, sectors)

    assert [s.sector for s in result] == ["IT", "Pharma"]
    assert [s.rank for s in result] == [1, 2]
    assert result[0].constituents == 2
    assert result[0].excess_return_pct["3m"] == Decimal("15.0000")  # (10 + 20) / 2
    assert result[0].excess_return_pct["1m"] == Decimal("2.0000")


def test_unclassified_symbols_are_excluded_not_bucketed() -> None:
    excess_by_symbol = {
        "A": _excess(**{"3m": "10"}),
        "NOSECTOR": _excess(**{"3m": "99"}),
        "BLANK": _excess(**{"3m": "99"}),
    }
    sectors: dict[str, str | None] = {"A": "IT", "NOSECTOR": None, "BLANK": "   "}

    result = compute_sector_relative_strength(excess_by_symbol, sectors)

    assert [s.sector for s in result] == ["IT"]
    assert result[0].constituents == 1


def test_unmeasurable_period_is_none_and_sorts_last() -> None:
    excess_by_symbol = {
        "A": _excess(**{"3m": None}),
        "B": _excess(**{"3m": "1"}),
    }
    sectors = {"A": "Unmeasured", "B": "Measured"}

    result = compute_sector_relative_strength(excess_by_symbol, sectors)

    assert [s.sector for s in result] == ["Measured", "Unmeasured"]
    assert result[1].excess_return_pct["3m"] is None


def test_sector_ranking_is_deterministic_for_tied_sectors() -> None:
    excess_by_symbol = {"A": _excess(**{"3m": "5"}), "B": _excess(**{"3m": "5"})}
    sectors = {"A": "Zeta", "B": "Alpha"}

    first = compute_sector_relative_strength(excess_by_symbol, sectors)
    second = compute_sector_relative_strength(excess_by_symbol, sectors)

    assert [s.sector for s in first] == ["Alpha", "Zeta"]  # name breaks the tie
    assert first == second
