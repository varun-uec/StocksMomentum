# Capability Validation Matrix — Round 3

Date: 2026-10-20. Inventory rebuilt from source: `web/src/main.tsx` routes, the OpenAPI document (68 operations on 59 paths), `chart-drawings.ts`, `lib/indicators/catalogue.ts`, `lib/workspace.ts`, `lib/shortcuts.ts`, `docs/current/capabilities.md`, and the 18 ADR files. The earlier ledger was reconciled against them, not trusted.

Status key: **PASS** (exercised, expected outcome observed), **FAIL** (observed defect, open), **BLOCKED** (needs an owner or legal decision), **NOT VERIFIED** (no evidence collected). "E2E" means a Playwright spec in `web/e2e/` that passed on the final run. "Ind." means a check written independently of the code under test.

## Inventory reconciliation (documents against code)

| Item | Document says | Source says | Disposition |
|---|---|---|---|
| Drawing tools | "12 drawing tools" (`capabilities.md`, `state.md`) | **21** `DrawingKind` values: trendline, ray, extended, horizontal, hline, vline, crossline, channel, rectangle, fib, price_range, text, arrow, date_range, date_price_range, ellipse, triangle, fib_extension, pitchfork, callout, price_label | Docs stale (R3-U-14, P3). Code is ahead of the docs. |
| Indicators | Not enumerated | About 35 entries in 8 groups, plus backend panes (RSI, MACD, ADX and others) | Listed below |
| Layouts | "up to 4 × 4" | 1×1, 2×1, 1×2, 2×2, 3×3, 4×4 | Matches |
| Alert sources | "close, RSI, ADX, ATR, MACD" | 7 sources × daily, weekly, monthly (R2 and `m15-alerts.spec.ts`) | Docs incomplete (P3) |
| Test counts | 684 / 815 backend; 101 web | **947** backend; **144** Vitest | Docs stale (R3-B-21) |
| Migrations | "19 migrations, 27 tables" | 21 migrations, 28 tables | Docs stale (R3-B-21) |
| ADR-056 | Named in the audit brief | Does not exist. ADRs run 001–015. No other numbering scheme. | R3-B-22 |
| Research strategies in the workspace picker | Journey 4 (old spec) | Production and saved user strategies only (commit `cecb3e5`) | Spec updated; defect R3-U-10 found and fixed |

## A. Routes and screens (all hard-loaded, light and dark, 1440 / 768 / 390)

| # | Capability | Status | Evidence |
|---|---|---|---|
| A1 | Screener `/` (filters, sort, pagination, saved screens, columns, search) | PASS | `b1-screener`, `momentum-ranking-display`, `strategy-integration` (pages of 10, symbol sort, search), real app run #149 |
| A2 | Chart workspace `/chart`, `/chart/:symbol` | PASS | many; section B |
| A3 | Stock `/stock/:symbol` and analysis, Elliott Wave | PASS | `m12-shell`, `momentum25`, axe sweep |
| A4 | Watchlist | PASS | `momentum25` (rank and qualification equal the screener), `m12-shell` Alt+W |
| A5 | Market | PASS | route sweep; sector panel empty by design |
| A6 | Strategies, Studio, Validation, Backtest, Historical, Experiment, Analytics | PASS (render and workflow); see C and D for results | `m14-studio`, `strategy-integration`, route sweep |
| A7 | Data (import instructions, status) | PASS | `m16-release-hardening` |
| A8 | Learn hub and 6 guides, About | PASS | route sweep, axe |
| A9 | Not-found, deep link, reload, new tab | PASS | `m10-stack` |
| A10 | `/lab/chart-grid` (unlisted) | PASS (renders); no `h1` | engineering route |
| A11 | Responsive reflow 390 / 768 / 1440 / 1920, 200% zoom | PASS | `r2-viewport-audit` (208 states), `r2-accessibility` 200%, 48 new screenshots |
| A12 | Accessibility, WCAG 2.x A/AA automated | PASS after fixes (R3-U-02..05) | `r3-axe-routes` (23 routes × 2 themes) |
| A13 | Screen-reader use, Safari, Firefox | NOT VERIFIED | not available here |

## B. Charting engine

