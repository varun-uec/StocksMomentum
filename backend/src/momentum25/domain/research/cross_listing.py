"""ISIN-based NSE/BSE cross-listing reconciliation (Phase 5.1) — pure domain logic.

A company listed on both exchanges must resolve to exactly *one* canonical
``Security``. The reconciliation key is the ISIN (the company's permanent
identity), never the ticker: tickers are exchange-local and collide across
exchanges for unrelated companies.

Rules (deterministic, no I/O):

1. **NSE is canonical.** Symbol, name and listing date of a cross-listed
   company are taken from the NSE master, so existing securities, runs and
   research artefacts keep their identity byte-for-byte.
2. An NSE instrument whose ISIN also appears in the BSE master is marked
   ``Exchange.BOTH``; otherwise ``Exchange.NSE``. No second record is created.
3. A BSE instrument whose ISIN is *not* in the NSE master is **BSE-only**.
   Admitting BSE-only names would enlarge the screening universe, which is a
   methodology change, not an engineering one — so it requires the caller to
   pass an explicit ``admit_bse_only_series`` whitelist (research-approved BSE
   group codes). The default is empty: BSE-only names are counted and reported
   but never silently admitted. There is no defensible way to derive an
   "equity" filter from the BSE bhavcopy alone — its groups mix equity, debt,
   ETFs, mutual-fund units and government securities under one instrument type.
4. A BSE-only name whose ticker is already used by a *different* ISIN on NSE is
   reported as a collision and excluded. Renaming it (e.g. a ``.BO`` suffix)
   would invent an identifier scheme the platform does not otherwise have.

Ordering of the result is by symbol so the output is reproducible regardless of
provider iteration order.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from momentum25.domain.ports.market_data import RawInstrument
from momentum25.domain.value_objects.types import Exchange


@dataclass(frozen=True, slots=True)
class CanonicalInstrument:
    """One company, one record, with the exchange(s) it trades on."""

    symbol: str
    name: str
    isin: str | None
    exchange: Exchange
    listing_date: date | None = None


@dataclass(frozen=True, slots=True)
class CrossListingReconciliation:
    """Outcome of reconciling an NSE and a BSE instrument master.

    ``bse_only_withheld`` and ``symbol_collisions`` are disclosed rather than
    dropped silently: they are the exact set of names the platform *knows about*
    but deliberately does not screen.
    """

    instruments: tuple[CanonicalInstrument, ...]
    cross_listed: int
    nse_only: int
    bse_only_admitted: int
    bse_only_withheld: tuple[str, ...]
    symbol_collisions: tuple[str, ...]


def _normalized_isin(value: str | None) -> str | None:
    """Return an upper-cased, stripped ISIN, or ``None`` if blank."""
    if value is None:
        return None
    text = value.strip().upper()
    return text or None


def reconcile_cross_listings(
    nse_instruments: Iterable[RawInstrument],
    bse_instruments: Iterable[RawInstrument],
    admit_bse_only_series: frozenset[str] = frozenset(),
) -> CrossListingReconciliation:
    """Merge two exchange instrument masters into one canonical set by ISIN.

    Args:
        nse_instruments: The NSE instrument master (canonical identity source).
        bse_instruments: The BSE instrument master.
        admit_bse_only_series: BSE group codes (``SctySrs``) whose BSE-only names
            may enter the canonical set. Empty by default — see module docstring
            rule 3.

    Returns:
        The canonical instruments plus a disclosure of everything withheld.
    """
    nse_list = list(nse_instruments)
    bse_list = list(bse_instruments)

    bse_isins = {isin for inst in bse_list if (isin := _normalized_isin(inst.isin))}
    nse_isins = {isin for inst in nse_list if (isin := _normalized_isin(inst.isin))}
    nse_symbols = {inst.symbol.strip().upper() for inst in nse_list}

    canonical: list[CanonicalInstrument] = []
    cross_listed = 0
    for inst in nse_list:
        isin = _normalized_isin(inst.isin)
        on_both = isin is not None and isin in bse_isins
        cross_listed += int(on_both)
        canonical.append(
            CanonicalInstrument(
                symbol=inst.symbol.strip().upper(),
                name=inst.name,
                isin=isin,
                exchange=Exchange.BOTH if on_both else Exchange.NSE,
                listing_date=inst.listing_date,
            )
        )

    withheld: list[str] = []
    collisions: list[str] = []
    admitted: dict[str, CanonicalInstrument] = {}
    for inst in sorted(bse_list, key=lambda i: (i.symbol.strip().upper(), i.isin or "")):
        isin = _normalized_isin(inst.isin)
        if isin is not None and isin in nse_isins:
            continue  # already represented by its canonical NSE record
        symbol = inst.symbol.strip().upper()
        if (inst.series or "") not in admit_bse_only_series:
            withheld.append(symbol)
            continue
        if symbol in nse_symbols:
            collisions.append(symbol)
            continue
        admitted.setdefault(
            symbol,
            CanonicalInstrument(
                symbol=symbol,
                name=inst.name,
                isin=isin,
                exchange=Exchange.BSE,
                listing_date=inst.listing_date,
            ),
        )

    canonical.extend(admitted.values())
    canonical.sort(key=lambda i: i.symbol)
    return CrossListingReconciliation(
        instruments=tuple(canonical),
        cross_listed=cross_listed,
        nse_only=len(nse_list) - cross_listed,
        bse_only_admitted=len(admitted),
        bse_only_withheld=tuple(sorted(set(withheld))),
        symbol_collisions=tuple(sorted(set(collisions))),
    )
