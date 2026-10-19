"""Authorized local imports preserve raw bars and recompute corporate actions."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.import_market_data import ImportBenchmarkCsv, ImportEodCsv
from momentum25.infrastructure.persistence.models import (
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlCorporateActionRepository,
    SqlOHLCVRepository,
    SqlSecurityRepository,
)
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)


@pytest.mark.asyncio
async def test_import_eod_is_idempotent_and_recomputes_adjusted_history(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    db_session.add(
        SecurityModel(
            symbol="TEST",
            name="Test Corporation",
            sector="Technology",
            industry="Software",
            exchange="NSE",
            is_active=True,
        )
    )
    await db_session.flush()
    bars = tmp_path / "bars.csv"
    bars.write_text(
        "symbol,date,open,high,low,close,volume,turnover_value,exchange\n"
        "TEST,2023-01-02,100,105,95,100,1000,100000,BSE\n"
        "TEST,2023-01-03,50,55,45,51,2000,102000,BSE\n",
        encoding="utf-8",
    )
    actions = tmp_path / "actions.csv"
    actions.write_text(
        "symbol,ex_date,type,ratio,raw_subject\nTEST,2023-01-03,bonus,0.5,1:1 bonus\n",
        encoding="utf-8",
    )
    importer = ImportEodCsv(
        SqlSecurityRepository(db_session),
        SqlOHLCVRepository(db_session),
        SqlCorporateActionRepository(db_session),
    )

    first = await importer.execute(bars, actions)
    second = await importer.execute(bars, actions)

    assert first == {"symbols": 1, "bars": 2, "actions": 1, "adjusted_bars": 2}
    assert second == first
    security = await db_session.scalar(select(SecurityModel).where(SecurityModel.symbol == "TEST"))
    assert security is not None
    assert (security.name, security.sector, security.industry, security.exchange) == (
        "Test Corporation",
        "Technology",
        "Software",
        "BSE",
    )
    result = await db_session.execute(
        select(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security.id)
        .order_by(OHLCVDailyModel.date)
    )
    older, ex_date = result.scalars().all()
    assert (older.close, older.adj_factor, older.adj_close) == (100, 0.5, 50)
    assert (ex_date.close, ex_date.adj_factor, ex_date.adj_close) == (51, 1, 51)


@pytest.mark.asyncio
async def test_invalid_import_does_not_write_partial_rows(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    bars = tmp_path / "invalid.csv"
    bars.write_text(
        "symbol,date,open,high,low,close,volume\n"
        "GOOD,2023-01-02,100,105,95,100,1000\n"
        "BAD,2023-01-03,100,99,95,100,1000\n",
        encoding="utf-8",
    )
    importer = ImportEodCsv(
        SqlSecurityRepository(db_session),
        SqlOHLCVRepository(db_session),
        SqlCorporateActionRepository(db_session),
    )
    with pytest.raises(ValueError, match="OHLC values violate"):
        await importer.execute(bars)
    assert await db_session.scalar(select(SecurityModel.id)) is None


@pytest.mark.asyncio
async def test_benchmark_csv_import_is_idempotent(tmp_path: Path, db_session: AsyncSession) -> None:
    benchmark = tmp_path / "benchmark.csv"
    benchmark.write_text(
        "index_code,date,close\nNIFTY500,2026-01-02,25000\nNIFTY500,2026-01-05,25100\n",
        encoding="utf-8",
    )
    importer = ImportBenchmarkCsv(SqlBenchmarkIndexRepository(db_session))

    first = await importer.execute(benchmark)
    second = await importer.execute(benchmark)

    assert first == second == {"index_code": "NIFTY500", "bars": 2}
    rows = await db_session.scalars(
        select(BenchmarkIndexDailyModel).order_by(BenchmarkIndexDailyModel.date)
    )
    assert [(row.index_code, row.close) for row in rows.all()] == [
        ("NIFTY500", 25000),
        ("NIFTY500", 25100),
    ]
