"""Validation and research evidence is per config version (R3-U-07, ADR-014 §9)."""

from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import ScreeningRun
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.config.strategy_loader import load_strategy_file, raw_from_config
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import (
    RuleResultModel,
    ScreeningResultModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)
from momentum25.main import create_app

_STRATEGY_FILE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)
_BUILTIN = load_strategy_file(_STRATEGY_FILE)
HASHES: dict[int, str] = {}


def _config(rs_min: int) -> dict[str, Any]:
    raw = copy.deepcopy(raw_from_config(_BUILTIN.config))
    raw["name"] = "my_rs"
    for engine in raw["engines"]:
        for rule in engine["rules"]:
            if rule["id"] == "tt_rs_rating_min":
                rule["params"]["min"] = rs_min
    return raw


async def _seed(client: httpx.AsyncClient, session: AsyncSession) -> dict[int, str]:
    """One user strategy name, three Studio versions: v1 has 2 runs, v2 has 1, v3 none."""
    family = (
        await client.post(
            "/api/v1/studio/families",
            json={
                "hypothesis": "A higher RS floor improves 120d returns.",
                "config": _config(90),
                "parent_config_hash": _BUILTIN.config_hash,
            },
        )
    ).json()
    hashes = {1: family["members"][0]["config_hash"]}
    for version, rs_min in ((2, 85), (3, 95)):
        member = (
            await client.post(
                f"/api/v1/studio/families/{family['id']}/strategies",
                json={"config": _config(rs_min), "parent_config_hash": hashes[1]},
            )
        ).json()
        assert member["version"] == version
        hashes[version] = member["config_hash"]

    security = SecurityModel(symbol="AAA", name="AAA", isin="INE000000001")
    session.add(security)
    await session.flush()
    strategies = SqlStrategyRepository(session)
    runs = SqlScreeningRunRepository(session)
    for version, day in ((1, 1), (1, 2), (2, 3)):
        strategy = await strategies.get_for_workspace("my_rs", hashes[version])
        assert strategy is not None and strategy.id is not None
        run_id = await runs.create(
            ScreeningRun(
                strategy_id=strategy.id,
                run_date=date(2026, 10, day),
                data_version=f"dv{day}",
                config_hash=hashes[version],
                trigger=RunTrigger.MANUAL,
                status=RunStatus.COMPLETED,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
        )
        session.add(
            ScreeningResultModel(
                run_id=run_id,
                security_id=security.id,
                rank=1,
                momentum_score=Decimal("50"),
                buy_setup_score=Decimal("40"),
                hard_filters_passed=True,
            )
        )
        session.add(
            RuleResultModel(
                run_id=run_id,
                security_id=security.id,
                rule_id="rs_rating",
                engine_id="relative_strength",
                passed=True,
                raw_value=Decimal("80"),
                threshold=Decimal("70"),
                operator=">=",
                weight=Decimal("2"),
                contribution=Decimal("1"),
                explanation="x",
            )
        )
    await session.commit()
    return hashes


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    await SqlStrategyRepository(db_session).upsert(_BUILTIN)
    await db_session.commit()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        HASHES.clear()
        HASHES.update(await _seed(http, db_session))
        yield http
    await get_database().engine.dispose()


@pytest.mark.parametrize(
    ("path", "count"),
    [
        ("/api/v1/research/contribution/my_rs", lambda b: b["run_count"]),
        ("/api/v1/research/evaluate/my_rs", lambda b: b["performance"]["run_count"]),
        ("/api/v1/validation/rules/my_rs", lambda b: b["total_runs_analyzed"]),
        ("/api/v1/validation/engines/my_rs", lambda b: b["total_runs_analyzed"]),
    ],
)
async def test_each_version_sees_only_its_own_runs(
    client: httpx.AsyncClient, path: str, count: object
) -> None:
    v1 = (await client.get(path, params={"config_hash": HASHES[1]})).json()
    v2 = (await client.get(path, params={"config_hash": HASHES[2]})).json()

    assert (v1["strategy_version"], v1["config_hash"]) == (1, HASHES[1])
    assert (v2["strategy_version"], v2["config_hash"]) == (2, HASHES[2])
    assert count(v1) == 2  # type: ignore[operator]
    assert count(v2) == 1  # type: ignore[operator]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/validation/historical/my_rs",
        "/api/v1/validation/alpha/my_rs",
        "/api/v1/validation/scorecard/my_rs",
        "/api/v1/validation/rules/my_rs",
        "/api/v1/validation/engines/my_rs",
        "/api/v1/research/evaluate/my_rs",
        "/api/v1/research/contribution/my_rs",
    ],
)
async def test_a_version_without_runs_is_insufficient_data_not_an_error(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path, params={"config_hash": HASHES[3]})
    assert response.status_code == 200
    assert response.json()["config_hash"] == HASHES[3]


async def test_user_versions_need_a_config_hash_and_bad_hashes_are_rejected(
    client: httpx.AsyncClient,
) -> None:
    # Without config_hash the name resolves the strategy-file definition only.
    assert (await client.get("/api/v1/validation/rules/my_rs")).status_code == 404
    assert (
        await client.get("/api/v1/validation/rules/my_rs", params={"config_hash": "d" * 64})
    ).status_code == 404
    assert (
        await client.get("/api/v1/validation/rules/my_rs", params={"config_hash": "XYZ"})
    ).status_code == 422
