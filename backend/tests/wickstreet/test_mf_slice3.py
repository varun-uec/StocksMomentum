"""Method v3, peers, formulas, views, calculators and tax on hand-built series."""

from __future__ import annotations

import math
from array import array
from dataclasses import replace
from datetime import date

import pytest

from tests.wickstreet.test_mf_metrics import FUND
from tests.wickstreet.test_mf_screening import NA, NM, ids, row
from wickstreet.analytics.domain import calculators, views
from wickstreet.analytics.domain.classify import sibling_categories
from wickstreet.analytics.domain.formulas import MAX_FORMULAS, with_formulas
from wickstreet.analytics.domain.metrics import (
    ANNUALISE_VOL,
    HISTORY_TOO_SHORT,
    NO_DRAWDOWN,
    NOT_RECOVERED,
    ZERO_DENOMINATOR,
    Missing,
    MonthEnds,
    RiskFree,
    compute,
    downside,
    month_key,
)
from wickstreet.analytics.domain.peers import (
    RANKED_INPUTS,
    PeerFund,
    add_group_fields,
    group_absence,
)
from wickstreet.analytics.domain.screening import FilterError, parse_filter, parse_sort, screen
from wickstreet.analytics.domain.tax import Sale, capital_gains_tax, held_over, tax_class_of


def o(text: str) -> int:
    return date.fromisoformat(text).toordinal()


def daily(first: str, navs: list[float]) -> list[tuple[int, float | None, str | None]]:
    start = o(first)
    return [(start + k, nav, None) for k, nav in enumerate(navs)]


def sparse(*points: tuple[str, float]) -> list[tuple[int, float | None, str | None]]:
    return [(o(day), nav, None) for day, nav in points]


# ---- method v3, per fund


def test_annual_fields_use_year_end_anchors() -> None:
    points = sparse(
        ("2021-12-31", 100.0), ("2022-12-30", 110.0), ("2023-12-29", 99.0), ("2024-06-28", 105.0)
    )
    v = compute(points, o("2024-06-28")).values
    assert v["ret_cy_last"] == pytest.approx(-0.1, rel=1e-12)
    assert v["ret_ytd"] == 105.0 / 99.0 - 1
    assert (v["cy_best"], v["cy_worst"], v["cy_positive_share"], v["cy_count"]) == (
        pytest.approx(0.1, rel=1e-12),
        pytest.approx(-0.1, rel=1e-12),
        0.5,
        2,
    )
    assert v["ret_fy_last"] == Missing("NA", HISTORY_TOO_SHORT)
    fy = compute(
        sparse(("2023-03-31", 100.0), ("2024-03-28", 120.0), ("2024-04-05", 121.0)), o("2024-04-05")
    )
    assert fy.values["ret_fy_last"] == pytest.approx(0.2, rel=1e-12)


def test_drawdown_episodes_name_peak_trough_and_recovery() -> None:
    v = compute(daily("2024-01-01", [100.0, 120.0, 90.0, 130.0, 117.0]), o("2024-01-05")).values
    assert (v["dd_since_peak"], v["dd_since_trough"], v["dd_since_recovery"]) == (
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    )
    assert (v["dd_since_fall_days"], v["dd_since_recovery_days"], v["mdd_since"]) == (1, 1, -0.25)
    open_fall = compute(daily("2024-01-01", [100.0, 120.0, 90.0, 100.0]), o("2024-01-04")).values
    assert open_fall["dd_since_recovery"] == Missing("NA", NOT_RECOVERED)
    assert open_fall["dd_since_recovery_days"] == Missing("NA", NOT_RECOVERED)
    rising = compute(daily("2024-01-01", [100.0, 101.0, 102.0]), o("2024-01-03")).values
    assert rising["dd_since_peak"] == Missing("NA", NO_DRAWDOWN)


def test_worst_periods_and_status() -> None:
    navs = [100.0 if k < 41 else 90.0 for k in range(91)]
    v = compute(daily("2024-01-01", navs), o("2024-03-31")).values
    assert v["worst_1m"] == pytest.approx(-0.1, rel=1e-12)
    assert v["worst_1y"] == Missing("NA", HISTORY_TOO_SHORT)
    assert v["status"] == "active"
    assert compute(daily("2024-01-01", navs), o("2024-06-30")).values["status"] == "historical"
    assert compute([], o("2024-06-30")).values["status"] == "no_nav"


