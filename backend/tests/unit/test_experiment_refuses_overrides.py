"""R3-R2-09: a variant with overrides must not run as the base strategy."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from momentum25.application.use_cases.research.experiment import ExperimentUseCase
from momentum25.application.use_cases.validation import ParameterResearchUseCase
from momentum25.domain.errors import ValidationError
from momentum25.domain.research.models import ExperimentConfig, ParameterOverride


class _Strategies:
    async def get_active(self, name: str) -> SimpleNamespace:
        return SimpleNamespace(id=1, name=name)


async def test_experiment_refuses_overrides() -> None:
    use_case = ExperimentUseCase(_Strategies(), None, None)
    config = ExperimentConfig(
        name="e",
        description="d",
        base_strategy_name="s",
        base_strategy_id=0,
        overrides=(ParameterOverride(parameter_path="x", new_value=1),),
        run_dates=(date(2025, 1, 1),),
    )
    with pytest.raises(ValidationError, match="not applied"):
        await use_case.run_experiment(config)


async def test_parameter_research_refuses_overrides() -> None:
    use_case = ParameterResearchUseCase(None, _Strategies(), None, None, None, None)
    with pytest.raises(ValidationError, match="not applied"):
        await use_case.execute("e", "s", [{"name": "v", "overrides": [{"parameter_path": "x"}]}])
