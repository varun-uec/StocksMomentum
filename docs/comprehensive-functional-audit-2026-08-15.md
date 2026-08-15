# Momentum25 India — Comprehensive Functional Audit

**Date:** 2026-08-15  
**Repository:** `/Users/varunagarwal/Downloads/Applications/StocksMomentum`  
**Auditor:** OpenCode (read-only)  
**Scope:** backend API, Next.js frontend, PostgreSQL data layer, architecture, tests, static analysis, documentation.

## How this audit was performed

- No source code, configuration, or database data was modified.
- Database access was read-only `SELECT`. The test database (`momentum25_test`) was used only for the existing pytest suite.
- The backend was started locally with `.venv/bin/uvicorn` against the existing Docker Compose PostgreSQL/Redis stack. No migrations or ingestion jobs were run.
- The frontend production server was started with `npm start` against the local API.
- Endpoints were exercised with `curl`. Page-level checks used `curl` against the running Next.js server (no interactive browser was available in this environment, so client-side-only states could not be fully exercised).
- Tests, lint, typecheck, build, and import-linter were run without modifying their configuration.

---

## Executive Summary

**Overall assessment: Not production ready.**

The core Momentum25 pipeline is implemented, deterministic, and well-tested. The production strategy (`minervini_trend_template` v3) runs successfully, produces rankings, and explains scores. Elliott Wave remains a properly isolated research screen with projected completion zones. Stop-loss output is risk-only and does not leak targets or risk/reward into the core product.

However, the platform cannot be considered production-ready today because:

1. **Market data is stale.** The latest bar is 2026-08-07; five trading sessions are missed as of 2026-08-15.
2. **Core user-facing endpoints are too slow.** `/stocks/{symbol}/live` takes ~8.5 s and `/validation/dashboard` takes ~40 s on warm hardware.
3. **Validation surfaces report "not measurable" for returns**, which is correct, but several research/validation endpoints return empty or misleading counts when forward returns are absent.
4. **Code-quality gates are red.** `ruff` reports 129 issues and `mypy` reports 33 issues.
5. **Documentation drift.** The README still claims the project is a greenfield with no implementation.

None of these are methodology defects in the approved strategy; they are engineering, data-integrity, and operational gaps.

---

## Feature Matrix

| Feature | API | UI | Data | Performance | Tests | Status |
|---|---|---|---|---|---|---|
| Screening / rankings | Works | Works | Works | Good | Pass | Working |
| Stock lookup | Works | Works | Works | Good | Pass | Working |
| Stock detail | Works | Works | Works | Good | Pass | Working |
| Momentum analysis (Trend Template, RS, Volume, Pattern, Setup) | Works | Works | Works | Good | Pass | Working |
| Technical indicators (RSI, MACD, ADX, ATR) | Works | Works | Works | Good | Pass | Working |
| Volume & accumulation | Works | Works | Works | Good | Pass | Working |
| Chart patterns | Works | Works | Works | Good | Pass | Working |
| Elliott Wave | Works | Works | Works | Good | Pass | Working, isolated |
| Stop-loss / risk management | Works | Works | Works | Good | Pass | Working, risk-only |
| Watchlist | Works | Works | Works | Good | Pass | Working |
| Market context | Works | Works | Sectors missing | Slow | Pass | Partial |
| Charting / drawing tools | Works | Works | Works | Good | Not tested | Working |
| Strategies config | Works | Works | Works | Good | Pass | Working |
| Validation | Works | Empty/Null | N/A | Very slow | Pass | Partial |
| Research (evaluate, compare, contribution) | Partial | Works | N/A | Slow | Pass | Partial |
| Health / operations | Works | Banner | Works | Good | Pass | Working |
| Learn / documentation | N/A | Works | N/A | N/A | N/A | Working |
| Frontend UX | N/A | Works | N/A | N/A | N/A | Working with gaps |
| Accessibility | N/A | Gaps | N/A | N/A | N/A | Needs work |
| Backend / API correctness | Works | N/A | N/A | Slow paths | Pass | Mostly working |
| Database / data integrity | Good schema | N/A | Gaps | Needs indexes | Pass | Mostly working |
| Performance | N/A | N/A | N/A | Poor on live/validation | Pass | Needs work |
| Architecture | Clean | Some logic in UI | N/A | N/A | Pass | Mostly clean |
| Documentation | Drift | N/A | N/A | N/A | N/A | Needs update |

