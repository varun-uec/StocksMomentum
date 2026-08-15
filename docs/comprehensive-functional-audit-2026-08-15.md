# Momentum25 India — Comprehensive Functional Audit

**Date:** 2026-08-15
**Repository:** `/Users/varunagarwal/Downloads/Applications/StocksMomentum`
**Auditor:** OpenCode (read-only)
**Scope:** backend API, Next.js frontend, PostgreSQL data layer, architecture, tests, static analysis, documentation.
**Mode:** AUDIT ONLY. No source, configuration, database data, or application state was modified.

---

## 1. Executive Summary

### 1.1 Overall status

**Committed implementation (repo HEAD `b9de0a1`): substantially production-ready and clean.**
The core Momentum25 pipeline is implemented, deterministic, and well-tested. The production strategy (`minervini_trend_template` v3) runs successfully, produces rankings, and explains every score. Elliott Wave remains a properly isolated research screen with projected completion zones retained. Stop-loss output is risk-only and does not leak targets or risk/reward into the core product. Static analysis is clean, tests pass, import-linter contracts hold, and the frontend builds.

**Running environment: NOT current.** Two environmental gaps dominate this audit and are the source of nearly every observable defect:

1. **The running dev API server predates the latest fix commit.** The uvicorn process started at `2026-08-15T04:50:07Z` (10:20 IST); HEAD commit `b9de0a1` ("Verification verdicts F1–F20") was authored at `2026-08-15 11:47 IST`. The server was launched without `--reload`, so it runs pre-fix bytecode. Every F2–F20 source fix exists in code but is unavailable to the live process until a restart.
2. **Database is one migration behind.** `alembic_version` is `0012_drop_legacy_ohlcv_bak`; migration `0013_filter_column_indexes` (the F4 `ix_ohlcv_daily_date` index plus four more filter-column indexes and the `screening_runs.status` CHECK constraint) is committed but not applied. I am forbidden to run migrations, so the index part of the F4 fix cannot take effect and could not be verified live.

### 1.2 Finding counts

| Severity | Count |
|---|---|
| P0 — Critical | 3 |
| P1 — High | 4 |
| P2 — Medium | 4 |
| P3 — Low | 5 |
| **Total** | **16** |

Recurrence note: many findings are prior audit items F2/F3/F4/F5/F8/F10 re-appearing **only because they are not deployed/migrated**, not because the committed code is wrong. Each finding states this explicitly.

### 1.3 Major strengths

- Deterministic, explainable screening with per-rule contribution and hard-filter reporting (verified on run 12).
- Corporate-action backward adjustment is correct: RELIANCE 2024-10-28 bonus verified `close 2655.70 → adj_close 1327.85` at `adj_factor 0.5`; no duplicate actions; unique constraint enforced.
- Elliott Wave is fully isolated from Momentum25 scoring, ranking, screening, gates, trend template, RS, volume, pattern, and stop-loss (verified both import directions in source).
- Stop-loss is risk-only in API (`level` + `method` only) and domain (`stop_loss.py` carries no reward/target/R-multiple).
- Static analysis clean against committed source: `ruff` 0, `mypy` 0/218 files, `tsc` clean, ESLint clean, frontend build clean, import-linter 2/2 contracts kept.
- Tests pass: 598 passed on the dedicated `momentum25_test` database (dev DB untouched).

### 1.4 Major risks

- Data freshness is STALE: latest bar `2026-08-07`, 5 sessions missed (operational, documented limitation).
- The committed performance fixes for `/live`, `/validation/dashboard`, and `/market/context` are not live: observed 8–10 s, 44 s, and 1.54 s respectively against the running server.
- The F4/F14 performance indexes are committed but not migrated; the running DB has only primary-key indexes on `ohlcv_daily`, `rule_results`, `forward_returns`, `universe_membership`, and `benchmark_index_daily`.
- `/research/contribution` is slow (~28.5 s) and emits 28-digit Decimal precision; the precision is at least partly present in committed code (`avg_importance` is an un-quantized mean).
- Watchlist detail `change_pct` is un-quantized in committed source (27-digit value observed) — a real, undeployed-but-present defect, not only a stale-server artifact.

### 1.5 Production-readiness assessment

**Not production-ready as currently running**, because the live process and DB do not reflect the committed fixes. **The committed codebase is close to production-ready**: deploy (server restart) + migrate (`alembic upgrade head`) + a data-ingestion refresh would resolve the deployable findings; the residual items are the sector-data ingest (documented), `/research/contribution` performance/precision, and the watchlist `change_pct` precision.

---

## 2. Audit Methodology

### 2.1 What was inspected

- Full source tree: backend (interface/application/domain/infrastructure) and frontend (web app routes, components, libs).
- Architecture docs, strategy configs, prior audit findings, and backlog for context.
- Database schema, row counts, indexes, corporate actions, screening-run distribution, sector nulls, and duplicate checks via `docker exec momentum25-db-1 psql` (read-only `SELECT` only).
- Running API responses, latencies, and schemas via `curl` against `http://localhost:8000/api/v1`.

### 2.2 What was executed

- All read-only GET endpoints: health (5), stocks (5), securities/ohlcv, indices, market context, rankings, runs/latest, strategies, watchlist (2), validation (scorecard/alpha/rules/engines/historical/dashboard), research (evaluate/compare/strategies/contribution).
- Static analysis against **committed** source: `ruff check src tests`, `mypy src`, `lint-imports`, `npx tsc --noEmit`, `npm run lint`, `npm run build`.
- Backend test suite against `momentum25_test` (the conftest `_require_test_database` guard refused anything else; the dev DB `momentum25` was never pointed at).

### 2.3 What could NOT be executed (and why)

- **Performance fixes requiring migration 0013** (`ix_ohlcv_daily_date`, etc.) could not be verified live because the audit forbids running migrations; the running DB is at `0012`.
- **Source-side perf fixes for `/live` and `/validation/dashboard`** could not be verified live because the running server predates the fix commit and restarting it is an operational action excluded by the read-only mandate.
- **Mutating endpoints** were not exercised: `POST /watchlist/{symbol}`, `DELETE /watchlist/{symbol}`, `POST /runs/execute`, `POST /research/*` (historical screen, determinism verify, experiment, corporate-actions refresh), `POST /stocks/{symbol}/chart-patterns`. `chart-patterns` is stateless (no commit/session/save in its use case) but it is a POST, so it was not invoked.
- **Interactive browser behavior** (focus, hover, chart drawing, keyboard sort/paginate, SR navigation) was not exercised; only server-rendered HTML shells were fetched with `curl`. Client-only states are therefore NOT VERIFIABLE here.

### 2.4 Environment

- API: local uvicorn, `:8000`, started 10:20 IST, no `--reload`.
- Web: Next.js, `:3000`.
- DB: Docker `momentum25-db-1`, port `55432`, database `momentum25` (dev) + `momentum25_test` (tests).
- Redis: `momentum25-redis-1`, `:6379`.
- Date: 2026-08-15 (Saturday).

---

## 3. Coverage Matrix

