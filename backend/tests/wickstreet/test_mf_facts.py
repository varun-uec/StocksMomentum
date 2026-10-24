"""AMFI scheme facts (doc 21 E1, E3): parsers, joins and method v6 fields. Synthetic data only."""

from __future__ import annotations

import io
import json
import math
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import pytest

from wickstreet.analytics.domain import enrichment as e
from wickstreet.analytics.domain.metrics import (
    GROWTH_ONLY,
    NO_PROXY,
    NO_SCHEME,
    NO_YEAR_AGO,
    Missing,
    RiskFree,
)
from wickstreet.analytics.domain.relations import DailyNavs
from wickstreet.mf_data.domain.facts import join_by_navs, nav_index, scheme_keys
from wickstreet.mf_data.domain.model import DIRECT, REGULAR, SCHEME, RawFile, SchemeRef
from wickstreet.mf_data.domain.reads import FactPoint, FactView
from wickstreet.mf_data.infrastructure import amfi_facts as a

_SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NOW = datetime(2026, 10, 24, tzinfo=UTC)


def _raw(content: bytes) -> RawFile:
    return RawFile("https://example.test/x", _NOW, content)


def _xlsx(rows: list[list[str | float]]) -> bytes:
    """A one-sheet workbook from column A, strings shared, numbers inline."""
    strings: list[str] = []
    cells = []
    for r, row in enumerate(rows, start=1):
        out = []
        for c, value in enumerate(row):
            ref = f"{chr(ord('A') + c)}{r}"
            if isinstance(value, str):
                strings.append(value)
                out.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                out.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{r}">{"".join(out)}</row>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        shared = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
        book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{_SHEET}">{shared}</sst>')
        body = f'<worksheet xmlns="{_SHEET}"><sheetData>{"".join(cells)}</sheetData></worksheet>'
        book.writestr("xl/worksheets/sheet1.xml", body)
    return buffer.getvalue()


_TER_HEADER = [
    "NSDL Scheme Code",
    "Scheme Name",
    "Scheme Type",
    "Scheme Category",
    "TER Date",
    "Regular Plan - Base Expense Ratio (BER) (%)",
    "b",
    "c",
    "d",
    "Regular Plan - Total TER (%)",
    "Direct Plan - Base Expense Ratio (BER) (%)",
    "f",
    "g",
    "h",
    "Direct Plan - Total TER (%)",
]


def _serial(day: date) -> int:
    return (day - date(1899, 12, 30)).days


def _ter_row(code: str, name: str, day: date, regular: float, direct: float) -> list[str | float]:
    return [
        code,
        name,
        "Open Ended",
        "Equity",
        _serial(day),
        1.0,
        0,
        0,
        0,
        regular,
        0.5,
        0,
        0,
        0,
        direct,
    ]


def test_ter_month_becomes_change_points_joined_by_code_then_name() -> None:
    rows = [
        _TER_HEADER,
        _ter_row("ABCD/O/E/FCF/13/04/0001", "Alpha Flexi Cap Fund", date(2026, 9, 1), 1.3, 0.69),
        _ter_row("ABCD/O/E/FCF/13/04/0001", "Alpha Flexi Cap Fund", date(2026, 9, 2), 1.3, 0.69),
        _ter_row("ABCD/O/E/FCF/13/04/0001", "Alpha Flexi Cap Fund", date(2026, 9, 3), 1.31, 0.69),
        _ter_row("X/1", "Beta Liquid Fund", date(2026, 9, 1), 0.3, 0.1),
        _ter_row("X/2", "Nobody Fund", date(2026, 9, 1), 2.0, 1.0),
    ]
    codes = {"abcdoefcf13040001": 7}
    found = a.parse_ter(_raw(_xlsx(rows)), codes, {"betaliquidfund": 9})
    ter = sorted((f.sd_id, f.plan, f.as_of.day, str(f.num)) for f in found.facts if f.name == "ter")
    assert ter == [
        (7, DIRECT, 1, "0.69"),
        (7, REGULAR, 1, "1.3"),
        (7, REGULAR, 3, "1.31"),
        (9, DIRECT, 1, "0.1"),
        (9, REGULAR, 1, "0.3"),
    ]
    assert found.unmatched == 1


