"""The engine-effectiveness DTO must carry its measurability block.

Regression for a silent drop: the router passed ``measurability=`` to
``EngineEffectivenessResponse``, which had no such field, so Pydantic discarded
it. The validation screen then crashed reading ``measurability`` whenever any
engine row was present (found by the M10 end-to-end suite, 2026-10-18).
"""

from __future__ import annotations

from momentum25.domain.research.validation_models import (
    NO_FORWARD_RETURNS,
    EngineEffectivenessReport,
    Measurability,
)
from momentum25.interface.api.routers.validation import _engines_dto


def test_engine_report_keeps_unmeasurable_flag() -> None:
    report = EngineEffectivenessReport(
        strategy_name="s",
        strategy_id=1,
        total_runs_analyzed=3,
        engines=(),
        best_engine="",
        worst_engine="",
        recommended_exclusions=(),
        summary="no returns yet",
        measurability=Measurability(forward_returns_available=False, reason=NO_FORWARD_RETURNS),
    )
    payload = _engines_dto(report).model_dump()
    assert payload["measurability"] == {
        "forward_returns_available": False,
        "reason": NO_FORWARD_RETURNS,
    }
