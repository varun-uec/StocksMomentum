"""Corporate-action adjustment sync — recomputes backward price-adjustment factors.

Not wired into the daily screening pipeline: NSE's corporate-actions endpoint
is per-symbol (no bulk/date-range form), so refreshing all ~500 universe
symbols every day would add ~500 external HTTP calls to every screening run
against a source that already 403s on its handshake request. Corporate
actions for a given symbol change rarely (a handful of times a year at
most), so this is meant to be invoked periodically (e.g. weekly) via
:mod:`momentum25.application.use_cases.research.refresh_corporate_actions`,
not inline with every bar upsert.

Known limitation — scope is ``ohlcv_daily`` only
------------------------------------------------

This refresh updates the live bar table. It does **not** touch the legacy
staging tables ``legacy_ohlcv_daily`` (NSE archive) or
``bse_legacy_ohlcv_daily`` (BSE pre-UDiFF archive), which hold their own
``adj_factor``/``adj_close`` columns and together carry millions of rows.

So a corporate action ingested today is reflected in live screening
immediately, but historical replay over the legacy era keeps the adjustment
factors written by the original backfill until that backfill is re-run.
Re-running it is the intended remedy: rebuilding adjustment factors across
the whole legacy archive is a bulk batch job
(``scripts/rp012_phase3_backfill.py``), not per-symbol work to fold into a
refresh that is already one external HTTP call per security.

The practical exposure is bounded. ``corporate_actions`` starts at
2011-01-06 (NSE's free API caps at 20 rows per symbol), and legacy bars
before that date have no action data to apply in either table.
"""

from __future__ import annotations

from datetime import date

from structlog import get_logger

from momentum25.domain.entities.market_data import compute_adjustment_factors
from momentum25.domain.ports.market_data import MarketDataProvider
from momentum25.domain.ports.repositories import CorporateActionRepository, OHLCVRepository

_logger = get_logger("corporate_actions_sync")

# NSE's corporate-actions endpoint returns full history regardless of ``since``;
# this only bounds what we request/retain, well beyond the platform's own
# 10-year research-history goal.
_LOOKBACK_YEARS = 15

# Effectively "all bars" for a single security -- bounded, not unlimited,
# to keep the query planner's LIMIT semantics intact (see get_series).
_MAX_LOOKBACK_DAYS = 10_000


async def refresh_adjustment_factors(
    market_data_provider: MarketDataProvider,
    corporate_action_repo: CorporateActionRepository,
    ohlcv_repo: OHLCVRepository,
    symbol: str,
    security_id: int,
    as_of: date,
) -> int:
    """Fetch, persist, and apply corporate actions for one security.

    Returns the number of bars whose ``adj_factor``/``adj_close`` were updated.
    """
    since = date(as_of.year - _LOOKBACK_YEARS, 1, 1)
    raw_actions = await market_data_provider.fetch_corporate_actions(symbol, since)
    if raw_actions:
        await corporate_action_repo.save_many(security_id, raw_actions)

    actions = await corporate_action_repo.list_for_security(security_id)
    if not actions:
        return 0

    series = await ohlcv_repo.get_series(
        security_id, lookback_days=_MAX_LOOKBACK_DAYS, as_of=as_of
    )
    if not series.bars:
        return 0

    factors = compute_adjustment_factors([b.date for b in series.bars], actions)
    updated = await ohlcv_repo.update_adjustment_factors(security_id, factors)
    _logger.info(
        "adjustment_factors_refreshed",
        symbol=symbol,
        security_id=security_id,
        actions=len(actions),
        bars_updated=updated,
    )
    return updated
