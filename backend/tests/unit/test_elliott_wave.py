"""Elliott Wave labelling tests — hand-built series with known pivots.

Each pattern gets a constructed textbook case and, where the pattern has rules,
a rejection case per rule. Ranking, degree recursion, personality corroboration
and determinism are covered end to end.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from momentum25.domain.analytics.elliott import fibonacci, patterns, personality, ranking
from momentum25.domain.analytics.elliott_wave import (
    PersonalityContext,
    Pivot,
    analyze_elliott_wave,
    label_waves,
    zigzag_pivots,
)
from momentum25.domain.entities.market_data import OHLCVBar

_START = date(2024, 1, 1)


def _bars(closes: list[float], volumes: list[int] | None = None) -> list[OHLCVBar]:
    """One bar per close, with high == low == close so pivots are unambiguous."""
    return [
        OHLCVBar(
            date=_START + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=volumes[i] if volumes else 1000,
        )
        for i, c in enumerate(closes)
    ]


def _ramp(start: float, end: float, steps: int = 5) -> list[float]:
    """Linear path from ``start`` to ``end`` (exclusive of ``start``)."""
    step = (end - start) / steps
    return [start + step * (i + 1) for i in range(steps)]


def _closes(points: list[float]) -> list[float]:
    closes = [points[0]]
    for a, b in zip(points, points[1:], strict=False):
        closes.extend(_ramp(a, b))
    return closes


def _path(points: list[float]) -> list[OHLCVBar]:
    return _bars(_closes(points))


def _pivots(kinds_prices: list[tuple[str, float]]) -> tuple[Pivot, ...]:
    return tuple(
        Pivot(_START + timedelta(days=i * 10), Decimal(str(p)), k)
        for i, (k, p) in enumerate(kinds_prices)
    )


def _top(kinds_prices: list[tuple[str, float]], span: int = 300):
    counts, _ = label_waves(_pivots(kinds_prices), span_sessions=span)
    return counts[0] if counts else None


def _labels(count) -> list[str]:
    return [w.label for w in count.labels]


def _fit(pattern: str, prices: list[float], up: bool = True):
    """Run one pattern's rules directly over normalised terminals."""
    spec = next(s for s in patterns.PATTERN_SPECS if s.pattern == pattern)
    return spec.fit(patterns.normalise([Decimal(str(p)) for p in prices], up), up)


# ── zigzag pivot detection ───────────────────────────────────────────────


def test_zigzag_finds_alternating_confirmed_pivots() -> None:
    pivots = zigzag_pivots(_path([100, 130, 110, 160, 140, 190]), Decimal("5"))
    # The final leg's extreme (190) is unconfirmed -- no reversal followed it.
    assert [p.kind for p in pivots] == ["L", "H", "L", "H", "L"]
    assert [float(p.price) for p in pivots] == [100, 130, 110, 160, 140]


def test_zigzag_ignores_moves_below_threshold() -> None:
    assert zigzag_pivots(_path([100, 102, 100, 102, 100]), Decimal("10")) == ()


def test_zigzag_rejects_a_non_positive_threshold() -> None:
    with pytest.raises(ValueError, match="positive"):
        zigzag_pivots(_path([100, 130]), Decimal("0"))


def test_one_wide_range_bar_is_not_both_a_swing_high_and_a_swing_low() -> None:
    # A single bar spanning more than the reversal threshold used to confirm a
    # high against itself and then seed the low tracker from the same bar,
    # emitting an H and an L on the identical date.
    def wide(day: int, low: float, high: float) -> OHLCVBar:
        return OHLCVBar(
            date=_START + timedelta(days=day),
            open=Decimal(str(high)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(low)),
            volume=1000,
        )

    pivots = zigzag_pivots(
        [
            wide(0, 100, 100),
            wide(1, 100, 120),
            wide(2, 100, 121),
            wide(3, 100, 101),
            wide(4, 130, 130),
        ],
        Decimal("5"),
    )
    dates = [p.bar_date for p in pivots]
    assert len(dates) == len(set(dates))
    kinds = [p.kind for p in pivots]
    assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))


