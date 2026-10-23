"""Method v4 (doc 21) on hand-built series: categories, point-in-time peers, relations,
views, backtests and the tax rule history."""

from __future__ import annotations

import math
from array import array
from dataclasses import replace

import pytest

from tests.wickstreet.test_mf_slice3 import daily, o, peer, sparse
from wickstreet.analytics.domain import backtest, classify, views
from wickstreet.analytics.domain.metrics import (
    NO_RECENT_NAV,
    Missing,
    MonthEnds,
    compute,
    last_complete_month,
    month_end_values,
    month_key,
    valid_series,
)
from wickstreet.analytics.domain.peers import add_group_fields, monthly_ranks, transitions
from wickstreet.analytics.domain.relations import (
    DailyNavs,
    near_duplicates,
    pair_fields,
    pairs,
    proxy_index,
    regimes,
    window_return,
)
from wickstreet.analytics.domain.tax import Sale, capital_gains_tax

# ---- categories (C9)


def test_sebi_2026_labels_are_their_own_categories() -> None:
    label = "Income/Debt Oriented Schemes - Ultra Short to Short Term Fund"
    assert classify.canonical_category(label) == label
    assert classify.asset_class(label) == "Debt"
    # A 2026 label with the same name as a 2017 category still maps to it.
    assert (
        classify.canonical_category("Income/Debt Oriented Schemes - Liquid Fund")
        == "Debt Scheme - Liquid Fund"
    )
    assert classify.canonical_category("Income") == classify.UNCLASSIFIED


@pytest.mark.parametrize(
    ("category", "scheme_type", "kind"),
    [
        ("Other Scheme - Index Funds", "Open Ended", "index"),
        ("Other Scheme - Gold ETF", "Open Ended", "etf"),
        ("Other Scheme - FoF Domestic", "Open Ended Schemes", "fof"),
        ("Unclassified", "Close Ended Schemes", "close_ended"),
        ("Unclassified", "Interval Fund", "interval"),
        ("Equity Scheme - Mid Cap Fund", None, "open_ended"),
    ],
)
def test_fund_type(category: str, scheme_type: str | None, kind: str) -> None:
    assert classify.fund_type(category, scheme_type) == kind


# ---- per-fund metrics (C2, C5)


def test_rolling_percentiles_use_nearest_rank() -> None:
    navs = [100 * (1.0 + 0.001 * k) for k in range(800)]
    v = compute(daily("2022-01-01", navs), o("2022-01-01") + 799).values
    assert v["rolling_1y_p10"] <= v["rolling_1y_p25"] <= v["rolling_1y_median"]
    assert v["rolling_1y_median"] <= v["rolling_1y_p75"] <= v["rolling_1y_p90"]
    assert v["rolling_1y_p10"] >= v["rolling_1y_min"]


def test_current_drawdown_and_longest_time_under_water() -> None:
    points = daily("2024-01-01", [100.0, 120.0, 90.0, 110.0, 125.0, 100.0])
    v = compute(points, o("2024-01-06")).values
    assert v["dd_now"] == pytest.approx(100 / 125 - 1)
    assert v["dd_now_days"] == 1
    assert v["underwater_max_days"] == 3  # 120 on day 2 regained on day 5
    old = compute(points, o("2024-03-01")).values
    assert old["dd_now"] == Missing("NA", NO_RECENT_NAV)
    assert old["underwater_max_days"] == 3


def test_month_ends_need_a_nav_within_7_days_of_the_month_end() -> None:
    points = sparse(("2024-01-31", 100.0), ("2024-02-20", 101.0), ("2024-03-29", 102.0))
    dates, navs, _, _ = valid_series(points)
    ends = month_end_values(dates, navs, o("2024-04-10"))
    # February's last NAV is 9 days before the month end: not alive at that month-end.
    assert list(ends.months) == [month_key(o("2024-01-31")), month_key(o("2024-03-29"))]
    assert last_complete_month(o("2024-03-31")) == month_key(o("2024-03-31"))
    assert last_complete_month(o("2024-03-30")) == month_key(o("2024-02-29"))


def test_year_ago_values_need_the_fund_alive_then() -> None:
    navs = [100 * 1.0002**k for k in range(800)]
    metrics = compute(daily("2022-01-01", navs), o("2022-01-01") + 799)
    assert set(metrics.then) == {"ret_1y"}
    assert metrics.then["ret_1y"] == pytest.approx(1.0002**365 - 1, rel=1e-9)
    late = compute(daily("2023-06-01", navs[:200]), o("2023-06-01") + 199)
    assert late.then == {}


# ---- point-in-time peers (C1, C24)


def ends(months: list[int], ret_1y: list[float], cagr_3y: list[float] | None = None) -> MonthEnds:
    return MonthEnds(
        array("l", months),
        array("d", [100.0] * len(months)),
        array("d", ret_1y),
        array("d", cagr_3y or [math.nan] * len(months)),
    )


