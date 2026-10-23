"""The AMFI adapter on synthetic files and a fake network: parsing, redirects, retries, pacing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from tests.wickstreet.amfi_files import master_file, nav_file
from wickstreet.mf_data.domain.ports import SourceError, SourceLayoutError
from wickstreet.mf_data.infrastructure.amfi import (
    NAV_HEADER,
    AmfiAdapter,
    amfi_date,
    parse_nav_file,
    parse_scheme_master,
)
from wickstreet.mf_data.infrastructure.client import USER_AGENT

DAY = date(2026, 10, 1)


def test_dates_use_amfi_month_names_whatever_the_locale() -> None:
    assert amfi_date(date(2026, 3, 4)) == "04-Mar-2026"


def test_a_nav_file_parses_with_its_section_and_fund_house() -> None:
    records = parse_nav_file(nav_file(DAY, {"10001": "12.3456", "10002": "N.A.", "10003": "222."}))
    assert [r.amfi_code for r in records] == ["10001", "10002", "10003"]
    first = records[0]
    assert first.nav == Decimal("12.3456")
    assert first.nav_date == DAY
    assert first.amc == "Example Mutual Fund"
    assert first.category == "Open Ended Schemes ( Equity Scheme - Large Cap Fund )"
    assert (first.plan, first.option, first.isin_growth, first.isin_reinvest) == (
        "Direct Plan",
        "Growth",
        "INF000X10001",
        None,
    )
    assert records[1].nav is None
    assert records[2].nav == Decimal("222")  # AMFI writes some NAVs with a bare point


@pytest.mark.parametrize(
    "content",
    [
        b"Scheme Code;Something Else\r\n",
        f"{NAV_HEADER}\r\n10001;X;;;;;1;01-Oct-2026\r\n".encode(),
        f"{NAV_HEADER}\r\nOpen Ended Schemes ( A )\r\nFund\r\n10001;X;;;1;01-Oct-2026\r\n".encode(),
        f"{NAV_HEADER}\r\nOpen Ended Schemes ( A )\r\nFund\r\n"
        "10001;X;;;;;1;2026-10-01\r\n".encode(),
        b"\xff\xfe",
    ],
    ids=["header", "row-before-section", "seven-fields", "date-format", "not-utf8"],
)
def test_an_unknown_nav_layout_is_refused(content: bytes) -> None:
    with pytest.raises(SourceLayoutError):
        parse_nav_file(content)


def test_the_scheme_master_splits_joined_isins_and_keeps_blank_dates() -> None:
    (record,) = parse_scheme_master(master_file(["10001"]))
    assert record.amfi_code == "10001"
    assert (record.isin_growth, record.isin_reinvest) == ("INF000X10001", "INF000Y10001")
    assert (record.launch_date, record.closure_date) == (date(2013, 1, 1), None)
    assert record.min_amount == "5000"


def test_an_unknown_master_header_is_refused() -> None:
    with pytest.raises(SourceLayoutError):
        parse_scheme_master(b"AMC,Code\r\nX,1\r\n")


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


def _adapter(handler: httpx.MockTransport, clock: _Clock, attempts: int = 3) -> AmfiAdapter:
    return AmfiAdapter(
        min_interval_seconds=1.0,
        timeout_seconds=5,
        max_attempts=attempts,
        transport=handler,
        sleep=clock.sleep,
        clock=clock,
    )


async def test_a_redirect_means_amfi_does_not_serve_the_date() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://www.amfiindia.com/"})

    adapter = _adapter(httpx.MockTransport(handle), _Clock())
    assert await adapter.nav_day(date(2016, 10, 3)) is None
    assert seen[0].url.params["frmdt"] == seen[0].url.params["todt"] == "03-Oct-2016"
    assert seen[0].headers["user-agent"] == USER_AGENT
    await adapter.aclose()


async def test_requests_are_paced_and_server_errors_retried() -> None:
    replies = iter(
        [httpx.Response(503), httpx.Response(200, content=nav_file(DAY, {"10001": "1"}))]
    )
    clock = _Clock()
    adapter = _adapter(httpx.MockTransport(lambda request: next(replies)), clock)
    raw = await adapter.nav_day(DAY)
    assert raw is not None and raw.content.startswith(NAV_HEADER.encode())
    assert clock.waits == [2.0]  # the retry waits twice the interval
    await adapter.aclose()


async def test_every_request_waits_for_the_interval() -> None:
    clock = _Clock()
    content = nav_file(DAY, {"10001": "1"})
    adapter = _adapter(
        httpx.MockTransport(lambda request: httpx.Response(200, content=content)), clock
    )
    await adapter.nav_day(DAY)
    await adapter.nav_day(DAY)
    assert clock.waits == [1.0]
    await adapter.aclose()


async def test_persistent_failure_raises_after_the_last_attempt() -> None:
    clock = _Clock()

    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    adapter = _adapter(httpx.MockTransport(handle), clock, attempts=3)
    with pytest.raises(SourceError, match="after 3 attempts"):
        await adapter.nav_day(DAY)
    assert clock.waits == [2.0, 4.0]
    await adapter.aclose()
