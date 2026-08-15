"""Unit tests for domain engines.

Verifies that all engines return valid :class:`EngineResult` objects without raising,
and that deterministic rule evaluations produce expected pass/fail outcomes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.engines.breakout import BreakoutEngine
from momentum25.domain.engines.fundamental import FundamentalEngine
from momentum25.domain.engines.momentum_quality import MomentumQualityEngine
from momentum25.domain.engines.pattern import PatternEngine
from momentum25.domain.engines.relative_strength import RelativeStrengthEngine
from momentum25.domain.engines.risk import RiskEngine
from momentum25.domain.engines.trend_template import TrendTemplateEngine
from momentum25.domain.engines.volume_accumulation import VolumeAccumulationEngine
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.domain.value_objects.results import SectorStats
from momentum25.domain.value_objects.types import Symbol

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_bar(
    close: Decimal,
    open_: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
    volume: int = 1_000_000,
    day_offset: int = 0,
) -> OHLCVBar:
    """Create a single OHLCVBar with sensible defaults."""
    base_date = date(2024, 12, 1)
    from datetime import timedelta

    return OHLCVBar(
        date=base_date + timedelta(days=day_offset),
        open=open_ or close - Decimal("5"),
        high=high or close + Decimal("10"),
        low=low or close - Decimal("10"),
        close=close,
        volume=volume,
    )


def _series(
    closes: list[Decimal],
    highs: list[Decimal] | None = None,
    lows: list[Decimal] | None = None,
    volumes: list[int] | None = None,
) -> OHLCVSeries:
    """Build an OHLCVSeries from a list of close prices."""
    bars = []
    for i, c in enumerate(closes):
        h = highs[i] if highs and i < len(highs) else c + Decimal("10")
        l_ = lows[i] if lows and i < len(lows) else c - Decimal("10")
        v = volumes[i] if volumes and i < len(volumes) else 1_000_000
        bars.append(_make_bar(close=c, high=h, low=l_, volume=v, day_offset=i))
    return OHLCVSeries(security_id=1, bars=tuple(bars))


def _make_context(
    *,
    close: Decimal = Decimal("150"),
    sma50: Decimal | None = Decimal("140"),
    sma150: Decimal | None = Decimal("130"),
    sma200: Decimal | None = Decimal("120"),
    sma200_slope_pct: Decimal | None = Decimal("2.5"),
    low_52w: Decimal | None = Decimal("100"),
    high_52w: Decimal | None = Decimal("200"),
    rs_rating: int | None = 85,
    pct_above_low_52w: Decimal | None = None,
    pct_below_high_52w: Decimal | None = None,
    ema10: Decimal | None = None,
    ema21: Decimal | None = None,
    rsi14: Decimal | None = None,
    atr14: Decimal | None = None,
    swing_resistance: Decimal | None = None,
    adr_pct: Decimal | None = None,
    avg_volume50: Decimal | None = None,
    rel_volume: Decimal | None = None,
    rs_line_slope: Decimal | None = None,
    closes: list[Decimal] | None = None,
    highs: list[Decimal] | None = None,
    lows: list[Decimal] | None = None,
    volumes: list[int] | None = None,
    sector: str = "Technology",
    sector_rs_percentile: Decimal | None = None,
    industry_rs_percentile: Decimal | None = None,
    by_sector: dict[str, list[Decimal]] | None = None,
    by_industry: dict[str, list[Decimal]] | None = None,
) -> EvaluationContext:
    """Build an EvaluationContext with a given set of indicators."""
    security = Security(
        id=1, symbol=Symbol("RELIANCE"), name="Reliance Industries Ltd", sector=sector
    )

    if closes is not None:
        series = _series(closes, highs=highs, lows=lows, volumes=volumes)
    else:
        bar = _make_bar(close=close)
        series = OHLCVSeries(security_id=1, bars=(bar,))

    indicators = IndicatorSet(
        as_of=date(2024, 12, 1),
        sma50=sma50,
        sma150=sma150,
        sma200=sma200,
        sma200_slope_pct=sma200_slope_pct,
        low_52w=low_52w,
        high_52w=high_52w,
        pct_above_low_52w=pct_above_low_52w,
        pct_below_high_52w=pct_below_high_52w,
        rs_rating=rs_rating,
        ema10=ema10,
        ema21=ema21,
        rsi14=rsi14,
        atr14=atr14,
        swing_resistance=swing_resistance,
        adr_pct=adr_pct,
        avg_volume50=avg_volume50,
        rel_volume=rel_volume,
        rs_line_slope=rs_line_slope,
        sector_rs_percentile=sector_rs_percentile,
        industry_rs_percentile=industry_rs_percentile,
    )
    benchmark_bar = _make_bar(close=Decimal("10000"))
    benchmark = OHLCVSeries(security_id=0, bars=(benchmark_bar,))
    sector_stats = SectorStats(
        by_sector=by_sector or {},
        by_industry=by_industry or {},
    )
    return EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=benchmark,
        sector_stats=sector_stats,
    )


def _make_config(
    engine_id: str = "test",
    rules: tuple[RuleConfig, ...] = (),
    weight: Decimal = Decimal("1"),
    gate: bool = False,
) -> EngineConfig:
    return EngineConfig(id=engine_id, enabled=True, weight=weight, rules=rules, gate=gate)


# ═══════════════════════════════════════════════════════════════════════════════
# Placeholder engines (unchanged from original)
# ═══════════════════════════════════════════════════════════════════════════════

_NON_TREND_ENGINES = [
    PatternEngine(),
    FundamentalEngine(),
]


@pytest.mark.parametrize("engine", _NON_TREND_ENGINES, ids=lambda e: e.engine_id)
def test_placeholder_engine_returns_valid_result(
    engine: object,
) -> None:
    """Placeholder engines must return an :class:`EngineResult` without raising."""
    ctx = _make_context()
    cfg = _make_config()
    result = engine.evaluate(ctx, cfg)  # type: ignore[union-attr]
    assert result.engine_id == engine.engine_id  # type: ignore[union-attr]
    assert isinstance(result.engine_score, Decimal)
    assert isinstance(result.passed_gate, bool)
    assert len(result.rule_results) > 0
    for rule in result.rule_results:
        assert rule.rule_id
        assert rule.engine_id == engine.engine_id  # type: ignore[union-attr]
        assert isinstance(rule.passed, bool)
        assert isinstance(rule.weight, Decimal)
        assert isinstance(rule.contribution, Decimal)


# ═══════════════════════════════════════════════════════════════════════════════
# Trend Template Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_trend_template_strict_compliance() -> None:
    """All 8 Trend Template rules pass => passed_gate=True, score=1.0."""
    engine = TrendTemplateEngine()
    ctx = _make_context(
        close=Decimal("150"),
        sma50=Decimal("140"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        sma200_slope_pct=Decimal("2.5"),
        low_52w=Decimal("100"),
        high_52w=Decimal("200"),
        rs_rating=85,
        pct_above_low_52w=Decimal("50"),
        pct_below_high_52w=Decimal("25"),
    )
    cfg = _make_config("trend_template")

    result = engine.evaluate(ctx, cfg)
    assert result.passed_gate is True
    assert result.engine_score == Decimal("1")
    assert result.metrics["checklist"]["tt_close_above_sma150_200"] is True
    assert result.metrics["checklist"]["tt_sma200_uptrend"] is True
    assert result.metrics["checklist"]["tt_rs_rating_min"] is True
    assert len(result.rule_results) == 8


def test_trend_template_fails_on_descending_ma200() -> None:
    """Descending SMA200 must fail tt_sma200_uptrend and thus the overall gate."""
    engine = TrendTemplateEngine()
    ctx = _make_context(
        close=Decimal("150"),
        sma50=Decimal("140"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        sma200_slope_pct=Decimal("-1.5"),
        low_52w=Decimal("100"),
        high_52w=Decimal("200"),
        rs_rating=85,
    )
    cfg = _make_config("trend_template")

    result = engine.evaluate(ctx, cfg)
    assert result.passed_gate is False
    assert result.engine_score == Decimal(str(7)) / Decimal("8")
    assert result.metrics["checklist"]["tt_sma200_uptrend"] is False
    assert result.metrics["checklist"]["tt_close_above_sma150_200"] is True


def test_trend_template_fails_low_rs_rating() -> None:
    """RS rating below 70 fails tt_rs_rating_min."""
    engine = TrendTemplateEngine()
    ctx = _make_context(
        close=Decimal("150"),
        sma50=Decimal("140"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        sma200_slope_pct=Decimal("2.5"),
        low_52w=Decimal("100"),
        high_52w=Decimal("200"),
        rs_rating=50,
    )
    cfg = _make_config("trend_template")

    result = engine.evaluate(ctx, cfg)
    assert result.passed_gate is False
    assert result.metrics["checklist"]["tt_rs_rating_min"] is False


def test_trend_template_missing_indicators() -> None:
    """Missing indicator values produce failed RuleResults."""
    engine = TrendTemplateEngine()
    # All indicators None -> all 8 rules fail
    ctx = _make_context(
        close=Decimal("150"),
        sma50=None,
        sma150=None,
        sma200=None,
        sma200_slope_pct=None,
        low_52w=None,
        high_52w=None,
        rs_rating=None,
    )
    cfg = _make_config("trend_template")

    result = engine.evaluate(ctx, cfg)
    assert result.passed_gate is False
    assert result.engine_score == Decimal("0")
    assert len(result.rule_results) == 8
    assert all(not r.passed for r in result.rule_results)


def test_trend_template_sma_stack() -> None:
    """tt_sma_stack requires SMA50 > SMA150 > SMA200."""
    engine = TrendTemplateEngine()
    # Bullish stack: 50 > 150 > 200
    ctx = _make_context(
        close=Decimal("150"),
        sma50=Decimal("140"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        rs_rating=85,
    )
    cfg = _make_config("trend_template")
    result = engine.evaluate(ctx, cfg)
    assert result.metrics["checklist"]["tt_sma_stack"] is True

    # SMA50 < SMA150 -> stack broken
    ctx2 = _make_context(
        close=Decimal("150"),
        sma50=Decimal("120"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        rs_rating=85,
    )
    result2 = engine.evaluate(ctx2, cfg)
    assert result2.metrics["checklist"]["tt_sma_stack"] is False


def test_trend_template_near_52w_high() -> None:
    """tt_near_52w_high uses pct_below_high_52w <= 25."""
    engine = TrendTemplateEngine()
    # 10% below high -> pass (<= 25)
    ctx = _make_context(
        close=Decimal("180"),
        high_52w=Decimal("200"),
        pct_below_high_52w=Decimal("10"),
        rs_rating=85,
    )
    cfg = _make_config("trend_template")
    result = engine.evaluate(ctx, cfg)
    assert result.metrics["checklist"]["tt_near_52w_high"] is True

    # 50% below high -> fail (> 25)
    ctx2 = _make_context(
        close=Decimal("100"),
        high_52w=Decimal("200"),
        pct_below_high_52w=Decimal("50"),
        rs_rating=85,
    )
    result2 = engine.evaluate(ctx2, cfg)
    assert result2.metrics["checklist"]["tt_near_52w_high"] is False


def test_trend_template_above_52w_low() -> None:
    """tt_above_52w_low uses pct_above_low_52w >= 30."""
    engine = TrendTemplateEngine()
    # 50% above low -> pass
    ctx = _make_context(
        close=Decimal("150"),
        low_52w=Decimal("100"),
        pct_above_low_52w=Decimal("50"),
        rs_rating=85,
    )
    cfg = _make_config("trend_template")
    result = engine.evaluate(ctx, cfg)
    assert result.metrics["checklist"]["tt_above_52w_low"] is True

    # 10% above low -> fail
    ctx2 = _make_context(
        close=Decimal("110"),
        low_52w=Decimal("100"),
        pct_above_low_52w=Decimal("10"),
        rs_rating=85,
    )
    result2 = engine.evaluate(ctx2, cfg)
    assert result2.metrics["checklist"]["tt_above_52w_low"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Relative Strength Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_relative_strength_high_rating() -> None:
    """High RS rating > 70 passes rs_rating with normalised contribution."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(rs_rating=90)
    rules = (
        RuleConfig(id="rs_rating", weight=Decimal("2"), params={"norm_min": 70, "norm_max": 99}),
    )
    cfg = _make_config("relative_strength", rules=rules, weight=Decimal("2"))

    result = engine.evaluate(ctx, cfg)
    assert result.engine_id == "relative_strength"
    # Only rs_rating is declared in cfg.rules -- the other 3 rule ids must
    # not be evaluated at all (ADR-005: cfg.rules controls inclusion).
    assert len(result.rule_results) == 1
    # rs_rating should have passed
    rating_rule = next(r for r in result.rule_results if r.rule_id == "rs_rating")
    assert rating_rule.passed is True
    assert rating_rule.contribution > 0