# ── impulse: the three cardinal rules (Lesson 2) ─────────────────────────


def test_valid_five_wave_impulse_is_labelled() -> None:
    count = _top([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160), ("H", 200)])
    assert count is not None
    assert count.pattern == "impulse"
    assert count.family == patterns.MOTIVE
    assert _labels(count) == ["0", "1", "2", "3", "4", "5"]
    assert count.current_position == "Impulse complete: waves 1-2-3-4-5 labelled"


def test_rule_1_wave_2_retracing_beyond_wave_1_start_is_rejected() -> None:
    assert _fit("impulse", [100, 130, 95, 180, 160, 200]) is None


def test_rule_2_wave_3_shortest_is_rejected() -> None:
    # w1 = 40, w3 = 20, w5 = 50 -> wave 3 is the shortest.
    assert _fit("impulse", [100, 140, 130, 150, 145, 195]) is None


def test_rule_3_wave_4_overlapping_wave_1_is_rejected_for_an_impulse() -> None:
    assert _fit("impulse", [100, 130, 115, 180, 125, 200]) is None


def test_a_rule_break_truncates_the_count_rather_than_discarding_it() -> None:
    # A rule violation at wave 4 says the count cannot be extended that far, not
    # that no count exists: the labelling truncates to the longest legal prefix.
    prices = [100, 130, 115, 180, 125, 200]
    assert _fit("impulse", prices) is None
    fit = _fit("impulse", prices[:4])
    assert fit is not None
    assert fit.labels == ("0", "1", "2", "3")


def test_wave_three_extension_is_named() -> None:
    fit = _fit("impulse", [100, 120, 110, 200, 180, 200.5])
    assert fit is not None
    assert fit.variant == "wave 3 extension"


def test_wave_five_extension_is_named() -> None:
    fit = _fit("impulse", [100, 120, 110, 140, 130, 260])
    assert fit is not None
    assert fit.variant == "wave 5 extension"


def test_truncated_fifth_is_valid_but_recorded_as_an_allowance() -> None:
    # Wave 5 tops at 178, below wave 3's 180: legal, but interpretive.
    fit = _fit("impulse", [100, 130, 115, 180, 160, 178])
    assert fit is not None
    assert any("truncated fifth" in a for a in fit.allowances)


# ── diagonals (Lesson 6) ─────────────────────────────────────────────────


def test_contracting_diagonal_permits_the_wave_4_wave_1_overlap() -> None:
    # w1=40 w2=-15 w3=35 w4=-13 w5=30, and wave 4 (147) sits inside wave 1 (140).
    fit = _fit("diagonal", [100, 140, 120, 155, 138, 165])
    assert fit is not None
    assert fit.pattern == "diagonal"
    assert fit.variant == "contracting"
    assert any("leading vs ending" in a for a in fit.allowances)


def test_expanding_diagonal_is_recognised() -> None:
    fit = _fit("diagonal", [100, 120, 110, 145, 118, 158])
    assert fit is not None
    assert fit.variant == "expanding"


def test_a_diagonal_is_not_offered_without_the_overlap() -> None:
    # A clean impulse must not also be labelled a diagonal: that would
    # manufacture a competing count out of the same terminals.
    assert _fit("diagonal", [100, 130, 115, 180, 160, 200]) is None


def test_a_diagonal_that_neither_contracts_nor_expands_is_rejected() -> None:
    assert _fit("diagonal", [100, 140, 125, 175, 130, 180]) is None


# ── zigzag correction (Lesson 8) ─────────────────────────────────────────


def test_zigzag_is_labelled_a_b_c() -> None:
    fit = _fit("zigzag", [200, 150, 180, 120], up=False)
    assert fit is not None
    assert fit.pattern == "zigzag"
    assert fit.labels == ("0", "A", "B", "C")
    assert fit.family == patterns.CORRECTIVE