def test_ter_rejects_a_changed_header() -> None:
    with pytest.raises(a.SourceLayoutError):
        a.parse_ter(_raw(_xlsx([["Code", "Name"]])), {}, {})


def test_ssd_keeps_filed_elements_and_lists_isins() -> None:
    xml = (
        '﻿<?xml version="1.0" encoding="utf-8"?><SchemeSummaryDocument><SchemeSummary>'
        "<Fund_Name>Alpha Flexi Cap Fund</Fund_Name>"
        "<Benchmark_Tier_1>NIFTY500(TRI)</Benchmark_Tier_1>"
        "<Benchmark_Tier_2>Not Applicable</Benchmark_Tier_2>"
        "<ISINs>Regular Plan - Growth : INF879O01019, "
        "Direct Plan - Growth : INF879O01027</ISINs>"
        "</SchemeSummary></SchemeSummaryDocument>"
    ).encode()
    found = a.parse_ssd(_raw(xml), 7, date(2026, 10, 24))
    assert {f.name: f.txt for f in found.facts} == {
        "ssd:Fund_Name": "Alpha Flexi Cap Fund",
        "ssd:Benchmark_Tier_1": "NIFTY500(TRI)",
        "ssd:ISINs": "Regular Plan - Growth : INF879O01019, Direct Plan - Growth : INF879O01027",
    }
    assert found.isins == {"INF879O01019": 7, "INF879O01027": 7}


def test_ssd_rows_map_to_the_summary_elements() -> None:
    rows = [
        ("Fund Type", "Index fund"),
        ("Stated Asset Allocation", "Equity 95-100%"),
        ("-", "Debt 0-5%"),
        ("Benchmark Tier 1", "Nifty 500 TRI"),
        ("Fund Manager 1 -  Name", "Mr. A B"),
        ("Fund Manager 1 - From Date", " 6-Sep-2019 "),
        ("Fund Manager 2 -  Name", "Ms. C D"),
        ("Fund Manager 2 - From Date", "01/04/2024"),
        ("Fund Manager 3 - Name", "-"),
        ("Exit Load", "Yes"),
        ("ISINS", "INF247L01957"),
        ("AMFI Codes to be phased out", "147625 and 147626"),
        ("SIP", ""),
        ("Frequency", "Annual"),
        ("", "Monthly"),
        ("Minimum Amount", "6000"),
        ("", "500"),
    ]
    records = "".join(
        f'<record index="{i}"><Fund_Name_>{k}</Fund_Name_><F>{v}</F></record>'
        for i, (k, v) in enumerate(rows)
    )
    xml = f"<data><columns /><records>{records}</records></data>".encode()
    found = a.parse_ssd(_raw(xml), 9, date(2026, 10, 24))
    facts = {f.name: f.txt for f in found.facts}
    assert facts == {
        "ssd:Fund_Type": "Index fund",
        "ssd:Stated_Asset_Allocation": "Equity 95-100%, Debt 0-5%",
        "ssd:Benchmark_Tier_1": "Nifty 500 TRI",
        "ssd:Fund_Manager_Name": "Mr. A B, Ms. C D",
        "ssd:Fund_Manager_From_Date": "Mr. A B - 6-Sep-2019, Ms. C D - 01/04/2024",
        "ssd:Exit_Load_if_applicable": "Yes",
        "ssd:ISINs": "INF247L01957",
        "ssd:AMFI_Codes_To_be_phased_out": "147625 and 147626",
        "ssd:SIP_SWP__STP_Details_Frequency": "SIP - Annual, Monthly",
        "ssd:SIP_SWP__STP_Details_Minimum_amount": "SIP - Monthly: 500, Annual: 6000",
    }
    assert found.isins == {"INF247L01957": 9}
    assert found.codes == {"147625": 9, "147626": 9}
    assert [d.isoformat() for _, d in e.manager_starts(facts["ssd:Fund_Manager_From_Date"])] == [
        "2019-09-06",
        "2024-04-01",
    ]
    with pytest.raises(a.SourceLayoutError):
        a.parse_ssd(_raw(b"<data><other /></data>"), 9, date(2026, 10, 24))


