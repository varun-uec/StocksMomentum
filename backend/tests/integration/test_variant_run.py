"""Variant-run handoff (ADR-014 section 12, R3-R2-09).

- An override produces a stored child strategy with a new ``config_hash``.
- The In-Sample run pins that hash, and the report states the variant.
- The run never reads the hold-out and never spends it.
- A repeated request or a retry does not count a second research run.
- A variant needs a stated hypothesis, or a confirmed family.

Reuses the small synthetic market and policy of ``test_strategy_evaluation``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_strategy_evaluation import _BUILTIN, DAYS, POLICY, _market, _Studio

from momentum25.application.dto.studio import VariantOverrideDTO, VariantRunRequest
from momentum25.application.use_cases.strategy_evaluation import RunEvaluation, SubmitEvaluation
from momentum25.application.use_cases.studio import CreateFamily, SaveStrategy
from momentum25.application.use_cases.variant_run import StartVariantRun
from momentum25.domain.errors import ConflictError, ValidationError
from momentum25.domain.research.strategy_evaluation import LABELS, NOT_EVIDENCE, holdout_window
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.infrastructure.config.strategy_loader import checked_config
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import (
    ScreeningRunModel,
    StrategyEvaluationModel,
    StrategyModel,
)
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.main import create_app

HYPOTHESIS = "A lower RS floor keeps more winners in the qualified set."
RS_FLOOR = "trend_template.tt_rs_rating_min.params.min"


@pytest.fixture
async def studio(db_session: AsyncSession) -> _Studio:
    register_builtin_engines()
    await _market(db_session)
    return _Studio(db_session)


def _request(**changes: Any) -> VariantRunRequest:
    body: dict[str, Any] = {
        "parent_config_hash": _BUILTIN.config_hash,
        "variant_name": "rs_floor_1",
        "overrides": [VariantOverrideDTO(parameter_path=RS_FLOOR, value="1")],
        "hypothesis": HYPOTHESIS,
    }
    return VariantRunRequest(**{**body, **changes})


def _use_case(studio: _Studio) -> StartVariantRun:
    strategies = SqlStrategyRepository(studio.session)
    parts = (studio.studio, studio.evaluations, studio.manifests, studio.market_at, POLICY)
    return StartVariantRun(
        studio.studio,
        studio.evaluations,
        CreateFamily(studio.studio, strategies, checked_config),
        SaveStrategy(studio.studio, checked_config),
        SubmitEvaluation(*parts),
        checked_config,
    )


async def _complete(studio: _Studio, evaluation_id: int, market: Any = None) -> dict[str, Any]:
    parts = (
        studio.studio,
        studio.evaluations,
        studio.manifests,
        market or studio.market_at,
        POLICY,
    )
    await RunEvaluation(*parts).execute(evaluation_id)
    done = await studio.evaluations.get(evaluation_id)
    assert done is not None and done.status == "completed", done and done.error
    assert done.result is not None
    result: dict[str, Any] = done.result
    return result


async def test_an_override_stores_a_child_strategy_with_a_new_hash(studio: _Studio) -> None:
    run = await _use_case(studio).execute(_request())

    assert run.parent.config_hash == _BUILTIN.config_hash
    assert run.variant.config_hash != run.parent.config_hash
    assert run.variant.parent_config_hash == _BUILTIN.config_hash
    assert run.variant.name == "rs_floor_1"
    assert run.family.hypothesis == HYPOTHESIS
    assert run.family.root_config_hash == _BUILTIN.config_hash
    assert not run.reused_variant and not run.reused_run

    stored = await studio.studio.get_strategy(run.variant.config_hash)
    assert stored is not None and stored.kind == "user" and stored.family_id == run.family.id
    rules = {r.id: r for e in stored.config.engines for r in e.rules}
    parent_rules = {r.id: r for e in _BUILTIN.config.engines for r in e.rules}
    assert rules["tt_rs_rating_min"].params["min"] == 1
    assert parent_rules["tt_rs_rating_min"].params["min"] == 70  # the parent is untouched
    assert await studio.studio.get_strategy(_BUILTIN.config_hash) is None  # still a strategy file


async def test_the_run_pins_the_variant_and_the_report_states_it(studio: _Studio) -> None:
    run = await _use_case(studio).execute(_request())

    assert run.evaluation.result_class == "in_sample"
    assert run.evaluation.label == LABELS["in_sample"] == "Historical Research — In-Sample"
    assert run.evaluation.config_hash == run.variant.config_hash
    assert run.notice == NOT_EVIDENCE
    result = await _complete(studio, run.evaluation.id)
    assert result["strategy"] == {
        "name": "rs_floor_1",
        "version": run.variant.version,
        "config_hash": run.variant.config_hash,
        "parent_config_hash": _BUILTIN.config_hash,
    }
    assert result["strategy"]["config_hash"] != _BUILTIN.config_hash
    assert result["research_runs"] == 1
    # The variant changed what qualifies: the parent's 70 floor leaves no names in a
    # twelve-name market, the variant's floor of 1 does.
    assert any(o["qualified"] for o in result["outcomes"])
    assert await studio.session.scalar(select(func.count()).select_from(ScreeningRunModel)) == 0


class _Recording:
    """A market that records every date a run asks for."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.dates: set[date] = set()

    async def sessions(self) -> list[date]:
        return await self._inner.sessions()  # type: ignore[no-any-return]

    async def screen(self, strategy: Any, decision: date) -> Any:
        self.dates.add(decision)
        return await self._inner.screen(strategy, decision)

    async def forward_excess(
        self, security_ids: list[int], decision: date, exit_on: date, benchmark: str
    ) -> dict[int, float]:
        self.dates.update((decision, exit_on))
        return await self._inner.forward_excess(  # type: ignore[no-any-return]
            security_ids, decision, exit_on, benchmark
        )

    async def benchmark_path(self, code: str, start: date, end: date) -> Any:
        self.dates.update((start, end))
        return await self._inner.benchmark_path(code, start, end)

    async def incomplete_months(self, start: date, end: date) -> list[str]:
        self.dates.update((start, end))
        return await self._inner.incomplete_months(start, end)  # type: ignore[no-any-return]


