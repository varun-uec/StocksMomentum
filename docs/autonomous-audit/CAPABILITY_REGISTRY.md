# Capability Registry

Source: capabilities-summary.md, verified against repo as of 2026-08-18.

| # | Capability | API | Backend | Frontend |
|---|---|---|---|---|
| 1 | Momentum Screening & Ranking | POST /runs, GET /runs/{id}, /runs/latest, GET /rankings/runs/{id} | domain/scoring/scoring_engine.py, ranking_engine.py, domain/engines/* | — |
| 2 | Backtesting / Walk-Forward | POST /backtest/walk-forward | application/use_cases/walk_forward.py | web/src/app/backtest/ |
| 3 | Elliott Wave Analysis | GET /stocks/{symbol}/elliott-wave | domain/analytics/elliott/* | web/src/app/stock/[symbol]/elliott-wave/ |
| 4 | Chart Pattern Recognition | POST /stocks/{symbol}/chart-patterns | domain/analytics/chart_patterns.py | — |
| 5 | Technical Indicators | GET /stocks/{symbol}/indicators/series (in stocks.py, not securities.py); GET /securities/{symbol}/ohlcv, /history | infrastructure/pipelines/indicator_pipeline.py::IndicatorPipelineImpl (real implementation; domain/indicators/pipeline.py holds only the Protocol port) | web/src/lib/indicators/catalogue.ts |
| 6 | Strategies | GET /strategies, /strategies/{name} | domain/rules/* | web/src/app/strategies/ |
| 7 | Market & Stock Data | market.py, market_data.py, stocks.py, securities.py, watchlist.py, indices.py, validation.py, research.py, health.py | — | web/src/app/market/, watchlist/, data/, validation/, analytics/ |
| 8-20 | Frontend pages | — | — | dashboard, strategies, backtest, historical, experiment, market, stock/[symbol] (analysis, elliott-wave), data, validation, watchlist, analytics, learn/* |

This registry is provisional. Reviewer must verify every row against current source before auditing.