def _performance(rows: list[dict[str, object]]) -> bytes:
    queries = [{"body": {}, "data": rows}, {"body": {}, "data": rows[:1]}]
    return json.dumps({"day": "2026-10-22", "queries": queries}).encode()


def test_performance_joins_by_name_then_nav_pair_and_drops_repeats() -> None:
    by_name = {
        "schemeName": "Alpha Flexi Cap Fund",
        "benchmark": "Nifty 500 TRI",
        "riskometerScheme": "Very High",
        "return1YearRegular": -5.0,
        "return1YearDirect": -4.5,
        "return1YearBenchmark": -6.0,
        "returnSinceLaunchBenchmarkDirect": 11.8,
        "ir3YrDirect": 0.28,
        "dailyAUM": 1234.5,
        "navRegular": 50.0,
        "navDirect": 55.0,
    }
    by_nav = {
        "schemeName": "Gamma Fund Renamed",
        "benchmark": "Nifty 50 TRI",
        "navRegular": 12.344,
        "navDirect": 13.0,
    }
    lost = {"schemeName": "Lost Fund", "navRegular": 10.0, "navDirect": 10.0}
    navs = nav_index({8: [Decimal("12.3400"), Decimal("13.0000")], 9: [Decimal("10.0000")]})
    found = a.parse_performance(
        _raw(_performance([by_name, by_nav, lost])),
        date(2026, 10, 22),
        {"alphaflexicapfund": 7},
        navs,
    )
    facts = {(f.sd_id, f.name, f.plan): f.num if f.num is not None else f.txt for f in found.facts}
    assert facts[(7, "ret_1y", REGULAR)] == Decimal("-5.0")
    assert facts[(7, "bench_ret_1y", SCHEME)] == Decimal("-6.0")
    assert facts[(7, "bench_ret_si", DIRECT)] == Decimal("11.8")
    assert facts[(7, "ir_3y", DIRECT)] == Decimal("0.28")
    assert facts[(7, "aum_cr", SCHEME)] == Decimal("1234.5")
    assert facts[(7, "benchmark", SCHEME)] == "Nifty 500 TRI"
    assert facts[(7, "riskometer", SCHEME)] == "Very High"
    assert facts[(8, "benchmark", SCHEME)] == "Nifty 50 TRI"  # joined by its NAV pair
    assert len(found.facts) == len(facts)  # the repeated listing added nothing
    assert found.unmatched == 1  # equal NAVs (10.00 and 10.00) are one value, not a pair


def test_a_nav_pair_must_point_to_one_scheme() -> None:
    index = nav_index({1: [Decimal("10.00"), Decimal("12.00")], 2: [Decimal("10.00")]})
    assert join_by_navs(index, [Decimal("10.001"), Decimal("12.0")]) == 1
    assert join_by_navs(index, [Decimal("10.00"), None]) is None
    assert join_by_navs(index, [Decimal("12.00"), Decimal("12.00")]) is None
    assert join_by_navs(index, [Decimal("10.00"), Decimal("11.00")]) is None


def test_a_name_two_schemes_share_joins_neither() -> None:
    schemes = [SchemeRef(1, 9, "Alpha Fund"), SchemeRef(2, 9, "ALPHA  fund"), SchemeRef(3, 9, "B")]
    codes, names = scheme_keys(schemes, {3: "ABC / O / 1"})
    assert names == {"b": 3}
    assert codes == {"abco1": 3}


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("NIFTY500(TRI)", "Nifty 500 TRI"),
        ("BSE 500 Index (TRI)", "BSE 500 Total Returns Index (TRI)"),
        ("S&P BSE 500 TRI", "BSE 500 TRI"),
        ("Nifty 50 Total Return Index", "NIFTY 50 TRI"),
    ],
)
def test_benchmark_names_as_filed_share_a_key(left: str, right: str) -> None:
    assert e.benchmark_key(left) == e.benchmark_key(right)


