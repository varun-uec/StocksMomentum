"""Strategy Studio use cases: the rule registry, families and user strategies (ADR-014 §2–4).

A family states a hypothesis and fixes its root. Every config saved into it
names its parent, which must be the root or a member, so a config cannot leave
its family. A user strategy changes only what the rule registry declares. Its
universe, indicators, ranking and benchmark are copied from its parent, and a
request that changes them is refused.
"""

from __future__ import annotations

from typing import Any

from momentum25.application.dto.studio import (
    CreateFamilyRequest,
    FamilyDTO,
    ParamSpecDTO,
    RuleRegistryDTO,
    RuleSchemaDTO,
    SaveStrategyRequest,
    StudioStrategyDTO,
)
from momentum25.domain.entities.strategy import Strategy, StrategyConfig, StrategyFamily
from momentum25.domain.errors import ConflictError, NotFoundError, ValidationError
from momentum25.domain.ports.repositories import StrategyRepository, StudioRepository
from momentum25.domain.ports.strategy_config import StrategyConfigChecker
from momentum25.domain.strategy.config_codec import compute_config_hash, raw_from_config
from momentum25.domain.strategy.rule_schemas import (
    ENGINE_IDS,
    ENGINES_WITHOUT_RULES,
    MAX_WEIGHT,
    RULES,
    registry_version,
)

# Not in the rule registry, so not configurable in Studio v1 (ADR-014 §1).
FIXED_SECTIONS = ("universe", "indicators", "ranking", "benchmark_index")
NAME_LENGTH = 80


def hypothesis_key(hypothesis: str) -> str:
    """The hypothesis with case and spacing removed: two families cannot share it."""
    return " ".join(hypothesis.split()).casefold()


def _strategy_dto(strategy: Strategy) -> StudioStrategyDTO:
    assert strategy.family_id is not None  # only user strategies reach the Studio
    return StudioStrategyDTO(
        config_hash=strategy.config_hash,
        name=strategy.name,
        version=strategy.version,
        family_id=strategy.family_id,
        parent_config_hash=strategy.parent_config_hash,
        config=raw_from_config(strategy.config),
    )


async def _family_dto(studio: StudioRepository, family: StrategyFamily) -> FamilyDTO:
    members = await studio.members(family.id)
    first = members[0] if members else None
    scratch = first is not None and first.config_hash == family.root_config_hash
    return FamilyDTO(
        id=family.id,
        hypothesis=family.hypothesis,
        root_config_hash=family.root_config_hash,
        root="scratch" if scratch else "builtin",
        created_at=family.created_at,
        members=[_strategy_dto(m) for m in members],
    )


def _user_strategy(
    config_hash: str, config: StrategyConfig, family_id: int | None, parent: str | None
) -> Strategy:
    return Strategy(
        name=config.name,
        version=config.version,
        config=config,
        config_hash=config_hash,
        kind="user",
        family_id=family_id,
        parent_config_hash=parent,
    )


class GetRuleRegistry:
    """Return the registry the Studio builds its form from."""

    def execute(self) -> RuleRegistryDTO:
        """Every engine, rule and parameter, in a stable order."""
        return RuleRegistryDTO(
            version=registry_version(),
            max_weight=MAX_WEIGHT,
            engines=sorted(ENGINE_IDS),
            engines_without_rules=sorted(ENGINES_WITHOUT_RULES),
            rules=[
                RuleSchemaDTO(
                    rule_id=s.rule_id,
                    engine_id=s.engine_id,
                    meaning=s.meaning,
                    note=s.note,
                    params=[
                        ParamSpecDTO(
                            name=p.name,
                            kind=p.kind,
                            unit=p.unit,
                            default=p.default,
                            meaning=p.meaning,
                            minimum=p.minimum,
                            maximum=p.maximum,
                            choices=list(p.choices),
                        )
                        for p in s.params
                    ],
                )
                for s in sorted(RULES.values(), key=lambda s: (s.engine_id, s.rule_id))
            ],
        )


class ListFamilies:
    """Return every family with its members."""

    def __init__(self, studio: StudioRepository) -> None:
        """Wire the use case with the Studio repository."""
        self._studio = studio

    async def execute(self) -> list[FamilyDTO]:
        """Families oldest first, members in save order."""
        return [await _family_dto(self._studio, f) for f in await self._studio.list_families()]