def test_relative_strength_excludes_rules_not_in_config() -> None:
    """A rule id absent from cfg.rules must not be evaluated at all (ADR-005)."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(rs_rating=90)
    rules = (
        RuleConfig(id="rs_rating", weight=Decimal("2"), params={"norm_min": 70, "norm_max": 99}),
        RuleConfig(id="rs_line_uptrend", weight=Decimal("1")),
    )
    cfg = _make_config("relative_strength", rules=rules, weight=Decimal("2"))

    result = engine.evaluate(ctx, cfg)
    rule_ids = {r.rule_id for r in result.rule_results}
    assert rule_ids == {"rs_rating", "rs_line_uptrend"}
    assert "rs_sector_relative" not in rule_ids
    assert "rs_industry_relative" not in rule_ids


def test_relative_strength_low_rating() -> None:
    """Low RS rating below norm_min fails rs_rating."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(rs_rating=30)
    rules = (
        RuleConfig(id="rs_rating", weight=Decimal("2"), params={"norm_min": 70, "norm_max": 99}),
    )
    cfg = _make_config("relative_strength", rules=rules, weight=Decimal("2"))

    result = engine.evaluate(ctx, cfg)
    rating_rule = next(r for r in result.rule_results if r.rule_id == "rs_rating")
    assert rating_rule.passed is False
    assert rating_rule.contribution == Decimal("0")


