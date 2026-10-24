"""Portfolio disclosures (doc 21 E4): the AMC workbook parser and the holdings analytics.

Synthetic workbooks only, shaped like the PPFAS and DSP files.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date
from decimal import Decimal

import httpx
import pytest

from tests.wickstreet.test_mf_facts import _xlsx
from wickstreet.analytics.domain import holdings as h
from wickstreet.mf_data.domain.facts import scheme_keys
from wickstreet.mf_data.domain.model import SchemeRef
from wickstreet.mf_data.domain.reads import HoldingRow, Portfolio
from wickstreet.mf_data.infrastructure.amc import (
    _LINK,
    AmcPortfolioAdapter,
    _first_month,
    _same_site,
    amc_adapters,
)
from wickstreet.mf_data.infrastructure.client import PacedClient
from wickstreet.mf_data.infrastructure.portfolios import parse_portfolios, sheet_codes

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


def test_manual_parser_reads_a_standard_csv_and_a_zip_of_csv_files() -> None:
    rows = [
        ["", "DSP Example Fund"],
        ["", "Portfolio as on September 30, 2026"],
        HEADER,
        ["", "EQUITY & EQUITY RELATED"],
        [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 60, 0.6],
        [2, "ICICI Bank Limited", "INE090A01021", "Banks", 100, 40, 0.4],
        ["", "Grand Total", "", "", "", 100, 1],
    ]
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerows(rows)
    content = text.getvalue().encode()

    direct = parse_portfolios(content, {"dspexamplefund": 7})
    assert [(line.name, line.weight) for line in direct.holdings] == [
        ("HDFC Bank Limited", Decimal("0.6")),
        ("ICICI Bank Limited", Decimal("0.4")),
    ]
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w") as files:
        files.writestr("fund.csv", content)
    zipped = parse_portfolios(bundle.getvalue(), {"dspexamplefund": 7})
    assert zipped.holdings == direct.holdings


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


def test_a_second_portfolio_of_one_scheme_is_listed_not_merged() -> None:
    """A segregated portfolio's name, its note dropped, joins the main scheme."""
    main = [
        ["SCHEME CODE080STARTS"],
        ["SCHEME: UTI Credit Risk Fund"],
        [
            "NAME OF THE INSTRUMENT",
            "RATING/INDUSTRY",
            "QUANTITY",
            "MARKET-VALUE",
            "% TO NAV",
            "ISIN",
        ],
        ["7.1% GOI 2034", "SOV", 10, 100, 100, "IN0020240019"],
        ["TOTAL : UTI Credit Risk Fund"],
    ]
    segregated = [
        ["SCHEME CODE081STARTS"],
        ["SCHEME: UTI Credit Risk Fund ( Segregated -06032020)"],
        *main[2:4],
    ]
    found = parse_portfolios(
        _xlsx([*main, *segregated]), {"uticreditriskfund": 3}, date(2026, 9, 30)
    )
    assert [(x.sd_id, x.weight) for x in found.holdings] == [(3, Decimal("1"))]
    assert found.unmatched == ["second portfolio of scheme 3"]


def test_tata_totals_end_rows_short_futures_swaps_and_lettered_headings() -> None:
    """Tata: totals named at the end, NET ASSETS closes, shorts in the equity section."""
    content = _xlsx(
        [
            ["", "TATA EXAMPLE FUND"],
            ["", "Portfolio as on 30-09-26"],
            ["", "NAME OF THE INSTRUMENT", "YIELD ( IN % )", "INDUSTRY", "ISIN CODE"]
            + ["QUANTITY", "MKT VAL(Rs. Lacs)", "% to NAV"],
            ["", "EQUITY & EQUITY RELATED"],
            ["", "A) LISTED/AWAITING LISTING ON STOCK EXCHANGES"],
            ["", "RELIANCE INDUSTRIES LTD", "NA", "Petroleum Products", "INE002A01018"]
            + [100, 59.5, 59.5],
            ["", "RELIANCE INDUSTRIES LTD^", "NA", "Petroleum Products", "INE002A01018"]
            + [-50, -30, -30],
            ["", "EQUITY & EQUITY RELATED TOTAL", "", "", "", "", 29.5, 29.5],
            ["", "IRS"],
            ["", "PAY FIXED 6.1% MD 2027", "", "", "", "", 20, 20],
            ["", "J) REPO", "", "", "", "", 41, 41],
            ["", "PORTFOLIO TOTAL", "", "", "", "", 100.5, 100.5],
            ["", "NET CURRENT LIABILITIES", "", "", "", "", -0.5, -0.5],
            ["", "NET ASSETS", "", "", "", "", 100, 100],
            ["", "A NOTE AFTER THE PORTFOLIO", "", "", "INE000000001", 1, 1, 1],
        ]
    )
    found = parse_portfolios(content, {"tataexamplefund": 4}, date(2026, 9, 30))
    assert [(x.name, x.asset, x.section, x.weight) for x in found.holdings] == [
        ("RELIANCE INDUSTRIES LTD", "equity", "A) LISTED/AWAITING LISTING ON STOCK EXCHANGES")
        + (Decimal("0.595"),),
        ("RELIANCE INDUSTRIES LTD^", "derivative", "A) LISTED/AWAITING LISTING ON STOCK EXCHANGES")
        + (Decimal("-0.3"),),
        ("PAY FIXED 6.1% MD 2027", "derivative", "IRS", Decimal("0.2")),
        ("J) REPO", "cash", "J) REPO", Decimal("0.41")),
        ("NET CURRENT LIABILITIES", "cash", "J) REPO", Decimal("-0.005")),
    ]


