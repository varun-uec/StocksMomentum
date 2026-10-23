"""TigZig adapter: AMFI NAV history republished as one archive (ADR-023 U11).

TigZig (https://www.tigzig.com, by Amar Harolikar) builds the archive from AMFI's
daily NAV file and AMFI's historical archives and states "Source: AMFI". Its terms
give no warranty; its citation line asks for credit to the source URL and author.
Files, as observed on 2026-10-23:

- NAV history, every scheme since April 2006: ``amfi_nav_master.csv.gz``, columns
  ``scheme_code,date,nav,scheme_name,isin,source``, sorted by code, then date. NAVs
  are kept to 4 decimals.
- Scheme master with each scheme's latest NAV: ``amfi_nav_master_latest.csv.gz``.

Rows whose ``source`` is not ``MF`` (Specialized Investment Funds) are skipped.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import re
import shutil
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import IO

import httpx

from wickstreet.mf_data.domain.model import TIGZIG, NavRecord, RawFile, SchemeRecord
from wickstreet.mf_data.domain.ports import SourceError, SourceLayoutError
from wickstreet.mf_data.infrastructure.client import PacedClient

ARCHIVE_URL = "https://api.tigzig.com/mf/v1/download/amfi_nav_master.csv.gz"
SNAPSHOT_URL = "https://api.tigzig.com/mf/v1/download/amfi_nav_master_latest.csv.gz"
ARCHIVE_HEADER = ("scheme_code", "date", "nav", "scheme_name", "isin", "source")
_SNAPSHOT_COLUMNS = ("scheme_code", "scheme_name", "amc", "scheme_type", "category", "isin")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _nav(value: str) -> Decimal | None:
    return Decimal(value) if _NUMBER.fullmatch(value) else None


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return None if value in ("", "-") else value


def _lines(content: bytes) -> IO[str]:
    return io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(content)), "utf-8", newline="")


def split_archive(content: bytes, start: date, end: date, work_dir: Path) -> list[Path]:
    """Write the archive's MF rows in ``[start, end]`` to one file per month, in order.

    One pass over a file sorted by code; each month file is small enough to group
    by date in memory. The whole file is checked before anything is returned.
    """
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True)
    first, last = start.isoformat(), end.isoformat()
    months: dict[str, IO[str]] = {}
    try:
        with _lines(content) as text_file:
            reader = csv.reader(text_file)
            if tuple(next(reader, ())) != ARCHIVE_HEADER:
                raise SourceLayoutError("Unexpected archive header.")
            for row in reader:
                if len(row) != len(ARCHIVE_HEADER) or not row[0].isdigit():
                    raise SourceLayoutError(f"Unexpected archive row: {row[:3]}.")
                code, day, nav, _, _, kind = row
                if not _ISO_DATE.fullmatch(day):
                    raise SourceLayoutError(f"Unexpected archive date: {day!r}.")
                if kind != "MF" or not first <= day <= last:
                    continue
                month = months.get(day[:7])
                if month is None:
                    month = months[day[:7]] = (work_dir / f"{day[:7]}.csv").open("w")
                month.write(f"{code},{day},{nav}\n")
    except (UnicodeDecodeError, EOFError, gzip.BadGzipFile) as exc:
        raise SourceLayoutError(f"Archive cannot be read: {exc}") from exc
    finally:
        for month in months.values():
            month.close()
    return [work_dir / f"{key}.csv" for key in sorted(months)]


def read_month(path: Path) -> Iterator[tuple[date, list[NavRecord]]]:
    """Yield one month file's NAVs grouped by date, in date order."""
    by_day: dict[str, list[NavRecord]] = defaultdict(list)
    with path.open() as month:
        for line in month:
            code, day, nav = line.rstrip("\n").split(",")
            by_day[day].append(NavRecord(code, date.fromisoformat(day), _nav(nav)))
    for day in sorted(by_day):
        yield date.fromisoformat(day), by_day[day]


def parse_snapshot(content: bytes) -> list[SchemeRecord]:
    """Parse the scheme-master snapshot into ``schemes-v1`` records.

    The snapshot has no launch, closure or minimum amount, and its scheme name is
    the latest filed name, which also stands for the NAV name.
    """
    try:
        with _lines(content) as text_file:
            reader = csv.DictReader(text_file)
            missing = set(_SNAPSHOT_COLUMNS + ("isin2", "source")) - set(reader.fieldnames or ())
            if missing:
                raise SourceLayoutError(f"Snapshot lacks columns {sorted(missing)}.")
            records = []
            for row in reader:
                if row["source"] != "MF":
                    continue
                code = row["scheme_code"].strip()
                if not code.isdigit():
                    raise SourceLayoutError(f"Unexpected snapshot code: {code!r}.")
                name = row["scheme_name"].strip()
                records.append(
                    SchemeRecord(
                        amfi_code=code,
                        amc=row["amc"].strip(),
                        scheme_name=name,
                        scheme_type=row["scheme_type"].strip(),
                        category=row["category"].strip(),
                        nav_name=name,
                        min_amount=None,
                        launch_date=None,
                        closure_date=None,
                        isin_growth=_text(row["isin"]),
                        isin_reinvest=_text(row["isin2"]),
                    )
                )
    except (UnicodeDecodeError, EOFError, gzip.BadGzipFile) as exc:
        raise SourceLayoutError(f"Snapshot cannot be read: {exc}") from exc
    return records


class TigzigAdapter:
    """The TigZig implementation of ``ArchiveSource``."""

    name = TIGZIG
    adapter_version = "tigzig-2026-10-23"

    def __init__(
        self,
        *,
        work_dir: Path,
        min_interval_seconds: float,
        timeout_seconds: float,
        max_attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the adapter; month files go to ``work_dir``, outside the repository."""
        self._work_dir = work_dir
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

    async def _file(self, url: str) -> RawFile:
        response = await self._client.get(url)
        if response.status_code != 200:
            raise SourceError(f"{url}: HTTP {response.status_code}")
        return RawFile(str(response.url), datetime.now(UTC), response.content)

    async def archive(self) -> RawFile:
        """Fetch the NAV history archive."""
        return await self._file(ARCHIVE_URL)

    async def scheme_master(self) -> RawFile:
        """Fetch the scheme-master snapshot."""
        return await self._file(SNAPSHOT_URL)

    def parse_archive(
        self, raw: RawFile, start: date, end: date
    ) -> Iterator[tuple[date, list[NavRecord]]]:
        """Yield the archive's NAVs in ``[start, end]`` one date at a time, in date order."""
        for path in split_archive(raw.content, start, end, self._work_dir):
            yield from read_month(path)
            path.unlink()

    def parse_schemes(self, raw: RawFile) -> list[SchemeRecord]:
        """Parse the scheme-master snapshot."""
        return parse_snapshot(raw.content)
