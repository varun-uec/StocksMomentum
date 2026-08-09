"""The rule sets of every modelled Elliott Wave structure.

Sources
-------
All rules and guidelines below are taken from A.J. Frost & Robert Prechter,
*Elliott Wave Principle: Key to Market Behavior* (1978), which restates R.N.
Elliott's original formulation:

* Lesson 2, "The Cardinal Rules" — the three rules governing impulses.
* Lesson 5, "Extension, Truncation" — extended waves and the truncated fifth.
* Lesson 6, "Diagonal Triangles" — leading and ending diagonals, the one motive
  structure in which wave 4 may enter wave 1's price territory.
* Lesson 8, "Zigzags" — the 5-3-5 sharp correction.
* Lesson 9, "Flats" — the 3-3-5 sideways correction and its regular, expanded
  and running variants.
* Lesson 10, "Triangles" — the 3-3-3-3-3 contracting and expanding triangle.
* Lesson 11, "Combinations" — double and triple threes.
* Lesson 21, "Ratio Analysis" — the Fibonacci proportions, applied in
  :mod:`.fibonacci` as *guidelines* only.

Rules versus guidelines
-----------------------
A **rule** is binary: a structure that breaks one is not that structure, and is
never labelled as one. A **guideline** is a tendency: it is measured, reported
as supporting or contradicting evidence, and fed into the ranking — but it never
accepts or rejects a count. That separation is the whole reason a marginal count
can be displayed honestly rather than silently suppressed or silently promoted.

An **allowance** records a judgment call the labelling had to make for the
structure to fit — a truncated fifth, a running flat, a diagonal whose position
cannot be established from the structure alone. Allowances are rule-legal by
construction; they are counted against the count's structural cleanliness so an
interpretation-heavy reading ranks below a textbook one.

Price normalisation
-------------------
Every fit function receives ``p``: the origin followed by each labelled wave
terminal, sign-normalised so the *first* leg always advances (increasing). An
upward impulse and a downward impulse therefore exercise identical arithmetic.

Pure and deterministic. No I/O, no clock, no randomness. Nothing here emits a
target price, a profit projection or a buy/sell verdict.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

SUPPORTING = "supporting"
CONTRADICTING = "contradicting"
NOT_MEASURABLE = "not measurable"

MOTIVE = "motive"
CORRECTIVE = "corrective"

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class GuidelineCheck:
    """One measured Elliott *guideline*, with the number that decided it.

    Never accepts or rejects a count — guidelines are tendencies, and a count
    that contradicts several of them is still a valid count, merely a less clean
    one.
    """

    name: str
    status: str  # SUPPORTING | CONTRADICTING | NOT_MEASURABLE
    detail: str


@dataclass(frozen=True, slots=True)
class PatternFit:
    """The outcome of testing one pattern's rules against a terminal sequence."""

    pattern: str
    family: str  # MOTIVE | CORRECTIVE
    variant: str | None
    labels: tuple[str, ...]
    rules_applied: tuple[str, ...]
    allowances: tuple[str, ...]
    guidelines: tuple[GuidelineCheck, ...]
    complete: bool


@dataclass(frozen=True, slots=True)
class PatternSpec:
    """A modelled structure: its label alphabet, its size range and its rules."""

    pattern: str
    family: str
    labels: tuple[str, ...]
    min_terminals: int
    max_terminals: int
    fit: Callable[[list[Decimal], bool], PatternFit | None]


# ── shared helpers ───────────────────────────────────────────────────────


def _legs(p: list[Decimal]) -> list[Decimal]:
    """Signed leg displacements; odd legs advance, even legs retrace."""
    return [b - a for a, b in zip(p, p[1:], strict=False)]


