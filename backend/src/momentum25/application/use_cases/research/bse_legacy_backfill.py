"""BseLegacyBackfill — bulk backfill of BSE's pre-UDiFF archive (RP-014).

Backfills BSE-sourced OHLCV for 2006-03-01 → 2023-12-29 (the legacy EQ_CSV
era, measured in RP-014) into the dedicated ``bse_legacy_ohlcv_daily`` staging
table (never the live ``ohlcv_daily``, never the NSE-anchored
``legacy_ohlcv_daily`` the historical screening reads).

Identity is the one thing that differs from the NSE legacy backfill, and it is
deliberately strict:

* A BSE legacy row carries no ISIN — its identity is the exchange-stable
  numeric ``SC_CODE`` (``native_code`` on :class:`RawBar`) plus the padded
  ``SC_NAME``.
* The use case first *learns* each ``SC_CODE``'s ISIN from a fixed set of
  modern UDiFF-era sessions (the same provider, same parser, verified format)
  and persists that junction insert-only into ``bse_scrip_junction``.
* Bars resolve through junction → ISIN → canonical ``securities`` only.
  There is **no** name-based cross-exchange fallback: the platform's
  cross-listing rule (``domain.research.cross_listing``) rejects non-ISIN
  joins because tickers are exchange-local, and this backfill keeps that
  discipline. A scrip never seen in a UDiFF session (delisted before 2024,
  or BSE-only and unadmitted) is counted and its name disclosed, never
  guessed.

Venue-level C1/C2 gap logging is deliberately not replicated here: the NSE
surface already logs corporate-action inference and survivorship events for
the same companies, and BSE's own session gaps have no consumer. Bars are raw
prints only, exactly like ``legacy_ohlcv_daily``.

Iteration is ascending by calendar date (deterministic, ADR-009); per-day
``ON CONFLICT`` upserts make the run idempotent and resumable, and the
junction's first-observation-wins semantics make re-runs stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.ports.market_data import RawBar
from momentum25.domain.research.symbol_resolution import normalize_isin
from momentum25.infrastructure.providers.bse_bhavcopy import (
    BSE_LEGACY_START,
    UDIFF_START,
)

_logger = get_logger("bse_legacy_backfill")

# The UDiFF-era sessions the SC_CODE → ISIN junction is learned from. Fixed
# constants so the learning set is reproducible run to run; a non-session in
# the list simply contributes no rows (the session is skipped, never error).
JUNCTION_SESSIONS: tuple[date, ...] = (
    date(2024, 1, 2),
    date(2024, 7, 1),
    date(2025, 1, 2),
    date(2025, 7, 1),
    date(2026, 1, 2),
    date(2026, 7, 6),
)


@dataclass(slots=True)
class BseBackfillSummary:
    """Outcome of a BSE legacy backfill run."""

    start: date
    end: date
    junction_rows: int = 0
    junction_mapped_to_canonical: int = 0
    trading_days: int = 0
    empty_days: int = 0
    rows_written: int = 0
    isin_resolved: int = 0
    unresolved: int = 0
    first_trading_day: date | None = None
    last_trading_day: date | None = None
    unknown_scrips: set[str] = field(default_factory=set)

    def to_report(self) -> dict[str, object]:
        """Return a serializable summary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "junction_rows": self.junction_rows,
            "junction_mapped_to_canonical": self.junction_mapped_to_canonical,
            "trading_days": self.trading_days,
            "empty_days": self.empty_days,
            "rows_written": self.rows_written,
            "isin_resolved": self.isin_resolved,
            "unresolved": self.unresolved,
            "distinct_unresolved_scrips": len(self.unknown_scrips),
            "first_trading_day": self.first_trading_day.isoformat()
            if self.first_trading_day
            else None,
            "last_trading_day": self.last_trading_day.isoformat()
            if self.last_trading_day
            else None,
        }


