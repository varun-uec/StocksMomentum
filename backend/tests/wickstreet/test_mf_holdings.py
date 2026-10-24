"""Portfolio disclosures (doc 21 E4): the AMC workbook parser and the holdings analytics.

Synthetic workbooks only, shaped like the PPFAS and DSP files.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.wickstreet.test_mf_facts import _xlsx
from wickstreet.analytics.domain import holdings as h
from wickstreet.mf_data.domain.reads import HoldingRow, Portfolio
from wickstreet.mf_data.infrastructure.amc import _LINK, amc_adapters
from wickstreet.mf_data.infrastructure.portfolios import parse_portfolios

HEADER = [
    "Sr",
    "Name of Instrument",
    "ISIN",
    "Rating/Industry",
    "Quantity",
    "Market value",
    "% to Net Assets",
]


def _book(lines: list[list[str | float]]) -> bytes:
    return _xlsx(
        [
            ["", "DSP Example Fund"],
            ["", "Portfolio as on September 30, 2026"],
            HEADER,
            ["", "EQUITY & EQUITY RELATED"],
            *lines,
            ["", "Grand Total", "", "", "", 100, 1],
            ["", "Note: this line is after the total", "INE000000001", "", "", 1, 0.5],
        ]
    )


def test_the_parser_reads_lines_to_the_grand_total_as_fractions() -> None:
    content = _book(
        [
            [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 60, 0.6],
            ["", "Total", "", "", "", 60, 0.6],
            ["", "TREPS"],
            [2, "Clearing Corporation of India", "", "", "", 40, 0.4],
        ]
    )
    found = parse_portfolios(content, {"dspexamplefund": 7})
    assert [(x.name, x.asset, x.weight) for x in found.holdings] == [
        ("HDFC Bank Limited", "equity", Decimal("0.6")),
        ("Clearing Corporation of India", "cash", Decimal("0.4")),
    ]
    assert found.holdings[0].as_of == date(2026, 9, 30)
    assert found.holdings[0].sd_id == 7


def test_futures_are_derivatives_and_never_section_headings() -> None:
    """DSP files a hedge as a long stock line and a short "<stock> <month><yy>" line."""
    content = _book(
        [
            [1, "Tata Steel Limited", "INE081A01020", "Ferrous Metals", 1000, 81, 0.81],
            ["", "ARBITRAGE"],
            [2, "Axis Bank Limited", "INE238A01034", "Banks", 500, 19, 0.19],
            [3, "Axis Bank Limited Oct26", "", "Stock Futures", -500, -19.1, -0.191],
            [4, "Tata Steel Limited Nov26", "", "", -10, -0.2, ""],  # figures, no weight
            [5, "NIFTY 23300 Call Oct26", "", "Index Options", 91, 0.1, 0.001],
        ]
    )
    found = parse_portfolios(content, {"dspexamplefund": 7})
    kinds = {x.name: (x.asset, x.section) for x in found.holdings}
    assert kinds == {
        "Tata Steel Limited": ("equity", "EQUITY & EQUITY RELATED"),
        "Axis Bank Limited": ("equity", "ARBITRAGE"),
        "Axis Bank Limited Oct26": ("derivative", "ARBITRAGE"),
        "NIFTY 23300 Call Oct26": ("derivative", "ARBITRAGE"),
    }


def _icici(lines: list[list[str | float]]) -> bytes:
    """ICICI's layout: a section heading carries its section's total weight."""
    return _xlsx(
        [
            ["", "ICICI Prudential Example Fund"],
            ["", "Portfolio as on Sep 30,2026"],
            HEADER,
            *lines,
            ["", "Total Net Assets", "", "", "", 100, 1],
        ]
    )


def test_headings_filed_with_their_total_weight_are_not_holdings() -> None:
    content = _icici(
        [
            ["", "Equity & Equity Related Instruments", "", "", "", 70, 0.70],
            ["", "Listed / Awaiting Listing On Stock Exchanges", "", "", "", 70, 0.70],
            [1, "HDFC Bank Ltd.", "INE040A01034", "Banks", 100, 40, 0.40],
            [2, "Infosys Ltd.", "INE009A01021", "IT - Software", 50, 30, 0.30],
            ["", "Debt Instruments", "", "", "", 25, 0.25],
            ["", "Listed / Awaiting Listing On Stock Exchanges", "", "", "", 25, 0.25],
            [3, "7.10% GOI 2034", "IN0020240019", "SOV", 2500, 25, 0.25],
            ["", "TREPS", "", "", "", 3, 0.03],
            ["", "Interest Rate Swaps- MD -21-Feb-2029", "", "", "", 1, 0.01],
            ["", "Interest Rate Swaps- MD -21-Feb-2029", "", "", "", 1, 0.01],
            ["", "Net Current Assets", "", "", "", 2, 0.02],
        ]
    )
    found = parse_portfolios(content, {"iciciprudentialexamplefund": 9})
    assert [(x.name, x.asset, x.weight) for x in found.holdings] == [
        ("HDFC Bank Ltd.", "equity", Decimal("0.40")),
        ("Infosys Ltd.", "equity", Decimal("0.30")),
        ("7.10% GOI 2034", "debt", Decimal("0.25")),
        ("TREPS", "cash", Decimal("0.03")),
        ("Interest Rate Swaps- MD -21-Feb-2029", "derivative", Decimal("0.01")),
        ("Interest Rate Swaps- MD -21-Feb-2029", "derivative", Decimal("0.01")),
        ("Net Current Assets", "cash", Decimal("0.02")),
    ]
    assert found.holdings[2].section == (
        "Debt Instruments / Listed / Awaiting Listing On Stock Exchanges"
    )


def test_a_sheet_that_reconciles_keeps_a_cash_line_equal_to_the_lines_below() -> None:
    """Without double counting there is nothing to drop, whatever the sums look like."""
    content = _book(
        [
            [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 60, 0.6],
            [2, "Cash and margin", "", "", "", 20, 0.2],
            [3, "Axis Bank Limited", "INE238A01034", "Banks", 50, 20, 0.2],
        ]
    )
    found = parse_portfolios(content, {"dspexamplefund": 7})
    assert [x.name for x in found.holdings] == [
        "HDFC Bank Limited",
        "Cash and margin",
        "Axis Bank Limited",
    ]


def _row(
    name: str, isin: str | None, weight: float, asset: str = "equity", industry: str = "Banks"
) -> HoldingRow:
    return HoldingRow(name, isin, industry, "", asset, weight)


def test_a_hedged_portfolio_reconciles_without_its_futures() -> None:
    portfolio = Portfolio(
        date(2026, 9, 30),
        [
            _row("Axis Bank", "INE238A01034", 0.70),
            _row("Axis Bank Oct26", None, -0.69, "derivative", "Stock Futures"),
            _row("TREPS", None, 0.30, "cash", ""),
        ],
    )
    s = h.summary(portfolio, {})
    assert s["weight_sum"] == pytest.approx(1.0)
    assert s["reconciled"] is True
    assert s["assets"]["equity"] == pytest.approx(0.70)
    assert s["assets"]["derivative"] == pytest.approx(-0.69)
    # A long future counts inside the 100%; the payable that funds it is negative cash.
    long = Portfolio(
        date(2026, 9, 30),
        [
            _row("Axis Bank", "INE238A01034", 0.95),
            _row("NIFTY Oct26", None, 0.08, "derivative", "Index Futures"),
            _row("Net Payables", None, -0.03, "cash", ""),
        ],
    )
    assert h.summary(long, {})["weight_sum"] == pytest.approx(1.0)


def test_concentration_sectors_and_market_cap_are_of_the_equity_part() -> None:
    caps = {"INE1": [(date(2026, 6, 30), "Large Cap")], "INE2": [(date(2026, 6, 30), "Mid Cap")]}
    portfolio = Portfolio(
        date(2026, 9, 30),
        [
            _row("A", "INE1", 0.30, industry="Banks"),
            _row("B", "INE2", 0.10, industry="IT"),
            _row("C", "US0000000001", 0.40, industry="IT"),
            _row("Bond", "INE3", 0.20, "debt", "CRISIL AAA"),
        ],
    )
    s = h.summary(portfolio, caps)
    assert s["effective_holdings"] == pytest.approx(1 / (0.375**2 + 0.125**2 + 0.5**2))
    assert s["sectors"] == {"IT": pytest.approx(0.625), "Banks": pytest.approx(0.375)}
    assert s["market_cap"]["Large Cap"] == pytest.approx(0.375)
    assert s["market_cap"]["Foreign"] == pytest.approx(0.5)
    assert s["ratings"] == {"CRISIL AAA": pytest.approx(0.20)}
    fields = h.holding_fields(portfolio, caps)
    assert fields["top10_weight"] == pytest.approx(1.0)
    assert fields["mid_cap_share"] == pytest.approx(0.125)


def test_overlap_is_the_sum_of_the_smaller_weights_of_shared_securities() -> None:
    a = Portfolio(
        date(2026, 9, 30),
        [_row("X", "INE1", 0.5), _row("Y", "INE2", 0.3), _row("Cash", None, 0.2, "cash")],
    )
    b = Portfolio(
        date(2026, 9, 30),
        [_row("X", "INE1", 0.2), _row("Y", "INE2", 0.6), _row("Cash", None, 0.2, "cash")],
    )
    found = h.overlap(a, b)
    assert found["weighted_overlap"] == pytest.approx(0.2 + 0.3)
    assert found["common_count"] == 2
    assert found["same_month"] is True


def test_an_amc_page_link_is_picked_by_month_year_and_words() -> None:
    nippon = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)["nippon"]
    base = "https://mf.example/docs/"
    links = [
        base + "NIMF-FORTNIGHTLY-PORTFOLIO-30-Sep-26.xls",
        base + "NIMF-MONTHLY-PORTFOLIO-26-Sep-2025.xls",  # a day 26, not the year 2026
        base + "NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls",
        base + "NIMF-MONTHLY-PORTFOLIO-30-Nov-2024.xls",
        base + "NIMF-MONTHLY-PORTFOLIO-Nov-25.xls",
    ]
    assert nippon.pick(links, date(2026, 9, 30)) == base + "NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls"
    assert nippon.pick(links, date(2025, 9, 30)) == base + "NIMF-MONTHLY-PORTFOLIO-26-Sep-2025.xls"
    assert nippon.pick(links, date(2024, 11, 30)) == base + "NIMF-MONTHLY-PORTFOLIO-30-Nov-2024.xls"
    assert nippon.pick(links, date(2025, 11, 30)) == base + "NIMF-MONTHLY-PORTFOLIO-Nov-25.xls"
    assert nippon.pick(links, date(2026, 8, 31)) is None


def test_links_are_read_from_pages_and_json_listings() -> None:
    text = (
        '<a href="/docs/NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls?v=2">x</a>'
        '{"url":"/downloads/Files/2026/Sep/Monthly-Portfolio-Disclosure-September-2026.zip"}'
        '{"url":"/downloads/Files/factsheet.pdf"}'
    )
    assert _LINK.findall(text) == [
        "/docs/NIMF-MONTHLY-PORTFOLIO-30-Sep-26.xls",
        "/downloads/Files/2026/Sep/Monthly-Portfolio-Disclosure-September-2026.zip",
    ]


def test_one_sheet_can_stack_portfolios_each_closed_by_its_own_total() -> None:
    """UTI's layout: blocks opened by a scheme-code line, closed by "TOTAL : <scheme>"."""

    def block(code: str, scheme: str, isin: str) -> list[list[str | float]]:
        return [
            [f"SCHEME CODE{code}STARTS"],
            ["UTI MUTUAL FUND"],
            [f"SCHEME: {scheme}"],
            ["PORTFOLIO DISCLOSURE AS OF 30/09/2026"],
            [
                "NAME OF THE INSTRUMENT",
                "RATING/INDUSTRY",
                "QUANTITY",
                "MARKET-VALUE",
                "% TO NAV",
                "ISIN",
            ],
            ["EQ - HDFC BANK LIMITED", "Banks", 10, 90, 90, isin],
            ["NET CURRENT ASSETS", "", "", 10, 10, ""],
            [f"TOTAL : {scheme}", "", "", 100, "", ""],
            ["NAME OF THE SECURITY", "ISIN NO", "VALUE AS PER NCA", "%AGE TO NAV", "Total Amt Due"],
            ["CP - DEFAULTED PAPER", "INE008I14OM7", 0, 0, 9991.55],
            [f"SCHEME CODE{code}ENDS"],
        ]

    content = _xlsx(
        [
            *block("002", "UTI Alpha Fund", "INE040A01034"),
            *block("003", "UTI Beta Fund", "INE040A01034"),
        ]
    )
    found = parse_portfolios(content, {"utialphafund": 1, "utibetafund": 2}, date(2026, 9, 30))
    assert [(x.sd_id, x.name, x.weight) for x in found.holdings] == [
        (1, "EQ - HDFC BANK LIMITED", Decimal("0.9")),
        (1, "NET CURRENT ASSETS", Decimal("0.1")),
        (2, "EQ - HDFC BANK LIMITED", Decimal("0.9")),
        (2, "NET CURRENT ASSETS", Decimal("0.1")),
    ]


def test_small_weights_filed_as_percentages_are_read_as_percentages() -> None:
    """Every line under 1.5% (a broad index fund) but the total near 100: percentages."""
    lines: list[list[str | float]] = [
        [k, f"Company {k}", f"INE{k:09d}", "Banks", 1, 1, 1.0] for k in range(1, 101)
    ]
    found = parse_portfolios(_book(lines), {"dspexamplefund": 7})
    assert sum(x.weight for x in found.holdings) == Decimal("1")
