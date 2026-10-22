# OpenChart ↔ Wickstreet Interaction Parity

**Date:** 2026-10-19 · **Wickstreet:** Chromium (Playwright), 1440×900, synthetic data in a disposable database · **OpenChart:** documentation only.

## Limits of this comparison

The OpenChart desktop app was not run ([clean-room record](OPENCHART_CLEAN_ROOM_RECORD.md) §1). So every OpenChart column below says what the documents state, or "documentation-only / unverified". No OpenChart action count, timing or friction rating exists in this audit, and none is estimated. The Wickstreet columns are measured in the browser.

"Actions" counts clicks, key presses that change state, and typed words (one per word). Moving the mouse does not count.

## 1. Core journeys

### J1. Open the application and find a symbol

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | "Search for the instrument you want to chart" (R3). Interface not described. | — |
| Start control | Unverified | Visible "Symbol or company…" box in the nav bar; or type anywhere on the chart; `/`; Ctrl/⌘+K |
| Actions | Unverified | 3: type "tc", Enter |
| Feedback | Unverified | Dialog lists matches with names and exchange; "↑↓ choose · Enter open · Esc close" |
| Context kept | Unverified | Range, interval, MAs, studies stay; URL changes to `/chart/TCS` |
| Keyboard | Unverified | Complete |
| Friction | — | Low |

### J2. Open a chart and inspect history

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | Not described | — |
| Actions | Unverified | 1 click per range (1W … MAX); wheel or drag to zoom and pan |
| Errors found | — | **D1 (fixed):** 1W and 1M were empty when stored data lagged today. **D2 (fixed):** MA200 drew only the last 10 bars of a 1Y chart |
| Remaining friction | — | Panning stops at the range start; the user must click MAX to see older bars (backlog BL-01) |

### J3. Add and configure several indicators

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | "Add indicators" (R1); "multiple panes per chart" (R7); parameters not described | — |
| Actions | Unverified | Indicators (or Alt+I) 1 · type a word 1 · Enter or click 1 → 3 per study. Parameter fields sit under "Active" in the same dialog |
| Discoverability | — | "Indicators" button in the header; RSI, MACD, ADX also as checkboxes above the chart |
| Errors found | — | **D3 (fixed):** RSI added from the dialog read twice in the crosshair box, and its checkbox could not turn it off. **D5 (fixed):** Alt+I did nothing after a checkbox click. **D10 (fixed):** Enter in the search did nothing |
| Remaining friction | — | Dialog studies have no legend on the chart (BL-03); no colour or hide (BL-04); RSI and MACD periods are fixed (backend series) |

### J4. Draw and edit a trendline

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | "Draw a line or zone" (R1); drawing menu: Create alert, Drawing style, Lock, Hide, Delete (R7) | — |
| Actions | Unverified | Create 3 (Alt+T, 2 clicks) · select 1 · move 1 drag · resize 1 drag · restyle 2 (right-click, swatch) · undo 1 · delete 1 |
| Feedback | — | Handles on selection; tool returns to Select after one drawing; "Saved ✓ hh:mm" |
| Errors found | — | **D6 (fixed):** a double-click saved a zero-length line |
| Persistence | Local database (R7) | Server document; survives reload, interval change and a second browser |
| Gap | — | No Lock, Hide or Create alert in the drawing menu |

### J5. Use the context menu to change the chart

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | Drawing menu only (R7) | — |
| Actions | Unverified | 2: right-click, pick (Reset view, Indicators…, Alert at this price…, Normal / Log / Percent scale) |
| Keyboard | Unverified | ContextMenu key or Shift+F10; Esc closes and returns focus |

### J6. Compare two securities

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | 16 stocks on a % chart (R7, demo image) | — |
| Actions | Unverified | Compare 1 · type 1 · Enter 1 → 3; remove 1 (× on the chip) |
| Feedback | — | Chip "E2E10Y5 +19.57%" in the header; % scale on request |
| Friction | — | On the % scale each MA starts from its own first value (D7, deferred); limit of 4 compared symbols |

