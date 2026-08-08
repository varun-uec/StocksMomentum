
"""Production-grade Relative Strength computation pipeline.

Fetches benchmark and universe price history from the database, computes
deterministic RS metrics including:

- Universe-wide RS Rating (1–99 percentile) using multi-timeframe returns
- RS Line (stock price / benchmark price ratio) with trend slopes
- Multi-timeframe RS raw returns (1m/3m/6m/12m)
- Sector and industry relative strength percentiles
- Historical RS tracking (1m and 3m ago)
- Deterministic percentile calculation with no randomness

All calculations are vectorised with numpy/pandas and fully reproducible.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.security import Security
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("relative_strength_pipeline")

# Lookback periods (trading days)
_RS_1M_DAYS = 22
_RS_3M_DAYS = 63
_RS_6M_DAYS = 126
_RS_12M_DAYS = 252
_RS_LINE_SLOPE_DAYS = 50
_MIN_BARS = _RS_12M_DAYS + 30  # buffer for rolling operations

# Fixed precision for egress
_QUANT = Decimal("0.0001")


def _quantize(value: float | None) -> Decimal | None:
    """Cast a float metric to fixed-precision Decimal (or None)."""
    if value is None:
        return None
    return Decimal(f"{value:.6f}").quantize(_QUANT)


def _quantize_int(value: float | None) -> int | None:
    """Cast a float to int percentile (or None)."""
    if value is None:
        return None
    return int(round(value))


class RelativeStrengthPipeline:
    """Computes RS metrics deterministically using pandas/numpy vectorization.

    Calculates:
    - RS Rating: 1–99 percentile rank of composite RS vs universe
    - RS Line: ratio of stock price to benchmark price over time
    - RS Line slopes: 22d and 63d linear regression slopes
    - Multi-timeframe RS raw returns (1m/3m/6m/12m)
    - Sector/Industry RS percentiles
    - Historical RS rating for trend detection
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the pipeline to an async DB session."""
        self._session = session

    async def compute(
        self,
        security: Security,
        benchmark: Security,
        universe: list[Security],
        reference_date: date,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Return RS metrics for a security relative to benchmark and universe.

        Args:
            security: Target security.
            benchmark: Benchmark security.
            universe: Full universe list for percentile calculations.
            reference_date: Date for which to compute RS.
            config: Pipeline configuration.

        Returns:
            Dictionary with all RS metrics. Returns all None if insufficient data.
        """
        stock_bars = await self._fetch_bars(security.id, reference_date)
        bench_bars = await self._fetch_bars(benchmark.id, reference_date)

        if not stock_bars or not bench_bars or len(stock_bars) < _MIN_BARS:
            _logger.warning(
                "rs_insufficient_history",
                security_id=security.id,
                date=reference_date.isoformat(),
                stock_bars=len(stock_bars) if stock_bars else 0,
                bench_bars=len(bench_bars) if bench_bars else 0,
            )
            return self._null_rs()

        stock_df = self._bars_to_dataframe(stock_bars, True)
        bench_df = self._bars_to_dataframe(bench_bars, True)

        # Align on common dates to a reasonable maximum
        aligned = self._align_series(stock_df, bench_df)
        if aligned is None or len(aligned[0]) < _RS_12M_DAYS:
            return self._null_rs()

        stock_aligned, bench_aligned = aligned

        # Compute RS Line (ratio of stock to benchmark)
        rs_line = self._compute_rs_line(stock_aligned, bench_aligned)

        # ── Multi-timeframe raw returns (cumulative, for diagnostics) ──
        raw_1m = self._total_return(stock_aligned, _RS_1M_DAYS)
        raw_3m = self._total_return(stock_aligned, _RS_3M_DAYS)
        raw_6m = self._total_return(stock_aligned, _RS_6M_DAYS)
        raw_12m = self._total_return(stock_aligned, _RS_12M_DAYS)

        # IBD-style composite: non-overlapping quarterly returns with Q4 weighted 2×.
        # Q4 = most recent 3m, Q3/Q2/Q1 are the three prior non-overlapping quarters.
        # Formula: (2*Q4 + Q3 + Q2 + Q1) / 5  (equivalent to IBD's 40/20/20/20 weight).
        rs_raw = self._ibd_composite(stock_aligned)

        # ── Universe percentile computation ────────────────────────────
        universe_returns: list[float] = []
        for peer in universe:
            if peer.id == security.id:
                continue
            peer_bars = await self._fetch_bars(peer.id, reference_date)
            if peer_bars and len(peer_bars) >= _RS_12M_DAYS:
                peer_df = self._bars_to_dataframe(peer_bars, True)
                aligned_pair = self._align_series(peer_df, bench_df)
                if aligned_pair is not None and len(aligned_pair[0]) >= _RS_12M_DAYS:
                    peer_composite = self._ibd_composite(aligned_pair[0])
                    universe_returns.append(peer_composite)

        rs_rating = self._percentile_rank(rs_raw, universe_returns) if universe_returns else 50

        # ── RS Line slopes ─────────────────────────────────────────────
        rs_line_1m_slope = self._line_slope(rs_line, _RS_1M_DAYS)
        rs_line_3m_slope = self._line_slope(rs_line, _RS_3M_DAYS)

        # Keep the 50-session slope for backward compatibility
        rs_line_slope = self._line_slope(rs_line, _RS_LINE_SLOPE_DAYS)

        # ── Sector/Industry RS percentiles ─────────────────────────────
        sector_info = await self._compute_sector_rs(
            security, universe, stock_aligned, bench_df, reference_date
        )

        # ── Historical RS tracking ─────────────────────────────────────
        hist_1m_ago = await self._compute_historical_rs(
            security, benchmark, universe, reference_date - timedelta(days=30), config
        )
        hist_3m_ago = await self._compute_historical_rs(
            security, benchmark, universe, reference_date - timedelta(days=90), config
        )

        # Determine RS trend
        if hist_1m_ago is not None and hist_3m_ago is not None:
            if rs_rating > hist_1m_ago > hist_3m_ago:
                rs_trend = "improving"
            elif rs_rating < hist_1m_ago < hist_3m_ago:
                rs_trend = "declining"
            else:
                rs_trend = "stable"
        else:
            rs_trend = None

        return {
            "rs_rating": rs_rating,
            "rs_percentile": round(rs_rating / 100.0, 4),
            "rs_line_slope": rs_line_slope,
            "rs_line_slope_1m": rs_line_1m_slope,
            "rs_line_slope_3m": rs_line_3m_slope,
            "rs_raw_1m": raw_1m,
            "rs_raw_3m": raw_3m,
            "rs_raw_6m": raw_6m,
            "rs_raw_12m": raw_12m,
            "sector_rs_percentile": sector_info.get("sector_percentile"),
            "industry_rs_percentile": sector_info.get("industry_percentile"),
            "rs_rating_1m_ago": hist_1m_ago,
            "rs_rating_3m_ago": hist_3m_ago,
            "rs_rating_trend": rs_trend,
        }

    async def compute_batch(
        self,
        securities: list[Security],
        benchmark: Security,
        reference_date: date,
        config: dict[str, Any],
    ) -> dict[int | None, dict[str, Any]]:
        """Compute RS metrics for all securities relative to one benchmark.

        This is more efficient than single calls because the universe percentiles
        are computed once for all securities.

        Args:
            securities: All securities to compute RS for.
            benchmark: Benchmark security.
            reference_date: Reference date.
            config: Pipeline configuration.

        Returns:
            Dict mapping security_id -> RS metrics dict.
        """
        # Fetch benchmark bars once
        bench_bars = await self._fetch_bars(benchmark.id, reference_date)
        if not bench_bars or len(bench_bars) < _MIN_BARS:
            return {s.id: self._null_rs() for s in securities}

        bench_df = self._bars_to_dataframe(bench_bars, True)

        # Pre-fetch all security bars
        all_bars: dict[int | None, pd.DataFrame | None] = {}
        for sec in securities:
            bars = await self._fetch_bars(sec.id, reference_date)
            if bars and len(bars) >= _MIN_BARS:
                all_bars[sec.id] = self._bars_to_dataframe(bars, True)
            else:
                all_bars[sec.id] = None

        # Align all to benchmark and compute composite returns
        security_returns: dict[int | None, float] = {}
        aligned_dfs: dict[int | None, tuple[pd.Series, pd.Series]] = {}
        for sec in securities:
            stock_df = all_bars.get(sec.id)
            if stock_df is None:
                continue
            aligned = self._align_series(stock_df, bench_df)
            if aligned is None or len(aligned[0]) < _RS_12M_DAYS:
                continue
            stock_aligned, bench_aligned = aligned
            aligned_dfs[sec.id] = (stock_aligned, bench_aligned)
            raw_1m_v = self._total_return(stock_aligned, _RS_1M_DAYS) or 0.0
            raw_3m_v = self._total_return(stock_aligned, _RS_3M_DAYS) or 0.0
            raw_6m_v = self._total_return(stock_aligned, _RS_6M_DAYS) or 0.0
            raw_12m_v = self._total_return(stock_aligned, _RS_12M_DAYS) or 0.0
            composite = self._ibd_composite(stock_aligned)
            security_returns[sec.id] = composite

        if not security_returns:
            return {s.id: self._null_rs() for s in securities}

        all_composites = list(security_returns.values())

        # Compute results for each security
        results: dict[int | None, dict[str, Any]] = {}
        for sec in securities:
            if sec.id not in aligned_dfs:
                results[sec.id] = self._null_rs()
                continue

            stock_aligned, bench_aligned = aligned_dfs[sec.id]
            rs_line = self._compute_rs_line(stock_aligned, bench_aligned)

            raw_1m_v = self._total_return(stock_aligned, _RS_1M_DAYS) or 0.0
            raw_3m_v = self._total_return(stock_aligned, _RS_3M_DAYS) or 0.0
            raw_6m_v = self._total_return(stock_aligned, _RS_6M_DAYS) or 0.0
            raw_12m_v = self._total_return(stock_aligned, _RS_12M_DAYS) or 0.0

            composite = security_returns[sec.id]
            rs_rating = self._percentile_rank(composite, all_composites)

            results[sec.id] = {
                "rs_rating": rs_rating,
                "rs_percentile": round(rs_rating / 100.0, 4),
                "rs_line_slope": self._line_slope(rs_line, _RS_LINE_SLOPE_DAYS),
                "rs_line_slope_1m": self._line_slope(rs_line, _RS_1M_DAYS),
                "rs_line_slope_3m": self._line_slope(rs_line, _RS_3M_DAYS),
                "rs_raw_1m": raw_1m_v,
                "rs_raw_3m": raw_3m_v,
                "rs_raw_6m": raw_6m_v,
                "rs_raw_12m": raw_12m_v,
                "sector_rs_percentile": None,  # Batch mode skips sector
                "industry_rs_percentile": None,
                "rs_rating_1m_ago": None,
                "rs_rating_3m_ago": None,
                "rs_rating_trend": None,
            }

        return results

    async def _fetch_bars(
        self, security_id: int | None, reference_date: date, limit: int = 300
    ) -> list[Any] | None:
        """Retrieve historical OHLCV bars for a security."""
        from momentum25.infrastructure.persistence.models import OHLCVDailyModel

        stmt = (
            select(OHLCVDailyModel)
            .where(
                OHLCVDailyModel.security_id == security_id,
                OHLCVDailyModel.date <= reference_date,
            )
            .order_by(OHLCVDailyModel.date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return None
        return list(reversed(rows))

    @staticmethod
    def _bars_to_dataframe(bars: list[Any], include_ohlcv: bool = False) -> pd.DataFrame:
        """Convert ORM bars to DataFrame."""
        if include_ohlcv:
            data = {
                "date": [b.date for b in bars],
                "close": [float(b.close) for b in bars],
                "open": [float(b.open) for b in bars],
                "high": [float(b.high) for b in bars],
                "low": [float(b.low) for b in bars],
            }
        else:
            data = {
                "date": [b.date for b in bars],
                "close": [float(b.close) for b in bars],
            }
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _align_series(
        stock: pd.DataFrame, benchmark: pd.DataFrame
    ) -> tuple[pd.Series, pd.Series] | None:
        """Align stock and benchmark DataFrames on common dates."""
        merged = pd.merge(
            stock[["date", "close"]],
            benchmark[["date", "close"]],
            on="date",
            suffixes=("_stock", "_bench"),
        )
        if len(merged) < _RS_12M_DAYS:
            return None
        return merged["close_stock"], merged["close_bench"]

    @staticmethod
    def _total_return(prices: pd.Series, days: int) -> float | None:
        """Compute total return over last N trading days."""
        if len(prices) < days + 1:
            return None
        start = prices.iloc[-(days + 1)]
        end = prices.iloc[-1]
        if start == 0 or pd.isna(start) or pd.isna(end):
            return None
        return float((end / start) - 1.0)

    @staticmethod
    def _percentile_rank(value: float, universe: list[float]) -> int:
        """Return 1–99 percentile rank of value within universe.

        Uses inclusive counting: rank = (count <= value) / total * 99 + 1
        Deterministic: no randomness, no interpolation.
        """
        if not universe:
            return 50
        arr = np.array(universe)
        count_le = float(np.sum(arr <= value))
        rank = int(round((count_le / len(arr)) * 98 + 1))
        return int(np.clip(rank, 1, 99))

    @staticmethod
    def _compute_rs_line(stock: pd.Series, bench: pd.Series) -> pd.Series:
        """RS Line = ratio of stock price to benchmark price, normalized."""
        ratio = stock / bench
        return ratio / ratio.iloc[0]  # normalize to 1.0 at start

    @staticmethod
    def _line_slope(line: pd.Series, window: int) -> float | None:
        """Linear regression slope over window using polyfit."""
        if len(line) < window:
            return None
        y = line.iloc[-window:].values
        x = np.arange(len(y), dtype=float)
        if np.any(np.isnan(y)):
            return None
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)

    async def _compute_sector_rs(
        self,
        security: Security,
        universe: list[Security],
        stock_aligned: pd.Series,
        bench_df: pd.DataFrame | None,
        reference_date: date,
    ) -> dict[str, Any]:
        """Compute sector and industry RS percentiles."""
        sector = (security.sector or "").strip()
        industry = (security.industry or "").strip()

        result: dict[str, Any] = {
            "sector_percentile": None,
            "industry_percentile": None,
        }

        # Group peers by sector
        sector_returns: list[float] = []
        industry_returns: list[float] = []

        stock_composite = self._compute_composite_return(stock_aligned)

        for peer in universe:
            if peer.id == security.id:
                continue
            peer_bars = await self._fetch_bars(peer.id, reference_date)
            if not peer_bars or len(peer_bars) < _RS_12M_DAYS:
                continue
            peer_df = self._bars_to_dataframe(peer_bars, True)
            aligned_pair = self._align_series(peer_df, bench_df) if bench_df is not None else None
            if aligned_pair is None or len(aligned_pair[0]) < _RS_12M_DAYS:
                continue
            peer_aligned, _ = aligned_pair
            peer_composite = self._compute_composite_return(peer_aligned)

            peer_sector = (peer.sector or "").strip()
            peer_industry = (peer.industry or "").strip()

            if sector and peer_sector == sector and peer_composite is not None:
                sector_returns.append(peer_composite)
            if industry and peer_industry == industry and peer_composite is not None:
                industry_returns.append(peer_composite)

        if sector_returns and stock_composite is not None:
            result["sector_percentile"] = float(self._percentile_rank(
                stock_composite, sector_returns
            ))

        if industry_returns and stock_composite is not None:
            result["industry_percentile"] = float(self._percentile_rank(
                stock_composite, industry_returns
            ))

        return result

    @classmethod
    def _compute_composite_return(cls, prices: pd.Series) -> float | None:
        """Compute IBD-style composite RS return from a price series."""
        return cls._ibd_composite(prices) if len(prices) >= _RS_12M_DAYS + 1 else None

    @staticmethod
    def _ibd_composite(prices: pd.Series) -> float:
        """Return IBD-style composite RS score using non-overlapping quarterly returns.

        IBD RS Rating weights the most recent 3-month period (Q4) 2× the three
        prior non-overlapping quarters (Q1, Q2, Q3):
            Q4 = price_now / price_63d_ago - 1          (most recent quarter)
            Q3 = price_63d_ago / price_126d_ago - 1
            Q2 = price_126d_ago / price_189d_ago - 1
            Q1 = price_189d_ago / price_252d_ago - 1
            composite = (2*Q4 + Q3 + Q2 + Q1) / 5

        Non-overlapping periods avoid the double-counting inherent in comparing
        cumulative returns of different durations back to the same present date.
        Returns 0.0 when there is insufficient history (< 253 bars).
        """
        n = len(prices)
        if n < _RS_12M_DAYS + 1:
            return 0.0

        def _qret(back_from: int, back_to: int) -> float:
            """Return from `back_from` days ago to `back_to` days ago (0 = today)."""
            p_start = float(prices.iloc[-(back_from + 1)])
            p_end = float(prices.iloc[-(back_to + 1)] if back_to > 0 else prices.iloc[-1])
            return float(p_end / p_start - 1.0) if p_start != 0 else 0.0

        # Non-overlapping 63-day quarters
        q4 = _qret(_RS_3M_DAYS, 0)           # 63d ago → today
        q3 = _qret(_RS_6M_DAYS, _RS_3M_DAYS) # 126d ago → 63d ago
        q2 = _qret(189, _RS_6M_DAYS)          # 189d ago → 126d ago
        q1 = _qret(_RS_12M_DAYS, 189)         # 252d ago → 189d ago

        return (2.0 * q4 + q3 + q2 + q1) / 5.0

    async def _compute_historical_rs(
        self,
        security: Security,
        benchmark: Security,
        universe: list[Security],
        historical_date: date,
        config: dict[str, Any],
    ) -> int | None:
        """Compute RS rating for a historical date (1m or 3m ago)."""
        # If historical date is too far back to have bar data, return None
        result = await self.compute(
            security, benchmark, universe, historical_date, config
        )
        return result.get("rs_rating")

    @staticmethod
    def _null_rs() -> dict[str, Any]:
        return {
            "rs_rating": None,
            "rs_percentile": None,
            "rs_line_slope": None,
            "rs_line_slope_1m": None,
            "rs_line_slope_3m": None,
            "rs_raw_1m": None,
            "rs_raw_3m": None,
            "rs_raw_6m": None,
            "rs_raw_12m": None,
            "sector_rs_percentile": None,
            "industry_rs_percentile": None,
            "rs_rating_1m_ago": None,
            "rs_rating_3m_ago": None,
            "rs_rating_trend": None,
        }