"""Walk-forward backtest DTOs — stable API contract for the backtest surface.

These Pydantic models are the boundary between the walk-forward runner and the
transport layer. Rules from ``docs/history/backtest-loop/`` are carried in the
shapes below and must survive any future edit:

* ``benchmark_return`` never travels without ``benchmark_label`` next to it
  (``brief-addendum-approximations.md``). Both are optional together: the
  runner returns ``None`` for both when no benchmark provider was bound.
* ``survivorship_warning`` is always present. The universe provider's
  membership and surveillance facts are stub, and every surface that shows a
  backtest result must show that caveat
  (``brief-addendum-loop3.md`` Item 13).
* Execution method v2 (``brief-addendum-execution-v2.md``): every result names
  its method version, policy, market data and build, reports the lower bound
  next to the return, and says that it is a simulation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from momentum25.application.use_cases.walk_forward import (
    NonTradingHolding,
    RebalanceRecord,
    TradeRecord,
    WalkForwardResult,
)
from momentum25.domain.backtest.execution import ClosedOrder
from momentum25.domain.value_objects.manifest import DataManifest

SIMULATION_NOTICE = (
    "Simulation on end-of-day data. Fills assume the session's opening price, capped at "
    "a share of the session's traded value; there is no order book. Sale proceeds fund "
    "buys in the same session. This is not evidence of investment performance."
)


class BacktestRequest(BaseModel):
    """Request to run a walk-forward backtest over a date range."""

    start: date
    end: date
    initial_capital: Decimal = Field(default=Decimal("1000000"), gt=0)


class TradeDTO(BaseModel):
    """One fill in the trade log. ``quantity`` and ``notional`` are signed: + buy, - sell."""

    security_id: int
    side: str
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal
    fill_date: date
    cost: Decimal
    order_date: date
    delay_sessions: int
    partial: bool
    participation: Decimal | None


class RebalanceDTO(BaseModel):
    """One rebalance in the log. Its trades include fills deferred past the fill date."""

    decision_date: date
    fill_date: date
    universe_size: int
    eligible_count: int
    scored_count: int
    selected: list[int]
    trade_count: int
    total_cost: Decimal
    nav_pre_cost: Decimal
    stale_marks: int
    buy_scale: Decimal


class ClosedOrderDTO(BaseModel):
    """An order that ended without filling in full."""

    security_id: int
    side: str
    order_date: date
    closed_on: date
    reason: str
    remaining_cash: Decimal
    remaining_shares: Decimal


class NonTradingHoldingDTO(BaseModel):
    """A holding with no bar for more than the policy's flag window at the end date."""

    security_id: int
    last_bar_date: date
    sessions_without_bar: int
    value: Decimal
    weight: Decimal
    identity_status: str


class BacktestProvenance(BaseModel):
    """What produced the result (ADR-014 §11)."""

    method_version: int
    execution_policy: dict[str, str | int | bool]
    market_data_version: str | None
    data_revision: int
    calendar_version: str
    build_id: str | None


class BacktestResponse(BaseModel):
    """Full walk-forward backtest result."""

    start: date
    end: date
    initial_capital: Decimal
    final_nav: Decimal
    total_return: Decimal
    cagr: Decimal | None
    max_drawdown: Decimal
    lower_bound_nav: Decimal | None
    lower_bound_return: Decimal | None
    benchmark_return: Decimal | None
    benchmark_label: str | None
    rebalance_count: int
    trade_count: int
    partial_fill_count: int
    deferred_fill_count: int
    rebalances: list[RebalanceDTO]
    trades: list[TradeDTO]
    closed_orders: list[ClosedOrderDTO]
    nontrading_holdings: list[NonTradingHoldingDTO]
    provenance: BacktestProvenance
    simulation_notice: str
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
        order_date=record.order_date,
        delay_sessions=record.delay_sessions,
        partial=record.partial,
        participation=record.participation,
    )


def to_rebalance_dto(record: RebalanceRecord) -> RebalanceDTO:
    """Map one rebalance record to its DTO."""
    return RebalanceDTO(
        decision_date=record.decision_date,
        fill_date=record.fill_date,
        universe_size=record.universe_size,
        eligible_count=record.eligible_count,
        scored_count=record.scored_count,
        selected=list(record.selected),
        trade_count=len(record.trades),
        total_cost=record.total_cost,
        nav_pre_cost=record.nav_pre_cost,
        stale_marks=record.stale_marks,
        buy_scale=record.buy_scale,
    )


def _closed(order: ClosedOrder) -> ClosedOrderDTO:
    return ClosedOrderDTO(
        security_id=order.security_id,
        side=order.side,
        order_date=order.order_date,
        closed_on=order.closed_on,
        reason=order.reason,
        remaining_cash=order.remaining_cash,
        remaining_shares=order.remaining_shares,
    )


def _nontrading(holding: NonTradingHolding) -> NonTradingHoldingDTO:
    return NonTradingHoldingDTO(
        security_id=holding.security_id,
        last_bar_date=holding.last_bar_date,
        sessions_without_bar=holding.sessions_without_bar,
        value=holding.value,
        weight=holding.weight,
        identity_status=holding.identity_status,
    )


def to_backtest_response(
    result: WalkForwardResult,
    start: date,
    end: date,
    survivorship_warning: str,
    manifest: DataManifest,
) -> BacktestResponse:
    """Map a runner result and the manifest of its data to the API response."""
    lower_return = (
        result.lower_bound_nav / result.initial_capital - 1
        if result.lower_bound_nav is not None and result.initial_capital
        else None
    )
    return BacktestResponse(
        start=start,
        end=end,
        initial_capital=result.initial_capital,
        final_nav=result.final_nav,
        total_return=result.total_return,
        cagr=result.cagr,
        max_drawdown=result.max_drawdown,
        lower_bound_nav=result.lower_bound_nav,
        lower_bound_return=lower_return,
        benchmark_return=result.benchmark_return,
        benchmark_label=result.benchmark_label,
        rebalance_count=len(result.rebalances),
        trade_count=len(result.trades),
        partial_fill_count=sum(1 for t in result.trades if t.partial),
        deferred_fill_count=sum(1 for t in result.trades if t.delay_sessions > 0),
        rebalances=[to_rebalance_dto(r) for r in result.rebalances],
        trades=[to_trade_dto(t) for t in result.trades],
        closed_orders=[_closed(o) for o in result.closed_orders],
        nontrading_holdings=[_nontrading(h) for h in result.nontrading_holdings],
        provenance=BacktestProvenance(
            method_version=result.method_version,
            execution_policy=result.execution_policy or {},
            market_data_version=manifest.market_data_version,
            data_revision=manifest.revision,
            calendar_version=manifest.calendar_version,
            build_id=manifest.build_id,
        ),
        simulation_notice=SIMULATION_NOTICE,
        survivorship_warning=survivorship_warning,
    )
