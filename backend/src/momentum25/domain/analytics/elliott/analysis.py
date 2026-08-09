"""Orchestration: pivots -> candidate counts -> ranking -> degree hierarchy.

This module owns the result shape the API returns and the assembly order, and
nothing else: every rule lives in :mod:`.patterns`, every ratio in
:mod:`.fibonacci`, every corroboration in :mod:`.personality`, and the ordering
method in :mod:`.ranking`.

Degrees (Frost & Prechter, Lesson 1) are inferred from the span of each labelled
structure in trading sessions. A degree cannot be established absolutely from
one series, so a degree name here describes the span of the structure, not a
claim about its place in a larger hierarchy. The hierarchy itself is built
top-down: the largest structure the history supports is labelled first, then each
of its legs is re-pivoted at a finer reversal size and labelled in turn, to a
bounded depth. Every child therefore nests inside its parent leg by construction.

Pure and deterministic. No I/O, no clock, no randomness. Nothing here produces a
target price, a profit projection, an R-multiple or a buy/sell verdict, and no
value it returns is an input to the Momentum25 score, ranking, gates, Trend
Template, Relative Strength or stop-loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from momentum25.domain.analytics.elliott import fibonacci, patterns, personality, ranking
from momentum25.domain.analytics.elliott.fibonacci import (
    FibonacciRelationship,
    ProjectionZone,
)
from momentum25.domain.analytics.elliott.patterns import GuidelineCheck, PatternFit
from momentum25.domain.analytics.elliott.personality import (
    PersonalityCheck,
    PersonalityContext,
)
from momentum25.domain.analytics.elliott.pivots import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    Pivot,
    zigzag_pivots,
)
from momentum25.domain.analytics.elliott.ranking import ConfidenceComponent
from momentum25.domain.entities.market_data import OHLCVBar

_DEGREE_BANDS: tuple[tuple[int, str], ...] = (
    (60, "Minute"),
    (250, "Minor"),
    (750, "Intermediate"),
)
_LARGEST_DEGREE = "Primary"

MAX_SUBDIVISION_DEPTH = 3
"""Nested degrees labelled below the top count.

