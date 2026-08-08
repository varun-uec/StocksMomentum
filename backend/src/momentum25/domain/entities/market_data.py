"""Market-data entities: a single OHLCV bar and an ordered series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from momentum25.domain.ports.market_data import RawCorporateAction


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """A single daily OHLCV bar. ``adj_close`` is the corporate-action-adjusted close."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adj_close: Decimal | None = None
    prev_close: Decimal | None = None
    turnover_value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class OHLCVSeries:
    """An ordered (ascending by date) price series for one security.

    Provides convenience accessors used by the indicator pipeline. Bars must be
    sorted ascending by date; this invariant is the caller's responsibility and is
    validated in :meth:`__post_init__`.
    """

    security_id: int
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        """Validate the ascending-date invariant."""
        dates = [b.date for b in self.bars]
        if dates != sorted(dates):
            raise ValueError("OHLCVSeries bars must be sorted ascending by date")

    def __len__(self) -> int:
        """Return the number of bars."""
        return len(self.bars)

    @property
    def latest(self) -> OHLCVBar | None:
        """Return the most recent bar, or ``None`` if empty."""
        return self.bars[-1] if self.bars else None

    def closes(self) -> list[Decimal]:
        """Return adjusted closes (falling back to raw close)."""
        return [b.adj_close if b.adj_close is not None else b.close for b in self.bars]

    def volumes(self) -> list[int]:
        """Return the volume series."""
        return [b.volume for b in self.bars]


def compute_adjustment_factors(
    bar_dates: list[date], actions: list[RawCorporateAction]
) -> dict[date, Decimal]:
    """Compute a cumulative backward-adjustment factor for each bar date.

    For a bar on ``d``, the factor is the product of the ``ratio`` of every
    action with ``ex_date > d`` (bars strictly before an action's ex-date are
    adjusted; the ex-date bar itself and all later bars already trade at the
    post-action price, factor 1.0). ``adjusted_price = raw_price * factor``
    and ``adjusted_volume = raw_volume / factor``.

    Actions with ``ratio is None`` (unparseable or non-price-affecting, e.g. a
    cash dividend) are skipped entirely -- they never contribute to the
    factor. This is deliberate: a wrong guessed ratio silently corrupts every
    bar before it, which is worse than leaving that specific action
    unadjusted and disclosed (see ``RawCorporateAction`` docstring).
    """
    priced_actions = [a for a in actions if a.ratio is not None]
    factors: dict[date, Decimal] = {}
    for d in bar_dates:
        factor = Decimal("1")
        for action in priced_actions:
            if action.ex_date > d:
                factor *= action.ratio  # type: ignore[operator]  # ratio is not None here
        factors[d] = factor
    return factors
