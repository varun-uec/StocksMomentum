"""Dotted override paths map to the structured form ``apply_parameter_overrides`` takes."""

from __future__ import annotations

import pytest

from momentum25.domain.errors import ValidationError
from momentum25.domain.research.services import (
    apply_parameter_overrides,
    coerce_override_value,
    override_from_path,
)


def test_each_path_form_maps_to_its_target() -> None:
    assert override_from_path("trend_template.weight", 2) == {
        "engine_id": "trend_template",
        "parameter_path": "weight",
        "new_value": 2,
    }
    assert override_from_path("trend_template.tt_rs_rating_min.params.min", 1) == {
        "engine_id": "trend_template",
        "rule_id": "tt_rs_rating_min",
        "parameter_path": "params.min",
        "new_value": 1,
    }
    assert override_from_path("scoring.momentum_weights.rs", 1)["parameter_path"] == (
        "scoring.momentum_weights.rs"
    )


@pytest.mark.parametrize(
    "path",
    ["", "trend_template", "x.weight", "trend_template.nope.weight", "scoring.x", "scoring.a.b.c"],
)
def test_other_paths_are_refused(path: str) -> None:
    with pytest.raises(ValidationError):
        override_from_path(path, 1)


def test_values_are_typed_and_the_input_is_not_mutated() -> None:
    assert coerce_override_value(" 7 ") == 7
    assert coerce_override_value("1.5") == 1.5
    assert coerce_override_value("True") is True
    assert coerce_override_value(3) == 3
    with pytest.raises(ValidationError):
        coerce_override_value("high")
    base = {"engines": [{"id": "e", "rules": [{"id": "r", "params": {"min": 70}}]}]}
    out = apply_parameter_overrides(
        base, [{"engine_id": "e", "rule_id": "r", "parameter_path": "params.min", "new_value": 1}]
    )
    assert out["engines"][0]["rules"][0]["params"]["min"] == 1
    assert base["engines"][0]["rules"][0]["params"]["min"] == 70
