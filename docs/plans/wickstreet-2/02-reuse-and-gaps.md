# 02 — Reuse and Gap Assessment

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Verified against branch `wickstreet/m10-m11` at `c03a890` on 2026-10-22.

This page says what Wickstreet 2.0 builds on. Every row names the code. A capability is "reused" only when the new work calls it without changing its behaviour.

## 1. What exists today

| Area | What ships | Where |
|---|---|---|
| Architecture | Hexagonal layers, two import contracts (`lint-imports`), one FastAPI process with APScheduler, PostgreSQL 16, Redis 7, Docker Compose on loopback | `backend/src/momentum25/`, ADR-001, ADR-007, ADR-012 |
| Instruments | `securities` (symbol, name, ISIN, empty `sector`/`industry`, listing and delisting dates, `tenant_id` seam), versioned | `infrastructure/persistence/models.py` (`SecurityModel`) |
| Identity continuity | Owner-verified rename links with an evidence source; never inferred | `domain/identity.py`, migration `0022` (table empty) |
| Prices | Daily bars 1994 → today across three tables; adjusted, weekly and monthly bars; `data_version` per symbol | `ohlcv_daily`, `legacy_ohlcv_daily`, `bse_legacy_ohlcv_daily`, `GET /securities/{symbol}/ohlcv` |
| Corporate actions | Splits, bonuses, rights; cash dividends skipped for adjustment | `corporate_actions`, `domain/entities/market_data.py` |
| Benchmarks | Price-index closes only (no TRI) | `benchmark_index_daily` |
| Point in time | `PointInTimeSource` bound to a decision session and a data revision; `LookAheadError` on any later read; adjustment rebuilt from actions known at the time | `infrastructure/persistence/point_in_time.py`, ADR-014 §7 |
| Versioning | `Versioned` mixin, trigger-maintained `<table>_history`, one `data_revision_seq`, `provenance` column (`recorded`, `published`, `reconstructed`) | `infrastructure/persistence/history.py` |
| Reproducibility | `data_manifests`, identity schema 3: `market_data_version`, `engine_identity`, `data_version`, `config_hash` | ADR-014 §10–§11, `domain/engine_version.py` |
| Momentum25 | 8 engines, strategy-as-config, scoring, ranking, explanations, immutable runs | `domain/engines/`, `domain/scoring/`, ADR-005, ADR-006 |
| Fundamentals | `FundamentalEngine` registered and disabled. It returns a placeholder rule. No data, no port implementation. | `domain/engines/fundamental.py` |
| Screener | Client-side filters over one run's rows: qualified, trend, risk, volume, breakout, sector, five numeric ranges; three column sets; saved screens as a server document | `web/src/components/momentum25/screener.tsx`, `saved_screens` document kind |
| Charting | Lightweight Charts 5 workspace: 21 drawing tools, indicator dialog, 1D/1W/1M, compare, layouts to 4×4, replay (`as_of`), alerts | `web/src/app/chart/`, `web/src/components/workspace/` |
| Research | Historical screening, Strategy Studio families and evaluations, walk-forward backtest, validation | `application/use_cases/research/`, `/studio`, `/backtest` |
| User state | `user_documents` with ETag/412/428 merge, watchlist, alerts | ADR-013 §5 |
| Navigation context | `?from=` same-origin return path; Assessment panel; workstation shell | `web/src/lib/return-path.ts`, `components/shell/`, `components/momentum25/` |
| Data intake | Offline CSV import (`import-eod`, `import-benchmark`); direct NSE/BSE adapters off by default | `application/use_cases/import_market_data.py`, `interface/cli/` |
| Visual identity | Paper/ink surfaces, restrained sea-green accent, one compact geometry | `web/src/app/globals.css` (`--ws-*` tokens) |

## 2. Reuse decisions

