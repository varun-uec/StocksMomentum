# M11 Vertical Slice Report — Find → Analyse → Draw → Restore

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [M11 vertical-slice plan](../plans/2026-10-18-m11-vertical-slice-plan.md)
> **Status:** first major review gate (ADD A1 §27). The owner accepted M9, M10 and ADR-013, and made M11 acceptance conditional on four corrections (C1–C4 below). The corrections are built and tested; the gate closes on the owner's final review.

## Try it

```bash
make up                         # or: docker compose up --build api
open http://localhost:8000/chart
```

1. **Find:** start typing a symbol anywhere on the chart (or press `/` or Ctrl/⌘+K). Pick with ↑/↓ and press Enter.
2. **Analyse:** change the range (1M … MAX), tick moving averages, add RSI or MACD.
3. **Draw:** pick Trendline, Horizontal ray, Rectangle or Fib retracement, and click on the chart. Click a drawing to select it, drag it or its handles, and press Delete to remove it.
4. **Restore:** reload, close the tab, or open `http://localhost:8000/chart` in another browser. The last symbol opens with its settings and drawings. The header shows "Saved ✓ hh:mm".

Drawings belong to the symbol, so the same drawings also show on `/stock/<symbol>` and the analysis screen.

## Acceptance

| Plan item | Result | Evidence |
|---|---|---|
| Find: keyboard-first search opens `/chart/:symbol` | **Pass** | E2E "Find" test: typing, Ctrl+K, Esc, Enter |
| Analyse: 1D bars, server RSI/MACD, browser overlays display-only | **Pass** | E2E restore test; panes still from `/stock/{s}/indicators/series` |
| Draw: 4 tools plus select, move, delete | **Pass** | E2E: draw two, drag one, delete one; geometry unit tests |
| Restore: reload and a second browser | **Pass** | E2E: reload and a fresh browser context both restore range, MAs, panes and drawings |
| Two windows, different drawings | **Pass**: merged silently | E2E merge test |
| Two windows, same drawing | **Pass**: conflict notice; the chosen side is saved | E2E conflict test; store unit tests |
| Two windows, different chart settings | **Pass**: merged silently *(C3)* | E2E settings-merge test |
| Two windows, same chart setting | **Pass**: conflict notice; nothing is overwritten *(C3)* | E2E settings-conflict test; merge unit tests |
| A conflict on a research screen | **Pass**: the same notice shows on every screen *(C3)* | E2E test on `/stock/HDFCBANK` |
| `localStorage` migration runs once; the server copy wins | **Pass**: drawings and chart settings *(C2)* | E2E import tests; import unit tests |
| Chart prices match the screener's adjusted series | **Pass** *(C1)* | Parity unit test against the indicator pipeline; GOLDIAM below |
| An edit just before leaving the page | **Pass**: sent with `keepalive` | E2E "edit before leaving" test |
| No regression on existing screens (NFR-13) | **Pass** | 21 route tests; the stock page saves drawings to the server |
| No console errors, CSP violations or page errors | **Pass** | Every E2E test fails on any of them |
| NFR-11 chart open | **Pass** | Below |

## NFR-11 measurement

`e2e/nfr11-chart-open.spec.ts`, 30 runs per case across 10 symbols with 10 years of daily bars (2,610 bars each, synthetic, E2E clone only). "Open" runs from navigation start to the first frame after the price series holds its bars (`wickstreet:chart-painted`).

| Case | Runs | P50 | P95 | Max | Target |
|---|---|---|---|---|---|
| Warm (assets cached, symbol data not cached) | 30 | 83 ms | 115 ms | 117 ms | P95 ≤ 1 s |
| Cold (new browser context per run) | 30 | 143 ms | 152 ms | 152 ms | P95 ≤ 3 s (provisional) |

Measured again after the corrections; the first run gave warm P95 115 ms and cold P95 156 ms. Environment: Apple M4 Pro × 14, 48 GB RAM; Darwin 27.0.0 arm64; Chromium 153.0.8010.12 headless; API on the same machine, served by uvicorn. Limitation: "cold" covers the browser only. The API process was not restarted between runs. The real dataset holds 6.9 years per symbol (2019-10-01 →), so 10 years needed synthetic symbols.

## Test evidence

| Suite | Result |
|---|---|
| Backend `pytest` (full, PostgreSQL) | 688 passed (+23 document-API contract tests, including a 5-writer race where exactly one wins; +2 OHLCV range tests; +4 adjusted-bar tests) |
| `ruff check`, `mypy --strict` (234 files), import contracts | clean |
| Web Vitest | 64 passed: merge (field conflicts, navigation fields), document store (debounce, 412 merge, conflict, retry, no-op edit), drawing and settings import, drawing geometry, schema compatibility |
| Web ESLint, build | clean |
| Playwright E2E | 41 passed; the M11 spec passed 5 repetitions in a row (55/55) |