def test_relative_strength_missing_rating() -> None:
    """Missing RS rating returns failed rules with explanation."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(rs_rating=None)
    cfg = _make_config("relative_strength")

    result = engine.evaluate(ctx, cfg)
    rating_rule = next(r for r in result.rule_results if r.rule_id == "rs_rating")
    assert rating_rule.passed is False
    assert "unavailable" in rating_rule.explanation.lower()


def test_relative_strength_sector_relative() -> None:
    """Sector-relative RS uses sector_rs_percentile from IndicatorSet."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(
        rs_rating=85,
        sector="Technology",
        sector_rs_percentile=Decimal("80"),
    )
    cfg = _make_config("relative_strength")
    result = engine.evaluate(ctx, cfg)
    sector_rule = next(r for r in result.rule_results if r.rule_id == "rs_sector_relative")
    assert sector_rule.passed is True  # 80 >= threshold 50


def test_relative_strength_industry_relative() -> None:
    """Industry-relative RS uses industry_rs_percentile from IndicatorSet."""
    engine = RelativeStrengthEngine()
    ctx = _make_context(
        rs_rating=40,
        sector="Technology",
        industry_rs_percentile=Decimal("30"),
    )
    cfg = _make_config("relative_strength")
    result = engine.evaluate(ctx, cfg)
    industry_rule = next(r for r in result.rule_results if r.rule_id == "rs_industry_relative")
    assert industry_rule.passed is False  # 30 < threshold 50


