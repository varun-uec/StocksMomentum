"""Rule parameter schemas (ADR-014 §2): what each registered rule may be set to.

Every rule declares its parameters: type, unit, bounds, default and meaning.
``StrategyConfig`` validation enforces them, so an out-of-range value is
rejected at the boundary, never clamped. The Strategy Studio builds its form
from this registry. Defaults equal the engines' own fallbacks (a test checks
each one against the engine source), so declaring a schema changes no result.

Bounds are wide on purpose. They keep values meaningful (a percentile stays in
1..99, a window fits the 252-session history), not near today's settings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from momentum25.domain.entities.strategy import StrategyConfig

ParamKind = Literal["number", "integer", "choice"]

# Weights are relative within an engine or a score. Zero switches a rule's
# contribution off without removing it; 10 is far beyond any use so far.
MAX_WEIGHT = Decimal("10")
# The indicator pipeline keeps 252 sessions (one year) for every symbol.
HISTORY_SESSIONS = 252


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One parameter of a rule."""

    name: str
    kind: ParamKind
    unit: str
    default: Decimal
    meaning: str
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    choices: tuple[Decimal, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleSchema:
    """A registered rule: its engine, what it tests, and its parameters."""

    rule_id: str
    engine_id: str
    meaning: str
    params: tuple[ParamSpec, ...] = ()
    # A rule that needs data no free NSE source provides today.
    note: str | None = None
    # A check across parameters; returns an error, or None.
    check: Callable[[Mapping[str, Decimal]], str | None] | None = field(default=None, compare=False)


def _num(name: str, unit: str, default: str, lo: str, hi: str, meaning: str) -> ParamSpec:
    return ParamSpec(name, "number", unit, Decimal(default), meaning, Decimal(lo), Decimal(hi))


def _int(name: str, unit: str, default: int, lo: int, hi: int, meaning: str) -> ParamSpec:
    return ParamSpec(name, "integer", unit, Decimal(default), meaning, Decimal(lo), Decimal(hi))


def _norm_range(p: Mapping[str, Decimal]) -> str | None:
    return None if p["norm_min"] < p["norm_max"] else "norm_min must be below norm_max"


def _fits_history(p: Mapping[str, Decimal]) -> str | None:
    if p["ma"] + p["lookback"] <= HISTORY_SESSIONS:
        return None
    return f"ma + lookback must fit the {HISTORY_SESSIONS}-session history"


_SMA_WINDOWS = (Decimal(50), Decimal(150), Decimal(200))
_NO_SECTOR_DATA = (
    "Needs sector or industry data, which no free NSE source provides; it never passes today."
)

RULES: dict[str, RuleSchema] = {
    s.rule_id: s
    for s in (
        # ── Trend Template ──
        RuleSchema(
            "tt_close_above_sma150_200", "trend_template", "Close above the 150- and 200-day SMAs."
        ),
        RuleSchema(
            "tt_sma150_above_sma200", "trend_template", "150-day SMA above the 200-day SMA."
        ),
        RuleSchema(
            "tt_sma200_uptrend",
            "trend_template",
            "200-day SMA rising over the slope window.",
            (
                _num(
                    "min_slope_pct",
                    "% over the slope window",
                    "0",
                    "-5",
                    "5",
                    "Smallest rise that counts.",
                ),
            ),
        ),
        RuleSchema(
            "tt_sma_stack",
            "trend_template",
            "50-day SMA above the 150- and 200-day SMAs. Needs tt_sma150_above_sma200.",
        ),
        RuleSchema("tt_close_above_sma50", "trend_template", "Close above the 50-day SMA."),
        RuleSchema(
            "tt_above_52w_low",
            "trend_template",
            "Close far enough above the 52-week low.",
            (
                _num(
                    "min_pct",
                    "% above the low",
                    "30",
                    "0",
                    "500",
                    "Smallest distance above the low.",
                ),
            ),
        ),
        RuleSchema(
            "tt_near_52w_high",
            "trend_template",
            "Close near enough to the 52-week high.",
            (
                _num(
                    "max_pct",
                    "% below the high",
                    "25",
                    "0",
                    "100",
                    "Largest distance below the high.",
                ),
            ),
        ),
        RuleSchema(
            "tt_rs_rating_min",
            "trend_template",
            "RS rating at or above a floor.",
            (_num("min", "RS rating (1-99)", "70", "1", "99", "Lowest rating that passes."),),
        ),
        # ── Relative Strength ──
        RuleSchema(
            "rs_rating",
            "relative_strength",
            "RS rating, scored between a floor and a ceiling.",
            (
                _num("norm_min", "RS rating (1-99)", "70", "1", "98", "Rating that scores zero."),
                _num(
                    "norm_max", "RS rating (1-99)", "99", "2", "99", "Rating that scores in full."
                ),
            ),
            check=_norm_range,
        ),
        RuleSchema(
            "rs_line_uptrend",
            "relative_strength",
            "Price relative to the benchmark rising.",
            (
                _num(
                    "min_slope",
                    "slope of the RS line",
                    "0",
                    "-10",
                    "10",
                    "Smallest slope that counts.",
                ),
            ),
            note=(
                "Removed from the production strategy in v3: "
                "it never fired under the current computation."
            ),
        ),
        RuleSchema(
            "rs_sector_relative",
            "relative_strength",
            "RS percentile within the sector.",
            (_num("threshold", "percentile", "50", "1", "99", "Lowest percentile that passes."),),
            note=_NO_SECTOR_DATA,
        ),
        RuleSchema(
            "rs_industry_relative",
            "relative_strength",
            "RS percentile within the industry.",
            (_num("threshold", "percentile", "50", "1", "99", "Lowest percentile that passes."),),
            note=_NO_SECTOR_DATA,
        ),
        # ── Volume / Accumulation ──
        RuleSchema(
            "vol_liquidity_min",
            "volume_accumulation",
            "Average daily turnover at or above a floor.",
            (
                _num(
                    "min_turnover_inr",
                    "INR per day",
                    "10000000",
                    "0",
                    "100000000000",
                    "Lowest average turnover that passes.",
                ),
            ),
        ),
        RuleSchema(
            "vol_accumulation_days",
            "volume_accumulation",
            "More up-volume days than down-volume days.",
            (_int("lookback", "sessions", 25, 5, HISTORY_SESSIONS, "Sessions counted."),),
        ),
        RuleSchema(
            "vol_breakout_confirm",
            "volume_accumulation",
            "Latest volume high relative to its average.",
            (
                _num(
                    "min_rel_volume",
                    "x average volume",
                    "1.4",
                    "0.5",
                    "10",
                    "Lowest ratio that passes.",
                ),
            ),
        ),
        # ── Breakout ──
        RuleSchema("bo_pivot_breakout", "breakout", "Close through the recent pivot high."),
        RuleSchema("bo_followthrough", "breakout", "The breakout held in later sessions."),
        RuleSchema("bo_false_breakout", "breakout", "No failed breakout back below the pivot."),
        # ── Momentum Quality ──
        RuleSchema(
            "mq_trend_persistence",
            "momentum_quality",
            "Share of recent sessions closing above a moving average.",
            (
                _int("ma", "sessions", 50, 5, 200, "Moving-average window."),
                _int("lookback", "sessions", 63, 5, HISTORY_SESSIONS, "Sessions counted."),
            ),
            check=_fits_history,
        ),
        RuleSchema(
            "mq_acceleration", "momentum_quality", "Recent returns faster than earlier ones."
        ),
        # ── Risk ──
        RuleSchema(
            "risk_extension",
            "risk",
            "Close not too far above a moving average.",
            (
                ParamSpec(
                    "ma",
                    "choice",
                    "sessions",
                    Decimal(50),
                    "SMA window the pipeline computes.",
                    choices=_SMA_WINDOWS,
                ),
                _num(
                    "max_pct", "% above the SMA", "25", "0", "200", "Largest extension that passes."
                ),
            ),
        ),
        RuleSchema(
            "risk_atr",
            "risk",
            "Average daily range not too wide.",
            (_num("max_adr_pct", "% of price", "8", "0.5", "50", "Widest range that passes."),),
        ),
        RuleSchema(
            "risk_rr",
            "risk",
            "An ATR-based stop fits within a share of price.",
            (
                _num(
                    "max_risk_pct",
                    "% of price",
                    "16",
                    "1",
                    "50",
                    "Largest stop distance that passes.",
                ),
            ),
        ),
    )
}

# Engines whose rules are not configured: pattern rules come from detectors,
# and the fundamental engine is not implemented. They can be enabled and weighted.
ENGINES_WITHOUT_RULES = frozenset({"pattern", "fundamental"})
ENGINE_IDS = frozenset({s.engine_id for s in RULES.values()} | ENGINES_WITHOUT_RULES)


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _check_param(rule_id: str, spec: ParamSpec, raw: Any) -> tuple[Decimal | None, str | None]:
    value = _as_decimal(raw)
    where = f"{rule_id}.{spec.name}"
    if value is None:
        return None, f"{where}: {raw!r} is not a number"
    if spec.kind == "integer" and value != value.to_integral_value():
        return None, f"{where}: {raw!r} is not a whole number"
    if spec.kind == "choice":
        if value not in spec.choices:
            allowed = ", ".join(str(c) for c in spec.choices)
            return None, f"{where}: {raw!r} is not one of {allowed}"
        return value, None
    assert spec.minimum is not None and spec.maximum is not None
    if not spec.minimum <= value <= spec.maximum:
        return None, f"{where}: {raw!r} is outside {spec.minimum}..{spec.maximum} ({spec.unit})"
    return value, None


def _check_weight(where: str, weight: Decimal) -> str | None:
    if not Decimal(0) <= weight <= MAX_WEIGHT:
        return f"{where}: weight {weight} is outside 0..{MAX_WEIGHT}"
    return None


def validate_config(config: StrategyConfig) -> list[str]:
    """Return every way ``config`` breaks the registry; an empty list means valid.

    Checks engine and rule ids, each rule's engine, parameter names, types and
    bounds, cross-parameter checks, and every weight.
    """
    errors: list[str] = []
    seen_rules: set[str] = set()
    for engine in config.engines:
        if engine.id not in ENGINE_IDS:
            errors.append(f"unknown engine: {engine.id}")
            continue
        if error := _check_weight(engine.id, engine.weight):
            errors.append(error)
        if engine.id in ENGINES_WITHOUT_RULES and engine.rules:
            errors.append(f"{engine.id}: this engine has no configurable rules")
        for rule in engine.rules:
            schema = RULES.get(rule.id)
            if schema is None:
                errors.append(f"unknown rule: {rule.id}")
                continue
            if schema.engine_id != engine.id:
                errors.append(f"{rule.id}: belongs to {schema.engine_id}, not {engine.id}")
            if rule.id in seen_rules:
                errors.append(f"{rule.id}: listed twice")
            seen_rules.add(rule.id)
            if error := _check_weight(rule.id, rule.weight):
                errors.append(error)
            declared = {p.name: p for p in schema.params}
            for name in rule.params:
                if name not in declared:
                    errors.append(f"{rule.id}: unknown parameter {name}")
            values: dict[str, Decimal] = {}
            for spec in schema.params:
                value, error = (
                    _check_param(rule.id, spec, rule.params[spec.name])
                    if spec.name in rule.params
                    else (spec.default, None)
                )
                if error:
                    errors.append(error)
                elif value is not None:
                    values[spec.name] = value
            complete = len(values) == len(schema.params)
            if schema.check and complete and (error := schema.check(values)):
                errors.append(f"{rule.id}: {error}")
    for score in ("momentum_weights", "buy_setup_weights"):
        for engine_id, weight in getattr(config, score).items():
            if engine_id not in ENGINE_IDS:
                errors.append(f"{score}: unknown engine {engine_id}")
            elif error := _check_weight(f"{score}.{engine_id}", weight):
                errors.append(error)
    return errors