| # | Capability | Status | Evidence |
|---|---|---|---|
| B1 | Candle body and wick geometry against stored bars, both sides of a split | PASS | `candle-anatomy` (11 tests). Wick-size defect not reintroduced. |
| B2 | Daily, weekly, monthly aggregation | PASS | Ind. `aggregation_check.py`: 0 mismatches on 4 real symbols; `candle-anatomy` |
| B3 | Adjusted and traded-price consistency | PASS | Ind. `adjust_parity.py`; `m11-slice` (drawings saved at traded prices across split and bonus) |
| B4 | Chart types: candles, bars, line, area, Heikin-Ashi | PASS | `m13-charting` (every type and scale draws and is saved) |
| B5 | Price scales: linear, percent, log | PASS | `m13-charting`, `candle-anatomy` axis-label tests |
| B6 | Indicators, 21 series with a golden reference (MA, EMA, WMA, Bollinger, Keltner, Donchian, Ichimoku tenkan/kijun, ATR, ATR%, RSI, Stoch, Williams, CCI, ROC, OBV, CMF, MFI, ±DI, MACD) | PASS | Ind. `golden.test.ts` (1e-9, warm-up gaps) |
| B7 | Indicators without a golden reference: Supertrend, Parabolic SAR, linear regression, pivots, anchored and rolling VWAP, swings, Ichimoku senkou/chikou | NOT VERIFIED against a reference; property tests only | `indicators.test.ts` |
| B8 | Indicator warm-up and parameters, dialog, Alt+I, Enter adds first match | PASS | `m13-charting`, `openchart-parity` D3, D5, D10 |
| B9 | MA lookback on short ranges (MA200 on a 1Y chart) | PASS | `openchart-parity` D1, D2 |
| B10 | Drawing tools, 21 kinds: create, select, move, resize, restyle, undo, redo, lock, hide, delete, save, reload | PASS | `m13-charting` (12 tools), `b3-drawing-tools` (9 tools), `openchart-parity` D6 |
| B11 | Drawing menu, object tree, contextual menus | PASS | `m13-charting`, `m12-shell` |
| B12 | Drawings stay on their bars across split and bonus | PASS | `m11-slice`, `b3-drawing-tools` |
| B13 | Compare overlay (rebased line), percent mode | PASS | `m13-charting` |
| B14 | Layouts 1×1 … 4×4, independent symbol and settings per cell, active-chart routing | PASS | `m13-layouts`, `openchart-parity` D8, `integrated-workflows` journey 2 |
| B15 | Sync: symbol, interval, crosshair | PASS | `m13-layouts`, `openchart-parity` D9 |
| B16 | Zoom, pan, wheel, resize, viewport restore, ranges | PASS | `m13-charting`, `r2-accessibility` |
| B17 | Bar Replay: cuts chart, panes, compare line; steps, plays, exits; hides later drawings; Assessment shows only runs dated on or before the replay date; candles equal the series as of the replay date, before a split | PASS | `b2-replay`, `candle-anatomy` |
| B18 | Legend values, crosshair readout, price-axis labels | PASS | `openchart-parity` D4, `candle-anatomy` |
| B19 | Workspaces: save, restore, two windows editing, conflict choice, offline edit then retry | PASS | `m11-slice`, `r2-adversarial` |
| B20 | Keyboard: shortcuts dialog (`?`), Alt tools, Escape, arrow moves, focus | PASS | `m12-shell`, `final-accessibility`, `r2-accessibility` |

## C. Alerts

| # | Capability | Status | Evidence |
|---|---|---|---|
| C1 | Price alert from chart; list, check, fire once, seen, re-arm | PASS | `m15-alerts` |
| C2 | 7 sources × daily / weekly / monthly | PASS | `m15-alerts` |
| C3 | Drawing-linked alert (ray) fires on first close above | PASS | `b4-line-alerts` |
| C4 | Threshold stays on the adjusted basis across a bonus | PASS | `m15-alerts` |
| C5 | Concurrent evaluation counts one firing | PASS | R2 regression, kept in backend suite |
| C6 | Alert from Assessment shows under "This symbol" | PASS | `integrated-workflows` journey 6 |
| C7 | Alert delivery outside the app | Not built (documented) | — |

## D. Momentum25 strategy lifecycle (Create → Configure → Save → Run → Screen → Rank → Chart → Assess → Watchlist → Research → Return → Reload)

| # | Capability | Status | Evidence |
|---|---|---|---|
| D1 | Create family, change a bounded rule, save an immutable version, duplicate and invalid saves refused | PASS | `strategy-integration` 1, `m14-studio` |
| D2 | Saved parameters drive the engine (RS gate 99 → only RS ≥ 99 pass) | PASS | `strategy-integration` 2 |
| D3 | Different configs give different rankings and different config hashes | PASS | `strategy-integration` 2; Ind. worker: top-25 overlap 5 of 25 |
| D4 | Every view names strategy, run, config hash, as-of date, data version | PASS | `integrated-workflows` 1,3,7,8; real app |
| D5 | Switching strategies cannot show another's results; unrun strategy shows an empty state | PASS | `strategy-integration` 3 |
| D6 | A stored strategy the workspace no longer offers | **PASS after fix** (was FAIL, R3-U-10) | `integrated-workflows` journey 4 |
| D7 | Chart cell and watchlist follow the exact custom run; return navigation keeps other cells | PASS | `strategy-integration` 4 |
| D8 | Saved screens stay distinct from strategy definitions | PASS | `strategy-integration` 5, `b1-screener` |
| D9 | Historical research keeps its original config hash after a later version is saved | PASS | `strategy-integration` 6 |
| D10 | Historical replay records point-in-time inputs, stays out of the live latest run | PASS | `m16-historical-pit` |
| D11 | Research navigation: tab row, selected strategy, way back to the chart | PASS | `momentum25` |
| D12 | Studio: In-Sample, sealed Out-of-Sample once per family, insufficient-data refusal | PASS | `m14-studio` |
| D13 | Backtest page and run | PASS (page); results **FAIL for fill prices** | R3-B-09 |
| D14 | Validation page offers saved strategies and shows their own evidence | **PASS after fix** (was FAIL, R3-U-07) | `strategy-integration.spec.ts` (picker lists each version; `config_hash` sent; unrun version reads empty); backend tests with three versions of one user strategy |
| D15 | Experiments, determinism check, contribution, comparison APIs | PASS (worker determinism and API probes); UI render PASS | backend report |

