"""Market-data entities: a single OHLCV bar and an ordered series."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from momentum25.domain.ports.market_data import RawCorporateAction


_PRICE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """A single daily OHLCV bar, as printed (raw).

    ``adj_close`` is the corporate-action-adjusted close. ``adj_factor`` is the
    stored backward adjustment factor (1 = no adjustment); the adjustment
    refresh owns it, so bar writers ignore this field.
    """

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adj_close: Decimal | None = None
    prev_close: Decimal | None = None
    turnover_value: Decimal | None = None
    adj_factor: Decimal = Decimal(1)

    def adjusted(self) -> OHLCVBar:
        """Return the bar on the adjusted basis screening uses.

        Prices are multiplied by ``adj_factor`` and volume divided by it, the
        contract of :func:`compute_adjustment_factors` and of the indicator
        pipeline. Prices keep the stored 4-decimal precision. ``prev_close`` and
        ``turnover_value`` have no single adjusted meaning across an ex-date, so
        they are dropped.
        """
        if self.adj_factor == 1:
            return self
        f = self.adj_factor

        def price(value: Decimal) -> Decimal:
            return (value * f).quantize(_PRICE_QUANTUM)

        return OHLCVBar(
            date=self.date,
            open=price(self.open),
            high=price(self.high),
            low=price(self.low),
            close=price(self.close),
            volume=round(self.volume / f),
            adj_close=self.adj_close,
            adj_factor=Decimal(1),
        )


@dataclass(frozen=True, slots=True)
class AdjustmentStep:
    """One run of equal ``adj_factor``: it applies to bars dated up to ``until``."""

    until: date
    factor: Decimal


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
        """Return adjusted closes, ``close × adj_factor`` (IMPLEMENTATION_SPEC §8)."""
        return [b.close * b.adj_factor for b in self.bars]

    def volumes(self) -> list[int]:
        """Return the volume series."""
        return [b.volume for b in self.bars]

    def as_of(self, day: date) -> OHLCVSeries:
        """Return the series as it stood on ``day``: no later bar, no later corporate action.

        A stored ``adj_factor`` folds in every action up to today. Dividing by the
        factor of the last bar on or before ``day`` leaves the product of the actions
        with an ex-date in ``(bar date, day]``: exactly what was known on ``day``.
        ``adj_close`` is dropped, because it carries today's factor.
        """
        kept = [b for b in self.bars if b.date <= day]
        base = kept[-1].adj_factor if kept else Decimal(1)
        return OHLCVSeries(
            security_id=self.security_id,
            bars=tuple(replace(b, adj_factor=b.adj_factor / base, adj_close=None) for b in kept),
        )

    def adjustment_schedule(self) -> tuple[AdjustmentStep, ...]:
        """Return the factor of every date, as runs of equal ``adj_factor``.

        A bar dated ``d`` takes the factor of the first step with ``until >= d``.
        The schedule has one step per corporate action plus one, so a chart can
        convert a price at any date without loading every bar.
        """
        steps: list[AdjustmentStep] = []
        for bar in self.bars:
            if steps and steps[-1].factor == bar.adj_factor:
                steps[-1] = AdjustmentStep(until=bar.date, factor=bar.adj_factor)
            else:
                steps.append(AdjustmentStep(until=bar.date, factor=bar.adj_factor))
        return tuple(steps)


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


Period = Literal["week", "month"]


@dataclass(frozen=True, slots=True)
class PeriodBar:
    """One ISO week or calendar month of trading sessions as a single bar (ADR-013 §4).

    ``partial`` is true when the exchange calendar has a session in the period
    after the bar's last session: the period is still running, or the security
    did not trade to the end of it.
    """

    bar: OHLCVBar
    partial: bool


def _period_of(day: date, period: Period) -> tuple[int, int]:
    if period == "month":
        return day.year, day.month
    iso = day.isocalendar()
    return iso.year, iso.week


def period_bars(
    daily: Sequence[OHLCVBar], sessions: Iterable[date], period: Period
) -> list[PeriodBar]:
    """Aggregate adjusted daily bars into one bar per ISO week or calendar month.

    Open is the first session's open, high the highest high, low the lowest
    low, close the last session's close and volume the sum. The bar is dated
    at its last session. A period with holidays still has one bar; a period
    with no bars has none. ``sessions`` is the exchange calendar over the bars'
    periods, used only for the ``partial`` flag.

    The daily bars must already be adjusted (``adj_factor`` 1). Aggregating raw
    prints across an ex-date would mix two price bases in one bar.
    """
    if any(b.adj_factor != 1 for b in daily):
        raise ValueError("period_bars needs adjusted daily bars (adj_factor 1)")
    last_session: dict[tuple[int, int], date] = {}
    for day in sessions:
        key = _period_of(day, period)
        last_session[key] = max(day, last_session.get(key, day))

    groups: dict[tuple[int, int], list[OHLCVBar]] = {}
    for bar in daily:
        groups.setdefault(_period_of(bar.date, period), []).append(bar)

    out: list[PeriodBar] = []
    for key, bars in groups.items():
        last = bars[-1]
        bar = OHLCVBar(
            date=last.date,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=last.close,
            volume=sum(b.volume for b in bars),
        )
        out.append(PeriodBar(bar=bar, partial=last_session.get(key, last.date) > last.date))
    return out


def series_data_version(bars: Iterable[OHLCVBar], indicator_version: int) -> str:
    """Return a short, deterministic hash of every stored input to a chart series.

    It covers each bar's raw prices, volume and ``adj_factor``, so a new
    session, a corrected print or a refreshed factor each give a new version,
    plus the indicator version. Until the history tables of ADR-014 §7 exist,
    this content hash is the data version that chart and alert responses
    share (ADR-013 §4).
    """
    digest = hashlib.sha256(f"indicators:{indicator_version}".encode())
    for b in bars:
        row = f"|{b.date}:{b.open}:{b.high}:{b.low}:{b.close}:{b.volume}:{b.adj_factor.normalize()}"
        digest.update(row.encode())
    return digest.hexdigest()[:12]