def test_zigzag_wave_b_beyond_wave_a_origin_is_rejected() -> None:
    assert _fit("zigzag", [200, 150, 205, 120], up=False) is None


def test_a_deep_wave_b_is_a_flat_not_a_zigzag() -> None:
    # B retraces 96% of A: above the 90% boundary, so the zigzag rule set
    # rejects it and the flat rule set accepts it.
    assert _fit("zigzag", [200, 150, 198, 120], up=False) is None
    assert _fit("flat", [200, 150, 198, 120], up=False) is not None


def test_truncated_zigzag_is_recorded_as_an_allowance() -> None:
    fit = _fit("zigzag", [200, 150, 180, 155], up=False)
    assert fit is not None
    assert any("truncated zigzag" in a for a in fit.allowances)


# ── flats (Lesson 9) ─────────────────────────────────────────────────────


def test_regular_flat_variant() -> None:
    fit = _fit("flat", [200, 150, 197, 148], up=False)
    assert fit is not None and fit.variant == "regular"


def test_expanded_flat_variant() -> None:
    fit = _fit("flat", [200, 150, 210, 140], up=False)
    assert fit is not None and fit.variant == "expanded"


def test_running_flat_variant_carries_an_allowance() -> None:
    fit = _fit("flat", [200, 150, 210, 160], up=False)
    assert fit is not None
    assert fit.variant == "running"
    assert any("running flat" in a for a in fit.allowances)


def test_flat_rejects_a_shallow_wave_b() -> None:
    # B retraces only 60% of A -- that is a zigzag, not a flat.
    assert _fit("flat", [200, 150, 180, 120], up=False) is None


# ── triangles (Lesson 10) ────────────────────────────────────────────────


def test_contracting_triangle_is_labelled_a_b_c_d_e() -> None:
    fit = _fit("triangle", [100, 140, 110, 132, 116, 127])
    assert fit is not None
    assert fit.variant == "contracting"
    assert fit.labels == ("0", "A", "B", "C", "D", "E")


def test_expanding_triangle_carries_the_rarity_allowance() -> None:
    fit = _fit("triangle", [100, 120, 110, 132, 100, 148])
    assert fit is not None
    assert fit.variant == "expanding"
    assert fit.allowances


def test_triangle_that_neither_converges_nor_diverges_is_rejected() -> None:
    assert _fit("triangle", [100, 140, 110, 150, 105, 130]) is None


def test_triangle_needs_four_confirmed_legs() -> None:
    # Three legs are indistinguishable from a zigzag or a flat, so no triangle
    # is asserted at that length.
    spec = next(s for s in patterns.PATTERN_SPECS if s.pattern == "triangle")
    assert spec.min_terminals == 5


# ── combinations (Lesson 11) ─────────────────────────────────────────────


def test_double_three_is_offered_for_a_sideways_three_leg_sequence() -> None:
    fit = _fit("double three", [100, 120, 102, 110])
    assert fit is not None
    assert fit.pattern == "double three"
    assert fit.labels == ("0", "W", "X", "Y")
    assert any("proportion, not substructure" in a for a in fit.allowances)


def test_triple_three_is_offered_for_a_sideways_five_leg_sequence() -> None:
    fit = _fit("triple three", [100, 120, 102, 116, 101, 112])
    assert fit is not None
    assert fit.labels == ("0", "W", "X", "Y", "X", "Z")


def test_a_trending_three_leg_sequence_is_not_a_combination() -> None:
    # Net displacement is larger than the first leg: this is a zigzag, not a
    # sideways combination.
    assert _fit("double three", [100, 130, 120, 200]) is None


# ── Fibonacci: price and time ────────────────────────────────────────────


def test_nearest_ratio_is_exact_on_a_canonical_value() -> None:
    nearest, proximity = fibonacci.nearest_ratio(Decimal("0.618"))
    assert nearest == Decimal("0.618")
    assert proximity == Decimal("1")


