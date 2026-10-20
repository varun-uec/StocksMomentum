"""Golden tests for sloped drawing alerts through the evaluator (ADR-013 line amendment).

The invariant: the alert compares each adjusted close with the adjusted line the
chart draws, both in the current basis. Each anchor's traded price takes its own
date's factor. The evaluator reads the frozen snapshot only; it has no access to
the live drawing document.

Base case, before any corporate action: a ray through (session 2, 100) and
(session 4, 110) rises 5 a session, so its level on session i is 100 + 5(i - 2).
Closes sit 1 below the line until session 10, which closes at 142 (line 140).
Every case below is that chart, re-expressed under a corporate action. The
first close cross above is always session 10.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from momentum25.application.dto.market_data import (
    AdjustmentStepDTO,
    OHLCVBarDTO,
    SecurityOHLCVDTO,
)
from momentum25.application.use_cases.alerts import EvaluateAlerts
from momentum25.domain.entities.alert import (
    Alert,
    DrawingAlert,
    DrawingAnchor,
    Firing,
    LineKind,
    SeriesPoint,
    first_line_firing,
    line_levels,
)

D = Decimal
SESSIONS = [d for d in (date(2026, 8, 3) + timedelta(days=n) for n in range(28)) if d.weekday() < 5]
ARMED = SESSIONS[5]
CROSS = 10


def _line(i: int) -> Decimal:
    return D(100) + 5 * (i - 2)


# The chart's closes (current basis): 1 below the line, then 142 on session 10, then above.
CHART_CLOSES = [_line(i) - 1 if i < CROSS else _line(i) + 2 for i in range(len(SESSIONS))]


def _factors(ex_index: int | None, ratio: Decimal) -> list[Decimal]:
    """Each session's backward factor for one action going ex on ``ex_index``."""
    return [ratio if ex_index is not None and i < ex_index else D(1) for i in range(len(SESSIONS))]


def _steps(factors: list[Decimal]) -> list[AdjustmentStepDTO]:
    steps: list[AdjustmentStepDTO] = []
    for day, factor in zip(SESSIONS, factors, strict=True):
        if steps and steps[-1].factor == factor:
            steps[-1] = AdjustmentStepDTO(until=day, factor=factor)
        else:
            steps.append(AdjustmentStepDTO(until=day, factor=factor))
    return steps


class _Prices:
    """The chart API's daily series: adjusted closes and the schedule that made them."""

    def __init__(self, closes: list[Decimal], factors: list[Decimal], count: int | None = None):
        n = count or len(SESSIONS)
        self.dto = SecurityOHLCVDTO(
            symbol="LINE",
            interval="1D",
            data_version="v1",
            bars=[
                OHLCVBarDTO(date=d, open=c, high=c, low=c, close=c, volume=1)
                for d, c in zip(SESSIONS[:n], closes[:n], strict=True)
            ],
            adjustments=_steps(factors),
        )

    async def execute(self, symbol: str, **_: Any) -> SecurityOHLCVDTO:
        return self.dto


class _Alerts:
    """One alert; `fire` is the one-shot, revision-guarded transition of the real store."""

    def __init__(self, alert: Alert) -> None:
        self.alert = alert
        self.firings: list[Firing] = []

    async def list_active(self) -> list[Alert]:
        return [self.alert] if self.alert.status == "active" else []

    async def fire(
        self, alert_id: int, firing: Firing, data_version: str, revision: int = 1
    ) -> bool:
        if self.alert.status != "active" or revision != self.alert.revision:
            return False
        self.alert = replace(self.alert, status="triggered")
        self.firings.append(firing)
        return True


def _alert(kind: str, traded: list[tuple[int, Decimal]], condition: str = "crosses_above") -> Alert:
    return Alert(
        id=1,
        symbol="LINE",
        source="close",
        interval="1D",
        condition=condition,  # type: ignore[arg-type]
        threshold=traded[0][1],
        armed_after=ARMED,
        drawing=DrawingAlert(
            id="d1",
            kind=kind,  # type: ignore[arg-type]
            revision=1,
            points=tuple(DrawingAnchor(SESSIONS[i], p) for i, p in traded),
        ),
    )


async def _evaluate(alert: Alert, prices: _Prices) -> tuple[_Alerts, int]:
    store = _Alerts(alert)
    result = await EvaluateAlerts(store, prices, None).execute()  # type: ignore[arg-type]
    return store, result.fired


async def test_the_base_chart_fires_on_the_first_close_above_the_ray() -> None:
    store, fired = await _evaluate(
        _alert("ray", [(2, D(100)), (4, D(110))]), _Prices(CHART_CLOSES, _factors(None, D(1)))
    )
    assert (fired, store.firings) == (1, [Firing(SESSIONS[CROSS], D(142))])


@pytest.mark.parametrize("ratio", [D("0.5"), D("0.75")], ids=["1:2 split", "1:3 bonus"])
async def test_an_action_between_the_anchors_keeps_the_drawn_line(ratio: Decimal) -> None:
    """Ex-date on session 3: the first anchor was traded in the old basis, at 100 / ratio."""
    factors = _factors(3, ratio)
    traded = [(2, D(100) / ratio), (4, D(110))]
    store, _ = await _evaluate(_alert("ray", traded), _Prices(CHART_CLOSES, factors))
    assert store.firings == [Firing(SESSIONS[CROSS], D(142))]


