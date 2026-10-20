"""Security identity continuity (R3-B-31, IMPLEMENTATION_SPEC §4, owner decision S-5).

A link says the predecessor row's history continues under the successor row
from ``effective_date``, the first session traded under the successor.
``ratio`` is successor shares per predecessor share, so a predecessor price
in successor terms is ``price / ratio``.

Links come only from an owner-supplied file backed by authoritative exchange
evidence. Nothing here infers one. A link applies only when the predecessor's
last bar is dated before ``effective_date`` and the successor has no bar
before it. Without an applicable link, a security whose bars stop is a
non-trading holding, never a guessed rename.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar


@dataclass(frozen=True, slots=True)
class IdentityLink:
    """One verified rename."""

    predecessor_id: int
    successor_id: int
    effective_date: date
    ratio: Decimal
    evidence_source: str
    evidence_reference: str

    @property
    def last_predecessor_day(self) -> date:
        """The last day the predecessor can have a bar."""
        return self.effective_date - timedelta(days=1)


class IdentityLinks:
    """A validated set of links: one per predecessor and per successor, no cycles."""

    def __init__(self, links: Iterable[IdentityLink] = ()) -> None:
        """Validate ``links``; raise ``ValueError`` on any inconsistency."""
        self._by_predecessor: dict[int, IdentityLink] = {}
        self._by_successor: dict[int, IdentityLink] = {}
        for link in links:
            if link.predecessor_id == link.successor_id:
                raise ValueError(f"security {link.predecessor_id} is linked to itself")
            if link.ratio <= 0:
                raise ValueError(f"link {link.predecessor_id}: ratio must be positive")
            if not link.evidence_source.strip() or not link.evidence_reference.strip():
                raise ValueError(f"link {link.predecessor_id}: evidence is required")
            if link.predecessor_id in self._by_predecessor:
                raise ValueError(f"security {link.predecessor_id} has two successors")
            if link.successor_id in self._by_successor:
                raise ValueError(f"security {link.successor_id} has two predecessors")
            self._by_predecessor[link.predecessor_id] = link
            self._by_successor[link.successor_id] = link
        for start in self._by_predecessor:
            seen, sid = {start}, start
            while (nxt := self._by_predecessor.get(sid)) is not None:
                sid = nxt.successor_id
                if sid in seen:
                    raise ValueError(f"identity links form a cycle through security {sid}")
                seen.add(sid)

    def __iter__(self) -> Iterator[IdentityLink]:
        """The links in predecessor order."""
        return iter(sorted(self._by_predecessor.values(), key=lambda link: link.predecessor_id))

    def __len__(self) -> int:
        """The number of links."""
        return len(self._by_predecessor)

    def successor_of(self, security_id: int) -> IdentityLink | None:
        """The link out of ``security_id``, if any."""
        return self._by_predecessor.get(security_id)

    def predecessor_of(self, security_id: int) -> IdentityLink | None:
        """The link into ``security_id``, if any."""
        return self._by_successor.get(security_id)

    def applicable(
        self,
        first_bar: Mapping[int, date | None],
        last_bar: Mapping[int, date | None],
    ) -> tuple[IdentityLinks, tuple[IdentityLink, ...]]:
        """Split into the links the bars allow and the ones they contradict.

        ``first_bar`` and ``last_bar`` give each security's first and last bar
        date (``None``: no bars). A contradicted link is reported, never applied.
        """
        kept, rejected = [], []
        for link in self:
            last = last_bar.get(link.predecessor_id)
            first = first_bar.get(link.successor_id)
            if (last is None or last < link.effective_date) and (
                first is None or first >= link.effective_date
            ):
                kept.append(link)
            else:
                rejected.append(link)
        return IdentityLinks(kept), tuple(rejected)

    def history(self, security_id: int, as_of: date) -> list[tuple[IdentityLink, Decimal]]:
        """The predecessors whose bars continue ``security_id``'s history on ``as_of``.

        Newest first, each with the cumulative ratio that converts its prices to
        ``security_id``'s shares. A link counts only once ``as_of`` reaches its
        effective date: before it, the predecessor is the live identity.
        """
        chain, ratio, sid = [], Decimal(1), security_id
        while (link := self._by_successor.get(sid)) is not None and link.effective_date <= as_of:
            ratio *= link.ratio
            chain.append((link, ratio))
            sid = link.predecessor_id
        return chain


def in_successor_terms(bars: Iterable[OHLCVBar], ratio: Decimal) -> list[OHLCVBar]:
    """Predecessor bars restated per successor share: prices ÷ ratio, volume × ratio.

    Adjusted prices are ``raw × adj_factor`` and adjusted volume is
    ``raw / adj_factor``, so dividing the factor by ``ratio`` does both.
    """
    return [
        replace(
            bar,
            adj_factor=bar.adj_factor / ratio,
            adj_close=None if bar.adj_close is None else bar.adj_close / ratio,
        )
        for bar in bars
    ]


async def with_history(
    own: list[OHLCVBar],
    links: IdentityLinks,
    security_id: int,
    as_of: date,
    limit: int,
    fetch: Callable[[int, date, int], Awaitable[list[OHLCVBar]]],
) -> list[OHLCVBar]:
    """``own`` bars extended back through the linked predecessors, up to ``limit`` bars.

    ``fetch(security_id, last_day, count)`` returns a security's last ``count``
    bars dated on or before ``last_day``, ascending.
    """
    bars = own
    for link, ratio in links.history(security_id, as_of):
        if len(bars) >= limit:
            break
        older = await fetch(link.predecessor_id, link.last_predecessor_day, limit - len(bars))
        bars = in_successor_terms(older, ratio) + bars
    return bars
