"""Monthly portfolio disclosures from AMC workbooks, and AMFI's market-cap list (doc 21 E4).

SEBI makes every AMC publish each scheme's portfolio, with ISINs, within 10 days of
month end "in a user-friendly and downloadable spreadsheet format". The layouts
differ by AMC, but each sheet has one header row with an ISIN column and a "% to net
assets" column. This parser finds that row, reads the scheme name and the date above
it, and reads every line under it:

- a line with a weight is a holding; a line without one is a section heading
  ("Equity & Equity related", "Debt Instruments", "TREPS");
- "Total" and "Sub Total" lines are skipped, and the portfolio ends at "Grand Total";
- the asset kind comes from the section, else from the line itself (TREPS is cash);
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
_GRAND_TOTAL = re.compile(r"^\s*grand\s*total\b", re.I)
_TOTAL = re.compile(r"^\s*(sub[\s-]*total|grand\s*total|total)\b", re.I)
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_AS_ON = re.compile(
    r"(?:as\s*(?:on|at)|ended|ending)\s*:?\s*"
    r"(?:(\d{1,2})(?:st|nd|rd|th)?[\s\-/.]+([A-Za-z]{3,9}|\d{1,2})[\s\-/.,]+(\d{2,4})"
    r"|([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4}))",
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
            "reverse repo",
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
    """The first text above the header that names a scheme, tried whole and before '('."""
    label = ""
    for row in rows:
        for text in row.values():
            if len(text) < 6 or text.replace(".", "").isdigit():
                continue
            label = label or text
            for candidate in (text, text.split("(")[0], text.split(" - ")[0]):
                key = compact(
                    candidate.replace("Portfolio of", "").replace("Monthly Portfolio", "")
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
    lines: list[
        tuple[str, str | None, str | None, str, Decimal | None, Decimal | None, Decimal]
    ] = []
    section = ""
    for row in rows[start + 1 :]:
        name = row.get(columns["name"], "") or next((t for t in row.values() if t), "")
        weight = _number(row.get(columns["weight"]))
        if _GRAND_TOTAL.match(name):
            break
        if not name or _TOTAL.match(name):
            continue
        if weight is None:
            section = name
            continue
        isin = row.get(columns["isin"]) or None
        lines.append(
            (
                name,
                isin
                if isin and re.fullmatch(r"IN[A-Z0-9]{10}|[A-Z]{2}[A-Z0-9]{10}", isin)
                else None,
                row.get(columns.get("industry", "")) or None,
                section,
                _number(row.get(columns.get("quantity", ""))),
                _number(row.get(columns.get("value", ""))),
                weight,
            )
        )
    percent = any(abs(w) > Decimal("1.5") for *_, w in lines)
    holdings = [
        Holding(
            sd_id,
            as_of,
            seq,
            name,
            isin,
            industry,
            section,
            _kind(section) or _kind(name) or (EQUITY if isin and isin.startswith("INE") else OTHER),
            quantity,
            value,
            weight / 100 if percent else weight,
        )
        for seq, (name, isin, industry, section, quantity, value, weight) in enumerate(lines)
    ]
    return holdings, None


def _workbooks(content: bytes) -> list[bytes]:
    """The workbooks in a file: the file itself, or each workbook inside a zip of them."""
    if content[:8] == XLS_SIGNATURE:
        return [content]
    book = zipfile.ZipFile(io.BytesIO(content))
    if any(n.startswith("xl/") for n in book.namelist()):
        return [content]
    return [book.read(n) for n in sorted(book.namelist()) if n.lower().endswith((".xlsx", ".xls"))]


def parse_portfolios(
    content: bytes, names: Mapping[str, int], fallback: date | None = None
) -> Portfolios:
    """Every scheme portfolio in a workbook or a zip of workbooks."""
    if content[:2] != b"PK" and content[:8] != XLS_SIGNATURE:
        raise SourceLayoutError("Not an XLS or XLSX workbook, or a zip of them.")
    holdings: list[Holding] = []
    unmatched: list[str] = []
    for workbook in _workbooks(content):
        for _, rows in any_sheets(workbook):
            found, missing = _sheet(rows, names, fallback)
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
