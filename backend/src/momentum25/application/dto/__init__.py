"""Data Transfer Objects forming the stable API contract (IMPLEMENTATION_SPEC §3/§5).

These Pydantic models are the boundary between the application and transport layers.
Their shapes are final for the MVP; adding business logic must not change them.
"""

from momentum25.application.dto.common import Page, ProblemDetail
from momentum25.application.dto.health import HealthDTO
from momentum25.application.dto.market_data import OHLCVBarDTO, SecurityOHLCVDTO
from momentum25.application.dto.rankings import (
    RankingItemDTO,
    RankingsResponseDTO,
)
from momentum25.application.dto.runs import RunDTO, TriggerRefreshRequest
from momentum25.application.dto.stocks import (
    EngineBreakdownDTO,
    RuleResultDTO,
    ScorePointDTO,
    StockExplanationDTO,
    StockHistoryDTO,
)
from momentum25.application.dto.strategies import StrategyDetailDTO, StrategySummaryDTO

__all__ = [
    "EngineBreakdownDTO",
    "HealthDTO",
    "OHLCVBarDTO",
    "Page",
    "ProblemDetail",
    "RankingItemDTO",
    "RankingsResponseDTO",
    "RuleResultDTO",
    "RunDTO",
    "ScorePointDTO",
    "SecurityOHLCVDTO",
    "StockExplanationDTO",
    "StockHistoryDTO",
    "StrategyDetailDTO",
    "StrategySummaryDTO",
    "TriggerRefreshRequest",
]
