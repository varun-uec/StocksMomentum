# M11 Vertical Slice Report — Find → Analyse → Draw → Restore

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [M11 vertical-slice plan](../plans/2026-10-18-m11-vertical-slice-plan.md)
> **Status:** first major review gate (ADD A1 §27). Built and tested; the owner decides whether it passes.

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
| `localStorage` migration runs once; the server copy wins | **Pass** | E2E import test; import unit tests |
| An edit just before leaving the page | **Pass**: sent with `keepalive` | E2E "edit before leaving" test |
| No regression on existing screens (NFR-13) | **Pass** | 21 route tests; the stock page saves drawings to the server |
| No console errors, CSP violations or page errors | **Pass** | Every E2E test fails on any of them |
| NFR-11 chart open | **Pass** | Below |

## NFR-11 measurement

`e2e/nfr11-chart-open.spec.ts`, 30 runs per case across 10 symbols with 10 years of daily bars (2,610 bars each, synthetic, E2E clone only). "Open" runs from navigation start to the first frame after the price series holds its bars (`wickstreet:chart-painted`).

| Case | Runs | P50 | P95 | Max | Target |
|---|---|---|---|---|---|
| Warm (assets cached, symbol data not cached) | 30 | 83 ms | 115 ms | 115 ms | P95 ≤ 1 s |
| Cold (new browser context per run) | 30 | 135 ms | 156 ms | 157 ms | P95 ≤ 3 s (provisional) |

Environment: Apple M4 Pro × 14, 48 GB RAM; Darwin 27.0.0 arm64; Chromium 153.0.8010.12 headless; API on the same machine, served by uvicorn. Limitation: "cold" covers the browser only. The API process was not restarted between runs. The real dataset holds 6.9 years per symbol (2019-10-01 →), so 10 years needed synthetic symbols.

## Test evidence

| Suite | Result |
|---|---|
| Backend `pytest` (full, PostgreSQL) | 684 passed (+23 document-API contract tests, including a 5-writer race where exactly one wins; +2 OHLCV range tests) |
| `ruff check`, `mypy --strict` (234 files), import contracts | clean |
| Web Vitest | 49 passed: merge, document store (debounce, 412 merge, conflict, retry), import, drawing geometry, schema compatibility |
| Web ESLint, build | clean |
| Playwright E2E | 37 passed; the M11 spec passed 8 repetitions in a row (56/56) |

## Defects found and fixed during M11

1. **MAX showed only 500 bars.** With no `from` date, `GetSecurityOHLCV` capped the series at 500 rows. MAX now returns the whole stored series. This was found by the NFR-11 measurement.
2. **A fast second click lost a drawing anchor.** Lightweight Charts drops a second click that comes inside its double-click window, even far from the first. Anchors are now placed from native click events.
3. **An action in the same frame as a tool change could start a stray draft.** The tool and drawing refs now change in the same step as the state.
4. **The chart blanked while a new range loaded.** It now keeps the previous bars on screen, and the footnote says "Loading price series…" until the new range arrives.

Items 2 and 3 were found by repeated E2E runs, which exposed intermittent failures. Both had real causes and were fixed at the cause.

## Decisions taken by default (please confirm or change)

| Decision | Why |
|---|---|
| Presentation settings now follow the **chart**, not the symbol: each screen has its own chart id (`main`, `stock`, `analysis`, `elliott-wave`) | ADR-013 §5. Indicators stay when you change symbol, as TradingView users expect. Drawings still follow the symbol. |
| The import moves **drawings only**; old per-symbol MA, pane and overlay settings start from defaults | Per-symbol settings have no faithful per-chart mapping. Drawings are the owner's work; settings are conveniences. The old keys stay as backup. |
| Presentation conflicts merge silently, field by field; only drawing conflicts ask | A prompt for an MA toggle would be noise. Recorded in ADR-013 §5. |
| `428` for any save without a precondition, including a create | Every save states its intent. Recorded in ADR-013 §5. |
| A "Chart" item in the nav bar; "Open in chart" on stock pages; on `/chart` the nav search changes the chart | Makes the workspace reachable without changing the existing screens' search behaviour. |
| The drawing tools stay in the chart's existing toolbar, not the left rail of the M9 wireframe | The left rail belongs to the M12 shell, where it can be built once for all tools. |

## Not in M11 (as planned)

Weekly bars (M11b), more drawing tools, undo and redo, the left drawing rail and the full shell (M12), multi-chart (M13), alerts (M15).

## Known limits to carry forward

- **Chart prices are unadjusted.** `/securities/{s}/ohlcv` serves raw bhavcopy prices. ADR-013 §4 says the chart uses the same corporate-action-adjusted series as screening. This is due in M11b, together with weekly bars and `data_version`.
- **`/` opens search in M11.** M13 moves `/` to the indicator dialog, once that exists (design record D7).
- **Drawings are not keyboard-movable yet** (arrow keys). That comes in M13.

## Decisions for the owner

1. **M11 gate:** does Find → Analyse → Draw → Restore feel professional enough to build on?
2. **ADR-013:** accept it, now that M10 and M11 run on it?
3. **The defaults above:** confirm or change.
