"""Real, Postgres-backed adapters for the walk-forward runner's data ports.

Implements :class:`PriceHistoryProvider` and :class:`BenchmarkProvider` from
``domain/ports/walk_forward.py`` (see ``handoff/brief-addendum-approximations.md``,
which points at real data already sitting in ``ohlcv_daily`` and
``benchmark_index_daily`` for these two ports).

Both ports are synchronous by design (the runner re-checks every price's date
itself and must not await mid-loop). SQLAlchemy's async session can't serve a
sync call, and a per-(security, date) round trip would be a query explosion —
one rebalance needs 4 prices per eligible security. So both adapters load their
full date range in one query at construction time (``load()``, async) and then
answer ``price_on_or_before`` / ``level_on_or_before`` from an in-memory,
per-key sorted list via binary search.

``EligibilityFactsProvider`` has no adapter here. Verified against this
database (2026-08-17): no table, column, or ingestion adapter anywhere in the
codebase carries Nifty 500 index membership (current or historical) or
ASM/GSM/T2T surveillance status — not even a "current list" to apply
retroactively as the brief-addendum-approximations.md universe/surveillance
approximation describes. ``universe_membership`` looks like a candidate but
its ``reason`` values (``below_liquidity_floor``, ``insufficient_history``,
``not_yet_listed``, ``stale_data``, ...) are a different production strategy's
screening gates, not Nifty 500 constituency or surveillance status — treating
it as such would fabricate the universe rather than approximate it. This
remains the same documented, human-decision-blocked gap recorded in
``handoff/reviewer-findings/loop2/round-1.md``.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.backtest.eligibility import EligibilityFacts
from momentum25.domain.ports.walk_forward import PricePoint
from momentum25.infrastructure.persistence.models import (
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    SecurityModel,
)

# brief-addendum-approximations.md §"Benchmark provider": verified against
# benchmark_index_daily (2015-01-01 level 6786.10, 2026-08-07 level
# 23712.10 — the well-known Nifty 500 *price* index range for this period).
# A TRI series compounds dividends on top of price return and would print
# materially higher over an 11-year span. No TRI series exists in this
# database to diff against directly, so this is a magnitude/plausibility
# check, not a row-for-row reconciliation — stated here rather than silently
# assumed.
BENCHMARK_LABEL = "Nifty 500 Price Index (not TRI)"


class SqlPriceHistoryProvider:
    """Real ``PriceHistoryProvider`` backed by ``ohlcv_daily.adj_close``.

    Rows with a ``NULL adj_close`` are excluded at load time (fail closed, same
    policy the runner already applies when a provider returns ``None`` —
    never fall back to an unadjusted ``close``).
    """

    def __init__(self, series: dict[int, tuple[list[date], list[Decimal]]]) -> None:
        """Bind the in-memory, per-security sorted (dates, closes) series."""
        self._series = series

    @classmethod
    async def load(
        cls, session: AsyncSession, start: date, end: date
    ) -> SqlPriceHistoryProvider:
        """Load every adjusted close in ``[start, end]`` in one query."""
        result = await session.execute(
            select(
                OHLCVDailyModel.security_id,
                OHLCVDailyModel.date,
                OHLCVDailyModel.adj_close,
            )
            .where(
                OHLCVDailyModel.date >= start,
                OHLCVDailyModel.date <= end,
                OHLCVDailyModel.adj_close.is_not(None),
            )
            .order_by(OHLCVDailyModel.security_id, OHLCVDailyModel.date)
        )
        by_security: dict[int, tuple[list[date], list[Decimal]]] = {}
        for security_id, session_date, adj_close in result.all():
            dates, closes = by_security.setdefault(security_id, ([], []))
            dates.append(session_date)
            closes.append(adj_close)
        return cls(by_security)

    def price_on_or_before(
        self, security_id: int, target: date, as_of: date
    ) -> PricePoint | None:
        """Latest adjusted close on or before ``min(target, as_of)``.

        Never looks past ``as_of`` even when ``target`` is later — matching
        the no-look-ahead contract the runner enforces on every call.
        """
        series = self._series.get(security_id)
        if not series:
            return None
        dates, closes = series
        horizon = min(target, as_of)
        idx = bisect_right(dates, horizon) - 1
        if idx < 0:
            return None
        return PricePoint(security_id, dates[idx], closes[idx])


class SqlBenchmarkProvider:
    """Real ``BenchmarkProvider`` backed by ``benchmark_index_daily``.

    Reporting only (brief §8) — never feeds selection. See ``BENCHMARK_LABEL``:
    this series is the Nifty 500 price index, not TRI; every caller that
    surfaces ``level_on_or_before``'s result to a human must carry that label
    next to the number.
    """

    def __init__(self, index_code: str, dates: list[date], levels: list[Decimal]) -> None:
        """Bind the in-memory, sorted (dates, levels) series for ``index_code``."""
        self.index_code = index_code
        self.label = BENCHMARK_LABEL
        self._dates = dates
        self._levels = levels

    @classmethod
    async def load(
        cls, session: AsyncSession, index_code: str, start: date, end: date
    ) -> SqlBenchmarkProvider:
        """Load every benchmark level in ``[start, end]`` in one query."""
        result = await session.execute(
            select(BenchmarkIndexDailyModel.date, BenchmarkIndexDailyModel.close)
            .where(
                BenchmarkIndexDailyModel.index_code == index_code,
                BenchmarkIndexDailyModel.date >= start,
                BenchmarkIndexDailyModel.date <= end,
            )
            .order_by(BenchmarkIndexDailyModel.date)
        )
        rows = result.all()
        return cls(index_code, [r[0] for r in rows], [r[1] for r in rows])

    def level_on_or_before(self, target: date, as_of: date) -> Decimal | None:
        """Latest level on or before ``min(target, as_of)``."""
        horizon = min(target, as_of)
        idx = bisect_right(self._dates, horizon) - 1
        if idx < 0:
            return None
        return self._levels[idx]


ELIGIBILITY_STUB_WARNING = (
    "STUB eligibility provider: every active NSE security is treated as a "
    "Nifty 500 constituent with clean T2T/ASM status. This is NOT real Nifty "
    "500 membership or surveillance data -- no such adapter exists in this "
    "codebase (see this module's docstring). Any run using this provider is "
    "not a Nifty 500 backtest and does not close checklist item 13 or the "
    "EligibilityFactsProvider gap; it exists only to give the walk-forward "
    "runner and its report a real, non-test execution path."
)


class StubAllActiveSecuritiesEligibilityProvider:
    """Known-gap stand-in for ``EligibilityFactsProvider`` -- see ``ELIGIBILITY_STUB_WARNING``.

    Treats every active NSE row in ``securities`` as an eligible-by-membership,
    surveillance-clean constituent. This does not approximate Nifty 500
    membership (there is no current *or* historical Nifty 500 constituent
    list anywhere in this database to apply retroactively, unlike the
    benchmark/universe approximation ``brief-addendum-approximations.md``
    describes) -- it is a wider, explicitly-labeled stand-in so real callers
    (a CLI command, a script) have something to pass the runner besides a
    hand-built fixture. Only ``listing_days_as_of_decision_date`` is computed
    from real data (``securities.listing_date``); ``in_nifty_500``,
    ``is_t2t``, and ``is_under_surveillance`` are not backed by any source.
    """

    def __init__(self, listings: list[tuple[int, date]]) -> None:
        """Bind the in-memory (security_id, listing_date) pairs for active NSE names."""
        self._listings = listings

    @classmethod
    async def load(cls, session: AsyncSession) -> StubAllActiveSecuritiesEligibilityProvider:
        """Load every active NSE security's listing date in one query."""
        result = await session.execute(
            select(SecurityModel.id, SecurityModel.listing_date).where(
                SecurityModel.exchange == "NSE",
                SecurityModel.is_active.is_(True),
                SecurityModel.listing_date.is_not(None),
            )
        )
        return cls([(sid, listed) for sid, listed in result.all()])

    def facts_as_of(self, decision_date: date) -> list[EligibilityFacts]:
        """Return stub facts for every listed-by-``decision_date`` active security."""
        facts = []
        for security_id, listed in self._listings:
            if listed > decision_date:
                continue
            facts.append(
                EligibilityFacts(
                    security_id=security_id,
                    listing_days_as_of_decision_date=(decision_date - listed).days,
                    is_t2t=False,
                    is_under_surveillance=False,
                    in_nifty_500=True,
                )
            )
        return facts