---

## Detailed Findings

### F1 — Market data is stale (P0)

- **Severity:** P0 — Critical
- **Feature:** Health / data freshness
- **Location:** `/api/v1/health/data-freshness`
- **Evidence:**
  - `latest_bar_date`: 2026-08-07
  - `as_of`: 2026-08-15
  - `sessions_missed`: 5
  - `classification`: STALE
- **Expected:** For a daily screener, the latest bar should be no more than one session behind on a trading day.
- **Actual:** Five sessions are missed. The dashboard and all rankings are based on 2026-08-07 data.
- **Impact:** Every score, rank, stop-loss, and Elliott Wave projection is stale. Safe use is blocked until data is refreshed.
- **Fix:** Run the approved ingestion job and daily scheduler. Add an operational alert on `classification != FRESH`.
- **Type:** Data-integrity / operational defect.

### F2 — `/stocks/{symbol}/live` is too slow (P0)

- **Severity:** P0 — Critical
- **Feature:** Stock detail / live analysis
- **Location:** `backend/src/momentum25/application/use_cases/stocks.py:512-530`
- **Evidence:**
  - `GET /api/v1/stocks/COMSYN/live` → 200 in **8.76 s**
  - `GET /api/v1/stocks/RELIANCE/live` → 200 in **8.49 s**
  - The use case calls `compute_universe_rs_ratings` against the full active universe on every request with no cache.
- **Expected:** Single-stock lookups should complete in sub-second time.
- **Actual:** ~8.5 s per request because the entire universe is re-ranked for RS.
- **Impact:** The stock detail page and analysis page both call this endpoint; the UI feels broken during load.
- **Fix:** Cache the universe RS rating table keyed by `(as_of_date, strategy, config_hash)` and reuse it across `/live`, `/watchlist/detail`, and `/market/context`.
- **Type:** Performance defect.

### F3 — `/validation/dashboard` is unusably slow (P0)

- **Severity:** P0 — Critical
- **Feature:** Validation
- **Location:** `/api/v1/validation/dashboard`
- **Evidence:** `POST /api/v1/validation/dashboard` → 200 in **41.55 s**.
- **Expected:** Validation dashboard should load in a few seconds.
- **Actual:** 41+ seconds for only two completed runs.
- **Impact:** The validation screen is effectively unusable and may time out in deployment.
- **Fix:** Pre-compute or materialize validation aggregates; avoid repeated full-table scans in `validation_services.py`.
- **Type:** Performance defect.

### F4 — Market context is slow and sector data is missing (P1)

- **Severity:** P1 — High
- **Feature:** Market context
- **Location:** `/api/v1/market/context`, `securities.sector`
- **Evidence:**
  - `GET /api/v1/market/context` → 200 in **1.54 s**
  - Response: `"sectors": []`, `"sectors_unavailable_reason": "no_sector_classification"`
  - `SELECT sector FROM securities WHERE symbol = 'RELIANCE'` returns `NULL`.
- **Expected:** Sector breadth should be populated; market context should be near-instant.
- **Actual:** No sector classification is loaded, so sector tables are empty.
- **Impact:** Market context cannot show sector-relative strength, a documented feature.
- **Fix:** Ingest NSE sector data into `securities.sector`; add a covering index on `ohlcv_daily(date)` to speed breadth calculations.
- **Type:** Data-integrity and performance defect.

### F5 — `/stocks/{symbol}/history` returns duplicate points (P2)

- **Severity:** P2 — Medium
- **Feature:** Stock detail / history
- **Location:** `/api/v1/stocks/{symbol}/history`, `backend/src/momentum25/application/use_cases/stocks.py:135-181`
- **Evidence:** `GET /api/v1/stocks/COMSYN/history?limit=10` returns two entries for `2026-08-09` (run IDs 12 and 146) and two for `2026-08-07`.
- **Expected:** One point per trading date, ideally from the latest live `data_version`.
- **Actual:** Multiple completed runs for the same `run_date` are all returned.
- **Impact:** Score/rank history charts can show duplicated or conflicting values.
- **Fix:** Filter by `data_version` (exclude historical/research runs) or collapse by `run_date` picking the latest run.
- **Type:** Data-integrity / functional defect.

