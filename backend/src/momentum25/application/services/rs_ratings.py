"""Universe-relative Relative Strength (RS) rating computation.

Shared by :class:`ScreeningOrchestrator` (live daily runs) and
:class:`HistoricalScreeningUseCase` (backtest replay) so both compute RS
ratings identically -- a rating computed one way for live runs and another
(or not at all) for historical replay would make backtests non-comparable
to production rankings.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum25.domain.entities.security import Security


async def compute_universe_rs_ratings(
    securities: list[Security],
    ohlcv_repo: Any,
    as_of_date: date,
    rs_return_weights: dict[str, Any] | None,
) -> dict[str, int]:
    """Compute universe-relative RS ratings as percentiles of a blended return.

    Uses the strategy's configured ``indicators.rs_return_weights``
    (``{period_days: weight}``) to blend multiple lookback returns per
    security -- this is what lets each Momentum Horizon strategy compute a
    genuinely horizon-appropriate RS ranking. Falls back to a single 63-day
    return if the strategy declares no weights.

    Args:
        securities: The universe to rank.
        ohlcv_repo: An :class:`OHLCVRepository` for price history.
        as_of_date: Only data up to and including this date is used (no lookahead).
        rs_return_weights: The strategy's ``indicators.rs_return_weights`` config.

    Returns:
        A mapping of symbol -> RS rating (1-99). A higher rating means
        stronger blended relative performance versus the universe.
    """
    weights_cfg = rs_return_weights or {"63": 1.0}
    periods = {int(period): float(weight) for period, weight in weights_cfg.items()}
    max_period = max(periods)

    returns: list[tuple[str, float]] = []
    for security in securities:
        if security.id is None:
            continue
        series = await ohlcv_repo.get_series(
            security.id, lookback_days=max_period + 5, as_of=as_of_date
        )
        bars: tuple[Any, ...] = series.bars if series else ()
        if len(bars) < 2:
            continue
        latest = float(bars[-1].close)
        weighted_sum = 0.0
        total_weight = 0.0
        for period, weight in periods.items():
            window = min(period, len(bars) - 1)
            if window <= 0:
                continue
            prior = float(bars[-(window + 1)].close)
            if prior <= 0:
                continue
            weighted_sum += weight * ((latest / prior) - 1.0)
            total_weight += weight
        if total_weight <= 0:
            continue
        returns.append((str(security.symbol), weighted_sum / total_weight))

    # A percentile needs at least two comparable returns; with 0 or 1, there is
    # no universe to rank against. Returning a fabricated midpoint (50) here
    # previously made a single-symbol lookup silently pass or fail
    # ``tt_rs_rating_min`` on a made-up number instead of surfacing that RS
    # could not be measured (Phase 1.2).
    if len(returns) < 2:
        return {}

    sorted_returns = sorted(returns, key=lambda x: x[1])
    n = len(sorted_returns)
    rs_ratings: dict[str, int] = {}
    for idx, (symbol, _) in enumerate(sorted_returns):
        # Percentile rank 1-99
        percentile = int(round((idx / (n - 1)) * 98)) + 1
        rs_ratings[symbol] = max(1, min(99, percentile))

    return rs_ratings
