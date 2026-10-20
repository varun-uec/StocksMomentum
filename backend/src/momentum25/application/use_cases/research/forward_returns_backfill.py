"""ForwardReturnsBackfill — persists forward-return features for a completed run.

A run's forward return is not knowable at run time (ADR-009: no lookahead) --
this use case is invoked later, once market data reaches the exit session
``horizon_days`` NSE sessions after the run date (R3-B-32), and appends rows
to ``forward_returns`` with ``horizon_basis = 'sessions'``. Already-computed
(run_id, security_id, horizon_days, basis) combinations are never recomputed
or revised, so re-running this is always safe to repeat. Rows of the legacy
``own_bars`` basis are left as they are.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from structlog import get_logger

from momentum25.domain.ports.trading_calendar import TradingCalendar
from momentum25.domain.research.forward_returns import ForwardReturn, compute_forward_return

_logger = get_logger("forward_returns_backfill")

# Standard research horizons spanning the platform's short- to long-term
# momentum horizons (Objective 4: "forward returns 5d-252d").
DEFAULT_HORIZONS: tuple[int, ...] = (5, 10, 20, 60, 120, 252)

# Every strategy config in this platform declares "NIFTY500" as its
# benchmark_index (ADR-005 strategy-as-config); used here as the default
# rather than looking it up per-run, since the run itself doesn't carry it.
DEFAULT_BENCHMARK_INDEX = "NIFTY500"


def _adjusted_close(bar: Any) -> Any:
    """``close × adj_factor``, the one adjusted-price rule (IMPLEMENTATION_SPEC §8)."""
    return bar.close * bar.adj_factor


class ForwardReturnsBackfill:
    """Backfills forward-return features for one completed screening run."""

    def __init__(
        self,
        screening_run_repo: Any,
        ohlcv_repo: Any,
        benchmark_index_repo: Any = None,
        horizons: tuple[int, ...] = DEFAULT_HORIZONS,
        benchmark_index_code: str = DEFAULT_BENCHMARK_INDEX,
        *,
        calendar: TradingCalendar,
    ) -> None:
        """Wire the use case with its collaborators.

        ``benchmark_index_repo`` is optional: when omitted, rows are still
        written with ``benchmark_return``/``excess_return`` left ``None``
        rather than guessed.
        """
        self._screening_run_repo = screening_run_repo
        self._ohlcv_repo = ohlcv_repo
        self._benchmark_index_repo = benchmark_index_repo
        self._horizons = horizons
        self._benchmark_index_code = benchmark_index_code
        self._calendar = calendar

    async def execute(self, run_id: int) -> dict[str, int]:
        """Compute and persist any newly-available forward-return rows for ``run_id``.

        Returns a summary: ``{"securities_evaluated": N, "rows_written": M}``.
        """
        run = await self._screening_run_repo.get(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        rankings, _total = await self._screening_run_repo.get_rankings(
            run_id, limit=10_000, offset=0
        )
        existing = await self._screening_run_repo.get_forward_returns(run_id)
        already_computed = {(fr.security_id, fr.horizon_days) for fr in existing}

        max_horizon = max(self._horizons)
        new_rows: list[ForwardReturn] = []
        securities_evaluated = 0

        # Preloaded once per run (a few thousand rows) rather than queried
        # per (security, horizon) -- this table is small relative to the
        # number of lookups a single run's backfill performs.
        benchmark_closes: dict[date, Any] = {}
        if self._benchmark_index_repo is not None:
            benchmark_closes = await self._benchmark_index_repo.get_close_series(
                self._benchmark_index_code
            )
        benchmark_entry_close = self._nearest_close(benchmark_closes, run.run_date)
        # The sessions after the run date that market data has reached.
        data_through = await self._ohlcv_repo.latest_date()
        sessions = (
            self._calendar.sessions_between(run.run_date + timedelta(days=1), data_through)[
                :max_horizon
            ]
            if data_through is not None
            else []
        )

        for ranking in rankings:
            security_id = ranking.security_id
            pending_horizons = [
                h for h in self._horizons if (security_id, h) not in already_computed
            ]
            if not pending_horizons:
                continue

            entry_series = await self._ohlcv_repo.get_series(
                security_id, lookback_days=1, as_of=run.run_date
            )
            if not entry_series.bars:
                continue
            entry_close = _adjusted_close(entry_series.latest)

            forward_bars = await self._ohlcv_repo.get_bars_after(
                security_id, after_date=run.run_date, limit=max_horizon
            )
            path = [(b.date, _adjusted_close(b)) for b in forward_bars]
            securities_evaluated += 1

            for horizon in pending_horizons:
                benchmark_exit_close = None
                if benchmark_entry_close is not None and len(sessions) >= horizon:
                    benchmark_exit_close = self._nearest_close(
                        benchmark_closes, sessions[horizon - 1]
                    )
                fr = compute_forward_return(
                    security_id,
                    horizon,
                    entry_close,
                    path,
                    sessions,
                    benchmark_entry_close=benchmark_entry_close,
                    benchmark_exit_close=benchmark_exit_close,
                )
                if fr is not None:
                    new_rows.append(fr)

        if new_rows:
            await self._screening_run_repo.save_forward_returns(run_id, new_rows)
            await self._commit()

        summary = {"securities_evaluated": securities_evaluated, "rows_written": len(new_rows)}
        _logger.info("forward_returns_backfill_completed", run_id=run_id, **summary)
        return summary

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._screening_run_repo, "_session", None)
        if session is not None:
            await session.commit()

    @staticmethod
    def _nearest_close(closes: dict[date, Any], as_of: date) -> Any:
        """Return ``closes[d]`` for the nearest ``d <= as_of`` within 10 days, or ``None``."""
        for offset in range(10):
            candidate = as_of - timedelta(days=offset)
            if candidate in closes:
                return closes[candidate]
        return None
