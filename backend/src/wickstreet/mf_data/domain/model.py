"""Import contracts for MF data (ADR-021 rule 1) and the records they carry.

``nav-v1`` is one NAV of one plan-option on one date. ``schemes-v1`` is one row of
the scheme master. A plan-option is identified by its AMFI scheme code; the store
keys it on a surrogate id (ADR-017 MF-2).

AMFI is the direct source. TigZig and MFAPI republish AMFI data; the owner chose
them for the dates AMFI no longer serves and for cross-checks (ADR-023 U11).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

AMFI = "amfi"
TIGZIG = "tigzig"
MFAPI = "mfapi"
NAV_CONTRACT = "nav-v1"
SCHEME_CONTRACT = "schemes-v1"
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
