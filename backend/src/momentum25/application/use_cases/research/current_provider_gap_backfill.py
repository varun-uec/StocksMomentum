"""CurrentProviderGapBackfill — RP-012 Phase 2, current-provider survivorship gap.

Fills the ``ohlcv_daily`` (current-provider) gap for securities that are present
in the ``legacy_ohlcv_daily`` staging table within the overlap window but wholly
absent from ``ohlcv_daily`` for that window. The root cause (investigated
separately) is that production's historical ingestion (`market_sync`) is
*symbol-keyed off the currently-active universe*: a security whose ticker drifted
between the session date and now (a rename collapsed in-place in the master) had
its in-window history fetched under its *current* symbol, under which the current
provider serves nothing for that era — so the bars were never captured.

The current provider's *daily full-market snapshot* (``sec_bhavdata_full``), by
contrast, is date-keyed and still serves every symbol that actually traded on a
date — including the security's *old* ticker. This use case therefore iterates
the window by date and, for each date, resolves each target security's
period-correct old ticker from the legacy archive's ISIN column (ISIN is stable
across a rename; used purely as a lookup key, never as price data) and writes the
current provider's own print for that ticker into ``ohlcv_daily``.

Provenance stays clean: every price written originates from the current provider,
so the Gate 4a legacy-vs-current reconciliation remains a genuine independent
cross-check rather than a tautology. A target/date the current provider does not
serve is recorded as a hard, disclosed limitation — never fabricated or
back-filled from legacy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.research.symbol_resolution import normalize_isin

_logger = get_logger("current_provider_gap_backfill")


@dataclass(slots=True)
class GapBackfillSummary:
    """Outcome of a current-provider gap backfill run."""

    start: date
    end: date
    target_securities: int = 0
    trading_days: int = 0
    empty_days: int = 0
    rows_written: int = 0
    securities_written: set[int] = field(default_factory=set)
    missing_from_current: int = 0
    missing_examples: list[str] = field(default_factory=list)
    already_present_skipped: int = 0

    def to_report(self) -> dict[str, object]:
        """Return a serializable summary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "target_securities": self.target_securities,
            "trading_days": self.trading_days,
            "empty_days": self.empty_days,
            "rows_written": self.rows_written,
            "securities_written": len(self.securities_written),
            "missing_from_current": self.missing_from_current,
            "missing_examples": self.missing_examples[:50],
            "already_present_skipped": self.already_present_skipped,
        }


class CurrentProviderGapBackfill:
    """Backfills ``ohlcv_daily`` for the current-provider survivorship gap."""

    _MISS_CAP = 50

    def __init__(self, provider: Any, ohlcv_repo: Any) -> None:
        """Wire the use case with the market-data provider and OHLCV repository."""
        self._provider = provider
        self._ohlcv_repo = ohlcv_repo

    async def execute(
        self,
        targets: dict[int, str],
        start: date,
        end: date,
        skip_existing: dict[int, set[date]] | None = None,
    ) -> GapBackfillSummary:
        """Backfill ``targets`` (``security_id -> ISIN``) over ``[start, end]``.

        Iterates ascending by calendar date. For each trading date, the target
        tickers are resolved from the legacy archive's ISIN column and the
        current provider's own print for each ticker is written to
        ``ohlcv_daily``. Per-day commits make a re-run resumable and idempotent
        (``ON CONFLICT`` upserts skip already-written rows).

        ``skip_existing`` maps ``security_id -> {dates already present in
        ohlcv_daily}``. Those (security, date) pairs are left untouched so that a
        partial-gap security's existing production rows — including their derived
        ``adj_close``/``adj_factor`` — are never overwritten. Only genuinely
        missing bars are filled. When ``None`` (the original whole-absent cohort,
        which by definition has no in-window rows) every legacy date is written.
        """
        isin_to_id = {
            normalized: sid
            for sid, isin in targets.items()
            if (normalized := normalize_isin(isin)) is not None
        }
        present = skip_existing or {}
        summary = GapBackfillSummary(start=start, end=end, target_securities=len(targets))

        current = start
        while current <= end:
            legacy_bars = await self._provider.fetch_eod_from_legacy_archive(current)
            if not legacy_bars:
                summary.empty_days += 1
                current += timedelta(days=1)
                continue

            symbol_for_target: dict[int, str] = {}
            for lb in legacy_bars:
                iid = normalize_isin(lb.isin)
                if iid is not None and iid in isin_to_id:
                    symbol_for_target[isin_to_id[iid]] = lb.symbol

            if not symbol_for_target:
                summary.empty_days += 1
                current += timedelta(days=1)
                continue

            summary.trading_days += 1
            await self._persist_day(current, symbol_for_target, present, summary)
            await self._commit()
            current += timedelta(days=1)

        _logger.info("current_provider_gap_backfill_completed", **summary.to_report())
        return summary

    async def _persist_day(
        self,
        day: date,
        symbol_for_target: dict[int, str],
        present: dict[int, set[date]],
        summary: GapBackfillSummary,
    ) -> None:
        """Write the current-provider print for each target trading on ``day``.

        Targets whose ``day`` is already present in ``ohlcv_daily`` (per
        ``present``) are skipped so existing production rows are never rewritten.
        """
        pending = {
            sid: sym for sid, sym in symbol_for_target.items() if day not in present.get(sid, ())
        }
        summary.already_present_skipped += len(symbol_for_target) - len(pending)
        if not pending:
            return
        current_bars = await self._provider.fetch_eod_full(day)
        by_symbol = {b.symbol: b for b in current_bars}
        for security_id, symbol in pending.items():
            cb = by_symbol.get(symbol)
            if cb is None:
                summary.missing_from_current += 1
                if len(summary.missing_examples) < self._MISS_CAP:
                    summary.missing_examples.append(f"{day.isoformat()}:{symbol}#{security_id}")
                continue
            bar = OHLCVBar(
                date=cb.date,
                open=cb.open,
                high=cb.high,
                low=cb.low,
                close=cb.close,
                volume=cb.volume,
                prev_close=cb.prev_close,
                turnover_value=cb.turnover_value,
            )
            summary.rows_written += await self._ohlcv_repo.upsert_bars(security_id, [bar])
            summary.securities_written.add(security_id)

    async def _commit(self) -> None:
        """Commit the current unit of work (bounded per-day write set)."""
        session = getattr(self._ohlcv_repo, "_session", None)
        if session is not None:
            await session.commit()
