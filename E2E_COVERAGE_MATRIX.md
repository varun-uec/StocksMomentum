# Wickstreet E2E Coverage Matrix

**Browser:** Chromium 153.0.8010.12, Playwright, local production build.

**Application revision:** `e7fd455`.

**Data:** synthetic fixtures in explicitly named, harness-verified `wickstreet_final_e2e` and `wickstreet_visual_e2e` databases backed by Docker tmpfs. No NSE downloads or real database writes were made.

Result terms: **Pass** = observed in a browser or measured and passed; **Partial** = main path passed, but meaningful permutations remain; **Route** = page hard-loaded and its primary heading rendered, without implying that every control on it was used; **Not tested** = no direct browser verification in this audit.

## Route coverage

All 26 route entries below are listed in `web/e2e/audit-visual.spec.ts`; each was hard-loaded in Chromium and captured at desktop width. The chart and Studio also have dedicated phone viewport captures. NFR-13 route checks in `m10-stack.spec.ts` additionally cover unknown routes and chart deep links.

| Route | Surface | Result / observed state | Evidence |
|---|---|---|---|
| `/` | Momentum25 dashboard / screener | Pass: qualified ranks, filtered/unranked row display, explanation panel; mobile horizontal-scroll hint and dark theme | [dashboard](audit-evidence/screenshots/dashboard-desktop.png), [mobile](audit-evidence/screenshots/dashboard-mobile.png), [dark](audit-evidence/screenshots/dashboard-dark-desktop.png) |
| `/chart` | Workspace entry / last-symbol fallback | Route; chart workspace initialization covered by chart tests | [entry](audit-evidence/screenshots/chart-entry-desktop.png) |
| `/chart/RELIANCE` | Chart workspace | Pass: browser interactions listed below | [chart](audit-evidence/screenshots/chart-desktop.png), [search](audit-evidence/screenshots/chart-search-desktop.png) |
| `/stock/RELIANCE` | Stock detail | Route; page render | [detail](audit-evidence/screenshots/stock-detail-desktop.png) |
| `/stock/RELIANCE/analysis` | Unified stock analysis | Route; existing chart save/persistence NFR-13 check | [analysis](audit-evidence/screenshots/stock-analysis-desktop.png) |
| `/stock/RELIANCE/elliott-wave` | Elliott Wave | Route; page render | [Elliott Wave](audit-evidence/screenshots/elliott-wave-desktop.png) |
| `/watchlist` | Watchlist | Route; add/remove current symbol also tested from workspace panel | [watchlist](audit-evidence/screenshots/watchlist-desktop.png) |
| `/market` | Market overview | Route; injected slow, unavailable and malformed API responses | [market](audit-evidence/screenshots/market-desktop.png), [slow](audit-evidence/screenshots/market-slow-loading.png), [503](audit-evidence/screenshots/market-api-unavailable.png), [incomplete](audit-evidence/screenshots/market-incomplete-response.png) |
| `/strategies` | Strategy catalogue | Route; page render | [strategies](audit-evidence/screenshots/strategies-desktop.png) |
| `/studio` | Strategy Studio | Pass: create family, change within bounds, save lineage, run Screening Result; mobile create/family view. Empty desktop/mobile screenshots were regenerated on a separate fresh synthetic E2E database. | [desktop](audit-evidence/screenshots/studio-desktop.png), [mobile](audit-evidence/screenshots/studio-mobile-viewport.png) |
| `/validation` | Validation | Route; historical point-in-time path covered by API-backed browser test | [validation](audit-evidence/screenshots/validation-desktop.png) |
| `/backtest` | Walk-forward backtest | Route; adjusted-open fill logic covered by backend regression tests, not a browser walk-forward run | [backtest](audit-evidence/screenshots/backtest-desktop.png) |
| `/historical` | Historical runs | Route; synthetic historical replay generated and manifest/revision checked; kept out of live latest run | [historical](audit-evidence/screenshots/historical-desktop.png) |
| `/experiment` | Experiment research | Route; historical replay path covered by backend/API regression, full UI experiment workflow not exhausted | [experiment](audit-evidence/screenshots/experiment-desktop.png) |
| `/analytics` | Analytics | Route; page render | [analytics](audit-evidence/screenshots/analytics-desktop.png) |
| `/data` | Data operations | Route; no real refresh/download invoked | [data](audit-evidence/screenshots/data-desktop.png) |
| `/learn` | Learning hub | Route | [learn](audit-evidence/screenshots/learn-desktop.png) |
| `/learn/momentum-investing` | Learning article | Route | [article](audit-evidence/screenshots/learn-momentum-investing-desktop.png) |
| `/learn/minervini-methodology` | Learning article | Route | [article](audit-evidence/screenshots/learn-minervini-methodology-desktop.png) |
| `/learn/momentum25-methodology` | Learning article | Route | [article](audit-evidence/screenshots/learn-momentum25-methodology-desktop.png) |
| `/learn/scoring-guide` | Learning article | Route | [article](audit-evidence/screenshots/learn-scoring-guide-desktop.png) |
| `/learn/rule-guide` | Learning article | Route | [article](audit-evidence/screenshots/learn-rule-guide-desktop.png) |
| `/learn/faq` | FAQ | Route | [FAQ](audit-evidence/screenshots/learn-faq-desktop.png) |
| `/about` | About / attribution | Route; attribution assertion passed across pages | [About](audit-evidence/screenshots/about-desktop.png) |
| `/lab/chart-grid?n=4&symbol=RELIANCE` | M10 chart diagnostic | Pass: four chart cells mounted | [diagnostic](audit-evidence/screenshots/chart-grid-diagnostic-desktop.png) |
| `/audit-missing-route` | Not found | Pass: not-found view rendered | [not found](audit-evidence/screenshots/not-found-desktop.png) |

