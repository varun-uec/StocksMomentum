"""Score history marks methodology breaks (ADR-014 §11)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from momentum25.application.use_cases.stocks import GetStockHistory
from momentum25.domain.value_objects.results import ScorePoint


def _point(day: int, methodology: str | None) -> ScorePoint:
    return ScorePoint(date(2026, 10, day), 1, Decimal(1), Decimal(1), methodology)


class _Securities:
    async def get_by_symbol(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(id=7)


class _Strategies:
    async def get_for_workspace(self, name: str, config_hash: str | None) -> SimpleNamespace:
        return SimpleNamespace(id=1)


class _Runs:
    async def score_history(self, strategy_id: int, security_id: int, limit: int) -> list:
        # Newest first, as the repository returns them.
        return [_point(20, "i3e2"), _point(19, "i3e2"), _point(16, "i2e1"), _point(15, None)]


async def test_a_point_breaks_where_the_methodology_changes() -> None:
    use_case = GetStockHistory(_Securities(), _Runs(), _Strategies())  # type: ignore[arg-type]
    history = await use_case.execute("X", "s", 90)
    breaks = [(p.run_date.day, p.methodology_break) for p in history.score_history]
    # 19 (engine v2) follows 16 (engine v1); 16 follows an unstamped run.
    assert breaks == [(20, False), (19, True), (16, True), (15, False)]
