"""Strategy Studio (FR-25, ADR-014 §2–4): the rule registry, families and lineage.

A family fixes its hypothesis and root. A config saved into it derives from
the root or a member, so it cannot leave the family. User strategies never
reach a live or research path.
"""

from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import ConflictError
from momentum25.domain.strategy.config_codec import raw_from_config
from momentum25.domain.strategy.rule_schemas import RULES, registry_version
from momentum25.infrastructure.config.strategy_loader import load_strategy_file
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.main import create_app

_FILE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)
_BUILTIN = load_strategy_file(_FILE)


def _config(name: str, rs_min: int = 80) -> dict[str, Any]:
    """The built-in config, renamed, with the RS rating floor set to ``rs_min``."""
    raw = copy.deepcopy(raw_from_config(_BUILTIN.config))
    raw["name"] = name
    for engine in raw["engines"]:
        for rule in engine["rules"]:
            if rule["id"] == "tt_rs_rating_min":
                rule["params"]["min"] = rs_min
    return raw


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    await SqlStrategyRepository(db_session).upsert(_BUILTIN)
    await db_session.commit()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


async def _family(
    client: httpx.AsyncClient,
    hypothesis: str = "A higher RS floor improves 120d returns of the qualified set.",
    name: str = "rs90",
    parent: str | None = _BUILTIN.config_hash,
    **changes: Any,
) -> httpx.Response:
    return await client.post(
        "/api/v1/studio/families",
        json={
            "hypothesis": hypothesis,
            "config": {**_config(name, 90), **changes},
            "parent_config_hash": parent,
        },
    )


async def test_the_registry_lists_every_rule_with_its_bounds(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/studio/rules")).json()
    assert body["version"] == registry_version()
    assert {r["rule_id"] for r in body["rules"]} == set(RULES)
    rs = next(r for r in body["rules"] if r["rule_id"] == "tt_rs_rating_min")
    assert rs["params"][0]["minimum"] is not None and rs["params"][0]["maximum"] is not None


async def test_a_family_records_its_hypothesis_root_and_first_member(
    client: httpx.AsyncClient,
) -> None:
    response = await _family(client, hypothesis="  A higher  RS floor improves returns.  ")
    assert response.status_code == 201, response.text
    family = response.json()
    assert family["hypothesis"] == "A higher RS floor improves returns."
    assert family["root"] == "builtin"
    assert family["root_config_hash"] == _BUILTIN.config_hash
    [member] = family["members"]
    assert (member["name"], member["version"]) == ("rs90", 1)
    assert member["parent_config_hash"] == _BUILTIN.config_hash
    # The fixed sections came from the parent.
    assert member["config"]["universe"] == raw_from_config(_BUILTIN.config)["universe"]

    listed = (await client.get("/api/v1/studio/families")).json()
    assert [f["id"] for f in listed] == [family["id"]]


async def test_user_strategies_never_reach_live_or_research_paths(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    assert (await _family(client)).status_code == 201
    names = {s["name"] for s in (await client.get("/api/v1/strategies")).json()}
    assert names == {_BUILTIN.name}
    assert (await client.get("/api/v1/strategies/rs90")).status_code == 404
    repo = SqlStrategyRepository(db_session)
    assert await repo.get_active("rs90") is None
    # The startup prune keeps them, and a strategy file cannot overwrite one.
    assert await repo.delete_orphans([_BUILTIN.name]) == []
    clash = Strategy(
        name="rs90", version=1, config=_BUILTIN.config, config_hash="x" * 64, kind="research"
    )
    with pytest.raises(ConflictError):
        await repo.upsert(clash)


async def test_an_out_of_range_parameter_is_refused_and_nothing_is_stored(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/studio/families",
        json={
            "hypothesis": "An impossible RS floor improves returns.",
            "config": _config("bad", 150),
            "parent_config_hash": _BUILTIN.config_hash,
        },
    )
    assert response.status_code == 422
    assert "tt_rs_rating_min.min" in response.json()["detail"]
    assert (await client.get("/api/v1/studio/families")).json() == []


async def test_a_malformed_config_is_a_422(client: httpx.AsyncClient) -> None:
    response = await _family(client, engines="not a list")
    assert response.status_code == 422
    assert "engines" in response.json()["detail"]


async def test_two_families_cannot_state_the_same_hypothesis(client: httpx.AsyncClient) -> None:
    assert (await _family(client)).status_code == 201
    again = await _family(
        client,
        hypothesis="a HIGHER rs floor improves 120d returns of the  qualified set.",
        name="rs90b",
    )
    assert again.status_code == 409


async def test_sections_outside_the_registry_cannot_change(client: httpx.AsyncClient) -> None:
    universe = {**raw_from_config(_BUILTIN.config)["universe"], "min_price_inr": 5}
    response = await _family(client, universe=universe)
    assert response.status_code == 422
    assert "universe" in response.json()["detail"]


async def test_a_name_is_held_by_one_family_and_never_by_a_file(
    client: httpx.AsyncClient,
) -> None:
    assert (await _family(client, name=_BUILTIN.name)).status_code == 409
    assert (await _family(client)).status_code == 201
    other = await _family(client, hypothesis="Another idea about the RS floor.", name="rs90")
    assert other.status_code == 409


async def test_lineage_keeps_a_config_in_its_family(client: httpx.AsyncClient) -> None:
    first = (await _family(client)).json()
    root = first["members"][0]
    save = f"/api/v1/studio/families/{first['id']}/strategies"

    child = await client.post(
        save, json={"config": _config("rs90", 85), "parent_config_hash": root["config_hash"]}
    )
    assert child.status_code == 201, child.text
    assert child.json()["version"] == 2
    assert child.json()["parent_config_hash"] == root["config_hash"]
    # The family's root (the strategy file) is also a valid parent.
    sibling = await client.post(
        save, json={"config": _config("rs95", 95), "parent_config_hash": _BUILTIN.config_hash}
    )
    assert sibling.status_code == 201

    # A member cannot found a new family: changing the hypothesis does not leave it.
    escape = await _family(
        client,
        hypothesis="A brand new idea, honestly.",
        name="rs99",
        parent=child.json()["config_hash"],
    )
    assert escape.status_code == 422

    second = (
        await _family(client, hypothesis="A scratch config of my own.", name="mine", parent=None)
    ).json()
    assert second["root"] == "scratch"
    assert second["root_config_hash"] == second["members"][0]["config_hash"]
    crossed = await client.post(
        f"/api/v1/studio/families/{second['id']}/strategies",
        json={"config": _config("mine", 70), "parent_config_hash": root["config_hash"]},
    )
    assert crossed.status_code == 422
    unknown = await client.post(
        "/api/v1/studio/families/999/strategies",
        json={"config": _config("x"), "parent_config_hash": root["config_hash"]},
    )
    assert unknown.status_code == 404


async def test_a_family_cannot_be_changed_after_creation(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    family_id = (await _family(client)).json()["id"]
    for statement in (
        f"UPDATE strategy_families SET hypothesis = 'x' WHERE id = {family_id}",
        f"DELETE FROM strategy_families WHERE id = {family_id}",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            await db_session.execute(text(statement))
        await db_session.rollback()