`/chart/:symbol` and `/stock/:symbol` are parameterized routes, not just the RELIANCE instance. A deep-link reload/new-tab test passed for the chart. The app’s 25 named route entries plus the wildcard route are all represented above.

## Architecture and milestone acceptance mapping

| Architecture item | Observable acceptance intent | Audit result |
|---|---|---|
| ADD A1 FR-17 / M12 shell | Terminal-style workspace, toolbars/panels, keyboard shortcuts, existing Momentum25 screens reachable | Pass for shell and tested shortcuts/panels. All legacy UI paths hard-loaded; some route interactions are route-only. |
| ADD A1 FR-18 / M13 | Candle/bar/line/area/Heikin-Ashi; 1D/1W/1M; log/percent and compare | Pass on synthetic browser data. |
| ADD A1 FR-19 / M13 | Overlay and pane indicators; backend authority for alert-capable studies | Partial: representative overlays/panes/timeframes and value checks passed; not every indicator/parameter was independently golden-compared in browser. |
| ADD A1 FR-20 / M11 + M13 | 12 drawing types, selection, move, delete/edit/style, undo/redo, symbol-shared persistence | Partial: all 12 were created; full lifecycle was demonstrated on representative tools, with persistence/conflict/corporate-action alignment checks. |
| ADD A1 FR-21 | Existing explainable Top-25 in Wickstreet shell | Pass for controlled synthetic ranking/explanation paths; no investment efficacy claim. |
| ADD A1 FR-22 / M15 | Daily price/indicator alerts with one-shot lifecycle and parity | Pass for 21 UI combinations and firing/rearm/list states; corporate-action and all historical re-evaluation edge cases not exhaustive. |
| ADD A1 FR-23 / M11 | Persistent workspace/drawings survive reload and browser change | Pass; tests include stale local import, second browser, and conflicting edits. |
| ADD A1 FR-24 / M13 | 1–16 chart layouts with optional symbol/interval/crosshair sync | Pass for layouts and observed sync transitions; benchmark report supplied. |
| ADD A1 FR-25 / M14 | Bounded registered configuration, lineage, reproducible PIT data, gated OOS | Partial browser verification: family/config lineage and bounded changes tested; deterministic, look-ahead and PIT contracts also have backend tests. Actual OOS exhaustion/failure matrix not fully browser-run. |
| M9 reference study | Usability/capability study from public docs/observable behavior under clean-room rule | Pass as documentation assessment; no proprietary source was read. See [M9 study](docs/history/plans/2026-10-18-m9-reference-study.md). |
| M10 stack | Same-origin SPA, Host/Origin guard, local deployment, attribution, deep links, 16-chart smoke | Pass for browser/API checks and route smoke. Loopback network configuration was inspected; not a public-security test. |
| M11 vertical slice | Find → Analyse → Draw → Restore and server-backed persistence | Pass for tested browser paths; see chart-state trace. |
| M11b weekly bars | Weekly aggregation, studies and drawing alignment | Pass on synthetic fixture, including drawing retained across daily/weekly switch. |
| M12 workspace shell | More-menu advanced routes, light/dark theme, panel persistence, keyboard map | Pass for tested states; accessibility and every shortcut/control were not exhaustively audited. |
| M13 professional charting | Chart types, drawing interactions, 4×4, sync, NFR and 1/4/16 benchmarks | Pass with partial per-drawing lifecycle coverage described above. |
| M14 Strategy Studio | Golden determinism, look-ahead, provenance, family/OOS rules and UI | Backend suite passed; browser UI is partial as stated. |
| M15 daily alerts | Daily alert evaluation, fixed-data parity, in-app state | Browser lifecycle and backend suite passed; no real market-day scheduled run was invoked. |
| M16 open-source release | Licence, data-use check, security, fresh install, usability, name | Engineering and audit reports exist, but public release exit is blocked: data-use decision, licence, name/legal clearance and auth boundary remain. |