| # | Feature | Code | API | Browser | Data | Tests | Perf | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Screening / rankings | Yes | Exercised | Shell only | Inspected | Pass | Good | Working |
| 2 | Stock lookup (securities search) | Yes | Exercised | Shell only | Inspected | Pass | Good | Working |
| 3 | Stock detail `/stocks/{symbol}` | Yes | Exercised | Shell only | Inspected | Pass | Good | Working |
| 4 | Momentum analysis (TT, RS, Volume, Pattern, Setup) | Yes | Exercised | n/a | Inspected | Pass | Good | Working |
| 5 | Technical indicators (RSI, MACD, ADX, ATR) series | Yes | Exercised | n/a | Inspected | Pass | Good | Working |
| 6 | Volume & accumulation | Yes | Exercised | n/a | Inspected | Pass | Good | Working |
| 7 | Chart patterns (stateless POST) | Yes | Not invoked (POST) | n/a | n/a | Pass | n/a | Not verifiable (verb) |
| 8 | Elliott Wave | Yes | Exercised | Shell only | n/a | Pass | Good | Working, isolated |
| 9 | Stop-loss (risk-only) | Yes | Exercised | n/a | n/a | Pass | Good | Working, risk-only |
| 10 | Watchlist (GET) | Yes | Exercised | Shell only | Inspected | Pass | Good | Working; precision defect |
| 11 | Market context | Yes | Exercised | Shell only | Inspected | Pass | Slow (no index) | Partial |
| 12 | Charting / drawing tools | Yes | n/a | Not interactive | n/a | None | n/a | Not verifiable (interactive) |
| 13 | Strategies config | Yes | Exercised | Shell only | Inspected | Pass | Good | Working |
| 14 | Validation (scorecard/alpha/rules/engines/historical/dashboard) | Yes | Exercised | Shell only | Inspected | Pass | Dashboard 44s slow | Partial |
| 15 | Research (evaluate/compare/contribution) | Yes | Exercised | Shell only | n/a | Pass | Contribution 28s | Partial |
| 16 | Health / operations | Yes | Exercised | Banner | Inspected | Pass | Good | Working; stale data |
| 17 | Learn (static pages) | Yes | n/a | Shell only | n/a | n/a | Good | Working |
| 18 | Responsive / mobile | Yes | n/a | Not interactive | n/a | n/a | n/a | Not verifiable (interactive) |
| 19 | Accessibility | Yes | n/a | Not interactive | n/a | n/a | n/a | Not verifiable (interactive) |
| 20 | Data integrity | Yes | n/a | n/a | Read-only | Pass | n/a | Mostly good; sectors empty |
| 21 | Corporate actions | Yes | n/a | n/a | Read-only | Pass | n/a | Adjustment correct |
| 22 | Architecture (hexagonal) | Yes | n/a | n/a | n/a | Pass (lint-imports) | n/a | Clean |
| 23 | Documentation | Yes | n/a | n/a | n/a | n/a | n/a | README current; minor drift |

---

## 4. Detailed Feature Findings

### 4.1 Screening / rankings — Working

- **API:** `GET /api/v1/runs/latest` → run 12, `COMPLETED`, `data_version=2026-08-07`, 218 passed / 1059 failed / 552 skipped / 2882 evaluated, duration 32.2 s (curl).
- `GET /api/v1/rankings/runs/12?limit=5` → ranked items with `momentum_score`, `buy_setup_score`, `rs_rating`, and a compact `explanation` block (checklist, risk_rating, volume_quality, breakout_quality, pattern, rank_change). Top rank: COMSYN, score 68.7007, RS 94.
- **Determinism:** `screening_orchestrator.py` and `screening.py` import no `elliott`/`wave`/`swing_target`/`stop_loss`/`chart_pattern` modules (grep, 0 hits) — Rankings are computed only from the configured engines.
- **Production strategy:** `docs/architecture/strategies/minervini_trend_template.json` v3 — TT 3.0, RS 2.0, Volume 1.0, Pattern 1.0, Breakout 1.5, Momentum Quality 1.0, Risk 0.5, Fundamental 0.0 (disabled); momentum + buy_setup weight maps present.
- **Data:** `screening_runs` 136 rows (135 COMPLETED, 1 FAILED); `data_version` distribution: historical 131, live 5. `screening_results` 218,864; `rule_results` 5,208,302.
- Verified working. No defect.

### 4.2 Stock lookup — Working

- `GET /api/v1/securities?...` routes through `GetSecurityOHLCV` / `SearchSecurities` (per audit plan; symbol normalization handles `reliance` → `RELIANCE`).
- `GET /api/v1/securities/RELIANCE/ohlcv` → 200 in 0.012 s; bars from 2024-07-30.
- **Note:** the audit plan lists `/stocks/{symbol}/ohlcv`; that exact path returns 404 (`{"detail":"Not Found"}`). OHLCV lives at `/securities/{symbol}/ohlcv`, which the README documents correctly. This is plan-vs-impl drift, not a defect — the README path is the source of truth.

### 4.3 Stock detail — Working

- `GET /api/v1/stocks/COMSYN` → 200 in 0.034 s; returns `StockExplanation` with `momentum_score`, `buy_setup_score`, `composite_score`, `rank`, `percentile`, `rule_explanations` (rule_id, engine_name, passed, explanation, threshold, actual_value, contribution, weight), `engine_explanations`, `hard_filter_failures`, `overall_rationale`, `overall_passed`.
- The prior audit's F6 noted the router returns the domain dataclass rather than a DTO; the b9de0a1 verdict deliberately kept the domain `response_model` on `/stocks/{symbol}` (the proposed `StockExplanationDTO` referenced fields that do not exist) and instead gave `/history` a real DTO. Verified in `routers/stocks.py` source shape. Accepted as documented design choice.

### 4.4 Momentum analysis — Working

- The `explanation` payload on rankings and `/stocks/{symbol}` covers Trend Template, Relative Strength, Volume, Pattern, and Buy Setup Quality, plus per-rule pass/fail and contribution. Verified on COMSYN (rank 1). No methodology concern observed.

### 4.5 Technical indicators — Working

- `GET /api/v1/stocks/COMSYN/indicators/series` → 200 in 0.010 s; `bars[]` with `rsi14`, `atr14`, `adx14`, `macd_line`, `macd_signal`, `macd_histogram`. Early dates are `null` (indicator warmup) — expected, not a defect.

### 4.6 Volume & accumulation — Working

- Volume quality (`"High"`) and breakout quality are part of the ranking `explanation`. Engine `volume_accumulation` is configured at weight 1.0.

### 4.7 Chart patterns — Not verifiable (verb)

- `POST /api/v1/stocks/{symbol}/chart-patterns` is a stateless detection endpoint: `chart_patterns.py` use case has no `commit`/`add`/`save`/`session`/`repo` references. Not invoked because it is a POST. Marked NOT VERIFIABLE under the read-only rule, not FAIL.

### 4.8 Elliott Wave — Working, isolated (see §6)

- `GET /api/v1/stocks/RELIANCE/elliott-wave` → 200 in 0.064 s; `pivots[]`, 3 `candidates` (`triangle`/`flat`/`diagonal`), each with `pattern`, `family`, `variant`, `direction`, `degree`, `labels`, `rules_applied`, `allowances`, `guideline_checks`, `personality`, `price_relationships`, `time_relationships`, `labelling_confidence`, `confidence_components`, `is_current`, `projection`, `subdivisions`. Two candidates carry a `projection` completion zone (`low`/`high`/`basis`). Retained and functioning.
- UI route `/stock/RELIANCE/elliott-wave` renders 200 (16.6 KB shell).