def test_futures_filed_in_percent_beside_fractions_are_read_apart() -> None:
    """Groww: fractions for holdings, percent for its futures, a sheet code before the name."""
    content = _xlsx(
        [
            ["AR", "IB67-Groww Example Arbitrage Fund"],
            ["", "Portfolio as on 30-SEP-2026"],
            ["", "ISIN", "Name of Instrument", "Rating/Industry", "Quantity"]
            + ["Market Value (In Rs. lakh)", "% To Net Assets"],
            ["", "", "EQUITY & EQUITY RELATED"],
            ["", "INE090A01021", "ICICI Bank Limited", "Banks", 100, 70, 0.7],
            ["", "", "DERIVATIVES"],
            ["", "", "ICICI Bank Limited Oct26", "Stock Futures", -100, -70.2, -70.2],
            ["", "", "TREPS"],
            ["", "", "Clearing Corporation of India", "", "", 30, 0.3],
            ["", "", "Grand Total", "", "", 100, 1],
        ]
    )
    found = parse_portfolios(content, {"growwexamplearbitragefund": 5})
    assert [(x.sd_id, x.asset, x.weight) for x in found.holdings] == [
        (5, "equity", Decimal("0.7")),
        (5, "derivative", Decimal("-0.702")),
        (5, "cash", Decimal("0.3")),
    ]


def test_a_scheme_is_named_inside_a_portfolio_statement_title() -> None:
    content = _xlsx(
        [
            ["", "SAMCO MUTUAL FUND"],
            [],
            ["", "MONTHLY PORTFOLIO STATEMENT OF SAMCO EXAMPLE FUND  AS ON September 30, 2026"],
            HEADER,
            [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 100, 1],
            ["", "Grand Total", "", "", "", 100, 1],
        ]
    )
    found = parse_portfolios(content, {"samcoexamplefund": 6})
    assert [(x.sd_id, x.as_of) for x in found.holdings] == [(6, date(2026, 9, 30))]


def test_numeric_month_end_dates_name_a_month_and_per_scheme_files_are_all_picked() -> None:
    adapters = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)
    base = "https://mf.example/docs/"
    monthly = [base + "Monthly Portfolio 31-07-2026-Final.xlsx"]
    monthly += [base + "Fortnightly Portfolio Report 31-07-2026.xlsx"]
    assert adapters["motilal"].pick(monthly, date(2026, 7, 31)) == monthly[0]
    each = [
        base + "FUND A Sep 2026.xlsx",
        "https://mirror.example/FUND A Sep 2026.xlsx",  # the same file on a second host
        base + "FUND B Sep 2026.xlsx",
        base + "FUND B Aug 2026.xlsx",
        base + "FUND C Fortnightly Sep 2026.xlsx",
        base + "Overnight_30092026_1791188043.xlsx",
    ]
    assert adapters["pgim"].picks(each, date(2026, 9, 30)) == [
        base + "FUND A Sep 2026.xlsx",
        base + "FUND B Sep 2026.xlsx",
        base + "Overnight_30092026_1791188043.xlsx",
    ]


def test_links_are_read_from_any_json_key_and_redirects_stay_on_the_site() -> None:
    assert _LINK.findall('{"publicUrl":"https://x.example/Monthly Portfolio - Sep 30.xlsx"}') == [
        "https://x.example/Monthly Portfolio - Sep 30.xlsx"
    ]
    assert _same_site(
        "https://betacms.tatamutualfund.com/a.xlsx", "https://www.tatamutualfund.com/a"
    )
    assert _same_site("https://www.x.co.in/a.xlsx", "/b.xlsx")
    assert not _same_site("https://www.miraeassetmf.co.in/a", "https://evil.co.in/a")
    assert not _same_site("https://tatamutualfund.com/a", "https://evil.com/a")