## Defects found and fixed during M11

1. **MAX showed only 500 bars.** With no `from` date, `GetSecurityOHLCV` capped the series at 500 rows. MAX now returns the whole stored series. This was found by the NFR-11 measurement.
2. **A fast second click lost a drawing anchor.** Lightweight Charts drops a second click that comes inside its double-click window, even far from the first. Anchors are now placed from native click events.
3. **An action in the same frame as a tool change could start a stray draft.** The tool and drawing refs now change in the same step as the state.
4. **The chart blanked while a new range loaded.** It now keeps the previous bars on screen, and the footnote says "Loading price series…" until the new range arrives.

Items 2 and 3 were found by repeated E2E runs, which exposed intermittent failures. Both had real causes and were fixed at the cause.

## Corrections after the owner's review

| # | Owner's condition | Fix | Evidence |
|---|---|---|---|
| C1 | Chart prices were unadjusted; the screener reads adjusted data | `GET /securities/{s}/ohlcv` applies `adj_factor` as the indicator pipeline does: price × factor, volume ÷ factor. ADR-013 §4. | Parity unit test; GOLDIAM's 1:5 split on 2022-03-28 showed as 790.80 → 173.70 (−78%); it now shows as 118.62 → 130.28 (+9.8%, the real move). |
| C2 | Keep compatible chart settings in the one-time migration, not only drawings | Range, moving averages and panes import to every chart; indicators and the signal preset to `analysis`. Each chart takes the setting chosen on the most symbols. Only charts the server lacks are added. ADR-013 §5. | Unit tests; E2E import test with a second browser |
| C3 | Merging never silently overwrites competing changes to the same field | A setting both windows changed differently now raises the conflict notice. The notice shows on every screen. | Unit tests; three E2E tests |
| C4 | `/` stays symbol search | Design record D9 supersedes D7. The M9 study note is amended. | — |

C3 also fixed three defects the new tests exposed:
1. **The chart did not show merged moving averages.** `PriceChart` read them once, at mount. After a merge, the next toggle saved the stale list and dropped the other window's change without a notice. Moving averages are now controlled by the saved settings, as panes already were.
2. **A drawing conflict on a research screen showed no notice.** Edits there were then ignored, silently. The notice now lives in the shared layout.
3. **Two first saves of one chart always conflicted.** A chart that did not exist yet now merges against the default chart, which is where both windows started.

**Exception, for the owner to confirm:** the open symbol of a chart and the active chart id record where the owner is, not what they set. For those two fields the newest window wins without a notice. Asking "which symbol should reopen?" would interrupt every switch between two windows.

## Decisions taken by default (please confirm or change)

| Decision | Why |
|---|---|
| Presentation settings follow the **chart**, not the symbol: each screen has its own chart id (`main`, `stock`, `analysis`, `elliott-wave`) | **Accepted by the owner.** Drawings still follow the symbol. |
| ~~The import moves drawings only~~ | **Changed by the owner (C2):** chart settings are imported too. |
| ~~Presentation conflicts merge silently~~ | **Changed by the owner (C3):** the same field changed differently asks. |
| `428` for any save without a precondition, including a create | **Accepted** (optimistic concurrency). |
| A "Chart" item in the nav bar; "Open in chart" on stock pages; on `/chart` the nav search changes the chart | **Accepted.** |
| The drawing tools stay in the chart's existing toolbar, not the left rail of the M9 wireframe | **Accepted:** the full rail is deferred to M12. |

## Not in M11 (as planned)

Weekly bars (M11b), more drawing tools, undo and redo, the left drawing rail and the full shell (M12), multi-chart (M13), alerts (M15).

## Known limits to carry forward

- **`data_version` is not on chart responses yet.** It comes in M11b, with weekly bars.
- **`/` stays symbol search** in every milestone (design record D9). M13 picks another shortcut for the indicator dialog.
- **GOLDIAM's 2026-07-10 bonus looks wrong.** The stored ratio is 0.75 (a 4:3 bonus), but the raw close fell only 10% that day (420.50 → 378.00). On adjusted data the close jumps +19.9%. Screening reads the same factor, so this is a data question, not a chart one. It needs a check against the NSE record.
- **The indicator panes span the whole history.** On a short range, the RSI pane stretches the time axis past the price bars. This was there before M11; it belongs to M12's shell work.
- **Drawings are not keyboard-movable yet** (arrow keys). That comes in M13.

## Decisions for the owner

1. **The navigation-field exception** in C3: confirm or change.
2. **M11 gate:** close it on the corrections above?