class BseLegacyBackfill:
    """Backfills the BSE pre-UDiFF archive into ``bse_legacy_ohlcv_daily``."""

    def __init__(
        self,
        provider: Any,
        security_repo: Any,
        bse_repo: Any,
        junction_repo: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._provider = provider
        self._security_repo = security_repo
        self._bse_repo = bse_repo
        self._junction_repo = junction_repo

    async def execute(
        self,
        start: date = BSE_LEGACY_START,
        end: date = UDIFF_START - timedelta(days=1),
    ) -> BseBackfillSummary:
        """Backfill ``[start, end]``; guard the bounds against misuse."""
        if start < BSE_LEGACY_START:
            msg = (
                f"backfill start {start.isoformat()} precedes the BSE archive "
                f"inception {BSE_LEGACY_START.isoformat()}."
            )
            raise ValueError(msg)
        if end >= UDIFF_START:
            msg = (
                f"backfill end {end.isoformat()} must precede the UDiFF era "
                f"({UDIFF_START.isoformat()}); post-cutover sessions use the "
                "live UDiFF source."
            )
            raise ValueError(msg)

        summary = BseBackfillSummary(start=start, end=end)

        junction = await self._learn_junction(summary)
        isin_to_id = self._unambiguous_isin_index(await self._security_repo.list_all())
        summary.junction_mapped_to_canonical = sum(
            1 for isin in junction.values() if isin in isin_to_id
        )

        current = start
        while current <= end:
            bars = await self._provider.fetch_eod(current)
            if not bars:
                summary.empty_days += 1
                current += timedelta(days=1)
                continue

            summary.trading_days += 1
            if summary.first_trading_day is None:
                summary.first_trading_day = current
            summary.last_trading_day = current

            items: list[tuple[int, OHLCVBar]] = []
            for raw in bars:
                resolution = self._resolve_bar(raw, junction, isin_to_id)
                if resolution is None:
                    summary.unresolved += 1
                    summary.unknown_scrips.add(raw.symbol)
                    continue
                summary.isin_resolved += 1
                items.append(
                    (
                        resolution,
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
            summary.rows_written += await self._bse_repo.upsert_day(items)
            await self._commit()
            current += timedelta(days=1)

        _logger.info("bse_legacy_backfill_completed", **summary.to_report())
        return summary

    async def _learn_junction(self, summary: BseBackfillSummary) -> dict[str, str]:
        """Learn and persist the SC_CODE → ISIN junction from UDiFF sessions.

        Persisted rows are insert-only (first observation wins), so a re-run
        never overwrites an earlier session's disclosure. Returns the full
        accumulated junction including rows learned in prior runs.
        """
        for session in JUNCTION_SESSIONS:
            master = await self._provider.fetch_instrument_master(session)
            if not master:
                _logger.warning(
                    "junction_session_empty", session=session.isoformat()
                )
                continue
            items = [
                (str(inst.native_code), str(inst.isin), str(inst.name), session)
                for inst in master
                if inst.native_code and inst.isin
            ]
            summary.junction_rows += await self._junction_repo.insert_many(items)
        junction = await self._junction_repo.sc_code_to_isin()
        return dict(junction)

    @staticmethod
    def _unambiguous_isin_index(securities: list[Any]) -> dict[str, int]:
        """Build ``ISIN -> security_id`` for ISINs held by exactly one security.

        Mirrors the NSE legacy backfill's index: ISINs shared by ≥2 securities
        (rename chains across ghost rows) are excluded so a flat ISIN join can
        never collapse distinct identities onto one id.
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
        raw: RawBar, junction: dict[str, str], isin_to_id: dict[str, int]
    ) -> int | None:
        """Resolve one BSE legacy bar to a ``security_id`` via the ISIN junction.

        Strictly single-path: ``SC_CODE → junction → ISIN → securities``. There
        is no symbol fallback (see module docstring) — an unscoped name is
        reported, never assumed.
        """
        if not raw.native_code:
            return None
        isin = junction.get(str(raw.native_code))
        if isin is None:
            return None
        normalized = normalize_isin(isin)
        if normalized is None:
            return None
        return isin_to_id.get(normalized)

    async def _commit(self) -> None:
        """Commit the current unit of work, so a long backfill isn't one txn."""
        session = getattr(self._bse_repo, "_session", None)
        if session is not None:
            await session.commit()