### F6 — `/stocks/{symbol}` and `/stocks/{symbol}/history` bypass DTO contracts (P2)

- **Severity:** P2 — Medium
- **Feature:** API schema
- **Location:** `backend/src/momentum25/interface/api/routers/stocks.py:28-52`
- **Evidence:**
  - `GET /api/v1/stocks/COMSYN` returns the domain `StockExplanation` dataclass, not `StockExplanationDTO`.
  - `GET /api/v1/stocks/COMSYN/history` declares `response_model=None` and returns `-> Any`.
- **Expected:** Routers should return typed DTOs so the OpenAPI contract is explicit.
- **Actual:** Domain objects leak through the interface layer.
- **Impact:** Contract drift; consumers rely on implicit field sets.
- **Fix:** Map domain results to `StockExplanationDTO` and `StockHistoryDTO` in the router.
- **Type:** Architecture / API defect.

### F7 — Research router uses hard-coded IDs and drops request fields (P2)

- **Severity:** P2 — Medium
- **Feature:** Research endpoints
- **Location:** `backend/src/momentum25/interface/api/routers/research.py:323`, `:398`, `:438-446`
- **Evidence:**
  - `/research/contribution/{strategy_name}` passes `strategy_id=0` regardless of the real strategy ID.
  - `/research/compare/strategies` maps `security_id=0` and misuses `symbol` as a run-date string.
  - `/research/experiment/run` ignores `body.overrides` and builds an `ExperimentConfig` with `base_strategy_id=0`.
- **Expected:** Endpoints should use the resolved strategy and request payload.
- **Actual:** Several research paths fabricate IDs or discard inputs.
- **Impact:** Research outputs are misleading or useless for non-default strategies.
- **Fix:** Pass the real `strategy_id` from the repository and respect request bodies.
- **Type:** Functional defect.

### F8 — `/research/evaluate` and `/research/compare` return empty results without a measurability flag (P2)

- **Severity:** P2 — Medium
- **Feature:** Research
- **Location:** `/api/v1/research/evaluate/{strategy_name}`, `/api/v1/research/compare/strategies`
- **Evidence:**
  - `GET /api/v1/research/evaluate/minervini_trend_template?max_runs=5` → `"run_summaries": []`
  - `GET /api/v1/research/compare/strategies?...` → `"comparisons": []`
- **Expected:** Empty results should carry a `measurability` block explaining why (as validation scorecard already does).
- **Actual:** Empty arrays with no explanation.
- **Impact:** Users cannot distinguish "no data" from "zero performance".
- **Fix:** Add a `measurability` object to these responses when forward returns are absent.
- **Type:** UX / functional defect.

### F9 — Cup-with-handle pattern detector has an index-selection bug (P2)

- **Severity:** P2 — Medium
- **Feature:** Pattern detection
- **Location:** `backend/src/momentum25/domain/patterns/cup_handle.py:77`
- **Evidence:**
  ```python
  cup_bottom_idx = recent_low.index(cup_bottom)
  ```
  `cup_bottom` is the minimum of `recent_low[left_peak_idx:]`, but `index()` returns the first occurrence in the whole list. If the same low appears before `left_peak_idx`, the index is wrong.
- **Expected:** The cup bottom index must be within the right-hand window.
- **Actual:** It can be earlier than the left peak, producing a negative or incorrect cup width.
- **Impact:** Cup-with-handle detection may mis-label patterns.
- **Fix:** Use `recent_low.index(cup_bottom, left_peak_idx)`.
- **Type:** Functional defect.

### F10 — Average scores in validation output have excessive precision (P3)

- **Severity:** P3 — Low
- **Feature:** Validation scorecard
- **Location:** `/api/v1/validation/scorecard/{strategy_name}`
- **Evidence:** `avg_momentum_score`: `"32.80407073184481310143477908"`
- **Expected:** Four decimal places, matching the rest of the API.
- **Actual:** Up to 28 decimal places.
- **Impact:** UI noise; suggests the value is more precise than it is.
- **Fix:** Quantize Decimal outputs in the DTO or use a `Decimal` serializer with fixed precision.
- **Type:** UX defect.

### F11 — Legacy staging tables are not refreshed by corporate-action updates (P2)