def test_relative_strength_rs_raw_return_from_series() -> None:
    """RS raw return is reported in metrics when rs_rating is available."""
    engine = RelativeStrengthEngine()
    closes = [Decimal(str(100 + i * 0.5)) for i in range(260)]
    ctx = _make_context(
        rs_rating=75,  # Pre-computed rating
        closes=closes,
    )
    cfg = _make_config("relative_strength")
    result = engine.evaluate(ctx, cfg)
    # Rating is available, line slope is reported
    assert result.metrics["rs_rating"] == 75


# ═══════════════════════════════════════════════════════════════════════════════
# Volume & Accumulation Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_volume_accumulation_liquidity_passes() -> None:
    """High turnover passes vol_liquidity_min."""
    engine = VolumeAccumulationEngine()
    ctx = _make_context(
        close=Decimal("1500"),
        avg_volume50=Decimal("100000"),
    )
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    liq_rule = next(r for r in result.rule_results if r.rule_id == "vol_liquidity_min")
    assert liq_rule.passed is True


def test_volume_accumulation_liquidity_fails() -> None:
    """Low turnover fails vol_liquidity_min."""
    engine = VolumeAccumulationEngine()
    ctx = _make_context(
        close=Decimal("10"),
        avg_volume50=Decimal("100"),
    )
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    liq_rule = next(r for r in result.rule_results if r.rule_id == "vol_liquidity_min")
    assert liq_rule.passed is False


def test_volume_accumulation_days() -> None:
    """Accumulation days detected from close > open ratio."""
    engine = VolumeAccumulationEngine()
    # 30 bars: 20 up days (close > open), 10 down days
    closes = [Decimal("100")]
    volumes = [1_000_000]
    for _ in range(1, 30):
        closes.append(closes[-1] + Decimal("2"))
        volumes.append(1_000_000)
    ctx = _make_context(closes=closes, volumes=volumes)
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    acc_rule = next(r for r in result.rule_results if r.rule_id == "vol_accumulation_days")
    assert acc_rule.passed is True  # Most days are up


def test_volume_accumulation_breakout_confirm() -> None:
    """High relative volume passes vol_breakout_confirm."""
    engine = VolumeAccumulationEngine()
    ctx = _make_context(rel_volume=Decimal("2.0"))
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    breakout_rule = next(r for r in result.rule_results if r.rule_id == "vol_breakout_confirm")
    assert breakout_rule.passed is True


def test_volume_accumulation_breakout_fails() -> None:
    """Low relative volume fails vol_breakout_confirm."""
    engine = VolumeAccumulationEngine()
    ctx = _make_context(rel_volume=Decimal("0.5"))
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    breakout_rule = next(r for r in result.rule_results if r.rule_id == "vol_breakout_confirm")
    assert breakout_rule.passed is False


def test_volume_accumulation_missing_data() -> None:
    """Missing data produces failed rules."""
    engine = VolumeAccumulationEngine()
    ctx = _make_context(avg_volume50=None, rel_volume=None)
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    assert all(not r.passed for r in result.rule_results)