def test_price_relationships_measure_the_documented_wave_pairs() -> None:
    prices = [Decimal(p) for p in ("100", "130", "115", "180", "160", "200")]
    names = [r.name for r in fibonacci.price_relationships("impulse", prices)]
    assert names == [
        "wave 2 / wave 1",
        "wave 3 / wave 1",
        "wave 4 / wave 3",
        "wave 5 / wave 1",
        "wave 5 / wave 3",
    ]


def test_time_relationships_measure_durations_in_sessions() -> None:
    dates = [_START + timedelta(days=d) for d in (0, 10, 15, 35)]
    sessions = {d: i for i, d in enumerate(_START + timedelta(days=n) for n in range(40))}
    rels = fibonacci.time_relationships("zigzag", dates, sessions)
    by_name = {r.name: r for r in rels}
    # wave B lasted 5 sessions against wave A's 10 -> exactly 0.5.
    assert by_name["wave B / wave A (duration)"].observed == Decimal("0.5")
    assert by_name["wave B / wave A (duration)"].nearest == Decimal("0.5")
    # wave C lasted 20 sessions against wave A's 10 -> 2.0, nearest 1.618.
    assert by_name["wave C / wave A (duration)"].nearest == Decimal("1.618")


def test_time_relationships_are_empty_when_a_turning_point_is_off_the_series() -> None:
    dates = [_START, _START + timedelta(days=5)]
    assert fibonacci.time_relationships("zigzag", dates, {_START: 0}) == ()


def test_wave_5_projection_is_a_range_off_the_wave_4_low() -> None:
    count = _top([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160)])
    assert count is not None
    zone = count.projection
    assert zone is not None and "wave 5" in zone.basis
    # wave 1 length = 30 -> 0.618x to 1.0x projected from the wave 4 low (160).
    assert float(zone.low) == 160 + 0.618 * 30
    assert float(zone.high) == 190.0
    assert zone.low < zone.high


def test_partial_impulse_reports_the_wave_in_progress() -> None:
    counts, _ = label_waves(_pivots([("L", 100), ("H", 130), ("L", 115)]), span_sessions=100)
    impulse = next(c for c in counts if c.pattern == "impulse")
    assert impulse.current_position == "Wave 2 complete, wave 3 in progress"
    assert impulse.projection is not None and "wave 3" in impulse.projection.basis


def test_no_projection_is_offered_for_a_structure_with_no_documented_next_leg() -> None:
    assert fibonacci.projection("double three", [Decimal("1"), Decimal("2")], True) is None


# ── ranking and labelling confidence ─────────────────────────────────────


def _evidence(**overrides) -> ranking.CountEvidence:
    base = {
        "is_current": True,
        "labelled_waves": 5,
        "pattern_waves": 5,
        "history_share": Decimal("1"),
        "price_adherence": Decimal("1"),
        "time_adherence": Decimal("1"),
        "personality_corroboration": Decimal("1"),
        "allowance_count": 0,
    }
    return ranking.CountEvidence(**{**base, **overrides})


def test_a_textbook_count_scores_the_full_hundred() -> None:
    total, components = ranking.score(_evidence())
    assert total == Decimal("100")
    assert sum(c.weight for c in components) == Decimal("100")


def test_an_unmeasurable_component_scores_neutral_rather_than_zero() -> None:
    scored, components = ranking.score(_evidence(personality_corroboration=None))
    personality_component = next(c for c in components if "personality" in c.name.lower())
    assert personality_component.score == Decimal("0.5")
    assert "not measurable" in personality_component.detail
    assert scored == Decimal("100") - ranking.WEIGHT_PERSONALITY / 2


def test_allowances_cost_structural_cleanliness() -> None:
    clean, _ = ranking.score(_evidence())
    messy, _ = ranking.score(_evidence(allowance_count=2))
    assert messy < clean


