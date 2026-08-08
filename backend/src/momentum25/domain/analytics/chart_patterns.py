"""Classical chart-pattern detection — a labelling of price geometry, not a signal.

Scope and intent
----------------
This module recognises the classical chart patterns and reports, for each
candidate, which *structural criteria* were met and the geometry that supports
it. It is a display/labelling feature only:

* it never emits a buy/sell verdict,
* it never emits a target price, price objective or profit projection,
* it never feeds the ranking/screening engines — nothing here participates in
  the composite score.

Detection criteria follow the geometric definitions used in the standard
reference literature on chart patterns (Bulkowski, *Encyclopedia of Chart
Patterns*, 2nd ed.): identification is by pivot geometry, trendline slope,
symmetry and volume behaviour. Where a numeric bound is used it is stated as a
named constant below so every accepted pattern is explainable down to the
measurement that qualified it.

Pivots come from :func:`momentum25.domain.analytics.elliott_wave.zigzag_pivots`
— the same confirmed-reversal pivot definition already used for wave labelling,
so this module adds no second notion of a swing point. Cup-with-handle bounds
are taken from the existing
:class:`momentum25.domain.patterns.cup_handle.CupWithHandleDetector` so the two
code paths cannot drift apart on what a cup is.

Everything here is pure and deterministic: same bars in, same patterns and
scores out. No I/O, no clock, no randomness.

Known limitation: flags and pennants are detected for an *upward* pole only.
The platform is long-only momentum, and the down-pole mirror image has no
consumer; its absence is reported in the analysis notes rather than implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from momentum25.domain.analytics.elliott_wave import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    Pivot,
    zigzag_pivots,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.patterns.cup_handle import CupWithHandleDetector

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")

# A pattern is reported only when its final pivot is one of the last
# ``_MAX_END_OFFSET + 1`` confirmed pivots: a structure that resolved long ago
# is history, not a pattern currently on the chart.
_MAX_END_OFFSET = 2

# ── Head & shoulders ────────────────────────────────────────────────────
_HS_MIN_HEAD_DOMINANCE_PCT = Decimal("2")  # head above both shoulders
_HS_MAX_SHOULDER_ASYMMETRY_PCT = Decimal("15")
_HS_MAX_NECKLINE_TILT_PCT = Decimal("10")
_HS_MAX_TIME_ASYMMETRY_RATIO = Decimal("2.5")
_HS_MIN_SPAN_SESSIONS = 20

# ── Double top / bottom ─────────────────────────────────────────────────
_DOUBLE_MAX_PEAK_DIVERGENCE_PCT = Decimal("3")
_DOUBLE_MIN_REACTION_PCT = Decimal("8")
_DOUBLE_MIN_SEPARATION_SESSIONS = 15

# ── Trendline patterns (triangles, wedges) ──────────────────────────────
# Slope is expressed in percent of price per session.
_FLAT_SLOPE_PCT_PER_SESSION = Decimal("0.05")
_MAX_CONVERGENCE_RATIO = Decimal("0.75")  # end width vs start width
_MAX_SYMMETRICAL_SLOPE_RATIO = Decimal("3")

# ── Flags & pennants ────────────────────────────────────────────────────
_POLE_MIN_GAIN_PCT = Decimal("15")
_POLE_MAX_SESSIONS = 25
_CONSOLIDATION_MIN_SESSIONS = 5
_CONSOLIDATION_MAX_SESSIONS = 25
_CONSOLIDATION_MAX_RETRACE_PCT = Decimal("38.2")
_FLAG_SEARCH_WINDOW = 60

# ── Cup with handle ─────────────────────────────────────────────────────
_CUP_MAX_RIM_DIVERGENCE_PCT = Decimal("8")
_CUP_MIN_HANDLE_SESSIONS = CupWithHandleDetector._MIN_HANDLE_LENGTH
_CUP_MIN_DEPTH_PCT = CupWithHandleDetector._MIN_CUP_DEPTH_PCT
_CUP_MAX_DEPTH_PCT = CupWithHandleDetector._MAX_CUP_DEPTH_PCT
_CUP_MIN_WIDTH_SESSIONS = CupWithHandleDetector._MIN_CUP_LENGTH
_CUP_MAX_HANDLE_DEPTH_PCT = CupWithHandleDetector._MAX_HANDLE_DEPTH_PCT


@dataclass(frozen=True, slots=True)
class PatternCriterion:
    """One structural test a pattern must (or may) satisfy, and its measurement."""

    label: str
    met: bool
    detail: str
    required: bool


@dataclass(frozen=True, slots=True)
class GeometryPoint:
    """One (date, price) vertex of a drawn pattern outline."""

    bar_date: date
    price: Decimal


@dataclass(frozen=True, slots=True)
class GeometryLine:
    """A named polyline of the pattern's geometry, for chart overlay."""

    name: str
    points: tuple[GeometryPoint, ...]


