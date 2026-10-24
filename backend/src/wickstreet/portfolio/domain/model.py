"""A consolidated account statement (CAS) and the ledger it becomes (Slice 6).

The statement is parsed on this machine. The file and its password are never stored;
the ledger keeps each transaction, and each scheme's closing balance as filed, so
the computed units can be checked against the statement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from wickstreet.context import TenantContext

# Kinds as CAMS and KFintech name them (casparser's transaction types).
CASH_IN = frozenset({"PURCHASE", "PURCHASE_SIP", "SWITCH_IN", "SWITCH_IN_MERGER", "GIFT_IN"})
CASH_OUT = frozenset({"REDEMPTION", "SWITCH_OUT", "SWITCH_OUT_MERGER", "GIFT_OUT"})
TAXES = frozenset({"STT_TAX", "STAMP_DUTY_TAX", "TDS_TAX"})
PAYOUT = "DIVIDEND_PAYOUT"
REINVEST = "DIVIDEND_REINVEST"


class StatementError(Exception):
    """The file is not a readable CAS, or the password is wrong."""


class UnknownImportError(LookupError):
    """No import with that id belongs to the caller."""


@dataclass(frozen=True, slots=True)
class Transaction:
    """One statement line. ``amount`` and ``units`` keep the statement's signs."""

    folio: str
    amc: str
    scheme: str
    isin: str | None
    amfi_code: str | None
    day: date
    kind: str
    description: str
    amount: Decimal | None
    units: Decimal | None
    nav: Decimal | None
    balance: Decimal | None


@dataclass(frozen=True, slots=True)
class Closing:
    """A scheme's closing balance and valuation, as the statement filed them."""

    folio: str
    scheme: str
    isin: str | None
    amfi_code: str | None
    units: Decimal
    value: Decimal | None
    nav: Decimal | None
    valued_on: date | None
    cost: Decimal | None


@dataclass(frozen=True, slots=True)
class Statement:
    """A parsed CAS: period, kind, transactions, closing balances and parser warnings."""

    file_sha256: str
    period_from: date | None
    period_to: date | None
    cas_type: str
    transactions: Sequence[Transaction]
    closings: Sequence[Closing]
    warnings: Sequence[str]


@dataclass(frozen=True, slots=True)
class ImportRecord:
    """One committed statement: what it added and when."""

    id: UUID
    file_sha256: str
    period_from: date | None
    period_to: date | None
    cas_type: str
    added: int
    duplicates: int
    closings: Sequence[Closing]
    created_at: str


class StatementReader(Protocol):
    """Port: read a CAS file in memory."""

    def read(self, content: bytes, password: str) -> Statement:
        """Parse, or raise :class:`StatementError`."""
        ...


class Ledger(Protocol):
    """Port: the caller's imports and transactions, under row-level security."""

    async def imports(self, context: TenantContext) -> list[ImportRecord]:
        """Every committed import, newest first."""
        ...

    async def find(self, context: TenantContext, file_sha256: str) -> ImportRecord | None:
        """The import of this exact file, if committed."""
        ...

    async def commit(self, context: TenantContext, statement: Statement) -> ImportRecord:
        """Store the statement as one import; a transaction already held is skipped."""
        ...

    async def undo(self, context: TenantContext, import_id: UUID) -> bool:
        """Remove one import and the transactions it added; ``False`` when unknown."""
        ...

    async def transactions(self, context: TenantContext) -> list[Transaction]:
        """Every transaction held, in date order."""
        ...
