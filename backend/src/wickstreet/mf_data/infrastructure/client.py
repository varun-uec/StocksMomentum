"""HTTP client shared by the MF source adapters (ADR-022 §2.11).

One request at a time, at least ``min_interval_seconds`` apart, with an honest
User-Agent. A transport error, 429 or 5xx is retried with a doubling wait.
Redirects are returned, not followed: AMFI signals an unserved date with one.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import httpx

from wickstreet.mf_data.domain.ports import SourceError

USER_AGENT = "Wickstreet/2.0 (self-hosted personal mutual-fund research)"


class PacedClient:
    """A throttled, retrying ``GET``."""

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
        """Create the client; ``transport`` replaces the network in tests."""
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._interval = min_interval_seconds
        self._attempts = max_attempts
        self._sleep = sleep
        self._clock = clock
        self._next_at = 0.0

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._client.aclose()

    async def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        """Return the first response that is not a 429 or 5xx, or raise :class:`SourceError`."""
        problem = ""
        for attempt in range(1, self._attempts + 1):
            wait = self._next_at - self._clock()
            if wait > 0:
                await self._sleep(wait)
            try:
                response = await self._client.get(url, params=params)
            except httpx.TransportError as exc:
                problem = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code != 429 and response.status_code < 500:
                    self._next_at = self._clock() + self._interval
                    return response
                problem = f"HTTP {response.status_code}"
            self._next_at = self._clock() + self._interval * 2**attempt
        raise SourceError(f"{url} failed after {self._attempts} attempts: {problem}")