async def test_the_run_never_reads_or_spends_the_holdout(studio: _Studio) -> None:
    run = await _use_case(studio).execute(_request())
    holdout = holdout_window(DAYS, POLICY)
    assert holdout is not None

    manifest = await studio.manifests.get(run.evaluation.data_version)
    assert manifest is not None
    recorder = _Recording(studio.market_at(manifest.revision))
    await _complete(studio, run.evaluation.id, lambda revision: recorder)

    assert recorder.dates, "the run read nothing"
    assert max(recorder.dates) < holdout[0]
    classes = await studio.session.scalars(select(StrategyEvaluationModel.result_class))
    assert set(classes) == {"in_sample"}


async def test_a_repeated_request_or_a_retry_counts_one_research_run(studio: _Studio) -> None:
    use_case = _use_case(studio)
    first = await use_case.execute(_request())
    again = await use_case.execute(_request())  # the same request, e.g. a double click
    assert again.variant.config_hash == first.variant.config_hash
    assert again.evaluation.id == first.evaluation.id
    assert again.reused_variant and again.reused_run
    assert again.research_runs == 1

    # A restart fails the run; a retry re-queues the same row.
    assert await studio.evaluations.interrupt_unfinished() == 1
    assert await studio.evaluations.requeue(first.evaluation.id)
    await _complete(studio, first.evaluation.id)
    joined = await use_case.execute(
        _request(hypothesis=None, family_id=first.family.id, hypothesis_confirmed=True)
    )
    assert joined.evaluation.id == first.evaluation.id and joined.research_runs == 1

    # A different variant is a different run.
    other = await use_case.execute(
        _request(
            variant_name="rs_floor_2",
            overrides=[VariantOverrideDTO(parameter_path=RS_FLOOR, value=2)],
            hypothesis=None,
            family_id=first.family.id,
            hypothesis_confirmed=True,
        )
    )
    assert other.variant.config_hash != first.variant.config_hash
    assert other.research_runs == 2
    rows = await studio.session.scalar(select(func.count()).select_from(StrategyEvaluationModel))
    assert rows == 2


async def test_a_duplicate_row_from_a_race_still_counts_one_research_run(
    studio: _Studio,
) -> None:
    run = await _use_case(studio).execute(_request())
    window = (run.evaluation.window_start, run.evaluation.window_end)
    # Two requests that pass the lookup together would each insert a row. The count is
    # over run identities, so the second row is redundant and the budget stays at one.
    await studio.evaluations.create(
        run.family.id, run.variant.config_hash, "in_sample", window, run.evaluation.data_version
    )
    assert await studio.evaluations.research_runs(run.family.id) == 1