def test_volume_accumulation_institutional_net_positive() -> None:
    """With avg_volume50 set, accumulation requires above-avg volume on up-days.

    Build 30 bars where 15 days have close > open on volume = 2_000_000
    (above avg) and 0 distribution days — net = +15 > 0 → passes.
    """
    engine = VolumeAccumulationEngine()
    # avg = 1_000_000; 15 up-days at 2×avg volume, 15 neutral/low-vol days
    avg_vol = 1_000_000
    closes: list[Decimal] = []
    opens: list[Decimal] = []
    highs: list[Decimal] = []
    lows: list[Decimal] = []
    volumes: list[int] = []
    base = Decimal("100")
    for i in range(30):
        c = base + Decimal(str(i))
        if i % 2 == 0:
            # Accumulation day: close > open, volume > avg
            o = c - Decimal("3")
            v = avg_vol * 2
        else:
            # Low-volume day: close > open but below-avg volume
            o = c - Decimal("1")
            v = avg_vol // 2
        closes.append(c)
        opens.append(o)
        highs.append(c + Decimal("2"))
        lows.append(o - Decimal("2"))
        volumes.append(v)

    bars = []
    from datetime import date, timedelta

    from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries

    base_date = date(2024, 12, 1)
    for i in range(30):
        bars.append(
            OHLCVBar(
                date=base_date + timedelta(days=i),
                open=opens[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=volumes[i],
            )
        )
    series = OHLCVSeries(security_id=1, bars=tuple(bars))

    from momentum25.domain.engines.base import EvaluationContext
    from momentum25.domain.entities.security import Security
    from momentum25.domain.value_objects.indicators import IndicatorSet
    from momentum25.domain.value_objects.results import SectorStats
    from momentum25.domain.value_objects.types import Symbol

    security = Security(id=1, symbol=Symbol("TEST"), name="Test Co", sector="Technology")
    indicators = IndicatorSet(
        as_of=base_date,
        avg_volume50=Decimal(str(avg_vol)),
    )
    benchmark = OHLCVSeries(security_id=0, bars=(bars[0],))
    ctx = EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=benchmark,
        sector_stats=SectorStats(by_sector={}, by_industry={}),
    )
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    acc_rule = next(r for r in result.rule_results if r.rule_id == "vol_accumulation_days")
    assert acc_rule.passed is True
    assert (
        "institutional" in acc_rule.explanation.lower() or "accum" in acc_rule.explanation.lower()
    )


def test_volume_accumulation_institutional_net_negative() -> None:
    """Distribution dominates: more high-vol down-days than up-days → fails."""
    engine = VolumeAccumulationEngine()
    avg_vol = 1_000_000
    closes: list[Decimal] = []
    opens: list[Decimal] = []
    highs: list[Decimal] = []
    lows: list[Decimal] = []
    volumes: list[int] = []
    base = Decimal("150")
    for i in range(30):
        c = base - Decimal(str(i))
        # Distribution day: close < open, above-avg volume
        o = c + Decimal("3")
        v = avg_vol * 2
        closes.append(c)
        opens.append(o)
        highs.append(o + Decimal("1"))
        lows.append(c - Decimal("2"))
        volumes.append(v)

    bars = []
    from datetime import date, timedelta

    from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries

    base_date = date(2024, 12, 1)
    for i in range(30):
        bars.append(
            OHLCVBar(
                date=base_date + timedelta(days=i),
                open=opens[i],
                high=highs[i],
                low=lows[i],
                close=closes[i],
                volume=volumes[i],
            )
        )
    series = OHLCVSeries(security_id=1, bars=tuple(bars))

    from momentum25.domain.engines.base import EvaluationContext
    from momentum25.domain.entities.security import Security
    from momentum25.domain.value_objects.indicators import IndicatorSet
    from momentum25.domain.value_objects.results import SectorStats
    from momentum25.domain.value_objects.types import Symbol

    security = Security(id=1, symbol=Symbol("TEST"), name="Test Co", sector="Technology")
    indicators = IndicatorSet(
        as_of=base_date,
        avg_volume50=Decimal(str(avg_vol)),
    )
    benchmark = OHLCVSeries(security_id=0, bars=(bars[0],))
    ctx = EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=benchmark,
        sector_stats=SectorStats(by_sector={}, by_industry={}),
    )
    cfg = _make_config("volume_accumulation")
    result = engine.evaluate(ctx, cfg)
    acc_rule = next(r for r in result.rule_results if r.rule_id == "vol_accumulation_days")
    assert acc_rule.passed is False


