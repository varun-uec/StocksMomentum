"""Wave personality — do volume and momentum corroborate the labelled position?

Source: Frost & Prechter, *Elliott Wave Principle* (1978), Lesson 14 ("Wave
Personality"), which describes the behaviour typical of each wave position:
wave 2 retraces deeply on fading participation, wave 3 is the strongest and
broadest leg, wave 4 is shallow and sideways, wave 5 advances on diminishing
volume and momentum, and so on.

What this module is for
-----------------------
It cross-checks a *labelling* against volume, RSI and ADX the platform already
computes, and reports each check as supporting, contradicting or not measurable
with the numbers that decided it. That is evidence about the internal
consistency of a wave count — nothing here is a trading signal, and no check can
accept or reject a count. A count whose personality evidence is entirely
contradicting is still a valid count; it simply ranks below one that the data
corroborates.

The context is optional throughout. When indicator data is unavailable (short
history, warm-up periods, a pipeline failure) every affected check reports "not
measurable" and the count is neither credited nor penalised for it.

Pure and deterministic. No I/O, no clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.domain.analytics.elliott.patterns import (
    CONTRADICTING,
    NOT_MEASURABLE,
    SUPPORTING,
)

_ZERO = Decimal("0")
_HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class PersonalityContext:
    """Per-bar series the personality checks read, aligned by position.

    Every tuple has exactly one entry per ``dates`` element, in ascending date
    order — the same contract as
    :class:`momentum25.domain.value_objects.indicators.IndicatorSeriesSet`, from
    which ``rsi14`` and ``adx14`` are taken verbatim. ``volumes`` comes off the
    OHLCV bars, which is where volume lives; no indicator math is duplicated
    here.
    """

    dates: tuple[date, ...] = ()
    rsi14: tuple[Decimal | None, ...] = ()
    adx14: tuple[Decimal | None, ...] = ()
    volumes: tuple[int | None, ...] = ()


@dataclass(frozen=True, slots=True)
class PersonalityCheck:
    """One wave position's expected behaviour, tested against real data."""

    wave: str  # the label of the wave being characterised, e.g. "3"
    expectation: str
    status: str  # SUPPORTING | CONTRADICTING | NOT_MEASURABLE
    detail: str


@dataclass(frozen=True, slots=True)
class _LegStats:
    """Aggregates over the bars a single labelled wave spans."""

    label: str
    mean_volume: Decimal | None
    mean_adx: Decimal | None
    terminal_rsi: Decimal | None
    displacement: Decimal


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, _ZERO) / Decimal(len(values))


def _leg_stats(
    context: PersonalityContext,
    label: str,
    start: date,
    end: date,
    displacement: Decimal,
) -> _LegStats:
    volumes: list[Decimal] = []
    adx: list[Decimal] = []
    terminal_rsi: Decimal | None = None
    for i, bar_date in enumerate(context.dates):
        if not (start <= bar_date <= end):
            continue
        volume = context.volumes[i] if i < len(context.volumes) else None
        if volume is not None:
            volumes.append(Decimal(volume))
        value = context.adx14[i] if i < len(context.adx14) else None
        if value is not None:
            adx.append(value)
        if bar_date == end and i < len(context.rsi14):
            terminal_rsi = context.rsi14[i]
    return _LegStats(
        label=label,
        mean_volume=_mean(volumes),
        mean_adx=_mean(adx),
        terminal_rsi=terminal_rsi,
        displacement=displacement,
    )


def _compare(
    wave: str, expectation: str, left: Decimal | None, right: Decimal | None, *, greater: bool
) -> PersonalityCheck:
    """Test ``left`` against ``right`` in the requested direction."""
    if left is None or right is None:
        return PersonalityCheck(
            wave, expectation, NOT_MEASURABLE, "the required series is unavailable for this leg"
        )
    holds = left > right if greater else left < right
    return PersonalityCheck(
        wave,
        expectation,
        SUPPORTING if holds else CONTRADICTING,
        f"measured {left:.2f} against {right:.2f}",
    )


def _retracement(stats: list[_LegStats], index: int) -> Decimal | None:
    """Depth of leg ``index`` relative to the leg before it."""
    if index == 0 or abs(stats[index - 1].displacement) == _ZERO:
        return None
    return abs(stats[index].displacement) / abs(stats[index - 1].displacement)


