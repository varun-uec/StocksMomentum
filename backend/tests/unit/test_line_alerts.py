"""Golden tests for sloped drawing alerts (ADR-013 line amendment, plan B4).

Sessions are the ten weekdays from Monday 3 August 2026, indices 0-9. Every
expected level and firing below is worked out by hand.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.entities.alert import Firing, SeriesPoint, first_line_firing, line_levels

D = Decimal
SESSIONS = [date(2026, 8, 3 + i) for i in range(5)] + [date(2026, 8, 10 + i) for i in range(5)]
# A line through (index 2, 100) and (index 4, 110): +5 per session.
UP = ((SESSIONS[2], D(100)), (SESSIONS[4], D(110)))


def _points(*closes: str) -> list[SeriesPoint]:
    return [SeriesPoint(SESSIONS[i], D(c)) for i, c in enumerate(closes)]


def test_each_kind_has_its_domain() -> None:
    assert (
        line_levels("trendline", UP, SESSIONS) == [None, None, D(100), D(105), D(110)] + [None] * 5
    )
    assert line_levels("ray", UP, SESSIONS) == [None, None] + [D(100 + 5 * i) for i in range(8)]
    assert line_levels("extended", UP, SESSIONS) == [D(90 + 5 * i) for i in range(10)]
    # Anchors given right to left draw the same trendline and extended line.
    back = (UP[1], UP[0])
    assert line_levels("trendline", back, SESSIONS) == line_levels("trendline", UP, SESSIONS)
    assert line_levels("extended", back, SESSIONS) == line_levels("extended", UP, SESSIONS)


def test_a_line_needs_two_sessions_and_a_ray_points_forward() -> None:
    with pytest.raises(ValueError, match="two different sessions"):
        line_levels("trendline", ((SESSIONS[2], D(1)), (SESSIONS[2], D(2))), SESSIONS)
    # A weekend anchor counts as the next session, so Saturday and Monday are one session.
    with pytest.raises(ValueError, match="two different sessions"):
        line_levels("ray", ((date(2026, 8, 8), D(1)), (SESSIONS[5], D(2))), SESSIONS)
    with pytest.raises(ValueError, match="forward"):
        line_levels("ray", (UP[1], UP[0]), SESSIONS)


@pytest.mark.parametrize(
    ("kind", "condition", "closes", "expected"),
    [
        # The ray rises 5 a session from 100 on Wednesday (index 2).
        ("ray", "crosses_above", ("0", "0", "99", "104", "111"), Firing(SESSIONS[4], D(111))),
        # Equality: on the line, then above it, is a cross (previous ≤ line < current).
        ("ray", "crosses_above", ("0", "0", "100", "106"), Firing(SESSIONS[3], D(106))),
        # On the line, then on the line again, is not.
        ("ray", "crosses_above", ("0", "0", "100", "105", "110"), None),
        ("ray", "crosses_below", ("0", "0", "101", "104"), Firing(SESSIONS[3], D(104))),
        # A close that rises with the line, always above it, never crosses.
        ("ray", "crosses_above", ("0", "0", "101", "106", "111", "116"), None),
        # Outside a trendline's domain nothing fires, even past its end.
        ("trendline", "crosses_above", ("0", "0", "99", "104", "109", "200"), None),
        ("trendline", "crosses_above", ("0", "0", "99", "106"), Firing(SESSIONS[3], D(106))),
    ],
)
def test_crossings_compare_each_close_with_the_line_on_its_session(
    kind: str, condition: str, closes: tuple[str, ...], expected: Firing | None
) -> None:
    points = _points(*closes)
    levels = line_levels(kind, UP, SESSIONS[: len(points)])  # type: ignore[arg-type]
    assert first_line_firing(condition, SESSIONS[0], points, levels) == expected  # type: ignore[arg-type]


def test_the_domain_edge_breaks_a_crossing() -> None:
    # Tuesday is before the ray starts, so Wednesday's close has no previous level.
    points = _points("0", "90", "101")
    levels = line_levels("ray", UP, SESSIONS[:3])
    assert first_line_firing("crosses_above", SESSIONS[0], points, levels) is None


def test_only_sessions_after_arming_fire_and_replay_is_deterministic() -> None:
    points = _points("0", "0", "99", "106", "99", "121")
    levels = line_levels("ray", UP, SESSIONS[:6])
    assert first_line_firing("crosses_above", SESSIONS[3], points, levels) == Firing(
        SESSIONS[5], D(121)
    )
    # A late job with more bars finds the same first firing.
    more = _points("0", "0", "99", "106", "99", "121", "0", "500")
    later = line_levels("ray", UP, SESSIONS[:8])
    assert first_line_firing("crosses_above", SESSIONS[3], more, later) == Firing(
        SESSIONS[5], D(121)
    )


def test_a_split_between_the_anchors_keeps_the_line_on_its_bars() -> None:
    """Traded anchors at 200 (before a 1:2 split) and 110 (after) draw 100 → 110 adjusted.

    Each anchor uses its own date's factor: 0.5 before the ex-date (Thursday,
    index 3), 1 from it. The adjusted closes cross the drawn line, not a line
    through the traded prices (200 → 110 would slope down).
    """
    factor = {d: D("0.5") if d < SESSIONS[3] else D(1) for d in SESSIONS}
    traded = ((SESSIONS[2], D(200)), (SESSIONS[4], D(110)))
    adjusted = tuple((d, p * factor[d]) for d, p in traded)
    assert adjusted == UP
    closes = _points("0", "0", "99", "104", "111")  # adjusted closes, as the chart shows them
    levels = line_levels("trendline", adjusted, SESSIONS[:5])  # type: ignore[arg-type]
    assert first_line_firing("crosses_above", SESSIONS[0], closes, levels) == Firing(
        SESSIONS[4], D(111)
    )
