"""ReconcileCrossListings — stamp the NSE/BSE exchange dimension on securities (Phase 5.1).

Deliberately *not* part of the daily ``ExecuteScreening`` pipeline, for the same
reason as :class:`ReconcileInstrumentMaster`: cross-listing status changes on the
timescale of corporate actions, not sessions, and folding a second exchange fetch
into every run would add a network dependency to the critical path for no
analytical gain.

The use case is identity-only. It never adds a security to (or removes one from)
the screening universe unless the caller explicitly whitelists BSE groups — see
``domain.research.cross_listing`` rule 3 — so running it cannot change any
screening result. The exchange value it writes is a disclosure ("this company is
also traded on BSE"), not an input to scoring.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.domain.entities.security import Security
from momentum25.domain.research.cross_listing import reconcile_cross_listings
from momentum25.domain.value_objects.types import Symbol

_logger = get_logger("reconcile_cross_listings")


class ReconcileCrossListings:
    """Reconciles the NSE and BSE instrument masters into canonical securities."""

    def __init__(
        self,
        nse_provider: Any,
        bse_provider: Any,
        security_repo: Any,
        admit_bse_only_series: frozenset[str] = frozenset(),
    ) -> None:
        """Wire the use case with its collaborators."""
        self._nse_provider = nse_provider
        self._bse_provider = bse_provider
        self._security_repo = security_repo
        self._admit_bse_only_series = admit_bse_only_series

    async def execute(self, as_of: date | None = None) -> dict[str, Any]:
        """Reconcile both masters and persist the exchange dimension.

        Args:
            as_of: BSE session whose bhavcopy supplies the BSE master. Must be a
                trading session; a non-session yields an empty BSE master, in
                which case nothing is written (every security would otherwise be
                demoted from ``BOTH`` back to ``NSE`` by an empty fetch).

        Returns:
            A summary of the reconciliation, including the names deliberately
            withheld from the universe.
        """
        nse_master = await self._nse_provider.fetch_instrument_master()
        bse_master = await self._bse_provider.fetch_instrument_master(as_of)

        if not bse_master:
            _logger.warning(
                "cross_listing_reconciliation_skipped_empty_bse_master",
                as_of=as_of.isoformat() if as_of else None,
            )
            return {
                "skipped": True,
                "reason": "empty_bse_master",
                "nse_master_size": len(nse_master),
            }

        result = reconcile_cross_listings(
            nse_master, bse_master, admit_bse_only_series=self._admit_bse_only_series
        )

        securities = [
            Security(
                symbol=Symbol(inst.symbol),
                name=inst.name,
                isin=inst.isin,
                exchange=str(inst.exchange),
                listing_date=inst.listing_date,
                is_active=True,
            )
            for inst in result.instruments
        ]
        await self._security_repo.upsert_many(securities)
        exchanges_set = await self._security_repo.set_exchanges(
            {inst.symbol: str(inst.exchange) for inst in result.instruments}
        )
        await self._commit()

        summary: dict[str, Any] = {
            "skipped": False,
            "nse_master_size": len(nse_master),
            "bse_master_size": len(bse_master),
            "cross_listed": result.cross_listed,
            "exchanges_written": exchanges_set,
            "nse_only": result.nse_only,
            "bse_only_admitted": result.bse_only_admitted,
            "bse_only_withheld": len(result.bse_only_withheld),
            "symbol_collisions": len(result.symbol_collisions),
        }
        _logger.info("cross_listing_reconciliation_completed", **summary)
        return summary

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._security_repo, "_session", None)
        if session is not None:
            await session.commit()