def test_a_stale_count_ranks_below_a_current_one() -> None:
    current, _ = ranking.score(_evidence())
    stale, _ = ranking.score(_evidence(is_current=False))
    assert current - stale == ranking.WEIGHT_CURRENCY


def test_competing_counts_are_ranked_and_explained() -> None:
    # Down-up-down off a high is genuinely ambiguous: waves 1-2-3 of a
    # developing impulse, or a completed A-B-C. Both are exposed.
    counts, rationale = label_waves(
        _pivots([("H", 200), ("L", 150), ("H", 180), ("L", 120)]), span_sessions=100
    )
    assert len(counts) >= 2
    kinds = {c.pattern for c in counts}
    assert "impulse" in kinds and "zigzag" in kinds
    # Ranked best first, and every alternate has a stated reason for its place.
    assert list(counts) == sorted(counts, key=lambda c: -c.labelling_confidence)
    assert len(rationale) == len(counts)
    assert all(r for r in rationale)


def test_at_most_one_candidate_per_pattern_is_offered() -> None:
    counts, _ = label_waves(
        _pivots(
            [
                ("L", 100),
                ("H", 130),
                ("L", 115),
                ("H", 180),
                ("L", 160),
                ("H", 200),
                ("L", 150),
                ("H", 190),
            ]
        ),
        span_sessions=300,
    )
    assert len({c.pattern for c in counts}) == len(counts)
    assert len(counts) <= ranking.MAX_CANDIDATES


def test_alternates_must_explain_the_same_price_action() -> None:
    counts, _ = label_waves(
        _pivots([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160), ("H", 200)]),
        span_sessions=300,
    )
    terminus = {c.labels[-1].bar_date for c in counts}
    assert len(terminus) == 1


def test_labelling_confidence_states_it_is_not_a_forecast() -> None:
    count = _top([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160), ("H", 200)])
    assert count is not None
    assert "not a forecast" in count.labelling_confidence_basis
    assert "probability" in count.labelling_confidence_basis


# ── wave personality (Lesson 14) ─────────────────────────────────────────


def _impulse_bars(volumes: list[int] | None = None) -> list[OHLCVBar]:
    closes = _closes([100, 130, 115, 180, 160, 200, 170])
    return _bars(closes, volumes)


def test_personality_corroborates_a_heavy_volume_wave_three() -> None:
    closes = _closes([100, 130, 115, 180, 160, 200, 170])
    # Wave 3 spans bars 10-15 in this construction; give it the heaviest volume.
    volumes = [5000 if 10 <= i <= 15 else 800 for i in range(len(closes))]
    bars = _bars(closes, volumes)
    context = PersonalityContext(
        dates=tuple(b.date for b in bars),
        rsi14=tuple(Decimal("60") for _ in bars),
        adx14=tuple(Decimal("25") for _ in bars),
        volumes=tuple(b.volume for b in bars),
    )
    result = analyze_elliott_wave("TEST", bars, Decimal("5"), context)
    impulse = next(c for c in result.candidates if c.pattern == "impulse")
    volume_check = next(
        c for c in impulse.personality if c.wave == "3" and "heaviest volume" in c.expectation
    )
    assert volume_check.status == patterns.SUPPORTING
    assert "measured" in volume_check.detail


def test_personality_contradicts_a_light_volume_wave_three() -> None:
    closes = _closes([100, 130, 115, 180, 160, 200, 170])
    volumes = [100 if 10 <= i <= 15 else 5000 for i in range(len(closes))]
    bars = _bars(closes, volumes)
    context = PersonalityContext(
        dates=tuple(b.date for b in bars),
        rsi14=tuple(Decimal("60") for _ in bars),
        adx14=tuple(Decimal("25") for _ in bars),
        volumes=tuple(b.volume for b in bars),
    )
    result = analyze_elliott_wave("TEST", bars, Decimal("5"), context)
    impulse = next(c for c in result.candidates if c.pattern == "impulse")
    volume_check = next(
        c for c in impulse.personality if c.wave == "3" and "heaviest volume" in c.expectation
    )
    assert volume_check.status == patterns.CONTRADICTING