- **Severity:** P2 — Medium
- **Feature:** Corporate actions / historical data
- **Location:** `backend/src/momentum25/application/services/corporate_actions.py:35`
- **Evidence:** The refresh use case only updates `ohlcv_daily`. `legacy_ohlcv_daily` and `bse_legacy_ohlcv_daily` each contain millions of rows and have their own adjustment methods, but are not targeted.
- **Expected:** Historical research tables should stay adjusted.
- **Actual:** Only the live table is updated.
- **Impact:** Historical backtests and overlap reconciliation may use unadjusted prices.
- **Fix:** Extend the refresh job to recompute adjustment factors for the legacy staging tables, or document the limitation.
- **Type:** Data-integrity defect.

### F12 — Screening-result persistence is not atomic and uses row-by-row inserts (P2)

- **Severity:** P2 — Medium
- **Feature:** Screening persistence
- **Location:** `backend/src/momentum25/infrastructure/persistence/repositories/screening_run.py:151`
- **Evidence:** `save_results` adds one `ScreeningResultModel` and many `RuleResultModel` rows in a Python loop. There is no bulk insert.
- **Expected:** Atomic bulk insert for a run's results.
- **Actual:** Row-by-row inserts; a partial commit could leave a `COMPLETED` run with incomplete explanations.
- **Impact:** Data integrity under load; slow persistence for large universes.
- **Fix:** Use SQLAlchemy bulk insert and wrap the whole operation in one transaction.
- **Type:** Architecture / data-integrity defect.

### F13 — `score_history` and `get_previous_run_ranks` can mix live and historical runs (P2)

- **Severity:** P2 — Medium
- **Feature:** Screening persistence / ranking history
- **Location:** `backend/src/momentum25/infrastructure/persistence/repositories/screening_run.py:363-390`
- **Evidence:** These methods filter by strategy and date but do not exclude historical/research `data_version` tags.
- **Expected:** Live history should only include live runs.
- **Actual:** Historical backfill runs could be used as the prior rank or score history.
- **Impact:** Rank-change and history displays may become inconsistent.
- **Fix:** Add `data_version` filters that exclude historical/research prefixes.
- **Type:** Data-integrity defect.

### F14 — Missing database indexes on frequently filtered columns (P2)

- **Severity:** P2 — Medium
- **Feature:** Database performance
- **Location:** Multiple tables
- **Evidence:** No standalone indexes on `ohlcv_daily(date)`, `corporate_actions(security_id)`, `screening_results(security_id)`, `rule_results(run_id)`, `forward_returns(security_id)`, `universe_membership(run_id)`, `benchmark_index_daily(date)`.
- **Expected:** Foreign-key and filter columns should be indexed.
- **Actual:** Many queries scan or join on unindexed columns.
- **Impact:** Slow explainability dumps, validation aggregates, and research reports.
- **Fix:** Add the missing indexes; verify with query plans.
- **Type:** Performance defect.

### F15 — Watchlist detail can trigger expensive live evaluations (P2)

- **Severity:** P2 — Medium
- **Feature:** Watchlist
- **Location:** `backend/src/momentum25/application/use_cases/watchlist.py:148-160`
- **Evidence:** Symbols not in the latest completed run are evaluated live via `StrategyEngine.score_security`, and the whole-universe RS table is computed once per request.
- **Expected:** Watchlist detail should remain fast regardless of list size.
- **Actual:** A large watchlist of out-of-run symbols triggers one full-universe RS computation plus per-symbol live scoring.
- **Impact:** Potential for accidental denial of service if users add many illiquid symbols.
- **Fix:** Cap watchlist size or paginate; cache the universe RS table per `(date, strategy, config_hash)`.
- **Type:** Performance defect.

### F16 — Frontend analysis page computes explicit targets and risk/reward (P2 — research-isolation finding)

- **Severity:** P2 — Medium
- **Feature:** Stock analysis / targets
- **Location:** `web/src/app/stock/[symbol]/analysis/page.tsx:597-652`
- **Evidence:** The "Targets and risk / reward" card computes target prices from Elliott Wave projections, pattern measured moves, and ATR multiples, then displays `R:R` against the suggested stop.
- **Expected:** Targets and R:R may exist only in the separate research surface and must not leak into the core Momentum25 score or stop-loss.
- **Actual:** Targets/R:R are shown on `/stock/[symbol]/analysis`, but they are not used by scoring, ranking, screening, or the stop-loss API.
- **Impact:** This is acceptable if the analysis page is treated as a research screen. It must remain isolated from the core product.
- **Fix:** Keep the page, but add a clear disclosure that targets and R:R are research annotations, not strategy inputs.
- **Type:** Methodology / research question (not a software defect if isolated).