# ═══════════════════════════════════════════════════════════════════════════════
# Breakout Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_breakout_pivot_breakout() -> None:
    """Close near top of 20-day range passes bo_pivot_breakout."""
    engine = BreakoutEngine()
    # 25 bars: low around 100, high around 200, latest close near top
    closes = [Decimal("150")]
    highs = [Decimal("200")]
    lows = [Decimal("100")]
    for i in range(1, 25):
        closes.append(Decimal(str(150 + i * 2)))
        highs.append(Decimal(str(200 + i)))
        lows.append(Decimal(str(100 + i)))
    closes[-1] = Decimal("195")  # Close near recent high
    ctx = _make_context(closes=closes, highs=highs, lows=lows)
    cfg = _make_config("breakout")
    result = engine.evaluate(ctx, cfg)
    pivot_rule = next(r for r in result.rule_results if r.rule_id == "bo_pivot_breakout")
    assert pivot_rule.passed is True


def test_breakout_false_breakout() -> None:
    """Close above midpoint passes bo_false_breakout."""
    engine = BreakoutEngine()
    closes = [Decimal("150")]
    for _ in range(1, 30):
        closes.append(closes[-1] + Decimal("1"))
    ctx = _make_context(closes=closes)
    cfg = _make_config("breakout")
    result = engine.evaluate(ctx, cfg)
    false_bo_rule = next(r for r in result.rule_results if r.rule_id == "bo_false_breakout")
    assert false_bo_rule.passed is True


def test_breakout_followthrough() -> None:
    """Upward price trend passes bo_followthrough."""
    engine = BreakoutEngine()
    # Strong uptrend: close > SMA5 > SMA10
    closes = [Decimal("100")]
    for _ in range(1, 15):
        closes.append(closes[-1] + Decimal("5"))
    ctx = _make_context(closes=closes)
    cfg = _make_config("breakout")
    result = engine.evaluate(ctx, cfg)
    ft_rule = next(r for r in result.rule_results if r.rule_id == "bo_followthrough")
    assert ft_rule.passed is True


def test_breakout_insufficient_data() -> None:
    """Insufficient data produces failed rules."""
    engine = BreakoutEngine()
    ctx = _make_context(closes=[Decimal("100"), Decimal("101")])
    cfg = _make_config("breakout")
    result = engine.evaluate(ctx, cfg)
    assert all(not r.passed for r in result.rule_results)


# ═══════════════════════════════════════════════════════════════════════════════
# Momentum Quality Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_momentum_quality_trend_persistence() -> None:
    """Strong uptrend passes mq_trend_persistence."""
    engine = MomentumQualityEngine()
    # 120 bars uptrending
    closes = [Decimal(str(100 + i * 2)) for i in range(120)]
    ctx = _make_context(closes=closes)
    rules = (
        RuleConfig(
            id="mq_trend_persistence", weight=Decimal("1"), params={"ma": 50, "lookback": 63}
        ),
    )
    cfg = _make_config("momentum_quality", rules=rules)
    result = engine.evaluate(ctx, cfg)
    pers_rule = next(r for r in result.rule_results if r.rule_id == "mq_trend_persistence")
    assert pers_rule.passed is True


def test_momentum_quality_acceleration() -> None:
    """Accelerating momentum: 20d return > 63d return."""
    engine = MomentumQualityEngine()
    # 100 bars: first 80 sideways/down, then 20 parabolic surge
    # 20d return = (240/140-1)*100 = 71%   (strong surge)
    # 63d return = (240/160-1)*100 = 50%   (mixed, includes flat period)
    # So 20d > 63d → acceleration detected
    closes = [Decimal("160")]
    for _ in range(1, 40):
        closes.append(closes[-1] - Decimal("0.5"))  # Decline to ~140
    for _ in range(40, 80):
        closes.append(closes[-1])  # Flat at ~140
    for _ in range(80, 100):
        closes.append(closes[-1] + Decimal("5"))  # Parabolic surge to ~240
    ctx = _make_context(closes=closes)
    cfg = _make_config("momentum_quality")
    result = engine.evaluate(ctx, cfg)
    accel_rule = next(r for r in result.rule_results if r.rule_id == "mq_acceleration")
    assert accel_rule.passed is True, f"Expected acceleration, got: {accel_rule.explanation}"


def test_momentum_quality_no_acceleration() -> None:
    """Slowing momentum: 20d return < 63d return."""
    engine = MomentumQualityEngine()
    # Decelerating: strong start, weak finish
    closes = [Decimal("100")]
    for _ in range(1, 45):
        closes.append(closes[-1] + Decimal("3"))  # Strong rise
    for _ in range(45, 65):
        closes.append(closes[-1] + Decimal("0.3"))  # Recent slowdown
    ctx = _make_context(closes=closes)
    cfg = _make_config("momentum_quality")
    result = engine.evaluate(ctx, cfg)
    accel_rule = next(r for r in result.rule_results if r.rule_id == "mq_acceleration")
    assert accel_rule.passed is False


