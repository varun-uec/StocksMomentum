# Capabilities

Verified against the routers, pages and use cases on branch `wickstreet/m10-m11` (M10) on 2026-10-18. All API paths sit under `/api/v1`. The live schema is at `http://localhost:8000/docs`.

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
| 14 | Market-data refresh (NSE/BSE latest session) | Shipped | `/data` |
| 15 | Health, data freshness, Prometheus metrics | Shipped | — |
| 16 | Learn hub (methodology, scoring, rules, FAQ) | Shipped | `/learn/*` |
| 17 | Chart workspace: type-to-search, drawings with select/move/delete, settings and drawings saved on the server (Wickstreet M11) | Shipped on branch `wickstreet/m10-m11`, awaiting the M11 review | `/chart`, `/chart/[symbol]` |
| — | Fundamentals screening | Not built. Port and disabled engine only. | — |
| — | Authentication, multi-tenancy | Not built (ADR-010). | — |
| — | Intraday data, alerts, broker trading | Not built. | — |

## API

| Area | Method and path | Notes |
|---|---|---|
| Health | `GET /health`, `/health/live`, `/health/ready`, `/health/startup`, `/health/data-freshness` | Freshness reports sessions missed since the latest bar. |
| Metrics | `GET /metrics` | Prometheus format. |
| Runs | `GET /runs`, `GET /runs/latest`, `GET /runs/{run_id}` | |
| | `POST /runs/execute` | Runs the full pipeline. Background by default; poll `GET /runs/{id}`. |
| | `POST /runs` | Creates a `PENDING` row only. Nothing executes it. |
| Rankings | `GET /rankings/runs/{run_id}`, `GET /rankings/runs/{run_id}/stocks/{security_id}/explanation` | |
| Stocks | `GET /stocks/{symbol}`, `/history`, `/live`, `/indicators/series?interval=1D\|1W`, `/elliott-wave`; `POST /stocks/{symbol}/chart-patterns` | `/live` evaluates any symbol on demand. |
| Securities | `GET /securities` (search), `GET /securities/{symbol}/ohlcv?interval=1D\|1W` (adjusted daily or weekly bars, the adjustment schedule, `data_version`) | |
| Market | `GET /market/context`, `GET /indices/{index_code}/closes` | |
| Market data | `POST /market-data/refresh` | Fetches the latest NSE/BSE session. No backfill, no screening. |
| Watchlist | `GET /watchlist`, `GET /watchlist/detail`, `POST /watchlist/{symbol}`, `DELETE /watchlist/{symbol}` | |
| Workspace | `GET`/`PUT /workspaces/{id}`, `GET`/`PUT /drawings/{symbol}` | Saved chart settings and drawings. `ETag`/`If-Match` concurrency: `412` with the current document, `428` without a precondition (ADR-013 §5). |
| Strategies | `GET /strategies`, `GET /strategies/{name}` | |
| Validation | `GET /validation/historical/{name}`, `/alpha/{name}`, `/scorecard/{name}`, `/rules/{name}`, `/engines/{name}`; `POST /validation/experiment/run`, `POST /validation/dashboard` | Return-derived metrics carry a `measurability` block. |
| Research | `POST /research/historical/screen`, `/compare/runs`, `/verify/determinism`, `/experiment/run`, `/corporate-actions/refresh`; `GET /research/evaluate/{name}`, `/contribution/{name}`, `/compare/strategies` | Two experiment endpoints exist: `/research/experiment/run` and `/validation/experiment/run`. |
| Backtest | `POST /backtest/walk-forward` | Every response carries `benchmark_label` and `survivorship_warning`. |

The web client calls every endpoint except the health probes, `/metrics`, `POST /runs`, the ranking explanation endpoint and `POST /research/corporate-actions/refresh`.

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
| `/validation` | Research dashboard: scorecard, alpha, rule and engine metrics |
| `/analytics` | Contribution analysis across runs |
| `/historical` | Browse past runs and their rankings |
| `/experiment` | Run a strategy experiment |
| `/backtest` | Walk-forward backtest with the data caveat shown first |
| `/data` | Refresh the latest market session |
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
| `ingest`, `screen` | Stubs. They print a message and exit. |

## Operational scripts

`backend/scripts/` holds one-off research and backfill scripts: `reingest_history.py`, `monthly_forward_returns_backfill.py`, the `rp012_*`, `rp013_*` and `rp014_*` data backfills, `phase3_swing_backtest.py`, `phase3b_swing_backtest.py`, `benchmark.py` and `seed_demo_data.py`. Each script's docstring states its purpose. The research reports in [docs/research/](../research/) say which ones produced which dataset.
