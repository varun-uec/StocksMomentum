"""Portfolio ledger and analytics (Slice 6). Synthetic statements only; no real CAS."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from platform_common.database import Database
from wickstreet.context import TenantContext
from wickstreet.identity.application.principals import RegisterPrincipal
from wickstreet.identity.infrastructure.registry import SqlPrincipalRegistry
from wickstreet.mf_data.domain.reads import HoldingRow, Portfolio
from wickstreet.persistence.database import tenant_transaction
from wickstreet.portfolio.domain import analytics as a
from wickstreet.portfolio.domain.model import Closing, Statement, Transaction
from wickstreet.portfolio.infrastructure.cas import statement_of
from wickstreet.portfolio.infrastructure.store import SqlLedger


def _t(
    day: str, kind: str, amount: str | None, units: str | None, code: str = "100"
) -> Transaction:
    return Transaction(
        "F1",
        "Alpha MF",
        "Alpha Flexi Cap Fund - Direct Growth",
        "INF000000001",
        code,
        date.fromisoformat(day),
        kind,
        kind.lower(),
        Decimal(amount) if amount is not None else None,
        Decimal(units) if units is not None else None,
        None,
        None,
    )


def _fund(code: str = "100", nav: float = 12.0, **extra: object) -> a.FundView:
    base = {
        "code": code,
        "name": f"Fund {code}",
        "category": "Equity Scheme - Flexi Cap Fund",
        "asset_class": "Equity",
        "plan": "direct",
        "nav": nav,
        "nav_date": date(2026, 10, 22),
        "ter": 0.007,
    }
    return a.FundView(**(base | extra))  # type: ignore[arg-type]


def test_casparser_output_maps_to_a_statement_without_personal_details() -> None:
    data = {
        "statement_period": {"from": "01-Jan-2024", "to": "22-Oct-2026"},
        "cas_type": "DETAILED",
        "investor_info": {"name": "Someone", "email": "x@example.test", "address": "Somewhere"},
        "folios": [
            {
                "folio": "123/45",
                "amc": "Alpha MF",
                "PAN": "ABCDE1234F",
                "schemes": [
                    {
                        "scheme": "Alpha Flexi Cap Fund - Direct Growth",
                        "isin": "INF000000001",
                        "amfi": "100",
                        "close": "150.000",
                        "valuation": {
                            "date": "2026-10-22",
                            "nav": "12.0",
                            "value": "1800",
                            "cost": "1500",
                        },
                        "transactions": [
                            {
                                "date": "2024-01-01",
                                "description": "SIP",
                                "amount": "1000",
                                "units": "100",
                                "type": "PURCHASE_SIP",
                            },
                            {
                                "date": "2024-01-01",
                                "description": "Stamp",
                                "amount": "0.05",
                                "units": None,
                                "type": "STAMP_DUTY_TAX",
                            },
                        ],
                    }
                ],
            }
        ],
    }
    s = statement_of(data, "abc")
    assert (s.period_from, s.period_to, s.cas_type) == (
        date(2024, 1, 1),
        date(2026, 10, 22),
        "DETAILED",
    )
    assert [t.kind for t in s.transactions] == ["PURCHASE_SIP", "STAMP_DUTY_TAX"]
    assert s.closings[0].units == Decimal("150.000")
    assert "ABCDE1234F" not in repr(s) and "Someone" not in repr(s)


def test_cash_flows_follow_the_investor() -> None:
    assert a.flow_of(_t("2024-01-01", "PURCHASE", "1000", "100")) == -1000
    assert a.flow_of(_t("2024-01-01", "REDEMPTION", "-500", "-40")) == 500
    assert a.flow_of(_t("2024-01-01", "DIVIDEND_PAYOUT", "20", None)) == 20
    assert a.flow_of(_t("2024-01-01", "STAMP_DUTY_TAX", "0.05", None)) == -0.05
    assert a.flow_of(_t("2024-01-01", "DIVIDEND_REINVEST", "20", "2")) == 0


def test_a_lump_sum_xirr_is_the_annual_growth() -> None:
    held = a.positions(
        [_t("2025-10-22", "PURCHASE", "10000", "1000")],
        [],
        {"100": _fund(nav=11.0)},
        date(2026, 10, 22),
    )
    assert held[0].value == pytest.approx(11000)
    assert held[0].xirr == pytest.approx(0.10, abs=1e-4)  # within 1 bp


def _newton(flows: list[tuple[int, float]]) -> float:
    """An independent XIRR: Newton's method on the same convention (days / 365)."""
    first, rate = flows[0][0], 0.1
    for _ in range(100):
        f = sum(v / (1 + rate) ** ((d - first) / 365) for d, v in flows)
        df = sum(-(d - first) / 365 * v / (1 + rate) ** ((d - first) / 365 + 1) for d, v in flows)
        rate -= f / df
    return rate


