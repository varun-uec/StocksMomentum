"""Repository ports — persistence interfaces implemented by the infrastructure layer.

Repositories map between domain objects and storage; ORM models never cross this
boundary (ADR-001/004). Run result writes are append-only (ADR-006).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.ports.market_data import RawCorporateAction, RawIndexBar
from momentum25.domain.research.forward_returns import ForwardReturn
from momentum25.domain.research.period_correct_resolution import SymbolInterval
from momentum25.domain.value_objects.results import (
    Ranking,
    RuleResult,
    ScorePoint,
    StockScore,
    UniverseMembership,
)

_BuiltinList = list


@runtime_checkable
class SecurityRepository(Protocol):
    """Persistence for the instrument master."""

    async def upsert_many(self, securities: list[Security]) -> None:
        """Insert or update securities by symbol."""
        ...

    async def list_active(self) -> list[Security]:
        """Return all active securities."""
        ...

    async def list_all(self) -> list[Security]:
        """Return every security, active and inactive."""
        ...

    async def rename_chain_intervals(self) -> dict[str, list[SymbolInterval]]:
        """Return ``symbol -> trading intervals`` for every ISIN-shared rename chain."""
        ...

    async def get_by_symbol(self, symbol: str) -> Security | None:
        """Return a security by symbol, or ``None``."""
        ...

    async def search(self, query: str, limit: int) -> list[Security]:
        """Return active securities matching *query* on symbol or name."""
        ...

    async def deactivate_symbols(self, symbols: list[str]) -> int:
        """Mark the given symbols inactive; return the number of rows updated."""
        ...


@runtime_checkable
class OHLCVRepository(Protocol):
    """Persistence for daily price series."""

    async def upsert_bars(self, security_id: int, bars: list[OHLCVBar]) -> int:
        """Insert or update bars; return the number written."""
        ...

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        """Return a price series up to ``as_of`` covering ``lookback_days``."""
        ...

    async def latest_date(self) -> date | None:
        """Return the most recent stored bar date, or ``None``."""
        ...

    async def list_distinct_dates(self, start: date, end: date) -> list[date]:
        """Return every distinct bar date in ``[start, end]``, ascending.

        This is the real trading calendar (derived from actual ingested
        data), used in place of any weekday/holiday approximation.
        """
        ...

    async def closes_between(
        self, start: date, end: date
    ) -> dict[int, list[tuple[date, Decimal]]]:
        """Return every close in ``[start, end]``, grouped by security, ascending by date.

        Bulk accessor for cross-sectional (universe-wide) analytics such as the
        market-breadth and sector-strength panels, which need one trailing year
        of closes for the whole universe at once. Issuing one query per security
        for that is thousands of round trips for a single page load.
        """
        ...

    async def get_bars_after(
        self, security_id: int, after_date: date, limit: int
    ) -> list[OHLCVBar]:
        """Return up to ``limit`` ascending bars strictly after ``after_date``."""
        ...

    async def update_adjustment_factors(
        self, security_id: int, factors: dict[date, Decimal]
    ) -> int:
        """Persist a computed backward-adjustment factor per bar date.

        ``adj_close`` is recomputed from the stored raw ``close`` in the same
        statement, so the two columns never drift apart. Returns the number of
        bars updated.
        """
        ...


@runtime_checkable
class CorporateActionRepository(Protocol):
    """Persistence for corporate actions (raw disclosure + resolved price ratio)."""

    async def save_many(self, security_id: int, actions: list[RawCorporateAction]) -> int:
        """Insert or update corporate actions for a security; return rows written."""
        ...

    async def list_for_security(self, security_id: int) -> list[RawCorporateAction]:
        """Return all persisted corporate actions for a security, ascending by ex_date."""
        ...


@runtime_checkable
class StrategyRepository(Protocol):
    """Persistence for strategy definitions."""

    async def upsert(self, strategy: Strategy) -> int:
        """Insert or update a strategy by (name, version); return its id."""
        ...

    async def get_active(self, name: str) -> Strategy | None:
        """Return the active strategy with the given name, or ``None``."""
        ...

    async def list(self) -> list[Strategy]:
        """Return all strategies."""
        ...

    async def list_with_completed_runs(self) -> _BuiltinList[Strategy]:
        """Return strategies that have at least one completed live run."""
        ...

    async def delete_orphans(self, names_on_disk: _BuiltinList[str]) -> _BuiltinList[str]:
        """Delete strategies absent from disk, but only those with no stored runs.

        Returns the names of the deleted strategies. Strategies that own run
        history are left untouched (run rows are append-only).
        """
        ...


@runtime_checkable
class ScreeningRunRepository(Protocol):
    """Persistence for screening runs and their immutable result snapshots."""

    async def create(self, run: ScreeningRun) -> int:
        """Persist a new run row; return its id."""
        ...

    async def update(self, run: ScreeningRun) -> None:
        """Update a run's mutable lifecycle fields (status/timestamps/error/stats)."""
        ...

    async def get(self, run_id: int) -> ScreeningRun | None:
        """Return a run by id, or ``None``."""
        ...

    async def list_runs(
        self,
        status: str | None,
        limit: int,
        offset: int,
        exclude_historical: bool = True,
        exclude_research: bool = True,
        strategy_id: int | None = None,
    ) -> tuple[list[ScreeningRun], int]:
        """Return a page of runs and the total count, optionally scoped to one strategy."""
        ...

    async def latest_completed(self, strategy_id: int) -> ScreeningRun | None:
        """Return the most recent completed run for a strategy, or ``None``."""
        ...

    async def save_results(
        self, run_id: int, scores: list[StockScore], rankings: list[Ranking]
    ) -> None:
        """Append result rows (scores, rankings, rule results) for a completed run."""
        ...

    async def save_universe_membership(
        self, run_id: int, memberships: list[UniverseMembership]
    ) -> None:
        """Append per-run universe eligibility records (survivorship-bias audit trail)."""
        ...

    async def save_forward_returns(self, run_id: int, returns: list[ForwardReturn]) -> None:
        """Append forward-return feature rows for a run (never revised once written)."""
        ...

    async def get_forward_returns(
        self, run_id: int, security_id: int | None = None
    ) -> list[ForwardReturn]:
        """Return persisted forward-return rows for a run, optionally scoped to one security."""
        ...

    async def get_rankings(self, run_id: int, limit: int, offset: int) -> tuple[list[Ranking], int]:
        """Return a page of rankings for a run and the total count."""
        ...

    async def get_screening_result(self, run_id: int, security_id: int) -> Ranking | None:
        """Return the persisted score/rank for one security in a run, or ``None``."""
        ...

    async def get_rule_results(self, run_id: int, security_id: int) -> list[RuleResult]:
        """Return all persisted rule results for one security in a run."""
        ...

    async def score_history(
        self, strategy_id: int, security_id: int, limit: int
    ) -> list[ScorePoint]:
        """Return a security's score/rank history across runs for a strategy."""
        ...


