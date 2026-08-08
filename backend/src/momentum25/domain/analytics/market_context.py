"""Market-context analytics: index-relative strength, breadth, sector strength.

Pure calculation only -- no I/O, no framework dependencies. Every function is a
deterministic transformation of already-fetched close series into raw numbers.

Nothing here produces a verdict, a rating, a target or a directional label. A
sector's rank is an ordering of a measured number (excess return), not a claim
that the sector will continue to lead; breadth counts are counts. This mirrors
the constraint the rest of the platform already enforces -- see
``domain/research/stop_loss.py`` and ``web/src/components/stock/SuggestedStop.tsx``.

None of these values feed the composite score or the ranking. They are display
context. Using any of them as a ranking input is a directional/selection claim
and would have to go through the hold-out research process first.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Lookback periods in *trading sessions*, matching the RS pipeline's convention
# (``infrastructure/pipelines/relative_strength_pipeline.py``) so a 3m figure
# here means the same thing as a 3m figure there.
RS_PERIODS: tuple[tuple[str, int], ...] = (
    ("1m", 22),
    ("3m", 63),
    ("6m", 126),
    ("12m", 252),
)

# Trailing sessions used for the moving averages and 52-week extremes in the
# breadth panel. 252 sessions is one trading year, the same window the indicator
# pipeline uses for its 52-week high/low (``_DEFAULT_HIGH_LOW_WINDOW``).
BREADTH_SMA_SHORT = 50
BREADTH_SMA_LONG = 200
BREADTH_52W_WINDOW = 252

# The period whose excess return orders the sector table. Fixed rather than
# caller-supplied so the rank is reproducible from the response alone.
SECTOR_RANK_PERIOD = "3m"

_PCT = Decimal("100")
_QUANT = Decimal("0.0001")


def _quantize(value: Decimal | None) -> Decimal | None:
    """Round to the platform's fixed egress precision (ADR-009)."""
    return None if value is None else value.quantize(_QUANT)


def _period_return_pct(closes: Sequence[Decimal], sessions: int) -> Decimal | None:
    """Percentage return over the trailing ``sessions`` closes, or ``None``.

    ``None`` means the series is too short to measure the period -- never a
    substituted zero, which would silently read as "flat" rather than
    "unmeasured".
    """
    if len(closes) < sessions + 1:
        return None
    start = closes[-(sessions + 1)]
    if start <= 0:
        return None
    return (closes[-1] / start - Decimal("1")) * _PCT


@dataclass(frozen=True, slots=True)
class RelativeStrengthPoint:
    """Stock vs index performance over one lookback period, as raw numbers."""

    period: str
    sessions: int
    stock_return_pct: Decimal | None
    index_return_pct: Decimal | None
    excess_return_pct: Decimal | None


def relative_strength_vs_index(
    stock_closes: Mapping[date, Decimal],
    index_closes: Mapping[date, Decimal],
) -> tuple[RelativeStrengthPoint, ...]:
    """Return ``stock return - index return`` over each period in :data:`RS_PERIODS`.

    Both series are first restricted to the dates they have in common and sorted
    ascending, so a period is always measured over the same sessions for the
    stock and the index. A stock missing an index session (or the reverse) would
    otherwise shift the two windows against each other and produce an excess
    return that compares different spans of time.

    Any period without enough common history yields ``None`` for all three
    figures rather than a partial or substituted value.
    """
    common = sorted(set(stock_closes) & set(index_closes))
    stock = [stock_closes[d] for d in common]
    index = [index_closes[d] for d in common]

    points: list[RelativeStrengthPoint] = []
    for label, sessions in RS_PERIODS:
        stock_ret = _period_return_pct(stock, sessions)
        index_ret = _period_return_pct(index, sessions)
        excess = None if stock_ret is None or index_ret is None else stock_ret - index_ret
        points.append(
            RelativeStrengthPoint(
                period=label,
                sessions=sessions,
                stock_return_pct=_quantize(stock_ret),
                index_return_pct=_quantize(index_ret),
                excess_return_pct=_quantize(excess),
            )
        )
    return tuple(points)


@dataclass(frozen=True, slots=True)
class MarketBreadth:
    """Cross-sectional counts over the tracked universe, as of one date.

    ``evaluated`` is the number of securities with enough history to be counted
    at all; the percentages are taken over ``above_sma50_of`` /
    ``above_sma200_of`` rather than over ``evaluated``, because a security with
    250 sessions can be measured against its 50-day average but not its 200-day
    one. Dividing both by a single universe size would understate the long-average
    figure by counting unmeasurable names as failures.
    """

    as_of: date
    evaluated: int
    above_sma50: int
    above_sma50_of: int
    pct_above_sma50: Decimal | None
    above_sma200: int
    above_sma200_of: int
    pct_above_sma200: Decimal | None
    new_52w_highs: int
    new_52w_lows: int
    high_low_of: int


