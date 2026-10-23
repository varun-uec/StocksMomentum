"""Methodology v1 on hand-built series: formulas, anchors, states, classification."""

from __future__ import annotations

import math
import statistics
from dataclasses import replace
from datetime import date, timedelta

import pytest

from wickstreet.analytics.domain import classify
from wickstreet.analytics.domain.fields import FIELDS, attributes, ordered
from wickstreet.analytics.domain.metrics import (
    ANNUALISE_VOL,
    GAP_AT_START,
    GAP_IN_WINDOW,
    HISTORY_TOO_SHORT,
    NO_NAV,
    NO_RECENT_NAV,
    Missing,
    compute,
    drawdown,
    months_back,
    rolling,
    volatility,
)
from wickstreet.analytics.domain.peers import absent_fields
from wickstreet.analytics.domain.snapshot import FundRow, decode, encode
from wickstreet.mf_data.domain.reads import FundRecord


def o(text: str) -> int:
    return date.fromisoformat(text).toordinal()


def series(*points: tuple[str, float | None]) -> list[tuple[int, float | None, str | None]]:
    return [(o(day), nav, None) for day, nav in points]


FUND = FundRecord(
    plan_option_id=1,
    amfi_code="10001",
    amc="Example AMC",
    scheme_name="Example Dividend Yield Fund",
    nav_name="Example Dividend Yield Fund - Direct Plan - Growth",
    scheme_type="Open Ended",
    category="Equity Schemes - Large Cap Fund",
    plan=None,
    option=None,
    isin_growth=None,
    isin_reinvest=None,
    launch_date=None,
)


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        ("2024-03-31", 1, "2024-02-29"),
        ("2023-03-31", 1, "2023-02-28"),
        ("2024-02-29", 12, "2023-02-28"),
        ("2024-01-15", 12, "2023-01-15"),
        ("2024-01-31", 2, "2023-11-30"),
    ],
)
def test_months_back_clamps_to_month_end(day: str, months: int, expected: str) -> None:
    assert months_back(o(day), months) == o(expected)


def test_trailing_returns_use_the_last_nav_within_the_gap() -> None:
    metrics = compute(
        series(("2023-06-23", 100.0), ("2023-06-27", 102.0), ("2024-06-28", 120.0)),
        o("2024-06-28"),
    )
    v = metrics.values
    assert v["ret_1y"] == 120.0 / 102.0 - 1
    assert metrics.anchors["ret_1y"] == "2023-06-27"
    assert v["ret_1m"] == Missing("NA", GAP_AT_START)
    assert v["cagr_3y"] == Missing("NA", HISTORY_TOO_SHORT)
    assert v["vol_1y"] == Missing("NA", HISTORY_TOO_SHORT)
    assert v["mdd_1y"] == Missing("NM", GAP_IN_WINDOW)
    assert v["since_start"] == "2023-06-23"
    assert v["ret_since"] == pytest.approx(0.2, rel=1e-15)
    assert v["cagr_since"] == 1.2 ** (365.25 / 371) - 1
    assert v["active"] is True
    assert v["last_nav_date"] == "2024-06-28"


def test_cagr_uses_calendar_days_between_the_anchors() -> None:
    metrics = compute(series(("2021-06-28", 50.0), ("2024-06-28", 80.0)), o("2024-06-28"))
    assert metrics.values["cagr_3y"] == (80.0 / 50.0) ** (365.25 / 1096) - 1
    assert metrics.anchors["cagr_3y"] == "2021-06-28"


def test_invalid_navs_are_excluded_and_counted_and_jumps_kept() -> None:
    points = [
        (o("2024-01-01"), 0.0, "nav_zero"),
        (o("2024-01-02"), None, "nav_missing"),
        (o("2024-01-03"), 10.0, None),
        (o("2024-01-04"), float("nan"), None),
        (o("2024-01-05"), -1.0, "nav_negative"),
        (o("2024-01-08"), 14.0, "nav_jump"),
    ]
    v = compute(points, o("2024-01-08")).values
    assert v["excluded_navs"] == 4
    assert v["jump_flags"] == 1
    assert v["since_start"] == "2024-01-03"
    assert v["ret_since"] == pytest.approx(0.4, rel=1e-15)
    assert v["nav"] == 14.0
    assert v["cagr_since"] == Missing("NA", HISTORY_TOO_SHORT)


