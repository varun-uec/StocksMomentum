# M13 Report — Professional Charting

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [milestones](../plans/shipped/2026-10-18-wickstreet-milestones.md) · **Data semantics:** [ADR-013 §4–5](../architecture/adr/ADR-013-web-stack-and-chart-data.md)

## What changed

| Part | Result | Commit |
|---|---|---|
| Chart types and scales | Candles, bars, line, area, Heikin Ashi. Normal, log and percent scales. Saved per chart. | `bef81a6` |
| Drawing tools | Twelve tools: trendline, ray, extended line, horizontal ray and line, vertical line, cross line, parallel channel, rectangle, Fib retracement, price range, text note. Select, move, delete, keyboard moves, undo and redo. A drawing menu sets colour, width and text. | `1b11e7e` |
| Indicator dialog | The catalogue opens on the chart workspace with Alt+I. The analysis screen and the workspace share one hook, so an indicator draws the same on both. | `2f266c5` |
| Context menu | A right-click away from a drawing, or ContextMenu / Shift+F10, opens the chart's menu: reset view, indicators, price scale. | `263644b` |
| Monthly bars | `interval=1M`: one bar per calendar month. One domain function, `period_bars`, builds weekly and monthly bars by the same rules. Monthly indicators run on monthly bars. | `3566ce5` |
| Compare | Up to 4 symbols per chart, each a line rebased to the chart symbol's close at the first shared bar. Each chip shows the change since then. | `24cf16c` |
| Layouts | 1, 2 (side by side or stacked), 4, 9 and 16 charts. Each slot keeps its own symbol and settings. Symbol, interval and crosshair sync. | `f54f3c9` |
| Benchmark | 1/4/16-chart benchmark, opt-in (`M13_BENCH=1`). The E2E seed now has 16 synthetic 10-year symbols. | this commit |

## Benchmark: 1, 4 and 16 charts

The NFR-11 method: 30 runs per case; each chart holds a different symbol's 10 years of daily bars (2,610 bars, MAX range); crosshair sync on.

| Charts | Warm open P50 / P95 | Cold open P50 / P95 | Pan, frames per second (P5 / P50) | JS heap after GC |
|---|---|---|---|---|
| 1 | 153 / 170 ms | 192 / 202 ms | 62 / 62 | 11 MB |
| 4 | 477 / 489 ms | 519 / 543 ms | 61 / 62 | 24 MB |
| 16 | 1,762 / 1,801 ms | 1,794 / 1,830 ms | 61 / 62 | 76 MB |

- **Environment:** Apple M4 Pro × 14, 48 GB RAM; macOS (Darwin 27.0.0, arm64); headless Chromium 153; viewport 1280 × 720; commit `f54f3c9`; API and Postgres on the same machine.
- **Open** runs from navigation start to the N-th chart's first frame with bars. No chart marked twice (checked each run), so the N-th mark is the last chart.
- **Pan** is a 0.5 s drag across the active chart. Headless Chromium caps frames at the display rate (about 60 per second), so these figures show no dropped frames; they cannot show headroom above 60.
- **Memory** is the JS heap after a forced garbage collection (6 samples per case). Canvas backing stores are outside it.
- **NFR-11 still holds** for one chart: warm P95 170 ms (target ≤ 1 s), cold P95 202 ms (target ≤ 3 s). The test asserts it.
- **Open time grows about 110 ms per chart.** Each chart loads its symbol's whole history for `data_version` and the adjustment schedule, plus its indicator series, so 16 charts make about 48 requests. 1.8 s at 16 charts is usable. The first lever, if it matters, is one batched request per layout.

Raw results: `web/test-results/m13-bench.json` (not committed). To rerun: `M13_BENCH=1 npx playwright test e2e/m13-bench.spec.ts` with `E2E_DATABASE_URL` set.

## Decisions taken

- **Sync flags belong to the layout, not to each chart.** ADR-013 §5 listed them per chart. The owner syncs a grid, not a pair of charts, and one set of flags is simpler to read. Recorded in ADR-013 §5 (M13).
- **Synced values are applied when drawing.** A synced chart keeps its own saved symbol and interval, so turning sync off restores them.
- **Grid slot ids are stable** (`main`, `c2` … `c16`), so a chart keeps its settings when the grid changes size.
- **The crosshair goes through an in-memory bus**, not React state. A mouse move redraws the other charts' crosshairs without a re-render. The bus drops a repeat of the last date, which ends the echo when a chart reports a position set from code.
- **Grid cells are compact:** range and interval only. The single-chart layout keeps the full toolbar, the drawing rail and the footnote. The context menu and the shortcuts work in every cell.
- **Compare lines are display-only** and use the adjusted series of both symbols.
- **The benchmark is opt-in.** It takes about 5 minutes; the regular suite keeps the NFR-11 check.
- **No new dependency.** Native `<dialog>` and `<select>`, TanStack Query's `useQueries` and the chart library cover M13.

## Defects found and fixed

1. **Symbol search dropped the first letter of a fast search.** The dialog set its opening text in a passive effect, so a second key that arrived first replaced it, and the box kept the last search's text. Found while scripting the 4 × 4 screenshots ("NFYIPRO" for "WIPRO"). It now sets the text in a layout effect. A regression test types at full speed; without the fix it reads "NFY" for "INFY".
2. **The footnote called a running month "the last week".** Introduced with monthly bars in `3566ce5`; fixed in `f54f3c9`.
3. **Grid polish from screenshots:** range buttons wrapped onto two rows in 4 × 4 cells (now a select), and the readout covered the price scale (now a one-line readout on the left).

One test expectation of mine was wrong, not the code: January 2025 in the golden monthly test has 20 sessions from the 6th, not 23. The expectation was corrected by hand count.

Every 404 in the browser console on these screens is a GET for a drawings document that does not exist yet. That is the documented protocol (ADR-013 §5), not an error.

## Verification

| Suite | Result |
|---|---|
| Backend `pytest` | 719 passed |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Web Vitest | 91 passed (geometry, merge, traded prices, rebasing, crosshair bus) |
| Web ESLint, build | clean |
| Playwright | 63 passed (plus the opt-in benchmark, 6 passed) |
| NFR-11 chart open (30 runs each) | Warm P95 165 ms (target ≤ 1 s); cold P95 205 ms (target ≤ 3 s) |

## Not in M13

- `spec=` on the indicator-series endpoint. The dialog serves the browser catalogue, which is display-only; M15's alerts add it.
- Resizable panels and per-cell toolbars.
- A batched layout request.