### 4.9 Stop-loss — Working, risk-only (see §7)

- `/live` returns `suggested_stop` and `trailing_stop`, each `{level, method}` only. RELIANCE: `{"level":"1286.9222","method":"2xATR"}` and `{"level":"1274.0833","method":"3xATR-chandelier(22)"}`; COMSYN: `194.0720` / `181.8630`. No target/reward/R-multiple fields.

### 4.10 Watchlist — Working; precision defect

- `GET /api/v1/watchlist` → `{"symbols":["TCS"]}` in 0.011 s.
- `GET /api/v1/watchlist/detail` → 200 in 0.10 s; TCS is `in_latest_run: true`, `momentum_score 53.5341`, `rs_rating 29`, `pct_below_high_52w 26.7851%`, `close 2452.70`.
- **Defect (see N3):** `change_pct` = `"3.358617783396544458491361146"` (27 significant digits). Source `watchlist.py:236` computes `change_pct = ((close - prev) / prev * 100)` with no `quantize` — present in committed code.
- No N+1 observed: `watchlist/detail` with one in-run symbol completed in 0.10 s.

### 4.11 Market context — Partial

- `GET /api/v1/market/context` → 200 in **1.54 s**; `breadth` populated (evaluated 2795, pct_above_sma50 62.71%, new 52w highs 124 / lows 14). `sectors: []` with `sectors_unavailable_reason: "no_sector_classification"`.
- `securities`: 3235 rows, `count(sector)=0`, `null_sector=3235`. Empty sectors is a documented known limitation (README "Known limitations"). Not a defect.
- The 1.54 s latency is the F4 perf half: the running DB has only the `(security_id, date)` PK index on `ohlcv_daily`; the committed `ix_ohlcv_daily_date` (migration 0013) is not applied. See F4.

### 4.12 Charting / drawing — Not verifiable (interactive)

- `PriceChart`, `TechnicalWorkbench`, `chart-drawings.ts`, `chart-preferences.ts` exist and import cleanly; the build succeeds. Drawing/interaction is client-only and was not exercised interactively.

### 4.13 Strategies — Working

- `GET /api/v1/strategies` → 7 strategies (ids 2–8): benchmarks A–E, `experimental_rs80`, and `minervini_trend_template` v3 (the only `kind: production`). `GET /api/v1/strategies/minervini_trend_template` resolves the detail. The audit plan's mention of "13 strategies" predates this state; 7 is current and intentional (research program retired several variants).

### 4.14 Validation — Partial

- `GET /api/v1/validation/scorecard/minervini_trend_template` → 200 in 7.9 s (slow on running server); full metrics (`cagr 0.2484`, `annual_return 0.4459`, `sharpe`, `sortino`, `max_drawdown`, etc.) with `measurability` block. Forward returns are now mature: `forward_returns` has 1,186,112 rows, so metrics are measurable (`measurability` not "not-measurable").
- `GET /api/v1/validation/rules/...` → 14.0 s, 100 runs analyzed; **`risk_rr` rule present with engine_id `risk`, pass_count 2471/2500**. Verified in source that `risk_rr` is downside-only (no reward term) — see §7.
- `GET /api/v1/validation/engines/...` → 14.7 s.
- `GET /api/v1/validation/alpha/...` → 7.1 s; `measurability: {forward_returns_available: true, reason: null}`.
- `GET /api/v1/validation/historical/...` → 0.25 s.
- `POST /api/v1/validation/dashboard` → 200 in **43.8 s** (running server). Aggregates `scorecard`, `alpha_analysis`, `rule_effectiveness`, `engine_effectiveness`, `historical_validation`, `ranking_stability`, FPR, FNR. This is the F3 finding, fixed in committed source but not deployed. See F3.

### 4.15 Research — Partial

- `GET /api/v1/research/evaluate/minervini_trend_template?max_runs=5` → 200 in 0.29 s; `run_count 3`, performance block, `measurability` (committed source has `_research_measurability`).
- `GET /api/v1/research/compare/strategies?strategy_a=...&strategy_b=...` requires `strategy_a`/`strategy_b` (422 if `strategies=` is used). With correct params → 200 in 2.23 s; `total_comparisons 0`, `comparisons []`. The committed source includes a `measurability` block (`no_common_run_dates`); the running server's response omitted it (stale code). See F8.
- `GET /api/v1/research/contribution/minervini_trend_template` → 200 in **28.5 s**; `avg_importance: "0.1103333333333333333333333333"` (28 digits). See F10 and N-contribution.

### 4.16 Health / operations — Working; stale data

- `/health` `ok`, `/health/live` `ok` (uptime 5430 s), `/health/ready` `ok`, `/health/startup` `ok` (7 strategies, 8 engines), `/health/data-freshness` STALE (`latest_bar_date 2026-08-07`, `sessions_missed 5`, `next_session 2026-08-17`).
- `/api/v1/metrics` → 200, `content-type: text/plain` (76 KB, Prometheus format) — expected.

### 4.17 Learn — Working

- 6 static `/learn/*` routes (faq, scoring-guide, rule-guide, momentum25-methodology, minervini-methodology, momentum-investing) prerender in the build.

### 4.18 Responsive / mobile / accessibility — Not verifiable (interactive)

- Build prerenders pages; responsive CSS and accessibility attributes exist in components. Interactive focus/keyboard/SR checks were not exercised. The b9de0a1 F17 verdict added `aria-label` to pagination and `tabIndex`/`onKeyDown`/`aria-sort` on sortable headers; these are present in the built client bundle per the verdict. Could not independently confirm behavior without a browser.

---

## 5. Defect Register

| ID | Sev | Category | Feature | Confidence | Status |
|---|---|---|---|---|---|
| E1 | P0 | Data Integrity / Ops | Health / freshness | High | Confirmed (operational, documented) |
| E2 | P0 | Performance | `/stocks/{symbol}/live` | High | Confirmed live; fixed in committed code, not deployed |
| E3 | P0 | Performance | `/validation/dashboard` | High | Confirmed live; fixed in committed code, not deployed |
| E4 | P1 | Performance / Data | `/market/context` + index migration | High | Perf confirmed live; index fix committed, NOT migrated |
| E5 | P1 | Performance | `/research/contribution` | High | Confirmed live; not fully addressed |
| E6 | P1 | Deployment / Ops | Stale running server vs HEAD | High | Confirmed |
| E7 | P1 | Deployment / Ops | Pending migration 0013 | High | Confirmed |
| E8 | P2 | Data Integrity / Functional | `/stocks/{symbol}/history` duplicates | High | Confirmed live; fixed in committed code, not deployed |
| E9 | P2 | UX / Accuracy | Decimal precision (contribution + watchlist) | High | Confirmed; partly fixed in committed code, watchlist `change_pct` still unfixed |
| E10 | P2 | UX / Functional | `/research/compare/strategies` measurability (live) | High | Confirmed live; fixed in committed code, not deployed |
| E11 | P2 | Architecture | Production risk engine imports research constants | High | Confirmed in source (harmless constants only) |
| E12 | P3 | UX | Ambiguous placeholders (`—`/`N/A`) lack "why" | Medium | Confirmed in design; partial F21 note |
| E13 | P3 | Accessibility | Chart canvas has no accessible alternative | Medium | Inferred from `lightweight-charts` usage; not interactive-verified |
| E14 | P3 | Documentation | Audit-plan endpoint `/stocks/{symbol}/ohlcv` not implemented | High | Confirmed; equivalent at `/securities/{symbol}/ohlcv` |
| E15 | P3 | Documentation | `screening_runs.status` has no CHECK constraint | High | Confirmed; fix is in pending migration 0013 |
| E16 | P3 | Methodology / Research | Browser-computed chart signal markers on analysis page | High | Confirmed by source; intended research surface, isolated |