def test_an_inactive_fund_has_no_trailing_metrics_but_keeps_its_history() -> None:
    v = compute(series(("2020-01-01", 10.0), ("2021-01-01", 12.0)), o("2024-01-01")).values
    assert v["active"] is False
    for name in ("ret_1m", "ret_1y", "cagr_3y", "vol_1y", "mdd_3y"):
        assert v[name] == Missing("NA", NO_RECENT_NAV)
    assert v["ret_since"] == pytest.approx(0.2, rel=1e-15)


def test_a_fund_without_a_valid_nav_is_unavailable_everywhere() -> None:
    v = compute([(o("2024-01-01"), 0.0, "nav_zero")], o("2024-01-01")).values
    assert v["active"] is False
    assert v["excluded_navs"] == 1
    assert v["ret_1y"] == v["nav"] == v["since_start"] == Missing("NA", NO_NAV)
    assert v["rolling_1y_count"] == Missing("NA", NO_NAV)


def test_volatility_is_the_annualised_sample_deviation() -> None:
    result = volatility([1, 2, 3], [100.0, 110.0, 99.0], 0, 2)
    r = [0.1, 99.0 / 110.0 - 1]
    assert result == pytest.approx(statistics.stdev(r) * ANNUALISE_VOL, rel=1e-12)
    assert volatility([1, 2], [100.0, 110.0], 0, 1) == Missing("NA", HISTORY_TOO_SHORT)
    assert volatility([1, 2, 20], [1.0, 1.0, 1.0], 0, 2) == Missing("NM", GAP_IN_WINDOW)


def test_drawdown_is_the_largest_fall_from_a_running_peak() -> None:
    assert drawdown([1, 2, 3, 4, 5], [100.0, 120.0, 90.0, 130.0, 117.0], 0, 4) == -0.25
    assert drawdown([1, 2], [100.0, 101.0], 0, 1) == 0.0


def test_rolling_returns_cover_every_window_with_a_valid_start() -> None:
    first = date(2020, 1, 1)
    dates = [(first + timedelta(days=k)).toordinal() for k in range(400)]
    navs = [100.0 + k + (k % 7) for k in range(400)]
    summary = rolling(dates, navs, 12)
    expected = [
        (navs[j] / navs[i]) ** (365.25 / (dates[j] - dates[i])) - 1
        for j in range(400)
        if (
            i := dates.index(months_back(dates[j], 12))
            if months_back(dates[j], 12) >= dates[0]
            else -1
        )
        >= 0
    ]
    assert summary["count"] == len(expected) == 34
    assert summary["median"] == statistics.median(expected)
    assert summary["mean"] == pytest.approx(statistics.fmean(expected), rel=1e-15)
    assert summary["min"] == min(expected)
    assert summary["max"] == max(expected)
    assert summary["positive_share"] == 1.0


def test_rolling_skips_windows_whose_start_falls_in_a_gap() -> None:
    dates = [o("2020-01-01"), o("2020-03-01"), o("2021-01-01"), o("2021-03-01")]
    summary = rolling(dates, [1.0, 1.0, 2.0, 2.0], 12)
    assert summary["count"] == 2
    assert rolling(dates[:2], [1.0, 1.0], 12)["count"] == 0
    assert rolling(dates[:2], [1.0, 1.0], 12)["mean"] == Missing("NA", HISTORY_TOO_SHORT)


