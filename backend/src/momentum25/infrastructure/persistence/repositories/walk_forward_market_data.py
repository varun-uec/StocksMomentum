"""Real, Postgres-backed adapters for the walk-forward runner's data ports.

Implements :class:`PriceHistoryProvider` and :class:`BenchmarkProvider` from
``domain/ports/walk_forward.py`` (see
``docs/history/backtest-loop/brief-addendum-approximations.md``,
which points at real data already sitting in ``ohlcv_daily`` and
``benchmark_index_daily`` for these two ports).

Both ports are synchronous by design (the runner re-checks every price's date
itself and must not await mid-loop). SQLAlchemy's async session can't serve a
sync call, and a per-(security, date) round trip would be a query explosion —
one rebalance needs 4 prices per eligible security. So both adapters load their
full date range in one query at construction time (``load()``, async) and then
answer ``price_on_or_before`` / ``level_on_or_before`` from an in-memory,
per-key sorted list via binary search.

``EligibilityFactsProvider`` has two adapters here. Membership/surveillance
(Nifty 500 constituency, T2T, ASM/GSM) is still STUB — re-verified 2026-08-17
against this database and against live nseindia.com endpoints (see
``docs/history/backtest-loop/builder-notes/round-1.md`` for exactly what was tried): no table,
column, or reachable NSE endpoint in this environment carries point-in-time
Nifty 500 membership or T2T/ASM/GSM status. ``universe_membership`` looks
like a candidate but its ``reason`` values (``below_liquidity_floor``,
``insufficient_history``, ``not_yet_listed``, ``stale_data``, ...) are a
different production strategy's screening gates, not Nifty 500 constituency
or surveillance status — treating it as such would fabricate the universe
rather than approximate it. This remains the same documented,
human-decision-blocked gap recorded in
``docs/history/backtest-loop/reviewer-findings/loop2/round-1.md``.

Survivorship (checklist item 8) is now REAL: ``securities.delisting_date``/
``last_trade_date`` are populated from observed bar coverage (see
``scripts/one_off/rp012_populate_survivorship_dates.py``), and
``SqlSurvivorshipEligibilityProvider`` below uses them instead of the
``is_active`` flag. See ``SURVIVORSHIP_ELIGIBILITY_WARNING``.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.backtest.eligibility import EligibilityFacts
from momentum25.domain.backtest.execution import ExecutionBar
from momentum25.domain.ports.walk_forward import PricePoint
from momentum25.domain.universe import in_reference_universe
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
    """Real ``PriceHistoryProvider`` backed by ``ohlcv_daily``.

    Every price is ``raw × adj_factor`` (IMPLEMENTATION_SPEC §8, R3-B-30). The
    stored ``adj_close`` column is not read: it was NULL on 17% of rows (all
    with ``adj_factor = 1``), and dropping those rows made names that traded
    look absent. Volume is ``raw / adj_factor``.
    """

    def __init__(self, series: dict[int, _Series]) -> None:
        """Bind sorted per-security series."""
        self._series = series

    @classmethod
    async def load(cls, session: AsyncSession, start: date, end: date) -> SqlPriceHistoryProvider:
        """Load every bar in ``[start, end]`` in one query."""
        result = await session.execute(
            select(
                OHLCVDailyModel.security_id,
                OHLCVDailyModel.date,
                OHLCVDailyModel.open,
                OHLCVDailyModel.high,
                OHLCVDailyModel.low,
                OHLCVDailyModel.close,
                OHLCVDailyModel.volume,
                OHLCVDailyModel.adj_factor,
                OHLCVDailyModel.turnover_value,
            )
            .where(OHLCVDailyModel.date >= start, OHLCVDailyModel.date <= end)
            .order_by(OHLCVDailyModel.security_id, OHLCVDailyModel.date)
        )
        by_security: dict[int, _Series] = {}
        for sid, day, o, h, lo, c, volume, factor, turnover in result.all():
            f = factor if factor is not None else Decimal(1)
            series = by_security.setdefault(sid, _Series())
            series.append(
                ExecutionBar(
                    session_date=day,
                    adj_open=o * f,
                    adj_high=h * f,
                    adj_low=lo * f,
                    adj_close=c * f,
                    volume=int(volume or 0),
                    turnover_value=turnover if turnover is not None else Decimal(0),
                )
            )
        return cls(by_security)

    def price_on_or_before(
        self, security_id: int, target: date, as_of: date
    ) -> PricePoint | None:
        """Latest adjusted bar on or before ``min(target, as_of)``.

        Never looks past ``as_of`` even when ``target`` is later — matching
        the no-look-ahead contract the runner enforces on every call.
        """
        series = self._series.get(security_id)
        if series is None:
            return None
        bar = series.on_or_before(min(target, as_of))
        if bar is None:
            return None
        return PricePoint(security_id, bar.session_date, bar.adj_close, bar.adj_open)

    def execution_bar(self, security_id: int, session: date) -> ExecutionBar | None:
        """The adjusted bar dated exactly ``session``, or ``None``."""
        series = self._series.get(security_id)
        return series.on(session) if series is not None else None


class _Series:
    """One security's bars, ascending by date."""

    __slots__ = ("bars", "dates", "index")

    def __init__(self) -> None:
        self.dates: list[date] = []
        self.bars: list[ExecutionBar] = []
        self.index: dict[date, int] = {}

    def append(self, bar: ExecutionBar) -> None:
        self.index[bar.session_date] = len(self.bars)
        self.dates.append(bar.session_date)
        self.bars.append(bar)

    def on(self, day: date) -> ExecutionBar | None:
        i = self.index.get(day)
        return self.bars[i] if i is not None else None

    def on_or_before(self, day: date) -> ExecutionBar | None:
        i = bisect_right(self.dates, day) - 1
        return self.bars[i] if i >= 0 else None


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
        return cls([(sid, listed) for sid, listed in result.all() if listed is not None])

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


