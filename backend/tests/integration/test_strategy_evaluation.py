"""Strategy evaluation (ADR-014 §5–7, M14 exit tests).

- Determinism: the same config_hash and data_version give the same result,
  even after the data changes.
- Isolation: evaluations never write screening runs.
- Provenance: a period with reconstructed inputs carries its label.
- Families: a second Out-of-Sample Evaluation in a family is refused.

A small synthetic market and a small policy keep each evaluation fast. The
API test at the end uses the real policy.
"""

from __future__ import annotations

import copy
import math
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.dto.studio import CreateFamilyRequest, SubmitEvaluationRequest
from momentum25.application.use_cases.strategy_evaluation import (
    RetryEvaluation,
    RunEvaluation,
    SubmitEvaluation,
)
from momentum25.application.use_cases.studio import CreateFamily
from momentum25.domain.errors import ConflictError, ValidationError
from momentum25.domain.research.strategy_evaluation import (
    INCOMPLETE_PROVENANCE,
    LABELS,
    NOT_EVIDENCE,
    EvaluationPolicy,
)
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.infrastructure.config.strategy_loader import load_strategy_file, raw_from_config
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.evaluation_market import PointInTimeMarket
from momentum25.infrastructure.persistence.models import (
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    ScreeningRunModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlStrategyRepository,
    SqlStudioRepository,
)
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)
from momentum25.infrastructure.persistence.repositories.evaluations import (
    SqlEvaluationRepository,
)
from momentum25.main import create_app

_BUILTIN = load_strategy_file(
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)
DAYS = [
    date(2023, 1, 2) + timedelta(days=i)
    for i in range(730)
    if (date(2023, 1, 2) + timedelta(days=i)).weekday() < 5
]
# Three-month blocks from 2024; the latest matured one is 2024-07..09.
POLICY = EvaluationPolicy(
    horizon=10,
    step=10,
    holdout_months=3,
    anchor=date(2024, 1, 1),
    min_decisions=3,
    min_qualified=3,
)


class _Weekdays:
    def is_session(self, day: date) -> bool:
        return day.weekday() < 5

    def sessions_between(self, start: date, end: date) -> list[date]:
        return [d for d in DAYS if start <= d <= end]

    def next_session(self, after: date) -> date:
        return next(d for d in DAYS if d > after)


def _close(name: int, i: int) -> Decimal:
    """Twelve uptrends of different slopes, with a small wave so returns differ."""
    drift = 1 + 0.0004 * (name + 1)
    wave = 1 + 0.03 * math.sin(i / (5 + name))
    return Decimal(str(round(100 * drift**i * wave, 2)))


async def _market(session: AsyncSession) -> None:
    for name in range(12):
        security = SecurityModel(
            symbol=f"S{name:02d}",
            name=f"S{name:02d}",
            isin=f"INE{name:09d}",
            listing_date=DAYS[0],
        )
        session.add(security)
        await session.flush()
        for i, day in enumerate(DAYS):
            close = _close(name, i)
            session.add(
                OHLCVDailyModel(
                    security_id=security.id,
                    date=day,
                    open=close,
                    high=close * Decimal("1.01"),
                    low=close * Decimal("0.99"),
                    close=close,
                    volume=1_000_000,
                    turnover_value=close * 1_000_000,
                    adj_factor=Decimal(1),
                    adj_close=close,
                )
            )
    for i, day in enumerate(DAYS):
        session.add(
            BenchmarkIndexDailyModel(
                index_code="NIFTY500", date=day, close=Decimal(str(round(100 * 1.0003**i, 2)))
            )
        )
    await SqlStrategyRepository(session).upsert(_BUILTIN)
    await session.commit()


def _config(name: str) -> dict[str, Any]:
    raw = copy.deepcopy(raw_from_config(_BUILTIN.config))
    raw["name"] = name
    for engine in raw["engines"]:
        for rule in engine["rules"]:
            if rule["id"] == "tt_rs_rating_min":
                rule["params"]["min"] = 1  # twelve names: let the trend gates decide
    return raw