def _sma(closes: Sequence[Decimal], window: int) -> Decimal | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:], Decimal("0")) / Decimal(window)


def compute_market_breadth(
    as_of: date,
    closes_by_symbol: Mapping[str, Sequence[Decimal]],
) -> MarketBreadth:
    """Count how much of the universe is above its 50/200-DMA and at 52w extremes.

    A "new 52-week high" is defined on *closes*: the latest close is the highest
    of the trailing :data:`BREADTH_52W_WINDOW` closes (symmetrically for lows).
    Closes are used rather than intraday highs/lows because a close-based
    extreme is measurable from the same series every other figure on this panel
    uses, and because the daily-bar high/low of a single illiquid print is a
    noisier definition. This is a definition, not an approximation of some other
    number -- it is stated on the panel itself.
    """
    evaluated = 0
    above50 = of50 = 0
    above200 = of200 = 0
    highs = lows = of_hl = 0

    for closes in closes_by_symbol.values():
        if not closes:
            continue
        evaluated += 1
        latest = closes[-1]

        sma_short = _sma(closes, BREADTH_SMA_SHORT)
        if sma_short is not None:
            of50 += 1
            above50 += latest > sma_short

        sma_long = _sma(closes, BREADTH_SMA_LONG)
        if sma_long is not None:
            of200 += 1
            above200 += latest > sma_long

        if len(closes) >= BREADTH_52W_WINDOW:
            window = closes[-BREADTH_52W_WINDOW:]
            of_hl += 1
            highs += latest >= max(window)
            lows += latest <= min(window)

    def pct(count: int, total: int) -> Decimal | None:
        return None if total == 0 else _quantize(Decimal(count) / Decimal(total) * _PCT)

    return MarketBreadth(
        as_of=as_of,
        evaluated=evaluated,
        above_sma50=above50,
        above_sma50_of=of50,
        pct_above_sma50=pct(above50, of50),
        above_sma200=above200,
        above_sma200_of=of200,
        pct_above_sma200=pct(above200, of200),
        new_52w_highs=highs,
        new_52w_lows=lows,
        high_low_of=of_hl,
    )


@dataclass(frozen=True, slots=True)
class SectorRelativeStrength:
    """Equal-weighted mean excess return of one sector's constituents."""

    sector: str
    constituents: int
    rank: int
    excess_return_pct: Mapping[str, Decimal | None]


def compute_sector_relative_strength(
    excess_by_symbol: Mapping[str, Mapping[str, Decimal | None]],
    sector_by_symbol: Mapping[str, str | None],
) -> tuple[SectorRelativeStrength, ...]:
    """Aggregate per-symbol excess returns into an equal-weighted sector ranking.

    Equal-weighted rather than market-cap-weighted: the platform ingests no
    share-count or market-cap data, so a cap weighting would have to be invented.

    Symbols with no sector classification are excluded rather than pooled into an
    "Other" bucket, which would present a made-up group as a real one. A period
    with no measurable constituent yields ``None`` for that period.

    Ranked by :data:`SECTOR_RANK_PERIOD` excess return descending, ties and
    unmeasurable sectors broken by sector name so the ordering is total and
    reproducible.
    """
    grouped: dict[str, list[Mapping[str, Decimal | None]]] = {}
    for symbol, excess in excess_by_symbol.items():
        sector = (sector_by_symbol.get(symbol) or "").strip()
        if not sector:
            continue
        grouped.setdefault(sector, []).append(excess)

    rows: list[tuple[str, int, dict[str, Decimal | None]]] = []
    for sector, members in grouped.items():
        means: dict[str, Decimal | None] = {}
        for label, _ in RS_PERIODS:
            values = [
                value for m in members if (value := m.get(label)) is not None
            ]
            means[label] = (
                _quantize(sum(values, Decimal("0")) / Decimal(len(values))) if values else None
            )
        rows.append((sector, len(members), means))

    # sort key: measurable sectors first, then by rank-period excess desc, then name
    def sort_key(row: tuple[str, int, dict[str, Decimal | None]]) -> tuple[int, Decimal, str]:
        value = row[2].get(SECTOR_RANK_PERIOD)
        return (0 if value is not None else 1, -(value or Decimal("0")), row[0])

    rows.sort(key=sort_key)
    return tuple(
        SectorRelativeStrength(
            sector=sector, constituents=count, rank=idx, excess_return_pct=means
        )
        for idx, (sector, count, means) in enumerate(rows, start=1)
    )
