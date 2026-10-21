"""The reason a security is outside the reference universe matches the membership test."""

from datetime import date

import pytest

from momentum25.domain.universe import in_reference_universe, reference_universe_exclusion

DAY = date(2026, 10, 19)
EQUITY = "INE002A01018"
FUND = "INF204KB14I2"


@pytest.mark.parametrize(
    ("exchange", "isin", "listed", "delisted", "reason"),
    [
        ("NSE", EQUITY, None, None, None),
        ("BOTH", EQUITY, date(2000, 1, 1), None, None),
        ("BSE", EQUITY, None, None, "listed on BSE only"),
        ("NSE", FUND, None, None, "fund or ETF unit"),
        ("NSE", EQUITY, date(2027, 1, 4), None, "lists on 2027-01-04"),
        ("NSE", EQUITY, None, date(2026, 10, 19), "delisted on 2026-10-19"),
    ],
)
def test_reason_agrees_with_membership(
    exchange: str, isin: str, listed: date | None, delisted: date | None, reason: str | None
) -> None:
    text = reference_universe_exclusion(exchange, isin, listed, delisted, DAY)
    assert (text is None) == in_reference_universe(exchange, isin, listed, delisted, DAY)
    if reason is None:
        assert text is None
    else:
        assert text is not None
        assert reason in text