SURVIVORSHIP_ELIGIBILITY_WARNING = (
    "Nifty 500 membership and T2T/ASM surveillance status are still STUB "
    "(is_t2t=False, is_under_surveillance=False, in_nifty_500=True for every "
    "security) -- no adapter for that data exists "
    "(docs/history/backtest-loop/brief-addendum-loop3.md Item 13). The candidate "
    "set is the reference equity universe: NSE and dual-listed equities, no "
    "fund or ETF units, listed and not delisted on the decision date. "
    "Survivorship IS real: securities.delisting_date/last_trade_date come from "
    "observed bar coverage (scripts/one_off/rp012_populate_survivorship_dates.py), so a "
    "delisted security is included until its delisting date and excluded from "
    "it, regardless of the is_active flag. Renames are separate security rows "
    "until a verified identity link joins them (R3-B-31); a holding whose bars "
    "stop is reported as a non-trading holding, never guessed to be a rename."
)


class SqlSurvivorshipEligibilityProvider:
    """Reference equity universe with real survivorship, stub membership/surveillance.

    See ``SURVIVORSHIP_ELIGIBILITY_WARNING``. A security is a candidate on
    ``decision_date`` when ``in_reference_universe`` holds (IMPLEMENTATION_SPEC
    §8) and its listing date is known, which the brief's twelve-month rule
    needs. ``is_active`` is never read.
    """

    def __init__(self, rows: list[tuple[int, str, str | None, date, date | None]]) -> None:
        """Bind (security_id, exchange, isin, listing_date, delisting_date) rows."""
        self._rows = rows

    @classmethod
    async def load(cls, session: AsyncSession) -> SqlSurvivorshipEligibilityProvider:
        """Load every security with a known listing date, ordered by id."""
        result = await session.execute(
            select(
                SecurityModel.id,
                SecurityModel.exchange,
                SecurityModel.isin,
                SecurityModel.listing_date,
                SecurityModel.delisting_date,
            )
            .where(SecurityModel.listing_date.is_not(None))
            .order_by(SecurityModel.id)
        )
        return cls([tuple(row) for row in result.all()])  # type: ignore[misc]

    def facts_as_of(self, decision_date: date) -> list[EligibilityFacts]:
        """Return facts for every reference-universe security on ``decision_date``."""
        return [
            EligibilityFacts(
                security_id=security_id,
                listing_days_as_of_decision_date=(decision_date - listed).days,
                is_t2t=False,
                is_under_surveillance=False,
                in_nifty_500=True,
            )
            for security_id, exchange, isin, listed, delisted in self._rows
            if in_reference_universe(exchange, isin, listed, delisted, decision_date)
        ]