class _Studio:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.studio = SqlStudioRepository(session)
        self.evaluations = SqlEvaluationRepository(session)
        self.manifests = SqlDataManifestRepository(session)

    def market_at(self, revision: int) -> PointInTimeMarket:
        return PointInTimeMarket(self.session, revision, _Weekdays(), POLICY.horizon)

    async def family(self, name: str, hypothesis: str) -> tuple[int, str]:
        family = await CreateFamily(self.studio, SqlStrategyRepository(self.session)).execute(
            CreateFamilyRequest(
                hypothesis=hypothesis,
                config=_config(name),
                parent_config_hash=_BUILTIN.config_hash,
            )
        )
        return family.id, family.members[0].config_hash

    async def run(self, family_id: int, config_hash: str, result_class: Any) -> dict[str, Any]:
        parts = (self.studio, self.evaluations, self.manifests, self.market_at, POLICY)
        queued = await SubmitEvaluation(*parts).execute(
            family_id, SubmitEvaluationRequest(config_hash=config_hash, result_class=result_class)
        )
        await RunEvaluation(*parts).execute(queued.id)
        done = await self.evaluations.get(queued.id)
        assert done is not None and done.status == "completed", done and done.error
        assert done.result is not None
        return {"id": done.id, "data_version": done.data_version, **done.result}


@pytest.fixture
async def studio(db_session: AsyncSession) -> _Studio:
    register_builtin_engines()
    await _market(db_session)
    return _Studio(db_session)


async def test_in_sample_research_is_labelled_and_never_writes_screening_runs(
    studio: _Studio,
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    result = await studio.run(family_id, config_hash, "in_sample")
    assert result["label"] == LABELS["in_sample"] == "Historical Research — In-Sample"
    assert result["notice"] == NOT_EVIDENCE
    assert result["research_runs"] == 1
    assert result["window"]["end"] < "2024-07-01"  # the gap keeps it out of the hold-out
    assert result["decisions"] >= POLICY.min_decisions
    assert any(o["qualified"] for o in result["outcomes"])
    assert result["metrics"]["top_n_excess"]["available"]
    assert "regime" in result and "NIFTY500 returned" in result["regime"]["text"]
    assert result["provenance"]["label"] is None
    runs = await studio.session.scalar(select(func.count()).select_from(ScreeningRunModel))
    assert runs == 0


async def test_same_config_and_data_version_give_the_same_result(studio: _Studio) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    first = await studio.run(family_id, config_hash, "in_sample")

    # A later correction to every bar must not reach an evaluation at the old manifest.
    await studio.session.execute(update(OHLCVDailyModel).values(close=OHLCVDailyModel.close * 2))
    await studio.session.commit()
    replay = await studio.evaluations.create(
        family_id,
        config_hash,
        "in_sample",
        (date.fromisoformat(first["window"]["start"]), date.fromisoformat(first["window"]["end"])),
        first["data_version"],
    )
    await RunEvaluation(
        studio.studio, studio.evaluations, studio.manifests, studio.market_at, POLICY
    ).execute(replay.id)
    again = await studio.evaluations.get(replay.id)
    assert again is not None and again.result is not None
    assert again.data_version == first["data_version"]
    for key in ("outcomes", "metrics", "regime", "provenance", "window"):
        assert again.result[key] == first[key], key


async def test_reconstructed_inputs_label_their_months(studio: _Studio) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    await studio.session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.date == date(2024, 3, 4))
        .values(provenance="reconstructed", volume=999)
    )
    await studio.session.commit()
    result = await studio.run(family_id, config_hash, "in_sample")
    assert result["provenance"] == {
        "incomplete_months": ["2024-03"],
        "label": INCOMPLETE_PROVENANCE,
    }


async def test_one_out_of_sample_evaluation_per_family_and_families_are_counted(
    studio: _Studio,
) -> None:
    first_id, first_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    result = await studio.run(first_id, first_hash, "out_of_sample")
    assert result["label"] == "Out-of-Sample Evaluation"
    assert result["window"] == {"start": "2024-07-01", "end": "2024-09-30"}
    assert result["families_on_window"] == 1
    assert "validated" not in str(result).lower()

    with pytest.raises(ConflictError):  # even for another member of the family
        await studio.run(first_id, first_hash, "out_of_sample")

    second_id, second_hash = await studio.family("rs1b", "A different idea about the floor.")
    second = await studio.run(second_id, second_hash, "out_of_sample")
    assert second["families_on_window"] == 2
    one, two = result["metrics"]["top_n_excess"], second["metrics"]["top_n_excess"]
    assert one["available"] and two["available"]
    assert two["p_adjusted"] == pytest.approx(min(1.0, two["p"] * 2))
    assert one["p_adjusted"] == pytest.approx(one["p"])

    # A completed evaluation is final, and a hold-out evaluation is never deleted.
    for statement in (
        f"UPDATE strategy_evaluations SET status = 'failed' WHERE id = {result['id']}",
        f"DELETE FROM strategy_evaluations WHERE id = {result['id']}",
    ):
        with pytest.raises(DBAPIError, match="strategy_evaluations"):
            await studio.session.execute(text(statement))
        await studio.session.rollback()


