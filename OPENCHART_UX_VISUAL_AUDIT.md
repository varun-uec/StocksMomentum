# OpenChart Parity: UX and Visual Quality Audit

**Date:** 2026-10-19 · **Browser:** Playwright Chromium · **Viewports:** 1440×900, 768×1024, 390×844 · **Data:** synthetic, disposable database.

## What can and cannot be compared

OpenChart's visual quality is known only from marketing images (R7). They show structure: a central candle chart with a lower oscillator pane, a side panel with a watchlist and heat map, a four-panel grid, a right-click menu on a drawing, and a dark theme. They do not show interaction states, empty or error states, focus, density at small sizes, or speed. So this audit **does not score product-quality parity** (sample size 0). It records Wickstreet's measured quality against the brief's checklist, and notes the few structural points the images allow.

Screenshots were used to understand layout only. No OpenChart artwork, icon or colour was copied.

## Structural comparison with the reference images

| Point | OpenChart images (R7) | Wickstreet | Note |
|---|---|---|---|
| Chart is the dominant element | Yes | Yes. At 1440×900 the plot takes 1068×600 px (49% of the window); header, toolbar rows and footer take the rest | Two toolbar rows above the chart (ranges, interval, type, scale, volume, MAs; then pane checkboxes) cost about 90 px |
| Side panel with a watchlist | Yes, with a heat map | Yes: Watchlist, Details, Alerts tabs; closable | Comparable structure |
| Oscillator pane under the price | Yes | Yes | — |
| Context menu on a drawing | Yes, five actions | Yes, colour, width, delete | Fewer actions (F-10, F-11, F-13) |
| Four-panel grid | Yes, each panel with its own panes | Yes; panes only on the active cell's settings | — |

## Wickstreet findings

### Information hierarchy and space

| Finding | Severity | Evidence | Disposition |
|---|---|---|---|
| Two rows of chart controls sit above every single chart; MA and pane checkboxes are always visible | P2 | `ws-chart-desktop-1440.png` | Backlog BL-14: collapse MAs and panes into the Indicators control or one row |
| Dialog studies have no legend on the chart | P1 | `ws-indicators-bb-ema-rsi.png` | Backlog BL-03 |
| The crosshair readout covered the price-axis labels | P2 | `ws-indicators-bb-ema-rsi.png` (before) | **Fixed (D4)**; regression test |
| The readout listed RSI twice | P2 | same | **Fixed (D3)** |
| 4×4 cells: about 50 of 180 px per cell are the cell header (symbol, range, interval) | P2 | `ws-layout-4x4.png` | Backlog BL-14 |
| The side panel keeps 290 px in a 4×4 layout | P3 | `ws-layout-4x4.png` | It can be closed (×); consider closing it by default for grids larger than 2×2 |

### Toolbars, menus and dialogs

| Finding | Severity | Evidence | Disposition |
|---|---|---|---|
| Drawing rail: 13 icon buttons with names and tooltips; a bin appears when a drawing is selected | Pass | `ws-draw-trendline-selected.png` | — |
| No drawing rail in grid layouts | P1 | `ws-layout-2x2.png` | Backlog BL-02 |
| Indicator dialog: search, groups, source label; Enter now adds the first match | Pass after D10 | `ws-indicator-dialog.png` | — |
| Text note uses the native `window.prompt` | P2 | observed in session | Backlog BL-05 |
| In the indicator dialog, Esc with text in the search box clears the text; a second Esc closes the dialog. This is the browser's own behaviour for search fields | P3 | observed in session | Consider one Esc to close, as in symbol search |
| Drawing and chart menus: named menu items, Esc closes, focus returns to the chart | Pass | `ws-draw-context-menu.png`, `ws-chart-context-menu.png` | — |

### Feedback and states

| Finding | Severity | Evidence | Disposition |
|---|---|---|---|
| "Saved ✓ hh:mm" after every change | Pass | all chart screenshots | — |
| An empty 1W or 1M chart showed no message when stored data lagged today | P1 | `ws-defect-range-1M-empty.png` | **Fixed (D1)**; the range now counts back from the last bar, so it cannot be empty while bars exist |
| Alert form explains the model: "Checked on complete bars after the last stored session…" | Pass | `ws-alert-created-from-chart.png` | — |
| Armed alerts are not drawn on the chart | P2 | same | Backlog BL-06 |
| A synced crosshair box stayed after a dialog closed | P2 | `ws-defect-stale-synced-readout.png` | **Fixed (D9)** |

### Keyboard and focus

| Finding | Severity | Disposition |
|---|---|---|
| Alt+I, Alt+W, `?` and type-to-search did nothing after a click on an MA or pane checkbox | P1 | **Fixed (D5)** |
| Chart focus ring visible; drawing nudges with arrow keys; Shift+F10 opens menus | Pass | — |
| Grid cells have names (`Chart c2: INFY`) | Pass | — |

### Responsive layouts

| Viewport | Plot area | Notes |
|---|---|---|
| 1440×900 | 1068×600 px, top at y = 198 | Side panel open |
| 768×1024 | 681×724 px, top at y = 254 | No page overflow (document width 753 px) |
| 390×844 | 319×544 px, top at y = 345 | Controls take the top 41% of the screen. The floating search button covers the plot, and the bottom navigation covers the RSI pane. Carried from the Round 2 audit (P2); backlog BL-14 |

### Stability and speed

- Switching to 4×4 rendered all 16 charts 36 ms after the layout change (one sample, synthetic data). The M13 benchmark (30 samples, 16-chart open P95 1.8 s) remains the reference figure.
- Changing a range no longer fetches: since D1, one request per symbol and interval loads the whole history (332 KB and 64 ms for 10 years of synthetic daily bars, against 27 KB for one year).
- During the session, screenshots stalled when macOS hid the browser window (2 frames per second). This was the test window, not Wickstreet: main-thread latency was 0.2 ms, and bringing the window forward restored 124 frames per second.

## Not checked

Screen-reader reading order, measured WCAG contrast, real 200% browser zoom, touch-only drawing, and dark-theme states for each new fix. The Round 2 audit lists the same open items. No accessibility conformance claim is made.
