"""LegacyOverlapBackfill — bulk backfill of the RP-012 overlap window (Phase 2 §1).

Backfills legacy-archive OHLCV for 2019-09-30 → ~2024-07-05 into the dedicated
``legacy_ohlcv_daily`` staging table (never the live ``ohlcv_daily``), while
exercising the two validation-gap logging mechanisms inline:

* **C1** — a PREVCLOSE-inferred corporate-action factor per session; only
  *flagged* (out-of-band) inferences are persisted, so the audit log is bounded
  and meaningful rather than one row per (security, session).
* **C2** — survivorship/gap events when a security disappears from the daily EQ
  set for more than the gap threshold and later reappears.

Iteration is ascending by calendar date; the legacy adapter returns an empty
list for non-trading days (archive 404) and those days are skipped. Running-state
(last-seen session index, last close) is kept in memory and is a deterministic
function of the ascending date order — no hidden randomness (ADR-009).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.ports.market_data import RawBar
from momentum25.domain.research.period_correct_resolution import (
    PeriodResolutionOutcome,
    SymbolInterval,
    resolve_period_correct,
)
from momentum25.domain.research.symbol_resolution import (
    Resolution,
    ResolutionPath,
    normalize_isin,
    resolve_security,
)
from momentum25.domain.research.validation_gaps import (
    InferredActionEvent,
    SurvivorshipGapEvent,
    detect_gap_event,
    infer_action_event,
)

_logger = get_logger("legacy_overlap_backfill")

# RP-012 Phase 2 overlap window (authoritative, measured in Phase 1 D4).
OVERLAP_START: date = date(2019, 9, 30)
OVERLAP_END: date = date(2024, 7, 5)
# NSE equities-archive inception — the earliest legacy bhavcopy (RP-012 D1).
# Used as the lower floor for the authorized Phase 3 pre-overlap backfill.
LEGACY_INCEPTION: date = date(1994, 11, 3)


@dataclass(slots=True)
class _SecurityState:
    """Per-security running state carried across ascending trading sessions."""

    last_session_index: int
    last_seen_date: date
    last_close: Any  # Decimal


@dataclass(slots=True)
class BackfillSummary:
    """Outcome of a backfill run over the window."""

    start: date
    end: date
    trading_days: int = 0
    empty_days: int = 0
    rows_written: int = 0
    unknown_symbols_skipped: int = 0
    isin_resolved: int = 0
    symbol_fallback_resolved: int = 0
    period_correct_resolved: int = 0
    unresolved: int = 0
    flagged_inferences: int = 0
    gap_events: int = 0
    first_trading_day: date | None = None
    last_trading_day: date | None = None
    unknown_symbols: set[str] = field(default_factory=set)

    def to_report(self) -> dict[str, object]:
        """Return a serializable summary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "trading_days": self.trading_days,
            "empty_days": self.empty_days,
            "rows_written": self.rows_written,
            "unknown_symbols_skipped": self.unknown_symbols_skipped,
            "distinct_unknown_symbols": len(self.unknown_symbols),
            "isin_resolved": self.isin_resolved,
            "symbol_fallback_resolved": self.symbol_fallback_resolved,
            "period_correct_resolved": self.period_correct_resolved,
            "unresolved": self.unresolved,
            "flagged_inferences": self.flagged_inferences,
            "gap_events": self.gap_events,
            "first_trading_day": self.first_trading_day.isoformat()
            if self.first_trading_day
            else None,
            "last_trading_day": self.last_trading_day.isoformat()
            if self.last_trading_day
            else None,
        }