### F17 — Frontend table and chart have accessibility gaps (P2)

- **Severity:** P2 — Medium
- **Feature:** Accessibility
- **Location:** `web/src/components/dashboard/MomentumTable.tsx:530-549`, `:463-490`; `web/src/components/stock/PriceChart.tsx`
- **Evidence:**
  - Pagination buttons are icon-only with no `aria-label`.
  - Sortable headers use `onClick` on `<th>` elements, which are not keyboard-focusable.
  - The `lightweight-charts` canvas has no keyboard navigation, no `role`, and no alternative data table.
- **Expected:** All interactive controls are reachable and labelled.
- **Actual:** Keyboard users cannot sort or paginate; screen-reader users have no access to chart data.
- **Impact:** WCAG compliance gap.
- **Fix:** Add `aria-label`s, make headers focusable buttons, and provide a visually hidden data table for charts.
- **Type:** Accessibility defect.

### F18 — Frontend computes some indicators and signals from raw bars (P2)

- **Severity:** P2 — Medium
- **Feature:** Charting / strategy presets
- **Location:** `web/src/lib/strategies.ts`, `web/src/lib/indicators/overlays.ts`, `web/src/lib/indicators/oscillators.ts`
- **Evidence:**
  - `StrategyPanel.tsx` and an optional hidden "Signal" column in `MomentumTable.tsx` derive `long` / `short` / `exit` signals from browser-computed MAs and MACD.
  - Moving averages on the chart are computed in the browser from fetched closes.
- **Expected:** Frontend display should agree with canonical backend calculations.
- **Actual:** Browser-calculated indicators can diverge from backend snapshots due to rounding or adjusted-close handling.
- **Impact:** Users may see inconsistent signals between table, chart, and API.
- **Fix:** Use backend series (`/stocks/{symbol}/indicators/series`) for all displayed indicators where possible; document any unavoidable browser-side computations.
- **Type:** Data-integrity / UX defect.

### F19 — README is materially out of date (P1)

- **Severity:** P1 — High
- **Feature:** Documentation
- **Location:** `README.md:5`, `README.md:22-23`
- **Evidence:** README states "Implementation has not started (greenfield)" and points to a roadmap where M6 Web UI is future work.
- **Expected:** README should reflect the implemented backend, frontend, API, and screening pipeline.
- **Actual:** It describes a project that does not exist in the repository.
- **Impact:** New contributors and operators will be misled.
- **Fix:** Rewrite README to match current capabilities and deployment instructions.
- **Type:** Documentation defect.

### F20 — `ruff` and `mypy` report many issues (P1)

- **Severity:** P1 — High
- **Feature:** Static analysis
- **Location:** Backend source and tests
- **Evidence:**
  - `ruff check src tests` → **129 errors** (56 line-too-long, 19 unused imports, 11 unsorted imports, 8 unused loop variables, etc.)
  - `mypy src` → **33 errors** in `validation_services.py`, `research.py`, `watchlist.py`, etc.
- **Expected:** Clean static analysis in a production codebase.
- **Actual:** Lint and type errors accumulate, masking real defects.
- **Impact:** Reduced confidence in refactors; real type mismatches exist (e.g., `RankingComparison` attributes).
- **Fix:** Fix mechanical `ruff` issues; resolve `mypy` errors, especially in routers that reference non-existent DTO attributes.
- **Type:** Code-quality defect.

---

## Elliott Wave

### API status

`GET /api/v1/stocks/{symbol}/elliott-wave` works and returns a structured `ElliottWaveAnalysis`.

Example: `GET /api/v1/stocks/RELIANCE/elliott-wave`

- Returns 3 candidates: `triangle`, `flat`, `diagonal`.
- Two candidates include a `projection` with `low`/`high` completion zone.
- Example projection:
  ```json
  {
    "low": "1318.60",
    "high": "1351.17",
    "basis": "wave C: 1.0-1.618 of wave A from wave B"
  }
  ```