| New capability | Reuses | How |
|---|---|---|
| Company financials store | `Versioned` mixin and history triggers, `provenance` column, `data_revision_seq` | New fundamentals tables are versioned the same way. A restatement is a new filing row, so history tables only catch corrections to our own import. |
| Point-in-time fundamentals | `PointInTimeSource` pattern and `LookAheadError` | Add `PointInTimeFundamentals` beside it, bound to the same `decision_at` and revision. One rule: a filing is visible if `published_at ≤ decision_at`. |
| `data_version` for screens and scorecards | `data_manifests`, identity schema 3 | Add the new tables' high-water revisions to `market_data_version`, and a `METRIC_VERSION` to `engine_identity`. No new identity concept. |
| Fund NAV and ETF price charts | Chart workspace, `lightweight-charts`, compare | A NAV series is a line series through the same chart slot. ETFs already trade on NSE, so their bars come from `ohlcv_daily`. |
| Screener UI | `ScreenerPanel`, column sets, `RangePill`, saved screens document | Extend: asset-class tabs, a field picker fed by a server registry, compound groups. Momentum25 filters keep their current meaning. |
| Field catalogue | Studio rule registry pattern (`GET /studio/rules`, `rule_schemas.py`) | `GET /screener/fields` serves typed field definitions the same way. The UI never hard-codes a fundamental field. |
| Fundamental screening inside strategies | `FundamentalEngine` slot, ADR-005 config | Phase 2 replaces the placeholder with real rules (e.g. `roce_min`) read through the new port. It stays disabled in `minervini_trend_template`. |
| Context across journeys | `?from=` return path, replay `as_of`, Assessment panel | Every new page accepts `from` and `as_of`. The fund → stock → chart trail is a chain of `from` values, not new state. |
| Imports | `import-eod` CLI pattern, normalized CSV, no network | One `import-*` command per dataset with a published CSV/XML contract. |
| Portfolio valuation at traded prices | `traded-prices.ts` and the drawings rule (`price_basis 'traded'`) | Holdings keep traded quantities. Corporate actions after the trade date scale the quantity, as drawings scale anchors. |
| Background work | APScheduler daily job, Studio background evaluations with progress | Metric snapshot rebuild and import validation run as jobs after the daily sync. |
| Caching | Redis cache keyed on engine identity | Screen snapshots key on `(asset_class, as_of, data_version)`. |
| Security boundary | Host/Origin guard, loopback, 5 MiB body cap | CSV and CAS uploads stay under the cap or go through the CLI. |

## 3. Gaps

| # | Gap | Effect on 2.0 | Phase that closes it |
|---|---|---|---|
| G1 | No company entity. Financials belong to a company, not to a listing. | Cannot attach statements, peers or shares outstanding. | 1 |
| G2 | `securities.sector` and `.industry` are empty. | No peer groups, no sector exposure, no sector RS. | 1 (needs a source, see [04](04-data-sources.md)) |
| G3 | No fundamentals data, port or importer. | Nothing to show or screen. | 1 |
| G4 | No shares-outstanding history. | No market cap, so no PE, PB, EV, size buckets. | 1 |
| G5 | Screener filters run in the browser over one run's rows (at most the evaluated set). No compound logic, no fundamental fields. | Cannot express "ROCE > 20% AND RS > 80". | 2 |
| G6 | No instrument type. ETFs sit in `securities` like equities. | ETFs and stocks are mixed in screens and RS universes. | 3 |
| G7 | No mutual-fund entities, NAV store or AMFI importer. | No fund research. | 3 |
| G8 | No TRI benchmarks. | Fund and ETF benchmark comparison and tracking error are wrong against a price index. | 3 (blocked on licence) |
| G9 | No holdings disclosures or ISIN resolution. | No look-through, overlap or fund → stock journey. | 4 |
| G10 | No portfolio or transaction model. | No portfolio intelligence. | 5 |
| G11 | No dividend history used for returns. | Stock total return and IDCW fund returns are not computable. | 5 (portfolio income), later for TRI-style stock returns |
| G12 | The shell search returns equities only. | No single search across asset types. | 3 |

## 4. Must not change

- Momentum25 engines, rule thresholds, scoring, ranking, `strategy_id=30` and every existing strategy file.
- `ENGINE_VERSION`, `INDICATOR_VERSION` and `REFERENCE_UNIVERSE_VERSION` semantics. New metric code gets its own `METRIC_VERSION` inside the engine identity, so a metric change never moves a Momentum25 run identity unless the run reads metrics.
- Existing API paths and response shapes (NFR-13). New endpoints are additive.
- Run immutability (ADR-006), the research namespace (ADR-014 §7), the sealed hold-out.
- The RS universe. ETFs and funds never enter the RS rating universe. Phase 3 adds `instrument_type` and the RS pipeline filters to `EQUITY`; it must produce identical ratings for every stored date (golden test). We have not checked whether ETFs sit in today's RS universe. If the golden test shows any difference, that is a Momentum25 methodology change: Phase 3 stops and the owner decides.

## 5. Risks found during inspection

| Risk | Detail | Mitigation |
|---|---|---|
| Database size | The dev DB is 4.6 GB. All-plan NAV history since 2006 adds roughly 40 M rows. | Import Growth options by default; store NAV as `numeric(14,4)`; measure before importing IDCW history. |
| Two experiment endpoints, open drift items D1–D9 | Existing debt in [current/architecture.md](../../current/architecture.md#drift-from-the-add). | Not in 2.0 scope. 2.0 adds no new drift: new code lives in the four layers. |
| `alembic check` drift (R3-B-15) | The ORM and migrations disagree on dev. | Each 2.0 migration is checked against a fresh database in CI, not the dev DB. |
| Client-side screener | Moving filters server-side changes where Momentum25 filters run. | The server evaluator must return the same rows as `applyFilters` for every saved screen. A parity test runs both. |