def test_downside_deviation_var_and_cvar() -> None:
    deviation, _, var, cvar = downside([1, 2, 3, 4], [100.0, 110.0, 99.0, 99.0], 0, 3)
    returns = [0.1, 99.0 / 110.0 - 1, 0.0]
    assert deviation == pytest.approx(math.sqrt(returns[1] ** 2 / 3) * ANNUALISE_VOL, rel=1e-12)
    assert var == cvar == returns[1]


def test_three_year_ratios_and_month_ends() -> None:
    first = date(2021, 6, 1)
    days = (date(2024, 6, 28) - first).days + 1
    points = daily("2021-06-01", [100 * 1.0003**k for k in range(days)])
    metrics = compute(points, o("2024-06-28"))
    assert metrics.values["downside_dev_3y"] == 0.0
    assert metrics.values["sortino_3y"] == Missing("NA", "no_risk_free")
    zero = RiskFree.of([(o("2021-01-01"), 0.0), (o("2024-06-01"), 0.0)])
    assert compute(points, o("2024-06-28"), zero).values["sortino_3y"] == Missing(
        "NM", ZERO_DENOMINATOR
    )
    assert isinstance(metrics.values["ret_risk_3y"], float)
    ends = metrics.month_ends
    # 2024-06 is not complete on 2024-06-28; no month-end has a full 3Y window.
    assert (len(ends.months), ends.months[0], ends.months[-1]) == (
        36,
        month_key(o("2021-06-30")),
        month_key(o("2024-05-31")),
    )
    assert all(math.isnan(v) for v in ends.cagr_3y)
    assert sum(not math.isnan(v) for v in ends.ret_1y) == 24


# ---- peers


def peer(
    values: dict[str, object],
    months: int = 0,
    value: float = 0.0,
    then: dict[str, float] | None = None,
    active: bool = True,
) -> PeerFund:
    base = dict.fromkeys(RANKED_INPUTS, NA) | values
    ends = MonthEnds(
        array("l", range(months)),
        array("d", [100.0] * months),
        array("d", [math.nan] * months),
        array("d", [value] * months),
    )
    return PeerFund(base, ends, then or {}, active)  # type: ignore[arg-type]


def test_category_ranks_split_ties_and_respect_direction() -> None:
    members = [
        peer({"ret_1y": r, "vol_3y": vol})
        for r, vol in zip([0.1, 0.2, 0.2, 0.3, 0.4], [0.5, 0.4, 0.3, 0.2, 0.1], strict=True)
    ]
    add_group_fields(members, 11)
    got = [
        (m.values["ret_1y_cat_rank"], m.values["ret_1y_cat_pct"], m.values["ret_1y_cat_quartile"])
        for m in members
    ]
    assert got == [(5, 0.0, 4), (3, 37.5, 3), (3, 37.5, 3), (2, 75.0, 1), (1, 100.0, 1)]
    assert {m.values["ret_1y_cat_median"] for m in members} == {0.2}
    assert {m.values["ret_1y_cat_count"] for m in members} == {5}
    assert [m.values["vol_3y_cat_rank"] for m in members] == [5, 4, 3, 2, 1]
    assert members[0].values["cagr_3y_cat_rank"] == NA


def test_too_few_peers_and_consistency_and_score() -> None:
    few = [peer({"ret_1y": 0.1}) for _ in range(4)]
    add_group_fields(few, 11)
    assert few[0].values["ret_1y_cat_pct"] == Missing("NA", "too_few_peers")
    members = [
        peer({"ret_risk_3y": float(i), "mdd_3y": -0.1 * (5 - i)}, months=12, value=float(i))
        for i in range(5)
    ]
    add_group_fields(members, 11)
    assert [m.values["consistency_3y"] for m in members] == [0.0, 0.0, 0.0, 1.0, 1.0]
    best = members[4].values
    assert best["score"] == pytest.approx((best["consistency_3y_cat_pct"] + 100 + 100) / 3)
    assert best["score_cat_rank"] == 1
    short = [peer({}, months=11, value=float(i)) for i in range(5)]
    add_group_fields(short, 11)
    assert short[0].values["consistency_3y"] == Missing("NA", HISTORY_TOO_SHORT)
    assert short[0].values["score"] == Missing("NA", HISTORY_TOO_SHORT)


def test_sibling_categories_and_group_absence() -> None:
    old = replace(FUND, plan_option_id=2, category="Income")
    current = replace(FUND, plan_option_id=3, category="Equity Scheme - Large Cap Fund")
    assert sibling_categories([old, current]) == {2: "Equity Scheme - Large Cap Fund"}
    split = replace(FUND, plan_option_id=4, category="Equity Scheme - Mid Cap Fund")
    assert sibling_categories([old, current, split]) == {}
    assert group_absence("active", "Unclassified", "Unclassified") == Missing("NA", "no_peer_group")
    assert group_absence("historical", "X", "Unclassified") == Missing("NA", "no_recent_nav")
    assert group_absence("active", "X", "Unclassified") is None


