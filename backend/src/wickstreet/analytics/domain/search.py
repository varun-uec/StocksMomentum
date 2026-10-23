"""Fund search order: a beginner sees the plan most people mean first.

The reader matches terms (``mf_data.domain.reads.search_terms``). This module
orders the matches: an exact code or ISIN, then current plans before historical
ones (independent audit A-07: a broad AMC query must not open on closed IDCW
series), then names that contain the whole query as one phrase, then Direct
Growth plans, then the longest NAV history (an AMC's flagship fund is usually its
oldest), then the name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NamedTuple

from wickstreet.mf_data.domain.reads import FundRecord, compact, search_terms


class Standing(NamedTuple):
    """What the snapshot knows about an active fund."""

    direct_growth: bool
    since: str


def ranked(
    query: str, found: Sequence[FundRecord], standing: Mapping[str, Standing]
) -> list[FundRecord]:
    """Order matches; ``standing`` holds the active funds among them."""
    exact = query.strip().upper()
    phrase = "".join(search_terms(query))

    def key(fund: FundRecord) -> tuple[bool, bool, bool, bool, str, str, str]:
        known = standing.get(fund.amfi_code)
        return (
            exact not in {fund.amfi_code, fund.isin_growth, fund.isin_reinvest},
            known is None,
            phrase not in compact(fund.nav_name or ""),
            not (known and known.direct_growth),
            known.since if known else "",
            fund.nav_name or "",
            fund.amfi_code,
        )

    return sorted(found, key=key)
