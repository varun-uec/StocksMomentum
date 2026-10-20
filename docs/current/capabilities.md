# Capabilities

Verified against the routers, pages and use cases on branch `wickstreet/m10-m11` through the M16 E2E audit on 2026-10-19. All API paths sit under `/api/v1`. The live schema is at `http://localhost:8000/docs`.

## Summary

| # | Capability | Status | Web page |
|---|---|---|---|
| 1 | Daily momentum screening and Top-25 ranking | Shipped | `/` |
| 2 | Per-stock score explanation and history | Shipped | `/stock/[symbol]` |
| 3 | Single-stock live analysis (any symbol, not only ranked ones) | Shipped | `/stock/[symbol]`, `/stock/[symbol]/analysis` |
| 4 | Charting and indicators (price panes, overlays, oscillators) | Shipped | `/stock/[symbol]/analysis` |
| 5 | Chart-pattern recognition | Shipped, research surface | `/stock/[symbol]/analysis` |
| 6 | Elliott Wave analysis | Shipped, research surface | `/stock/[symbol]/elliott-wave` |
| 7 | Suggested stop-loss (risk only) | Shipped | stock pages, dashboard |
| 8 | Watchlist | Shipped | `/watchlist` |
| 9 | Market context (breadth, index) | Shipped; sector panel empty (no sector data) | `/market` |
| 10 | Strategies: list, inspect, compare | Shipped | `/strategies` |
| 11 | Validation: scorecard, alpha, rule and engine IC | Shipped | `/validation` |
| 12 | Research: historical screening, run comparison, contribution, experiments, determinism check | Shipped | `/analytics`, `/historical`, `/experiment` |
| 13 | Walk-forward backtest (3/6/12M, monthly) | Shipped with labelled approximations | `/backtest` |
| 14 | Market-data import from authorized CSV; optional direct NSE/BSE refresh when explicitly enabled | Shipped | `/data` |
| 15 | Health, data freshness, Prometheus metrics | Shipped | — |
| 16 | Learn hub (methodology, scoring, rules, FAQ) | Shipped | `/learn/*` |
| 17 | Chart workspace: search, 21 drawing tools, indicators (Alt+I), chart types and scales, 1D/1W/1M bars, compare, layouts up to 4 × 4 with sync, saved on the server (M11–M13) | Shipped on branch `wickstreet/m10-m11` | `/chart`, `/chart/[symbol]` |
| 18 | Daily alerts on a chart series: close, RSI, ADX, ATR, MACD; fire once, re-arm (M15) | Shipped on branch `wickstreet/m10-m11` | chart side panel |
| 19 | Strategy Studio: families with a hypothesis and lineage, registry-bounded configs, Screening Result / Historical Research — In-Sample / Out-of-Sample Evaluation, point in time (M14) | Shipped on branch `wickstreet/m10-m11` | `/studio` |
| — | Fundamentals screening | Not built. Port and disabled engine only. | — |
| — | Authentication, multi-tenancy | Not built (ADR-010). | — |
| — | Intraday data, broker trading, alert delivery outside the app | Not built. | — |

## API

| Area | Method and path | Notes |
|---|---|---|
| Health | `GET /health`, `/health/live`, `/health/ready`, `/health/startup`, `/health/data-freshness` | Freshness reports sessions missed since the latest bar. |
| Metrics | `GET /metrics` | Prometheus format. |
| Runs | `GET /runs`, `GET /runs/latest`, `GET /runs/{run_id}` | |
| | `POST /runs/execute` | Screens stored bars by default. Background by default; poll `GET /runs/{id}`. Direct exchange downloads require explicit operator opt-in; `force=true` returns `409` while disabled. |
| | `POST /runs` | Creates a `PENDING` row and schedules screening over stored data by default; returns `202`; poll `GET /runs/{id}`. Forced exchange downloads return `409` while the adapter is disabled. |
| Rankings | `GET /rankings/runs/{run_id}`, `GET /rankings/runs/{run_id}/stocks/{security_id}/explanation` | |
| Stocks | `GET /stocks/{symbol}`, `/history`, `/live`, `/indicators/series?interval=1D\|1W`, `/elliott-wave`; `POST /stocks/{symbol}/chart-patterns` | `/live` evaluates any symbol on demand. |
| Securities | `GET /securities` (search), `GET /securities/{symbol}/ohlcv?interval=1D\|1W\|1M` (adjusted daily, weekly or monthly bars, the adjustment schedule, `data_version`) | |
| Market | `GET /market/context`, `GET /indices/{index_code}/closes` | |
| Market data | `GET /market-data/status`, `POST /market-data/refresh` | Direct exchange refresh is disabled by default and returns `409` unless `M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED=true`. The supported default import path is the local `import-eod` / `import-benchmark` CLI. |
| Watchlist | `GET /watchlist`, `GET /watchlist/detail`, `POST /watchlist/{symbol}`, `DELETE /watchlist/{symbol}` | |
| Workspace | `GET`/`PUT /workspaces/{id}`, `GET`/`PUT /drawings/{symbol}` | Saved chart settings and drawings. `ETag`/`If-Match` concurrency: `412` with the current document, `428` without a precondition (ADR-013 §5). |
| Strategies | `GET /strategies`, `GET /strategies/{name}` | User strategies never appear here. |
| Alerts | `GET /alerts`, `POST /alerts`, `DELETE /alerts/{id}`, `POST /alerts/{id}/rearm`, `POST /alerts/seen`, `POST /alerts/evaluate` | The daily job evaluates after every strategy has synced. |
| Studio | `GET /studio/rules`; `GET`/`POST /studio/families`; `POST /studio/families/{id}/strategies`; `GET`/`POST /studio/families/{id}/evaluations`; `GET /studio/evaluations/{id}`, `POST /studio/evaluations/{id}/retry` | Saves are checked against the rule registry (422). Evaluations run in the background and return `202`; poll for progress. A second Out-of-Sample Evaluation in a family returns `409`. |
| Validation | `GET /validation/historical/{name}`, `/alpha/{name}`, `/scorecard/{name}`, `/rules/{name}`, `/engines/{name}`; `POST /validation/experiment/run`, `POST /validation/dashboard` | Return-derived metrics carry a `measurability` block. |
| Research | `POST /research/historical/screen`, `/compare/runs`, `/verify/determinism`, `/experiment/run`, `/corporate-actions/refresh`; `GET /research/evaluate/{name}`, `/contribution/{name}`, `/compare/strategies` | Two experiment endpoints exist: `/research/experiment/run` and `/validation/experiment/run`. |
| Backtest | `POST /backtest/walk-forward` | Every response carries `benchmark_label` and `survivorship_warning`. |

