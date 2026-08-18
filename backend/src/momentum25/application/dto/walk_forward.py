"""Walk-forward backtest DTOs — stable API contract for the backtest surface.

These Pydantic models are the boundary between the walk-forward runner and the
transport layer. Two rules from ``handoff/`` are carried in the shapes below
and must survive any future edit:

* ``benchmark_return`` never travels without ``benchmark_label`` next to it
  (``brief-addendum-approximations.md``). Both are optional together: the
  runner returns ``None`` for both when no benchmark provider was bound.
* ``survivorship_warning`` is always present. The universe provider's
  membership and surveillance facts are stub, and every surface that shows a
  backtest result must show that caveat
  (``brief-addendum-loop3.md`` Item 13).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from momentum25.application.use_cases.walk_forward import (
    RebalanceRecord,
    TradeRecord,
    WalkForwardResult,
)


class BacktestRequest(BaseModel):
    """Request to run a walk-forward backtest over a date range."""

    start: date
    end: date
    initial_capital: Decimal = Field(default=Decimal("1000000"), gt=0)


class TradeDTO(BaseModel):
    """One fill in the trade log."""

    security_id: int
    side: str
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal
    fill_date: date
    cost: Decimal


class RebalanceDTO(BaseModel):
    """One rebalance in the log."""

    decision_date: date
    fill_date: date
    universe_size: int
    eligible_count: int
    selected: list[int]
    trade_count: int
    total_cost: Decimal
    nav_pre_cost: Decimal


class BacktestResponse(BaseModel):
    """Full walk-forward backtest result."""

    start: date
    end: date
    initial_capital: Decimal
    final_nav: Decimal
    total_return: Decimal
    benchmark_return: Decimal | None
    benchmark_label: str | None
    rebalance_count: int
    trade_count: int
    rebalances: list[RebalanceDTO]
    trades: list[TradeDTO]
    survivorship_warning: str


def to_trade_dto(record: TradeRecord) -> TradeDTO:
    """Map one trade record to its DTO."""
    return TradeDTO(
        security_id=record.security_id,
        side=record.side,
        quantity=record.quantity,
        fill_price=record.fill_price,
        notional=record.notional,
        fill_date=record.fill_date,
        cost=record.cost,
    )


def to_rebalance_dto(record: RebalanceRecord) -> RebalanceDTO:
    """Map one rebalance record to its DTO."""
    return RebalanceDTO(
        decision_date=record.decision_date,
        fill_date=record.fill_date,
        universe_size=record.universe_size,
        eligible_count=record.eligible_count,
        selected=list(record.selected),
        trade_count=len(record.trades),
        total_cost=record.total_cost,
        nav_pre_cost=record.nav_pre_cost,
    )


def to_backtest_response(
    result: WalkForwardResult, start: date, end: date, survivorship_warning: str
) -> BacktestResponse:
    """Map a runner result to the API response."""
    return BacktestResponse(
        start=start,
        end=end,
        initial_capital=result.initial_capital,
        final_nav=result.final_nav,
        total_return=result.total_return,
        benchmark_return=result.benchmark_return,
        benchmark_label=result.benchmark_label,
        rebalance_count=len(result.rebalances),
        trade_count=len(result.trades),
        rebalances=[to_rebalance_dto(r) for r in result.rebalances],
        trades=[to_trade_dto(t) for t in result.trades],
        survivorship_warning=survivorship_warning,
    )
