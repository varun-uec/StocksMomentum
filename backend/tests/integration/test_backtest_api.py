"""Contract tests for the walk-forward backtest route.

The runner itself is covered by ``tests/unit/test_walk_forward.py``. What this
file pins is the transport contract: the DTO shape, the benchmark label
travelling next to the benchmark number, and the survivorship caveat always
being in the response. A stub runner stands in for the database so the
contract is testable without Postgres.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from momentum25.application.dto.walk_forward import SIMULATION_NOTICE
from momentum25.application.use_cases.walk_forward import (
    NonTradingHolding,
    RebalanceRecord,
    TradeRecord,
    WalkForwardResult,
)
from momentum25.domain.backtest.execution import ExecutionPolicy
from momentum25.domain.value_objects.manifest import DataManifest
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SURVIVORSHIP_ELIGIBILITY_WARNING,
)
from momentum25.interface.api.routers.backtest import get_walk_forward_runner_factory
from momentum25.main import create_app

_TRADE = TradeRecord(
    security_id=7,
    side="BUY",
    quantity=Decimal("10"),
    fill_price=Decimal("100"),
    notional=Decimal("1000"),
    fill_date=date(2023, 3, 1),
    cost=Decimal("1.5"),
    order_date=date(2023, 3, 1),
    delay_sessions=0,
    partial=False,
    participation=Decimal("0.001"),
)

_RESULT = WalkForwardResult(
    rebalances=(
        RebalanceRecord(
            decision_date=date(2023, 2, 28),
            fill_date=date(2023, 3, 1),
            universe_size=500,
            eligible_count=420,
            scored_count=400,
            selected=(7,),
            trades=(_TRADE,),
            total_cost=Decimal("1.5"),
            nav_pre_cost=Decimal("1000000"),
            stale_marks=0,
            buy_scale=Decimal("1"),
        ),
    ),
    trades=(_TRADE,),
    initial_capital=Decimal("1000000"),
    final_nav=Decimal("1100000"),
    total_return=Decimal("0.1"),
    benchmark_return=Decimal("0.05"),
    benchmark_label="Nifty 500 Price Index (not TRI)",
    execution_policy=ExecutionPolicy().as_dict(),
    cagr=Decimal("0.07"),
    max_drawdown=Decimal("-0.12"),
    lower_bound_nav=Decimal("1050000"),
    nontrading_holdings=(
        NonTradingHolding(
            security_id=9,
            last_bar_date=date(2023, 6, 1),
            sessions_without_bar=40,
            value=Decimal("50000"),
            weight=Decimal("0.0455"),
            identity_status="no verified identity link",
        ),
    ),
)

_MANIFEST = DataManifest(
    revision=133621,
    indicator_version=2,
    rule_registry_version="41cc5e4529c8",
    calendar_version="exchange_calendars 4.13.2 XBOM",
    build_id="img-1",
    engine_version=1,
    reference_universe_version=1,
)


class _StubRunner:
    """Returns a fixed result, ignoring inputs. Stands in for the DB-backed runner."""

    def run(self, start: date, end: date, initial_capital: Decimal) -> WalkForwardResult:
        return _RESULT


def _client() -> TestClient:
    app = create_app()

    async def _factory(start: date, end: date) -> tuple[_StubRunner, DataManifest]:
        return _StubRunner(), _MANIFEST

    app.dependency_overrides[get_walk_forward_runner_factory] = lambda: _factory
    return TestClient(app)


def test_walk_forward_route_returns_full_dto() -> None:
    response = _client().post(
        "/api/v1/backtest/walk-forward",
        json={"start": "2023-03-01", "end": "2023-08-31", "initial_capital": "1000000"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_nav"] == "1100000"
    assert body["total_return"] == "0.1"
    assert body["rebalance_count"] == 1
    assert body["trade_count"] == 1
    assert body["rebalances"][0]["selected"] == [7]
    assert body["rebalances"][0]["nav_pre_cost"] == "1000000"
    assert body["trades"][0]["side"] == "BUY"


def test_response_names_its_method_data_and_lower_bound() -> None:
    body = _client().post(
        "/api/v1/backtest/walk-forward",
        json={"start": "2023-03-01", "end": "2023-08-31"},
    ).json()
    provenance = body["provenance"]
    assert provenance["method_version"] == 2
    assert provenance["execution_policy"]["participation_cap"] == "0.10"
    assert provenance["market_data_version"] == _MANIFEST.market_data_version
    assert provenance["data_revision"] == 133621 and provenance["build_id"] == "img-1"
    assert body["lower_bound_return"] == "0.05"
    assert body["nontrading_holdings"][0]["identity_status"] == "no verified identity link"
    assert body["simulation_notice"] == SIMULATION_NOTICE


def test_benchmark_number_never_travels_without_its_label() -> None:
    body = _client().post(
        "/api/v1/backtest/walk-forward",
        json={"start": "2023-03-01", "end": "2023-08-31"},
    ).json()
    assert body["benchmark_return"] == "0.05"
    assert body["benchmark_label"] == "Nifty 500 Price Index (not TRI)"


def test_response_carries_the_survivorship_warning() -> None:
    body = _client().post(
        "/api/v1/backtest/walk-forward",
        json={"start": "2023-03-01", "end": "2023-08-31"},
    ).json()
    assert body["survivorship_warning"] == SURVIVORSHIP_ELIGIBILITY_WARNING


def test_reversed_date_range_is_rejected() -> None:
    response = _client().post(
        "/api/v1/backtest/walk-forward",
        json={"start": "2023-08-31", "end": "2023-03-01"},
    )
    assert response.status_code == 422