Subdivision is the only part of the analysis whose cost grows with itself: each
level re-pivots and re-labels every leg of the level above. Three levels is what
a daily series with a few hundred bars can actually support — below that the
finer threshold floors out at 1% and the "structure" is noise.
"""

_SUBDIVISION_DIVISOR = Decimal("3")
_MIN_THRESHOLD_PCT = Decimal("1")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class WaveLabel:
    """One labelled wave terminal: the pivot at which that wave ended."""

    label: str
    bar_date: date
    price: Decimal


@dataclass(frozen=True, slots=True)
class Subdivision:
    """Finer-degree labelling of the leg ending at ``of_label``.

    Recursive: a subdivision carries its own subdivisions, so the response is a
    tree of degrees rather than a single flat level.
    """

    of_label: str
    degree: str
    pattern: str
    variant: str | None
    labels: tuple[WaveLabel, ...]
    position_fit: GuidelineCheck
    subdivisions: tuple[Subdivision, ...] = ()


@dataclass(frozen=True, slots=True)
class WaveCount:
    """One internally consistent labelling of the pivot sequence."""

    pattern: str
    family: str
    variant: str | None
    direction: str  # "up" | "down"
    degree: str
    labels: tuple[WaveLabel, ...]
    current_position: str
    rules_applied: tuple[str, ...]
    allowances: tuple[str, ...] = ()
    guideline_checks: tuple[GuidelineCheck, ...] = ()
    personality: tuple[PersonalityCheck, ...] = ()
    price_relationships: tuple[FibonacciRelationship, ...] = ()
    time_relationships: tuple[FibonacciRelationship, ...] = ()
    labelling_confidence: Decimal = Decimal("0")
    labelling_confidence_basis: str = ranking.LABELLING_CONFIDENCE_BASIS
    confidence_components: tuple[ConfidenceComponent, ...] = ()
    # True when the count runs through the most recent confirmed pivot, i.e. it
    # describes the structure now in progress rather than a completed one that
    # later price action has already left behind.
    is_current: bool = True
    projection: ProjectionZone | None = None
    subdivisions: tuple[Subdivision, ...] = ()


@dataclass(frozen=True, slots=True)
class ElliottWaveAnalysis:
    """The full labelling result for one symbol."""

    symbol: str
    as_of: date | None
    threshold_pct: Decimal
    # The reversal size the *top* degree was labelled at: the requested
    # threshold coarsened until the pivots describe one large structure rather
    # than dozens of small ones. Equal to `threshold_pct` when no coarsening was
    # needed.
    top_degree_threshold_pct: Decimal
    bars_analyzed: int
    pivots: tuple[Pivot, ...]
    candidates: tuple[WaveCount, ...] = ()
    ranking_rationale: tuple[str, ...] = ()
    ranking_method: str = ranking.RANKING_METHOD
    notes: tuple[str, ...] = field(default_factory=tuple)


def _degree(span_sessions: int) -> str:
    for limit, name in _DEGREE_BANDS:
        if span_sessions < limit:
            return name
    return _LARGEST_DEGREE


def _position_text(fit: PatternFit, pattern_labels: tuple[str, ...]) -> str:
    """Describe where the labelled structure stands, without overstating it."""
    labelled = len(fit.labels) - 1
    if fit.complete:
        span = "-".join(pattern_labels[1:])
        return f"{fit.pattern.capitalize()} complete: waves {span} labelled"
    return (
        f"Wave {pattern_labels[labelled]} complete, wave {pattern_labels[labelled + 1]} in progress"
    )


def _stale_suffix(ends: date) -> str:
    return (
        f" as of {ends.isoformat()}; later price action does not extend this count, "
        "so no projection is offered"
    )


# ── candidate generation ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    count: WaveCount
    evidence: ranking.CountEvidence


def _build_count(
    spec: patterns.PatternSpec,
    fit: PatternFit,
    segment: tuple[Pivot, ...],
    up: bool,
    is_current: bool,
    degree: str,
    sessions: dict[date, int],
) -> WaveCount:
    prices = [p.price for p in segment]
    dates = [p.bar_date for p in segment]
    position = _position_text(fit, spec.labels)
    price_rel = fibonacci.price_relationships(fit.pattern, prices)
    time_rel = fibonacci.time_relationships(fit.pattern, dates, sessions)
    return WaveCount(
        pattern=fit.pattern,
        family=fit.family,
        variant=fit.variant,
        direction="up" if up else "down",
        degree=degree,
        labels=tuple(WaveLabel(fit.labels[i], p.bar_date, p.price) for i, p in enumerate(segment)),
        current_position=position if is_current else position + _stale_suffix(dates[-1]),
        rules_applied=fit.rules_applied,
        allowances=fit.allowances,
        guideline_checks=fit.guidelines,
        price_relationships=price_rel,
        time_relationships=time_rel,
        is_current=is_current,
        projection=(
            fibonacci.projection(fit.pattern, prices, up, fit.variant) if is_current else None
        ),
    )


def _candidates_at(
    pivots: tuple[Pivot, ...],
    start: int,
    span_sessions: int,
    last_pivot_date: date,
    sessions: dict[date, int],
) -> list[_Candidate]:
    """Every admissible count anchored at ``pivots[start]``, longest per pattern.

    A structure that breaks a cardinal rule at wave *n* is not discarded
    outright: the labelling is truncated to the longest prefix that satisfies
    every rule of that pattern, which is what a rule violation actually tells you
    — the count cannot be extended that far, not that no count exists.
    """
    up = pivots[start].kind == "L"
    found: list[_Candidate] = []
    total_sessions = len(sessions) or span_sessions

    for spec in patterns.PATTERN_SPECS:
        for size in range(spec.max_terminals, spec.min_terminals - 1, -1):
            segment = tuple(pivots[start : start + size])
            if len(segment) != size or size - 1 < patterns.MIN_WAVES:
                continue
            prices = patterns.normalise([p.price for p in segment], up)
            fit = spec.fit(prices, up)
            if fit is None:
                continue

            first, last = segment[0].bar_date, segment[-1].bar_date
            if first in sessions and last in sessions:
                span = sessions[last] - sessions[first] + 1
            else:
                span = span_sessions
            count = _build_count(
                spec,
                fit,
                segment,
                up,
                segment[-1].bar_date == last_pivot_date,
                _degree(span),
                sessions,
            )
            found.append(
                _Candidate(
                    start=start,
                    count=count,
                    evidence=ranking.CountEvidence(
                        is_current=count.is_current,
                        labelled_waves=len(fit.labels) - 1,
                        pattern_waves=len(spec.labels) - 1,
                        history_share=(
                            Decimal(span) / Decimal(total_sessions) if total_sessions else None
                        ),
                        price_adherence=fibonacci.adherence(count.price_relationships),
                        time_adherence=fibonacci.adherence(count.time_relationships),
                        personality_corroboration=None,
                        allowance_count=len(fit.allowances),
                    ),
                )
            )
            break  # longest admissible prefix of this pattern only

    return found


def label_waves(
    pivots: tuple[Pivot, ...],
    span_sessions: int,
    sessions: dict[date, int] | None = None,
    context: PersonalityContext | None = None,
) -> tuple[tuple[WaveCount, ...], tuple[str, ...]]:
    """Return ``(ranked counts, rationale)`` over ``pivots``.

    Ranking follows the two-stage method documented in :mod:`.ranking`: rule
    admissibility first and absolutely, then a weighted, transparent ordering.
    At most one candidate per pattern is returned, because a second anchor of the
    same pattern is a variation on one reading rather than a competing one, and
    only candidates within :data:`~.ranking.COMPETITIVE_MARGIN` of the best are
    offered at all.
    """
    if len(pivots) < 2:
        return (), ()
    sessions = sessions or {}

    candidates: list[_Candidate] = []
    for start in range(len(pivots) - 1):
        candidates.extend(
            _candidates_at(pivots, start, span_sessions, pivots[-1].bar_date, sessions)
        )
    if not candidates:
        return (), ()

    scored: list[tuple[Decimal, _Candidate, tuple[ConfidenceComponent, ...]]] = []
    for candidate in candidates:
        evidence = candidate.evidence
        if context is not None:
            checks = personality.evaluate(
                candidate.count.pattern,
                tuple((w.label, w.bar_date, w.price) for w in candidate.count.labels),
                context,
            )
            candidate = replace(
                candidate,
                count=replace(candidate.count, personality=checks),
                evidence=replace(
                    evidence, personality_corroboration=personality.corroboration(checks)
                ),
            )
        total, components = ranking.score(candidate.evidence)
        scored.append((total, candidate, components))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].start,
            item[1].count.pattern,
            len(item[1].count.labels),
        )
    )

    best_total = scored[0][0]
    chosen: list[tuple[Decimal, _Candidate, tuple[ConfidenceComponent, ...]]] = []
    seen: set[str] = set()
    terminus = scored[0][1].count.labels[-1].bar_date
    for item in scored:
        if item[1].count.pattern in seen:
            continue
        if item[0] < best_total - ranking.COMPETITIVE_MARGIN:
            continue
        # A competing count must explain the *same* price action: one that stops
        # earlier is a fragment nested inside the top count, not another reading
        # of it, and offering it as an alternative would invent a contest.
        if chosen and item[1].count.labels[-1].bar_date != terminus:
            continue
        seen.add(item[1].count.pattern)
        chosen.append(item)
        if len(chosen) == ranking.MAX_CANDIDATES:
            break

    counts = tuple(
        replace(
            item[1].count,
            labelling_confidence=item[0],
            confidence_components=item[2],
        )
        for item in chosen
    )

    best_name = _display_name(counts[0])
    rationale = [
        f"Top-ranked: the {best_name} count scores {chosen[0][0]:.0f} of 100 on "
        "rule admissibility, guideline adherence and structural cleanliness."
    ]
    rationale.extend(
        ranking.rationale(
            (best_name, chosen[0][2], chosen[0][0]),
            (_display_name(item[1].count), item[2], item[0]),
        )
        for item in chosen[1:]
    )
    return counts, tuple(rationale)


def _display_name(count: WaveCount) -> str:
    """Human name for a count, used in the ranking explanation."""
    return f"{count.variant} {count.pattern}" if count.variant else count.pattern


# ── recursive degree hierarchy ───────────────────────────────────────────

# Which family the Wave Principle expects inside each labelled position: motive
# waves subdivide into motive structures, corrective waves into corrective ones
# (Frost & Prechter, Lesson 3). Zigzags are 5-3-5 and flats 3-3-5, so wave A
# differs between them; triangles are 3-3-3-3-3 throughout. This is a
# *guideline*: a mismatch is reported as contradicting evidence, never enforced.
_EXPECTED_CHILD_FAMILY: dict[str, dict[str, str]] = {
    "impulse": {
        "1": patterns.MOTIVE,
        "2": patterns.CORRECTIVE,
        "3": patterns.MOTIVE,
        "4": patterns.CORRECTIVE,
        "5": patterns.MOTIVE,
    },
    "diagonal": {
        "1": patterns.CORRECTIVE,
        "2": patterns.CORRECTIVE,
        "3": patterns.CORRECTIVE,
        "4": patterns.CORRECTIVE,
        "5": patterns.CORRECTIVE,
    },
    "zigzag": {"A": patterns.MOTIVE, "B": patterns.CORRECTIVE, "C": patterns.MOTIVE},
    "flat": {"A": patterns.CORRECTIVE, "B": patterns.CORRECTIVE, "C": patterns.MOTIVE},
    "triangle": dict.fromkeys(("A", "B", "C", "D", "E"), patterns.CORRECTIVE),
    "double three": dict.fromkeys(("W", "X", "Y"), patterns.CORRECTIVE),
    "triple three": dict.fromkeys(("W", "X", "Y", "Z"), patterns.CORRECTIVE),
}

# A diagonal's position — leading (wave 1 or A) or ending (wave 5 or C) — is a
# claim about its parent, so it can only be named once the parent is known.
_LEADING_POSITIONS = frozenset({"1", "A", "W"})
_ENDING_POSITIONS = frozenset({"5", "C", "Z"})


def _position_fit(parent_pattern: str, of_label: str, child: WaveCount) -> GuidelineCheck:
    expected = _EXPECTED_CHILD_FAMILY.get(parent_pattern, {}).get(of_label)
    name = f"Wave {of_label} subdivides into a {expected or 'structure of unstated'} form"
    if expected is None:
        return GuidelineCheck(name, patterns.NOT_MEASURABLE, "no expectation is defined")
    holds = child.family == expected
    return GuidelineCheck(
        name,
        patterns.SUPPORTING if holds else patterns.CONTRADICTING,
        f"the finer degree labelled a {child.pattern}, a {child.family} structure",
    )


def _diagonal_variant(of_label: str, child: WaveCount) -> str | None:
    if child.pattern != "diagonal":
        return child.variant
    if of_label in _LEADING_POSITIONS:
        return f"{child.variant} leading"
    if of_label in _ENDING_POSITIONS:
        return f"{child.variant} ending"
    return child.variant


def _subdivide(
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    parent_pattern: str,
    labels: tuple[WaveLabel, ...],
    threshold_pct: Decimal,
    finest_pct: Decimal,
    sessions: dict[date, int],
    depth: int,
) -> tuple[Subdivision, ...]:
    """Label ``depth`` further degrees inside each leg of a labelled structure.

    Each adjacent label pair ``(a, b)`` bounds a leg; the bars in
    ``[a.bar_date, b.bar_date]`` are re-pivoted at a finer reversal size and
    labelled with the same rule set and the same ranking, so a child count is
    admissible by exactly the criteria its parent was. A subdivision is emitted
    only when the finer structure reaches at least three confirmed labels — two
    waves is not a structure worth drawing.

    Recursion stops at ``finest_pct``: the caller's requested reversal size is
    the finest degree the reader asked to see, and labelling below it would
    invent structure they did not ask for.

    Subdivisions carry no projection zone and no confidence score of their own:
    they are labelling depth, and the count that owns them is what the reader is
    being asked to judge.
    """
    if depth <= 0:
        return ()
    finer = max(threshold_pct / _SUBDIVISION_DIVISOR, finest_pct, _MIN_THRESHOLD_PCT)
    if finer >= threshold_pct:
        return ()

    subdivisions: list[Subdivision] = []
    for a, b in zip(labels, labels[1:], strict=False):
        segment = [bar for bar in bars if a.bar_date <= bar.date <= b.bar_date]
        sub_pivots = zigzag_pivots(segment, finer)
        children, _ = label_waves(sub_pivots, len(segment), sessions)
        if not children or len(children[0].labels) < 3:
            continue
        child = children[0]
        subdivisions.append(
            Subdivision(
                of_label=b.label,
                degree=child.degree,
                pattern=child.pattern,
                variant=_diagonal_variant(b.label, child),
                labels=child.labels,
                position_fit=_position_fit(parent_pattern, b.label, child),
                subdivisions=_subdivide(
                    segment, child.pattern, child.labels, finer, finest_pct, sessions, depth - 1
                ),
            )
        )
    return tuple(subdivisions)


def _span_sessions(sessions: dict[date, int], labels: tuple[WaveLabel, ...]) -> int:
    """Sessions the count itself spans, not the sessions loaded.

    Degree describes the labelled structure. Sizing it by the length of the
    requested history called a three-week count "Primary" purely because 500
    bars were fetched.
    """
    first, last = labels[0].bar_date, labels[-1].bar_date
    if first not in sessions or last not in sessions:
        return 0
    return sessions[last] - sessions[first] + 1


TOP_DEGREE_MAX_PIVOTS = 12
"""Pivots the top degree may rest on.