### 5.1 E1 — Market data is stale (P0)

- **Category:** Data Integrity / Operational. **Confidence:** High.
- **Evidence:** `GET /api/v1/health/data-freshness` → `latest_bar_date 2026-08-07`, `as_of 2026-08-15`, `sessions_missed 5`, `classification STALE`, `next_session 2026-08-17`.
- **Expected:** Latest bar within one session on a trading day.
- **Actual:** Five sessions missed; all rankings/ranks/explanations are based on 2026-08-07.
- **Impact:** Every score, rank, stop-loss, and Elliott Wave projection describes stale data. Safe use is blocked until ingestion runs.
- **Type:** Operational/data-freshness. Documented as a known limitation in README and the b9de0a1 verdict (F1 OUT-OF-SCOPE). Remains a P0 risk for any live decision.

### 5.2 E2 — `/stocks/{symbol}/live` is slow until redeploy (P0)

- **Category:** Performance. **Confidence:** High.
- **Evidence (live):** `GET /stocks/RELIANCE/live` → 200 in **10.13 s**; `GET /stocks/COMSYN/live` → 200 in **8.92 s**.
- **Committed fix (HEAD):** `application/use_cases/stocks.py` wires `resolve_universe_rs_ratings(..., self._rs_rating_cache)` (the shared `RedisRsRatingCache` already used by watchlist). Verified present in source (lines 16, 533–534).
- **Expected:** Single-stock live lookup sub-second warm.
- **Actual (running server):** ~8.5–10 s because old code recomputes universe RS per request.
- **Impact:** Stock-detail and analysis pages feel broken during load; the dev server predates the fix.
- **Type:** Performance; source-fixed but NOT deployed. A restart is required to make the cache live.

### 5.3 E3 — `/validation/dashboard` is unusably slow until redeploy (P0)

- **Category:** Performance. **Confidence:** High.
- **Evidence (live):** `POST /api/v1/validation/dashboard` → 200 in **43.82 s**. Response aggregates scorecard, alpha, rule effectiveness, engine effectiveness, historical validation, ranking stability, FPR, FNR.
- **Committed fix (HEAD):** `use_cases/validation.py` rewritten (251-line diff) to use `get_rule_results_bulk`, `get_forward_return_by_security`, `horizon_days` filter, and column projection; b9de0a1 reports 41.6 s → 6.1 s A/B-proved.
- **Expected:** Dashboard loads in a few seconds.
- **Actual (running server):** 43.8 s (old ORM-hydration path).
- **Type:** Performance; source-fixed but NOT deployed.

### 5.4 E4 — `/market/context` slow and performance index not migrated (P1)

- **Category:** Performance / Data. **Confidence:** High.
- **Evidence (live):** `GET /api/v1/market/context` → 200 in **1.54 s**. `pg_indexes` on `ohlcv_daily` shows only `ohlcv_daily_pkey` (`security_id, date`); no `ix_ohlcv_daily_date`.
- **Committed fix (HEAD):** migration `0013_filter_column_indexes` adds `ix_ohlcv_daily_date` (and benchmark/corporate-actions/screening-results/forward-returns indexes + `ck_screening_runs_status`). `alembic_version` is `0012_drop_legacy_ohlcv_bak` → migration NOT applied.
- **Expected:** Market context near-instant with a date-leading index.
- **Actual:** Date-range scan over ~3.07 M `ohlcv_daily` rows uses only the PK; 1.54 s.
- **Impact:** Market page latency; the index half of F4 cannot take effect until `alembic upgrade head` (forbidden here).
- **Type:** Performance; index committed but NOT migrated. The sector half is a documented known limitation (no sector classification).

### 5.5 E5 — `/research/contribution` is slow and imprecise (P1)

- **Category:** Performance / UX. **Confidence:** High.
- **Evidence (live):** `GET /api/v1/research/contribution/minervini_trend_template` → 200 in **28.5 s**; `engine_stats[].avg_importance = "0.1103333333333333333333333333"` (28 digits). `run_count 4`, `security_count 1396`, `date_range "2026-08-07 to 2026-08-09"`.
- **Committed state:** The b9de0a1 verdict does not list `contribution` perf as fixed; the use case aggregates over 5.2 M `rule_results` across all matching runs. The `avg_importance` is an un-quantized mean computed in `routers/research.py` (`sum(...) / max(len(...),1)`).
- **Expected:** Contribution completes in a few seconds with fixed precision.
- **Actual:** 28.5 s with 28-digit Decimals.
- **Type:** Performance + UX; partially unfixed in committed code.

### 5.6 E6 — Running dev server is stale relative to HEAD (P1)

- **Category:** Deployment / Operational. **Confidence:** High.
- **Evidence:** `ps` shows uvicorn started 10:20 IST without `--reload`; `/health/live` `started_at 2026-08-15T04:50:07Z`; HEAD `b9de0a1` authored `2026-08-15 11:47:44 +0530` (after). The live process therefore runs pre-F2/F3/F5/F8/F10 bytecode.
- **Expected:** The running server reflects HEAD.
- **Actual:** It does not; F2/F3/F5/F8/F10 fixes are invisible live until restart.
- **Type:** Deployment hygiene. Not a code defect; reconciles the "fixed in source but broken live" paradox across E2/E3/E8/E10.

### 5.7 E7 — Database one migration behind HEAD (P1)

- **Category:** Deployment / Operational. **Confidence:** High.
- **Evidence:** `alembic_version = 0012_drop_legacy_ohlcv_bak`; repo has `0013_filter_column_indexes.py`. `pg_indexes` confirms none of the 0013 indexes exist; `screening_runs.status` has no CHECK constraint (verified by absence in `pg_indexes`/catalog).
- **Expected:** DB at HEAD migration.
- **Actual:** One migration pending; performance indexes and the status CHECK absent.
- **Type:** Deployment hygiene. Forbidden to remediate (`alembic upgrade`) under read-only rules.

### 5.8 E8 — `/stocks/{symbol}/history` duplicates points until redeploy (P2)

- **Category:** Data Integrity / Functional. **Confidence:** High.
- **Evidence (live):** `GET /stocks/COMSYN/history?limit=20` returns three rows for `2026-08-09` (rank 1, 2, 1) and two for `2026-08-07` (rank 3, 1).
- **Committed fix (HEAD):** `screening_run.py:465 score_history` uses `DISTINCT ON (run_date)` + `_LIVE_RUN_PREDICATES` (excludes `historical:%`, `:research:`, `:icv2:`) — verified in source.
- **Expected:** One point per live run_date (newest run).
- **Actual (running server):** Multiple completed runs per date all returned (old code).
- **Type:** Data-integrity; source-fixed but NOT deployed.

