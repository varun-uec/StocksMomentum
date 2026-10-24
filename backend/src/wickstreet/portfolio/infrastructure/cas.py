"""CAS reader: CAMS and KFintech statements through ``casparser``, in memory only.

The file and the password stay in this process. Nothing here logs either, and the
investor's name, PAN, email and address are not copied into the statement.
"""

from __future__ import annotations

import hashlib
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import casparser  # type: ignore[import-untyped]

from wickstreet.portfolio.domain.model import Closing, Statement, StatementError, Transaction

_DAY_FORMATS = ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y")


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    for fmt in _DAY_FORMATS:
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def statement_of(data: dict[str, Any], file_sha256: str) -> Statement:
    """A statement from casparser's dict output (what ``read_cas_pdf`` gives)."""
    transactions, closings = [], []
    for folio in data.get("folios", []):
        number, amc = str(folio.get("folio", "")), str(folio.get("amc", ""))
        for s in folio.get("schemes", []):
            isin, code = s.get("isin") or None, s.get("amfi") or None
            name = str(s.get("scheme", ""))
            for t in s.get("transactions", []):
                day = _day(t.get("date"))
                if day is None:
                    continue
                kind = t.get("type")
                transactions.append(
                    Transaction(
                        number,
                        amc,
                        name,
                        isin,
                        code,
                        day,
                        str(getattr(kind, "name", kind) or "UNKNOWN"),
                        str(t.get("description", "")),
                        _dec(t.get("amount")),
                        _dec(t.get("units")),
                        _dec(t.get("nav")),
                        _dec(t.get("balance")),
                    )
                )
            valuation = s.get("valuation") or {}
            closings.append(
                Closing(
                    number,
                    name,
                    isin,
                    code,
                    _dec(s.get("close")) or Decimal(0),
                    _dec(valuation.get("value")),
                    _dec(valuation.get("nav")),
                    _day(valuation.get("date")),
                    _dec(valuation.get("cost")),
                )
            )
    period = data.get("statement_period") or {}
    kind = data.get("cas_type")
    return Statement(
        file_sha256,
        _day(period.get("from")),
        _day(period.get("to")),
        str(getattr(kind, "name", kind) or "UNKNOWN"),
        transactions,
        closings,
        [str(w) for w in data.get("parse_warnings", []) or []],
    )


class CasparserReader:
    """The ``StatementReader`` port over casparser."""

    def read(self, content: bytes, password: str) -> Statement:
        """Parse a CAS PDF held in memory."""
        try:
            data = casparser.read_cas_pdf(io.BytesIO(content), password)
        except Exception as exc:  # casparser raises its own and pdf errors
            raise StatementError(
                f"Could not read the statement ({type(exc).__name__}). Check the file and password."
            ) from None
        if not isinstance(data, dict) or "folios" not in data:
            raise StatementError("This is not a CAMS or KFintech mutual-fund statement.")
        return statement_of(data, hashlib.sha256(content).hexdigest())
