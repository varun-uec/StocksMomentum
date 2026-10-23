"""AMFI adapter: direct from amfiindia.com, throttled, with retries (ADR-022 §2.11).

It uses AMFI's own download forms, as observed on 2026-10-23:

- NAV history, all schemes for one date:
  ``DownloadNAVHistoryReport_Po.aspx?frmdt=DD-Mon-YYYY&todt=DD-Mon-YYYY``. A date
  AMFI does not serve (before 2023-04-03) redirects to the download page.
- Scheme master, every plan-option including closed ones:
  ``DownloadSchemeData_Po.aspx?mf=0``.
"""

from __future__ import annotations

import asyncio
import csv
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

from wickstreet.mf_data.domain.model import AMFI, NavRecord, RawFile, SchemeRecord
from wickstreet.mf_data.domain.ports import SourceError, SourceLayoutError
from wickstreet.mf_data.infrastructure.client import PacedClient

NAV_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
SCHEME_MASTER_URL = "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx"

NAV_HEADER = (
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;"
    "ISIN Div Reinvestment;Net Asset Value;Date"
)
MASTER_HEADER = (
    "AMC",
    "Code",
    "Scheme Name",
    "Scheme Type",
    "Scheme Category",
    "Scheme NAV Name",
    "Scheme Minimum Amount",
    "Launch Date",
    "Closure Date",
    "ISIN Div Payout/ ISIN GrowthISIN Div Reinvestment",
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# AMFI writes some NAVs with a bare trailing point: "222." is 222.
_NUMBER = re.compile(r"-?\d+(\.\d*)?")
_ISIN = re.compile(r"INF[A-Z0-9]{9}")


def amfi_date(day: date) -> str:
    """Format a date as AMFI does, without depending on the locale: ``03-Oct-2026``."""
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def parse_amfi_date(text: str) -> date:
    """Parse ``03-Oct-2026``; raise :class:`SourceLayoutError` on anything else."""
    try:
        day, month, year = text.split("-")
        return date(int(year), _MONTHS.index(month) + 1, int(day))
    except ValueError as exc:
        raise SourceLayoutError(f"Unexpected date {text!r}.") from exc


def _blank(value: str) -> str | None:
    value = value.strip()
    return None if value in ("", "-") else value


def parse_nav_file(content: bytes) -> list[NavRecord]:
    """Parse a NAV history file into ``nav-v1`` records.

    Layout: a header line, then section lines (``Open Ended Schemes ( ... )``) and
    fund-house lines, each followed by ``;``-separated rows of eight fields. A row
    takes the latest section and fund house above it.
    """
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise SourceLayoutError("NAV file is not UTF-8.") from exc
    body = [line.strip() for line in lines if line.strip()]
    if not body or body[0] != NAV_HEADER:
        raise SourceLayoutError(f"Unexpected NAV header: {body[0] if body else '(empty)'!r}.")
    records: list[NavRecord] = []
    category = amc = None
    for line in body[1:]:
        if ";" not in line:
            if "Schemes" in line and "(" in line:
                category = " ".join(line.split())
            else:
                amc = " ".join(line.split())
            continue
        fields = line.split(";")
        if len(fields) != 8 or not fields[0].strip().isdigit():
            raise SourceLayoutError(f"Unexpected NAV row: {line[:120]!r}.")
        if category is None or amc is None:
            raise SourceLayoutError("A NAV row comes before its section and fund house.")
        code, name, plan, option, isin_growth, isin_reinvest, value, filed = fields
        value = value.strip()
        records.append(
            NavRecord(
                amfi_code=code.strip(),
                nav_date=parse_amfi_date(filed.strip()),
                nav=Decimal(value) if _NUMBER.fullmatch(value) else None,
                amc=amc,
                category=category,
                nav_name=name.strip(),
                plan=_blank(plan),
                option=_blank(option),
                isin_growth=_blank(isin_growth),
                isin_reinvest=_blank(isin_reinvest),
            )
        )
    return records


def parse_scheme_master(content: bytes) -> list[SchemeRecord]:
    """Parse the scheme master CSV into ``schemes-v1`` records.

    The last column holds up to two ISINs written together without a separator
    (growth or payout first, then reinvestment).
    """
    try:
        rows = list(csv.reader(content.decode("utf-8").splitlines()))
    except UnicodeDecodeError as exc:
        raise SourceLayoutError("Scheme master is not UTF-8.") from exc
    if not rows or tuple(cell.strip() for cell in rows[0]) != MASTER_HEADER:
        raise SourceLayoutError(
            f"Unexpected scheme-master header: {rows[0] if rows else '(empty)'}."
        )
    records: list[SchemeRecord] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(MASTER_HEADER) or not row[1].strip().isdigit():
            raise SourceLayoutError(f"Unexpected scheme-master row: {row[:3]}.")
        amc, code, name, kind, category, nav_name, minimum, launch, closure, isins = row
        found = _ISIN.findall(isins)
        records.append(
            SchemeRecord(
                amfi_code=code.strip(),
                amc=amc.strip(),
                scheme_name=name.strip(),
                scheme_type=kind.strip(),
                category=category.strip(),
                nav_name=nav_name.strip(),
                min_amount=_blank(minimum),
                launch_date=parse_amfi_date(launch.strip()) if launch.strip() else None,
                closure_date=parse_amfi_date(closure.strip()) if closure.strip() else None,
                isin_growth=found[0] if found else None,
                isin_reinvest=found[1] if len(found) > 1 else None,
            )
        )
    return records


class AmfiAdapter:
    """The AMFI implementation of ``NavSource``."""

    name = AMFI
    adapter_version = "amfi-2026-10-23.2"

    def __init__(
        self,
        *,
        min_interval_seconds: float,
        timeout_seconds: float,
        max_attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the adapter; ``transport`` replaces the network in tests."""
        self._client = PacedClient(
            min_interval_seconds=min_interval_seconds,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            transport=transport,
            sleep=sleep,
            clock=clock,
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def nav_day(self, day: date) -> RawFile | None:
        """Fetch all NAVs for ``day``; ``None`` when AMFI redirects (date not served)."""
        when = amfi_date(day)
        response = await self._client.get(NAV_HISTORY_URL, {"frmdt": when, "todt": when})
        if response.is_redirect:
            return None
        if response.status_code != 200:
            raise SourceError(f"NAV history for {day}: HTTP {response.status_code}")
        return RawFile(str(response.url), datetime.now(UTC), response.content)

    async def scheme_master(self) -> RawFile:
        """Fetch the scheme master."""
        response = await self._client.get(SCHEME_MASTER_URL, {"mf": "0"})
        if response.status_code != 200:
            raise SourceError(f"Scheme master: HTTP {response.status_code}")
        return RawFile(str(response.url), datetime.now(UTC), response.content)

    def parse_nav(self, raw: RawFile) -> list[NavRecord]:
        """Parse a NAV file."""
        return parse_nav_file(raw.content)

    def parse_schemes(self, raw: RawFile) -> list[SchemeRecord]:
        """Parse the scheme master."""
        return parse_scheme_master(raw.content)
