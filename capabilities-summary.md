# Momentum25 — Core Capabilities

## 1. Momentum Screening & Ranking
Runs a screening pass over the equity universe and ranks qualified stocks.

- API: `POST /runs` (trigger a run), `GET /runs/{run_id}`, `GET /runs/latest`, `GET /rankings/runs/{run_id}`
- Files: `interface/api/routers/runs.py`, `rankings.py`
- Logic: `domain/scoring/scoring_engine.py`, `ranking_engine.py` — apply hard gates first (a stock that fails a gate gets `rank=None`), then score with factor engines in `domain/engines/`: `trend_template.py`, `momentum_quality.py`, `relative_strength.py`, `breakout.py`, `pattern.py`, `volume_accumulation.py`, `risk.py`, `fundamental.py`

## 2. Backtesting / Walk-Forward
Validates the ranking methodology out-of-sample.

- API: `POST /backtest/walk-forward` (`interface/api/routers/backtest.py`)
- Logic: `application/use_cases/walk_forward.py`, `interface/walk_forward_wiring.py`
- Frontend: `web/src/app/backtest/`

## 3. Elliott Wave Analysis
Full wave-pattern analysis on individual stocks.

- API: `GET /stocks/{symbol}/elliott-wave`
- Use case: `application/use_cases/elliott_wave.py`
- Domain: `domain/analytics/elliott/` — `analysis.py`, `fibonacci.py`, `patterns.py`, `personality.py`, `ranking.py`
- Frontend: `web/src/app/stock/[symbol]/elliott-wave/page.tsx`, `elliott-wave-panels.tsx`, `useElliottWaveChart.ts`

## 4. Chart Pattern Recognition
Detects classic chart patterns on a stock's price history.

- API: `POST /stocks/{symbol}/chart-patterns`
- Domain: `domain/analytics/chart_patterns.py`

## 5. Technical Indicators
Serves indicator series and OHLCV data per stock.

- API: `GET /securities/{symbol}/indicators/series`, `/ohlcv`, `/history`
- Backend: `domain/indicators/pipeline.py` / `pipeline_impl.py`
- Frontend: `web/src/lib/indicators/catalogue.ts`

**Gap:** `pipeline_impl.py` currently holds only an `IndicatorPipelinePlaceholder` that returns `None`s. The real indicator math was not found here — verify where it's actually computed before relying on this path.

## 6. Strategies
Exposes named rule sets that drive screening.

- API: `GET /strategies`, `GET /strategies/{name}`
- Domain: `domain/rules/`

## 7. Market & Stock Data
Supporting data endpoints: `market.py`, `market_data.py`, `stocks.py`, `securities.py`, `watchlist.py`, `indices.py`, `validation.py`, `research.py`, `health.py`.

## Frontend Routes
`web/src/app/`: `/` (dashboard), `strategies`, `backtest`, `historical`, `experiment`, `market`, `stock/[symbol]` (+ `analysis`, `elliott-wave`), `data`, `validation`, `watchlist`, `analytics`, `learn` (+ `scoring-guide`, `minervini-methodology`, `faq`, `momentum25-methodology`, `momentum-investing`, `rule-guide`).