def test_momentum_quality_insufficient_data() -> None:
    """Insufficient data produces failed rules."""
    engine = MomentumQualityEngine()
    closes = [Decimal("100"), Decimal("101"), Decimal("102")]
    ctx = _make_context(closes=closes)
    cfg = _make_config("momentum_quality")
    result = engine.evaluate(ctx, cfg)
    assert all(not r.passed for r in result.rule_results)


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Engine
# ═══════════════════════════════════════════════════════════════════════════════


def test_risk_extension_within_range() -> None:
    """Price within acceptable extension passes risk_extension."""
    engine = RiskEngine()
    ctx = _make_context(
        close=Decimal("140"),
        sma50=Decimal("130"),  # ~7.7% extension
    )
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    ext_rule = next(r for r in result.rule_results if r.rule_id == "risk_extension")
    assert ext_rule.passed is True


def test_risk_extension_overextended() -> None:
    """Price too far above MA fails risk_extension."""
    engine = RiskEngine()
    ctx = _make_context(
        close=Decimal("200"),
        sma50=Decimal("130"),  # ~54% extension
    )
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    ext_rule = next(r for r in result.rule_results if r.rule_id == "risk_extension")
    assert ext_rule.passed is False


def test_risk_atr_acceptable() -> None:
    """Low ADR% passes risk_atr."""
    engine = RiskEngine()
    ctx = _make_context(adr_pct=Decimal("2.5"))
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    atr_rule = next(r for r in result.rule_results if r.rule_id == "risk_atr")
    assert atr_rule.passed is True


def test_risk_atr_excessive() -> None:
    """High ADR% fails risk_atr."""
    engine = RiskEngine()
    ctx = _make_context(adr_pct=Decimal("15.0"))
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    atr_rule = next(r for r in result.rule_results if r.rule_id == "risk_atr")
    assert atr_rule.passed is False


def test_risk_rr_contained_downside_passes() -> None:
    """A tight ATR keeps the protective stop close beneath price.

    2026-08-09 audit / S3: ``risk_rr`` no longer computes a reward or target.
    It measures ``2 x ATR14`` as a percentage of price -- pure downside.
    Here 2 x 1 = 2 on a ~102 close is ~2%, well within the 16% ceiling.
    """
    engine = RiskEngine()
    closes = [Decimal("100") + Decimal("0.1") * i for i in range(25)]
    ctx = _make_context(closes=closes, atr14=Decimal("1"))
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    rr_rule = next(r for r in result.rule_results if r.rule_id == "risk_rr")
    assert rr_rule.passed is True, rr_rule.explanation
    assert rr_rule.raw_value is not None and rr_rule.raw_value < Decimal("3")


def test_risk_rr_wide_downside_fails() -> None:
    """A wide ATR pushes the stop far below price and fails the rule."""
    engine = RiskEngine()
    closes = [Decimal("100") + Decimal("0.1") * i for i in range(25)]
    ctx = _make_context(closes=closes, atr14=Decimal("15"))
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    rr_rule = next(r for r in result.rule_results if r.rule_id == "risk_rr")
    assert rr_rule.passed is False, rr_rule.explanation


def test_risk_rr_is_independent_of_swing_resistance() -> None:
    """Product constraint: no reward/target term may influence this rule.

    Swing resistance is the input the old reward leg read. Varying it -- or
    removing it entirely -- must not move the result by so much as a digit.
    """
    engine = RiskEngine()
    closes = [Decimal("100") + Decimal("0.1") * i for i in range(25)]
    cfg = _make_config("risk")

    results = [
        next(
            r
            for r in engine.evaluate(
                _make_context(closes=closes, atr14=Decimal("4"), swing_resistance=res),
                cfg,
            ).rule_results
            if r.rule_id == "risk_rr"
        )
        for res in (None, Decimal("90"), Decimal("150"), Decimal("1000"))
    ]

    assert len({(r.passed, r.raw_value, r.contribution) for r in results}) == 1
    for r in results:
        assert "target" not in r.explanation.lower()
        assert "reward" not in r.explanation.lower()


def test_risk_missing_data() -> None:
    """Missing indicator data produces meaningful results (not crashes)."""
    engine = RiskEngine()
    # All indicators None -> risk_extension uses series fallback but with
    # insufficient bars it should return a failed result
    ctx = _make_context(
        close=Decimal("150"),
        sma50=None,
        adr_pct=None,
        atr14=None,
    )
    cfg = _make_config("risk")
    result = engine.evaluate(ctx, cfg)
    # All rules should have explanations (not crash)
    for rule in result.rule_results:
        assert rule.explanation
    # risk_atr should fail since adr_pct is None
    atr_rule = next(r for r in result.rule_results if r.rule_id == "risk_atr")
    assert atr_rule.passed is False


