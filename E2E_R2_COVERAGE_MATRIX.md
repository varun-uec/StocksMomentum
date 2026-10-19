# Wickstreet Round 2 E2E Coverage Matrix

**Date:** 2026-10-19 · **Browser:** Chromium 153.0.8010.12 · **Machine:** Apple M4 Pro ×14, 48 GB · **Test data:** synthetic and isolated.  
Status: **Pass** means the stated behavior was exercised with meaningful assertions. **Partial** means a material permutation remains. **Not tested** means no direct Round 2 execution; prior reports are linked as historical evidence where relevant.

## Route, theme, and viewport sweep

All routes below were rendered in light and dark themes at 1440×900, 1920×1080, 768×1024, and 390×844: **26 routes × 2 themes × 4 sizes = 208 states**. The measured root `documentElement.scrollWidth` and body width did not exceed the viewport after the responsive fix. Per-route page height and widths are in [`viewport-audit.json`](audit-evidence/r2/viewport-audit.json). Forty-six screenshots are in `audit-evidence/r2/`; screenshots are a focused subset, not a capture of every dynamic state.

| Route | Surface covered |
|---|---|
| `/` | Dashboard / screener |
| `/chart` | Workspace entry/fallback |
| `/chart/RELIANCE` | Chart workspace |
| `/stock/RELIANCE` | Stock detail |
| `/stock/RELIANCE/analysis` | Unified stock analysis |
| `/stock/RELIANCE/elliott-wave` | Elliott Wave |
| `/watchlist` | Watchlist |
| `/market` | Market overview |
| `/strategies` | Strategy catalogue and comparison |
| `/studio` | Strategy Studio |
| `/validation` | Validation |
| `/backtest` | Walk-forward backtest |
| `/historical` | Historical runs |
| `/experiment` | Experiment research |
| `/analytics` | Analytics |
| `/data` | Data/import operations |
| `/learn` | Learning hub |
| `/learn/momentum-investing` | Learning article |
| `/learn/minervini-methodology` | Learning article |
| `/learn/momentum25-methodology` | Learning article |
| `/learn/scoring-guide` | Learning article |
| `/learn/rule-guide` | Learning article |
| `/learn/faq` | FAQ |
| `/about` | Attribution/about |
| `/lab/chart-grid?n=4&symbol=RELIANCE` | Chart-grid diagnostic |
| `/audit-missing-route` | Not-found state |

## Charting and workspace workflows

| Feature / combination | Round 2 coverage | Result and limits |
|---|---|---|
| Drawing tool create → select → edit → move → restyle → undo → redo → save → reload → delete | All 12 supported tools | **Pass.** Browser checks assert server state changes and restored IDs/style after reload. Undo restores deletion. Invalid geometry and self-overlap fuzzing remain partial. |
| Drawing boundary behavior | Drag a drawing; keyboard movement; right-click context menu; delete versus concurrent remote edit; save failure/retry | **Pass for tested flows.** One network-aborted style save showed “Not saved”, retained server’s last value, and retried successfully. Dragging outside the visible data range and chart resize during an in-progress draft were not directly tested. |
| Concurrent drawing edits | Two browser contexts; one deletes while the other edits, conflict asks which copy to apply | **Pass.** Also Round 1 merge/conflict tests remain in the baseline report. Rapid simultaneous PUT ordering and many-window conflicts not tested. |
| Chart type and scales | Candles, bars, line, area, Heikin-Ashi; normal/log/percent | **Pass for type rendering and persisted selection** in existing M13 browser suite. No exhaustive numeric oracle at every chart type/scale. |
| Visible ranges | 1W, 1M, 3M, 6M, 1Y, MAX | **Pass.** Each selection updates `aria-pressed` and the persisted workspace. |
| Intervals and periods | Daily, weekly, monthly; bonus-week/month aggregation; weekly drawing alignment | **Pass with backend golden tests.** A monthly browser chart with monthly indicators is covered. Calendar tests cover holiday-shortened weeks, incomplete weeks/months, empty periods, year crossings, and corporate-action weeks. Long synthetic stress data is weekday-only and does not model NSE holidays. |
| Indicators | SMA/EMA, Bollinger, Donchian, RSI, MACD, ADX in stress; overlay and pane examples; weekly/monthly indicators | **Partial.** Backend formula tests and representative UI parameter controls pass, but every catalogue indicator and invalid parameter boundary was not browser-compared to independent golden values. |
| Comparison symbols / moving averages | Four comparisons and four moving averages per loaded chart; comparison add/remove and rebased line | **Pass for these controls and stress configuration.** Sparse-history and symbol change while comparison fetches are pending are not exhaustively exercised. |
| Zoom/pan and gestures | Wheel zoom, pointer pan, crosshair, right-click menu, focus/keyboard delete and arrows | **Pass for observed interactions.** Exact zoom-anchor invariance, reversed pan-direction conventions, every focus edge and context menu at viewport boundaries remain partial. |
| Layouts | 1×1, 2×1, 2×2, 3×3, 4×4 (16); save/reload; active chart; symbol, interval and crosshair sync toggles | **Pass.** 16 charts mount and restore. Per-chart independent setting combinations are exercised in workspace flows but not all combinations across 16 charts. Switching layouts while a write is pending and rapid symbol churn with out-of-order responses remain partial. |
| Shared drawings across layouts | Symbol-scoped drawing persisted and independently edited in a second chart/window | **Pass for core symbol-shared persistence.** Large 120-drawing collections stress rendering; cross-tab 120-drawing conflict recovery not run. |

## Financial, research, and notification workflows