def test_past_month_ends_rank_funds_that_later_stopped() -> None:
    survivors = [peer({}) for _ in range(4)]
    for fund, value in zip(survivors, [0.1, 0.2, 0.3, 0.4], strict=True):
        fund.month_ends = ends([0, 1], [value, value])
    stopped = peer({}, active=False)
    stopped.month_ends = ends([0], [0.5])
    ranks = monthly_ranks([*survivors, stopped], "ret_1y")
    # Month 0 has five funds alive, so it ranks; month 1 has four, so it does not.
    assert ranks[3][0].rank == 2 and ranks[4][0].rank == 1
    assert 1 not in ranks[0]


def test_persistence_and_transitions() -> None:
    members = []
    for i in range(5):
        fund = peer({"ret_1y": 0.1 * i})
        fund.month_ends = ends(list(range(24)), [0.1 * i] * 24)
        members.append(fund)
    add_group_fields(members, 23)
    best, worst = members[4].values, members[0].values
    assert (best["q1_share_3y"], best["pct_mean_3y"]) == (1.0, 100.0)
    assert (worst["q1_share_3y"], worst["pct_mean_3y"]) == (0.0, 0.0)
    counts = transitions(monthly_ranks(members, "ret_1y"))
    # 12 pairs (month, month + 12) per fund; every fund keeps its quartile.
    assert counts[0][0] == 24 and sum(map(sum, counts)) == 60


def test_year_ago_ranks_and_changes() -> None:
    members = [peer({"ret_1y": 0.1 * i}, then={"ret_1y": 0.1 * (4 - i)}) for i in range(5)]
    add_group_fields(members, 0)
    top = members[4].values
    assert (top["ret_1y_cat_pct_1y_ago"], top["ret_1y_cat_pct"]) == (0.0, 100.0)
    assert top["ret_1y_pct_chg_1y"] == 100.0
    assert top["quartile_change_1y"] == 3  # quartile 4 a year ago, quartile 1 now
    assert top["vol_3y_cat_pct_1y_ago"] == Missing("NA", "too_few_peers")


# ---- relations (C4, C7, C23)


def test_pairs_need_one_plan_on_each_side() -> None:
    keys = {
        1: ("A", "S", "growth", "direct"),
        2: ("A", "S", "growth", "regular"),
        3: ("A", "S", "idcw", "direct"),
        4: ("A", "S", "idcw", "regular"),
        5: ("A", "S", "idcw", "regular"),
    }
    assert pairs(keys) == {1: 2, 2: 1}
    gap = pair_fields(
        {"ret_1y": 0.12, "cagr_3y": 0.11}, {"ret_1y": 0.10, "cagr_3y": Missing("NA", "x")}
    )
    assert gap["dr_gap_1y"] == pytest.approx(0.02)
    assert gap["dr_gap_3y"] == gap["dr_wealth_10y"] == Missing("NA", "x")
    full = pair_fields({"ret_1y": 0.1, "cagr_3y": 0.11}, {"ret_1y": 0.1, "cagr_3y": 0.10})
    assert full["dr_wealth_10y"] == pytest.approx(1e6 * (1.11**10 - 1.10**10))


def test_near_duplicates_match_the_compare_correlation() -> None:
    start = o("2023-01-02")
    base = [math.sin(k / 7) * 0.01 for k in range(600)]
    twin = [r + (0.0005 if k % 3 == 0 else -0.0002) for k, r in enumerate(base)]
    other = [math.cos(k / 3) * 0.01 for k in range(600)]

    def navs(rets: list[float], skip: int = 0) -> list[tuple[int, float | None, str | None]]:
        level, points = 100.0, [(start - 1, 100.0, None)]
        for k, r in enumerate(rets):
            level *= 1 + r
            if not skip or k % skip:
                points.append((start + k, level, None))
        return points

    # The twin skips every 9th date, as a fund on another holiday calendar would.
    series = {1: navs(base), 2: navs(twin, skip=9), 3: navs(other)}
    funds = [
        DailyNavs(pid, array("i", [d for d, _, _ in p]), array("d", [n for _, n, _ in p]))
        for pid, p in series.items()
    ]
    found = near_duplicates(funds)
    assert set(found) == {1, 2}
    pid, value, compared = found[1][0]
    expected, observations = views.correlation(series[1], series[2])
    assert (pid, compared) == (2, observations)
    assert value == pytest.approx(expected, rel=1e-12)


def test_proxy_index_and_regimes() -> None:
    by_day = {d: [r] * 5 for d, r in enumerate([0.0, -0.06, -0.06, 0.05, 0.10, 0.02], start=1)}
    levels = proxy_index(by_day)
    assert levels[0] == (1, 100.0)
    windows = regimes([(o("2024-01-01") + d, level) for d, level in levels])
    assert [w["kind"] for w in windows] == ["correction", "recovery"]
    assert windows[0]["proxy_return"] == pytest.approx(0.94 * 0.94 - 1)
    assert windows[1]["ongoing"] is False
    assert proxy_index({1: [0.1] * 4}) == []
    dates, navs, _, _ = valid_series(daily("2024-01-01", [100.0, 90.0, 99.0]))
    assert window_return(dates, navs, "2024-01-01", "2024-01-03") == pytest.approx(-0.01)


