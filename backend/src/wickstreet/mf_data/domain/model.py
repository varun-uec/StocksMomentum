"""Import contracts for MF data (ADR-021 rule 1) and the records they carry.

``nav-v1`` is one NAV of one plan-option on one date. ``schemes-v1`` is one row of
the scheme master. A plan-option is identified by its AMFI scheme code; the store
keys it on a surrogate id (ADR-017 MF-2).

AMFI is the direct source. TigZig and MFAPI republish AMFI data; the owner chose
them for the dates AMFI no longer serves and for cross-checks (ADR-023 U11).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

AMFI = "amfi"
TIGZIG = "tigzig"
MFAPI = "mfapi"
RBI = "rbi"
NAV_CONTRACT = "nav-v1"
SCHEME_CONTRACT = "schemes-v1"
# Reference rates imported from files (doc 21 E2); no fetcher.
RATE_CONTRACT = "rates-v1"
# The 91-day Treasury Bill implicit yield at the auction cut-off price, % a year.
TBILL_91 = "tbill_91d_cutoff_yield"
REFRESH = "daily-refresh"
# Archive values are kept to 4 decimals; a smaller difference is rounding, not a conflict.
ARCHIVE_TOLERANCE = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class NavRecord:
    """One NAV as filed. ``nav`` is ``None`` when the source gives no number.

    The listing attributes come with AMFI's own files. An archive row carries the
    NAV only, so its attributes are ``None`` and no listing row is written.
    """

    amfi_code: str
    nav_date: date
    nav: Decimal | None
    amc: str | None = None
    category: str | None = None
    nav_name: str | None = None
    plan: str | None = None
    option: str | None = None
    isin_growth: str | None = None
    isin_reinvest: str | None = None


@dataclass(frozen=True, slots=True)
class SchemeRecord:
    """One scheme-master row as filed."""

    amfi_code: str
    amc: str
    scheme_name: str
    scheme_type: str
    category: str
    nav_name: str
    min_amount: str | None
    launch_date: date | None
    closure_date: date | None
    isin_growth: str | None
    isin_reinvest: str | None


@dataclass(frozen=True, slots=True)
class RawFile:
    """A source file exactly as fetched."""

    url: str
    fetched_at: datetime
    content: bytes

    @property
    def sha256(self) -> str:
        """Hash of the content; equal hashes mean an unchanged source (MF-7)."""
        return hashlib.sha256(self.content).hexdigest()


class Anomaly(StrEnum):
    """A row stored as filed but flagged for review (MF-8)."""

    MISSING = "nav_missing"
    ZERO = "nav_zero"
    NEGATIVE = "nav_negative"
    JUMP = "nav_jump"


@dataclass(frozen=True, slots=True)
class RatePoint:
    """One published rate: ``value`` in % a year, in force from ``day`` (an auction date)."""

    series: str
    day: date
    value: Decimal


# Scheme facts from AMFI's research pages (doc 21 E1, E3): TER, fund performance against
# the benchmark, scheme summary documents and index-fund tracking error. A scheme is
# AMFI's scheme id (``SD_Id``); its plan-options join through the ISINs it lists.
FACT_CONTRACT = "scheme-facts-v1"
SCHEME_LIST = "scheme-list"
TER_MONTH = "ter-month"
PERFORMANCE_DAY = "performance-day"
SSD = "ssd"
TRACKING_ERROR_DAY = "tracking-error-day"
# A fact's plan: the whole scheme, or one plan type of it.
SCHEME, REGULAR, DIRECT = "", "regular", "direct"


@dataclass(frozen=True, slots=True)
class SchemeRef:
    """One AMFI scheme: its id, its fund house's AMFI id and its name as listed."""

    sd_id: int
    mf_id: int
    name: str


@dataclass(frozen=True, slots=True)
class Fact:
    """One filed value of one scheme: a number or a text, in force from ``as_of``.

    ``plan`` is ``SCHEME`` for the whole scheme, else ``REGULAR`` or ``DIRECT``.
    """

    sd_id: int
    name: str
    plan: str
    as_of: date
    num: Decimal | None = None
    txt: str | None = None


@dataclass(frozen=True, slots=True)
class SchemeFacts:
    """What one facts file gave: the facts and the keys that join plans to schemes."""

    facts: list[Fact]
    isins: dict[str, int] = field(default_factory=dict)
    unmatched: int = 0
    # AMFI code -> scheme, from an SSD's own list; an ISIN listed directly wins.
    codes: dict[str, int] = field(default_factory=dict)


# Monthly portfolio disclosures (doc 21 E4): one row per filed line of one scheme's
# portfolio on its disclosure date. ``weight`` is a fraction of net assets.
HOLDINGS_CONTRACT = "holdings-v1"
HOLDINGS_MONTH = "holdings-month"
# AMFI's half-yearly market-cap list (SEBI categorisation of 6 Oct 2017).
MARKET_CAP = "market-cap"
EQUITY, DEBT, CASH, DERIVATIVE, OTHER = "equity", "debt", "cash", "derivative", "other"


@dataclass(frozen=True, slots=True)
class Holding:
    """One filed line of a scheme's portfolio: its section, asset kind and weight."""

    sd_id: int
    as_of: date
    seq: int
    name: str
    isin: str | None
    industry: str | None
    section: str
    asset: str
    quantity: Decimal | None
    value: Decimal | None
    weight: Decimal


@dataclass(frozen=True, slots=True)
class Portfolios:
    """What one disclosure file gave: the holdings, and sheets no scheme matched."""

    holdings: list[Holding]
    unmatched: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CapClass:
    """One company in AMFI's market-cap list: average market cap (₹ crore) and class."""

    isin: str
    as_of: date
    name: str
    market_cap_cr: Decimal | None
    cap_class: str


# IDCW payouts as AMFI lists them (doc 21 E5, M13): sourced records only, never inferred.
IDCW = "idcw"


@dataclass(frozen=True, slots=True)
class Distribution:
    """One IDCW payout of one plan-option: ₹ per unit, on its record date."""

    amfi_code: str
    record_date: date
    per_unit: Decimal