def _alternates(p: list[Decimal]) -> bool:
    """Legs strictly alternate advance/retrace, with no zero-length leg."""
    for i in range(1, len(p)):
        if i % 2 == 1 and p[i] <= p[i - 1]:
            return False
        if i % 2 == 0 and p[i] >= p[i - 1]:
            return False
    return True


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Magnitude ratio, or ``None`` when the denominator is degenerate."""
    if denominator == _ZERO:
        return None
    return abs(numerator) / abs(denominator)


def _check(name: str, holds: bool | None, detail: str) -> GuidelineCheck:
    if holds is None:
        return GuidelineCheck(name, NOT_MEASURABLE, detail)
    return GuidelineCheck(name, SUPPORTING if holds else CONTRADICTING, detail)


def _pct(value: Decimal | None) -> str:
    return "unavailable" if value is None else f"{value:.3f}"


# ── motive: impulse (Lesson 2, Lesson 5) ─────────────────────────────────

IMPULSE_RULES = (
    "Wave 2 never retraces more than 100% of wave 1",
    "Wave 3 is never the shortest of waves 1, 3 and 5",
    "Wave 4 never enters the price territory of wave 1",
)

_EXTENSION_RATIO = Decimal("1.618")
"""A wave counts as *extended* when it is at least this multiple of the longer
of its two sibling motive waves (Lesson 5: an extension is an elongated impulse
whose subdivisions are of nearly the same amplitude as the parent)."""

_DEEP_RETRACE = Decimal("0.5")
"""Boundary between a deep and a shallow retracement, used only by the
alternation guideline (Lesson 12)."""


def _impulse_extension(legs: list[Decimal]) -> str | None:
    """Name the extended wave, if one motive leg dominates the other two."""
    motive = {1: abs(legs[0]), 3: abs(legs[2]), 5: abs(legs[4])}
    position, longest = max(motive.items(), key=lambda item: (item[1], -item[0]))
    others = max(v for k, v in motive.items() if k != position)
    if others == _ZERO or longest / others < _EXTENSION_RATIO:
        return None
    return f"wave {position} extension"


def _impulse_guidelines(p: list[Decimal], legs: list[Decimal]) -> tuple[GuidelineCheck, ...]:
    checks: list[GuidelineCheck] = []
    r2 = _ratio(legs[1], legs[0]) if len(legs) > 1 else None
    checks.append(
        _check(
            "Wave 2 retraces a substantial part of wave 1 (Lesson 21)",
            None if r2 is None else Decimal("0.382") <= r2 <= Decimal("0.886"),
            f"wave 2 retraced {_pct(r2)} of wave 1",
        )
    )
    r4 = _ratio(legs[3], legs[2]) if len(legs) > 3 else None
    checks.append(
        _check(
            "Wave 4 is shallow relative to wave 3 (Lesson 21)",
            None if r4 is None else r4 <= _DEEP_RETRACE,
            f"wave 4 retraced {_pct(r4)} of wave 3",
        )
    )
    checks.append(
        _check(
            "Waves 2 and 4 alternate in depth (Lesson 12, the Guideline of Alternation)",
            None if (r2 is None or r4 is None) else (r2 > _DEEP_RETRACE) != (r4 > _DEEP_RETRACE),
            f"wave 2 {_pct(r2)} vs wave 4 {_pct(r4)} of their preceding waves",
        )
    )
    if len(legs) >= 5:
        w1, w3, w5 = abs(legs[0]), abs(legs[2]), abs(legs[4])
        checks.append(
            _check(
                "Wave 3 is the longest motive wave (Lesson 21)",
                w3 >= w1 and w3 >= w5,
                f"wave 1 {w1:.2f}, wave 3 {w3:.2f}, wave 5 {w5:.2f}",
            )
        )
    return tuple(checks)


def _fit_impulse(p: list[Decimal], up: bool) -> PatternFit | None:
    """Standard impulse: the three cardinal rules, plus extension/truncation."""
    if not _alternates(p):
        return None
    if len(p) > 2 and p[2] <= p[0]:  # cardinal rule 1
        return None
    if len(p) > 4 and p[4] <= p[1]:  # cardinal rule 3 (diagonals handled separately)
        return None
    legs = _legs(p)
    if len(p) > 5:  # cardinal rule 2
        w1, w3, w5 = abs(legs[0]), abs(legs[2]), abs(legs[4])
        if w3 < w1 and w3 < w5:
            return None

    complete = len(p) == 6
    allowances: list[str] = []
    variant = None
    if complete:
        variant = _impulse_extension(legs)
        if p[5] <= p[3]:
            allowances.append(
                "truncated fifth: wave 5 failed to exceed the end of wave 3 "
                "(Lesson 5, 'Truncation')"
            )
    return PatternFit(
        pattern="impulse",
        family=MOTIVE,
        variant=variant,
        labels=IMPULSE_LABELS[: len(p)],
        rules_applied=IMPULSE_RULES,
        allowances=tuple(allowances),
        guidelines=_impulse_guidelines(p, legs),
        complete=complete,
    )


# ── motive: diagonal (Lesson 6) ──────────────────────────────────────────

DIAGONAL_RULES = (
    "Wave 2 never retraces more than 100% of wave 1",
    "Wave 3 is never the shortest of waves 1, 3 and 5",
    "Wave 4 enters wave 1's price territory — permitted, and characteristic, "
    "only in a diagonal (Lesson 6)",
    "The structure converges (contracting) or diverges (expanding) monotonically",
)


def _fit_diagonal(p: list[Decimal], up: bool) -> PatternFit | None:
    """Leading/ending diagonal: the impulse rules minus the overlap prohibition.

    A diagonal is offered *only* when wave 4 actually overlaps wave 1. Without
    the overlap the same terminals are already a plain impulse, and labelling
    them twice would manufacture a competing count out of nothing.

    Whether a diagonal is *leading* (position 1 or A) or *ending* (position 5 or
    C) is a claim about its place in a larger structure, not something its own
    terminals can settle. When this pattern is labelled as a subdivision of a
    parent leg the position is known and named; standing alone it is recorded as
    an allowance rather than guessed.
    """
    if len(p) != 6 or not _alternates(p):
        return None
    if p[2] <= p[0]:
        return None
    if p[4] > p[1]:  # no overlap -> this is an impulse, not a diagonal
        return None
    legs = _legs(p)
    w1, w2, w3, w4, w5 = (abs(leg) for leg in legs)
    if w3 < w1 and w3 < w5:
        return None

    if w3 < w1 and w5 < w3 and w4 < w2:
        variant = "contracting"
    elif w3 > w1 and w5 > w3 and w4 > w2:
        variant = "expanding"
    else:
        return None

    return PatternFit(
        pattern="diagonal",
        family=MOTIVE,
        variant=variant,
        labels=IMPULSE_LABELS,
        rules_applied=DIAGONAL_RULES,
        allowances=(
            "diagonal position (leading vs ending) is not determinable from the "
            "structure alone; it is established only by the parent count",
        ),
        guidelines=_impulse_guidelines(p, legs),
        complete=True,
    )


# ── corrective: zigzag (Lesson 8) ────────────────────────────────────────

ZIGZAG_RULES = (
    "Wave B never retraces beyond the start of wave A",
    "Wave B retraces less than 90% of wave A (a deeper B is a flat, not a zigzag)",
)

_FLAT_B_MINIMUM = Decimal("0.9")
"""Frost & Prechter, Lesson 9: in a flat, wave B terminates at or beyond the
start of wave A — conventionally at least 90% of wave A. Below that the
correction is sharp, i.e. a zigzag."""


def _fit_zigzag(p: list[Decimal], up: bool) -> PatternFit | None:
    if not _alternates(p):
        return None
    legs = _legs(p)
    rb = _ratio(legs[1], legs[0]) if len(legs) > 1 else None
    if len(p) > 2:
        if p[2] <= p[0]:
            return None
        if rb is not None and rb >= _FLAT_B_MINIMUM:
            return None

    complete = len(p) == 4
    allowances: list[str] = []
    if complete and p[3] <= p[1]:
        allowances.append("truncated zigzag: wave C failed to exceed the end of wave A (Lesson 8)")

    checks = [
        _check(
            "Wave B retraces 0.5-0.786 of wave A (Lesson 21)",
            None if rb is None else Decimal("0.5") <= rb <= Decimal("0.786"),
            f"wave B retraced {_pct(rb)} of wave A",
        )
    ]
    if complete:
        rc = _ratio(legs[2], legs[0])
        checks.append(
            _check(
                "Wave C is 0.618-1.618 of wave A (Lesson 21)",
                None if rc is None else Decimal("0.618") <= rc <= Decimal("1.618"),
                f"wave C measured {_pct(rc)} of wave A",
            )
        )
    return PatternFit(
        pattern="zigzag",
        family=CORRECTIVE,
        variant=None,
        labels=ABC_LABELS[: len(p)],
        rules_applied=ZIGZAG_RULES,
        allowances=tuple(allowances),
        guidelines=tuple(checks),
        complete=complete,
    )


# ── corrective: flat (Lesson 9) ──────────────────────────────────────────

FLAT_RULES = (
    "Wave B retraces at least 90% of wave A",
    "Wave C travels beyond the end of wave B",
)


def _fit_flat(p: list[Decimal], up: bool) -> PatternFit | None:
    """Flat 3-3-5, in its regular, expanded and running variants.

    The variant is read off the terminals: whether wave B ends beyond the start
    of wave A, and whether wave C reaches beyond the end of wave A. A running
    flat — B beyond A's origin but C failing to reach A's end — is the most
    interpretation-heavy of the three and is recorded as an allowance.
    """
    if len(p) < 3 or not _alternates(p):
        return None
    legs = _legs(p)
    rb = _ratio(legs[1], legs[0])
    if rb is None or rb < _FLAT_B_MINIMUM:
        return None

    complete = len(p) == 4
    allowances: list[str] = []
    if not complete:
        variant = "developing"
    elif p[2] < p[0] and p[3] <= p[1]:
        variant = "running"
        allowances.append("running flat: wave C failed to reach the end of wave A (Lesson 9)")
    elif p[2] < p[0]:
        variant = "expanded"
    else:
        variant = "regular"

    checks = [
        _check(
            "Wave B retraces 1.0-1.382 of wave A, the expanded-flat proportion (Lesson 21)",
            Decimal("1.0") <= rb <= Decimal("1.382"),
            f"wave B retraced {_pct(rb)} of wave A",
        )
    ]
    if complete:
        rc = _ratio(legs[2], legs[0])
        checks.append(
            _check(
                "Wave C is 1.0-1.618 of wave A (Lesson 21)",
                None if rc is None else Decimal("1.0") <= rc <= Decimal("1.618"),
                f"wave C measured {_pct(rc)} of wave A",
            )
        )
    return PatternFit(
        pattern="flat",
        family=CORRECTIVE,
        variant=variant,
        labels=ABC_LABELS[: len(p)],
        rules_applied=FLAT_RULES,
        allowances=tuple(allowances),
        guidelines=tuple(checks),
        complete=complete,
    )


# ── corrective: triangle (Lesson 10) ─────────────────────────────────────

TRIANGLE_RULES = (
    "Every leg alternates direction (a 3-3-3-3-3 structure)",
    "Successive legs contract monotonically, or expand monotonically — "
    "a triangle whose boundaries neither converge nor diverge is not a triangle",
)

_TRIANGLE_SIDEWAYS = Decimal("0.5")
"""A triangle is a sideways structure: net displacement over the whole pattern
is small relative to its first leg. Measured as a guideline, not a rule."""


def _fit_triangle(p: list[Decimal], up: bool) -> PatternFit | None:
    """Contracting or expanding triangle, labelled A-B-C-D-E.

    A four-terminal prefix is indistinguishable from a zigzag or a flat, so a
    triangle is offered only once at least four legs are confirmed and the
    contraction or expansion is therefore actually observable.
    """
    if len(p) < 5 or not _alternates(p):
        return None
    legs = [abs(leg) for leg in _legs(p)]
    contracting = all(legs[i] < legs[i - 2] for i in range(2, len(legs)))
    expanding = all(legs[i] > legs[i - 2] for i in range(2, len(legs)))
    if not contracting and not expanding:
        return None

    complete = len(p) == 6
    net = _ratio(p[-1] - p[0], _legs(p)[0])
    return PatternFit(
        pattern="triangle",
        family=CORRECTIVE,
        variant="contracting" if contracting else "expanding",
        labels=TRIANGLE_LABELS[: len(p)],
        rules_applied=TRIANGLE_RULES,
        allowances=(
            () if contracting else ("expanding triangle: the rarer of the two forms (Lesson 10)",)
        ),
        guidelines=(
            _check(
                "The structure moves sideways: small net displacement (Lesson 10)",
                None if net is None else net <= _TRIANGLE_SIDEWAYS,
                f"net displacement was {_pct(net)} of the first leg",
            ),
        ),
        complete=complete,
    )


# ── corrective: combinations (Lesson 11) ─────────────────────────────────

COMBINATION_RULES = (
    "Every component alternates direction",
    "The combination moves sideways: net displacement stays small relative to its first leg",
)

_COMBINATION_SIDEWAYS = Decimal("0.618")

_COMBINATION_ALLOWANCE = (
    "identified from proportion, not substructure: terminal geometry alone "
    "cannot separate a combination from a single correction — the reading rests "
    "on its sideways character (Lesson 11)"
)


def _fit_combination(p: list[Decimal], up: bool) -> PatternFit | None:
    """Double three (W-X-Y) and triple three (W-X-Y-X-Z).

    A combination shares its terminal skeleton with a zigzag (three legs) or a
    triangle (five legs); what distinguishes it is the substructure of each
    component, which terminals alone cannot show. Rather than assert it
    silently, the combination is offered only for a genuinely *sideways*
    sequence and always carries the allowance saying how it was identified.
    """
    if len(p) not in (4, 6) or not _alternates(p):
        return None
    net = _ratio(p[-1] - p[0], _legs(p)[0])
    if net is None or net > _COMBINATION_SIDEWAYS:
        return None
    double = len(p) == 4
    return PatternFit(
        pattern="double three" if double else "triple three",
        family=CORRECTIVE,
        variant=None,
        labels=(DOUBLE_THREE_LABELS if double else TRIPLE_THREE_LABELS),
        rules_applied=COMBINATION_RULES,
        allowances=(_COMBINATION_ALLOWANCE,),
        guidelines=(
            _check(
                "Components are of comparable size (Lesson 11)",
                _comparable(p),
                "component legs measured against the first leg",
            ),
        ),
        complete=True,
    )


def _comparable(p: list[Decimal]) -> bool:
    """Whether the advancing components of a combination are similar in size."""
    advances = [abs(leg) for leg in _legs(p)[::2]]
    longest, shortest = max(advances), min(advances)
    return shortest > _ZERO and longest / shortest <= Decimal("2.618")


# ── the registry ─────────────────────────────────────────────────────────

IMPULSE_LABELS = ("0", "1", "2", "3", "4", "5")
ABC_LABELS = ("0", "A", "B", "C")
TRIANGLE_LABELS = ("0", "A", "B", "C", "D", "E")
DOUBLE_THREE_LABELS = ("0", "W", "X", "Y")
TRIPLE_THREE_LABELS = ("0", "W", "X", "Y", "X", "Z")

MIN_WAVES = 2
"""A single leg is a move, not a structure."""

PATTERN_SPECS: tuple[PatternSpec, ...] = (
    PatternSpec("impulse", MOTIVE, IMPULSE_LABELS, 3, 6, _fit_impulse),
    PatternSpec("diagonal", MOTIVE, IMPULSE_LABELS, 6, 6, _fit_diagonal),
    PatternSpec("zigzag", CORRECTIVE, ABC_LABELS, 3, 4, _fit_zigzag),
    PatternSpec("flat", CORRECTIVE, ABC_LABELS, 3, 4, _fit_flat),
    PatternSpec("triangle", CORRECTIVE, TRIANGLE_LABELS, 5, 6, _fit_triangle),
    PatternSpec("double three", CORRECTIVE, DOUBLE_THREE_LABELS, 4, 4, _fit_combination),
    PatternSpec("triple three", CORRECTIVE, TRIPLE_THREE_LABELS, 6, 6, _fit_combination),
)
"""Every structure the platform models, in a fixed order so that ties between
equally-scored candidates always break the same way (the determinism contract)."""


def normalise(prices: list[Decimal], up: bool) -> list[Decimal]:
    """Sign-normalise terminals so the first leg always advances."""
    sign = Decimal("1") if up else Decimal("-1")
    return [sign * price for price in prices]
