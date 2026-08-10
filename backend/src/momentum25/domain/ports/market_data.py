"""Market-data provider port and its raw transfer types.

Implementations live in ``infrastructure/providers`` (e.g. ``BhavcopyProvider``).
The port is interval-agnostic so intraday adapters can be added later (ADD §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RawInstrument:
    """A raw instrument record as returned by a provider, pre-normalization.

    ``sector``/``industry`` are always ``None`` for the NSE Bhavcopy provider:
    no free NSE endpoint (nor ``nsemine``) publishes equity sector/industry
    classification, current or historical -- see the corresponding gap
    disclosure in ``docs/research``. Guessing a classification from the
    company name would be exactly the kind of fabricated certainty the
    research charter forbids, so the fields are left unpopulated rather than
    inferred.
    """

    symbol: str
    name: str
    isin: str | None = None
    sector: str | None = None
    industry: str | None = None
    series: str | None = None
    listing_date: date | None = None
    native_code: str | None = None


@dataclass(frozen=True, slots=True)
class RawBar:
    """A raw OHLCV record as returned by a provider, pre-normalization.

    ``prev_close`` and ``turnover_value`` are the source's reported previous
    close and total traded value (rupee turnover) for the session. They are
    populated by the legacy NSE bhavcopy archive (RP-012 §1.2/§2.2: previous
    close drives corporate-action ratio inference, turnover drives the
    historical liquidity gate) and left ``None`` by providers that do not
    expose them. They are never derived or guessed.

    ``isin`` is the source's reported ISIN for the security on that session,
    present in the 2019+ legacy bhavcopy schema (RP-012 Phase 2 §2.2). It is
    the period-correct security identity and is used to resolve a bar to a
    ``security_id`` robustly to ticker drift (a symbol renamed between the
    session date and today's instrument master); ``None`` when the source does
    not carry an ISIN column. It is never derived or guessed.

    ``native_code`` is the source exchange's own stable instrument code when
    the source publishes one (BSE's ``SC_CODE`` in the 2006–2023 legacy
    bhavcopy and ``FinInstrmId`` in the UDiFF format). It is the identity key
    the RP-014 BSE legacy backfill uses to learn a scrip's ISIN from modern
    UDiFF sessions; ``None`` when the source prints only a ticker.
    """

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    prev_close: Decimal | None = None
    turnover_value: Decimal | None = None
    isin: str | None = None
    native_code: str | None = None


@dataclass(frozen=True, slots=True)
class RawIndexBar:
    """A raw benchmark-index close as returned by a provider."""

    index_code: str
    date: date
    close: Decimal


@dataclass(frozen=True, slots=True)
class RawCorporateAction:
    """A raw corporate action as returned by a provider, pre-normalization.

    ``ratio`` is the price-adjustment multiplier to apply to bars *before*
    ``ex_date`` (i.e. ``adjusted_price = raw_price * ratio``), already resolved
    from whatever free-text description the source uses. ``ratio is None``
    means the action was recognized but its type does not require a price
    adjustment (e.g. a cash dividend) or could not be confidently parsed --
    callers must not guess a ratio in that case (see
    ``domain.entities.market_data.compute_adjustment_factors``).
    """

    symbol: str
    ex_date: date
    action_type: str
    ratio: Decimal | None
    raw_subject: str


@runtime_checkable
class MarketDataProvider(Protocol):
    """Fetches market data from an external source.

    Selected via ``settings.data_provider``. New sources (broker APIs, vendors)
    implement this same port without any change to the core (ADR-003).
    """

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        """Return EOD bars for all instruments on ``for_date`` (empty on holidays)."""
        ...

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        """Return the current instrument master list."""
        ...

    async def fetch_benchmark(self, index_code: str, for_date: date) -> RawIndexBar | None:
        """Return the benchmark index close for ``for_date``, if available."""
        ...

    async def fetch_corporate_actions(
        self, symbol: str, since: date
    ) -> list[RawCorporateAction]:
        """Return corporate actions for ``symbol`` with ``ex_date >= since``."""
        ...
