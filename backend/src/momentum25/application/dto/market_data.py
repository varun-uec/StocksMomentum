"""Market-data DTOs: chart price series and the manual refresh contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OHLCVBarDTO(BaseModel):
    """A single OHLCV bar for chart rendering."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class SecurityOHLCVDTO(BaseModel):
    """A symbol's price series."""

    symbol: str
    bars: list[OHLCVBarDTO]


class IndexCloseBarDTO(BaseModel):
    """A single benchmark-index bar.

    Close only: ``benchmark_index_daily`` stores no open/high/low/volume, and
    a fabricated OHLC would misrepresent the source.
    """

    date: date
    close: Decimal


class IndexOHLCVDTO(BaseModel):
    """A benchmark index's close series."""

    index_code: str
    bars: list[IndexCloseBarDTO]


class SecuritySearchResultDTO(BaseModel):
    """One typeahead suggestion for the symbol lookup."""

    symbol: str
    name: str
    sector: str | None = None


class IndicatorBarDTO(BaseModel):
    """One day's indicator values for the chart sub-panes (Phase 9).

    ``None`` fields mean the indicator was undefined that bar (warm-up or
    insufficient history). Every value is the same quantized series the
    snapshot endpoint reports as its latest value.
    """

    date: date
    rsi14: Decimal | None = None
    atr14: Decimal | None = None
    adx14: Decimal | None = None
    macd_line: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None


class SecurityIndicatorSeriesDTO(BaseModel):
    """A symbol's per-bar indicator series."""

    symbol: str
    bars: list[IndicatorBarDTO]


# ── Manual latest-session refresh ─────────────────────────────────────

Exchange = Literal["NSE", "BSE"]


@dataclass(slots=True)
class ExchangeRefreshResult:
    """What one exchange's refresh actually did (mutated in place by the use case)."""

    exchange: str
    bars_fetched: int = 0
    securities_matched: int = 0
    securities_missing: int = 0
    securities_unmapped: int = 0
    rows_written: int = 0
    provider_error: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RefreshSummary:
    """Structured result of one refresh, across every requested exchange."""

    target_date: date
    results: list[ExchangeRefreshResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def overall_status(self) -> str:
        """``success`` when every exchange wrote rows, ``partial`` / ``failed`` otherwise."""
        if not self.results:
            return "failed"
        failed = sum(1 for r in self.results if r.provider_error is not None or r.rows_written == 0)
        if failed == 0:
            return "success"
        return "failed" if failed == len(self.results) else "partial"


class ExchangeRefreshResultDTO(BaseModel):
    """Per-exchange refresh outcome as exposed by the API."""

    exchange: str
    bars_fetched: int
    securities_matched: int
    securities_missing: int
    securities_unmapped: int
    rows_written: int
    provider_error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RefreshMarketDataRequest(BaseModel):
    """Request body for ``POST /market-data/refresh``."""

    exchanges: list[Exchange] = Field(
        default=["NSE"],
        min_length=1,
        description="Exchanges to refresh. Duplicates are ignored, order is preserved.",
    )


class RefreshMarketDataResponse(BaseModel):
    """Result of a latest-session market-data refresh."""

    overall_status: str
    target_date: date
    duration_seconds: float
    results: list[ExchangeRefreshResultDTO]

    @classmethod
    def from_summary(cls, summary: RefreshSummary) -> RefreshMarketDataResponse:
        """Map the use-case summary onto the wire shape."""
        return cls(
            overall_status=summary.overall_status,
            target_date=summary.target_date,
            duration_seconds=round(summary.duration_seconds, 3),
            results=[
                ExchangeRefreshResultDTO(
                    exchange=r.exchange,
                    bars_fetched=r.bars_fetched,
                    securities_matched=r.securities_matched,
                    securities_missing=r.securities_missing,
                    securities_unmapped=r.securities_unmapped,
                    rows_written=r.rows_written,
                    provider_error=r.provider_error,
                    warnings=list(r.warnings),
                )
                for r in summary.results
            ],
        )