@pytest.mark.parametrize("ratio", [D("0.5"), D("0.75")], ids=["1:2 split", "1:3 bonus"])
async def test_an_action_after_arming_rescales_the_line_with_the_closes(ratio: Decimal) -> None:
    """Ex-date on session 8, after arming (5) and before the cross (10).

    Both anchors and every close before session 8 take the new factor, so the
    whole chart, line included, is the base chart × ratio, and it fires on the
    same session at the scaled close.
    """
    factors = _factors(8, ratio)
    closes = [c * ratio for c in CHART_CLOSES]
    store, _ = await _evaluate(_alert("ray", [(2, D(100)), (4, D(110))]), _Prices(closes, factors))
    assert store.firings == [Firing(SESSIONS[CROSS], D(142) * ratio)]


async def test_an_ex_date_between_two_sessions_is_not_a_cross_and_does_not_hide_one() -> None:
    """The ex-date is the crossing session itself: the raw print halves, the adjusted one does not.

    Comparing traded closes would read the raw drop from 139 to 71 as a cross
    below. In the chart's basis the series is the base chart × 0.5: a cross
    above on session 10, and never a cross below.
    """
    factors = _factors(CROSS, D("0.5"))
    closes = [c * D("0.5") for c in CHART_CLOSES]
    above, _ = await _evaluate(_alert("ray", [(2, D(100)), (4, D(110))]), _Prices(closes, factors))
    below, _ = await _evaluate(
        _alert("ray", [(2, D(100)), (4, D(110))], "crosses_below"), _Prices(closes, factors)
    )
    assert above.firings == [Firing(SESSIONS[CROSS], D(71))]
    assert below.firings == []


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("ray", Firing(SESSIONS[CROSS], D(142))),
        ("extended", Firing(SESSIONS[CROSS], D(142))),
        # A trendline ends on its second anchor (session 4), before arming: nothing to watch.
        ("trendline", None),
    ],
)
async def test_each_line_kind_watches_its_own_sessions(kind: str, expected: Firing | None) -> None:
    store, _ = await _evaluate(
        _alert(kind, [(2, D(100)), (4, D(110))]), _Prices(CHART_CLOSES, _factors(None, D(1)))
    )
    assert store.firings == ([expected] if expected else [])


async def test_a_trendline_spanning_the_cross_fires_inside_its_span_only() -> None:
    inside, _ = await _evaluate(
        _alert("trendline", [(2, D(100)), (12, D(150))]),
        _Prices(CHART_CLOSES, _factors(None, D(1))),
    )
    short, _ = await _evaluate(
        _alert("trendline", [(2, D(100)), (9, D(135))]), _Prices(CHART_CLOSES, _factors(None, D(1)))
    )
    assert inside.firings == [Firing(SESSIONS[CROSS], D(142))]
    assert short.firings == []


async def test_evaluation_is_idempotent_and_reads_only_the_frozen_snapshot() -> None:
    alert = _alert("ray", [(2, D(100)), (4, D(110))])
    prices = _Prices(CHART_CLOSES, _factors(None, D(1)))
    store = _Alerts(alert)
    evaluate = EvaluateAlerts(store, prices, None)  # type: ignore[arg-type]
    first, second = await evaluate.execute(), await evaluate.execute()
    assert (first.fired, second.fired, second.evaluated) == (1, 0, 0)
    assert store.firings == [Firing(SESSIONS[CROSS], D(142))]
    # A stale revision (the rule was edited meanwhile) never fires the old rule.
    stale = _Alerts(replace(alert, revision=3))
    assert await stale.fire(1, Firing(SESSIONS[CROSS], D(142)), "v1", revision=2) is False


async def test_no_look_ahead_a_firing_needs_only_bars_up_to_it() -> None:
    """Every stored prefix gives the same answer as the whole series, or no firing yet."""
    alert = _alert("ray", [(2, D(100)), (4, D(110))])
    for n in range(5, len(SESSIONS) + 1):
        store, _ = await _evaluate(alert, _Prices(CHART_CLOSES, _factors(None, D(1)), count=n))
        assert store.firings == ([Firing(SESSIONS[CROSS], D(142))] if n > CROSS else []), n


def test_no_look_ahead_a_level_never_depends_on_later_sessions() -> None:
    anchors = ((SESSIONS[2], D(100)), (SESSIONS[4], D(110)))
    kind: LineKind
    for kind in ("trendline", "ray", "extended"):
        full = line_levels(kind, anchors, SESSIONS)
        for n in range(5, len(SESSIONS)):
            assert line_levels(kind, anchors, SESSIONS[:n]) == full[:n]
    # A wild later close never changes an earlier firing.
    points = [SeriesPoint(d, c) for d, c in zip(SESSIONS, CHART_CLOSES, strict=True)]
    levels = line_levels("ray", anchors, SESSIONS)
    shocked = [*points[:-1], SeriesPoint(SESSIONS[-1], D(0))]
    assert first_line_firing("crosses_above", ARMED, shocked, levels) == first_line_firing(
        "crosses_above", ARMED, points, levels
    )
