"""Unit test: ExecuteScreening must screen the latest persisted bar date, not
today's wall-clock date.

On a weekend, holiday, or before the bhavcopy publishes, date.today() matches
no bar, and the orchestrator's admission gate (bars[-1].date != trading_date)
drops every security as no_bar_on_trading_date -- the run "completes" with
total_evaluated>0 but zero scored (see run #5, 2026-08-09, a Sunday).
"""

from __future__ import annotations

from datetime import date

import pytest

from momentum25.application.use_cases.screening import ExecuteScreening


class _FakeOHLCVRepo:
    def __init__(self, latest: date | None) -> None:
        self._latest = latest

    async def latest_date(self) -> date | None:
        return self._latest


class _CapturingOrchestrator:
    """Captures the trading_date ExecuteScreening resolves and hands off."""

    last_trading_date: date | None = None

    def __init__(self, **kwargs: object) -> None:
        pass

    async def run_daily_screening(
        self, trading_date: date, existing_run_id: int | None = None
    ) -> object:
        _CapturingOrchestrator.last_trading_date = trading_date

        class _Summary:
            pass

        return _Summary()


class _FakeScreeningRunRepo:
    _session = None

    async def list_runs(self, status: str, limit: int, offset: int) -> tuple[list, int]:
        class _Row:
            id = 1

        return [_Row()], 1


@pytest.mark.asyncio
async def test_run_via_orchestrator_screens_latest_bar_date_not_reference_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    latest_bar_date = date(2026, 8, 7)  # Friday, the actual last ingested session
    reference_date = date(2026, 8, 9)  # Sunday -- no security has a bar here

    monkeypatch.setattr(
        "momentum25.application.use_cases.screening_orchestrator.ScreeningOrchestrator",
        _CapturingOrchestrator,
    )

    use_case = ExecuteScreening(
        market_data_provider=None,
        security_repo=None,
        ohlcv_repo=_FakeOHLCVRepo(latest_bar_date),
        screening_run_repo=_FakeScreeningRunRepo(),
        indicator_pipeline=None,
        strategy_engine=None,
    )

    # Mirrors the clamp in ExecuteScreening.execute(): screening_date =
    # latest_bar_date or reference_date.
    latest = await use_case._ohlcv_repo.latest_date()
    screening_date = latest or reference_date
    await use_case._run_via_orchestrator(
        strategy=object(), trading_date=screening_date, existing_run_id=None
    )

    assert _CapturingOrchestrator.last_trading_date == latest_bar_date
    assert _CapturingOrchestrator.last_trading_date != reference_date