# ---- formulas


ROWS = (row(1, cagr_3y=0.1, vol_3y=0.2), row(2, cagr_3y=0.2, vol_3y=0.0), row(3, cagr_3y=NM))


def test_formulas_compute_propagate_and_screen() -> None:
    rows, columns, missing = with_formulas(ROWS, {"edge": "-(cagr_3y / vol_3y) * 2 + 1"})
    values = [r.values[columns["edge"][1]] for r in rows]
    assert values == [pytest.approx(0.0), Missing("NM", ZERO_DENOMINATOR), NM]
    assert missing["edge"] == {ZERO_DENOMINATOR: 1, "gap_in_window": 1}
    where = parse_filter({"field": "edge", "op": "is_available"}, columns)
    assert ids(screen(rows, where, parse_sort([{"field": "edge"}], columns))) == [1]
    assert with_formulas(ROWS, {}) == (ROWS, with_formulas(ROWS, {})[1], {})


@pytest.mark.parametrize(
    "definitions",
    [
        {"x": "__import__('os')"},
        {"x": "cagr_3y.real"},
        {"x": "cagr_3y ** 2"},
        {"x": "plan + 1"},
        {"x": "unknown_field"},
        {"x": "1 +"},
        {"x": "True + 1"},
        {"ret_1y": "cagr_3y"},
        {"Bad": "cagr_3y"},
        {"x": "1" + " + 1" * 200},
        {f"f{i}": "1" for i in range(MAX_FORMULAS + 1)},
    ],
)
def test_formulas_refuse_anything_but_arithmetic(definitions: dict[str, str]) -> None:
    with pytest.raises(FilterError):
        with_formulas(ROWS, definitions)


# ---- views


def test_annual_view_labels_partial_years() -> None:
    points = sparse(
        ("2022-06-15", 100.0), ("2022-12-30", 110.0), ("2023-12-29", 121.0), ("2024-03-15", 133.1)
    )
    table = views.annual(points, o("2024-03-15"))
    assert [(r["period"], round(r["return"], 12), r["partial"]) for r in table["calendar"]] == [
        ("2022", 0.1, True),
        ("2023", 0.1, False),
        ("2024", 0.1, True),
    ]
    assert [(r["period"], r["partial"]) for r in table["financial"]] == [("FY2023-24", True)]
    monthly = views.annual(daily("2024-01-01", [100.0 + k for k in range(91)]), o("2024-03-31"))
    assert [(m["year"], m["month"]) for m in monthly["monthly"]] == [(2024, 2), (2024, 3)]
    assert monthly["monthly"][0]["return"] == 159.0 / 130.0 - 1


def test_drawdown_episodes_and_correlation() -> None:
    episodes = views.drawdowns(daily("2024-01-01", [100.0, 120, 90, 130, 117, 140, 100]), 2)
    assert [round(e["depth"], 6) for e in episodes] == [round(100 / 140 - 1, 6), -0.25]
    assert episodes[0]["recovery"] is None and episodes[1]["recovery"] == "2024-01-04"
    wave = [100 + 10 * math.sin(k) for k in range(40)]
    same, n = views.correlation(daily("2024-01-01", wave), daily("2024-01-01", wave))
    assert same == pytest.approx(1.0) and n == 39
    assert views.correlation(daily("2024-01-01", wave[:10]), daily("2024-01-01", wave[:10])) == (
        None,
        9,
    )


# ---- calculators


def test_xirr_and_lumpsum() -> None:
    assert calculators.xirr([(0, -100.0), (365, 110.0)]) == pytest.approx(0.1, abs=1e-9)
    assert calculators.xirr([(0, -100.0)]) is None
    growth = daily("2020-01-01", [10.0 + 10.0 * k / 365 for k in range(366)])
    outcome = calculators.lumpsum(growth, 1000.0, date(2020, 1, 1), date(2020, 12, 31))
    assert outcome.summary["value"] == pytest.approx(2000.0)
    assert outcome.summary["xirr"] == pytest.approx(1.0, abs=1e-9)
    assert sum(s.units for s in outcome.sales) == pytest.approx(100.0)


FLAT = daily("2021-01-01", [10.0] * 365)