def test_missing_indicator_data_reports_the_affected_checks_as_not_measurable() -> None:
    bars = _impulse_bars()
    context = PersonalityContext(
        dates=tuple(b.date for b in bars),
        rsi14=tuple(None for _ in bars),
        adx14=tuple(None for _ in bars),
        volumes=tuple(None for _ in bars),
    )
    checks = analyze_elliott_wave("TEST", bars, Decimal("5"), context).candidates[0].personality
    # Every volume- and momentum-derived check degrades to "not measurable"...
    indicator_checks = [c for c in checks if "volume" in c.expectation or "RSI" in c.expectation]
    assert indicator_checks
    assert all(c.status == patterns.NOT_MEASURABLE for c in indicator_checks)
    # ...while the retracement-depth checks, which read price alone, still hold.
    depth_checks = [c for c in checks if "retraces" in c.expectation or "shallow" in c.expectation]
    assert depth_checks
    assert all(c.status != patterns.NOT_MEASURABLE for c in depth_checks)


def test_an_entirely_unmeasurable_personality_never_penalises_the_score() -> None:
    empty = personality.PersonalityContext()
    bars = _impulse_bars()
    with_empty = analyze_elliott_wave("TEST", bars, Decimal("5"), empty)
    without = analyze_elliott_wave("TEST", bars, Decimal("5"), None)
    assert personality.corroboration(with_empty.candidates[0].personality) is None
    assert (
        with_empty.candidates[0].labelling_confidence == without.candidates[0].labelling_confidence
    )


def test_no_personality_is_reported_without_a_context() -> None:
    result = analyze_elliott_wave("TEST", _impulse_bars(), Decimal("5"), None)
    assert result.candidates[0].personality == ()


# ── multi-degree hierarchy ───────────────────────────────────────────────


def _impulse_leg(a: float, b: float) -> list[float]:
    """Terminals of a five-wave path from ``a`` to ``b`` (``a`` excluded)."""
    d = b - a
    return [a + 0.40 * d, a + 0.22 * d, a + 0.85 * d, a + 0.68 * d, b]


def _zigzag_leg(a: float, b: float) -> list[float]:
    d = b - a
    return [a + 0.62 * d, a + 0.30 * d, b]


def _self_similar_impulse() -> list[OHLCVBar]:
    """A five-wave impulse whose every leg is itself a correct finer structure.

    Motive legs (1, 3, 5) expand into five-wave impulses and corrective legs
    (2, 4) into zigzags, which is what the Wave Principle expects inside each
    position — so this fixture exercises the degree recursion *and* the
    position-fit guideline at once.
    """
    top = [100.0, *_impulse_leg(100, 200)]
    points = [top[0]]
    for index, (a, b) in enumerate(zip(top, top[1:], strict=False)):
        points += _impulse_leg(a, b) if index % 2 == 0 else _zigzag_leg(a, b)
    closes = [points[0]]
    for a, b in zip(points, points[1:], strict=False):
        closes.extend(_ramp(a, b, steps=4))
    return _bars(closes)


def test_the_top_degree_is_coarsened_to_the_largest_structure_available() -> None:
    result = analyze_elliott_wave("TEST", _self_similar_impulse(), Decimal("3"))
    # The requested threshold is the *finest* degree; the top degree steps away
    # from it so the highest level is not merely the last few swings.
    assert result.top_degree_threshold_pct > Decimal("3")
    assert result.candidates[0].pattern == "impulse"
    assert any("coarsened" in note for note in result.notes)


def test_each_leg_subdivides_into_the_family_the_theory_expects() -> None:
    result = analyze_elliott_wave("TEST", _self_similar_impulse(), Decimal("3"))
    top = result.candidates[0]
    by_label = {s.of_label: s for s in top.subdivisions}
    assert set(by_label) >= {"1", "2", "3", "4"}
    assert by_label["1"].pattern == "impulse"
    assert by_label["2"].pattern == "zigzag"
    assert all(s.position_fit.status == patterns.SUPPORTING for s in by_label.values())