async def _build(
    studio: StudioRepository,
    raw: dict[str, Any],
    reference: StrategyConfig,
    family_id: int | None,
    checker: StrategyConfigChecker,
) -> tuple[str, StrategyConfig]:
    """Check the name, set the version and the fixed sections, enforce the schemas.

    Returns the config's hash and the config. ``family_id`` is None for a new family.
    """
    name = raw.get("name")
    if not isinstance(name, str) or not 0 < len(name.strip()) <= NAME_LENGTH:
        raise ValidationError(f"name: give a name of 1 to {NAME_LENGTH} characters")
    name = name.strip()
    holder = await studio.named(name)
    if holder is not None and holder.kind != "user":
        raise ConflictError(f"{name!r} is the name of a strategy file")
    if holder is not None and holder.family_id != family_id:
        raise ConflictError(f"{name!r} belongs to family {holder.family_id}")
    body = {**raw, "name": name, "version": await studio.next_version(name)}
    fixed = raw_from_config(reference)
    for section in FIXED_SECTIONS:
        if section in raw and raw[section] != fixed[section]:
            raise ValidationError(
                f"{section}: not configurable in Strategy Studio v1; omit it to keep "
                "the parent's value"
            )
        body[section] = fixed[section]
    config = checker(body)
    return compute_config_hash(config), config


class CreateFamily:
    """Start a family from a strategy file or from scratch."""

    def __init__(
        self,
        studio: StudioRepository,
        strategies: StrategyRepository,
        checker: StrategyConfigChecker,
    ) -> None:
        """Wire the use case with the Studio and strategy repositories and the config checker."""
        self._studio = studio
        self._strategies = strategies
        self._checker = checker

    async def _reference(self, parent_hash: str | None) -> Strategy:
        if parent_hash is None:
            production = [s for s in await self._strategies.list() if s.kind == "production"]
            if not production:
                raise NotFoundError("No production strategy to take the fixed sections from")
            return production[0]
        builtin = await self._studio.get_builtin(parent_hash)
        if builtin is not None:
            return builtin
        member = await self._studio.get_strategy(parent_hash)
        if member is not None:
            raise ValidationError(
                f"{parent_hash[:12]} belongs to family {member.family_id}. Save it there: "
                "a new family starts from a strategy file or from scratch"
            )
        raise NotFoundError(f"No strategy file has config hash {parent_hash[:12]}")

    async def execute(self, request: CreateFamilyRequest) -> FamilyDTO:
        """Record the hypothesis and root, then store the first member."""
        hypothesis = " ".join(request.hypothesis.split())
        reference = await self._reference(request.parent_config_hash)
        config_hash, config = await _build(
            self._studio, request.config, reference.config, None, self._checker
        )
        family = await self._studio.create_family(
            hypothesis,
            hypothesis_key(hypothesis),
            request.parent_config_hash or config_hash,
            _user_strategy(config_hash, config, None, request.parent_config_hash),
        )
        return await _family_dto(self._studio, family)


class SaveStrategy:
    """Save a new config into a family, derived from its root or a member."""

    def __init__(self, studio: StudioRepository, checker: StrategyConfigChecker) -> None:
        """Wire the use case with the Studio repository and the config checker."""
        self._studio = studio
        self._checker = checker

    async def execute(self, family_id: int, request: SaveStrategyRequest) -> StudioStrategyDTO:
        """Store the config as a new version; the family is the parent's."""
        family = await self._studio.get_family(family_id)
        if family is None:
            raise NotFoundError(f"No family {family_id}")
        parent_hash = request.parent_config_hash
        parent = await self._studio.get_strategy(parent_hash)
        if parent is None and parent_hash == family.root_config_hash:
            parent = await self._studio.get_builtin(parent_hash)
        if parent is None or (parent.kind == "user" and parent.family_id != family_id):
            raise ValidationError(
                f"{parent_hash[:12]} is not in family {family_id}: a config derives from "
                "its family's root or one of its members"
            )
        config_hash, config = await _build(
            self._studio, request.config, parent.config, family_id, self._checker
        )
        return _strategy_dto(
            await self._studio.add_strategy(
                _user_strategy(config_hash, config, family_id, parent_hash)
            )
        )
