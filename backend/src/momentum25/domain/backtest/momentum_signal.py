"""3/6/12-month composite momentum score — brief §2.

No skip-month. Equal weights (w3 = w6 = w12 = 1/3). All prices must already
be adjusted for splits, bonuses, and dividends — this module does not adjust
prices itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_WEIGHT = Decimal("1") / Decimal("3")


@dataclass(frozen=True, slots=True)
class MomentumSignal:
    """Composite momentum score for one security as of one decision date."""

    security_id: int
    return_3m: Decimal
    return_6m: Decimal
    return_12m: Decimal
    composite_score: Decimal


def compute_return(price_t: Decimal, price_lookback: Decimal) -> Decimal:
    """Return ``price_t / price_lookback - 1``.

    Raises:
        ValueError: if either price is not strictly positive — a
            non-positive adjusted price is a data-integrity fault, not a
            valid input to score.
    """
    if price_t <= 0 or price_lookback <= 0:
        raise ValueError(
            f"prices must be positive: price_t={price_t}, price_lookback={price_lookback}"
        )
    return price_t / price_lookback - 1


def compute_momentum_signal(
    security_id: int,
    price_t: Decimal,
    price_3m_ago: Decimal,
    price_6m_ago: Decimal,
    price_12m_ago: Decimal,
) -> MomentumSignal:
    """Compute the brief §2 composite score for one security.

    Every return is measured against the same decision-date price ``price_t``
    (last adjusted close before the rebalance date). No information dated on
    or after the decision date may enter this calculation (brief §9).
    """
    r3 = compute_return(price_t, price_3m_ago)
    r6 = compute_return(price_t, price_6m_ago)
    r12 = compute_return(price_t, price_12m_ago)
    score = _WEIGHT * r3 + _WEIGHT * r6 + _WEIGHT * r12
    return MomentumSignal(
        security_id=security_id,
        return_3m=r3,
        return_6m=r6,
        return_12m=r12,
        composite_score=score,
    )
