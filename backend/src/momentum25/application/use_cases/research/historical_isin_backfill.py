"""HistoricalIsinBackfill — RP-012, populate ISIN for historical/inactive rows.

The instrument master carries a cohort of ``is_active=false`` rows whose ``isin``
was never captured: these are the *old-ticker* ghosts of renamed companies
(e.g. ``ADANIGAS``, delisted 2021-01-12) whose real-world successor row (``ATGL``)
does hold the ISIN. Because the ingestion is symbol-keyed off the *currently
active* universe, the ghost's identity link was never recorded, leaving
``isin IS NULL`` and the rename chain invisible to any ISIN join.

This use case recovers each ghost's ISIN using the exact technique built for
:class:`CurrentProviderGapBackfill`: the legacy NSE archive's daily bhavcopy
carries an ``ISIN`` column, and ISIN is stable across a rename. For each target
the ISIN is read off the legacy print of the ghost's *own* ticker on a date
inside its trading interval — used purely as a lookup key, never as price data.
Probing each ghost's ``last_trade_date`` (a guaranteed real trading day for that
ticker) makes the read unambiguous: only one security traded that symbol on that
exact date, so the archive row's ISIN is the period-correct identity.

Nothing is fabricated: a target whose ticker the archive does not serve on any
of its candidate dates is reported as an undiscoverable, disclosed limitation and
its ``isin`` stays NULL. The write is fill-only (``WHERE isin IS NULL``) so an
already-known ISIN is never overwritten and a re-run is idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.domain.research.symbol_resolution import normalize_isin

_logger = get_logger("historical_isin_backfill")


@dataclass(frozen=True, slots=True)
class IsinProbeTarget:
    """A ghost security to resolve: its ticker and ordered candidate probe dates."""

    security_id: int
    symbol: str
    candidate_dates: tuple[date, ...]


@dataclass(slots=True)
class IsinBackfillSummary:
    """Outcome of a historical-ISIN backfill run."""

    targets: int = 0
    resolved: dict[int, str] = field(default_factory=dict)
    written: int = 0
    archive_fetches: int = 0
    unresolved: list[str] = field(default_factory=list)

    def to_report(self) -> dict[str, object]:
        """Return a serializable summary."""
        return {
            "targets": self.targets,
            "resolved": len(self.resolved),
            "written": self.written,
            "archive_fetches": self.archive_fetches,
            "unresolved": len(self.unresolved),
            "unresolved_examples": self.unresolved[:50],
        }


class HistoricalIsinBackfill:
    """Populates ``securities.isin`` for historical rows from the legacy archive."""

    def __init__(self, provider: Any, security_repo: Any) -> None:
        """Wire the use case with the market-data provider and security repository."""
        self._provider = provider
        self._security_repo = security_repo

    async def execute(self, targets: Sequence[IsinProbeTarget]) -> IsinBackfillSummary:
        """Resolve each target's ISIN off the legacy archive and persist it.

        Proceeds in rounds keyed by each unresolved target's *next* candidate
        date, so every distinct archive date is fetched at most once and fallback
        dates are only fetched for targets the primary probe did not resolve.
        """
        summary = IsinBackfillSummary(targets=len(targets))
        pending: dict[int, tuple[IsinProbeTarget, int]] = {
            t.security_id: (t, 0) for t in targets if t.candidate_dates
        }

        while pending:
            by_date: dict[date, list[IsinProbeTarget]] = {}
            for target, cursor in pending.values():
                by_date.setdefault(target.candidate_dates[cursor], []).append(target)

            for on_date in sorted(by_date):
                await self._resolve_on_date(on_date, by_date[on_date], summary)

            pending = self._advance(pending, summary)

        if summary.resolved:
            summary.written = await self._security_repo.backfill_isins(summary.resolved)
        _logger.info("historical_isin_backfill_completed", **summary.to_report())
        return summary

    async def _resolve_on_date(
        self, on_date: date, targets: list[IsinProbeTarget], summary: IsinBackfillSummary
    ) -> None:
        """Fetch ``on_date`` once and resolve every target whose ticker prints then."""
        legacy_bars = await self._provider.fetch_eod_from_legacy_archive(on_date)
        summary.archive_fetches += 1
        isin_by_symbol: dict[str, str] = {}
        for bar in legacy_bars:
            normalized = normalize_isin(bar.isin)
            if normalized is not None:
                isin_by_symbol.setdefault(bar.symbol.upper(), normalized)
        for target in targets:
            isin = isin_by_symbol.get(target.symbol.upper())
            if isin is not None:
                summary.resolved.setdefault(target.security_id, isin)

    def _advance(
        self,
        pending: dict[int, tuple[IsinProbeTarget, int]],
        summary: IsinBackfillSummary,
    ) -> dict[int, tuple[IsinProbeTarget, int]]:
        """Drop resolved targets; advance the rest to their next candidate date."""
        nxt: dict[int, tuple[IsinProbeTarget, int]] = {}
        for security_id, (target, cursor) in pending.items():
            if security_id in summary.resolved:
                continue
            if cursor + 1 < len(target.candidate_dates):
                nxt[security_id] = (target, cursor + 1)
            else:
                summary.unresolved.append(f"{target.symbol}#{security_id}")
        return nxt