## Capability and workflow coverage

| Capability | Browser/API state exercised | Result | Remaining coverage gap |
|---|---|---|---|
| Symbol search | Chart-focused keyboard entry, `Ctrl/⌘+K`, choose result, open symbol; 20 rapid open/type/close/reopen repetitions | Pass; 20/20 | No large-search-index stress run. |
| Daily/weekly/monthly bars | 1D default, 1W switch, 1M switch; interval persistence; daily, weekly and monthly chart panes/indicators | Pass for synthetic fixtures | Provider data quality over real market history not checked; no NSE download. |
| Ranges, pan, zoom, crosshair | 1W, 1M, 3M, 6M, 1Y and MAX; wheel zoom, pointer drag pan; synchronized crosshair | Pass | No long-duration pointer/gesture stress or touch pinch validation. |
| Chart types/scales/compare | Candle, bar, line, area, Heikin-Ashi; normal, log, percent; add/remove compared symbol | Pass | No edge-case comparison with disjoint history or zero/negative price fixtures. |
| Indicators | Indicator dialog; overlay and pane add/save; Bollinger/CCI/RSI/MACD examples and monthly indicator consistency; legends/value checks | Partial | Not every catalog indicator, parameter boundary, pane arrangement, and stale-version combination was exhaustively compared to a hand-calculated golden series in browser. |
| Drawing tools | All 12 tool types created and saved; selection/style edit/move/delete/undo/redo/arrow movement exercised on representative drawings; restore after reload and in second browser; conflict flows; daily/weekly persistence; split/bonus price alignment | Partial | Full select/move/edit/delete/undo/redo lifecycle was not repeated individually for every tool type. No very-large drawing collection benchmark. |
| Workspace layouts | 1, 2, 4, 9 and 16-chart mount counts; sync symbol, interval, crosshair; independent chart state and layout persistence | Pass for tested transitions | Concurrent same-field edits were tested; prolonged multi-client conflict storms and offline merge were not. |
| Momentum25 ranking | Controlled synthetic screening fixture; qualified-first ordering, zero/filtered row shown unranked, sorting, filters and explanation panel | Pass for fixture | Synthetic outcomes do not validate investment efficacy; not every filter/sort permutation or every legacy report/export control was visited. |
| Momentum25 legacy screens | Stock detail/analysis, Elliott Wave, watchlist, historical, validation, experiment, analytics, backtest, data and learning routes opened; selected interactions tested | Partial | Browser workflow depth varies by route; several are route-render checks only. CLI `ingest` and `screen` are documented stubs and were not invoked. |
| Strategy Studio | New family, bounded parameter update (valid value accepted, out-of-range rejected), lineage, config hash, Screening Result, hold-out confirmation dialog | Partial | Actual OOS evaluation/exhaustion, all rule/gate/weight/threshold schema permutations, failure recovery and every insufficient-data boundary not exhaustively browser-run. Determinism/look-ahead/PIT constraints also have backend tests. |
| Historical point-in-time | New historical replay records data basis, revision and manifest; isolation from `/runs/latest` | Pass for synthetic path | Broad backfill across corporate-action edge dates and repeated as-of snapshots was not comprehensively run. Legacy saved runs remain marked with warning and are not rewritten. |
| Alerts | 7 supported value kinds × 3 intervals (21 combinations), create, list, trigger, one-shot/seen state, re-arm and delete | Pass for exercised lifecycle | Corporate-action adjusted alert thresholds and historical re-evaluation did not receive exhaustive browser-level date matrices; backend parity tests are separate. |
| Security/deployment boundary | Same-origin API requests, CSRF/Origin rejection and no-Origin allowance, Host guard checks, local anonymous use | Pass within loopback model | No auth exists; not a public-network pen test, multi-user isolation audit or hostile-origin browser suite. |
| API resilience | 1.2 s injected delay with loading state, HTTP 503 error state, incomplete JSON error handling | Pass | DNS failure, connection reset, timeout exhaustion, malformed types beyond the captured response, and API outage during mutation not tested. |
| Restart/persistence | API process restart per NFR cold sample; tmpfs Postgres restart empties only disposable target; guard/migrations/fixtures/browser cleanup restored against exact same DB | Pass for test harness | Does not validate durable-volume restart, backup restore, crash during transaction, or migration from every supported historical schema. |
| Browser/local persistence | Server workspace survives reload, second browser; local legacy import once; stale/incomplete server documents covered by existing tests | Pass for selected paths | Corrupt browser storage and all migration-version combinations were not exhaustively fault-injected. |