def test_nifty_50_and_nifty_500_keep_apart() -> None:
    assert e.benchmark_key("Nifty 50 TRI") != e.benchmark_key("Nifty 500 TRI")


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("24/05/2013", date(2013, 5, 24)),
        ("24-May-2013", date(2013, 5, 24)),
        ("24.05.2013", date(2013, 5, 24)),
        ("May 24, 2013", date(2013, 5, 24)),
        ("05 Jul 2023", date(2023, 7, 5)),
        ("9th November, 2011", date(2011, 11, 9)),
        ("Since 20-Mar-26", date(2026, 3, 20)),
        ("no date", None),
    ],
)
def test_ssd_dates_parse(text: str, day: date | None) -> None:
    assert e.parse_day(text) == day


def test_tenure_reads_the_earliest_of_every_filed_start_date() -> None:
    assert min(e.all_days("FM1 24-October-2025 FM 2 01-Feb-2015")) == date(2015, 2, 1)
    assert e.all_days("01/07/2026 (Mr. A), 21/10/2024 (Mr. B)") == [
        date(2026, 7, 1),
        date(2024, 10, 21),
    ]


def test_manager_start_dates_parse_from_the_filed_text() -> None:
    text = (
        "Mr. Rajeev Thakkar - 24/05/2013 , Mr. Rukun Tarachandani - 16/05/2022, "
        "Mr. Tejas Soman - 01/09/2025 Ms. Mansi Kariya - 22/12/2023"
    )
    starts = e.manager_starts(text)
    assert ("Mr. Rajeev Thakkar", date(2013, 5, 24)) in starts
    assert ("Mr. Rukun Tarachandani", date(2022, 5, 16)) in starts
    assert min(d for _, d in starts) == date(2013, 5, 24)


def _view(facts: dict[tuple[str, str], list[FactPoint]]) -> FactView:
    latest = {k: v[-1] for k, v in facts.items()}
    return FactView({100: 7}, {7: latest}, {7: facts})


def _p(day: date, num: float | None = None, txt: str | None = None) -> FactPoint:
    return FactPoint(day.toordinal(), num, txt)


AS_OF = date(2026, 10, 22)


def test_fact_fields_resolve_the_plan_and_convert_percent() -> None:
    view = _view(
        {
            ("ter", DIRECT): [_p(date(2025, 9, 1), 0.80), _p(date(2026, 9, 1), 0.69)],
            ("ter", REGULAR): [_p(date(2026, 9, 1), 1.30)],
            ("aum_cr", SCHEME): [_p(date(2025, 10, 22), 1000.0), _p(AS_OF, 1500.0)],
            ("riskometer", SCHEME): [_p(AS_OF, txt="Very High")],
            ("benchmark", SCHEME): [_p(AS_OF, txt="NIFTY 500 TRI")],
            ("bench_ret_3y", SCHEME): [_p(AS_OF, 12.0)],
            ("ret_3y", DIRECT): [_p(AS_OF, 14.5)],
            ("ssd:Fund_Manager_From_Date", SCHEME): [_p(AS_OF, txt="Mr. A B - 22/10/2016")],
            ("ssd:Fund_Manager_Name", SCHEME): [_p(AS_OF, txt="Mr. A B, Ms. C D")],
            ("ssd:Minimum_Application_Amount", SCHEME): [_p(AS_OF, txt="Rs. 5,000 and more")],
            ("ssd:SIP_SWP__STP_Details_Minimum_amount", SCHEME): [
                _p(AS_OF, txt="SIP - Monthly: 1000 /Quarterly : 3000")
            ],
        }
    )
    facts = e.facts_of(view, 100, DIRECT, "open")
    values = e.fact_fields(facts, "growth", AS_OF.toordinal())
    assert values["ter"] == pytest.approx(0.0069)
    assert values["ter_change_1y"] == pytest.approx(-0.0011)
    assert values["aum_cr"] == 1500.0
    assert values["aum_change_1y"] == pytest.approx(0.5)
    assert values["riskometer_level"] == 6
    assert values["excess_3y"] == pytest.approx(0.025)
    assert values["manager_count"] == 2
    assert values["manager_tenure_y"] == pytest.approx(10.0, abs=0.01)
    assert values["min_lumpsum"] == 5000.0
    assert values["min_sip"] == 1000.0
    idcw = e.fact_fields(facts, "idcw", AS_OF.toordinal())
    assert idcw["excess_3y"] == Missing("NM", GROWTH_ONLY)
    regular = e.fact_fields(e.facts_of(view, 100, REGULAR, "open"), "growth", AS_OF.toordinal())
    assert regular["ter_change_1y"] == Missing("NA", NO_YEAR_AGO)
    assert e.facts_of(view, 999, DIRECT, "open") is None
    assert e.fact_fields(None, "growth", 0)["ter"] == Missing("NA", NO_SCHEME)


