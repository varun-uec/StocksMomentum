"""Monthly portfolio disclosures from AMC workbooks, and AMFI's market-cap list (doc 21 E4).

SEBI makes every AMC publish each scheme's portfolio, with ISINs, within 10 days of
month end "in a user-friendly and downloadable spreadsheet format". The layouts
differ by AMC, but each sheet has one header row with an ISIN column and a "% to net
assets" column. This parser finds that row, reads the scheme name and the date above
it, and reads every line under it:

- a line with a weight is a holding; a line with no weight and no figures is a section
  heading ("Equity & Equity related", "Debt Instruments", "TREPS");
- "Total" and "Sub Total" lines, and lines that end in "Total" (Tata), are skipped; the
  portfolio ends at "Grand Total", or at "Net Assets" (Tata);
- a futures or options line is a derivative, by its industry or contract month; other
  kinds come from the section, else from the line itself (TREPS is cash);
- weights filed as percentages are divided by 100, so every weight is a fraction.

A sheet joins its AMFI scheme by name. A sheet it cannot join is listed, never guessed.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from wickstreet.mf_data.domain.facts import compact
from wickstreet.mf_data.domain.model import (
    CASH,
    DEBT,
    DERIVATIVE,
    EQUITY,
    OTHER,
    CapClass,
    Holding,
    Portfolios,
)
from wickstreet.mf_data.domain.ports import SourceLayoutError
from wickstreet.mf_data.infrastructure.xlsx import XLS_SIGNATURE, Row, any_sheets, first_sheet

_WEIGHT = re.compile(r"%\s*(to|of)?\s*(the\s*)?(net\s*assets?|nav|aum|net\s*asset\s*value)", re.I)
_HEADERS = {
    "name": re.compile(
        r"name\s*of\s*(the\s*)?(instrument|security|issuer)|instrument\s*name|company|issuer|security\s*name",
        re.I,
    ),
    "isin": re.compile(r"\bisin\b", re.I),
    "industry": re.compile(r"industry|rating|sector", re.I),
    "quantity": re.compile(r"quantity|no\.?\s*of\s*(shares|units)", re.I),
    "value": re.compile(r"market.*value|fair\s*value|value\s*\(", re.I),
}
# The portfolio ends at its grand total; notes and ratio tables follow it.
_GRAND_TOTAL = re.compile(r"^\s*(grand\s*total\b|net\s*assets\s*$)", re.I)
_TOTAL = re.compile(r"^\s*(sub[\s-]*total|grand\s*total|total)\b|\btotal\s*$", re.I)
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_AS_ON = re.compile(
    r"(?:as\s*(?:on|at)|ended|ending)\s*:?\s*"
    r"(?:(\d{1,2})(?:st|nd|rd|th)?[\s\-/.]+([A-Za-z]{3,9}|\d{1,2})[\s\-/.,]+(\d{2,4})"
    r"|([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4}))",
    re.I,
)
# Section and line words to asset kinds, checked in this order.
_KINDS = (
    (
        CASH,
        (
            "treps",
            "tri-party",
            "triparty",
            "repo",
            "cblo",
            "net receivable",
            "net current",
            "cash",
            "margin",
        ),
    ),
    (DERIVATIVE, ("future", "option", "derivative", "swap")),
    (
        OTHER,
        ("mutual fund", "units of", "reit", "invit", "exchange traded", "etf", "gold", "silver"),
    ),
    (
        DEBT,
        (
            "debt",
            "bond",
            "debenture",
            "government securit",
            "g-sec",
            "treasury",
            "t-bill",
            "state development",
            "sdl",
            "certificate of deposit",
            "commercial paper",
            "money market",
            "ncd",
            "securitised",
            "pass through",
        ),
    ),
    (EQUITY, ("equity", "share", "stock", "listed", "preference")),
)


# A futures or options contract: "Tata Steel Limited Oct26", "NIFTY 23300 Call Oct26".
_CONTRACT = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{2}$", re.I)
# A sheet code before a scheme name: "IB43-".
_SHEET_CODE = re.compile(r"^[A-Z]{1,4}\d{1,3}\s*-\s*")
# The words around a scheme name in a title: "... PORTFOLIO STATEMENT OF <name> AS ON ...".
_TITLE = re.compile(r"^.*?portfolio\s+statement\s+of\s+|\s+as\s+(?:on|at)\b.*$", re.I | re.S)
# A section heading lettered "I) "; Tata files some with their own weight.
_LETTERED = re.compile(r"[A-Z]\)\s")
# Tata files interest rate swaps under a section named "IRS".
_SWAPS = re.compile(r"\s*irs\s*", re.I)


def _asset(
    section: str, industry: str | None, name: str, isin: str | None, quantity: Decimal | None
) -> str:
    """A line's asset kind: a derivative by industry or contract month, else by section.

    A futures or swap line is a derivative ("Stock Futures", "Interest Rate Swaps- MD
    ...") whatever section it is filed under. So is a line with a negative quantity: a
    fund holds no negative shares, so it is a short future, as Tata files them in its
    equity section. Other kinds come from the section, then from the line's name.
    """
    if (
        _kind(industry or "") == DERIVATIVE
        or (isin is None and _CONTRACT.search(name))
        or "swap" in name.lower()
        or _SWAPS.fullmatch(section)
        or (quantity is not None and quantity < 0)
    ):
        return DERIVATIVE
    return _kind(section) or _kind(name) or (EQUITY if isin and isin.startswith("INE") else OTHER)


def _kind(text: str) -> str | None:
    lowered = text.lower()
    for kind, words in _KINDS:
        if any(w in lowered for w in words):
            return kind
    return None


def _number(text: str | None) -> Decimal | None:
    if not text:
        return None
    try:
        value = Decimal(text.replace(",", "").replace("%", "").strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _day(text: str) -> date | None:
    found = _AS_ON.search(text)
    if found is None:
        return None
    if found.group(1):
        day, month, year = found.group(1), found.group(2), found.group(3)
    else:
        month, day, year = found.group(4), found.group(5), found.group(6)
    number = int(month) if month.isdigit() else _MONTHS.get(month[:3].lower())
    full = int(year) + 2000 if len(year) == 2 else int(year)
    try:
        return date(full, number or 0, int(day))
    except ValueError:
        return None


# One filed line: name, ISIN, industry, section, quantity, value, weight.
_Line = tuple[str, str | None, str | None, str, Decimal | None, Decimal | None, Decimal]


def _header(rows: list[Row]) -> tuple[int, dict[str, str]] | None:
    for i, row in enumerate(rows[:60]):
        weight = next((col for col, text in row.items() if _WEIGHT.search(text)), None)
        isin = next((col for col, text in row.items() if _HEADERS["isin"].search(text)), None)
        if weight and isin:
            columns = {"weight": weight, "isin": isin}
            for key in ("name", "industry", "quantity", "value"):
                found = next(
                    (
                        c
                        for c, t in row.items()
                        if c not in columns.values() and _HEADERS[key].search(t)
                    ),
                    None,
                )
                if found:
                    columns[key] = found
            columns.setdefault("name", min(row, key=lambda c: (len(c), c)))
            return i, columns
    return None


def _scheme(rows: list[Row], names: Mapping[str, int]) -> tuple[int | None, str]:
    """The first text above the header that names a scheme.

    Each text is tried whole, before '(' or ' - ', without a leading sheet code
    ("IB43-Groww Nifty 50 Index Fund", as Groww files them), and as a title's name
    ("MONTHLY PORTFOLIO STATEMENT OF SAMCO FLEXICAP FUND AS ON ...", as Samco does).
    """
    label = ""
    for row in rows:
        for text in row.values():
            if len(text) < 6 or text.replace(".", "").isdigit() or _BLOCK.match(text):
                continue
            label = label or text
            for candidate in (
                text,
                text.split("(")[0],
                text.split(" - ")[0],
                _SHEET_CODE.sub("", text),
                _TITLE.sub("", text),
            ):
                key = compact(
                    candidate.replace("Portfolio of", "")
                    .replace("Monthly Portfolio", "")
                    .removeprefix("SCHEME:")
                )
                if key in names:
                    return names[key], text
    return None, label


def _sheet(
    rows: list[Row], names: Mapping[str, int], fallback: date | None
) -> tuple[list[Holding], str | None]:
    found = _header(rows)
    if found is None:
        return [], None
    start, columns = found
    sd_id, label = _scheme(rows[:start], names)
    if sd_id is None:
        return [], label or "(no scheme name)"
    as_of = next((d for r in rows[:start] for t in r.values() if (d := _day(t))), None) or fallback
    if as_of is None:
        raise SourceLayoutError(f"No disclosure date above the header for {label}.")
    own = compact(label.removeprefix("SCHEME:")) or "\0"
    lines: list[_Line] = []
    section = ""
    for row in rows[start + 1 :]:
        name = row.get(columns["name"], "") or next((t for t in row.values() if t), "")
        weight = _number(row.get(columns["weight"]))
        if _GRAND_TOTAL.match(name) or (_TOTAL.match(name) and own in compact(name)):
            break  # UTI closes a portfolio with "TOTAL : <scheme>", then prints notes
        if not name or _TOTAL.search(name):
            continue
        isin = row.get(columns["isin"]) or None
        quantity = _number(row.get(columns.get("quantity", "")))
        value = _number(row.get(columns.get("value", "")))
        if isin is None and _LETTERED.match(name):
            section = name  # Tata files "I) REPO" as a heading with its own weight
        if weight is None:
            # A heading has no figures; a line with figures but no weight is skipped.
            if isin is None and quantity is None and value is None:
                section = name
            continue
        lines.append(
            (
                name,
                isin
                if isin and re.fullmatch(r"IN[A-Z0-9]{10}|[A-Z]{2}[A-Z0-9]{10}", isin)
                else None,
                row.get(columns.get("industry", "")) or None,
                section,
                quantity,
                value,
                weight,
            )
        )
    # Filed as percentages: a line above 1.5, or a total near 100 when every line is
    # small (a portfolio of 250 stocks); fraction sheets total 4 at most, headings and all.
    # Derivatives are judged apart: Groww files them in percent beside fractions, and
    # no future is 150% of net assets.
    future = [_asset(sc, ind, nm, isn, q) == DERIVATIVE for nm, isn, ind, sc, q, _, _ in lines]
    held = [line[-1] for line, f in zip(lines, future, strict=True) if not f]
    percent = any(abs(w) > Decimal("1.5") for w in held) or sum(held, Decimal(0)) > 50
    percent_futures = percent or any(
        abs(line[-1]) > Decimal("1.5") for line, f in zip(lines, future, strict=True) if f
    )
    lines = [
        (*line[:-1], line[-1] / 100 if (percent_futures if f else percent) else line[-1])
        for line, f in zip(lines, future, strict=True)
    ]
    lines = _without_subtotals(lines, Decimal(1))
    holdings = [
        Holding(
            sd_id,
            as_of,
            seq,
            name,
            isin,
            industry,
            section,
            _asset(section, industry, name, isin, quantity),
            quantity,
            value,
            weight,
        )
        for seq, (name, isin, industry, section, quantity, value, weight) in enumerate(lines)
    ]
    return holdings, None


def _off(lines: list[_Line], whole: Decimal) -> Decimal:
    """How far the lines miss net assets, with or without derivatives, whichever is closer."""
    every = sum((w for *_, w in lines), Decimal(0))
    held = sum(
        (
            w
            for name, isin, industry, section, quantity, _, w in lines
            if _asset(section, industry, name, isin, quantity) != DERIVATIVE
        ),
        Decimal(0),
    )
    return min(abs(every - whole), abs(held - whole))


def _without_subtotals(lines: list[_Line], whole: Decimal) -> list[_Line]:
    """Drop headings filed with their section's total weight, as ICICI files them.

    A line with a weight but no ISIN and no quantity is such a heading when the
    securities under it (lines with an ISIN or a quantity, up to the next cash or swap
    line) add up to its weight, within 0.05% of net assets. Headings are found from
    the bottom up, so a nested one is known before the heading above it, and its
    securities count once. They are dropped only when the sheet is more than 2% off its net assets
    with them and within 2% without them, counted with or without derivatives as the
    holdings check counts them; a sheet that reconciles is left alone. A line under
    dropped headings takes their names as its section, outermost first
    ("Debt Instruments / Listed").
    """
    tolerance, near = whole * Decimal("0.0005"), whole * Decimal("0.02")
    ends: dict[int, int] = {}
    for i in range(len(lines) - 1, -1, -1):
        _, isin, _, _, quantity, _, weight = lines[i]
        if isin is not None or quantity is not None:
            continue
        total = Decimal(0)
        for j in range(i + 1, len(lines)):
            if j in ends:
                continue
            if lines[j][1] is None and lines[j][4] is None:
                break  # a cash or swap line ends the section
            total += lines[j][-1]
            if abs(total - weight) <= tolerance:
                ends[i] = j
                break
    kept = [line for k, line in enumerate(lines) if k not in ends]
    if not ends or _off(lines, whole) <= near or _off(kept, whole) > near:
        return lines
    result = []
    for k, (name, isin, industry, section, quantity, value, weight) in enumerate(lines):
        if k in ends:
            continue
        headings = [lines[h][0] for h in sorted(ends) if h < k <= ends[h]]
        result.append(
            (name, isin, industry, " / ".join(headings) or section, quantity, value, weight)
        )
    return result


# UTI stacks every scheme on one sheet, each block opened by "SCHEME CODE002STARTS".
_BLOCK = re.compile(r"^\s*scheme\s*code\s*\w*\s*starts\s*$", re.I)


def _blocks(rows: list[Row]) -> list[list[Row]]:
    """A sheet's portfolios: the whole sheet, or each block a scheme-code line opens."""
    starts = [i for i, row in enumerate(rows) if any(_BLOCK.match(t) for t in row.values())]
    if not starts:
        return [rows]
    return [rows[a:b] for a, b in zip(starts, [*starts[1:], len(rows)], strict=True)]


def _workbooks(content: bytes) -> list[bytes]:
    """The workbooks in a file: the file itself, or each workbook inside a zip of them."""
    if content[:8] == XLS_SIGNATURE:
        return [content]
    book = zipfile.ZipFile(io.BytesIO(content))
    if any(n.startswith("xl/") for n in book.namelist()):
        return [content]
    return [
        book.read(n)
        for n in sorted(book.namelist())
        if n.lower().endswith((".xlsx", ".xlsm", ".xls"))
    ]


def parse_portfolios(
    content: bytes, names: Mapping[str, int], fallback: date | None = None
) -> Portfolios:
    """Every scheme portfolio in a workbook or a zip of workbooks."""
    if content[:2] != b"PK" and content[:8] != XLS_SIGNATURE:
        raise SourceLayoutError("Not an XLS or XLSX workbook, or a zip of them.")
    holdings: list[Holding] = []
    unmatched: list[str] = []
    seen: set[tuple[int, date]] = set()
    for workbook in _workbooks(content):
        for _, sheet in any_sheets(workbook):
            for rows in _blocks(sheet):
                found, missing = _sheet(rows, names, fallback)
                if found and (found[0].sd_id, found[0].as_of) in seen:
                    # A second portfolio for one scheme and date, such as its
                    # segregated portfolio: listed, never merged.
                    missing, found = f"second portfolio of scheme {found[0].sd_id}", []
                if found:
                    seen.add((found[0].sd_id, found[0].as_of))
                holdings.extend(found)
                if missing:
                    unmatched.append(missing)
    if not holdings and not unmatched:
        raise SourceLayoutError("No sheet has an ISIN and a % to net assets header.")
    return Portfolios(holdings, unmatched)


def parse_market_caps(content: bytes) -> list[CapClass]:
    """AMFI's average market capitalisation list: ISIN, company, ₹ crore and the class."""
    rows = first_sheet(content)
    title = next((t for r in rows[:3] for t in r.values() if "ended" in t.lower()), "")
    as_of = _day(title)
    header = next(
        (i for i, r in enumerate(rows[:10]) if any("ISIN" in t for t in r.values())), None
    )
    if as_of is None or header is None:
        raise SourceLayoutError("Not AMFI's market-cap list (no title date or ISIN header).")
    columns = rows[header]
    isin = next(c for c, t in columns.items() if "ISIN" in t)
    name = next((c for c, t in columns.items() if "Company" in t), isin)
    cap = next((c for c, t in columns.items() if t.startswith("Average of All")), None)
    kind = next((c for c, t in columns.items() if "Categori" in t), None)
    if kind is None:
        raise SourceLayoutError("No categorisation column in the market-cap list.")
    found = []
    for row in rows[header + 1 :]:
        code, label = row.get(isin, ""), row.get(kind, "")
        if re.fullmatch(r"IN[A-Z0-9]{10}", code) and label:
            found.append(
                CapClass(code, as_of, row.get(name, ""), _number(row.get(cap or "")), label)
            )
    if not found:
        raise SourceLayoutError("The market-cap list has no rows.")
    return found
