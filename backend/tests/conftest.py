"""Pytest fixtures, configuration, and markers for the test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.engines.trend_template import TrendTemplateEngine
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import EngineConfig
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.domain.value_objects.results import SectorStats
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import Base


_TEST_DATABASE_SUFFIX = "_test"


def _require_test_database(engine: AsyncEngine) -> None:
    """Abort unless the configured database is a dedicated test database.

    The integration fixtures ``TRUNCATE`` every table, so pointing the suite at a
    development or production database destroys its contents. The database name
    must therefore end in ``_test``; ``M25_DATABASE_URL`` is the knob that
    selects it.
    """
    name = engine.url.database or ""
    if not name.endswith(_TEST_DATABASE_SUFFIX):
        raise pytest.UsageError(
            f"Refusing to run database tests against {name!r}: these fixtures truncate "
            f"every table. Point M25_DATABASE_URL at a database whose name ends in "
            f"{_TEST_DATABASE_SUFFIX!r}."
        )


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Session-scoped engine bound to the session event loop; schema created once.

    Because the engine is created once on the single session-scoped event loop (see
    ``asyncio_default_*_loop_scope`` in ``pyproject.toml``), connections are never
    reused across loops — eliminating the "attached to a different loop" /
    "Event loop is closed" failures.
    """
    engine = get_database().engine
    _require_test_database(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a clean unit-of-work session, isolating each test.

    Every test starts from an empty schema: all tables are truncated (identities
    reset, FKs cascaded) in a committed transaction *before* the test runs. The test
    and the code under test then commit normally — which also lets components that
    open their own session (e.g. the API via TestClient) observe seeded rows. The next
    test's pre-truncate restores the pristine state, so no container teardown is needed.

    Note: an outer-transaction ROLLBACK / SAVEPOINT scheme was attempted first but the
    async (asyncpg) driver in this stack commits through ``join_transaction_mode``
    SAVEPOINTs, so truncation is used to guarantee deterministic isolation.
    """
    table_names = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    async with get_database().session() as session:
        yield session


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """Return a single OHLCV bar for testing."""
    return OHLCVBar(
        date=date(2024, 12, 1),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("104"),
        volume=1000000,
    )


@pytest.fixture
def sample_security() -> Security:
    """Return a test security."""
    return Security(
        id=1,
        symbol=Symbol("RELIANCE"),
        name="Reliance Industries Ltd",
        sector="Oil & Gas",
    )


@pytest.fixture
def sample_series(sample_bar: OHLCVBar) -> OHLCVSeries:
    """Return a one-bar OHLCV series."""
    return OHLCVSeries(security_id=1, bars=(sample_bar,))


@pytest.fixture
def empty_indicator_set() -> IndicatorSet:
    """Return an empty IndicatorSet for testing."""
    return IndicatorSet(as_of=date(2024, 12, 1))


@pytest.fixture
def empty_engine_config() -> EngineConfig:
    """Return an empty engine configuration."""
    return EngineConfig(id="test", enabled=True, weight=Decimal("1"))


@pytest.fixture
def trend_template_engine() -> TrendTemplateEngine:
    """Return a TrendTemplateEngine instance."""
    return TrendTemplateEngine()


@pytest.fixture
def minimal_evaluation_context(
    sample_security: Security,
    sample_series: OHLCVSeries,
    empty_indicator_set: IndicatorSet,
) -> EvaluationContext:
    """Return a minimal evaluation context for engine testing."""
    benchmark = OHLCVSeries(security_id=0, bars=sample_series.bars)
    return EvaluationContext(
        security=sample_security,
        series=sample_series,
        indicators=empty_indicator_set,
        benchmark=benchmark,
        sector_stats=SectorStats(),
    )