## E. Backend services and data (68 operations)

| # | Capability | Status | Evidence |
|---|---|---|---|
| E1 | Screening engine, rankings, explanations | PASS | Financial Correctness Report |
| E2 | Run identity and immutability; same-session corrections | PASS (app level); no DB-level guard | R2-LIMIT-01 resolved |
| E3 | Concurrent screens | PASS after fix (R3-B-04) | worker |
| E4 | Optimistic concurrency on workspaces, drawings, screens (10 parallel PUTs → 1 × 200, 9 × 412; 428 without precondition) | PASS | worker `api-probe/` |
| E5 | API validation and error semantics | PASS, with `/runs/<huge int>` → 500 (R3-B-19, P3) | worker |
| E6 | Import of authorised EOD CSV, corporate actions, benchmark | PASS after fix (R3-B-02, P1) | worker `eod/` |
| E7 | Corporate-action adjustment, exactly once | PASS | worker, 893,479 bars |
| E8 | Health, freshness, metrics endpoints | PASS | probes; real app `FRESH` |
| E9 | Migrations upgrade and downgrade | PASS; schema drift FAIL (R3-B-15) | worker |
| E10 | Backup and restore | PASS | worker, row counts and checksums on 14 tables |
| E11 | Scheduler, EOD job | Implemented PASS; enabled PASS; **observed PASS (one run, 18:30 IST, run 150)**; catch-up and weekday numbering **FAIL in the deployed image, fixed in source**; automated authorised source BLOCKED | `EOD_AUTOMATION_REPORT.md` |
| E12 | Direct exchange downloads | Off, answers 409 | BLOCKED by rights (not enabled) |
| E13 | Authentication, multi-tenancy, intraday, broker trading, fundamentals | Not built (documented) | — |

## F. Performance (Apple M4 Pro, 14 cores, 48 GB; Chromium 153 headless; synthetic 2,610-bar fixtures)

| # | Capability | Status | Measured | Limit |
|---|---|---|---|---|
| F1 | NFR-11 warm chart open, 30 runs | PASS | P50 135 ms, P95 152 ms | P95 ≤ 1 s |
| F2 | NFR-11 cold chart open after API restart, 30 runs | PASS | P50 496 ms, P95 513 ms | P95 ≤ 3 s |
| F3 | 1 / 4 / 16 charts warm open, 30 runs | Reported (no limit set by ADD A1) | P95 151 / 448 / 1,525 ms | none |
| F4 | 1 / 4 / 16 charts cold open | Reported | P95 193 / 497 / 1,604 ms | none |
| F5 | Pan responsiveness | PASS | FPS P5 60 / 62 / 61 | — |
| F6 | JS heap at 1 / 4 / 16 charts | Reported | max 13 / 28 / 85 MB | — |
| F7 | 24-cycle 1×1 ↔ 4×4 endurance releases DOM and canvases | PASS | `final-performance` | — |
| F8 | Search, workspace save, live screening after a correction, 20-alert evaluation (API) | Reported | search P95 7 ms; save P95 7 ms; screening P95 355 ms (n=10); alerts P95 783 ms (n=20) | none set |
| F9 | Studio Screening Result and In-Sample research | Reported | screening P50 315 / P95 831 ms (n=10); In-Sample research P50 62.6 s (n=3, P95 = max 65.1 s) | none set |
| F10 | Full-universe screening, 3.2 M bars, 3,096 universe, 5 runs (real-data copy) | Reported | pipeline P50 32.6 s, P95 33.5 s | none set |
| F11 | Real-data API latency (n=30) | Reported | OHLCV P95 62 ms; rankings P95 76 ms; workspace PUT P95 5 ms | none set |
| F12 | Main web bundle | **Improved after fix** (R3-U-01) | 654.3 kB raw, 208.8 kB gzip (was 1,009.9 / 315.6; R2: 565.8 / 182.1). `recharts` entered the shell via the Assessment panel and now loads on demand. | warning at 500 kB (still above; accepted) |
| F13 | Multi-hour memory stability | NOT VERIFIED | only a 24-cycle soak | — |

Raw data: `ui/nfr11-r3.json`, `ui/m13-bench-r3.json`, `ui/performance-r3.json`, backend `determinism/timings.txt`, `api-probe/`.

## G. Governance

| # | Capability | Status |
|---|---|---|
| G1 | ADR-001 … ADR-015 compliance | See `ADR_COMPLIANCE.md` |
| G2 | Chart attribution on every page and on About | PASS (`m10-stack`) |
| G3 | Licence file, notices | BLOCKED (owner) |
| G4 | Data-use rights | BLOCKED (counsel) |
