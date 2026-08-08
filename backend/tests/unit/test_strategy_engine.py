"""Unit tests for the StrategyEngine orchestrator."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.engines.trend_template import TrendTemplateEngine
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import (
    EngineConfig,
    Strategy,
    StrategyConfig,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.domain.value_objects.results import SectorStats
from momentum25.domain.value_objects.types import Symbol


@pytest.fixture
def registry() -> EngineRegistry:
    """Return an engine registry with the Trend Template engine registered."""
    reg = EngineRegistry()
    reg.register(TrendTemplateEngine())
    return reg


@pytest.fixture
def scoring_engine() -> ScoringEngineImpl:
    """Return a scoring engine instance."""
    return ScoringEngineImpl()


@pytest.fixture
def ranking_engine() -> RankingEngineImpl:
    """Return a ranking engine instance."""
    return RankingEngineImpl()


@pytest.fixture
def strategy_engine(
    registry: EngineRegistry,
    scoring_engine: ScoringEngineImpl,
    ranking_engine: RankingEngineImpl,
) -> StrategyEngine:
    """Return a wired StrategyEngine."""
    return StrategyEngine(engines=registry, scoring=scoring_engine, ranking=ranking_engine)


@pytest.fixture
def sample_strategy() -> Strategy:
    """Return a minimal strategy that enables the trend_template engine."""
    return Strategy(
        name="test_strategy",
        version=1,
        config_hash="abc123",
        config=StrategyConfig(
            name="test_strategy",
            version=1,
            engines=(
                EngineConfig(
                    id="trend_template",
                    enabled=True,
                    weight=Decimal("1"),
                    gate=True,
                ),
            ),
        ),
    )


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    """Return a minimal evaluation context for testing."""
    security = Security(id=1, symbol=Symbol("RELIANCE"), name="Reliance Industries Ltd")
    bar = OHLCVBar(
        date=date.today(),
        open=Decimal("2500"),
        high=Decimal("2520"),
        low=Decimal("2490"),
        close=Decimal("2510"),
        volume=1000000,
    )
    series = OHLCVSeries(security_id=1, bars=(bar,))
    indicators = IndicatorSet(as_of=date.today())
    benchmark = OHLCVSeries(security_id=0, bars=(bar,))
    return EvaluationContext(
        security=security,
        series=series,
        indicators=indicators,
        benchmark=benchmark,
        sector_stats=SectorStats(),
    )


class TestStrategyEngine:
    """Tests for the StrategyEngine orchestrator."""

    def test_score_security_returns_stock_score(
        self,
        strategy_engine: StrategyEngine,
        evaluation_context: EvaluationContext,
        sample_strategy: Strategy,
    ) -> None:
        """score_security should return a valid StockScore without raising."""
        score = strategy_engine.score_security(evaluation_context, sample_strategy)
        assert score.security_id == 1
        assert isinstance(score.momentum_score, Decimal)
        assert isinstance(score.buy_setup_score, Decimal)
        assert len(score.engine_results) > 0
        assert isinstance(score.hard_filters_passed, bool)

    def test_run_returns_scores_and_rankings(
        self,
        strategy_engine: StrategyEngine,
        evaluation_context: EvaluationContext,
        sample_strategy: Strategy,
    ) -> None:
        """run should return scores and rankings for multiple contexts."""
        contexts = [evaluation_context, evaluation_context]
        scores, rankings = strategy_engine.run(contexts, sample_strategy)
        assert len(scores) == 2
        assert len(rankings) == 2
        for score in scores:
            assert isinstance(score.momentum_score, Decimal)
        for rank in rankings:
            assert isinstance(rank.momentum_score, Decimal)