def _serve(adapter: AmcPortfolioAdapter, routes: dict[str, httpx.Response]) -> list[str]:
    """Answer the adapter from ``routes`` by URL path; return the URLs it asked for."""
    asked: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return routes[request.url.path]

    adapter._http = PacedClient(
        min_interval_seconds=0,
        timeout_seconds=1,
        max_attempts=1,
        transport=httpx.MockTransport(handle),
    )
    return asked


async def test_an_escaped_page_link_is_fetched_through_a_same_site_redirect() -> None:
    tata = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)["tata"]
    link = (
        "https://betacms.tatamutualfund.com/files/Monthly Portfolio as on 30th September 2026.xlsx"
    )
    page = '{\\"field_media_document\\":\\"' + link + '\\"}'
    moved = "https://www.tatamutualfund.com/system/files/september.xlsx"
    _serve(
        tata,
        {
            "/schemes-related/portfolio": httpx.Response(200, text=page),
            "/files/Monthly Portfolio as on 30th September 2026.xlsx": httpx.Response(
                302, headers={"location": moved}
            ),
            "/system/files/september.xlsx": httpx.Response(200, content=b"book"),
        },
    )
    raw = await tata.portfolio(date(2026, 9, 30))
    assert raw is not None
    assert (raw.url, raw.content) == (moved, b"book")


async def test_per_scheme_files_of_a_month_are_kept_as_one_repeatable_zip() -> None:
    samco = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)["samco"]
    names = [
        "IN_MF_MONTHLY_PORTFOLIO_September_2026_Samco_B_Fund_2.xlsx",
        "IN_MF_MONTHLY_PORTFOLIO_September_2026_Samco_A_Fund_1.xlsx",
    ]
    page = "".join(f'<a href="/docs/{n}">x</a>' for n in names)
    routes = {"/StatutoryDisclosure": httpx.Response(200, text=page)}
    routes |= {f"/docs/{n}": httpx.Response(200, content=n.encode()) for n in names}
    _serve(samco, routes)
    first = await samco.portfolio(date(2026, 9, 30))
    _serve(samco, routes)
    samco._links = None
    second = await samco.portfolio(date(2026, 9, 30))
    assert first is not None and second is not None
    assert first.content == second.content
    bundle = zipfile.ZipFile(io.BytesIO(first.content))
    assert bundle.namelist() == sorted(n.lower() for n in names)


async def test_whiteoak_and_trust_name_the_month_in_a_title_not_a_file_name() -> None:
    adapters = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)

    def row(name: str, url: str) -> dict[str, object]:
        return {
            "attributes": {"doc_name": name, "doc_file": {"data": {"attributes": {"url": url}}}}
        }

    cms = {
        "meta": {"pagination": {"pageCount": 1}},
        "data": [
            row(
                "A Fund Monthly Portfolio Disclosure - 30th September2026",
                "https://c.example/A_Sept.xlsx",
            ),
            row(
                "A Fund Monthly Portfolio Disclosure - 31st August2026",
                "https://c.example/A_Aug.xlsx",
            ),
        ],
    }
    whiteoak = adapters["whiteoak"]
    asked = _serve(
        whiteoak,
        {
            "/api/scheme-portfolios": httpx.Response(200, text=json.dumps(cms)),
            "/A_Sept.xlsx": httpx.Response(200, content=b"september"),
        },
    )
    raw = await whiteoak.portfolio(date(2026, 9, 30))
    assert raw is not None
    assert zipfile.ZipFile(io.BytesIO(raw.content)).read("a_sept.xlsx") == b"september"
    assert "filters%5Bperiod%5D%5B%24eq%5D=Monthly" in asked[0]

    trust = adapters["trust"]
    rows = {
        "resultSetArray": [
            {
                "title": "TRUSTMF Monthly Portfolio Report as on 31.08.2026",
                "fileurl": "https://t.example/Aug.xlsx",
            },
            {
                "title": "TRUSTMF Monthly Portfolio Report as on 30.09.2026",
                "fileurl": "https://t.example/Sep.xlsx",
            },
        ]
    }
    _serve(
        trust,
        {
            "/api/api/Trust/GetData": httpx.Response(200, text=json.dumps(rows)),
            "/Sep.xlsx": httpx.Response(200, content=b"sep"),
        },
    )
    found = await trust.portfolio(date(2026, 9, 30))
    assert found is not None and found.content == b"sep"


def test_a_title_names_the_month_of_its_first_date() -> None:
    assert _first_month("Portfolio as on 30th September 2023 for Apr 2026 Index Fund") == (
        2023,
        9,
    )
    assert _first_month("Disclosure - 30th September2026") == (2026, 9)
    assert _first_month("Report as on 30.09.2026") == (2026, 9)
    assert _first_month("Sep 30, 2026 - All Funds") == (2026, 9)
    assert _first_month("Fund Monthly Portfolio") is None


