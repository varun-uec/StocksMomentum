"""Survivorship / delisting classification (RP-012 §3.3).

Pure, I/O-free classification (ADR-009) of a security's listing and delisting
state from its observed bar coverage across the full ingested panel (both
``ohlcv_daily`` and ``legacy_ohlcv_daily`` combined).

Definitions (RP-012 §3.3):

* ``listing_date`` — the earliest observed bar date for the security (the first
  date it is known to have traded in our data).
* ``last_trade_date`` — the date of the security's last observed bar.
* delisting detection — a security is **delisted** iff it has no bar for at least
  ``GAP_THRESHOLD_TRADING_DAYS`` *consecutive trading days* through the end of the
  panel; equivalently, the number of panel trading dates strictly after its last
  bar is ``>= GAP_THRESHOLD_TRADING_DAYS``. This distinguishes a genuine
  delisting from a still-listed-but-illiquid security (whose final gap is short
  because it traded again near the panel end) without misclassifying a temporary
  illiquid gap.
* ``delisting_date`` — for a delisted security, the last observed trading date
  (the inclusive end of its ``[listing_date, delisting_date]`` trading interval,
  chosen so period-correct-split resolution of a bar dated ``D <= last_trade``
  falls inside the interval). ``None`` for a security still trading at panel end.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# T_gap — the consecutive-trading-day absence that constitutes a delisting.
GAP_THRESHOLD_TRADING_DAYS: int = 60


@dataclass(frozen=True, slots=True)
class SurvivorshipClassification:
    """The listing/delisting classification of a single security."""

    listing_date: date
    last_trade_date: date
    delisting_date: date | None
    delisted: bool


def classify_survivorship(
    first_bar: date,
    last_bar: date,
    trading_days_after_last_bar: int,
    gap_threshold: int = GAP_THRESHOLD_TRADING_DAYS,
) -> SurvivorshipClassification:
    """Classify a security from its bar coverage (pure).

    Args:
        first_bar: The security's earliest observed bar date (``listing_date``).
        last_bar: The security's last observed bar date (``last_trade_date``).
        trading_days_after_last_bar: Count of panel trading dates strictly after
            ``last_bar`` — i.e. the length of its final absence, in trading days.
        gap_threshold: The delisting threshold in consecutive trading days.

    Returns:
        A :class:`SurvivorshipClassification`. ``delisting_date`` equals
        ``last_bar`` when delisted, else ``None``.
    """
    delisted = trading_days_after_last_bar >= gap_threshold
    return SurvivorshipClassification(
        listing_date=first_bar,
        last_trade_date=last_bar,
        delisting_date=last_bar if delisted else None,
        delisted=delisted,
    )