### 5.9 E9 — Decimal precision leaks (P2)

- **Category:** UX / Accuracy. **Confidence:** High.
- **Evidence:**
  - `/research/contribution` `avg_importance` = `0.1103333333333333333333333333` (28 digits).
  - `/watchlist/detail` `change_pct` = `3.358617783396544458491361146` (27 digits).
- **Committed state:** F10 quantized `_screening_metrics` means in validation (verified verdict: 28-digit → `30.1920`). But `routers/research.py:367` computes `avg_importance` as an un-quantized `sum(...) / max(len(...),1)`, and `use_cases/watchlist.py:236` computes `change_pct` with no `quantize`. Both remain in committed code.
- **Expected:** Four-decimal precision matching the rest of the API.
- **Actual:** Up to 28-digit Decimals in two places.
- **Type:** UX; partly fixed (validation), partly still present (contribution, watchlist).

### 5.10 E10 — `/research/compare/strategies` measurability missing until redeploy (P2)

- **Category:** UX / Functional. **Confidence:** High.
- **Evidence (live):** `GET /research/compare/strategies?strategy_a=...&strategy_b=...` response keys: `strategy_a_name, strategy_b_name, total_comparisons, agreement_count, agreement_rate, a_wins, b_wins, comparisons, rule_level_diffs` — **no `measurability`**. `total_comparisons 0`.
- **Committed fix (HEAD):** `routers/research.py:440` adds `measurability=_research_measurability(bool(result.score_deltas), "no_common_run_dates")`; `evaluate` gets it at `:315`.
- **Expected:** Empty results carry a measurability reason.
- **Actual (running server):** Omitted; users cannot tell "no common run dates" from "zero effect".
- **Type:** UX; source-fixed but NOT deployed.

### 5.11 E11 — Production risk engine imports research-module constants (P2)

- **Category:** Architecture. **Confidence:** High.
- **Evidence:** `domain/engines/risk.py:22` — `from momentum25.domain.research.swing_targets import DEFAULT_ATR_STOP_MULTIPLE, DEFAULT_FALLBACK_RISK_PCT`. These are constants only; `risk_rr` is downside-only (verified, §7).
- **Expected:** Production domain engines depend only on domain core; cross-package reach into a research module is a layering smell.
- **Actual:** A production engine reads from a `research/` module.
- **Impact:** Harmless today (constants) but creates a reverse dependency edge from production to research; a future change to `swing_targets` could silently move the risk rule.
- **Type:** Architecture smell (not a functional defect).

### 5.12 E12 — Ambiguous placeholders lack "why" (P3)

- **Category:** UX. **Confidence:** Medium.
- **Evidence:** UI copy uses `—` and `N/A` for missing values (`format.ts`, component copy). Whether "not qualified", "no data", or "stale" is not disambiguated.
- **Type:** UX; acknowledged in the prior audit's F21 note.

### 5.13 E13 — Chart canvas has no accessible alternative (P3)

- **Category:** Accessibility. **Confidence:** Medium.
- **Evidence:** `PriceChart` uses `lightweight-charts` (canvas). The b9de0a1 F17 verdict explicitly **skipped** the chart alt-data table as instructed. Keyboard/screen-reader access to chart data is therefore absent.
- **Type:** Accessibility; deferred per prior product decision.

### 5.14 E14 — Audit-plan endpoint `/stocks/{symbol}/ohlcv` not implemented (P3)

- **Category:** Documentation. **Confidence:** High.
- **Evidence:** `GET /api/v1/stocks/RELIANCE/ohlcv` → 404 `{"detail":"Not Found"}`. OpenAPI lists 42 paths; OHLCV is at `/api/v1/securities/{symbol}/ohlcv`.
- **Type:** Audit-plan vs implementation drift; README documents the real path. Not a defect.

### 5.15 E15 — `screening_runs.status` has no CHECK constraint (P3)

- **Category:** Data Integrity. **Confidence:** High.
- **Evidence:** No CHECK constraint on `screening_runs.status` in the running DB.
- **Committed fix (HEAD):** migration `0013` adds `ck_screening_runs_status` (`status IN ('PENDING','RUNNING','COMPLETED','FAILED')`).
- **Type:** Data-integrity; committed but NOT migrated (same blocker as E7).

### 5.16 E16 — Browser-computed chart signal markers on the analysis page (P3, methodology/research)

- **Category:** Methodology / Research. **Confidence:** High.
- **Evidence:** `web/src/app/stock/[symbol]/analysis/page.tsx:476` — chart copy: "Signal markers: ▲ long, ▼ short, × exit.", computed in-browser from fetched bars. Page docstring (lines 5–13) states it is presentation-only and feeds nothing back to score/rank/screen/stop-loss.
- **Type:** Research overlay, intentionally isolated (F18 NOTE-ONLY). Documented, not a defect.

---

## 6. Elliott Wave Audit

### 6.1 API

`GET /api/v1/stocks/{symbol}/elliott-wave` — 200 in 0.064 s. Payload:

- `symbol`, `as_of`, `threshold_pct` (5), `top_degree_threshold_pct` (5), `bars_analyzed` (500).
- `pivots[]` — `{bar_date, price, kind}` with H/L alternation.
- `candidates[]` (3) — each with `pattern`, `family`, `variant`, `direction`, `degree`, `labels`, `current_position`, `rules_applied`, `allowances`, `guideline_checks`, `personality`, `price_relationships`, `time_relationships`, `labelling_confidence`, `confidence_components`, `is_current`, `projection`, `subdivisions`.
- **Projected completion zone** (retained): two candidates carry `projection: {low, high, basis}`. Example: `{"low":"1318.60","high":"1351.17","basis":"wave C: 1.0-1.618 of wave A from wave B"}`.
- `ranking_method` (admissibility-then-scoring: currency 25 / structural completeness 20 / price Fib 20 / personality 15 / time Fib 10 / cleanliness 10). `ranking_rationale[]` explains the ordering. `notes[]` flags degree limitations.

### 6.2 Wave count, pivots, degree, projection, completion zone

- Wave count: heuristic pattern fits over 500 bars; 3 candidate structures (triangle/flat/diagonal) with rule admissibility truncation to the longest rule-satisfying prefix.
- Pivots: H/L alternation with `threshold_pct` minimum separation.
- Degree: derived; `notes` reports when finer-degree labeling is not supportable.
- Fibonacci relationships: `price_relationships` and `time_relationships` per candidate; `projection.basis` cites the Fib relation (e.g., 0.382–0.618 retracement, 1.0–1.618 extension).
- **Projected completion zone is retained and functioning** — confirmed live.

### 6.3 UI

- Dedicated route `/stock/[symbol]/elliott-wave` renders 200 (16.6 KB). The analysis page (`/stock/[symbol]/analysis`) integrates an Elliott Wave mode that swaps annotation props on the shared `PriceChart` shell (`useElliottWaveChart`, `elliott-wave-panels`).

### 6.4 Chart overlay

- `PriceChart` accepts `ChartMarker`/`ChartOverlayLine`/`PaneDef` props; Elliott candidates annotate pivots and the completion zone on the same shell used for indicators and patterns. Loading/empty/error states handled in the shell hook.

### 6.5 Performance

- 0.064 s — good.