async def test_mirae_invesco_and_quantum_pick_the_month_by_title() -> None:
    adapters = amc_adapters(min_interval_seconds=0, timeout_seconds=1, max_attempts=1)
    mirae = adapters["mirae"]
    listing = {
        "DataCount": 3,
        "Data": [
            {"Title": "Portfolio Details as on 30th September 2026 for A Fund", "URL": "/a.xlsx"},
            {
                "Title": "Portfolio Details as on 31st August 2026 for Sep 2032 FMP",
                "URL": "/b.xlsx",
            },
            {"Title": "Fortnightly Portfolio as on 15th September 2026", "URL": "/c.xlsx"},
        ],
    }
    _serve(
        mirae,
        {
            "/AjaxService/GetDownloadsData": httpx.Response(200, text=json.dumps(listing)),
            "/a.xlsx": httpx.Response(200, content=b"a"),
        },
    )
    raw = await mirae.portfolio(date(2026, 9, 30))
    assert raw is not None
    assert zipfile.ZipFile(io.BytesIO(raw.content)).namelist() == ["a.xlsx"]

    invesco = adapters["invesco"]
    rows = [
        {
            "Name": "Invesco A Fund",
            "AugUrl": "https://i.example/aug.xlsx",
            "SepUrl": "https://i.example/sep.xlsx",
        }
    ]
    asked = _serve(
        invesco,
        {
            "/api/CompleteMonthlyHoldings": httpx.Response(200, text=json.dumps(rows)),
            "/sep.xlsx": httpx.Response(200, content=b"sep"),
        },
    )
    raw = await invesco.portfolio(date(2026, 9, 30))
    assert raw is not None
    assert zipfile.ZipFile(io.BytesIO(raw.content)).namelist() == ["sep.xlsx"]
    assert len([u for u in asked if "classification=" in u]) == len(invesco.CLASSES)

    quantum = adapters["quantum"]
    page = (
        "GTMcodeforxml('https://q.example/f/aug.xlsx', 'x', 'August 2026 - All Funds')"
        "GTMcodeforxml('https://q.example/f/sep.xlsx', 'x', 'September 2026 - All Funds')"
    )
    _serve(
        quantum,
        {
            "/portfolio/combined/-1/1/2026/0": httpx.Response(200, text=page),
            "/f/sep.xlsx": httpx.Response(200, content=b"sep"),
        },
    )
    raw = await quantum.portfolio(date(2026, 9, 30))
    assert raw is not None and raw.content == b"sep"


def _one_scheme(scheme: str) -> bytes:
    return _xlsx(
        [
            ["", scheme],
            ["", "Portfolio as on September 30, 2026"],
            HEADER,
            [1, "HDFC Bank Limited", "INE040A01034", "Banks", 100, 100, 1],
            ["", "Grand Total", "", "", "", 100, 1],
        ]
    )


def test_a_renamed_scheme_joins_its_old_months_by_sheet_code() -> None:
    """SBI renamed "SBI Arbitrage Opportunities Fund"; its sheet code stayed."""
    names = {"sbiarbitragefund": 11608}
    codes = sheet_codes(_one_scheme("SBI Arbitrage Fund"), names)
    assert list(codes.values()) == [11608]
    older = _one_scheme("SBI Arbitrage Opportunities Fund")
    assert parse_portfolios(older, names).holdings == []
    assert {x.sd_id for x in parse_portfolios(older, names, codes=codes).holdings} == {11608}
    # A code that names two sheets, as two workbooks' "Sheet1" in a zip, never counts.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("a.xlsx", _one_scheme("SBI Arbitrage Fund"))
        bundle.writestr("b.xlsx", _one_scheme("SBI Other Fund"))
    assert sheet_codes(buffer.getvalue(), names | {"sbiotherfund": 2}) == {}


def test_a_sheet_joins_by_its_whole_loose_name_only() -> None:
    _, names = scheme_keys(
        [
            SchemeRef(5, 9, "SBI Fixed Maturity Plan (FMP) - Series 1 (3668 Days)"),
            SchemeRef(6, 9, "SBI Debt Fund Series C - 27 (391 Days)"),
        ],
        {},
    )
    fmp = parse_portfolios(_one_scheme("SBI Fixed Maturity Plan (FMP)- Series 1"), names)
    assert {x.sd_id for x in fmp.holdings} == {5}
    other = _one_scheme("SBI Debt Fund Series C - 27 (1260 Days)")
    assert parse_portfolios(other, names).holdings == []