class LegacyOverlapBackfill:
    """Backfills the legacy overlap window and logs C1/C2 validation gaps."""

    def __init__(
        self,
        provider: Any,
        security_repo: Any,
        legacy_repo: Any,
        gap_log_repo: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._provider = provider
        self._security_repo = security_repo
        self._legacy_repo = legacy_repo
        self._gap_log_repo = gap_log_repo

    async def execute(
        self,
        start: date = OVERLAP_START,
        end: date = OVERLAP_END,
        floor: date = OVERLAP_START,
    ) -> BackfillSummary:
        """Backfill ``[start, end]`` from the legacy archive; return a summary.

        ``floor`` is the lowest permissible ``start`` for the run. It defaults to
        ``OVERLAP_START`` so the Phase 2 caller keeps its guard against an
        accidental pre-cutover run; the authorized Phase 3 pre-overlap backfill
        passes ``floor=LEGACY_INCEPTION`` explicitly. The resolution / logging
        pipeline itself is identical for either range.
        """
        if start < floor:
            msg = (
                f"backfill start {start.isoformat()} precedes the permitted floor "
                f"{floor.isoformat()}."
            )
            raise ValueError(msg)

        # Build resolution maps from the FULL master (active + inactive), not
        # just active securities: historical/ghost rows (delisted, renamed-away,
        # merged) must remain resolvable so their bars attach to their own
        # security_id instead of collapsing onto an active successor.
        securities = await self._security_repo.list_all()
        symbol_to_id = {str(s.symbol): s.id for s in securities if s.id is not None}
        # ISIN-first resolution index, restricted to *unambiguous* ISINs (exactly
        # one security). ISINs shared by ≥2 securities are rename chains and are
        # deliberately excluded here — a flat ISIN join would collapse every
        # chain member onto one id. Those are resolved by period-correct interval
        # containment (below) instead, keeping resolution deterministic.
        isin_to_id = self._unambiguous_isin_index(securities)
        # symbol -> dated trading intervals for every ISIN-shared rename chain.
        intervals_by_symbol = await self._security_repo.rename_chain_intervals()
        summary = BackfillSummary(start=start, end=end)
        state: dict[int, _SecurityState] = {}
        session_index = 0

        current = start
        while current <= end:
            bars = await self._provider.fetch_eod_from_legacy_archive(current)
            if not bars:
                summary.empty_days += 1
                current += timedelta(days=1)
                continue

            summary.trading_days += 1
            if summary.first_trading_day is None:
                summary.first_trading_day = current
            summary.last_trading_day = current
            session_index += 1

            await self._persist_day(
                current,
                bars,
                symbol_to_id,
                isin_to_id,
                intervals_by_symbol,
                state,
                session_index,
                summary,
            )
            await self._commit()
            current += timedelta(days=1)

        _logger.info("legacy_overlap_backfill_completed", **summary.to_report())
        return summary

    @staticmethod
    def _unambiguous_isin_index(securities: list[Any]) -> dict[str, int]:
        """Build ``ISIN -> security_id`` for ISINs held by exactly one security.

        Ambiguous ISINs (rename chains) are excluded so ISIN-first resolution
        never silently collapses chain members onto a single id.
        """
        by_isin: dict[str, list[int]] = {}
        for s in securities:
            if s.id is None:
                continue
            normalized = normalize_isin(s.isin)
            if normalized is not None:
                by_isin.setdefault(normalized, []).append(s.id)
        return {isin: ids[0] for isin, ids in by_isin.items() if len(ids) == 1}

    @staticmethod
    def _resolve_bar(
        raw: RawBar,
        symbol_to_id: dict[str, int],
        isin_to_id: dict[str, int],
        intervals_by_symbol: dict[str, list[SymbolInterval]],
    ) -> Resolution:
        """Resolve one legacy bar, period-correct for rename-chain tickers.

        A bar whose (period-correct) ticker belongs to a rename chain is resolved
        by interval containment on its session date — attributing e.g. a 2020
        ADANIGAS print to the historical ADANIGAS security, not its ATGL
        successor. All other bars use the unchanged ISIN-first / symbol-fallback
        path. An unresolved period-correct outcome (overlap/unknown) falls through
        to that path rather than guessing.
        """
        if raw.symbol.upper() in intervals_by_symbol:
            period = resolve_period_correct(
                raw.symbol.upper(), raw.date, intervals_by_symbol
            )
            if period.security_id is not None and period.outcome in (
                PeriodResolutionOutcome.CONTAINED,
                PeriodResolutionOutcome.BOUNDARY_GAP,
            ):
                return Resolution(period.security_id, ResolutionPath.PERIOD_CORRECT)
        return resolve_security(raw.symbol, raw.isin, symbol_to_id, isin_to_id)

    async def _commit(self) -> None:
        """Commit the current unit of work, so a long backfill isn't one txn.

        Per-day commits keep the write set bounded and make a re-run resumable
        (the idempotent ``ON CONFLICT`` upserts skip already-written days).
        """
        session = getattr(self._legacy_repo, "_session", None)
        if session is not None:
            await session.commit()

    async def _persist_day(
        self,
        day: date,
        bars: list[RawBar],
        symbol_to_id: dict[str, int],
        isin_to_id: dict[str, int],
        intervals_by_symbol: dict[str, list[SymbolInterval]],
        state: dict[int, _SecurityState],
        session_index: int,
        summary: BackfillSummary,
    ) -> None:
        """Persist one trading day's bars in bulk and log any C1/C2 events.

        All writes for the day are batched into three statements (bars, flagged
        C1 inferences, C2 gaps) rather than one statement per symbol — the hot
        path for the ~1,200-day overlap backfill.
        """
        day_bars: list[tuple[int, OHLCVBar]] = []
        c1_events: list[tuple[int, InferredActionEvent]] = []
        c2_events: list[tuple[int, SurvivorshipGapEvent]] = []

        for raw in bars:
            resolution = self._resolve_bar(
                raw, symbol_to_id, isin_to_id, intervals_by_symbol
            )
            security_id = resolution.security_id
            if security_id is None:
                # Neither ISIN nor symbol resolved to a master security — likely a
                # security absent from the current master with no usable ISIN. No
                # FK target exists, so the row is skipped and disclosed rather than
                # guessing an identity (a known Phase 2 limitation; the C2 gap
                # mechanism still surfaces such securities in Phase 3 once the
                # master is backfilled).
                summary.unresolved += 1
                summary.unknown_symbols_skipped += 1
                summary.unknown_symbols.add(raw.symbol)
                continue
            if resolution.path is ResolutionPath.PERIOD_CORRECT:
                summary.period_correct_resolved += 1
            elif resolution.path is ResolutionPath.ISIN:
                summary.isin_resolved += 1
            elif resolution.path is ResolutionPath.SYMBOL_FALLBACK:
                summary.symbol_fallback_resolved += 1

            day_bars.append(
                (
                    security_id,
                    OHLCVBar(
                        date=raw.date,
                        open=raw.open,
                        high=raw.high,
                        low=raw.low,
                        close=raw.close,
                        volume=raw.volume,
                        prev_close=raw.prev_close,
                        turnover_value=raw.turnover_value,
                    ),
                )
            )

            prior = state.get(security_id)
            if prior is not None:
                c1 = infer_action_event(
                    symbol=raw.symbol,
                    session_date=day,
                    prev_close_reported=raw.prev_close,
                    prior_session_close=prior.last_close,
                )
                if c1 is not None and c1.flagged:
                    c1_events.append((security_id, c1))
                c2 = detect_gap_event(
                    symbol=str(security_id),
                    last_seen_date=prior.last_seen_date,
                    current_date=day,
                    gap_sessions=session_index - prior.last_session_index - 1,
                )
                if c2 is not None:
                    c2_events.append((security_id, c2))

            state[security_id] = _SecurityState(
                last_session_index=session_index,
                last_seen_date=day,
                last_close=raw.close,
            )

        summary.rows_written += await self._legacy_repo.upsert_day(day_bars)
        summary.flagged_inferences += await self._gap_log_repo.log_inferred_actions_bulk(
            c1_events
        )
        summary.gap_events += await self._gap_log_repo.log_gap_events_bulk(c2_events)
