"""Chart-pattern detection tests (Phase 8) — hand-built series with known geometry."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from momentum25.domain.analytics.chart_patterns import (
    ChartPatternAnalysis,
    detect_chart_patterns,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.patterns.cup_handle import CupWithHandleDetector

_START = date(2024, 1, 1)


def _bars(closes: list[float], volumes: list[int] | None = None) -> list[OHLCVBar]:
    """One bar per close, with high == low == close so pivots are unambiguous."""
    vols = volumes if volumes is not None else [1000] * len(closes)
    return [
        OHLCVBar(
            date=_START + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, vols, strict=True))
    ]


def _ramp(start: float, end: float, steps: int) -> list[float]:
    step = (end - start) / steps
    return [start + step * (i + 1) for i in range(steps)]


def _path(points: list[tuple[float, int]]) -> list[float]:
    """Piecewise-linear close series: ``(price, sessions to reach it)`` legs."""
    closes = [points[0][0]]
    for (_, _), (price, steps) in zip(points, points[1:], strict=False):
        closes.extend(_ramp(closes[-1], price, steps))
    return closes


def _names(analysis: ChartPatternAnalysis) -> list[str]:
    return [p.pattern for p in analysis.patterns]


def _get(analysis: ChartPatternAnalysis, pattern: str):
    return next(p for p in analysis.patterns if p.pattern == pattern)


# ── Head & shoulders ─────────────────────────────────────────────────────


def _head_and_shoulders_closes() -> list[float]:
    return _path(
        [
            (100.0, 0),
            (120.0, 15),  # left shoulder
            (105.0, 12),  # left armpit
            (140.0, 18),  # head
            (106.0, 15),  # right armpit
            (121.0, 14),  # right shoulder
            (104.0, 12),  # confirms the right shoulder pivot
        ]
    )


def test_head_and_shoulders_is_detected_with_neckline_geometry() -> None:
    analysis = detect_chart_patterns("TEST", _bars(_head_and_shoulders_closes()))

    assert "head_and_shoulders" in _names(analysis)
    hs = _get(analysis, "head_and_shoulders")
    assert hs.display_name == "Head & Shoulders"
    assert all(c.met for c in hs.criteria if c.required)
    assert hs.completion_score >= 80
    neckline = next(line for line in hs.geometry if line.name == "Neckline")
    assert len(neckline.points) == 2
    assert neckline.points[0].price < neckline.points[1].price  # rising armpits


def test_inverse_head_and_shoulders_is_detected() -> None:
    closes = _path(
        [
            (140.0, 0),
            (118.0, 15),  # left shoulder (low)
            (134.0, 12),
            (100.0, 18),  # head (low)
            (133.0, 15),
            (117.0, 14),  # right shoulder (low)
            (140.0, 12),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "inverse_head_and_shoulders" in _names(analysis)


def test_symmetric_head_dominance_is_required() -> None:
    """A middle peak no higher than its shoulders is not a head."""
    closes = _path(
        [
            (100.0, 0),
            (120.0, 15),
            (105.0, 12),
            (121.0, 18),  # only 0.8% above the shoulders
            (106.0, 15),
            (120.0, 14),
            (104.0, 12),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "head_and_shoulders" not in _names(analysis)


# ── Double top / bottom ──────────────────────────────────────────────────


def test_double_top_is_detected_with_confirmation_level() -> None:
    closes = _path([(100.0, 0), (130.0, 20), (112.0, 15), (129.0, 20), (110.0, 15)])
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "double_top" in _names(analysis)
    dt = _get(analysis, "double_top")
    level = next(line for line in dt.geometry if line.name == "Confirmation level")
    assert level.points[0].price == level.points[1].price  # horizontal


def test_double_bottom_is_detected() -> None:
    closes = _path([(130.0, 0), (100.0, 20), (116.0, 15), (101.0, 20), (118.0, 15)])
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "double_bottom" in _names(analysis)


def test_unequal_peaks_are_not_a_double_top() -> None:
    closes = _path([(100.0, 0), (130.0, 20), (112.0, 15), (118.0, 20), (100.0, 15)])
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "double_top" not in _names(analysis)


# ── Triangles and wedges ─────────────────────────────────────────────────


def test_ascending_triangle_has_flat_top_and_rising_lows() -> None:
    closes = _path(
        [
            (80.0, 0),
            (120.0, 20),  # high 1
            (100.0, 12),  # low 1
            (120.5, 12),  # high 2 (flat top)
            (112.0, 12),  # low 2 (higher low)
            (119.0, 8),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "ascending_triangle" in _names(analysis)
    tri = _get(analysis, "ascending_triangle")
    assert {line.name for line in tri.geometry} == {"Upper trendline", "Lower trendline"}


def test_descending_triangle_has_flat_base_and_falling_highs() -> None:
    closes = _path(
        [
            (140.0, 0),
            (100.0, 20),  # low 1
            (125.0, 12),  # high 1
            (100.5, 12),  # low 2 (flat base)
            (110.0, 12),  # high 2 (lower high)
            (101.5, 8),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "descending_triangle" in _names(analysis)


def test_symmetrical_triangle_converges_from_both_sides() -> None:
    closes = _path(
        [
            (80.0, 0),
            (130.0, 20),  # high 1
            (100.0, 12),  # low 1
            (120.0, 12),  # high 2 (lower)
            (110.0, 12),  # low 2 (higher)
            (117.0, 8),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "symmetrical_triangle" in _names(analysis)


def test_rising_wedge_has_both_boundaries_rising_and_converging() -> None:
    closes = _path(
        [
            (80.0, 0),
            (120.0, 20),  # high 1
            (100.0, 12),  # low 1
            (128.0, 12),  # high 2 (higher)
            (118.0, 12),  # low 2 (much higher -> converging)
            (126.0, 8),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "rising_wedge" in _names(analysis)


def test_falling_wedge_has_both_boundaries_falling_and_converging() -> None:
    closes = _path(
        [
            (150.0, 0),
            (100.0, 20),  # low 1
            (135.0, 12),  # high 1
            (90.0, 12),  # low 2 (lower)
            (100.0, 12),  # high 2 (much lower -> converging)
            (92.0, 8),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "falling_wedge" in _names(analysis)


def test_a_widening_range_is_no_triangle_or_wedge() -> None:
    closes = _path(
        [
            (100.0, 0),
            (120.0, 15),
            (95.0, 15),
            (135.0, 15),
            (80.0, 15),
            (110.0, 10),
        ]
    )
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert not {
        "ascending_triangle",
        "descending_triangle",
        "symmetrical_triangle",
        "rising_wedge",
        "falling_wedge",
    } & set(_names(analysis))


# ── Flags & pennants ─────────────────────────────────────────────────────


def test_pennant_requires_pole_and_converging_consolidation() -> None:
    closes = [100.0] * 30 + _ramp(100.0, 130.0, 15)
    bars = _bars(closes, [3000] * 45)
    # Consolidation with a narrowing high/low range: converging boundaries.
    for i in range(15):
        width = 4.0 - i * 0.25
        bars.append(
            OHLCVBar(
                date=_START + timedelta(days=45 + i),
                open=Decimal("126"),
                high=Decimal(str(126.0 + width)),
                low=Decimal(str(126.0 - width)),
                close=Decimal("126"),
                volume=800,
            )
        )
    analysis = detect_chart_patterns("TEST", bars)

    assert "pennant" in _names(analysis)
    pennant = _get(analysis, "pennant")
    assert {line.name for line in pennant.geometry} == {
        "Flagpole",
        "Upper boundary",
        "Lower boundary",
    }
    assert any("Volume contracts" in c.label and c.met for c in pennant.criteria)


def test_a_deep_retrace_after_a_pole_is_not_a_flag() -> None:
    closes = [100.0] * 30 + _ramp(100.0, 130.0, 15) + _ramp(130.0, 105.0, 15)
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert not {"flag", "pennant"} & set(_names(analysis))


# ── Cup with handle ──────────────────────────────────────────────────────


def _cup_closes() -> list[float]:
    return (
        _path(
            [
                (100.0, 0),
                (130.0, 15),  # left rim
                (100.0, 25),  # cup low (23% deep)
                (128.0, 25),  # right rim
            ]
        )
        + _ramp(128.0, 120.0, 5)
        + [120.0, 121.0, 122.0]
    )


def test_cup_with_handle_is_detected_with_cup_and_handle_geometry() -> None:
    volumes = [2000] * 66 + [700] * 8
    analysis = detect_chart_patterns("TEST", _bars(_cup_closes(), volumes))

    assert "cup_with_handle" in _names(analysis)
    cup = _get(analysis, "cup_with_handle")
    assert {line.name for line in cup.geometry} == {"Cup", "Handle"}
    assert any(c.label == "Volume contraction in the handle" and c.met for c in cup.criteria)


def test_cup_bottom_index_is_found_to_the_right_of_the_left_peak() -> None:
    """F9 regression: the cup low may also occur *before* the left rim.

    ``recent_low.index(cup_bottom)`` searched from position 0, so an equal low
    early in the window returned an index left of the peak. ``cup_width`` then
    came out zero or negative and the detector rejected a real cup on a bogus
    "cup width" reason. The bar series below starts at exactly the cup low, so
    the value repeats on both sides of the peak.
    """
    closes = (
        [100.0]
        + _ramp(100.0, 130.0, 8)
        + _ramp(130.0, 100.0, 40)
        + _ramp(100.0, 128.0, 40)
        + _ramp(128.0, 120.0, 5)
        + [120.0, 121.0, 122.0]
    )
    detector = CupWithHandleDetector()
    decimals = [Decimal(str(c)) for c in closes]
    result = detector.detect(
        close=decimals,
        high=decimals,
        low=decimals,
        volume=[2000] * (len(closes) - 8) + [700] * 8,
    )

    assert "Cup width" not in result.explanation


def test_a_shallow_cup_is_rejected() -> None:
    closes = _path([(100.0, 0), (130.0, 15), (122.0, 25), (129.0, 25)]) + _ramp(129.0, 124.0, 6)
    analysis = detect_chart_patterns("TEST", _bars(closes))

    assert "cup_with_handle" not in _names(analysis)


# ── Contract-level guarantees ────────────────────────────────────────────


def test_detection_is_deterministic() -> None:
    bars = _bars(_head_and_shoulders_closes())
    first = detect_chart_patterns("TEST", bars)
    second = detect_chart_patterns("TEST", bars)

    assert first == second


def test_flat_series_yields_no_pattern_and_says_so() -> None:
    analysis = detect_chart_patterns("TEST", _bars([100.0] * 200))

    assert analysis.patterns == ()
    assert any("No classical chart pattern" in n for n in analysis.notes)


def test_empty_history_is_reported_not_raised() -> None:
    analysis = detect_chart_patterns("TEST", [])

    assert analysis.patterns == ()
    assert analysis.as_of is None
    assert any("No price history" in n for n in analysis.notes)


def test_candidates_are_ordered_by_completion_score() -> None:
    analysis = detect_chart_patterns("TEST", _bars(_head_and_shoulders_closes()))
    scores = [p.completion_score for p in analysis.patterns]

    assert scores == sorted(scores, reverse=True)


def test_every_reported_pattern_meets_all_required_criteria() -> None:
    for closes in (_head_and_shoulders_closes(), _cup_closes()):
        analysis = detect_chart_patterns("TEST", _bars(closes))
        for pattern in analysis.patterns:
            assert all(c.met for c in pattern.criteria if c.required)
            assert 0 <= pattern.completion_score <= 100
            assert pattern.starts_on <= pattern.ends_on


def test_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError):
        detect_chart_patterns("TEST", _bars([100.0, 110.0, 100.0]), Decimal("0"))
