"""The production runner agrees with an independent reference, fill for fill.

The synthetic market is deterministic (no random source) and holds every case
method v2 must handle: trading gaps, a delisting, thin-turnover sessions, a
split, a fund unit, a dual-listed name, a BSE-only row and a late listing.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from momentum25.application.use_cases.walk_forward import WalkForwardRunner, _months_before
from momentum25.domain.backtest.execution import ExecutionBar
from momentum25.domain.ports.walk_forward import PricePoint
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SqlSurvivorshipEligibilityProvider,
)
from tests.reference import walk_forward_reference as reference
from tests.unit.test_walk_forward import WeekdayCalendar

START, END = date(2022, 3, 1), date(2023, 12, 29)
CAPITAL = Decimal(1_000_000)
CAL = WeekdayCalendar()
DAYS = CAL.sessions_between(date(2020, 11, 2), END)
SPLIT_SID, SPLIT_DAY = 4, date(2022, 9, 1)
# Two strong names first eligible at the June 2022 decision. Their first fill
# date opens a trading gap: 4 sessions (the buy fills on the 5th, the last day
# of the window) and 5 sessions (the buy expires; a 6-session window would fill).
JUNE_F = date(2022, 6, 1)
GAPS = {
    41: CAL.sessions_between(JUNE_F, date(2022, 6, 30))[:4],
    42: CAL.sessions_between(JUNE_F, date(2022, 6, 30))[:5],
}


def _q(x: float) -> Decimal:
    return Decimal(str(round(x, 2)))


def _market() -> tuple[dict[int, list[tuple]], list[tuple]]:
    bars: dict[int, list[tuple]] = {}
    universe: list[tuple] = []
    for sid in range(1, 91):
        drift = 0.0002 * ((sid * 7) % 11 - 4) if sid not in GAPS else 0.003
        price = 50.0 + sid
        rows = []
        for i, day in enumerate(DAYS):
            price *= 1 + drift + 0.015 * math.sin(i * 0.21 + sid)
            if sid % 9 == 0 and 300 <= i < 360:
                continue  # a trading gap (suspension or trade-for-trade period)
            if sid == 17 and day > date(2023, 2, 15):
                continue  # delisted
            if sid == 23 and i % 4 == 0:
                continue  # an illiquid name that skips sessions
            if day in GAPS.get(sid, ()):
                continue
            close = _q(price)
            open_ = _q(price * (1 + 0.004 * math.cos(i + sid)))
            high, low = max(open_, close) + Decimal("0.5"), min(open_, close) - Decimal("0.5")
            turnover = Decimal(40_000) if sid % 5 == 0 and i % 3 == 0 else Decimal(50_000_000)
            factor = Decimal(1)
            if sid == SPLIT_SID and day < SPLIT_DAY:
                # 1:2 split: raw prints before it are double; their factor is 0.5
                close, open_, high, low = close * 2, open_ * 2, high * 2, low * 2
                factor = Decimal("0.5")
            rows.append((day, open_, high, low, close, 10_000, factor, turnover))
        bars[sid] = rows
        exchange = "BOTH" if sid % 4 == 0 else "NSE"
        isin = f"INE{sid:06d}01"
        listed = date(2015, 1, 1)
        delisted = date(2023, 2, 15) if sid == 17 else None
        if sid == 30:
            isin = "INF000030A01"  # a fund unit: excluded however strong
        if sid == 31:
            exchange = "BSE"  # BSE-only: not admitted
        if sid == 33:
            listed = date(2022, 6, 1)  # a late listing: eligible only after twelve months
        if sid in GAPS:
            listed = date(2021, 9, 15)  # 258 days at the 2022-05-31 decision, 226 at 2022-04-29
        universe.append((sid, exchange, isin, listed, delisted))
    return bars, universe


class _Prices:
    """Adjusted prices from the same rows the reference reads: raw × factor."""

    def __init__(self, bars: dict[int, list[tuple]]) -> None:
        self._rows = {
            sid: [
                ExecutionBar(d, o * f, h * f, lo * f, c * f, v, t)
                for (d, o, h, lo, c, v, f, t) in rows
            ]
            for sid, rows in bars.items()
        }
        self._index = {sid: {b.session_date: b for b in rows} for sid, rows in self._rows.items()}

    def price_on_or_before(self, security_id: int, target: date, as_of: date) -> PricePoint | None:
        horizon = min(target, as_of)
        best = None
        for bar in self._rows.get(security_id, []):
            if bar.session_date > horizon:
                break
            best = bar
        if best is None:
            return None
        return PricePoint(security_id, best.session_date, best.adj_close, best.adj_open)

    def execution_bar(self, security_id: int, session: date) -> ExecutionBar | None:
        return self._index.get(security_id, {}).get(session)


def test_production_runner_matches_the_independent_reference() -> None:
    bars, universe = _market()
    runner = WalkForwardRunner(CAL, _Prices(bars), SqlSurvivorshipEligibilityProvider(universe))
    result = runner.run(START, END, CAPITAL)
    sessions = CAL.sessions_between(_months_before(START, 13), END)
    expected = reference.run(bars, universe, sessions, START, END, CAPITAL)

    assert [r.selected for r in result.rebalances] == expected.selected
    produced = [
        (t.security_id, t.side, t.fill_date, t.fill_price, abs(t.quantity), t.notional, t.cost)
        for t in result.trades
    ]
    assert produced == expected.fills
    closed = sorted((o.security_id, o.side, o.order_date, o.reason) for o in result.closed_orders)
    assert closed == sorted(expected.closed)
    assert result.final_nav == expected.final_nav
    peak, worst = expected.navs[0], Decimal(0)
    for nav in expected.navs:
        peak = max(peak, nav)
        worst = min(worst, nav / peak - 1)
    assert result.max_drawdown == worst


def test_the_synthetic_market_exercises_every_rule() -> None:
    """Guards the fixture: if a case stops occurring, the agreement test proves less."""
    bars, universe = _market()
    runner = WalkForwardRunner(CAL, _Prices(bars), SqlSurvivorshipEligibilityProvider(universe))
    result = runner.run(START, END, CAPITAL)
    selected = {sid for r in result.rebalances for sid in r.selected}
    reasons = {o.reason for o in result.closed_orders}
    assert any(t.partial for t in result.trades)  # thin turnover
    assert any(t.delay_sessions > 0 and t.side == "SELL" for t in result.trades)  # gap retry
    assert {"superseded", "expired"} <= reasons
    first_buy = {sid: next(t for t in result.trades if t.security_id == sid) for sid in GAPS}
    assert first_buy[41].order_date == JUNE_F and first_buy[41].delay_sessions == 4
    assert first_buy[42].order_date > JUNE_F  # the June buy expired; a later plan bought it
    assert any(o.security_id == 42 and o.reason == "expired" for o in result.closed_orders)
    assert 30 not in selected and 31 not in selected  # fund unit, BSE-only
    assert any(sid % 4 == 0 for sid in selected)  # a dual-listed name is held
    assert SPLIT_SID in {t.security_id for t in result.trades}
    late = [r for r in result.rebalances if 33 in r.selected]
    assert all(r.decision_date >= date(2023, 6, 1) for r in late)
    assert result.rebalances[0].scored_count < len(universe)
