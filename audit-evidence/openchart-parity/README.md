# OpenChart Parity Audit Evidence

**Date:** 2026-10-19 · **Report:** [OPENCHART_COMPATIBILITY_AUDIT.md](../../OPENCHART_COMPATIBILITY_AUDIT.md)

## What is here

Wickstreet screenshots only. No OpenChart screenshot, asset or page capture is stored. The OpenChart desktop app was not run, and the audit kept no copies of its marketing images ([clean-room record](../../OPENCHART_CLEAN_ROOM_RECORD.md)).

## How they were made

- The production web build was served by the real API on `127.0.0.1:8766`.
- The database was `wickstreet_parity_e2e` in a new PostgreSQL 16 container on tmpfs, port 60570. The E2E harness (`web/e2e/db.py verify`) checked that it was empty and marked it, then migrated and seeded it with synthetic bars that end on 2026-08-07. The application database was not touched. The container was removed after the audit.
- Browser: Playwright Chromium. Viewport 1440×900 unless the name says otherwise.
- Files named `ws-defect-*` show a defect before its fix. Files named `ws-fixed-*` show the same state after it.

## Index

| File | Shows |
|---|---|
| `ws-chart-desktop-1440.png` | Chart workspace, one chart, side panel |
| `ws-chart-tablet-768.png`, `ws-chart-mobile-390.png` | Same at tablet and phone widths |
| `ws-defect-range-1M-empty.png` | D1 before the fix: 1M range with 0 bars |
| `ws-fixed-range-1W.png` | D1 and D2 after the fix: 1W with bars and an MA200 value |
| `ws-indicator-dialog.png`, `ws-indicator-added-bb.png` | Indicator dialog and search |
| `ws-indicators-bb-ema-rsi.png` | D3 and D4 before the fix: RSI twice in the readout, readout over the price axis |
| `ws-fixed-readout.png` | D3 and D4 after the fix |
| `ws-draw-trendline-created.png`, `-selected.png`, `-moved-resized.png` | Trendline lifecycle |
| `ws-draw-context-menu.png` | Drawing menu: colours, widths, Delete |
| `ws-draw-weekly.png` | The same drawing on weekly bars |
| `ws-chart-context-menu.png` | Chart menu |
| `ws-symbol-search.png` | Symbol search after typing "tc" |
| `ws-compare-open.png`, `ws-compare-percent.png` | Compare dialog; compare line on the percent scale (D7 visible) |
| `ws-layout-2x2.png`, `ws-layout-2x2-sync-interval.png`, `ws-layout-3x3.png`, `ws-layout-4x4.png` | Layouts. The 2×2 sync and 4×4 images show D8 and D9 before the fix |
| `ws-fixed-layout-4x4.png` | D8 after the fix: new cells keep their own symbol |
| `ws-defect-stale-synced-readout.png` | D9 before the fix |
| `ws-alerts-tab-empty.png`, `ws-alert-created-from-chart.png` | Alerts tab; alert made from the chart menu |
| `ws-watchlist-panel.png` | Watchlist tab |

## Measurements

| Measure | Value | Method |
|---|---|---|
| 4×4 render after the layout change | 36 ms | One sample: time from `selectOption` to 16 chart elements |
| Full-history request, 10 years of daily bars | 332 KB, 64 ms | `curl` on loopback, one sample |
| One-year request (old behaviour) | 27 KB, 28 ms | Same |
| Plot area share at 1440×900 | 1068×600 px, 49% of the window | Bounding box |
| Phone controls height | 345 of 844 px (41%) | Bounding box of the plot top |

Single samples only. They show the order of size. The M13 benchmark (`../benchmarks/m13-bench.json`, 30 samples) and the NFR-11 benchmark (`../benchmarks/nfr11.json`) remain the performance references.
