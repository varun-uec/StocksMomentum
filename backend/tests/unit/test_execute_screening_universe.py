"""Unit test for ExecuteScreening's instrument-master enrichment (Objective 3).

Without this enrichment, every security upserted by the daily screening run
carries ``listing_date=None`` forever, which silently defeats the
survivorship-bias mitigation in ``HistoricalScreeningUseCase`` (a ``None``
listing date is always treated as eligible).
"""

from __future__ import annotations

from datetime import date

import pytest

from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.domain.ports.market_data import RawInstrument
from momentum25.domain.value_objects.types import Symbol


class _FakeMarketDataProvider:
    async def fetch_instrument_master(self) -> list[RawInstrument]:
        return [
            RawInstrument(
                symbol="INFY",
                name="Infosys Limited",
                isin="INE009A01021",
                listing_date=date(1995, 6, 8),
            )
        ]


class _FakeSecurityRepo:
    def __init__(self) -> None:
        self.upserted: list[object] = []

    async def upsert_many(self, securities: list[object]) -> None:
        self.upserted.extend(securities)

    async def list_active(self) -> list[object]:
        return self.upserted


class _FakeScreeningRunRepo:
    _session = None


@pytest.mark.asyncio
async def test_upsert_securities_enriches_from_instrument_master() -> None:
    security_repo = _FakeSecurityRepo()
    use_case = ExecuteScreening(
        market_data_provider=_FakeMarketDataProvider(),
        security_repo=security_repo,
        ohlcv_repo=None,
        screening_run_repo=_FakeScreeningRunRepo(),
        indicator_pipeline=None,
        strategy_engine=None,
    )

    result = await use_case._upsert_securities(["INFY", "UNKNOWNCO"])

    by_symbol = {str(s.symbol): s for s in result}
    assert by_symbol[Symbol("INFY")].listing_date == date(1995, 6, 8)
    assert by_symbol[Symbol("INFY")].name == "Infosys Limited"
    # A symbol absent from the instrument master falls back to a bare
    # placeholder rather than failing the whole ingest.
    assert by_symbol[Symbol("UNKNOWNCO")].listing_date is None
    assert by_symbol[Symbol("UNKNOWNCO")].name == "UNKNOWNCO"
