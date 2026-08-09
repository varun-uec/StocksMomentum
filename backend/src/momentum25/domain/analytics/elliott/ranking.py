"""How competing wave counts are ranked, and how confident the labelling is.

The method, stated in full
--------------------------
Elliott labelling is under-determined: several rule-legal counts routinely
explain the same pivots. Rather than pick one silently, the platform ranks them
in two deliberately separated stages.

**Stage 1 — admissibility (binary).** A sequence that breaks a *rule* of the
pattern being tested is not that pattern, full stop. It is never scored, never
displayed and never ranked; the labelling is instead truncated to the longest
prefix that satisfies every rule, which is what a rule violation actually tells
you — that the count cannot be extended that far, not that no count exists. Rules
are never traded off against guidelines, so nothing shown here ever breaks one.

**Stage 2 — ordering (weighted, transparent).** Admissible candidates are scored
0-100 out of six named components. The weights encode a single editorial
judgment, stated here so it can be argued with:

======================  ======  ==========================================
component               weight  why it carries that weight
======================  ======  ==========================================
currency                    25  A count that terminated months ago describes
                                history, not the structure now in progress.
                                This is the single most decisive fact about a
                                count's relevance, so it carries the most.
structural completeness     20  A count that labels more of its pattern, more
                                waves in absolute terms, and more of the visible
                                history rests on more confirmed pivots and
                                leaves less to interpretation. All three are
                                averaged: scoring only the fraction of a
                                pattern's own length would rank every three-leg
                                correction above every five-wave impulse.
price Fibonacci             20  Lesson 21's price proportions are the most
                                extensively documented guidelines in the text
                                and the ones practitioners weigh most heavily.
personality corroboration   15  Independent confirmation from volume and
                                momentum (Lesson 14). Weighted below the price
                                proportions because it is indirect evidence
                                about a labelling, and often unmeasurable.
time Fibonacci              10  Real, documented, but acknowledged in the text
                                itself as looser than the price relationships.
structural cleanliness      10  Each allowance the count needed - a truncated
                                fifth, a running flat, an expanding triangle -
                                is interpretation the reader must accept. A
                                textbook count outranks a rule-legal but
                                interpretation-heavy one.
======================  ======  ==========================================

A component that cannot be measured (no indicator history, too few waves for a
ratio) scores the neutral 0.5 rather than 0 or 1: an unmeasured component must
neither reward nor punish the count that carries it, or absent data would masquerade
as evidence.

Ties break deterministically on ``(-score, earliest anchor, pattern name, label
count)``, so identical bars always produce an identical order.

Confidence-in-labelling
-----------------------
The same 0-100 total is surfaced as the count's ``labelling_confidence``. It
measures **how cleanly the price action fits the labelled Elliott structure** —
how much of the theory is satisfied outright versus how much interpretation the
label required. It is not a forecast, not a probability that the count will play
out, and not a probability of profit. It is not wired into the Momentum25 score,
ranking, gates or any strategy decision.

Pure and deterministic. No I/O, no clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_QUANTUM = Decimal("0.01")
"""Egress precision for every score this module publishes (ADR-009). Rounding is
applied once, at construction, so the number displayed is the number that
ordered the candidates."""

_NEUTRAL = Decimal("0.5")
"""Score awarded to a component that could not be measured (see module docstring)."""

_ZERO = Decimal("0")
_ONE = Decimal("1")

WEIGHT_CURRENCY = Decimal("25")
WEIGHT_COMPLETENESS = Decimal("20")
WEIGHT_PRICE_FIBONACCI = Decimal("20")
WEIGHT_PERSONALITY = Decimal("15")
WEIGHT_TIME_FIBONACCI = Decimal("10")
WEIGHT_CLEANLINESS = Decimal("10")

_LONGEST_PATTERN_WAVES = Decimal("5")
"""Waves in the longest structures modelled (impulse, diagonal, triangle,
triple three). Used to score labelled waves in absolute terms alongside the
fraction-of-pattern reading."""

_ALLOWANCE_PENALTY = Decimal("0.34")
"""Cleanliness lost per allowance invoked: three allowances exhaust the
component, which is about as much interpretation as a displayable count can
carry."""

COMPETITIVE_MARGIN = Decimal("20")
"""A candidate is shown as a competing count only when it scores within this
many points of the best. Beyond it the reading is not meaningfully competitive,
and showing it would imply a contest that does not exist."""

MAX_CANDIDATES = 3
"""Top-N counts returned. Three is the most a reader can hold side by side."""

RANKING_METHOD = (
    "Candidates are ranked in two stages. First, admissibility: a sequence that breaks "
    "a rule of the pattern being tested is never labelled as that pattern, and is "
    "truncated to its longest rule-satisfying prefix instead — rules are never traded "
    "off against guidelines. Second, ordering: admissible counts are scored out of 100 "
    "on currency (25), structural completeness (20), price Fibonacci adherence (20), "
    "wave personality corroboration (15), time Fibonacci adherence (10) and structural "
    "cleanliness (10). A component that cannot be measured scores neutral, so absent "
    "data never masquerades as evidence."
)

LABELLING_CONFIDENCE_BASIS = (
    "How cleanly the price action satisfies the Elliott Wave rules and guidelines "
    "for this labelling, against how much interpretation the label required. "
    "It measures fit to the theory — it is not a forecast and not a probability."
)


@dataclass(frozen=True, slots=True)
class ConfidenceComponent:
    """One weighted component of the labelling-confidence score."""

    name: str
    weight: Decimal
    score: Decimal  # 0-1
    points: Decimal  # weight * score
    detail: str


@dataclass(frozen=True, slots=True)
class CountEvidence:
    """Everything stage 2 needs about one admissible candidate."""

    is_current: bool
    labelled_waves: int
    pattern_waves: int
    history_share: Decimal | None  # sessions the count spans / sessions available
    price_adherence: Decimal | None
    time_adherence: Decimal | None
    personality_corroboration: Decimal | None
    allowance_count: int


def _component(
    name: str, weight: Decimal, score: Decimal | None, detail: str
) -> ConfidenceComponent:
    measured = (_NEUTRAL if score is None else min(max(score, _ZERO), _ONE)).quantize(_QUANTUM)
    return ConfidenceComponent(
        name=name,
        weight=weight,
        score=measured,
        points=(weight * measured).quantize(_QUANTUM),
        detail=detail if score is not None else f"{detail} — not measurable, scored neutral",
    )


def score(evidence: CountEvidence) -> tuple[Decimal, tuple[ConfidenceComponent, ...]]:
    """Return ``(total 0-100, components)`` for one admissible candidate."""
    # Three readings of "how much of the structure is actually pinned down by
    # confirmed pivots", averaged. The absolute-wave term matters: scoring only
    # the fraction of a pattern's own length would rank every three-leg
    # correction above every five-wave impulse, because three legs complete a
    # zigzag but only start an impulse — a scoring artefact, not a fact about
    # the price action.
    parts = [
        Decimal(evidence.labelled_waves) / Decimal(evidence.pattern_waves),
        min(Decimal(evidence.labelled_waves) / _LONGEST_PATTERN_WAVES, _ONE),
    ]
    if evidence.history_share is not None:
        parts.append(evidence.history_share)
    completeness = sum(parts, _ZERO) / Decimal(len(parts))
    span = (
        "span unavailable"
        if evidence.history_share is None
        else f"spanning {evidence.history_share:.0%} of the visible history"
    )

    components = (
        _component(
            "Currency",
            WEIGHT_CURRENCY,
            _ONE if evidence.is_current else _ZERO,
            (
                "the count runs through the latest confirmed pivot"
                if evidence.is_current
                else "the count ended before the latest confirmed pivot"
            ),
        ),
        _component(
            "Structural completeness",
            WEIGHT_COMPLETENESS,
            completeness,
            f"{evidence.labelled_waves} of {evidence.pattern_waves} waves labelled, {span}",
        ),
        _component(
            "Price Fibonacci adherence",
            WEIGHT_PRICE_FIBONACCI,
            evidence.price_adherence,
            "mean proximity of the wave ratios to their nearest Fibonacci value",
        ),
        _component(
            "Wave personality corroboration",
            WEIGHT_PERSONALITY,
            evidence.personality_corroboration,
            "share of measurable volume and momentum checks supporting the labelling",
        ),
        _component(
            "Time Fibonacci adherence",
            WEIGHT_TIME_FIBONACCI,
            evidence.time_adherence,
            "mean proximity of the wave durations to their nearest Fibonacci value",
        ),
        _component(
            "Structural cleanliness",
            WEIGHT_CLEANLINESS,
            _ONE - _ALLOWANCE_PENALTY * Decimal(evidence.allowance_count),
            (
                "no interpretive allowance was needed"
                if evidence.allowance_count == 0
                else f"{evidence.allowance_count} interpretive allowance(s) invoked"
            ),
        ),
    )
    return sum((c.points for c in components), _ZERO).quantize(_QUANTUM), components


def rationale(
    best: tuple[str, tuple[ConfidenceComponent, ...], Decimal],
    other: tuple[str, tuple[ConfidenceComponent, ...], Decimal],
) -> str:
    """Explain, in one sentence, what separates ``best`` from ``other``."""
    best_name, best_components, best_total = best
    other_name, other_components, other_total = other
    gaps = sorted(
        (
            (b.points - o.points, b.name)
            for b, o in zip(best_components, other_components, strict=True)
        ),
        key=lambda gap: (-gap[0], gap[1]),
    )
    decisive = [name for points, name in gaps if points > _ZERO][:2]
    if not decisive:
        return (
            f"The {best_name} count scores {best_total:.0f} against the {other_name} "
            f"count's {other_total:.0f}; no single component separates them, and the "
            "order is settled by the deterministic tie-break."
        )
    return (
        f"The {best_name} count scores {best_total:.0f} against the {other_name} "
        f"count's {other_total:.0f}, ahead chiefly on {' and '.join(decisive).lower()}."
    )
