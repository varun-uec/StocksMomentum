"""Strategy Studio requests and responses (FR-25, ADR-014)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ParamSpecDTO(BaseModel):
    """One rule parameter: what it may be set to."""

    name: str
    kind: Literal["number", "integer", "choice"]
    unit: str
    default: Decimal
    meaning: str
    minimum: Decimal | None
    maximum: Decimal | None
    choices: list[Decimal]


class RuleSchemaDTO(BaseModel):
    """A registered rule, its engine and its parameters."""

    rule_id: str
    engine_id: str
    meaning: str
    note: str | None
    params: list[ParamSpecDTO]


class RuleRegistryDTO(BaseModel):
    """Every engine and rule a user strategy may configure (ADR-014 §2)."""

    version: str
    max_weight: Decimal
    engines: list[str]
    engines_without_rules: list[str]
    rules: list[RuleSchemaDTO]


class StudioStrategyDTO(BaseModel):
    """A saved user strategy and the config it came from."""

    config_hash: str
    name: str
    version: int
    family_id: int
    parent_config_hash: str | None
    config: dict[str, Any]


class FamilyDTO(BaseModel):
    """A family: its hypothesis, its root and its members in save order."""

    id: int
    hypothesis: str
    root_config_hash: str
    root: Literal["builtin", "scratch"]
    created_at: datetime
    members: list[StudioStrategyDTO]


class CreateFamilyRequest(BaseModel):
    """A new family: a hypothesis and its first config.

    ``parent_config_hash`` names the strategy file it starts from, or is null
    for a config written from scratch.
    """

    model_config = ConfigDict(extra="forbid")

    hypothesis: str = Field(min_length=10, max_length=300)
    config: dict[str, Any]
    parent_config_hash: str | None = None


class SaveStrategyRequest(BaseModel):
    """A new config in a family, derived from one of its members or its root."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any]
    parent_config_hash: str


class SubmitEvaluationRequest(BaseModel):
    """Evaluate one family member in one result class."""

    model_config = ConfigDict(extra="forbid")

    config_hash: str
    result_class: Literal["screening", "in_sample", "out_of_sample"]


class EvaluationDTO(BaseModel):
    """An evaluation, its progress and, once complete, its result."""

    id: int
    family_id: int
    config_hash: str
    result_class: Literal["screening", "in_sample", "out_of_sample"]
    label: str
    window_start: date
    window_end: date
    data_version: str
    status: Literal["queued", "running", "completed", "failed"]
    progress_done: int
    progress_total: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
