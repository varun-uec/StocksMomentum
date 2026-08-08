"""ReconcileInstrumentMaster — deactivate securities no longer on the exchange.

Deliberately not part of the daily ``ExecuteScreening`` pipeline (same reasoning
as ``RefreshCorporateActions``): the instrument master doesn't need reconciling
on every run, only periodically. Intended to be invoked on its own schedule
(e.g. weekly/monthly).

Discovered 2026-07-02: ``upsert_many`` only ever inserts or updates symbols
present in a fresh instrument-master fetch -- a symbol that's been delisted,
merged, or renamed (and so no longer appears in the fetch) is never touched,
so its ``is_active`` flag silently stays ``True`` forever. Verified against a
live fetch: at least 357 securities marked active in this platform's database
(e.g. GMRINFRA, IDFC, HBLPOWER, IIFLSEC, TV18BRDCST) are absent from NSE's
current instrument master -- real corporate actions (IDFC's 2024 merger into
IDFC First Bank is a documented example), not a data gap. Leaving them active
doesn't corrupt screening results (the stale-OHLCV-data exclusion already
built this session keeps them out of scoring), but it does mean every run
still iterates and attempts to evaluate several hundred securities that can
never contribute a result.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

_logger = get_logger("reconcile_instrument_master")


class ReconcileInstrumentMaster:
    """Deactivates active securities that are no longer in the current instrument master."""

    def __init__(
        self,
        market_data_provider: Any,
        security_repo: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._market_data_provider = market_data_provider
        self._security_repo = security_repo

    async def execute(self) -> dict[str, int]:
        """Deactivate active securities absent from the current instrument master.

        Returns a summary: ``{"active_before": N, "current_master_size": M,
        "deactivated": K}``.
        """
        current_master = await self._market_data_provider.fetch_instrument_master()
        current_symbols = {instrument.symbol for instrument in current_master}

        active_securities = await self._security_repo.list_active()
        stale_symbols = [
            str(s.symbol) for s in active_securities if str(s.symbol) not in current_symbols
        ]

        deactivated = await self._security_repo.deactivate_symbols(stale_symbols)
        await self._commit()

        summary = {
            "active_before": len(active_securities),
            "current_master_size": len(current_symbols),
            "deactivated": deactivated,
        }
        _logger.info("instrument_master_reconciliation_completed", **summary)
        return summary

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._security_repo, "_session", None)
        if session is not None:
            await session.commit()