def test_portfolio_xirr_matches_an_independent_solver() -> None:
    txns = [
        _t("2023-01-05", "PURCHASE_SIP", "5000", "500"),
        _t("2023-01-05", "STAMP_DUTY_TAX", "0.25", None),
        _t("2023-07-05", "PURCHASE_SIP", "5000", "450"),
        _t("2024-03-11", "REDEMPTION", "-3000", "-250"),
        _t("2024-06-01", "DIVIDEND_PAYOUT", "120", None),
        _t("2025-02-14", "PURCHASE", "20000", "1600", code="200"),
    ]
    funds = {"100": _fund(nav=13.2), "200": _fund("200", nav=14.1)}
    as_of = date(2026, 10, 22)
    held = a.positions(txns, [], funds, as_of)
    got = a.summary(held, funds, as_of)
    flows = sorted([(t.day.toordinal(), a.flow_of(t)) for t in txns if a.flow_of(t)])
    flows.append((as_of.toordinal(), 700 * 13.2 + 1600 * 14.1))
    assert got["value"] == pytest.approx(700 * 13.2 + 1600 * 14.1)
    assert got["xirr"] == pytest.approx(_newton(flows), abs=1e-4)
    assert got["invested"] == pytest.approx(30000.25)


def test_units_that_disagree_with_the_statement_are_reported() -> None:
    txns = [_t("2024-01-01", "PURCHASE", "1000", "100")]
    closing = Closing(
        "F1", "Alpha", "INF000000001", "100", Decimal("100.5"), None, None, None, None
    )
    held = a.positions(txns, [closing], {"100": _fund()}, date(2026, 10, 22))
    report = a.summary(held, {"100": _fund()}, date(2026, 10, 22))["reconciliation"]
    assert report["checked"] == 1 and report["matched"] == 0
    assert report["gaps"][0]["statement"] == "100.5"


def test_costs_show_what_a_direct_plan_would_save() -> None:
    funds = {"100": _fund(plan="regular", ter=0.018, direct_ter=0.008)}
    held = a.positions([_t("2024-01-01", "PURCHASE", "1000", "100")], [], funds, date(2026, 10, 22))
    costs = a.summary(held, funds, date(2026, 10, 22))["costs"]
    assert costs["annual_cost"] == pytest.approx(1200 * 0.018)
    assert costs["direct_switch_saving"] == pytest.approx(1200 * 0.010)
    assert costs["regular_plan_share"] == 1.0


def test_look_through_weights_holdings_by_value() -> None:
    p1 = Portfolio(
        date(2026, 9, 30),
        [HoldingRow("HDFC Bank", "INE040A01034", "Banks", "Equity", "equity", 0.10)],
    )
    p2 = Portfolio(
        date(2026, 9, 30),
        [HoldingRow("HDFC Bank", "INE040A01034", "Banks", "Equity", "equity", 0.05)],
    )
    funds = {"100": _fund(nav=10.0, holdings=p1), "200": _fund("200", nav=10.0, holdings=p2)}
    txns = [
        _t("2024-01-01", "PURCHASE", "750", "75"),
        _t("2024-01-01", "PURCHASE", "250", "25", code="200"),
    ]
    held = a.positions(txns, [], funds, date(2026, 10, 22))
    found = a.look_through(held, funds, {})
    assert found["coverage"] == pytest.approx(1.0)
    assert found["securities"][0]["weight"] == pytest.approx(0.75 * 0.10 + 0.25 * 0.05)


def test_rebalancing_trades_close_the_gap() -> None:
    trades = a.rebalance({"Equity": 0.8, "Debt": 0.2}, 100_000, {"Equity": 0.6, "Debt": 0.4})
    assert {t["asset_class"]: round(t["trade"]) for t in trades} == {
        "Debt": 20_000,
        "Equity": -20_000,
    }


async def test_the_ledger_skips_repeated_lines_and_undoes_one_import(
    app_database: Database,
) -> None:
    context = TenantContext(uuid4(), uuid4())
    first = Statement(
        "sha-1", None, None, "DETAILED", [_t("2024-01-01", "PURCHASE", "1000", "100")], [], []
    )
    overlapping = Statement(
        "sha-2",
        None,
        None,
        "DETAILED",
        [_t("2024-01-01", "PURCHASE", "1000", "100"), _t("2024-02-01", "PURCHASE", "1000", "95")],
        [],
        [],
    )
    async with tenant_transaction(app_database, context.tenant_id) as session:
        await RegisterPrincipal(SqlPrincipalRegistry(session)).execute(context)
        ledger = SqlLedger(session)
        one = await ledger.commit(context, first)
        two = await ledger.commit(context, overlapping)
        assert (one.added, two.added, two.duplicates) == (1, 1, 1)
        assert len(await ledger.transactions(context)) == 2
        assert await ledger.undo(context, two.id)
        assert len(await ledger.transactions(context)) == 1
        assert not await ledger.undo(context, two.id)