### 6.6 Separation from Momentum25 (critical guardrail)

Verified in source (grep both directions):

- `domain/engines/`, `domain/scoring/`, `domain/strategy/`, `domain/rules/`, `application/use_cases/screening*.py`, `application/use_cases/stocks.py` — **0 imports of `elliott`**.
- `domain/analytics/elliott_wave.py` and `domain/analytics/elliott/*.py` — **0 imports of `engines`/`scoring`/`strategy`/`rules`**.
- Import-linter: "Domain is pure" + "Dependencies point inward" — both KEPT.

**Conclusion:** Elliott Wave is a separate research screen. It does not influence momentum score, rank, screening, gates, trend template, RS, volume, pattern, buy-setup quality, or stop-loss. The projected completion zone is intentionally retained as a forward-looking Elliott-Wave analytical projection. It is NOT a Momentum25 target.

### 6.7 Methodology questions (not defects)

- Ranking weights are editorial (documented in `ranking.py` and the `ranking_method` string).
- Wave counts are heuristic pattern fits, not probabilities.
- No change recommended.

---

## 7. Stop-Loss Audit

### 7.1 API

Stop-loss is returned only inside `/api/v1/stocks/{symbol}/live`. Fields: `suggested_stop` and `trailing_stop`, each `{level, method}`.

- RELIANCE: `{"level":"1286.9222","method":"2xATR"}`, trailing `{"level":"1274.0833","method":"3xATR-chandelier(22)"}`.
- COMSYN: `194.0720` / `181.8630`.

No `target`, `take_profit`, `reward`, `r_multiple`, or `risk_reward` field in the live payload.

### 7.2 Domain

- `domain/research/stop_loss.py` — module docstring: "deliberately isolated from `swing_targets.py` — it makes no reward/target claim and carries no R-multiple or RR ratio." Two functions: `suggest_stop_loss` and `suggest_chandelier_stop`; both documented as downside caps with "no target, no reward estimate, no R-multiple."
- `domain/engines/risk.py::_eval_risk_rr` — measures only the risk leg: `risk_amount = atr14 * DEFAULT_ATR_STOP_MULTIPLE` (or `entry * DEFAULT_FALLBACK_RISK_PCT`), `risk_pct = (risk_amount/entry)*100`, passes when `<= max_risk_pct`. Docstring explicitly states the prior risk-*reward* ratio was removed in the 2026-08-09 audit and only the risk leg remains. **No reward term.**

### 7.3 Risk-only behavior

- Stop-loss output: downside level + method only. No profit target, take-profit, price objective, R-multiple, or risk/reward anywhere in the stop-loss surfaces.

### 7.4 Target / reward leakage

- **None into core Momentum25.** The only target/R:R surface is the analysis page "Targets and risk / reward" card (`web/src/app/stock/[symbol]/analysis/page.tsx:598`), which the page docstring declares "presentation only ... no number on this page feeds the composite score, the ranking, or the trend template." The page calls only read-only GETs (`getLiveStockAnalysis`, `getStockExplanation`, `getIndexCloses`) — no target data is POSTed to any core endpoint. Targets/R:R are browser-computed research annotations and remain isolated.
- The legacy `risk_rr` rule **name** persists, but the rule logic is downside-only. The name is a residual, not leakage.

### 7.5 One architectural note (E11)

`risk.py` imports two constants from `domain/research/swing_targets.py`. This is a layering smell (production engine → research module) but carries no reward/target semantics. See E11.

### 7.6 Tests

Stop-loss and risk-only behavior covered by the passing suite (598 passed).

**Verdict:** Stop-loss is risk-only. No leakage found.

---

## 8. Data Integrity Audit

### 8.1 Corporate actions

- `corporate_actions`: 25,864 rows; types: `other` 24,939 (dividends/demergers, `ratio NULL`), `split` 482, `bonus` 443. Date range 2011-01-06 → 2026-08-31.
- **RELIANCE bonus 2024-10-28 (ratio 0.5):** verified backward adjustment — `2024-10-25 close 2655.70 → adj_close 1327.85 (adj_factor 0.5)`; on ex-date `2024-10-28` raw close drops to 1334.35 with `adj_factor 1.0` (post-event bars need no backward adjustment). A 2019-10-01 bar also carries `adj_factor 0.5` — correct (it pre-dates only the 2024 bonus; the 2017 bonus affects bars before 2017, and RELIANCE `ohlcv_daily` starts 2019-10-01).
- **Uniqueness:** no duplicate `(security_id, ex_date, type)` (group-HAVING query returned 0 rows). Unique constraint enforced.
- **No mutations performed.** Adjustment correctness PASS.

### 8.2 Row counts

| Table | Rows |
|---|---|
| securities | 3,235 |
| ohlcv_daily | 3,076,892 |
| strategies | 7 |
| screening_runs | 136 (135 COMPLETED, 1 FAILED) |
| screening_results | 218,864 |
| rule_results | 5,208,302 |
| forward_returns | 1,186,112 |
| corporate_actions | 25,864 |
| watchlist_items | 1 (TCS) |
| universe_membership | 438,901 |
| benchmark_index_daily | 2,858 |
| legacy_ohlcv_daily | 6,343,469 |
| bse_legacy_ohlcv_daily | 5,779,288 |
| historical_universe | 0 |
| survivorship_gap_event | 9,902 |
| bse_scrip_junction | 6,386 |

### 8.3 Backup / snapshot tables (retain — valuable)

| Table | Value |
|---|---|
| `legacy_ohlcv_daily` (6.34 M) | NSE legacy archive for overlap reconciliation (research). README: re-running the legacy backfill re-adjusts these; the per-symbol refresh targets `ohlcv_daily` only. |
| `bse_legacy_ohlcv_daily` (5.78 M) | BSE pre-UDiFF archive. |
| `bse_scrip_junction` (6,386) | Learned BSE code-to-ISIN mapping. |
| `ohlcv_adj_snapshot_20260810`, `screening_results_snapshot_20260810`, `screening_results_snapshot_run12_20260810`, `screening_runs_snapshot_run12_20260810`, `corporate_actions_snapshot_20260810` | Pre-change backup snapshots. |

**Recommendation: retain all backup/legacy tables** — they are the only surviving copies of pre-change state for research reconciliation. Removal is an operator decision.

### 8.4 Index / constraint gaps (running DB at migration 0012)

Confirmed present: `ohlcv_daily_pkey`, `ix_screening_results_rank`, `ix_screening_runs_status`, `ix_screening_runs_strategy_id_run_date_data_version_config_has_key`, `corporate_actions_security_id_ex_date_type_key`.

Confirmed **absent** (committed in migration 0013, not applied):
- `ix_ohlcv_daily_date`
- `ix_benchmark_index_daily_date`
- `ix_corporate_actions_security_id`
- `ix_screening_results_security_id`
- `ix_forward_returns_security_id`
- `ck_screening_runs_status` CHECK constraint

`rule_results` and `universe_membership` carry only their (run_id-leading) PK indexes — the b9de0a1 verdict notes these are already PK-leading and intentionally not re-indexed.

### 8.5 Sectors

`securities`: 3235 rows, `count(sector) = 0` — all NULL. Documented known limitation ("No sector classification"); market-context sector panel empty by design.

### 8.6 Survivalship / historical universe