@runtime_checkable
class BenchmarkIndexRepository(Protocol):
    """Persistence for benchmark index (e.g. Nifty 50/500) daily closes."""

    async def upsert_bars(self, index_code: str, bars: list[RawIndexBar]) -> int:
        """Insert or update benchmark index bars; return the number written."""
        ...

    async def get_return(self, index_code: str, as_of: date) -> Decimal | None:
        """Return the index's close-to-close return ending on ``as_of``, or ``None``.

        ``None`` means fewer than two persisted closes exist on or before
        ``as_of`` -- callers must not substitute a guessed value (e.g. zero)
        in that case, since a fabricated "flat" benchmark silently corrupts
        every alpha/beta computed against it.
        """
        ...

    async def get_close(self, index_code: str, as_of: date) -> Decimal | None:
        """Return the index's close on or before ``as_of``, or ``None`` if none exists."""
        ...

    async def get_close_series(self, index_code: str) -> dict[date, Decimal]:
        """Return every persisted close for ``index_code``, keyed by date.

        Bulk accessor for callers (e.g. forward-return backfills) that need
        many date lookups against the same index -- avoids one query per
        lookup against a table that is small (a few thousand rows) relative
        to the number of lookups.
        """
        ...


@runtime_checkable
class WatchlistRepository(Protocol):
    """Persistence for the single global watchlist (Phase 6.9)."""

    async def add(self, security_id: int) -> None:
        """Add a security to the watchlist; a no-op if already present."""
        ...

    async def remove(self, security_id: int) -> None:
        """Remove a security from the watchlist; a no-op if absent."""
        ...

    async def list_symbols(self) -> list[str]:
        """Return the watchlisted symbols, oldest addition first."""
        ...