# ---- views (C3, C5, C6)


def test_underwater_and_recovery_spread() -> None:
    points = daily("2024-01-01", [100.0, 90.0, 100.0, 80.0, 81.0])
    assert [v for _, v in views.underwater(points)] == pytest.approx([0, -0.1, 0, -0.2, -0.19])
    spread = views.recovery_spread(views.drawdowns(points, 10), -0.05)
    assert (spread["recovered"], spread["not_recovered"], spread["median_days"]) == (1, 1, 1)


def test_rolling_sip_covers_every_full_tenor_start() -> None:
    navs = [10.0 * 1.0003**k for k in range(1200)]
    points = daily("2021-01-01", navs)
    starts = views.rolling_sip(points, o("2021-01-01") + 1199, 36, 1000.0, 1, 0.0)
    assert starts[0]["start"] == "2021-01-01"
    assert starts[-1]["start"] == "2021-04-01"  # tenor ends 2024-03-31, before 2024-04-14
    assert all(s["xirr"] > 0 and s["sip_drawdown"] <= 0 for s in starts)
    stepped = views.rolling_sip(points, o("2021-01-01") + 1199, 36, 1000.0, 1, 0.1)
    assert stepped[0]["invested"] > starts[0]["invested"]


def test_frontier_keeps_only_undominated_points() -> None:
    points = [("a", 0.1, 0.08), ("b", 0.2, 0.12), ("c", 0.2, 0.10), ("d", 0.3, 0.11)]
    assert views.frontier(points) == {"a", "b"}


# ---- backtests (C10)


def test_backtest_holds_the_top_funds_against_the_median() -> None:
    members = {}
    for i in range(6):
        navs = [100.0 * (1 + 0.01 * i) ** m for m in range(4)]
        members[f"f{i}"] = MonthEnds(
            array("l", [2023 * 12 + 11 + m for m in range(4)]),
            array("d", navs),
            array("d", [0.01 * i] * 4),
            array("d", [math.nan] * 4),
        )
    months = backtest.run(members, "ret_1y", 2)
    assert [m.picks for m in months] == [("f5", "f4")] * 3
    assert months[0].strategy == pytest.approx(0.045)
    assert months[0].median == pytest.approx(0.025)
    summary = backtest.summarise(months)
    assert (summary["in_sample"]["months"], summary["holdout"]["months"]) == (1, 2)
    assert summary["whole"]["beat_share"] == 1.0
    with pytest.raises(backtest.BacktestError):
        backtest.run(members, "score", 2)


# ---- tax rule history (C22)


def sale(bought: str, sold: str, cost: float, proceeds: float) -> Sale:
    return Sale(o(bought), o(sold), 1.0, cost, proceeds)


def test_equity_before_the_2024_act() -> None:
    long = capital_gains_tax([sale("2020-01-01", "2022-06-01", 0, 300_000)], "equity", None, None)
    assert long.total == pytest.approx(200_000 * 0.10 * 1.04)
    short = capital_gains_tax([sale("2022-01-01", "2022-06-01", 0, 10_000)], "equity", None, None)
    assert short.total == pytest.approx(10_000 * 0.15 * 1.04)


def test_fy2024_25_uses_the_exemption_against_the_higher_rate_first() -> None:
    sales = [
        sale("2022-01-01", "2024-05-01", 0, 100_000),
        sale("2022-01-01", "2024-09-01", 0, 100_000),
    ]
    result = capital_gains_tax(sales, "equity", None, None)
    # ₹1.25 lakh comes off the 12.5% gain first, then ₹25,000 off the 10% gain.
    assert result.total == pytest.approx(75_000 * 0.10 * 1.04)


def test_debt_indexation_and_loss_set_off() -> None:
    indexed = capital_gains_tax(
        [sale("2019-05-01", "2023-01-01", 100.0, 200.0)], "debt", None, None
    )
    assert indexed.total == pytest.approx((200 - 100 * 331 / 289) * 0.20 * 1.04)
    mixed = [
        sale("2019-05-01", "2023-01-01", 100.0, 200.0),
        sale("2022-06-01", "2023-01-01", 50, 30),
    ]
    offset = capital_gains_tax(mixed, "debt", 0.3, None)
    assert offset.total == pytest.approx((200 - 100 * 331 / 289 - 20) * 0.20 * 1.04)
    assert (
        capital_gains_tax(
            [replace(mixed[0], sold=o("2018-03-01"))], "debt", None, None
        ).not_modelled
        == 1
    )
