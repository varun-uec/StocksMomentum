"""Unit tests for domain.backtest — hand-computed against handoff/brief.md."""

from dataclasses import replace
from decimal import Decimal

import pytest

from momentum25.domain.backtest.eligibility import EligibilityFacts, is_eligible
from momentum25.domain.backtest.momentum_signal import (
    compute_momentum_signal,
    compute_return,
)
from momentum25.domain.backtest.portfolio_step import (
    COST_BPS,
    plan_equal_weight_rebalance,
)
from momentum25.domain.backtest.rebalance import (
    BUFFER_RANK,
    PORTFOLIO_SIZE,
    RankedSignal,
    rank_signals,
    select_portfolio,
)


def test_compute_return_hand_calculated():
    # 120 -> 100 is a -1/6 return, exactly.
    assert compute_return(Decimal(100), Decimal(120)) == Decimal(100) / Decimal(120) - 1


def test_compute_return_rejects_non_positive_price():
    with pytest.raises(ValueError):
        compute_return(Decimal(100), Decimal(0))


def test_composite_score_equal_weight_hand_calculated():
    # price now = 110; 3m ago = 100 (+10%); 6m ago = 100 (+10%); 12m ago = 55 (+100%).
    sig = compute_momentum_signal(
        security_id=1,
        price_t=Decimal(110),
        price_3m_ago=Decimal(100),
        price_6m_ago=Decimal(100),
        price_12m_ago=Decimal(55),
    )
    expected = (Decimal("0.1") + Decimal("0.1") + Decimal(1)) / 3
    assert sig.composite_score == expected


def test_eligibility_requires_all_conditions():
    base = EligibilityFacts(
        security_id=1,
        listing_days_as_of_decision_date=300,
        is_t2t=False,
        is_under_surveillance=False,
        in_nifty_500=True,
    )
    assert is_eligible(base)
    assert not is_eligible(replace(base, is_t2t=True))
    assert not is_eligible(replace(base, is_under_surveillance=True))
    assert not is_eligible(replace(base, listing_days_as_of_decision_date=100))
    assert not is_eligible(replace(base, in_nifty_500=False))


def _signal(security_id: int, score: str, r12: str = "0", r6: str = "0", r3: str = "0") -> object:
    from momentum25.domain.backtest.momentum_signal import MomentumSignal

    return MomentumSignal(
        security_id=security_id,
        return_3m=Decimal(r3),
        return_6m=Decimal(r6),
        return_12m=Decimal(r12),
        composite_score=Decimal(score),
    )


def test_rank_signals_tie_break_by_12m_then_6m_then_3m():
    # Three securities tie on composite_score; brief tie-break is 12M, then 6M, then 3M.
    a = _signal(1, "0.10", r12="0.30", r6="0.10", r3="0.05")
    b = _signal(2, "0.10", r12="0.30", r6="0.20", r3="0.01")
    c = _signal(3, "0.10", r12="0.10", r6="0.90", r3="0.90")
    ranked = rank_signals([a, b, c])
    ranks_by_id = {r.signal.security_id: r.rank for r in ranked}
    # b beats a on 6M despite equal 12M and score; c loses on 12M despite winning 6M/3M.
    assert ranks_by_id[2] == 1
    assert ranks_by_id[1] == 2
    assert ranks_by_id[3] == 3


def test_select_portfolio_buffer_keeps_existing_holding_outside_top_30():
    # Security 99 currently held, ranked 40 (inside buffer 45) -> kept.
    # Security 100 currently held, ranked 46 (outside buffer) -> dropped.
    # A fresh non-holding ranked 5 -> added.
    ranked = [RankedSignal(signal=_signal(99, "0"), rank=40)]
    ranked.append(RankedSignal(signal=_signal(100, "0"), rank=46))
    ranked.append(RankedSignal(signal=_signal(5, "0"), rank=5))
    result = select_portfolio(ranked, current_holdings=frozenset({99, 100}))
    assert 99 in result  # inside buffer -> kept despite rank > 30
    assert 100 not in result  # outside buffer -> dropped
    assert 5 in result  # top-30 rank -> added
    assert BUFFER_RANK == 45
    assert PORTFOLIO_SIZE == 30


def test_select_portfolio_hard_cutoff_would_be_a_brief_violation():
    # Regression guard: a holding ranked 31-45 must survive. If someone
    # "simplifies" select_portfolio to `rank <= 30`, this goes red.
    ranked = [RankedSignal(signal=_signal(7, "0"), rank=35)]
    result = select_portfolio(ranked, current_holdings=frozenset({7}))
    assert 7 in result


def test_plan_equal_weight_rebalance_cost_hand_calculated():
    # Move from {A: 100} to equal-weight {A, B} on portfolio value 200.
    # Target each = 100. A: delta 0 (no trade). B: delta +100 (buy).
    step = plan_equal_weight_rebalance(
        target_holdings=frozenset({1, 2}),
        current_positions={1: Decimal(100)},
        portfolio_value=Decimal(200),
    )
    trades_by_id = {t.security_id: t.notional for t in step.trades}
    assert 1 not in trades_by_id  # no-op trade omitted
    assert trades_by_id[2] == Decimal(100)
    assert step.total_cost == Decimal(100) * COST_BPS
    assert Decimal("0.003") == COST_BPS


def test_plan_equal_weight_rebalance_sells_dropped_holding_in_full():
    step = plan_equal_weight_rebalance(
        target_holdings=frozenset({1}),
        current_positions={1: Decimal(50), 2: Decimal(50)},
        portfolio_value=Decimal(100),
    )
    trades_by_id = {t.security_id: t.notional for t in step.trades}
    assert trades_by_id[2] == Decimal(-50)