## Test suite and performance evidence

| Measure | Result | Evidence |
|---|---|---|
| Backend | 815 passed, 2 deprecation warnings; Ruff and strict mypy clean | `e2e-suite-summary.json` and CI/local logs |
| Web | lint passed; 101 Vitest passed; production build passed | `e2e-suite-summary.json` |
| Playwright full suite | 108 passed, 6 opt-in benchmark cases skipped | `e2e-suite-summary.json` |
| M13 benchmark suite | 6 cases passed separately; 30 runs per case | `m13-bench.json` |
| NFR-11 | Warm P95 165 ms; cold (after API process restart) P95 482 ms | `nfr11.json` |
| 1 / 4 / 16-chart open | Warm P95 185 / 495 / 1,772 ms; fresh browser-context cold P95 201 / 528 / 1,785 ms | `m13-bench.json` |
| 1 / 4 / 16-chart pan | P5 61 / 61 / 61 FPS; median 62 / 63 / 62 FPS | `m13-bench.json` |
| JS heap | 1 / 4 / 16 charts: max sample 11 / 25 / 79 MB | `m13-bench.json` |
| API delay | Artificial 1,200 ms delay, 1,375 ms observed render | `api-resilience.json` |

NFR-11 cold sample starts navigation after the fresh API process answers `/health/live`; API boot time is excluded. The M13 “cold” samples mean a new browser context against an already-running API, so those numbers are not interchangeable with NFR-11 cold. All performance figures use local synthetic data and the hardware/browser details embedded in the JSON.

## Evidence files

- Screenshots: [audit-evidence/screenshots](audit-evidence/screenshots/)
- Browser traces: [chart state restore](audit-evidence/traces/chart-state-restore.zip), [slow API response](audit-evidence/traces/api-slow-response.zip)
- Benchmarks and test summary: [audit-evidence/benchmarks](audit-evidence/benchmarks/)
- Detailed evidence notes: [audit-evidence README](audit-evidence/README.md)
