"""Elliott Wave labelling tests (Phase 7) — hand-built series with known pivots."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.domain.analytics.elliott_wave import (
    Pivot,
    analyze_elliott_wave,
    label_waves,
    zigzag_pivots,
)
from momentum25.domain.entities.market_data import OHLCVBar

_START = date(2024, 1, 1)


def _bars(closes: list[float]) -> list[OHLCVBar]:
    """One bar per close, with high == low == close so pivots are unambiguous."""
    return [
        OHLCVBar(
            date=_START + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=1000,
        )
        for i, c in enumerate(closes)
    ]


def _ramp(start: float, end: float, steps: int = 5) -> list[float]:
    """Linear path from ``start`` to ``end`` (exclusive of ``start``)."""
    step = (end - start) / steps
    return [start + step * (i + 1) for i in range(steps)]


def _path(points: list[float]) -> list[OHLCVBar]:
    closes = [points[0]]
    for a, b in zip(points, points[1:], strict=False):
        closes.extend(_ramp(a, b))
    return _bars(closes)


def _pivots(kinds_prices: list[tuple[str, float]]) -> tuple[Pivot, ...]:
    return tuple(
        Pivot(_START + timedelta(days=i * 10), Decimal(str(p)), k)
        for i, (k, p) in enumerate(kinds_prices)
    )


# ── zigzag ───────────────────────────────────────────────────────────────


def test_zigzag_finds_alternating_confirmed_pivots() -> None:
    pivots = zigzag_pivots(_path([100, 130, 110, 160, 140, 190]), Decimal("5"))
    # The final leg's extreme (190) is unconfirmed -- no reversal followed it.
    assert [p.kind for p in pivots] == ["L", "H", "L", "H", "L"]
    assert [float(p.price) for p in pivots] == [100, 130, 110, 160, 140]


def test_zigzag_ignores_moves_below_threshold() -> None:
    # 2% wiggles against a 10% threshold produce no confirmed reversal.
    assert zigzag_pivots(_path([100, 102, 100, 102, 100]), Decimal("10")) == ()


def test_zigzag_is_deterministic() -> None:
    bars = _path([100, 130, 110, 160, 140, 190, 170])
    assert zigzag_pivots(bars, Decimal("5")) == zigzag_pivots(bars, Decimal("5"))


# ── cardinal rules ───────────────────────────────────────────────────────


def test_valid_five_wave_impulse_is_labelled() -> None:
    pivots = _pivots(
        [("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160), ("H", 200)]
    )
    primary, _ = label_waves(pivots, span_sessions=300)
    assert primary is not None
    assert primary.pattern == "impulse"
    assert [w.label for w in primary.labels] == ["0", "1", "2", "3", "4", "5"]
    assert primary.current_position == "Waves 1-5 complete, A-B-C correction expected"
    assert primary.degree == "Intermediate"


def test_wave_2_retracing_beyond_wave_1_start_is_rejected() -> None:
    pivots = _pivots([("L", 100), ("H", 130), ("L", 95), ("H", 180), ("L", 160), ("H", 200)])
    primary, _ = label_waves(pivots, span_sessions=300)
    assert primary is None or [w.label for w in primary.labels] != ["0", "1", "2", "3", "4", "5"]


def test_wave_4_overlapping_wave_1_is_rejected() -> None:
    # Wave 4 low (125) drops into wave 1's territory (which topped at 130).
    pivots = _pivots([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 125), ("H", 200)])
    primary, _ = label_waves(pivots, span_sessions=300)
    assert primary is not None
    assert [w.label for w in primary.labels] == ["0", "1", "2", "3"]  # truncated before wave 4


def test_wave_3_shortest_is_rejected() -> None:
    # w1 = 40, w3 = 20, w5 = 50 -> wave 3 is the shortest.
    pivots = _pivots([("L", 100), ("H", 140), ("L", 130), ("H", 150), ("L", 145), ("H", 195)])
    primary, alternative = label_waves(pivots, span_sessions=300)
    assert primary is not None
    # No count may label all five waves over these pivots; the structure is
    # re-anchored instead of asserting an impulse that breaks the rule.
    for count in (primary, alternative):
        assert count is None or "5" not in [w.label for w in count.labels]
    assert float(primary.labels[0].price) != 100.0


# ── no price projection ──────────────────────────────────────────────────


def test_wave_count_publishes_no_price_projection() -> None:
    # A wave-count-derived price objective is a target; targets live only in the
    # validated swing-target module (audit 2026-08-09 section 2.1).
    pivots = _pivots([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160)])
    primary, _ = label_waves(pivots, span_sessions=300)
    assert primary is not None
    assert not hasattr(primary, "projection")


def test_partial_impulse_reports_the_wave_in_progress() -> None:
    pivots = _pivots([("L", 100), ("H", 130), ("L", 115)])
    primary, _ = label_waves(pivots, span_sessions=100)
    assert primary is not None
    assert primary.current_position == "Wave 2 complete, wave 3 in progress"


# ── corrective structures ────────────────────────────────────────────────


def test_downward_abc_correction_is_offered_as_the_alternative_count() -> None:
    # Down-up-down off a high is genuinely ambiguous: waves 1-2-3 of a developing
    # impulse, or a completed A-B-C. Both are exposed, neither is picked silently.
    pivots = _pivots([("H", 200), ("L", 150), ("H", 180), ("L", 120)])
    primary, alternative = label_waves(pivots, span_sessions=100)
    assert primary is not None and alternative is not None
    assert primary.pattern == "impulse"
    assert primary.direction == "down"
    assert alternative.pattern == "correction"
    assert [w.label for w in alternative.labels] == ["0", "A", "B", "C"]
    assert alternative.current_position == "Waves A-B-C complete"


def test_no_alternative_is_manufactured_when_only_one_count_holds() -> None:
    pivots = _pivots([("L", 100), ("H", 130), ("L", 115), ("H", 180), ("L", 160), ("H", 200)])
    _, alternative = label_waves(pivots, span_sessions=300)
    assert alternative is None


# ── end-to-end ───────────────────────────────────────────────────────────


def test_analyze_reports_pivots_and_notes_when_no_count_holds() -> None:
    result = analyze_elliott_wave("TEST", _path([100, 102, 100]), Decimal("10"))
    assert result.pivots == ()
    assert result.primary is None
    assert result.notes and "too few" in result.notes[0]


def test_analyze_is_deterministic_end_to_end() -> None:
    bars = _path([100, 130, 110, 180, 160, 200, 170])
    a = analyze_elliott_wave("TEST", bars, Decimal("5"))
    b = analyze_elliott_wave("TEST", bars, Decimal("5"))
    assert a == b
    assert a.symbol == "TEST"
    assert a.bars_analyzed == len(bars)


# ── finer-degree subdivisions ────────────────────────────────────────────


def _wave3_with_substructure() -> list[OHLCVBar]:
    """Five-wave impulse whose wave-3 leg hides a clean finer-degree impulse.

    Sub-legs are 2-5% reversals: too small to disturb the parent zigzag at the
    ``threshold_pct``=5% level, large enough to confirm pivots at the finer
    ``max(5/3, 1)%`` level used by ``subdivide``.
    """
    return _path(
        [
            100,  # wave 0 origin
            130,  # wave 1
            115,  # wave 2
            # wave 3 leg carries a nested impulse: 115 -> 124 -> 119 -> 127 ->
            # 124.6 (above wave-1 sub top 124, so rule 3 holds) -> then the leg
            # continues to 180
            124,
            119,
            127,
            124.6,
            130,
            180,  # wave 3
            160,  # wave 4
            200,  # wave 5
            140,  # reversal confirming the wave 5 top
        ]
    )


def test_wave_3_contains_one_finer_degree_subdivision() -> None:
    bars = _wave3_with_substructure()
    result = analyze_elliott_wave("TEST", bars, Decimal("5"))
    assert result.primary is not None
    assert result.primary.pattern == "impulse"
    assert [w.label for w in result.primary.labels] == ["0", "1", "2", "3", "4", "5"]
    subdivs = result.primary.subdivisions
    assert len(subdivs) == 1
    assert subdivs[0].of_label == "3"
    assert len(subdivs[0].labels) >= 3
    assert [w.label for w in subdivs[0].labels] == ["0", "1", "2", "3", "4"]


def test_subdivision_labels_stay_inside_their_parent_leg() -> None:
    bars = _wave3_with_substructure()
    result = analyze_elliott_wave("TEST", bars, Decimal("5"))
    assert result.primary is not None
    parent = result.primary.labels
    for subdiv in result.primary.subdivisions:
        idx = next(i for i, w in enumerate(parent) if w.label == subdiv.of_label)
        lo = parent[idx - 1]
        hi = parent[idx]
        assert lo.bar_date <= subdiv.labels[0].bar_date
        assert subdiv.labels[-1].bar_date <= hi.bar_date


def test_subdivisions_are_deterministic() -> None:
    bars = _wave3_with_substructure()
    a = analyze_elliott_wave("TEST", bars, Decimal("5"))
    b = analyze_elliott_wave("TEST", bars, Decimal("5"))
    assert a == b
    assert a.primary is not None and b.primary is not None
    assert a.primary.subdivisions == b.primary.subdivisions


def test_no_subdivision_when_legs_lack_finer_structure() -> None:
    bars = _path([100, 130, 115, 180, 160, 200, 170])
    result = analyze_elliott_wave("TEST", bars, Decimal("5"))
    assert result.primary is not None
    assert result.primary.subdivisions == ()
    assert any(
        "No leg of this count contains enough confirmed pivots "
        "to label a finer degree." in note
        for note in result.notes
    )


# ── pivot separation (audit 2026-08-09, U2a) ─────────────────────────────


def _wide_bar(day: int, low: float, high: float) -> OHLCVBar:
    return OHLCVBar(
        date=_START + timedelta(days=day),
        open=Decimal(str(high)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(low)),
        volume=1000,
    )


def test_one_wide_range_bar_is_not_both_a_swing_high_and_a_swing_low() -> None:
    # A single bar spanning more than the reversal threshold used to confirm a
    # high against itself and then seed the low tracker from the same bar,
    # emitting an H and an L on the identical date.
    bars = [
        _wide_bar(0, 100, 100),
        _wide_bar(1, 100, 120),  # rally
        _wide_bar(2, 100, 121),  # wide bar: high 121, low 100 (-17%)
        _wide_bar(3, 100, 101),
        _wide_bar(4, 130, 130),  # rally back up, confirming the low
    ]
    pivots = zigzag_pivots(bars, Decimal("5"))
    dates = [p.bar_date for p in pivots]
    assert len(dates) == len(set(dates))
    kinds = [p.kind for p in pivots]
    assert all(a != b for a, b in zip(kinds, kinds[1:], strict=False))