def test_ter_ranks_put_the_cheapest_first() -> None:
    values = {pid: {"ter": ter} for pid, ter in enumerate([0.005, 0.01, 0.015, 0.02, 0.025])}
    values[9] = {"ter": Missing("NA", "not_filed")}
    e.cost_ranks({("Flexi", DIRECT, "growth"): [*range(5), 9]}, values)
    assert values[0]["ter_cat_pct"] == 100.0
    assert values[4]["ter_cat_pct"] == 0.0
    assert values[2]["ter_cat_median"] == 0.015
    assert values[9]["ter_cat_pct"] == Missing("NA", "not_filed")


def _series(start: date, returns: np.ndarray) -> tuple[list[int], list[float]]:
    days, level, levels = [], 100.0, []
    day = start
    for r in [0.0, *returns]:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        level *= 1 + r
        days.append(day.toordinal())
        levels.append(level)
        day += timedelta(days=1)
    return days, levels


def test_proxy_statistics_match_an_independent_recompute() -> None:
    rng = np.random.default_rng(7)
    market = rng.normal(0.0004, 0.01, 780)
    fund = 1.2 * market + rng.normal(0.0001, 0.002, 780)
    days, proxy_levels = _series(date(2023, 7, 3), market)
    _, fund_levels = _series(date(2023, 7, 3), fund)
    rf = RiskFree.of([(date(2023, 1, 1).toordinal(), 6.5), (days[-1] - 10, 6.5)])
    got = e.proxy_fields(DailyNavs(1, days, fund_levels), DailyNavs(2, days, proxy_levels), rf)

    frame = pd.DataFrame({"f": fund_levels, "p": proxy_levels}).pct_change().dropna()
    beta = frame.cov().loc["f", "p"] / frame["p"].var()
    te = (frame["f"] - frame["p"]).std() * math.sqrt(252)
    years = (days[-1] - days[0]) / 365.25
    cagr_f = (fund_levels[-1] / fund_levels[0]) ** (1 / years) - 1
    cagr_p = (proxy_levels[-1] / proxy_levels[0]) ** (1 / years) - 1
    rf_cagr = rf.annualised(days[0], days[-1])
    assert isinstance(rf_cagr, float)
    months = (
        pd.Series(fund_levels, index=pd.to_datetime([date.fromordinal(d) for d in days]))
        .resample("ME")
        .last()
    )
    bench = (
        pd.Series(proxy_levels, index=pd.to_datetime([date.fromordinal(d) for d in days]))
        .resample("ME")
        .last()
    )
    mf, mb = months.pct_change().dropna(), bench.pct_change().dropna()
    up = mb > 0
    geo = lambda s: float(np.prod(1 + s) ** (1 / len(s)) - 1)  # noqa: E731

    assert got["beta_3y"] == pytest.approx(beta, rel=1e-9)
    assert got["te_3y"] == pytest.approx(te, rel=1e-9)
    assert got["r2_3y"] == pytest.approx(frame.corr().loc["f", "p"] ** 2, rel=1e-9)
    assert got["alpha_3y"] == pytest.approx(cagr_f - rf_cagr - beta * (cagr_p - rf_cagr), rel=1e-9)
    assert got["ir_3y_proxy"] == pytest.approx((cagr_f - cagr_p) / te, rel=1e-9)
    assert got["up_capture_3y"] == pytest.approx(geo(mf[up]) / geo(mb[up]), rel=1e-9)
    assert got["down_capture_3y"] == pytest.approx(geo(mf[~up]) / geo(mb[~up]), rel=1e-9)
    assert got["beta_3y"] == pytest.approx(1.2, abs=0.02)


