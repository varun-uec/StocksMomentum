"""RBI adapter: the 91-day Treasury Bill cut-off yield from RBI files (doc 21 E2).

RBI's terms permit reproduction "provided an acknowledgement of the primary source is
made" (https://data.rbi.org.in/DBIE/#/dbie/disclaimer). RBI's file host answers
scripts with a bot challenge, so this adapter fetches nothing: a person downloads the
files and ``wickstreet mf import-rates`` imports them. Two layouts, as observed on
2026-10-23:

- Handbook of Statistics on the Indian Economy, "Auctions of 91-Day Government of
  India Treasury Bills" (one edition a year, auctions of about July to June): an
  XLSX with a "Date of Auction" column (Excel serial numbers, or ``01-Jul-2020`` text
  in the 2021 edition) and an "Implicit Yield at Cut-off Price" column.
- Press release "Treasury Bills: Full Auction Result" (one a week): HTML with
  "Date : Oct 14, 2026" and row III, the cut-off price, then "(YTM: 5.7281%)" for
  the 91-day bill. A week with no accepted bids shows "-" and gives no rate.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from wickstreet.mf_data.domain.model import RBI, TBILL_91, RatePoint, RawFile
from wickstreet.mf_data.domain.ports import SourceLayoutError
from wickstreet.mf_data.infrastructure.xlsx import first_sheet

_EXCEL_EPOCH = date(1899, 12, 30)
_DAY_TEXT = "%d-%b-%Y"
_RELEASE_DATE = re.compile(r"Date\s*:\s*([A-Z][a-z]{2} \d{1,2}, \d{4})")
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_YTM = re.compile(r"\(YTM:\s*([0-9.]+)%\)")


def _text(cell: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cell))).strip()


def _auction_day(value: str) -> date | None:
    try:
        return _EXCEL_EPOCH + timedelta(days=int(float(value)))
    except ValueError:
        pass
    try:
        return datetime.strptime(value, _DAY_TEXT).date()
    except ValueError:
        return None


def _yield(value: str) -> Decimal | None:
    try:
        # Spreadsheet floats carry binary noise (6.7809999999999997): 4 decimals as published.
        return Decimal(value).quantize(Decimal("0.0001"))
    except InvalidOperation:
        return None


def parse_handbook(content: bytes) -> list[RatePoint]:
    """Rates from a Handbook table: one per auction row with a date and a yield."""
    rows = first_sheet(content)
    header = next((r for r in rows if any("Implicit Yield" in v for v in r.values())), None)
    if header is None:
        raise SourceLayoutError("No 'Implicit Yield at Cut-off Price' column.")
    day_column = next((k for k, v in header.items() if v.startswith("Date of Auction")), None)
    yield_column = next(k for k, v in header.items() if "Implicit Yield" in v)
    if day_column is None:
        raise SourceLayoutError("No 'Date of Auction' column.")
    found = []
    for row in rows:
        day = _auction_day(row.get(day_column, ""))
        value = _yield(row.get(yield_column, ""))
        # The column-number row ("1", "13") parses as a 1899 date; real auctions are later.
        if day is not None and value is not None and day.year >= 1990:
            found.append(RatePoint(TBILL_91, day, value))
    return found


def parse_release(content: bytes) -> list[RatePoint]:
    """The 91-day rate from a weekly full auction result; empty when no bid was accepted."""
    page = content.decode("utf-8", "replace")
    start = page.find("Treasury Bills: Full Auction Result")
    if start < 0:
        raise SourceLayoutError("Not a 'Treasury Bills: Full Auction Result' release.")
    stated = _RELEASE_DATE.search(_text(page[start:]))
    if stated is None:
        raise SourceLayoutError("No release date.")
    day = datetime.strptime(stated.group(1), "%b %d, %Y").date()
    rows = [[_text(c) for c in _CELL.findall(r)] for r in _ROW.findall(page[start:])]
    header = next((r for r in rows if "91-Day" in r), None)
    cut_off = next((i for i, r in enumerate(rows) if any("Cut-off price" in c for c in r)), None)
    if header is None or cut_off is None or cut_off + 1 >= len(rows):
        raise SourceLayoutError("No cut-off row for the 91-day bill.")
    column = header.index("91-Day") - 1
    yields = rows[cut_off + 1]
    if column >= len(yields):
        return []
    found = _YTM.search(yields[column])
    return [RatePoint(TBILL_91, day, Decimal(found.group(1)))] if found else []


class RbiAdapter:
    """Parses RBI files a person obtained; never fetches."""

    name = RBI
    adapter_version = "rbi-2026-10-23.1"

    def parse_rates(self, raw: RawFile) -> list[RatePoint]:
        """Handbook XLSX (a zip) or a full auction result release (HTML)."""
        if raw.content[:2] == b"PK":
            return parse_handbook(raw.content)
        return parse_release(raw.content)