A single structure is at most six terminals, so a pivot set much larger than
that is not one structure — it is many, and labelling the largest of them
requires a coarser reversal size. Twelve leaves room for competing counts
anchored a little earlier without letting the top level collapse onto the last
handful of swings.
"""

TOP_DEGREE_MIN_PIVOTS = 4
"""Below this a coarsening step has thrown away the structure it was meant to
reveal, so the previous, finer threshold stands."""

_MAX_THRESHOLD_PCT = Decimal("50")


def _top_degree_threshold(
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar], threshold_pct: Decimal
) -> tuple[Decimal, tuple[Pivot, ...]]:
    """Coarsen the reversal size until the pivots describe one large structure.

    The requested threshold is the finest degree the caller wants to see. Taken
    as the *top* degree it would label whatever small structure happens to sit
    at the right-hand edge — five hundred bars at a 5% reversal produce dozens
    of pivots, and the largest count that can be built from six of them spans a
    few weeks. Stepping the threshold up by the same factor subdivision steps it
    down (:data:`_SUBDIVISION_DIVISOR`) keeps the degrees commensurate: each
    level is exactly one subdivision step from the one above.
    """
    threshold = threshold_pct
    pivots = zigzag_pivots(bars, threshold)
    while len(pivots) > TOP_DEGREE_MAX_PIVOTS:
        coarser = threshold * _SUBDIVISION_DIVISOR
        if coarser > _MAX_THRESHOLD_PCT:
            break
        candidate = zigzag_pivots(bars, coarser)
        if len(candidate) < TOP_DEGREE_MIN_PIVOTS:
            break
        threshold, pivots = coarser, candidate
    return threshold, pivots


def analyze_elliott_wave(
    symbol: str,
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
    context: PersonalityContext | None = None,
) -> ElliottWaveAnalysis:
    """Detect pivots, label every admissible structure and rank the candidates.

    ``threshold_pct`` is the *finest* reversal size the caller wants labelled.
    The top degree is coarsened away from it (see :func:`_top_degree_threshold`)
    so the highest-level count describes the largest structure the history
    supports, and the finer degrees are then recovered by subdivision.
    """
    sessions = {bar.date: i for i, bar in enumerate(bars)}
    as_of = bars[-1].date if bars else None
    top_threshold, pivots = _top_degree_threshold(bars, threshold_pct)

    counts, rationale = label_waves(pivots, len(bars), sessions, context)
    counts = tuple(
        replace(
            count,
            degree=_degree(_span_sessions(sessions, count.labels)),
            subdivisions=_subdivide(
                bars,
                count.pattern,
                count.labels,
                top_threshold,
                threshold_pct,
                sessions,
                MAX_SUBDIVISION_DEPTH,
            ),
        )
        for count in counts
    )

    notes: list[str] = []
    if top_threshold != threshold_pct:
        notes.append(
            f"The top degree is labelled at a {top_threshold}% reversal threshold — coarsened "
            f"from the requested {threshold_pct}% so the highest level describes the largest "
            "structure the loaded history supports; finer degrees are labelled down to "
            f"{threshold_pct}% by subdivision."
        )
    if len(pivots) < 2:
        notes.append(
            f"Only {len(pivots)} confirmed pivot(s) at a {top_threshold}% reversal threshold — "
            "too few to label a wave structure."
        )
    elif not counts:
        notes.append(
            "No pivot sequence in the visible history satisfies the rules of any modelled "
            "structure, so no count is asserted."
        )
    if counts and not counts[0].is_current:
        notes.append(
            "No count reaching the latest confirmed pivot satisfies the rules; the labelled "
            "structure ends earlier and no projection is offered."
        )
    if len(counts) == 1:
        notes.append("The pivots support a single competitive count; no alternative is asserted.")
    if counts and not counts[0].subdivisions:
        notes.append(
            "No leg of the top-ranked count contains enough confirmed pivots to label a "
            "finer degree."
        )

    return ElliottWaveAnalysis(
        symbol=symbol,
        as_of=as_of,
        threshold_pct=threshold_pct,
        top_degree_threshold_pct=top_threshold,
        bars_analyzed=len(bars),
        pivots=pivots,
        candidates=counts,
        ranking_rationale=rationale,
        notes=tuple(notes),
    )
