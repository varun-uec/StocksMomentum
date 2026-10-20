"""Relative Strength (RS) ratings, calendar-aligned (IMPLEMENTATION_SPEC §8, engine v2).

Shared by :class:`ScreeningOrchestrator` (live daily runs),
:class:`HistoricalScreeningUseCase` (historical and point-in-time replay) and
the read paths, so every surface computes RS identically.

The rule, exactly:

- t is the run date; sessions come from the injected NSE trading calendar.
- S_d is the d-th session before t (t is session 0). The anchor for R(d) is the
  security's last bar on or before S_d, valid only if it is dated no more than
  ``ANCHOR_TOLERANCE_SESSIONS`` sessions before S_d. Otherwise R(d) is
  undefined and the security gets no rating. No window is ever shortened.
- Prices are ``close × adj_factor`` (one adjusted-price rule, R3-B-30).
- The population is the reference equity universe on t, restricted to names
  with at least ``MIN_RS_BARS`` bars, a last bar not stale on t, and a defined
  raw return. It does not depend on any strategy's eligibility settings.
- Percentile: sort ascending by (raw return, security_id); the i-th of n gets
  ``round(i / (n - 1) * 98) + 1``.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from datetime import date, timedelta
from typing import Any, Protocol

from momentum25.domain.engine_version import ENGINE_VERSION, REFERENCE_UNIVERSE_VERSION
from momentum25.domain.entities.security import Security
from momentum25.domain.ports.trading_calendar import TradingCalendar
from momentum25.domain.research.data_quality import is_stale_as_of
from momentum25.domain.universe import REFERENCE_EXCHANGES, reference_universe
from momentum25.domain.value_objects.instrument import is_equity

ANCHOR_TOLERANCE_SESSIONS = 5  # owner decision S-4, 2026-10-20
MIN_RS_BARS = 253  # R(252) needs the bar 252 bars before the latest


class RsRatingCache(Protocol):
    """Cache for one day's universe RS ratings, keyed by (date, computation basis)."""

    async def get(self, as_of: date, basis: str) -> dict[str, int] | None:
        """Return the cached ratings, or ``None`` on a miss."""
        ...

    async def set(self, as_of: date, basis: str, ratings: dict[str, int]) -> None:
        """Cache *ratings* for the given trading date and basis."""
        ...


def rs_cache_basis(rs_return_weights: dict[str, Any] | None) -> str:
    """The cache basis: the engine and universe versions plus the RS weights.

    Two strategies with the same weights share ratings; a strategy edited to new
    weights, or a new engine version, never reads another's (ADR-014 §11).
    """
    weights = json.dumps(
        {str(k): str(v) for k, v in (rs_return_weights or {}).items()}, sort_keys=True
    )
    digest = hashlib.sha256(weights.encode()).hexdigest()[:12]
    return f"e{ENGINE_VERSION}u{REFERENCE_UNIVERSE_VERSION}w{digest}"


async def resolve_universe_rs_ratings(
    securities_repo: Any,
    ohlcv_repo: Any,
    strategy: Any,
    as_of: date,
    cache: RsRatingCache | None,
    calendar: TradingCalendar,
) -> dict[str, int]:
    """Return the RS ratings for *as_of*, computing them only on a miss.

    Every read path that needs a single symbol's RS rating (``/stocks/{symbol}
    /live`` and ``/watchlist/detail``) ranks it against the same population the
    run uses, which costs one price-history walk over the universe. Ratings for
    a trading date do not change intraday, so they are shared through the cache.
    """
    weights = strategy.config.indicators.get("rs_return_weights")
    basis = rs_cache_basis(weights)
    if cache is not None:
        cached = await cache.get(as_of, basis)
        if cached is not None:
            return cached

    population = reference_universe(await securities_repo.list_all(), as_of)
    ratings = await compute_universe_rs_ratings(population, ohlcv_repo, as_of, weights, calendar)

    if cache is not None:
        await cache.set(as_of, basis, ratings)
    return ratings


def _adjusted_close(bar: Any) -> float:
    """``close × adj_factor``: a raw close across a 1:5 split would read as -80%."""
    return float(bar.close * bar.adj_factor)


def _session_index(sessions: list[date], day: date) -> int:
    """Index of the last session on or before ``day`` (-1 if none)."""
    return bisect_right(sessions, day) - 1


async def compute_universe_rs_ratings(
    securities: list[Security],
    ohlcv_repo: Any,
    as_of_date: date,
    rs_return_weights: dict[str, Any] | None,
    calendar: TradingCalendar,
) -> dict[str, int]:
    """Compute calendar-aligned RS ratings for the reference population.

    ``securities`` is the caller's reference equity universe on the date (live:
    ``reference_universe``; point in time: the decision's universe). Fund units
    and non-NSE rows are dropped here as an invariant; the data-validity rules
    (bars, staleness, anchors) are applied here. Uses the strategy's
    ``indicators.rs_return_weights`` (``{period_sessions: weight}``); a single
    63-session return when none.

    Returns ``{symbol: rating}`` (1-99). A security outside the population has
    no entry.
    """
    weights_cfg = rs_return_weights or {"63": 1.0}
    periods = {int(period): float(weight) for period, weight in weights_cfg.items()}
    max_period = max(periods)
    sessions = calendar.sessions_between(
        as_of_date - timedelta(days=2 * (max_period + ANCHOR_TOLERANCE_SESSIONS) + 30),
        as_of_date,
    )
    t_index = _session_index(sessions, as_of_date)
    if t_index - max_period - ANCHOR_TOLERANCE_SESSIONS < 0:
        raise ValueError(f"calendar holds too few sessions before {as_of_date} for RS")
    lookback = max(MIN_RS_BARS, max_period + ANCHOR_TOLERANCE_SESSIONS + 1)

    returns: list[tuple[float, int, str]] = []
    for security in securities:
        if str(security.exchange) not in REFERENCE_EXCHANGES or not is_equity(security.isin):
            continue
        if security.id is None:
            continue
        series = await ohlcv_repo.get_series(
            security.id, lookback_days=lookback, as_of=as_of_date
        )
        bars: tuple[Any, ...] = series.bars if series else ()
        if len(bars) < MIN_RS_BARS or is_stale_as_of(as_of_date, bars[-1].date):
            continue
        dates = [b.date for b in bars]
        latest = _adjusted_close(bars[-1])
        weighted_sum = 0.0
        for period, weight in periods.items():
            reference_index = t_index - period
            i = bisect_right(dates, sessions[reference_index]) - 1
            earliest = reference_index - ANCHOR_TOLERANCE_SESSIONS
            if i < 0 or _session_index(sessions, dates[i]) < earliest:
                break  # no valid anchor: R(period) is undefined
            anchor = _adjusted_close(bars[i])
            if anchor <= 0:
                break
            weighted_sum += weight * (latest / anchor - 1.0)
        else:
            raw_return = weighted_sum / sum(periods.values())
            returns.append((raw_return, security.id, str(security.symbol)))

    # A percentile needs at least two comparable returns. Returning a made-up
    # midpoint for a lone name would pass or fail ``tt_rs_rating_min`` on a
    # number nobody measured (Phase 1.2).
    if len(returns) < 2:
        return {}

    ordered = sorted(returns, key=lambda r: (r[0], r[1]))
    n = len(ordered)
    return {
        symbol: max(1, min(99, int(round(idx / (n - 1) * 98)) + 1))
        for idx, (_, _, symbol) in enumerate(ordered)
    }