def test_subdivision_labels_stay_inside_their_parent_leg() -> None:
    result = analyze_elliott_wave("TEST", _self_similar_impulse(), Decimal("3"))
    top = result.candidates[0]
    for subdivision in top.subdivisions:
        index = next(i for i, w in enumerate(top.labels) if w.label == subdivision.of_label)
        assert top.labels[index - 1].bar_date <= subdivision.labels[0].bar_date
        assert subdivision.labels[-1].bar_date <= top.labels[index].bar_date


def test_no_degree_finer_than_the_requested_threshold_is_labelled() -> None:
    # The caller's threshold is the finest degree they asked to see; inventing
    # structure below it would label noise.
    result = analyze_elliott_wave("TEST", _self_similar_impulse(), Decimal("9"))
    assert result.top_degree_threshold_pct == Decimal("9")
    assert result.candidates[0].subdivisions == ()


def test_recursion_is_bounded_by_the_declared_depth() -> None:
    from momentum25.domain.analytics.elliott.analysis import MAX_SUBDIVISION_DEPTH

    def depth(subdivisions, level=1):
        return max(
            (depth(s.subdivisions, level + 1) for s in subdivisions if s.subdivisions),
            default=level if subdivisions else 0,
        )

    result = analyze_elliott_wave("TEST", _self_similar_impulse(), Decimal("1"))
    for count in result.candidates:
        assert depth(count.subdivisions) <= MAX_SUBDIVISION_DEPTH


def test_subdivisions_are_deterministic() -> None:
    bars = _self_similar_impulse()
    a = analyze_elliott_wave("TEST", bars, Decimal("3"))
    b = analyze_elliott_wave("TEST", bars, Decimal("3"))
    assert a.candidates[0].subdivisions == b.candidates[0].subdivisions


def test_no_subdivision_when_legs_lack_finer_structure() -> None:
    result = analyze_elliott_wave("TEST", _path([100, 130, 115, 180, 160, 200, 170]), Decimal("5"))
    assert result.candidates[0].subdivisions == ()
    assert any("finer degree" in note for note in result.notes)


def test_degree_describes_the_labelled_span_not_the_history_loaded() -> None:
    # A short structure inside a long history is not a Primary-degree count.
    result = analyze_elliott_wave("TEST", _path([100, 130, 115, 180, 160, 200, 170]), Decimal("5"))
    assert result.candidates[0].degree in ("Minute", "Minor")


# ── end to end ───────────────────────────────────────────────────────────


def test_analyze_reports_pivots_and_notes_when_no_count_holds() -> None:
    result = analyze_elliott_wave("TEST", _path([100, 102, 100]), Decimal("10"))
    assert result.pivots == ()
    assert result.candidates == ()
    assert result.notes and "too few" in result.notes[0]


def test_analyze_is_deterministic_end_to_end() -> None:
    bars = _path([100, 130, 110, 180, 160, 200, 170])
    assert analyze_elliott_wave("TEST", bars, Decimal("5")) == analyze_elliott_wave(
        "TEST", bars, Decimal("5")
    )


def test_the_ranking_method_is_published_with_the_result() -> None:
    result = analyze_elliott_wave("TEST", _path([100, 130, 115, 180, 160, 200, 170]), Decimal("5"))
    assert "admissibility" in result.ranking_method
    assert "rules are never traded off against guidelines" in result.ranking_method.lower()


def test_no_output_field_expresses_a_target_or_a_verdict() -> None:
    """The item-8 constraint, asserted rather than assumed."""
    result = analyze_elliott_wave("TEST", _path([100, 130, 115, 180, 160, 200, 170]), Decimal("5"))
    banned = ("target", "buy", "sell", "profit", "r-multiple", "stop loss", "stop-loss")
    text = repr(result).lower()
    assert not [word for word in banned if word in text]