| Feature | Round 2 exercise | Result and remaining gap |
|---|---|---|
| Corporate action → adjusted bars → indicators → chart | Synthetic splits/bonuses, dividend, GOLDIAM bonus boundary, MCX 1:5 split golden | **Pass.** `raw × adjustment factor` is applied once; volume uses inverse factor; chart close equals stored adjusted close; drawings remain in traded-price basis and are converted by date for display. |
| OHLCV aggregation | Daily to weekly/monthly; partial periods, holiday week, action week; missing/sparse data tests in backend | **Pass for existing deterministic backend fixture set.** Round 2 did not independently import a complete real NSE calendar/history dataset. |
| RS/ranking | Split in lookback, MCX 1:5 500→100→120 case | **Pass.** MCX adjusted return is +20%; MCX ranks 99 versus flat control rank 1 in the two-security golden. |
| Point-in-time decisions | Future bonus/action boundary, delisting/listing membership, revision/manifests, correction reproducibility tests in backend | **Pass for fixtures.** No Round 2 full-universe query on a separate historical database. Stored/research comparison from the prior M14.7 report is reproducible in that report but was not re-run in Round 2 because its historical copy was not an explicitly isolated R2 target. |
| Strategy Studio lifecycle | Create family → configure → immutable version → Screening Result → reopen → compare two stored results | **Pass.** Distinct hashes and saved results persist; UI labels Screening Result as selection-only and says it has no performance figure. |
| Strategy eligibility and provenance | Insufficient holdout does not spend slot; matured OOS one-shot; restart marks unfinished failed; retry reuses sealed snapshot/manifest; deterministic repeat | **Pass in browser/backend tests.** Semantic similarity detection between close but non-identical hypotheses is not implemented; rename/clone family reset permutations and maximum-budget exhaustion not all run in browser. |
| Alerts | Seven supported sources × three intervals; create, persistence, check, fire, acknowledgement, repeat check, edit/delete/rearm; bonus threshold | **Pass for supported sources and one-shot lifecycle.** Competing manual requests forced through a deterministic concurrent read barrier: exactly one reports a new firing. Scheduler itself was disabled; overlap behavior is simulated with two API requests. Correction-after-fire and process death mid-transaction remain untested. |
| Research old versus PIT | Prior M14.7 report compares eight dates and stored/live/PIT sets | **Not independently rerun on R2 data.** Round 2 records the known differences and causes in `E2E_R2_FINANCIAL_CORRECTNESS.md`; old snapshot rows were not rewritten. |

## Failure injection, security, and persistence

| Scenario | Result |
|---|---|
| API 404, unsupported 405, malformed JSON | JSON error responses; no SPA shell and malformed write did not create an alert. |
| Host/Origin | Hostile Host returned 421; foreign Origin write returned 403; alert table remained empty. |
| Static traversal | Encoded `/.env` request did not return environment/database secrets. |
| Drawing network failure | Local edit stayed visible, unsaved state was actionable, retry saved it. Trace and screenshot are retained. |
| PostgreSQL restart | Verified exact R2 container label and named volume; workspace, drawing, and alert recovered through a new API process and browser invocation. |
| Invalid/outdated workspace document | Existing schema/merge tests cover malformed and stale versions; R2 did not exhaust every imported shape/schema version. |
| Database outage mid-save, failed migration, partial authorized import, app process kill during transaction | **Not tested.** |
| Raw invalid HTTP header syntax / oversized bodies / unsupported content encodings | **Not tested.** |
| Network exposure/authentication | Binding is loopback and app intentionally has no login. No external-interface deployment or proxy configuration was tested. |

## Performance and endurance coverage

| Measurement | Runs / scenario | Result |
|---|---|---|
| NFR-11 warm/cold chart open | 30 each, 10 synthetic symbols, 2,610 bars, cold includes fresh API/browser process (API startup excluded) | Warm P95 184 ms ≤1 s; cold P95 506 ms ≤3 s. |
| 1/4/16 layout benchmark | 30 warm + 30 cold per layout; 2,610 bars | Warm P95 185/495/1,772 ms; cold P95 201/528/1,785 ms; pan P5 61 FPS. |
| Loaded charts | 1/4/16, 7 indicators, 4 compares, 4 MAs, 120 drawings per symbol | One sample open 1,244/1,136/2,348 ms; pan 62 FPS; 16-chart JS heap after GC 242.9 MB. |
| Endurance | Eight symbol switches, drawing create/delete, layout changes | Heap samples 12.78→15.86 MB over the bounded run; canvas count returned to 7 at each one-chart sample. |
| Search latency; workspace save/restore latency; screening/research execution latency; alert evaluation duration; memory after hundreds/thousands of cycles | **Not reported as repeated timing distributions.** Functional correctness was exercised, but duration evidence is insufficient for a performance pass on these cases. |

## Accessibility and visual interaction coverage

Reduced-motion preference, keyboard open/tab/Escape/focus restore for mobile More, focusable controls/labels in the exercised flows, and a 720×450 desktop-equivalent reflow for dashboard/chart/Studio were checked. This equivalent viewport approximates 200% desktop zoom; actual browser zoom behavior was not directly set. We did not complete screen-reader flows, page-by-page WCAG contrast calculations, high-contrast mode, all dialogs/tooltips/dropdowns at all sizes/themes, touch-only drawing, or full keyboard-only tasks across every route.

## Coverage comparison with Round 1

Round 1: 26 desktop route renders; 12 drawing workflows; 815 backend tests; 108 Playwright passes plus six opt-in layout benchmarks run separately; known gaps around full tablet/theme sweep, reduced motion, simultaneous alert evaluation, loaded drawings, navigation soak, real database restart, and CLI repeatability. Round 2: same route inventory × four sizes × two themes = 208 states; 833 backend passes; dedicated tests/evidence for all listed gap areas except those explicitly marked partial/not tested above. Round 2 retained the same definition of route coverage: a rendered route is not itself proof of a complete workflow.