The web client calls every endpoint except the health probes, `/metrics`, `POST /runs`, the ranking explanation endpoint and `POST /research/corporate-actions/refresh`. `POST /runs` is covered by an API integration regression with the market provider stubbed.

## Web UI

A Vite single-page app: React 18, React Router 7, TypeScript, Tailwind. The API serves the build and the app calls same-origin `/api/v1`. Routes are code-split (`web/src/main.tsx`). Charts: `lightweight-charts` 5 and `recharts`. Data: TanStack Query through one client, `web/src/lib/api-client.ts`. Light, dark and system themes. Every page footer credits the chart library.

| Route | Purpose |
|---|---|
| `/` | Dashboard: run summary, Top-25 table, strategy selector, "run screening" |
| `/chart`, `/chart/[symbol]` | Chart workspace. Type anywhere, `/` or Ctrl/⌘+K to search. Drawings: select, drag, Delete. Saved on the server; `/chart` reopens the last symbol. |
| `/stock/[symbol]` | Score breakdown, rule matrix, engine contributions, history, live analysis, stop-loss |
| `/stock/[symbol]/analysis` | Unified analysis screen: multi-pane chart, indicator catalogue, patterns, in-browser signal score |
| `/stock/[symbol]/elliott-wave` | Elliott Wave counts and Fibonacci zones |
| `/watchlist` | Saved symbols with live detail |
| `/market` | Breadth and index context |
| `/strategies` | Strategy list, comparison, contribution |
| `/studio` | Strategy Studio: families, lineage, a config form from the rule registry, the three result classes |
| `/validation` | Research dashboard: scorecard, alpha, rule and engine metrics |
| `/analytics` | Contribution analysis across runs |
| `/historical` | Browse past runs and their rankings |
| `/experiment` | Run a strategy experiment |
| `/backtest` | Walk-forward backtest with the data caveat shown first |
| `/data` | Inspect stored data; import authorized CSV data by CLI. The direct refresh control appears only when the operator explicitly enables downloads. |
| `/learn`, `/learn/{minervini-methodology, momentum25-methodology, momentum-investing, scoring-guide, rule-guide, faq}` | Methodology and education |
| `/about` | What Wickstreet is; the chart-library licence notice |
| `/lab/chart-grid?n=&symbol=` | Engineering diagnostic: `n` charts on one symbol (multi-chart smoke check). Not in the navigation. |

## CLI

`cd backend && uv run momentum25 <command>` (Typer).

| Command | Status |
|---|---|
| `engines` | Lists registered engines. |
| `strategies` | Lists strategy files with config hash. |
| `walk-forward --start --end --initial-capital` | Runs the backtest. Same wiring as the API. |
| `import-eod FILE [--actions FILE]` | Imports normalized authorized daily-bar CSV and optional corporate-action history; no network access. |
| `import-benchmark FILE` | Imports one authorized benchmark close series from CSV. |
| `screen [--strategy NAME]` | Screens already stored data and never downloads. |
| `ingest` | Retired; exits nonzero with the supported `import-eod` workflow. |

## Operational scripts

`backend/scripts/` holds one-off research and backfill scripts: `reingest_history.py`, `monthly_forward_returns_backfill.py`, the `rp012_*`, `rp013_*` and `rp014_*` data backfills, `phase3_swing_backtest.py`, `phase3b_swing_backtest.py`, `benchmark.py` and `seed_demo_data.py`. Each script's docstring states its purpose. The research reports in [docs/research/](../research/) say which ones produced which dataset.
