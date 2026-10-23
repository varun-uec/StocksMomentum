"""MFAPI adapter: one plan-option's NAV history from api.mfapi.in (ADR-023 U11).

MFAPI republishes AMFI NAVs as JSON, one request per code. Wickstreet uses it only
to cross-check the store. Layout, as observed on 2026-10-23:
``{"meta": {...}, "data": [{"date": "22-10-2026", "nav": "106.53250"}], "status": "SUCCESS"}``.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from wickstreet.mf_data.domain.model import MFAPI, RawFile
from wickstreet.mf_data.domain.ports import SourceError, SourceLayoutError
from wickstreet.mf_data.infrastructure.client import PacedClient

HISTORY_URL = "https://api.mfapi.in/mf/{code}"


def parse_history(content: bytes) -> dict[date, Decimal | None]:
    """Parse one history into NAVs by date; a non-numeric NAV is ``None``."""
    try:
        body = json.loads(content)
        if body.get("status") != "SUCCESS":
            raise SourceLayoutError(f"MFAPI status {body.get('status')!r}.")
        navs: dict[date, Decimal | None] = {}
        for row in body["data"]:
            day, month, year = row["date"].split("-")
            try:
                value: Decimal | None = Decimal(row["nav"])
            except InvalidOperation:
                value = None
            navs[date(int(year), int(month), int(day))] = value
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SourceLayoutError(f"Unexpected MFAPI history: {exc}") from exc
    return navs


class MfapiAdapter:
    """The MFAPI implementation of ``ReferenceSource``."""

    name = MFAPI
    adapter_version = "mfapi-2026-10-23"

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

    async def history(self, amfi_code: str) -> RawFile:
        """Fetch the history of one code."""
        url = HISTORY_URL.format(code=amfi_code)
        response = await self._client.get(url)
        if response.status_code != 200:
            raise SourceError(f"{url}: HTTP {response.status_code}")
        return RawFile(str(response.url), datetime.now(UTC), response.content)

    def parse_history(self, raw: RawFile) -> dict[date, Decimal | None]:
        """Parse one history."""
        return parse_history(raw.content)