def _impulse_checks(stats: list[_LegStats]) -> list[PersonalityCheck]:
    """Lesson 14's characterisation of each impulse position."""
    by_label = {leg.label: leg for leg in stats}
    index_of = {leg.label: i for i, leg in enumerate(stats)}
    checks: list[PersonalityCheck] = []

    w1, w2, w3, w4, w5 = (by_label.get(k) for k in ("1", "2", "3", "4", "5"))

    if w1 is not None and w3 is not None:
        checks.append(
            _compare(
                "1",
                "Wave 1 draws less participation than wave 3",
                w1.mean_volume,
                w3.mean_volume,
                greater=False,
            )
        )
    if w2 is not None:
        depth = _retracement(stats, index_of["2"])
        checks.append(
            PersonalityCheck(
                "2",
                "Wave 2 retraces deeply (at least half of wave 1)",
                NOT_MEASURABLE
                if depth is None
                else (SUPPORTING if depth >= _HALF else CONTRADICTING),
                "not measurable" if depth is None else f"retraced {depth:.3f} of wave 1",
            )
        )
        if w1 is not None:
            checks.append(
                _compare(
                    "2",
                    "Wave 2 sees participation contract against wave 1",
                    w2.mean_volume,
                    w1.mean_volume,
                    greater=False,
                )
            )
    if w3 is not None:
        others = [leg.mean_volume for leg in stats if leg is not w3 and leg.mean_volume is not None]
        checks.append(
            _compare(
                "3",
                "Wave 3 carries the heaviest volume of the impulse",
                w3.mean_volume,
                max(others) if others else None,
                greater=True,
            )
        )
        adx_others = [leg.mean_adx for leg in stats if leg is not w3 and leg.mean_adx is not None]
        checks.append(
            _compare(
                "3",
                "Wave 3 shows the strongest trend (highest ADX)",
                w3.mean_adx,
                max(adx_others) if adx_others else None,
                greater=True,
            )
        )
    if w4 is not None:
        depth = _retracement(stats, index_of["4"])
        checks.append(
            PersonalityCheck(
                "4",
                "Wave 4 is shallow (no more than half of wave 3)",
                NOT_MEASURABLE
                if depth is None
                else (SUPPORTING if depth <= _HALF else CONTRADICTING),
                "not measurable" if depth is None else f"retraced {depth:.3f} of wave 3",
            )
        )
        if w3 is not None:
            checks.append(
                _compare(
                    "4",
                    "Wave 4 trades on lighter volume than wave 3",
                    w4.mean_volume,
                    w3.mean_volume,
                    greater=False,
                )
            )
    if w5 is not None and w3 is not None:
        checks.append(
            _compare(
                "5",
                "Wave 5 advances on lighter volume than wave 3",
                w5.mean_volume,
                w3.mean_volume,
                greater=False,
            )
        )
        checks.append(
            _compare(
                "5",
                "Momentum diverges: RSI at the wave 5 terminal is below its wave 3 reading",
                w5.terminal_rsi,
                w3.terminal_rsi,
                greater=False,
            )
        )
    return checks


def _corrective_checks(stats: list[_LegStats]) -> list[PersonalityCheck]:
    """Lesson 14 on corrective positions: B is weak, C is impulsive in character."""
    by_label = {leg.label: leg for leg in stats}
    checks: list[PersonalityCheck] = []
    a, b, c = (by_label.get(k) for k in ("A", "B", "C"))
    if a is not None and b is not None:
        checks.append(
            _compare(
                "B",
                "Wave B draws weaker participation than wave A",
                b.mean_volume,
                a.mean_volume,
                greater=False,
            )
        )
    if b is not None and c is not None:
        checks.append(
            _compare(
                "C",
                "Wave C is impulsive in character: heavier volume than wave B",
                c.mean_volume,
                b.mean_volume,
                greater=True,
            )
        )
        checks.append(
            _compare(
                "C",
                "Wave C trends more strongly than wave B (higher ADX)",
                c.mean_adx,
                b.mean_adx,
                greater=True,
            )
        )
    return checks


def _triangle_checks(stats: list[_LegStats]) -> list[PersonalityCheck]:
    """A triangle's hallmark is steadily drying-up participation (Lesson 10)."""
    volumes = [(leg.label, leg.mean_volume) for leg in stats if leg.mean_volume is not None]
    if len(volumes) < 3:
        return [
            PersonalityCheck(
                stats[-1].label,
                "Volume contracts as the triangle develops",
                NOT_MEASURABLE,
                "too few legs carry volume data",
            )
        ]
    first, last = volumes[0][1], volumes[-1][1]
    return [
        PersonalityCheck(
            stats[-1].label,
            "Volume contracts as the triangle develops",
            SUPPORTING if last < first else CONTRADICTING,
            f"first leg averaged {first:.0f}, final leg {last:.0f}",
        )
    ]


def evaluate(
    pattern: str,
    labels: tuple[tuple[str, date, Decimal], ...],
    context: PersonalityContext | None,
) -> tuple[PersonalityCheck, ...]:
    """Return the personality evidence for one count.

    ``labels`` is the count's terminals as ``(label, bar_date, price)``, origin
    first. With no context, an empty tuple is returned and the ranking treats
    personality as unmeasured rather than as failed.
    """
    if context is None or len(labels) < 2 or not context.dates:
        return ()

    stats = [
        _leg_stats(context, label, previous[1], bar_date, price - previous[2])
        for previous, (label, bar_date, price) in zip(labels, labels[1:], strict=False)
    ]

    if pattern in ("impulse", "diagonal"):
        checks = _impulse_checks(stats)
    elif pattern == "triangle":
        checks = _triangle_checks(stats)
    elif pattern in ("zigzag", "flat"):
        checks = _corrective_checks(stats)
    else:
        checks = []
    return tuple(checks)


def corroboration(checks: tuple[PersonalityCheck, ...]) -> Decimal | None:
    """Share of *measurable* checks that support the labelling, or ``None``."""
    measurable = [c for c in checks if c.status != NOT_MEASURABLE]
    if not measurable:
        return None
    supporting = sum(1 for c in measurable if c.status == SUPPORTING)
    return Decimal(supporting) / Decimal(len(measurable))