def test_no_proxy_and_short_history_are_reasons_not_numbers() -> None:
    rf = RiskFree.of([])
    assert e.proxy_fields(None, None, rf)["beta_3y"] == Missing("NA", NO_PROXY)
    days, levels = _series(date(2026, 1, 1), np.full(100, 0.001))
    short = DailyNavs(1, days, levels)
    assert e.proxy_fields(short, short, rf)["beta_3y"].reason == "history_too_short"  # type: ignore[union-attr]


def test_the_proxy_is_the_lowest_filed_tracking_error_then_the_lower_id() -> None:
    chosen = e.choose_proxies(
        [
            (5, "5", "B Nifty 50 Index Fund", "Nifty 50 TRI", 0.05, 0.0),
            (4, "4", "A Nifty 50 Index Fund", "NIFTY 50 TRI", 0.05, 0.0),
            (3, "3", "C Nifty 50 ETF", "Nifty 50 TRI", 0.20, 0.0),
            (6, "6", "D Nifty 500 Index Fund", "Nifty 500 TRI", None, 0.0),
        ]
    )
    assert chosen[e.benchmark_key("Nifty 50 TRI")].pid == 4
    assert chosen[e.benchmark_key("Nifty 500 TRI")].pid == 6


def test_idcw_rows_join_by_amfi_code_and_keep_positive_rates() -> None:
    rows = {
        "2082": [
            {"SD_ID": 122168, "Div_year": "2026-03-02T00:00:00.000Z", "Rate_of_div": "0.0700"},
            {"SD_ID": 122168, "Div_year": "2026-03-02T00:00:00.000Z", "Rate_of_div": "0.0700"},
            {"SD_ID": 122168, "Div_year": "2026-04-01T00:00:00.000Z", "Rate_of_div": "0"},
        ]
    }
    found = a.parse_idcw(_raw(json.dumps(rows).encode()))
    assert [(d.amfi_code, d.record_date, str(d.per_unit)) for d in found] == [
        ("122168", date(2026, 3, 2), "0.0700")
    ]


def test_returns_with_idcw_reinvest_each_payout_at_its_record_date_nav() -> None:
    days, levels = _series(date(2025, 8, 1), np.zeros(300))  # NAV flat at 100, over a year
    as_of = days[-1]
    payout_day = days[200]
    start = date.fromordinal(days[0]).isoformat()
    anchors = {"ret_1y": start, "cagr_3y": start}
    got = e.idcw_fields("idcw", [(payout_day, 2.0)], DailyNavs(1, days, levels), as_of, anchors)
    assert got["idcw_count_1y"] == 1
    assert got["idcw_yield_1y"] == pytest.approx(0.02)
    assert got["ret_1y_with_idcw"] == pytest.approx(0.02)
    # Annualised over the anchor-to-last span, as cagr_3y is.
    span = days[-1] - days[0]
    assert got["cagr_3y_with_idcw"] == pytest.approx(1.02 ** (365.25 / span) - 1)
    # Without a 3Y anchor (a fund under 3 years old) the 3Y figure is missing.
    young = e.idcw_fields(
        "idcw", [(payout_day, 2.0)], DailyNavs(1, days, levels), as_of, {"ret_1y": start}
    )
    assert young["cagr_3y_with_idcw"] == Missing("NA", "history_too_short")
    growth = e.idcw_fields("growth", [], None, as_of, {})
    assert growth["idcw_1y"] == Missing("NM", "not_idcw_option")