async def test_no_matured_holdout_means_unavailable_and_nothing_is_spent(
    studio: _Studio,
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    late = replace(POLICY, anchor=date(2030, 1, 1))
    with pytest.raises(ValidationError, match="unavailable: insufficient data"):
        await SubmitEvaluation(
            studio.studio, studio.evaluations, studio.manifests, studio.market_at, late
        ).execute(
            family_id,
            SubmitEvaluationRequest(config_hash=config_hash, result_class="out_of_sample"),
        )
    assert await studio.evaluations.list_for_family(family_id) == []


async def test_a_screening_result_shows_the_selection_and_no_performance(
    studio: _Studio,
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    result = await studio.run(family_id, config_hash, "screening")
    assert result["label"] == "Screening Result"
    assert result["session"] == DAYS[-1].isoformat()
    assert result["selection"] and result["selection"][0]["rank"] == 1
    assert result["selection"][0]["rules"]
    assert not {"metrics", "outcomes", "regime"} & set(result)


async def test_a_restart_fails_unfinished_evaluations_and_retry_requeues(
    studio: _Studio,
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    manifest = await studio.manifests.capture()
    queued = await studio.evaluations.create(
        family_id, config_hash, "screening", (DAYS[-1], DAYS[-1]), manifest.data_version
    )
    assert await studio.evaluations.interrupt_unfinished() == 1
    failed = await studio.evaluations.get(queued.id)
    assert failed is not None and failed.status == "failed" and "restart" in (failed.error or "")
    assert await studio.evaluations.requeue(queued.id)
    assert not await studio.evaluations.requeue(queued.id)  # only a failed one


async def test_interrupted_holdout_keeps_its_slot_and_retries_on_the_sealed_snapshot(
    studio: _Studio,
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    parts = (studio.studio, studio.evaluations, studio.manifests, studio.market_at, POLICY)
    queued = await SubmitEvaluation(*parts).execute(
        family_id, SubmitEvaluationRequest(config_hash=config_hash, result_class="out_of_sample")
    )
    original_version = queued.data_version

    assert await studio.evaluations.interrupt_unfinished() == 1
    failed = await studio.evaluations.get(queued.id)
    assert failed is not None and failed.status == "failed"
    assert "restart" in (failed.error or "")

    # A failed job still reserves the family's one hold-out slot. Recovery must
    # retry that immutable evaluation instead of creating a fresh opportunity.
    with pytest.raises(ConflictError, match="one Out-of-Sample Evaluation per family"):
        await SubmitEvaluation(*parts).execute(
            family_id,
            SubmitEvaluationRequest(config_hash=config_hash, result_class="out_of_sample"),
        )

    retried = await RetryEvaluation(studio.evaluations).execute(queued.id)
    assert retried.status == "queued"
    await RunEvaluation(*parts).execute(queued.id)
    completed = await studio.evaluations.get(queued.id)
    assert completed is not None and completed.status == "completed"
    assert completed.data_version == original_version
    assert completed.result is not None
    assert completed.result["notice"].startswith("One evaluation is not validation.")


@pytest.fixture
async def client(studio: _Studio) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
    await get_database().engine.dispose()


async def test_the_api_queues_runs_and_reports_an_evaluation(
    client: httpx.AsyncClient, studio: _Studio
) -> None:
    family_id, config_hash = await studio.family("rs1", "A low RS floor keeps the winners.")
    url = f"/api/v1/studio/families/{family_id}/evaluations"
    queued = await client.post(url, json={"config_hash": config_hash, "result_class": "screening"})
    assert queued.status_code == 202, queued.text
    assert queued.json()["label"] == "Screening Result"
    # The background task ran before the transport returned.
    done = (await client.get(f"/api/v1/studio/evaluations/{queued.json()['id']}")).json()
    assert done["status"] == "completed" and done["result"]["selection"]
    assert [e["id"] for e in (await client.get(url)).json()] == [done["id"]]
    stranger = await client.post(
        url, json={"config_hash": _BUILTIN.config_hash, "result_class": "screening"}
    )
    assert stranger.status_code == 422
    # The real 36-month policy finds no matured hold-out in two years of data.
    oos = await client.post(url, json={"config_hash": config_hash, "result_class": "out_of_sample"})
    assert oos.status_code == 422 and "insufficient data" in oos.json()["detail"]