async def test_a_variant_needs_an_explicit_hypothesis(studio: _Studio) -> None:
    use_case = _use_case(studio)
    first = await use_case.execute(_request())
    second_changes: dict[str, Any] = {
        "variant_name": "rs_floor_3",
        "overrides": [VariantOverrideDTO(parameter_path=RS_FLOOR, value=3)],
    }

    with pytest.raises(ValidationError, match="Give one, not both"):
        await use_case.execute(_request(hypothesis=None))
    with pytest.raises(ValidationError, match="Give one, not both"):
        await use_case.execute(_request(**second_changes, family_id=first.family.id))
    with pytest.raises(ValidationError, match="hypothesis_confirmed"):
        await use_case.execute(
            _request(**second_changes, hypothesis=None, family_id=first.family.id)
        )
    joined = await use_case.execute(
        _request(
            **second_changes,
            hypothesis=None,
            family_id=first.family.id,
            hypothesis_confirmed=True,
        )
    )
    assert joined.family.id == first.family.id and joined.family.hypothesis == HYPOTHESIS
    assert joined.variant.parent_config_hash == _BUILTIN.config_hash

    # The same hypothesis text on another root is another family's idea: refused.
    stranger = await studio.studio.get_strategy(first.variant.config_hash)
    assert stranger is not None
    with pytest.raises(ConflictError, match="another root"):
        await use_case.execute(
            _request(
                **{
                    **second_changes,
                    "parent_config_hash": first.variant.config_hash,
                    "variant_name": "rs_floor_4",
                }
            )
        )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (RS_FLOOR, "70", "equal its parent"),  # no change
        ("trend_template.no_such_rule.params.min", "1", "no rule"),
        ("no_such_engine.weight", "1", "parameter_path"),
        ("trend_template", "1", "parameter_path"),
        (RS_FLOOR, "high", "number or true/false"),
        (RS_FLOOR, "500", "tt_rs_rating_min"),  # outside the declared bound
        ("trend_template.tt_rs_rating_min.params.nope", "1", "nope"),
    ],
)
async def test_a_bad_override_is_refused_and_writes_nothing(
    studio: _Studio, path: str, value: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        await _use_case(studio).execute(
            _request(overrides=[VariantOverrideDTO(parameter_path=path, value=value)])
        )
    assert await studio.studio.list_families() == []
    strategies = await studio.session.scalar(
        select(func.count()).select_from(StrategyModel).where(StrategyModel.kind == "user")
    )
    assert strategies == 0


@pytest.fixture
async def client(studio: _Studio) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await get_database().engine.dispose()


async def test_the_handoff_endpoint_queues_the_run_and_reports_the_variant(
    client: httpx.AsyncClient,
) -> None:
    body = {
        "parent_config_hash": _BUILTIN.config_hash,
        "variant_name": "rs_floor_api",
        "overrides": [{"parameter_path": RS_FLOOR, "value": "1"}],
        "hypothesis": HYPOTHESIS,
    }
    response = await client.post("/api/v1/studio/variants", json=body)
    assert response.status_code == 202, response.text
    run = response.json()
    assert run["variant"]["name"] == "rs_floor_api"
    assert run["variant"]["config_hash"] != run["parent"]["config_hash"] == _BUILTIN.config_hash
    assert run["family"]["hypothesis"] == HYPOTHESIS
    assert run["evaluation"]["label"] == "Historical Research — In-Sample"
    assert run["research_runs"] == 1 and not run["reused_run"]
    # The background task ran before the transport returned.
    done = (await client.get(f"/api/v1/studio/evaluations/{run['evaluation']['id']}")).json()
    assert done["status"] == "completed"
    assert done["config_hash"] == run["variant"]["config_hash"]
    assert done["result"]["strategy"]["config_hash"] == run["variant"]["config_hash"]

    again = (await client.post("/api/v1/studio/variants", json=body)).json()
    assert again["reused_run"] and again["evaluation"]["id"] == run["evaluation"]["id"]
    assert again["research_runs"] == 1

    refused = await client.post(
        "/api/v1/studio/variants", json={**body, "hypothesis": None, "variant_name": "x"}
    )
    assert refused.status_code == 422
    unknown = await client.post(
        "/api/v1/studio/variants", json={**body, "parent_config_hash": "0" * 64}
    )
    assert unknown.status_code == 404