### UI status

The dedicated route `/stock/[symbol]/elliott-wave` exists and renders the same chart shell as the analysis page. The analysis page includes an Elliott Wave mode that displays candidates and projected completion zones.

### Isolation from Momentum25

Elliott Wave is correctly isolated:

- No imports from `domain/analytics/elliott*` exist in `domain/engines/`, `domain/scoring/`, `domain/strategy/`, or the screening orchestrator.
- The only shared code is the zigzag pivot utility, reused for chart-pattern detection.
- Elliott Wave does not influence momentum score, rank, screening, gates, trend template, RS, volume, pattern score, buy-setup quality, or stop-loss.
- The completion zone is forward-looking by design and is part of the research screen only.

### Methodology questions (not defects)

- The ranking weights in `domain/analytics/elliott/ranking.py` are editorial and documented as such.
- Wave counts are heuristic pattern fits, not probabilities.

**Conclusion:** Elliott Wave remains a separate research screen and the projected completion-zone functionality is retained and working.

---

## Stop Loss

### API status

Stop-loss information is returned inside `/api/v1/stocks/{symbol}/live` only.

Example (`RELIANCE`):

```json
{
  "suggested_stop": { "level": "1286.9222", "method": "2xATR" },
  "trailing_stop": { "level": "1274.0833", "method": "3xATR-chandelier(22)" }
}
```

### UI status

`SuggestedStop.tsx` displays both levels as downside caps. Copy explicitly states they are not targets and carry no reward estimate.

### Risk-only behavior

- `domain/research/stop_loss.py` contains only `level` and `method`.
- The module docstring forbids profit targets, R-multiples, and risk/reward ratios.
- `domain/engines/risk.py` computes only downside stop distance.
- No API or core UI endpoint exposes profit targets, take-profit, price objectives, R-multiples, or risk/reward.

### Target / reward leakage

The only target/reward surface is the optional "Targets and risk / reward" card on `/stock/[symbol]/analysis`. It is a research annotation and does not feed scoring, ranking, screening, or stop-loss. No leakage into the core product was found.

---

## Data Integrity

### Corporate actions

- `corporate_actions` contains 25,864 rows.
- RELIANCE bonus 2024-10-28 is present with `ratio = 0.5`.
- `ohlcv_daily` shows correct adjusted prices: pre-bonus close 2655.70 maps to `adj_close` 1327.85.
- Unique constraint `(security_id, ex_date, type)` prevents duplicate actions.
- Cash dividends and demergers are stored as `type = 'other'` with `ratio = NULL`; price is not adjusted for cash dividends by design.

### Backup / legacy tables

| Table | Rows | Value |
|---|---|---|
| `legacy_ohlcv_daily` | 6,343,469 | High — NSE legacy archive for overlap reconciliation |
| `bse_legacy_ohlcv_daily` | present | High — BSE pre-UDiFF archive |
| `bse_scrip_junction` | present | High — learned BSE code to ISIN mapping |
| `ohlcv_adj_snapshot_20260810` | 3,076,892 | Backup snapshot of adjusted prices |
| `screening_results_snapshot_20260810` | present | Backup of screening results |

### Missing indexes and constraints

- No standalone index on `ohlcv_daily(date)`.
- No index on `screening_results(security_id)`.
- No index on `rule_results(run_id)` or `(security_id)`.
- `screening_runs.status` has no `CHECK` constraint.

---

## Performance

Measured on a warm local process (MacBook, Docker Desktop, local API and frontend).

