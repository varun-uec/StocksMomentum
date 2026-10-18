"""Rule parameter schemas (ADR-014 §2, M14).

The registry must match the engines exactly: every parameter a rule reads is
declared with the engine's own default, and nothing else is declared. Strategy
files are checked against it when loaded; stored strategies are not.
"""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from momentum25.domain.entities.strategy import EngineConfig, RuleConfig, StrategyConfig
from momentum25.domain.errors import ValidationError
from momentum25.domain.strategy.rule_schemas import RULES, validate_config
from momentum25.infrastructure.config.strategy_loader import load_strategy_file

_ENGINES = Path(__file__).resolve().parents[2] / "src" / "momentum25" / "domain" / "engines"
_STRATEGIES = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "strategies"

_PARAM = re.compile(r'_(int_)?param\(rc, "(\w+)", (?:Decimal\("([^"]+)"\)|(\w+))\)')


def _engine_reads() -> dict[str, dict[str, Decimal]]:
    """Every ``_param``/``_int_param`` call inside an ``_eval_*`` method, by rule id."""
    reads: dict[str, dict[str, Decimal]] = {}
    for path in sorted(_ENGINES.glob("*.py")):
        module = importlib.import_module(f"momentum25.domain.engines.{path.stem}")
        for block in re.split(r"\n    def ", path.read_text())[1:]:
            if not block.startswith("_eval_"):
                continue
            rule = re.search(r'rule_id = "(\w+)"', block)
            for match in _PARAM.finditer(block):
                assert rule, f"{path.name}: a parameter read outside a rule: {match.group(0)}"
                _, name, literal, constant = match.groups()
                if literal or constant.isdigit():
                    default = Decimal(literal or constant)
                else:
                    default = Decimal(str(getattr(module, constant)))
                reads.setdefault(rule.group(1), {})[name] = default
    return reads


def test_every_parameter_an_engine_reads_is_declared_with_its_default() -> None:
    reads = _engine_reads()
    declared = {
        rule_id: {p.name: p.default for p in schema.params}
        for rule_id, schema in RULES.items()
        if schema.params
    }
    assert reads == declared


def test_every_rule_an_engine_evaluates_is_registered() -> None:
    evaluated: set[str] = set()
    for path in _ENGINES.glob("*.py"):
        evaluated |= set(re.findall(r'"(\w+)": lambda rc', path.read_text()))
    assert evaluated == set(RULES)


@pytest.mark.parametrize("path", sorted(_STRATEGIES.glob("*.json")), ids=lambda p: p.stem)
def test_every_strategy_file_is_valid(path: Path) -> None:
    assert validate_config(load_strategy_file(path).config) == []


def _production() -> StrategyConfig:
    return load_strategy_file(_STRATEGIES / "minervini_trend_template.json").config


def _with_rule(config: StrategyConfig, rule_id: str, **changes: Any) -> StrategyConfig:
    engines = tuple(
        replace(e, rules=tuple(replace(r, **changes) if r.id == rule_id else r for r in e.rules))
        for e in config.engines
    )
    return replace(config, engines=engines)


@pytest.mark.parametrize(
    ("rule_id", "params", "error"),
    [
        ("tt_rs_rating_min", {"min": 0}, "tt_rs_rating_min.min: 0 is outside 1..99"),
        ("tt_rs_rating_min", {"min": "seventy"}, "is not a number"),
        ("tt_rs_rating_min", {"min": True}, "is not a number"),
        ("vol_accumulation_days", {"lookback": 25.5}, "is not a whole number"),
        ("risk_extension", {"ma": 100, "max_pct": 25}, "is not one of 50, 150, 200"),
        ("rs_rating", {"norm_min": 90, "norm_max": 80}, "norm_min must be below norm_max"),
        ("mq_trend_persistence", {"ma": 200, "lookback": 63}, "must fit the 252-session"),
        ("tt_near_52w_high", {"max_pct": 25, "extra": 1}, "unknown parameter extra"),
        ("tt_near_52w_high", {"max_pct": "NaN"}, "is not a number"),
    ],
)
def test_out_of_bounds_values_are_rejected_not_clamped(
    rule_id: str, params: dict[str, Any], error: str
) -> None:
    errors = validate_config(_with_rule(_production(), rule_id, params=params))
    assert len(errors) == 1 and error in errors[0], errors


def test_ids_weights_and_placement_are_checked() -> None:
    config = _production()
    assert validate_config(_with_rule(config, "tt_sma_stack", weight=Decimal("11"))) == [
        "tt_sma_stack: weight 11 is outside 0..10"
    ]
    assert validate_config(_with_rule(config, "tt_sma_stack", id="tt_made_up")) == [
        "unknown rule: tt_made_up"
    ]
    misplaced = replace(
        config,
        engines=(
            *config.engines,
            EngineConfig(
                id="risk",
                enabled=True,
                weight=Decimal("1"),
                rules=(RuleConfig(id="tt_sma_stack", weight=Decimal("1")),),
            ),
        ),
    )
    assert "tt_sma_stack: belongs to trend_template, not risk" in validate_config(misplaced)
    assert "tt_sma_stack: listed twice" in validate_config(misplaced)
    heavy = replace(config, momentum_weights={**config.momentum_weights, "risk": Decimal("-1")})
    assert validate_config(heavy) == ["momentum_weights.risk: weight -1 is outside 0..10"]


def test_a_strategy_file_that_breaks_a_schema_does_not_load(tmp_path: Path) -> None:
    raw = json.loads((_STRATEGIES / "minervini_trend_template.json").read_text())
    for engine in raw["engines"]:
        for rule in engine.get("rules", []):
            if rule["id"] == "tt_rs_rating_min":
                rule["params"]["min"] = 150
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValidationError, match=r"tt_rs_rating_min\.min: 150 is outside 1\.\.99"):
        load_strategy_file(path)