@pytest.mark.parametrize(
    ("changes", "option", "plan"),
    [
        ({}, classify.GROWTH, classify.DIRECT),
        (
            {
                "scheme_name": "UTI - Dividend Yield Fund",
                "nav_name": "UTI-Dividend Yield Fund.-Growth",
            },
            classify.GROWTH,
            classify.REGULAR,
        ),
        (
            {
                "scheme_name": "Principal Gilt Fund-Savings-Dividend",
                "nav_name": "Principal Gilt Fund-Savings-Dividend",
            },
            classify.IDCW,
            classify.REGULAR,
        ),
        (
            {"scheme_name": "Franklin India Growth Fund", "nav_name": "Franklin India Growth Fund"},
            classify.UNKNOWN,
            classify.REGULAR,
        ),
        (
            {"scheme_name": "IDFC-FMP-QS36-A-GROWTH", "nav_name": "IDFC-FMP-QS36-A-GROWTH"},
            classify.GROWTH,
            classify.REGULAR,
        ),
        ({"nav_name": "Example Top 100 Fund - Div Reinvest"}, classify.IDCW, classify.REGULAR),
        (
            {"option": "Unclaimed Redemption and Dividend Plan-Growth Option"},
            classify.GROWTH,
            classify.DIRECT,
        ),
        (
            {"nav_name": "X LIQUID FUND SPECIAL UNCLAIMED DIV 36A -- GROWTH OPTION"},
            classify.GROWTH,
            classify.REGULAR,
        ),
        (
            {"nav_name": "X Liquid Fund-Direct Plan- Growth- Unclaimed Dividend < 3 Yrs"},
            classify.GROWTH,
            classify.DIRECT,
        ),
        (
            {"nav_name": "HSBC Asia Pacific IDCW Yield Fund Direct Plan Growth"},
            classify.GROWTH,
            classify.DIRECT,
        ),
        ({"nav_name": "HSBC Asia Pacific IDCW Yield Fund IDCW"}, classify.IDCW, classify.REGULAR),
        (
            {"nav_name": "X Dividend Opportunities Index Fund - Growth"},
            classify.GROWTH,
            classify.REGULAR,
        ),
        (
            {"nav_name": "ING RetireInvest Fund Series I - Growth"},
            classify.GROWTH,
            classify.REGULAR,
        ),
        (
            {"nav_name": "X Manufacturing Fund - Direct Plan - IDWC Option"},
            classify.IDCW,
            classify.DIRECT,
        ),
        ({"nav_name": "X Cash Fund-Growth-Dividend Option"}, classify.IDCW, classify.REGULAR),
        ({"option": "IDCW Payout", "plan": "Direct Plan"}, classify.IDCW, classify.DIRECT),
        ({"option": "Bonus Option"}, classify.BONUS, classify.DIRECT),
        ({"option": "GROWTH OPTION", "nav_name": "X Regular"}, classify.GROWTH, classify.REGULAR),
        (
            {"option": "Payout of Income Distribution cum capital withdrawal option"},
            classify.IDCW,
            classify.DIRECT,
        ),
    ],
)
def test_option_comes_from_the_plan_option_text_only(
    changes: dict[str, str], option: str, plan: str
) -> None:
    fund = replace(FUND, **changes)
    assert classify.option_of(fund) == option
    assert classify.plan_of(fund) == plan


def test_every_alias_names_one_canonical_category() -> None:
    assert set(classify.ALIASES.values()) <= set(classify.CATEGORIES)
    assert not set(classify.ALIASES) & set(classify.CATEGORIES)


@pytest.mark.parametrize(
    ("label", "category", "asset_class"),
    [
        ("Equity Scheme - Large Cap Fund", "Equity Scheme - Large Cap Fund", "Equity"),
        ("Equity Schemes - Large Cap Fund", "Equity Scheme - Large Cap Fund", "Equity"),
        ("Income/Debt Oriented Schemes - Liquid Fund", "Debt Scheme - Liquid Fund", "Debt"),
        ("Liquid", "Debt Scheme - Liquid Fund", "Debt"),
        ("Index Funds - Equity Funds", "Other Scheme - Index Funds", "Other"),
        ("Income", classify.UNCLASSIFIED, classify.UNCLASSIFIED),
        ("Gilt", classify.UNCLASSIFIED, classify.UNCLASSIFIED),
        (
            "Income/Debt Oriented Schemes - Short Term Fund",
            classify.UNCLASSIFIED,
            classify.UNCLASSIFIED,
        ),
        (None, classify.UNCLASSIFIED, classify.UNCLASSIFIED),
    ],
)
def test_categories_map_only_when_unambiguous(
    label: str | None, category: str, asset_class: str
) -> None:
    assert classify.canonical_category(label) == category
    assert classify.asset_class(category) == asset_class


def test_non_growth_options_are_flagged_as_excluding_payouts() -> None:
    assert classify.return_basis(classify.GROWTH) == classify.NAV_BASIS
    for option in (classify.IDCW, classify.BONUS, classify.UNKNOWN):
        assert classify.return_basis(option) == classify.NAV_EXCLUDING_PAYOUTS


def test_the_encoding_is_deterministic_and_round_trips() -> None:
    metrics = compute(series(("2023-06-23", 100.0), ("2024-06-28", 120.0)), o("2024-06-28"))
    values = attributes(FUND, None) | metrics.values | absent_fields(Missing("NA", "no_peer_group"))
    rows = [FundRow(1, "10001", "Example", ordered(values), metrics.anchors)]
    first = encode(1, 7, date(2024, 6, 28), ["tigzig", "amfi"], rows)
    second = encode(1, 7, date(2024, 6, 28), ["amfi", "tigzig"], list(rows))
    assert first == second
    snapshot = decode(1, first.payload)
    assert snapshot.rows == tuple(rows)
    assert snapshot.sources == ("amfi", "tigzig")
    assert len(snapshot.rows[0].values) == len(FIELDS)
    assert all(not isinstance(v, float) or math.isfinite(v) for v in snapshot.rows[0].values)