@dataclass(frozen=True, slots=True)
class DetectedPattern:
    """One recognised pattern: name, completion score, evidence and geometry."""

    pattern: str
    display_name: str
    starts_on: date
    ends_on: date
    # Share of the pattern's criteria that were met, 0-100. All required
    # criteria are met for any reported pattern, so this measures how textbook
    # the formation is — not a probability and not a recommendation.
    completion_score: int
    criteria: tuple[PatternCriterion, ...]
    geometry: tuple[GeometryLine, ...]


@dataclass(frozen=True, slots=True)
class ChartPatternAnalysis:
    """All pattern candidates the stored history supports for one symbol."""

    symbol: str
    as_of: date | None
    threshold_pct: Decimal
    bars_analyzed: int
    pivots: tuple[Pivot, ...]
    patterns: tuple[DetectedPattern, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


# ── Shared helpers ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Ctx:
    """Bars plus a date-to-index map, so pivot spacing is in sessions not days."""

    bars: tuple[OHLCVBar, ...]
    index: dict[date, int]
    pivots: tuple[Pivot, ...]

    def sessions_between(self, a: Pivot, b: Pivot) -> int:
        return self.index[b.bar_date] - self.index[a.bar_date]

    def avg_volume(self, start: date, end: date) -> Decimal:
        lo, hi = self.index[start], self.index[end]
        window = self.bars[lo : hi + 1]
        if not window:
            return _ZERO
        return Decimal(sum(b.volume for b in window)) / Decimal(len(window))


def _pct_diff(a: Decimal, b: Decimal) -> Decimal:
    """Absolute difference between ``a`` and ``b`` as a percent of the larger."""
    ref = max(abs(a), abs(b))
    return _ZERO if ref == 0 else abs(a - b) / ref * _HUNDRED


def _slope_pct_per_session(ctx: _Ctx, a: Pivot, b: Pivot) -> Decimal:
    """Trendline slope through two pivots, in percent of ``a``'s price per session."""
    sessions = ctx.sessions_between(a, b)
    if sessions == 0 or a.price == 0:
        return _ZERO
    return (b.price - a.price) / a.price * _HUNDRED / Decimal(sessions)


def _least_squares_slope_pct(values: list[Decimal]) -> Decimal:
    """Percent-per-session slope of the least-squares line through ``values``."""
    n = len(values)
    if n < 2:
        return _ZERO
    mean_x = Decimal(n - 1) / Decimal(2)
    mean_y = sum(values, _ZERO) / Decimal(n)
    num = sum(
        ((Decimal(i) - mean_x) * (v - mean_y) for i, v in enumerate(values)),
        _ZERO,
    )
    den = sum(((Decimal(i) - mean_x) ** 2 for i in range(n)), _ZERO)
    if den == 0 or mean_y == 0:
        return _ZERO
    return num / den / mean_y * _HUNDRED


def _score(criteria: tuple[PatternCriterion, ...]) -> int:
    met = sum(1 for c in criteria if c.met)
    return int(round(met * 100 / len(criteria))) if criteria else 0


def _emit(
    pattern: str,
    display_name: str,
    starts_on: date,
    ends_on: date,
    criteria: tuple[PatternCriterion, ...],
    geometry: tuple[GeometryLine, ...],
) -> DetectedPattern | None:
    """Return the pattern only if every *required* criterion is met."""
    if not all(c.met for c in criteria if c.required):
        return None
    return DetectedPattern(
        pattern=pattern,
        display_name=display_name,
        starts_on=starts_on,
        ends_on=ends_on,
        completion_score=_score(criteria),
        criteria=criteria,
        geometry=geometry,
    )


def _point(p: Pivot) -> GeometryPoint:
    return GeometryPoint(p.bar_date, p.price)


def _outline(name: str, pivots: tuple[Pivot, ...]) -> GeometryLine:
    return GeometryLine(name, tuple(_point(p) for p in pivots))


def _windows(ctx: _Ctx, kinds: str) -> list[tuple[Pivot, ...]]:
    """Consecutive pivot runs matching ``kinds`` and ending near the last pivot."""
    size = len(kinds)
    n = len(ctx.pivots)
    out: list[tuple[Pivot, ...]] = []
    for start in range(n - size + 1):
        end = start + size - 1
        if end < n - 1 - _MAX_END_OFFSET:
            continue
        window = ctx.pivots[start : start + size]
        if "".join(p.kind for p in window) == kinds:
            out.append(window)
    return out


def _volume_declines(ctx: _Ctx, early: tuple[date, date], late: tuple[date, date]) -> Decimal:
    """Late-window average volume as a percent of the early window's (100 = flat)."""
    early_avg = ctx.avg_volume(*early)
    late_avg = ctx.avg_volume(*late)
    if early_avg == 0:
        return _HUNDRED
    return late_avg / early_avg * _HUNDRED


# ── Head & shoulders (and inverse) ───────────────────────────────────────


def _head_and_shoulders(ctx: _Ctx) -> list[DetectedPattern]:
    found: list[DetectedPattern] = []
    for kinds, pattern, name, top in (
        ("HLHLH", "head_and_shoulders", "Head & Shoulders", True),
        ("LHLHL", "inverse_head_and_shoulders", "Inverse Head & Shoulders", False),
    ):
        for window in _windows(ctx, kinds):
            left, t1, head, t2, right = window
            sign = Decimal("1") if top else Decimal("-1")
            head_over_left = sign * (head.price - left.price) / left.price * _HUNDRED
            head_over_right = sign * (head.price - right.price) / right.price * _HUNDRED
            head_dominance = min(head_over_left, head_over_right)
            shoulder_asymmetry = _pct_diff(left.price, right.price)
            neckline_tilt = _pct_diff(t1.price, t2.price)
            left_span = ctx.sessions_between(left, head)
            right_span = ctx.sessions_between(head, right)
            time_ratio = Decimal(max(left_span, right_span)) / Decimal(
                max(min(left_span, right_span), 1)
            )
            span = ctx.sessions_between(left, right)
            vol_ratio = _volume_declines(
                ctx, (left.bar_date, head.bar_date), (head.bar_date, right.bar_date)
            )
            criteria = (
                PatternCriterion(
                    f"Head exceeds both shoulders by ≥ {_HS_MIN_HEAD_DOMINANCE_PCT}%",
                    head_dominance >= _HS_MIN_HEAD_DOMINANCE_PCT,
                    f"head is {head_dominance:.1f}% beyond the nearer shoulder",
                    required=True,
                ),
                PatternCriterion(
                    f"Formation spans ≥ {_HS_MIN_SPAN_SESSIONS} sessions",
                    span >= _HS_MIN_SPAN_SESSIONS,
                    f"{span} sessions from left shoulder to right shoulder",
                    required=True,
                ),
                PatternCriterion(
                    f"Shoulders within {_HS_MAX_SHOULDER_ASYMMETRY_PCT}% of each other",
                    shoulder_asymmetry <= _HS_MAX_SHOULDER_ASYMMETRY_PCT,
                    f"shoulders differ by {shoulder_asymmetry:.1f}%",
                    required=False,
                ),
                PatternCriterion(
                    f"Neckline near-level (armpits within {_HS_MAX_NECKLINE_TILT_PCT}%)",
                    neckline_tilt <= _HS_MAX_NECKLINE_TILT_PCT,
                    f"neckline points differ by {neckline_tilt:.1f}%",
                    required=False,
                ),
                PatternCriterion(
                    f"Time symmetry within {_HS_MAX_TIME_ASYMMETRY_RATIO}:1",
                    time_ratio <= _HS_MAX_TIME_ASYMMETRY_RATIO,
                    f"{left_span} vs {right_span} sessions either side of the head",
                    required=False,
                ),
                PatternCriterion(
                    "Volume lower on the right half than the left",
                    vol_ratio < _HUNDRED,
                    f"right-half volume is {vol_ratio:.0f}% of the left half",
                    required=False,
                ),
            )
            emitted = _emit(
                pattern,
                name,
                left.bar_date,
                right.bar_date,
                criteria,
                (
                    _outline("Formation", window),
                    GeometryLine("Neckline", (_point(t1), _point(t2))),
                ),
            )
            if emitted is not None:
                found.append(emitted)
    return found


# ── Double top / double bottom ───────────────────────────────────────────


def _double_top_bottom(ctx: _Ctx) -> list[DetectedPattern]:
    found: list[DetectedPattern] = []
    for kinds, pattern, name, top in (
        ("HLH", "double_top", "Double Top", True),
        ("LHL", "double_bottom", "Double Bottom", False),
    ):
        for window in _windows(ctx, kinds):
            first, middle, second = window
            divergence = _pct_diff(first.price, second.price)
            ref = min(first.price, second.price) if top else max(first.price, second.price)
            reaction = abs(middle.price - ref) / ref * _HUNDRED
            separation = ctx.sessions_between(first, second)
            vol_ratio = _volume_declines(
                ctx, (first.bar_date, middle.bar_date), (middle.bar_date, second.bar_date)
            )
            last_close = ctx.bars[-1].close
            confirmed = last_close < middle.price if top else last_close > middle.price

            criteria = (
                PatternCriterion(
                    f"Two turns within {_DOUBLE_MAX_PEAK_DIVERGENCE_PCT}% of each other",
                    divergence <= _DOUBLE_MAX_PEAK_DIVERGENCE_PCT,
                    f"the two extremes differ by {divergence:.1f}%",
                    required=True,
                ),
                PatternCriterion(
                    f"Intervening reaction ≥ {_DOUBLE_MIN_REACTION_PCT}%",
                    reaction >= _DOUBLE_MIN_REACTION_PCT,
                    f"reaction of {reaction:.1f}% between the two turns",
                    required=True,
                ),
                PatternCriterion(
                    f"Turns separated by ≥ {_DOUBLE_MIN_SEPARATION_SESSIONS} sessions",
                    separation >= _DOUBLE_MIN_SEPARATION_SESSIONS,
                    f"{separation} sessions apart",
                    required=True,
                ),
                PatternCriterion(
                    "Volume lower into the second turn",
                    vol_ratio < _HUNDRED,
                    f"second-leg volume is {vol_ratio:.0f}% of the first leg",
                    required=False,
                ),
                PatternCriterion(
                    "Confirmation line already crossed by the latest close",
                    confirmed,
                    (f"latest close {last_close:.2f} vs confirmation level {middle.price:.2f}"),
                    required=False,
                ),
            )
            emitted = _emit(
                pattern,
                name,
                first.bar_date,
                second.bar_date,
                criteria,
                (
                    _outline("Formation", window),
                    GeometryLine(
                        "Confirmation level",
                        (
                            GeometryPoint(first.bar_date, middle.price),
                            GeometryPoint(ctx.bars[-1].date, middle.price),
                        ),
                    ),
                ),
            )
            if emitted is not None:
                found.append(emitted)
    return found


# ── Triangles and wedges ─────────────────────────────────────────────────


def _describe_slope(slope: Decimal) -> str:
    if abs(slope) < _FLAT_SLOPE_PCT_PER_SESSION:
        return f"flat ({slope:+.3f}%/session)"
    return f"{'rising' if slope > 0 else 'falling'} ({slope:+.3f}%/session)"


_TRENDLINE_SHAPES: tuple[tuple[str, str, str, str], ...] = (
    # (pattern id, display name, upper-line requirement, lower-line requirement)
    ("ascending_triangle", "Ascending Triangle", "flat", "rising"),
    ("descending_triangle", "Descending Triangle", "falling", "flat"),
    ("symmetrical_triangle", "Symmetrical Triangle", "falling", "rising"),
    ("rising_wedge", "Rising Wedge", "rising", "rising"),
    ("falling_wedge", "Falling Wedge", "falling", "falling"),
)


def _slope_matches(slope: Decimal, requirement: str) -> bool:
    if requirement == "flat":
        return abs(slope) < _FLAT_SLOPE_PCT_PER_SESSION
    if requirement == "rising":
        return slope >= _FLAT_SLOPE_PCT_PER_SESSION
    return slope <= -_FLAT_SLOPE_PCT_PER_SESSION


def _trendline_patterns(ctx: _Ctx) -> list[DetectedPattern]:
    found: list[DetectedPattern] = []
    for kinds in ("HLHL", "LHLH"):
        for window in _windows(ctx, kinds):
            highs = tuple(p for p in window if p.kind == "H")
            lows = tuple(p for p in window if p.kind == "L")
            if len(highs) != 2 or len(lows) != 2:
                continue
            upper_slope = _slope_pct_per_session(ctx, *highs)
            lower_slope = _slope_pct_per_session(ctx, *lows)
            start_width = _pct_diff(highs[0].price, lows[0].price)
            end_width = _pct_diff(highs[1].price, lows[1].price)
            convergence = end_width / start_width if start_width > 0 else Decimal("1")
            first, last = window[0], window[-1]
            mid = (
                ctx.index[first.bar_date]
                + (ctx.index[last.bar_date] - ctx.index[first.bar_date]) // 2
            )
            vol_ratio = _volume_declines(
                ctx,
                (first.bar_date, ctx.bars[mid].date),
                (ctx.bars[mid].date, last.bar_date),
            )
            last_close = ctx.bars[-1].close
            inside = min(p.price for p in lows) <= last_close <= max(p.price for p in highs)

            for pattern, name, upper_req, lower_req in _TRENDLINE_SHAPES:
                if pattern == "symmetrical_triangle":
                    ratio_ok = max(
                        abs(upper_slope), abs(lower_slope)
                    ) <= _MAX_SYMMETRICAL_SLOPE_RATIO * max(
                        min(abs(upper_slope), abs(lower_slope)), Decimal("0.0001")
                    )
                else:
                    ratio_ok = True

                criteria = (
                    PatternCriterion(
                        f"Upper trendline {upper_req}",
                        _slope_matches(upper_slope, upper_req) and ratio_ok,
                        f"upper trendline is {_describe_slope(upper_slope)}",
                        required=True,
                    ),
                    PatternCriterion(
                        f"Lower trendline {lower_req}",
                        _slope_matches(lower_slope, lower_req) and ratio_ok,
                        f"lower trendline is {_describe_slope(lower_slope)}",
                        required=True,
                    ),
                    PatternCriterion(
                        "Four alternating touch points (2 highs, 2 lows)",
                        True,
                        f"{len(window)} confirmed pivots define the two trendlines",
                        required=True,
                    ),
                    PatternCriterion(
                        f"Range contracts to ≤ {_MAX_CONVERGENCE_RATIO:.0%} of its start",
                        convergence <= _MAX_CONVERGENCE_RATIO,
                        f"range narrowed to {convergence:.0%} of the opening width",
                        required=True,
                    ),
                    PatternCriterion(
                        "Volume contracts through the formation",
                        vol_ratio < _HUNDRED,
                        f"second-half volume is {vol_ratio:.0f}% of the first half",
                        required=False,
                    ),
                    PatternCriterion(
                        "Latest close still inside the formation",
                        inside,
                        f"latest close {last_close:.2f}",
                        required=False,
                    ),
                )
                emitted = _emit(
                    pattern,
                    name,
                    first.bar_date,
                    last.bar_date,
                    criteria,
                    (
                        GeometryLine("Upper trendline", tuple(_point(p) for p in highs)),
                        GeometryLine("Lower trendline", tuple(_point(p) for p in lows)),
                    ),
                )
                if emitted is not None:
                    found.append(emitted)
    return found


# ── Flags & pennants ─────────────────────────────────────────────────────


def _flag_or_pennant(ctx: _Ctx) -> list[DetectedPattern]:
    bars = ctx.bars
    if len(bars) < _FLAG_SEARCH_WINDOW:
        return []
    search = bars[-_FLAG_SEARCH_WINDOW:]

    # Pole top: the highest high in the search window (earliest such bar, so the
    # consolidation that follows is the longest one consistent with that high).
    top_i = max(range(len(search)), key=lambda i: (search[i].high, -i))
    pole_lo_start = max(0, top_i - _POLE_MAX_SESSIONS)
    if top_i == 0:
        return []
    base_i = min(range(pole_lo_start, top_i), key=lambda i: (search[i].low, i))
    pole_low, pole_high = search[base_i].low, search[top_i].high
    if pole_low <= 0:
        return []
    pole_gain = (pole_high - pole_low) / pole_low * _HUNDRED
    pole_sessions = top_i - base_i

    consolidation = search[top_i + 1 :]
    if len(consolidation) < _CONSOLIDATION_MIN_SESSIONS:
        return []
    cons_low = min(b.low for b in consolidation)
    retrace = (
        (pole_high - cons_low) / (pole_high - pole_low) * _HUNDRED
        if pole_high > pole_low
        else _HUNDRED
    )
    high_slope = _least_squares_slope_pct([b.high for b in consolidation])
    low_slope = _least_squares_slope_pct([b.low for b in consolidation])
    converging = high_slope < low_slope
    vol_ratio = _volume_declines(
        ctx,
        (search[base_i].date, search[top_i].date),
        (consolidation[0].date, consolidation[-1].date),
    )

    pattern, name = ("pennant", "Pennant") if converging else ("flag", "Flag")
    criteria = (
        PatternCriterion(
            f"Flagpole advance ≥ {_POLE_MIN_GAIN_PCT}% in ≤ {_POLE_MAX_SESSIONS} sessions",
            pole_gain >= _POLE_MIN_GAIN_PCT and pole_sessions <= _POLE_MAX_SESSIONS,
            f"{pole_gain:.1f}% over {pole_sessions} sessions",
            required=True,
        ),
        PatternCriterion(
            f"Consolidation of {_CONSOLIDATION_MIN_SESSIONS}"
            f"–{_CONSOLIDATION_MAX_SESSIONS} sessions",
            _CONSOLIDATION_MIN_SESSIONS <= len(consolidation) <= _CONSOLIDATION_MAX_SESSIONS,
            f"{len(consolidation)} sessions since the pole high",
            required=True,
        ),
        PatternCriterion(
            f"Consolidation retraces ≤ {_CONSOLIDATION_MAX_RETRACE_PCT}% of the pole",
            retrace <= _CONSOLIDATION_MAX_RETRACE_PCT,
            f"retraced {retrace:.1f}% of the pole",
            required=True,
        ),
        PatternCriterion(
            "Consolidation boundaries converge (pennant) rather than run parallel (flag)",
            converging,
            (
                f"upper boundary {high_slope:+.3f}%/session, "
                f"lower boundary {low_slope:+.3f}%/session"
            ),
            required=False,
        ),
        PatternCriterion(
            "Volume contracts through the consolidation",
            vol_ratio < _HUNDRED,
            f"consolidation volume is {vol_ratio:.0f}% of the pole's",
            required=False,
        ),
    )
    emitted = _emit(
        pattern,
        name,
        search[base_i].date,
        consolidation[-1].date,
        criteria,
        (
            GeometryLine(
                "Flagpole",
                (
                    GeometryPoint(search[base_i].date, pole_low),
                    GeometryPoint(search[top_i].date, pole_high),
                ),
            ),
            GeometryLine(
                "Upper boundary",
                (
                    GeometryPoint(consolidation[0].date, consolidation[0].high),
                    GeometryPoint(consolidation[-1].date, max(b.high for b in consolidation[-3:])),
                ),
            ),
            GeometryLine(
                "Lower boundary",
                (
                    GeometryPoint(consolidation[0].date, consolidation[0].low),
                    GeometryPoint(consolidation[-1].date, min(b.low for b in consolidation[-3:])),
                ),
            ),
        ),
    )
    return [emitted] if emitted is not None else []


# ── Cup with handle ──────────────────────────────────────────────────────


def _cup_with_handle(ctx: _Ctx) -> list[DetectedPattern]:
    found: list[DetectedPattern] = []
    for window in _windows(ctx, "HLH"):
        left_rim, cup_low, right_rim = window
        if left_rim.price <= 0:
            continue
        depth = (left_rim.price - cup_low.price) / left_rim.price * _HUNDRED
        width = ctx.sessions_between(left_rim, right_rim)
        rim_divergence = _pct_diff(left_rim.price, right_rim.price)

        rim_i = ctx.index[right_rim.bar_date]
        handle_bars = ctx.bars[rim_i + 1 :]
        if len(handle_bars) < _CUP_MIN_HANDLE_SESSIONS:
            continue
        handle_low = min(b.low for b in handle_bars)
        handle_depth = (right_rim.price - handle_low) / right_rim.price * _HUNDRED
        vol_ratio = _volume_declines(
            ctx,
            (cup_low.bar_date, right_rim.bar_date),
            (handle_bars[0].date, handle_bars[-1].date),
        )
        # Rounded rather than V-shaped: the cup spends a meaningful share of its
        # width in the lower third of its depth.
        lo_i, hi_i = ctx.index[left_rim.bar_date], rim_i
        lower_third = left_rim.price - (left_rim.price - cup_low.price) * Decimal("2") / Decimal(
            "3"
        )
        bars_low = sum(1 for b in ctx.bars[lo_i : hi_i + 1] if b.low <= lower_third)
        rounded_pct = Decimal(bars_low) / Decimal(max(width, 1)) * _HUNDRED

        criteria = (
            PatternCriterion(
                f"Cup depth {_CUP_MIN_DEPTH_PCT}–{_CUP_MAX_DEPTH_PCT}%",
                _CUP_MIN_DEPTH_PCT <= depth <= _CUP_MAX_DEPTH_PCT,
                f"cup is {depth:.1f}% deep",
                required=True,
            ),
            PatternCriterion(
                f"Cup width ≥ {_CUP_MIN_WIDTH_SESSIONS} sessions",
                width >= _CUP_MIN_WIDTH_SESSIONS,
                f"{width} sessions rim to rim",
                required=True,
            ),
            PatternCriterion(
                f"Rims within {_CUP_MAX_RIM_DIVERGENCE_PCT}% of each other",
                rim_divergence <= _CUP_MAX_RIM_DIVERGENCE_PCT,
                f"rims differ by {rim_divergence:.1f}%",
                required=True,
            ),
            PatternCriterion(
                f"Handle depth ≤ {_CUP_MAX_HANDLE_DEPTH_PCT}%",
                handle_depth <= _CUP_MAX_HANDLE_DEPTH_PCT,
                f"handle pulled back {handle_depth:.1f}% from the right rim",
                required=True,
            ),
            PatternCriterion(
                f"Handle at least {_CUP_MIN_HANDLE_SESSIONS} sessions long",
                len(handle_bars) >= _CUP_MIN_HANDLE_SESSIONS,
                f"{len(handle_bars)} sessions since the right rim",
                required=True,
            ),
            PatternCriterion(
                "Volume contraction in the handle",
                vol_ratio < _HUNDRED,
                f"handle volume is {vol_ratio:.0f}% of the cup's right side",
                required=False,
            ),
            PatternCriterion(
                "Rounded (not V-shaped) base",
                rounded_pct >= _HUNDRED / Decimal("5"),
                f"{rounded_pct:.0f}% of the cup sits in its lower third",
                required=False,
            ),
        )
        emitted = _emit(
            "cup_with_handle",
            "Cup with Handle",
            left_rim.bar_date,
            handle_bars[-1].date,
            criteria,
            (
                _outline("Cup", window),
                GeometryLine(
                    "Handle",
                    (
                        _point(right_rim),
                        GeometryPoint(handle_bars[-1].date, handle_low),
                    ),
                ),
            ),
        )
        if emitted is not None:
            found.append(emitted)
    return found


_DETECTORS = (
    _head_and_shoulders,
    _double_top_bottom,
    _trendline_patterns,
    _flag_or_pennant,
    _cup_with_handle,
)


def detect_chart_patterns(
    symbol: str,
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
) -> ChartPatternAnalysis:
    """Return every classical pattern the visible history structurally supports.

    All plausible candidates are returned, ordered by completion score then
    name: when the same price action fits more than one definition that
    ambiguity is reported rather than resolved into a single best guess, and
    when nothing qualifies the empty result is the answer.
    """
    ordered = tuple(bars)
    pivots = zigzag_pivots(ordered, threshold_pct)
    ctx = _Ctx(
        bars=ordered,
        index={b.date: i for i, b in enumerate(ordered)},
        pivots=pivots,
    )

    patterns: list[DetectedPattern] = []
    if ordered and len(pivots) >= 1:
        for detector in _DETECTORS:
            patterns.extend(detector(ctx))
    patterns.sort(key=lambda p: (-p.completion_score, p.pattern, p.starts_on))

    notes: list[str] = []
    if not ordered:
        notes.append("No price history available.")
    elif len(pivots) < 3:
        notes.append(
            f"Only {len(pivots)} confirmed pivot(s) at a {threshold_pct}% reversal "
            "threshold — too few to define most classical formations."
        )
    if ordered and not patterns:
        notes.append(
            "No classical chart pattern currently meets its structural criteria on "
            "this history. That absence is the result, not a failure to look."
        )
    elif len(patterns) > 1:
        notes.append(
            f"{len(patterns)} formations fit this price action. They are alternative "
            "readings of the same bars, not independent confirmations."
        )
    notes.append(
        "Flags and pennants are detected for an upward flagpole only; a downward "
        "pole is not searched for."
    )

    return ChartPatternAnalysis(
        symbol=symbol,
        as_of=ordered[-1].date if ordered else None,
        threshold_pct=threshold_pct,
        bars_analyzed=len(ordered),
        pivots=pivots,
        patterns=tuple(patterns),
        notes=tuple(notes),
    )
