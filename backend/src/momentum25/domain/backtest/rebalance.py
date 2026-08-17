"""Ranking, tie-break, and buffered rebalance selection — brief §3, §6.

Portfolio size N=30, buffer 1.5x (45). Existing holdings survive down to
rank 45; new entries need rank <=30. This asymmetric band is intentional
(brief §6) — it is not a bug to "fix" into a hard top-30 cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass

from momentum25.domain.backtest.momentum_signal import MomentumSignal

PORTFOLIO_SIZE = 30
BUFFER_MULTIPLIER = 1.5
BUFFER_RANK = int(PORTFOLIO_SIZE * BUFFER_MULTIPLIER)  # 45


@dataclass(frozen=True, slots=True)
class RankedSignal:
    """A momentum signal paired with its 1-based rank in the universe."""

    signal: MomentumSignal
    rank: int


def rank_signals(signals: list[MomentumSignal]) -> list[RankedSignal]:
    """Sort desc by composite score; ties broken by 12M, then 6M, then 3M return.

    security_id is not part of the sort key — if three returns are all equal,
    the result is a genuine tie the brief does not resolve. That case is
    flagged as a judgment call in builder-notes rather than silently broken
    by an arbitrary id-ordering tiebreaker.
    """
    ordered = sorted(
        signals,
        key=lambda s: (
            -s.composite_score,
            -s.return_12m,
            -s.return_6m,
            -s.return_3m,
        ),
    )
    return [RankedSignal(signal=s, rank=i) for i, s in enumerate(ordered, start=1)]


def select_portfolio(
    ranked: list[RankedSignal], current_holdings: frozenset[int]
) -> frozenset[int]:
    """Apply the buffer/hysteresis rule to produce the next holding set.

    - A current holding is kept if its rank <= BUFFER_RANK (45).
    - A non-holding is added if its rank <= PORTFOLIO_SIZE (30).
    - Ranked-out securities (not in `ranked`, e.g. failed eligibility) are
      never held, regardless of prior membership.
    """
    rank_by_security = {r.signal.security_id: r.rank for r in ranked}

    kept = {
        sid
        for sid in current_holdings
        if rank_by_security.get(sid, BUFFER_RANK + 1) <= BUFFER_RANK
    }
    candidates = [
        r for r in ranked if r.rank <= PORTFOLIO_SIZE and r.signal.security_id not in kept
    ]
    candidates.sort(key=lambda r: r.rank)

    slots_free = PORTFOLIO_SIZE - len(kept)
    added = {c.signal.security_id for c in candidates[: max(slots_free, 0)]}

    return frozenset(kept | added)