def test_sip_buys_on_the_first_nav_after_each_scheduled_day() -> None:
    outcome = calculators.sip(FLAT, 1000.0, 5, date(2021, 1, 1), date(2021, 12, 31))
    assert outcome.summary["instalments"] == 12
    assert outcome.summary["value"] == pytest.approx(12 * 1000 * (1 - calculators.STAMP_DUTY))
    assert -0.001 < outcome.summary["xirr"] < 0
    stepped = calculators.sip(FLAT, 1000.0, 5, date(2021, 1, 1), date(2022, 1, 31), step_up=0.1)
    assert stepped.summary["invested"] == pytest.approx(12_000.0)
    with pytest.raises(calculators.SimulationError):
        calculators.sip(FLAT, 1000.0, 5, date(2030, 1, 1), date(2030, 12, 31))


def test_swp_and_stp() -> None:
    swp = calculators.swp(FLAT, 12_000.0, 1000.0, 1, date(2021, 1, 1), date(2021, 12, 31))
    assert swp.summary["withdrawals"] == 11
    assert swp.summary["withdrawn"] == pytest.approx(11_000.0)
    assert swp.summary["value"] == pytest.approx(12_000 * (1 - calculators.STAMP_DUTY) - 11_000)
    target = daily("2021-01-01", [20.0] * 365)
    stp = calculators.stp(FLAT, target, 10_000.0, 1000.0, 1, date(2021, 1, 1), date(2021, 12, 31))
    assert stp.summary["transfers"] == 10
    assert stp.summary["source_value"] == pytest.approx(0.0, abs=1e-6)
    assert stp.summary["target_value"] == pytest.approx(
        10_000 * (1 - calculators.STAMP_DUTY) * (1 - calculators.STAMP_DUTY)
    )


# ---- tax


def sale(bought: str, sold: str, cost: float, proceeds: float, units: float = 1.0) -> Sale:
    return Sale(o(bought), o(sold), units, cost, proceeds)


def test_equity_tax_rates_exemption_and_grandfathering() -> None:
    long = capital_gains_tax(
        [sale("2023-01-01", "2024-08-01", 100_000, 400_000)], "equity", None, None
    )
    assert long.total == pytest.approx(175_000 * 0.125 * 1.04)
    short = capital_gains_tax(
        [sale("2024-05-01", "2024-09-01", 100_000, 110_000)], "equity", None, None
    )
    assert short.total == pytest.approx(2080.0)
    old = capital_gains_tax([sale("2017-01-01", "2024-08-01", 100, 400)], "equity", None, 150.0)
    assert old.years[0]["long_term"] == 250
    assert old.total == 0


def test_holding_periods_use_calendar_anniversaries() -> None:
    # Independent audit A-03: 24 Jul 2023 -> 24 Jul 2024 is 366 days but exactly
    # 12 months, so it is short term (20% + cess), not long term.
    gain = 376_182.5337657018
    on = capital_gains_tax([sale("2023-07-24", "2024-07-24", 0, gain)], "equity", None, None)
    assert on.years[0]["short_term"] == pytest.approx(gain)
    assert on.total == pytest.approx(78_245.97, abs=0.01)
    after = capital_gains_tax([sale("2023-07-24", "2024-07-25", 0, gain)], "equity", None, None)
    assert after.years[0]["long_term"] == pytest.approx(gain)
    assert held_over(o("2023-07-24"), o("2024-07-23"), 12) is False
    assert held_over(o("2023-07-24"), o("2024-07-24"), 12) is False
    assert held_over(o("2023-07-24"), o("2024-07-25"), 12) is True
    # A leap-day purchase reaches its anniversary on the month's last day.
    assert held_over(o("2024-02-29"), o("2025-02-28"), 12) is False
    assert held_over(o("2024-02-29"), o("2025-03-01"), 12) is True
    assert held_over(o("2023-01-31"), o("2025-01-31"), 24) is False
    assert held_over(o("2023-01-31"), o("2025-02-01"), 24) is True
    assert held_over(o("2019-03-01"), o("2022-03-01"), 36) is False
    assert held_over(o("2019-03-01"), o("2022-03-02"), 36) is True
    # Debt bought before April 2023 and sold on its 24-month anniversary stays at slab.
    debt = capital_gains_tax([sale("2022-08-01", "2024-08-01", 0, 10_000)], "debt", 0.3, None)
    assert debt.years[0]["slab"] == pytest.approx(10_000)