| Endpoint | Latency | Assessment |
|---|---|---|
| `GET /api/v1/health` | 0.48 s | Acceptable |
| `GET /api/v1/health/ready` | 0.006 s | Good |
| `GET /api/v1/health/data-freshness` | 0.30 s | Good |
| `GET /api/v1/strategies` | 0.006 s | Good |
| `GET /api/v1/runs` | 0.04 s | Good |
| `GET /api/v1/rankings/runs/12?limit=10` | 0.17 s | Good |
| `GET /api/v1/stocks/COMSYN` | 0.02 s | Good |
| `GET /api/v1/stocks/{symbol}/live` | **~8.5 s** | Critical |
| `GET /api/v1/stocks/{symbol}/indicators/series` | 0.02 s | Good |
| `GET /api/v1/securities/{symbol}/ohlcv` | 0.015 s | Good |
| `GET /api/v1/stocks/{symbol}/elliott-wave` | 0.03 s | Good |
| `POST /api/v1/stocks/{symbol}/chart-patterns` | 0.01 s | Good |
| `GET /api/v1/watchlist` | 0.014 s | Good |
| `GET /api/v1/watchlist/detail` | 0.02 s | Good (with cached run symbols) |
| `GET /api/v1/market/context` | **1.54 s** | Slow |
| `GET /api/v1/research/evaluate/...` | 0.07 s | Empty result |
| `GET /api/v1/research/contribution/...` | **4.46 s** | Slow |
| `GET /api/v1/research/compare/strategies` | **2.76 s** | Slow, empty result |
| `POST /api/v1/validation/dashboard` | **41.55 s** | Critical |
| `GET /api/v1/validation/scorecard/...` | 0.03 s | Good |
| `GET /api/v1/validation/rules/...` | 0.20 s | Good |
| `GET /api/v1/validation/engines/...` | 0.17 s | Good |

Key performance drivers:

- `/live` recomputes universe RS ratings per request.
- `/market/context` scans a large slice of the universe without a date-leading index.
- `/validation/dashboard` performs repeated full-table aggregations.

---

## Accessibility / UX

### Working

- Loading, empty, and error states are handled on all major routes.
- Static learn pages render consistently with the app chrome.
- Dark mode and responsive layout are implemented.

### Gaps

- Icon-only pagination buttons lack `aria-label`.
- Sortable table headers are not keyboard-focusable.
- Charts are mouse-only canvas elements with no accessible alternative.
- Ambiguous placeholders (`—`, `N/A`) are used for missing values without explaining *why* the value is missing.
- The optional "Signal" column in the dashboard table computes browser-side long/short/exit signals; it is hidden by default.

---

## Architecture

### What is clean

- Import-linter contracts are kept:
  - `interface -> application -> domain` layering is respected.
  - `domain` imports no infrastructure, interface, or application modules.
- Engines are registered through a strategy-agnostic registry.
- Scoring, ranking, and explainability are separated.
- I/O is behind ports (repositories, market data, calendar, Redis).

### Concerns

- Domain dataclasses (`StockExplanation`, `LiveStockAnalysis`) leak through the API router instead of being mapped to DTOs.
- Some frontend business logic exists in `lib/strategies.ts` (signal scoring, preset rules).
- `domain/engines/risk.py` imports constants from `domain/research/swing_targets.py`. The import is harmless (constants only) but creates a dependency from a production engine into a research module.

---

## Tests

```text
593 passed, 1 warning in 10.63s
```

- All backend tests pass.
- Test coverage includes screening, watchlist, corporate actions, Elliott Wave, stop-loss, determinism, validation, and API behavior.
- Frontend tests are not present in the project.

---

## Static Analysis

| Tool | Result |
|---|---|
| `ruff check src tests` | 129 errors |
| `mypy src` | 33 errors |
| `import-linter` | 2 contracts kept, 0 broken |
| `web: npx tsc --noEmit` | clean |
| `web: npm run lint` | clean |
| `web: npm run build` | clean |

`ruff` breakdown (top categories):

- 56 line-too-long
- 19 unused imports
- 11 unsorted imports
- 8 unused loop variables
- 6 undocumented `__init__`
- 5 undocumented public methods
- 4 unused variables

`mypy` errors are concentrated in:

- `domain/research/validation_services.py`
- `application/use_cases/research/contribution.py`
- `application/use_cases/watchlist.py`
- `interface/api/routers/research.py`

---

## Documentation

### Drift

- `README.md` claims the project is a greenfield with no implementation. This is false.
- `domain/scoring/__init__.py` still calls implementations "placeholder" even though the scoring engine is implemented.
- Strategy descriptions in `docs/architecture/strategies/minervini_trend_template.json` are accurate and versioned.

### Consistency

- API terminology (`momentum_score`, `buy_setup_score`, `hard_filters_passed`) is consistent across endpoints and UI.
- The separation between "core Momentum25" and "separate research" is documented and enforced in code.

---

## Methodology / Research Questions

These are intentional or unvalidated research choices, not software defects.