`survivorship_gap_event` 9,902 rows (membership recorded per run → no survivorship bias in backtests, per README). `historical_universe` 0 rows.

---

## 9. Performance Audit

Measured against the running dev server (stale code, DB at migration 0012). Timings are end-to-end `curl` total.

| Endpoint | Latency | Assessment |
|---|---|---|
| `GET /health` | 0.48 s | OK |
| `GET /health/ready` | 0.006 s | Good |
| `GET /health/data-freshness` | 0.30 s | Good |
| `GET /strategies` | 0.006 s | Good |
| `GET /runs` | 0.04 s | Good |
| `GET /runs/latest` | 0.03 s | Good |
| `GET /rankings/runs/12?limit=10` | 0.17 s | Good |
| `GET /stocks/COMSYN` | 0.034 s | Good |
| `GET /stocks/{symbol}/history` | 0.012 s | Good (content duplicates, not perf) |
| `GET /stocks/{symbol}/indicators/series` | 0.010 s | Good |
| `GET /securities/{symbol}/ohlcv` | 0.012 s | Good |
| `GET /indices/NIFTY500/closes` | 0.014 s | Good |
| `GET /stocks/{symbol}/elliott-wave` | 0.064 s | Good |
| `GET /watchlist` | 0.011 s | Good |
| `GET /watchlist/detail` | 0.10 s | Good |
| `GET /market/context` | **1.54 s** | Slow — missing `ix_ohlcv_daily_date` (E4) |
| `GET /stocks/RELIANCE/live` | **10.13 s** | Critical — universe RS per request (E2, source-fixed) |
| `GET /stocks/COMSYN/live` | **8.92 s** | Critical — same (E2) |
| `GET /research/evaluate/...` | 0.29 s | Good |
| `GET /research/compare/strategies` | 2.23 s | OK |
| `GET /research/contribution/...` | **28.5 s** | Critical — 5.2 M rule_results aggregation (E5) |
| `GET /validation/scorecard/...` | 7.9 s | Slow — uses historical runs (E3-class) |
| `GET /validation/rules/...` | 14.0 s | Slow |
| `GET /validation/engines/...` | 14.7 s | Slow |
| `GET /validation/alpha/...` | 7.1 s | Slow |
| `GET /validation/historical/...` | 0.25 s | Good |
| `POST /validation/dashboard` | **43.8 s** | Critical — ORM hydration of ~213 k rows × 4 uses (E3, source-fixed) |

Drivers:
- `/live`: per-request full-universe RS recomputation (source-fixed via Redis cache; not deployed).
- `/market/context`: `closes_between` date scan with no date-leading index (index committed in 0013; not migrated).
- `/validation/*`: ORM hydration of large `rule_results`/`screening_results` slices (source-fixed via bulk + column projection for dashboard; not deployed).
- `/research/contribution`: not covered by the F3 bulk optimization; still aggregating 5.2 M rows.

No optimization was performed (audit-only).

---

## 10. UX / Accessibility Audit

### 10.1 Working

- Loading, empty, and error states are implemented on all major routes (build succeeds; shells render 200).
- Dark mode and responsive layout present.
- Validation/research surfaces report `measurability` blocks (committed source) so "not measured" never reads as "zero".
- Freshness banner surfaces `STALE` classification on the dashboard.

### 10.2 Gaps

- **E12:** `—` and `N/A` placeholders do not explain *why* a value is missing (not-qualified vs no-data vs stale).
- **E13:** Chart canvas is mouse-only with no accessible alternative (alt table deferred per product decision).
- **E9:** Decimal precision leaks (27–28 digits) in watchlist `change_pct` and research `avg_importance`.
- Accessibility attributes added by the F17 verdict (pagination `aria-label`, sortable-header `tabIndex`/`onKeyDown`/`aria-sort`) exist in the built bundle but their interactive behavior could not be verified without a browser.

### 10.3 Interactive-only (NOT VERIFIABLE here)

Focus order, keyboard sort/paginate, screen-reader navigation, chart drawing, and mobile layout were not exercised. Marked NOT VERIFIABLE, not FAIL.

---

## 11. Architecture Audit

### 11.1 Clean (verified)

- Import-linter: "Clean architecture layering (dependencies point inward)" KEPT; "Domain is pure (no infrastructure/interface/application imports)" KEPT (2/2 contracts, 202 files, 509 deps).
- Engines registered through a strategy-agnostic registry; scoring, ranking, and explainability separated.
- I/O behind ports (repositories, market data, calendar, Redis).
- `mypy` strict: 0 issues / 218 files.

### 11.2 Concerns

- **E11:** `domain/engines/risk.py` imports constants from `domain/research/swing_targets.py` — a production engine reaches into a research module (harmless constants today; layering smell).
- Some frontend business logic lives in `lib/strategies.ts`/`lib/indicators/*` (browser-side signal presets, MA/MACD from fetched closes) — research overlays, isolated, but can diverge from backend canonical values (F18 NOTE-ONLY).
- `/stocks/{symbol}` returns the domain dataclass rather than a DTO; the b9de0a1 verdict documented this as deliberate (the proposed DTO referenced non-existent fields).

---

## 12. Test / Build Results

All run against committed source/HEAD; none modified.

| Check | Command | Result |
|---|---|---|
| Backend lint | `ruff check src tests` | **All checks passed** (was 129) |
| Backend types | `mypy src` | **Success: no issues in 218 files** (was 33) |
| Import-linter | `lint-imports` | **2 kept, 0 broken** |
| Backend tests | `pytest` (against `momentum25_test`) | **598 passed, 1 warning in 11.11 s** |
| Frontend types | `npx tsc --noEmit` | **Clean** |
| Frontend lint | `npm run lint` | **No ESLint warnings or errors** |
| Frontend build | `npm run build` | **Clean** — all routes prerender/dynamic; `/stock/[symbol]/analysis` 295 kB First Load (largest) |

Test coverage includes screening, watchlist, corporate actions, Elliott Wave, stop-loss, determinism, validation, API, and the F9/F13 regression tests added in b9de0a1. The 1 warning is a benign `starlette.testclient` deprecation (requests `httpx2`).

---

## 13. Documentation Audit

### 13.1 Current (good)

- `README.md` rewritten in b9de0a1 (F19) from verified facts: real routes, engines, pages, stack, and a **Known limitations** section covering data freshness, sector classification, legacy adjustment, corporate-action start date, and editorial thresholds. Matches implementation.
- Strategy configs in `docs/architecture/strategies/` are accurate and versioned (production v3).
- API terminology (`momentum_score`, `buy_setup_score`, `hard_filter_failures`, `measurability`) consistent across endpoints and UI.
- Core-vs-research separation documented and enforced in code.

### 13.2 Drift

- **E14:** the audit plan (`docs/2026-08-09-functional-audit-plan.md`) lists `/stocks/{symbol}/ohlcv`; this path is 404. The README correctly documents `/securities/{symbol}/ohlcv`. Plan-vs-impl drift, not a code defect.
- The audit plan states "13 strategies"; the live state is 7 (research program retired variants). Intentional.
- `domain/scoring/__init__.py` previously called implementations "placeholder"; b9de0a1 (F19) fixed this.

---

## 14. Methodology / Research Questions

These are intentional or unvalidated research choices, **not software defects**.

