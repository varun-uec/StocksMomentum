"""RefreshCorporateActions — periodic maintenance use case (Objective 1, Phase 1).

Deliberately not part of the daily ``ExecuteScreening`` pipeline -- see
``application.services.corporate_actions`` for why bulk-refreshing every
symbol on every run is the wrong trigger. Intended to be invoked on its own
schedule (e.g. weekly) independent of the daily screening run.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.application.services.corporate_actions import refresh_adjustment_factors

_logger = get_logger("refresh_corporate_actions")


class RefreshCorporateActions:
    """Refreshes corporate-action-adjusted prices for the active universe."""

    def __init__(
        self,
        market_data_provider: Any,
        security_repo: Any,
        corporate_action_repo: Any,
        ohlcv_repo: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._market_data_provider = market_data_provider
        self._security_repo = security_repo
        self._corporate_action_repo = corporate_action_repo
        self._ohlcv_repo = ohlcv_repo

    async def execute(self, as_of: date | None = None) -> dict[str, Any]:
        """Refresh adjustment factors for every active security.

        Returns a summary of securities processed, bars updated, and errors.
        """
        reference_date = as_of or date.today()
        securities = await self._security_repo.list_active()

        processed = 0
        bars_updated = 0
        errors = 0
        first_error: str | None = None
        for security in securities:
            if security.id is None:
                continue
            try:
                updated = await refresh_adjustment_factors(
                    market_data_provider=self._market_data_provider,
                    corporate_action_repo=self._corporate_action_repo,
                    ohlcv_repo=self._ohlcv_repo,
                    symbol=str(security.symbol),
                    security_id=security.id,
                    as_of=reference_date,
                )
                # Commit per security, not once at the end.
                #
                # A single unit of work spanning the whole universe was a data
                # loss bug, not just a scale concern: one symbol's DB error
                # aborts the Postgres transaction, every later statement then
                # fails with PendingRollbackError, each is swallowed by the
                # `except` below, and the trailing commit lands on a fresh
                # empty transaction. The endpoint returned
                # `{"securities_processed": 160, "bars_updated": 31093}` while
                # writing zero rows (observed 2026-08-09). Per-security commits
                # bound the blast radius to the failing symbol, keep completed
                # work durable, and make the operation resumable.
                await self._commit()
                bars_updated += updated
                processed += 1
            except Exception as exc:
                await self._rollback()
                errors += 1
                if first_error is None:
                    first_error = f"{type(exc).__name__}: {exc}"
                _logger.warning(
                    "corporate_action_refresh_failed",
                    symbol=str(security.symbol),
                    error=str(exc),
                )

        summary: dict[str, Any] = {
            "securities_processed": processed,
            "bars_updated": bars_updated,
            "errors": errors,
        }
        # A swallowed error must remain visible to the operator; the previous
        # summary reported only a count, so a total failure looked like a
        # partial success.
        if first_error is not None:
            summary["first_error"] = first_error
        _logger.info("corporate_actions_refresh_completed", **summary)
        return summary

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._ohlcv_repo, "_session", None)
        if session is not None:
            await session.commit()

    async def _rollback(self) -> None:
        """Discard the failed security's partial work so the session stays usable."""
        session = getattr(self._ohlcv_repo, "_session", None)
        if session is not None:
            await session.rollback()
