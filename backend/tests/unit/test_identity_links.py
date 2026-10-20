"""Identity links (R3-B-31): validation, the bar check and history chains."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.identity import (
    IdentityLink,
    IdentityLinks,
    in_successor_terms,
    with_history,
)

E1, E2 = date(2023, 6, 19), date(2024, 1, 15)


def _link(pred: int, succ: int, eff: date = E1, ratio: str = "1") -> IdentityLink:
    return IdentityLink(pred, succ, eff, Decimal(ratio), "NSE symbol change", "file sha256 ab")


@pytest.mark.parametrize(
    ("links", "message"),
    [
        ([_link(1, 1)], "linked to itself"),
        ([_link(1, 2, ratio="0")], "ratio must be positive"),
        ([IdentityLink(1, 2, E1, Decimal(1), "", "x")], "evidence is required"),
        ([_link(1, 2), _link(1, 3)], "two successors"),
        ([_link(1, 3), _link(2, 3)], "two predecessors"),
        ([_link(1, 2), _link(2, 1)], "cycle"),
    ],
)
def test_an_inconsistent_link_set_is_refused(links, message) -> None:
    with pytest.raises(ValueError, match=message):
        IdentityLinks(links)


def test_a_link_the_bars_contradict_is_rejected_not_applied() -> None:
    links = IdentityLinks([_link(1, 2), _link(3, 4), _link(5, 6)])
    first = {2: E1, 4: date(2023, 6, 1), 6: E1}
    last = {1: date(2023, 6, 16), 3: date(2023, 6, 16), 5: E1}
    applicable, rejected = links.applicable(first, last)
    # 3 -> 4: the successor traded before the effective date. 5 -> 6: the
    # predecessor traded on it. Both are reported and neither applies.
    assert [link.predecessor_id for link in applicable] == [1]
    assert [link.predecessor_id for link in rejected] == [3, 5]


def test_history_follows_a_chain_newest_first_with_cumulative_ratios() -> None:
    links = IdentityLinks([_link(1, 2, E1, "2"), _link(2, 3, E2, "5")])
    chain = links.history(3, E2)
    assert [(link.predecessor_id, ratio) for link, ratio in chain] == [
        (2, Decimal(5)),
        (1, Decimal(10)),
    ]
    # Before a link's effective date the predecessor is still the live identity.
    assert links.history(3, date(2024, 1, 12)) == []
    assert [link.predecessor_id for link, _ in links.history(2, E2)] == [1]


def _bar(day: date, close: str) -> OHLCVBar:
    c = Decimal(close)
    return OHLCVBar(date=day, open=c, high=c, low=c, close=c, volume=1000, adj_close=c)


def test_predecessor_bars_are_restated_per_successor_share() -> None:
    [bar] = in_successor_terms([_bar(date(2023, 6, 16), "200")], Decimal(2))
    assert bar.close == Decimal(200)  # the raw print is kept
    assert bar.close * bar.adj_factor == Decimal(100)  # adjusted price ÷ ratio
    assert bar.volume / bar.adj_factor == Decimal(2000)  # adjusted volume × ratio
    assert bar.adj_close == Decimal(100)


async def test_with_history_prepends_only_the_bars_still_needed() -> None:
    links = IdentityLinks([_link(1, 2, E1, "2")])
    stored = {
        1: [_bar(date(2023, 6, d), str(100 + d)) for d in (13, 14, 15, 16)],
        2: [_bar(date(2023, 6, d), "60") for d in (19, 20)],
    }
    asked = []

    async def fetch(sid: int, last_day: date, count: int) -> list[OHLCVBar]:
        asked.append((sid, last_day, count))
        return [b for b in stored[sid] if b.date <= last_day][-count:]

    bars = await with_history(stored[2], links, 2, date(2023, 6, 20), 5, fetch)
    assert asked == [(1, date(2023, 6, 18), 3)]
    assert [b.date.day for b in bars] == [14, 15, 16, 19, 20]
    assert [b.close * b.adj_factor for b in bars[:3]] == [
        Decimal("57"),
        Decimal("57.5"),
        Decimal(58),
    ]
    # Before the effective date nothing is stitched.
    assert await with_history([], links, 2, date(2023, 6, 16), 5, fetch) == []
