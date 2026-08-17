"""One rebalance step: equal-weight targets, turnover, and transaction costs.

Brief §4 (equal weight), §7 (30bps per buy/sell on traded notional). Fill
timing (decide close t-1, fill open t) is an execution-layer concern handled
by the caller — this module only prices the trades it is given.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

COST_BPS = Decimal("30") / Decimal("10000")


@dataclass(frozen=True, slots=True)
class Trade:
    """A single-security trade; positive notional is a buy, negative a sell."""

    security_id: int
    notional: Decimal


@dataclass(frozen=True, slots=True)
class RebalanceStep:
    """Trades required for one rebalance and their total transaction cost."""

    trades: tuple[Trade, ...]
    total_cost: Decimal


def plan_equal_weight_rebalance(
    target_holdings: frozenset[int],
    current_positions: dict[int, Decimal],
    portfolio_value: Decimal,
) -> RebalanceStep:
    """Compute trades to move ``current_positions`` to equal weight.

    Targets ``target_holdings`` and prices the brief §7 cost (30bps on each
    trade's notional). Securities not in ``target_holdings`` but currently
    held are sold in full.
    """
    if not target_holdings:
        target_value = Decimal(0)
    else:
        target_value = portfolio_value / Decimal(len(target_holdings))

    all_ids = set(target_holdings) | set(current_positions)
    trades: list[Trade] = []
    for sid in sorted(all_ids):
        current = current_positions.get(sid, Decimal(0))
        target = target_value if sid in target_holdings else Decimal(0)
        delta = target - current
        if delta != 0:
            trades.append(Trade(security_id=sid, notional=delta))

    total_cost = sum((abs(t.notional) * COST_BPS for t in trades), Decimal(0))
    return RebalanceStep(trades=tuple(trades), total_cost=total_cost)