1. **Risk stop-distance threshold.** `DEFAULT_MAX_RISK_PCT = 16%` is chosen for consistency with the volatility rule, not walk-forward validation.
2. **Pattern detector thresholds.** VCP, cup-with-handle, ascending-base, and flat-base use fixed constants without documented calibration evidence.
3. **Elliott Wave ranking weights.** The component weights in `domain/analytics/elliott/ranking.py` are editorial and documented as such.
4. **Forward-return tier thresholds.** `domain/research/forward_returns.py` uses fixed thresholds (50%, 20%, 0%, -15%) by design.
5. **Browser-side signal column.** The optional dashboard signal and `StrategyPanel` presets produce long/short/exit annotations from raw bars; these are research overlays, not strategy inputs.
6. **Analysis-page targets/R:R.** The arithmetic is presented as a research illustration and does not feed the strategy.

---

## Recommended Remediation Plan

### P0 — Critical

1. Refresh market data so the latest bar is current; confirm `health/data-freshness` returns `FRESH`.
2. Cache the universe RS rating table and reuse it across `/stocks/{symbol}/live`, `/watchlist/detail`, and `/market/context`.
3. Optimize or pre-compute `/validation/dashboard` so it loads in under 5 s.

### P1 — High

4. Fix `README.md` to reflect the implemented product.
5. Resolve `ruff` and `mypy` failures.
6. Ingest sector classification so market context can show sector breadth.
7. Add missing database indexes on frequently filtered/joined columns.
8. Map `/stocks/{symbol}` and `/stocks/{symbol}/history` to typed DTOs in the router.

### P2 — Medium

9. Fix cup-with-handle index-selection bug.
10. Deduplicate `/stocks/{symbol}/history` by run date / data version.
11. Fix research endpoints that fabricate IDs or drop request fields.
12. Add measurability flags to `/research/evaluate` and `/research/compare`.
13. Make screening-result persistence atomic with bulk inserts.
14. Add `data_version` filters to `score_history` and `get_previous_run_ranks`.
15. Refresh adjustment factors for legacy staging tables or document the limitation.
16. Cap or paginate watchlist detail to avoid accidental expensive live evaluations.
17. Add accessible labels and keyboard support to tables and charts.
18. Reduce excessive decimal precision in validation DTOs.

### P3 — Low

19. Add a `CHECK` constraint on `screening_runs.status`.
20. Review and document browser-side indicator computations that may diverge from backend values.
21. Standardize ambiguous placeholder copy (`—`, `N/A`) with tooltips explaining not-qualified vs no-data vs stale.

---

## Final Acceptance Assessment

### What works

- Core screening, ranking, and explainability for the production strategy.
- Stock detail, live analysis, OHLCV charting, and indicator series.
- Elliott Wave analysis, including projected completion zones, isolated from core scoring.
- Stop-loss calculation and UI, risk-only.
- Watchlist read operations.
- Symbol search and market breadth.
- Test suite, import-linter, frontend build, TypeScript, and ESLint.

### What does not work

- Data freshness: latest bar is 2026-08-07, five sessions stale.
- `/stocks/{symbol}/live` latency (~8.5 s) and `/validation/dashboard` latency (~40 s).
- Sector classification is missing, so sector tables are empty.
- Several research/validation endpoints return empty or misleading results without explaining why.
- Static analysis gates (`ruff`, `mypy`) are failing.
- README is materially out of date.

### What cannot be verified

- Interactive browser behavior (hover, focus, chart interactions, actual rendering) because only `curl`-based page fetches were possible.
- POST/PUT/DELETE watchlist behavior and screening triggers were not exercised to preserve read-only safety.
- Real-world production deployment behavior (CORS, load balancing, scheduler concurrency).

### What needs engineering work

- Data ingestion refresh.
- Performance fixes for live lookup, validation dashboard, and market context.
- Static analysis cleanup.
- README rewrite.
- Database index additions.
- Research router corrections and measurability flags.

### What needs research validation

- Risk stop-distance threshold (`16%`).
- Pattern detector constants.
- Elliott Wave ranking weights.
- Browser-side signal presets and target/R:R arithmetic.

### What needs product decisions

- Whether the analysis-page targets/R:R card should remain visible by default or be gated behind an explicit "Research" mode.
- Whether to cap watchlist size or paginate detail.
- How to present "not measurable" validation states in the UI.
