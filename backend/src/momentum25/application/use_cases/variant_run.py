"""Variant-run handoff (ADR-014 section 12): a parameter variant runs inside a Studio family.

The generic experiment page changes a parent strategy's parameters. This use
case applies those overrides to the parent's stored config and saves the result
as a user strategy of its own, with its own ``config_hash``. The strategy joins
a family that states a hypothesis. Then it queues one Historical Research —
In-Sample run for that stored strategy. It never queues an Out-of-Sample
Evaluation, so the family's single hold-out (section 6) stays untouched.
"""

from __future__ import annotations

from typing import Any

from momentum25.application.dto.studio import (
    CreateFamilyRequest,
    FamilyRefDTO,
    ParentStrategyDTO,
    SaveStrategyRequest,
    SubmitEvaluationRequest,
    VariantOverrideDTO,
    VariantRunDTO,
    VariantRunRequest,
)
from momentum25.application.use_cases.strategy_evaluation import SubmitEvaluation
from momentum25.application.use_cases.studio import (
    CreateFamily,
    SaveStrategy,
    hypothesis_key,
    strategy_dto,
)
from momentum25.domain.entities.strategy import Strategy, StrategyFamily
from momentum25.domain.errors import ConflictError, NotFoundError, ValidationError
from momentum25.domain.ports.evaluation import EvaluationRepository
from momentum25.domain.ports.repositories import StudioRepository
from momentum25.domain.ports.strategy_config import StrategyConfigChecker
from momentum25.domain.research.services import (
    apply_parameter_overrides,
    coerce_override_value,
    override_from_path,
)
from momentum25.domain.research.strategy_evaluation import NOT_EVIDENCE
from momentum25.domain.strategy.config_codec import raw_from_config

_IDENTITY_KEYS = ("name", "version", "description")


def _behaviour(raw: dict[str, Any]) -> dict[str, Any]:
    """The config without its label: two configs with equal behaviour are the same variant."""
    return {k: v for k, v in raw.items() if k not in _IDENTITY_KEYS}


class StartVariantRun:
    """Save a variant in a family and queue its In-Sample run."""

    def __init__(
        self,
        studio: StudioRepository,
        evaluations: EvaluationRepository,
        create_family: CreateFamily,
        save_strategy: SaveStrategy,
        submit: SubmitEvaluation,
        checker: StrategyConfigChecker,
    ) -> None:
        """Wire the use case with the Studio use cases it composes."""
        self._studio = studio
        self._evaluations = evaluations
        self._create_family = create_family
        self._save_strategy = save_strategy
        self._submit = submit
        self._checker = checker

    async def execute(self, request: VariantRunRequest) -> VariantRunDTO:
        """Store the variant, join or start its family, and queue the run.

        Repeating a request returns the stored variant and run: neither counts twice.
        """
        self._check_hypothesis_source(request)
        parent = await self._parent(request.parent_config_hash)
        parent_raw = raw_from_config(parent.config)
        applied = apply_parameter_overrides(
            parent_raw,
            [
                override_from_path(o.parameter_path, coerce_override_value(o.value))
                for o in request.overrides
            ],
        )
        # The schema check rejects unknown or out-of-range values before any write. Its
        # canonical form makes two requests for the same variant compare equal.
        child = raw_from_config(
            self._checker({**applied, "name": request.variant_name, "version": 1})
        )
        if _behaviour(child) == _behaviour(parent_raw):
            raise ValidationError(
                "overrides: the variant would equal its parent. Name an existing "
                "engine, rule or parameter and a different value"
            )
        family, variant, reused_variant = await self._place(request, parent, child)
        evaluation, created = await self._submit.submit(
            family.id,
            SubmitEvaluationRequest(config_hash=variant.config_hash, result_class="in_sample"),
        )
        return VariantRunDTO(
            parent=ParentStrategyDTO(
                config_hash=parent.config_hash, name=parent.name, version=parent.version
            ),
            variant=strategy_dto(variant),
            family=FamilyRefDTO(
                id=family.id,
                hypothesis=family.hypothesis,
                root_config_hash=family.root_config_hash,
            ),
            overrides=[
                VariantOverrideDTO(
                    parameter_path=o.parameter_path, value=coerce_override_value(o.value)
                )
                for o in request.overrides
            ],
            evaluation=evaluation,
            research_runs=await self._evaluations.research_runs(family.id),
            reused_variant=reused_variant,
            reused_run=not created,
            notice=NOT_EVIDENCE,
        )

    @staticmethod
    def _check_hypothesis_source(request: VariantRunRequest) -> None:
        stated = request.hypothesis is not None
        joined = request.family_id is not None
        if stated == joined:
            raise ValidationError(
                "hypothesis: state a hypothesis for a new family, or give a family_id "
                "and confirm its hypothesis. Give one, not both"
            )
        if joined and not request.hypothesis_confirmed:
            raise ValidationError(
                "hypothesis_confirmed: confirm that the family's hypothesis covers this variant"
            )

    async def _parent(self, config_hash: str) -> Strategy:
        parent = await self._studio.get_builtin(config_hash) or await self._studio.get_strategy(
            config_hash
        )
        if parent is None:
            raise NotFoundError(f"No parent strategy has config hash {config_hash[:12]}")
        return parent

    async def _place(
        self, request: VariantRunRequest, parent: Strategy, child: dict[str, Any]
    ) -> tuple[StrategyFamily, Strategy, bool]:
        """The variant's family and stored strategy; the flag says it was already stored."""
        family = await self._family(request, parent)
        if family is None:
            assert request.hypothesis is not None  # checked: no family_id means a hypothesis
            created = await self._create_family.execute(
                CreateFamilyRequest(
                    hypothesis=request.hypothesis,
                    config=child,
                    parent_config_hash=parent.config_hash,
                )
            )
            stored = await self._studio.get_strategy(created.members[0].config_hash)
            family_row = await self._studio.get_family(created.id)
            assert stored is not None and family_row is not None
            return family_row, stored, False
        for member in await self._studio.members(family.id):
            if member.parent_config_hash == parent.config_hash and _behaviour(
                raw_from_config(member.config)
            ) == _behaviour(child):
                return family, member, True
        saved = await self._save_strategy.execute(
            family.id, SaveStrategyRequest(config=child, parent_config_hash=parent.config_hash)
        )
        stored = await self._studio.get_strategy(saved.config_hash)
        assert stored is not None
        return family, stored, False

    async def _family(self, request: VariantRunRequest, parent: Strategy) -> StrategyFamily | None:
        """The family to join, or ``None`` when the request starts a new one."""
        if request.family_id is not None:
            family = await self._studio.get_family(request.family_id)
            if family is None:
                raise NotFoundError(f"No family {request.family_id}")
            return family
        assert request.hypothesis is not None
        key = hypothesis_key(request.hypothesis)
        for family in await self._studio.list_families():
            if hypothesis_key(family.hypothesis) == key:
                if family.root_config_hash != parent.config_hash:
                    raise ConflictError(
                        f"Family {family.id} states this hypothesis on another root. "
                        "A hypothesis belongs to one family"
                    )
                return family
        return None