def test_debt_and_other_tax_and_reasons() -> None:
    new_debt = [sale("2023-05-01", "2025-08-01", 0, 10_000)]
    assert capital_gains_tax(new_debt, "debt", 0.3, None).total == pytest.approx(3120.0)
    assert capital_gains_tax(new_debt, "debt", None, None).reason == "slab_rate_needed"
    old_debt = [sale("2021-01-01", "2024-08-01", 0, 10_000)]
    assert capital_gains_tax(old_debt, "debt", None, None).total == pytest.approx(1300.0)
    assert capital_gains_tax(old_debt, "other", None, None).total == pytest.approx(1300.0)
    early = capital_gains_tax([sale("2017-01-01", "2018-03-01", 0, 10)], "equity", None, None)
    assert (early.total, early.not_modelled) == (0.0, 1)
    assert capital_gains_tax(new_debt, None, 0.3, None).reason == "tax_class_needed"
    assert tax_class_of("Equity Scheme - Large Cap Fund", "Equity") == "equity"
    assert tax_class_of("Hybrid Scheme - Arbitrage Fund", "Hybrid") == "equity"
    assert tax_class_of("Debt Scheme - Liquid Fund", "Debt") == "debt"
    assert tax_class_of("Other Scheme - Index Funds", "Other") is None


def test_overseas_funds_are_never_taxed_as_domestic_equity() -> None:
    # Independent review R-01: an international equity fund (119517) is filed as
    # thematic, so no thematic or overseas category implies the equity class.
    for category, asset_class in (
        ("Equity Scheme - Sectoral/ Thematic", "Equity"),
        ("Other Scheme - FoF Overseas", "Other"),
        ("Other Scheme - FoF Domestic", "Other"),
        ("Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage", "Hybrid"),
    ):
        assert tax_class_of(category, asset_class) is None
    for category in ("Flexi Cap Fund", "ELSS", "Small Cap Fund", "Value Fund"):
        assert tax_class_of("Equity Scheme - " + category, "Equity") == "equity"
    # 119517, ₹10 lakh, 24 Jul 2023 -> 25 Jul 2024: the live gain at the 30% slab.
    gain = 49_103.06868
    overseas = [sale("2023-07-24", "2024-07-25", 0, gain)]
    assert capital_gains_tax(overseas, "other", 0.3, None).total == pytest.approx(
        15_320.16, abs=0.01
    )
    assert capital_gains_tax(overseas, "equity", 0.3, None).total == 0  # the old error


def test_overseas_units_follow_section_50aa_across_rule_changes() -> None:
    def term(bought: str, sold: str) -> str:
        year = capital_gains_tax([sale(bought, sold, 0, 1000)], "other", 0.3, None).years[0]
        return next(t for t in ("short_term", "long_term", "slab") if year[t])

    # Bought from April 2023 and sold before April 2025: slab whatever the holding.
    assert term("2023-04-01", "2025-03-31") == "slab"
    # From April 2025 section 50AA no longer covers them: over 24 months is long term.
    assert term("2023-04-01", "2025-04-01") == "slab"
    assert term("2023-04-01", "2025-04-02") == "long_term"
    # Bought before April 2023: 36 months (indexed 20%) until 22 Jul 2024, then 24 months.
    assert term("2022-01-03", "2024-07-22") == "slab"
    assert term("2022-01-03", "2024-07-23") == "long_term"
    indexed = capital_gains_tax([sale("2020-05-04", "2024-07-22", 100, 200)], "other", 0.3, None)
    assert indexed.total == pytest.approx((200 - 100 * 363 / 301) * 0.20 * 1.04)
    after = capital_gains_tax([sale("2022-01-03", "2024-07-23", 100, 200)], "other", 0.3, None)
    assert after.total == pytest.approx(100 * 0.125 * 1.04)


def test_schedule_clamps_to_month_end() -> None:
    days = calculators.schedule(date(2024, 1, 15), date(2024, 4, 30), 31)
    assert [date.fromordinal(d).isoformat() for d in days] == [
        "2024-01-31",
        "2024-02-29",
        "2024-03-31",
        "2024-04-30",
    ]


def test_month_end_navs_keep_the_last_valid_nav_of_each_month() -> None:
    """Sparklines (audit U-05): NAVs as filed, one per month, the last 3 years only."""
    start = date(2022, 1, 3).toordinal()
    points = [(start + i, 10.0 + i, None) for i in range(0, 1400, 7)]
    points.append((points[-1][0] + 1, None, "jump"))
    line = views.month_end_navs(points, 36)
    assert len(line) == 37
    assert line[-1] == (date.fromordinal(points[-2][0]).isoformat(), points[-2][1])
    assert [d[:7] for d, _ in line] == sorted({d[:7] for d, _ in line})
    assert views.month_end_navs([], 36) == []