### J7. Configure a multi-chart layout

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | "Expand to a 4×4 grid" (R1); four-panel image (R7) | — |
| Actions | Unverified | Layout select 1 · per cell: click 1, type 1, Enter 1 → 3 per symbol; sync: 1 click per checkbox |
| Errors found | — | **D8 (fixed):** with symbol sync off, cells without their own symbol followed the active chart, so one search changed 15 of 16 charts. **D9 (fixed):** a synced crosshair box stuck after a dialog opened over a chart |
| Remaining friction | — | No drawing rail in grids (keys only, BL-02); type, scale, MA and study controls apply to the active chart only and are hidden in grids; each 4×4 cell spends about 50 of its 180 px on its own header |

### J8. Save and restore the working environment

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | Strategies, alerts and research in a local database (R7) | — |
| Actions | Unverified | 0: autosave. A new browser context opened `/chart/INFY` with 4 studies and the saved layout |
| Feedback | — | "Saved ✓ hh:mm"; "Not saved" with Retry on failure (R2 audit) |

### J9. Create and manage an alert

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | Describe it to an agent, or create it from the sidebar; edit later; Once/Repeat; Enabled; Feed (R4, R7, R8) | — |
| Create | Unverified | 3: right-click at a price, "Alert at this price…", Add alert. The form prefills Close, crosses above, the price and Daily |
| View | Unverified | Alerts tab: "INFY Close crosses above 281.34 · Daily — Watching bars after 2026-08-07" |
| Edit | Documented (R4) | Not possible; delete and create again |
| Delete | Unverified | 1 |
| Fired state | Feed (R4) | Fired alerts show with Re-arm; no history list |
| Model difference | Runtime monitoring while the app runs | Daily evaluation on complete bars (by design) |

### J10. Move between charts, watchlist and analysis views

| | OpenChart | Wickstreet (measured) |
|---|---|---|
| Reference | Sidebar and Feed (R4) | — |
| Watchlist → chart | Unverified | 1 click in the Watchlist tab |
| Chart → Momentum25 view | No equivalent | Details tab: readiness, momentum and setup scores, gate failures, "Why it ranks"; link to `/stock/<symbol>` (1 click) |
| Research screens | No equivalent | "Research" menu in the nav bar |

## 2. Interaction scores (documented interactions only)

Score only where OpenChart documents the interaction. Rubric: 0 missing or unusable; 1 major gap; 2 works with real friction; 3 comparable; 4 comparable or better.

| # | Interaction the reference documents | Wickstreet | Score |
|---|---|---|---|
| B-1 | Drawing menu: Create alert, Drawing style, Lock, Hide, Delete | Style (colour, width) and Delete; three of five items missing | 2 |
| B-2 | Create an alert from the sidebar | Alerts tab, plus prefilled "Alert at this price…" from the chart | 3 |
| B-3 | Edit an alert later | Not possible | 1 |
| B-4 | Alert rule state: Once/Repeat, Enabled | One-shot and Re-arm; no pause | 2 |
| B-5 | Draw a line or zone and alert when price crosses it | Not possible | 0 |
| B-6 | Several panes per chart | Checkbox row and dialog; one owner per pane after D3 | 3 |
| B-7 | 4×4 workspace | Works; per-cell symbols after D8; no drawing rail; heavy cell headers | 2 |
| B-8 | Alert events in one place | Fired state only | 2 |

n = 8. Distribution: one 0, one 1, four 2s, two 3s. Mean 1.9. Before this audit's fixes, B-6 and B-7 scored 2 and 1.

The ten journeys above have no OpenChart measurements, so they carry no parity score. They are a Wickstreet friction record.

## 3. Keyboard and accessibility notes from the journeys

- Every journey except freehand drawing can be done by keyboard. The chart must have focus for pan, zoom and drawing keys (click or Tab).
- Workspace keys now work after a click on any checkbox or radio (D5).
- Drawing menus have named items (`Indigo`, `Width 2`, `Delete`) with menu roles.
- Grid cells have accessible names (`Chart c2: INFY`).
- The text-note tool uses the browser's native prompt (BL-05).