1. **Risk stop-distance ceiling.** `DEFAULT_MAX_RISK_PCT = 16%` is a consistency floor (2 × the 8% `risk_atr` cap), chosen for consistency, not walk-forward validation. Documented in `risk.py`.
2. **Pattern detector thresholds.** VCP, cup-with-handle, ascending-base, flat-base use fixed constants without documented calibration evidence. F9 (cup-handle index bug) is fixed in source; the constants remain editorial.
3. **Elliott Wave ranking weights.** Currency/structural/Fib/personality/time/cleanliness weights are editorial and documented.
4. **Forward-return tier thresholds.** `domain/research/forward_returns.py` uses fixed boundaries by design.
5. **Browser-side signal presets.** The dashboard "Signal" column and `StrategyPanel` presets produce long/short/exit annotations from raw bars; research overlays only (F18 NOTE-ONLY).
6. **Analysis-page targets/R:R.** Arithmetic on the bars on screen; presentation-only research illustration; isolated from the strategy. The underlying Phase 3/3b target methodology was closed FAILED (per backlog), which is why the stop-loss alone was shipped without reward.
7. **Elliott Wave projected completion zone.** Intentionally retained as a forward-looking analytical projection on the separate Elliott Wave research screen — **not** a Momentum25 target. No change recommended.

No methodology was changed during this audit.

---

## 15. Recommended Remediation Plan (NOT implemented)

### P0 — Critical

1. **Refresh market data** so the latest bar is current; confirm `/health/data-freshness` returns `FRESH` (E1 — operational).
2. **Deploy the committed fixes** (restart the dev API so the `/live` cache, validation bulk optimization, history dedup, and research measurability take effect) (E2, E3, E8, E10).

### P1 — High

3. **Apply migration 0013** (`alembic upgrade head`) to create the filter-column indexes and the `screening_runs.status` CHECK constraint (E4, E15).
4. **Optimize `/research/contribution`**: apply the same bulk/column-projection pattern used for the validation dashboard; pre-aggregate or materialize per (strategy, run) (E5).
5. **Quantize `avg_importance` and `change_pct`** to four decimals in the research router and watchlist use case (E9).
6. **Reconcile deployment hygiene**: run from a single source of truth (CI artifact or `--reload` dev workflow) so the live process matches HEAD (E6, E7).

### P2 — Medium

7. **Add a `measurability` block** is already in committed source — verify after deploy that `/research/compare/strategies` and `/research/evaluate` surface it (E10).
8. **Move the risk-engine constants** (`DEFAULT_ATR_STOP_MULTIPLE`, `DEFAULT_FALLBACK_RISK_PCT`) out of `domain/research/swing_targets.py` into the domain core to remove the production→research import edge (E11).

### P3 — Low

9. **Disambiguate placeholders** (`—`/`N/A`) with tooltips specifying not-qualified vs no-data vs stale (E12).
10. **Provide an accessible data table** for the price chart, or document the deferral explicitly (E13).
11. **Update the audit plan** to reference `/securities/{symbol}/ohlcv` instead of the non-existent `/stocks/{symbol}/ohlcv` (E14).

---

## 16. Final Assessment

### 16.1 What is verified working

- Core screening, ranking, and explainability for the production strategy (`minervini_trend_template` v3), run 12.
- Stock detail, history (perf), indicators series, OHLCV, index closes, and Elliott Wave — all fast and correct on the committed code paths exercised through the OS-level data.
- Elliott Wave analysis **including projected completion zones**, verified live and isolated from Momentum25.
- Stop-loss calculation and UI **risk-only**; no target/reward/R-multiple leakage into core.
- Corporate-action backward adjustment correctness (RELIANCE 2024 bonus verified).
- Watchlist read operations.
- Static analysis clean, tests pass (598), import-linter contracts kept, frontend build/lint/tsc clean against HEAD.
- Architecture: hexagonal layering enforced; engines strategy-agnostic.

### 16.2 What is broken (in the running environment)

- Data freshness STALE (5 sessions missed) — E1.
- `/stocks/{symbol}/live` ~8.5–10 s and `/validation/dashboard` ~44 s on the running server — E2, E3 (source-fixed, not deployed).
- `/market/context` 1.54 s — E4 (index committed, not migrated).
- `/stocks/{symbol}/history` duplicate points on the running server — E8 (source-fixed, not deployed).
- `/research/compare/strategies` lacks `measurability` on the running server — E10 (source-fixed, not deployed).

### 16.3 What is partially working

- Validation surfaces are measurable (forward returns present) but slow until the committed validation optimization is deployed, and the dashboard is unusable at 44 s — E3.
- `/research/contribution` returns data but at 28.5 s with 28-digit precision — E5, E9.
- Watchlist detail returns correct data but `change_pct` has 27-digit precision — E9.

### 16.4 What could not be verified

- Live behavior of all source-side perf/measurability fixes (server stale, forbidden to restart) — E2, E3, E8, E10.
- `ix_ohlcv_daily_date` and the other 0013 indexes (DB at 0012, forbidden to migrate) — E4, E15.
- Interactive browser behavior: focus, keyboard sort/paginate, screen-reader navigation, chart drawing, mobile layout — NOT VERIFIABLE without a browser.
- Mutating endpoints (watchlist POST/DELETE, runs/execute, research POSTs, chart-patterns POST) — not invoked under the read-only rule.

### 16.5 What requires engineering

- Data-ingestion refresh (E1).
- Deploy of committed fixes (server restart) + `alembic upgrade head` (E2, E3, E4, E8, E10, E15).
- `/research/contribution` performance + precision (E5, E9).
- Watchlist `change_pct` quantization (E9).
- Risk-engine constant relocation (E11).

### 16.6 What requires research

- The editorial thresholds listed in §14 (risk cap, pattern constants, Elliott weights, forward-return tiers) remain unvalidated by walk-forward evidence.
- Phase 3/3b target methodology is closed FAILED; targets/R:R remain a research illustration only.

### 16.7 What requires product decisions

- Whether to provide an accessible alternative for the price chart (E13).
- Whether to disambiguate ambiguous placeholders surface-wide (E12).

---

### Guardrail Confirmation

- **Elliott Wave projections are retained and functioning** (`/stocks/{symbol}/elliott-wave`, live, with `projection.low/high/basis`). Elliott Wave is fully isolated from Momentum25 score, rank, screening, gates, trend template, RS, volume, pattern, buy-setup quality, and stop-loss.
- **Stop-loss is risk-only** (`suggested_stop`/`trailing_stop` = `level` + `method` only; `stop_loss.py` and `risk_rr` carry no reward/target/R-multiple).
- **No unsupported target/reward logic is exposed in core Momentum25.** The only target/R:R surface is the analysis-page research card, which is presentation-only and isolated.
- **No unsupported Buy/Sell indicator signals are introduced in core Momentum25.** The only buy/sell-style markers are browser-computed signals on the research analysis page (F18 NOTE-ONLY). Card components explicitly state PASS/FAIL is "never a buy/sell verdict" and "no buy/sell call is derived from any pattern."
- **Corporate-action behavior was audited read-only** (no refreshes, no mutations; adjustment correctness verified on RELIANCE).
- **No application code, configuration, database data, or git state was modified.** The only file written is this audit report.