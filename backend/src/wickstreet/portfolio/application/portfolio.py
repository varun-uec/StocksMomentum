"""Preview, import, undo and analyse the caller's CAS statements (Slice 6).

A preview parses and reports; it stores nothing. An import stores the statement as
one batch; the same file twice is the same import. Undo removes the batch. The
analysis values the ledger with the research snapshot's latest NAVs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from wickstreet.context import TenantContext
from wickstreet.mf_data.domain.reads import Portfolio
from wickstreet.portfolio.domain.analytics import (
    FundView,
    fund_overlaps,
    look_through,
    positions,
    rebalance,
    summary,
)
from wickstreet.portfolio.domain.model import (
    Closing,
    ImportRecord,
    Ledger,
    StatementReader,
    UnknownImportError,
)


class FundData(Protocol):
    """Port: what research knows about held funds."""

    async def funds(
        self, codes: Sequence[str]
    ) -> tuple[date, dict[str, FundView], Mapping[str, Sequence[tuple[date, str]]]]:
        """The data date, each known code's view, and market-cap classes."""
        ...

    async def alternatives(self, code: str) -> list[dict[str, Any]]:
        """Higher-scored direct growth funds in the same category."""
        ...


def _latest_closings(imports: Sequence[ImportRecord]) -> list[Closing]:
    """Each scheme's closing balance from the newest statement that lists it."""
    seen: dict[tuple[str, str], Closing] = {}
    for record in sorted(imports, key=lambda r: (r.period_to or date.min, r.created_at)):
        for c in record.closings:
            seen[(c.folio, c.amfi_code or c.isin or c.scheme)] = c
    return list(seen.values())


def _import_json(record: ImportRecord) -> dict[str, Any]:
    out = asdict(record)
    out["id"] = str(record.id)
    out["closings"] = len(record.closings)
    for key in ("period_from", "period_to"):
        out[key] = out[key].isoformat() if out[key] else None
    return out


class PortfolioService:
    """The portfolio use cases over a ledger, a statement reader and research data."""

    def __init__(self, ledger: Ledger, reader: StatementReader, funds: FundData) -> None:
        """Create the use cases."""
        self._ledger = ledger
        self._reader = reader
        self._funds = funds

    async def preview(
        self, context: TenantContext, content: bytes, password: str
    ) -> dict[str, Any]:
        """What an import would add; nothing is stored."""
        statement = self._reader.read(content, password)
        codes = [c.amfi_code for c in statement.closings if c.amfi_code]
        _, known, _ = await self._funds.funds(codes)
        existing = await self._ledger.find(context, statement.file_sha256)
        return {
            "file_sha256": statement.file_sha256,
            "already_imported": existing is not None,
            "period_from": statement.period_from.isoformat() if statement.period_from else None,
            "period_to": statement.period_to.isoformat() if statement.period_to else None,
            "cas_type": statement.cas_type,
            "transactions": len(statement.transactions),
            "schemes": [
                {
                    "scheme": c.scheme,
                    "folio": c.folio,
                    "isin": c.isin,
                    "amfi_code": c.amfi_code,
                    "known": (c.amfi_code or "") in known,
                    "closing_units": str(c.units),
                    "statement_value": str(c.value) if c.value is not None else None,
                }
                for c in statement.closings
            ],
            "warnings": list(statement.warnings),
        }

    async def commit(self, context: TenantContext, content: bytes, password: str) -> dict[str, Any]:
        """Store the statement as one import, or return the import of the same file."""
        statement = self._reader.read(content, password)
        existing = await self._ledger.find(context, statement.file_sha256)
        record = existing or await self._ledger.commit(context, statement)
        return {**_import_json(record), "new": existing is None}

    async def undo(self, context: TenantContext, import_id: UUID) -> None:
        """Remove one import and the transactions it added."""
        if not await self._ledger.undo(context, import_id):
            raise UnknownImportError

    async def view(
        self, context: TenantContext, target: Mapping[str, float] | None = None
    ) -> dict[str, Any]:
        """Value, return, allocation, costs, look-through, overlap and alternatives."""
        imports = await self._ledger.imports(context)
        transactions = await self._ledger.transactions(context)
        closings = _latest_closings(imports)
        codes = sorted(
            {x.amfi_code for x in transactions if x.amfi_code}
            | {c.amfi_code for c in closings if c.amfi_code}
        )
        as_of, funds, caps = await self._funds.funds(codes)
        held = positions(transactions, closings, funds, as_of)
        totals = summary(held, funds, as_of)
        live = [p for p in held if p.value]
        live_funds = [funds[p.code] for p in live if p.code in funds]
        return {
            "imports": [_import_json(r) for r in imports],
            "summary": totals,
            "positions": [
                {
                    "scheme": p.scheme,
                    "folio": p.folio,
                    "code": p.code,
                    "isin": p.isin,
                    "units": str(p.units),
                    "invested": p.invested,
                    "withdrawn": p.withdrawn,
                    "value": p.value,
                    "xirr": p.xirr,
                    "reconciled": p.reconciled,
                    "fund": _fund_json(funds.get(p.code or "")),
                }
                for p in held
            ],
            "look_through": look_through(held, funds, caps),
            "overlaps": fund_overlaps(live_funds),
            "alternatives": {f.code: await self._funds.alternatives(f.code) for f in live_funds},
            "rebalance": (
                rebalance(totals["allocation"].get("asset_class", {}), totals["value"], target)
                if target
                else None
            ),
        }


def _fund_json(fund: FundView | None) -> dict[str, Any] | None:
    if fund is None:
        return None
    out = asdict(fund)
    holdings: Portfolio | None = fund.holdings
    out["holdings"] = holdings.as_of.isoformat() if holdings else None
    out["nav_date"] = fund.nav_date.isoformat() if fund.nav_date else None
    return out