# ═══════════════════════════════════════════════════════════════════════════════
# Engine determinism contract tests
# ═══════════════════════════════════════════════════════════════════════════════

_DETERMINISTIC_ENGINES = [
    TrendTemplateEngine(),
    RelativeStrengthEngine(),
    VolumeAccumulationEngine(),
    BreakoutEngine(),
    MomentumQualityEngine(),
    RiskEngine(),
]


@pytest.mark.parametrize("engine", _DETERMINISTIC_ENGINES, ids=lambda e: e.engine_id)
def test_engine_determinism(engine: object) -> None:
    """Same inputs must produce identical outputs on consecutive calls."""
    ctx = _make_context(
        close=Decimal("150"),
        sma50=Decimal("140"),
        sma150=Decimal("130"),
        sma200=Decimal("120"),
        sma200_slope_pct=Decimal("2.5"),
        low_52w=Decimal("100"),
        high_52w=Decimal("200"),
        rs_rating=85,
        avg_volume50=Decimal("100000"),
        rel_volume=Decimal("1.5"),
        adr_pct=Decimal("2.5"),
        atr14=Decimal("3.0"),
        rs_line_slope=Decimal("0.5"),
        pct_above_low_52w=Decimal("50"),
        pct_below_high_52w=Decimal("25"),
    )
    cfg = _make_config(engine.engine_id)  # type: ignore[union-attr]

    result1 = engine.evaluate(ctx, cfg)  # type: ignore[union-attr]
    result2 = engine.evaluate(ctx, cfg)  # type: ignore[union-attr]

    assert result1.engine_score == result2.engine_score
    assert result1.passed_gate == result2.passed_gate
    assert len(result1.rule_results) == len(result2.rule_results)
    for r1, r2 in zip(result1.rule_results, result2.rule_results, strict=True):
        assert r1.passed == r2.passed
        assert r1.contribution == r2.contribution
        assert r1.explanation == r2.explanation


# ═══════════════════════════════════════════════════════════════════════════════
# RS composite formula unit tests (IBD non-overlapping quarters)
# ═══════════════════════════════════════════════════════════════════════════════


def test_ibd_composite_weights_recent_quarter_more() -> None:
    """Q4 (most recent 3m) is weighted 2× in the IBD composite.

    Build a series where only Q4 is strongly positive and all prior quarters
    are flat. The composite should be positive and higher than if we averaged
    all quarters equally.
    """
    import pandas as pd

    from momentum25.infrastructure.pipelines.relative_strength_pipeline import (
        RelativeStrengthPipeline,
    )

    # 280 bars: flat for first 220 bars, then +20% surge in the last 60 bars (Q4)
    n = 280
    prices_list = [100.0] * (n - 63) + [float(100 + (i / 62) * 20) for i in range(63)]
    prices = pd.Series(prices_list)

    composite = RelativeStrengthPipeline._ibd_composite(prices)

    # Q4 is ~20%, Q3/Q2/Q1 are ~0%; composite = (2*0.20 + 0 + 0 + 0) / 5 = 0.08
    assert composite > 0.07, f"Expected composite > 0.07, got {composite:.4f}"
    assert composite < 0.12, f"Expected composite < 0.12, got {composite:.4f}"


def test_ibd_composite_insufficient_history_returns_zero() -> None:
    """_ibd_composite returns 0.0 when fewer than 253 bars are provided."""
    import pandas as pd

    from momentum25.infrastructure.pipelines.relative_strength_pipeline import (
        RelativeStrengthPipeline,
    )

    prices = pd.Series([100.0] * 200)
    assert RelativeStrengthPipeline._ibd_composite(prices) == 0.0


def test_ibd_composite_deterministic() -> None:
    """_ibd_composite returns identical results on repeated calls."""
    import pandas as pd

    from momentum25.infrastructure.pipelines.relative_strength_pipeline import (
        RelativeStrengthPipeline,
    )

    prices = pd.Series([float(100 + i * 0.1) for i in range(280)])
    v1 = RelativeStrengthPipeline._ibd_composite(prices)
    v2 = RelativeStrengthPipeline._ibd_composite(prices)
    assert v1 == v2


def test_ibd_composite_flat_market_returns_near_zero() -> None:
    """Flat prices across all quarters produce a composite near zero."""
    import pandas as pd

    from momentum25.infrastructure.pipelines.relative_strength_pipeline import (
        RelativeStrengthPipeline,
    )

    prices = pd.Series([100.0] * 280)
    composite = RelativeStrengthPipeline._ibd_composite(prices)
    assert abs(composite) < 1e-9, f"Expected ~0, got {composite}"
