# OpenChart ↔ Wickstreet Parity Matrix

**Date:** 2026-10-19 · **Wickstreet:** branch `wickstreet/m10-m11`, after the fixes in this audit · **OpenChart evidence:** documentation only (R1–R9 in the [clean-room record](OPENCHART_CLEAN_ROOM_RECORD.md)).

## How to read this

- **OpenChart evidence** gives the source ID and its confidence: *Doc* (stated in words), *Ill.* (shown in a product image, possibly a demo), *Soon* (listed as coming soon), *Unv.* (no evidence).
- **Wickstreet evidence** is a browser observation from this audit (screenshot names in `audit-evidence/openchart-parity/`) or an E2E test.
- **Class:** Full, Partial, Alternative, Missing, Out of scope, Unverified (definitions in the [audit brief](OPENCHART_COMPATIBILITY_AUDIT.md#method)).
- **Cap.** is the 0–4 capability score. It is given only for in-scope rows with documented or illustrated OpenChart evidence. Out of scope, Alternative and Unverified rows have no score and never count as parity.
- **Priority:** P1 closes a gap users hit often; P2 completes a workflow; P3 is nice to have. **Effort:** S (≤1 day), M (≤1 week), L (more).

## A. Application shell and navigation

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| A-01 | Product form | Desktop app for macOS and Windows; local runtime (R3, Doc) | Self-hosted web app on loopback; any browser (ADR-012) | Alternative | — | — | — | Keep. A browser app needs no install and serves several windows. |
| A-02 | Sidebar with lists (alerts, schedules) | Sidebar; lists can be sorted (R4, R8, Doc) | Right side panel: Watchlist, Details, Alerts tabs; closable (`ws-chart-desktop-1440.png`) | Partial | — | P3 | S | Scored once, as H-02. Add sorting to the watchlist and alert lists. |
| A-03 | Settings: models, data providers, permissions | Settings → Models, Data Providers, Permissions (R3, Doc) | No settings screen. Data import is a CLI; theme in the nav bar | Out of scope | — | — | — | Agents and provider choice are excluded (A1 §4). |
| A-04 | Feed of alert events and agent posts | "The Feed brings alert events and Agent posts together" (R4, Doc) | Alert list shows the fired state; no event history | Partial | — | P2 | M | Scored once, as I-10. Agent posts are out of scope. |
| A-05 | In-app changelog and update button | Settings → Changelog; update button (R8, Doc) | `v0.2.0` in the nav bar; no changelog screen | Out of scope | — | — | — | Releases are git tags; not a product feature. |

## B. Symbol search and instrument discovery

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| B-01 | Search for an instrument | "Search for the instrument you want to chart" (R3, Doc); no interface details | Type on the chart, `/` or Ctrl/⌘+K; ↑↓, Enter, Esc; nav-bar box too. "tc" + Enter opens TCS in 3 actions (`ws-symbol-search.png`) | Unverified | — | — | — | Wickstreet behaviour is strong; no reference to compare. |
| B-02 | Instrument universe | Binance and yfinance instruments; Cloud US equities (R5, Doc) | NSE equities from authorized EOD import | Alternative | — | — | — | Keep; NSE focus is the product. |

## C. Chart rendering and navigation

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| C-01 | Candlestick chart with volume | Candles with a volume pane (R7, Ill.) | Candles; Volume toggle adds a pane | Full | 3 | — | — | — |
| C-02 | Several panes per chart | "Multiple panes per chart"; Stochastic, RSI, MACD panes (R7, Doc/Ill.) | Up to 4 sub-panes plus volume; RSI, MACD, ADX, ATR from the backend; 12 browser panes | Full | 3 | — | — | — |
| C-03 | Percent-change comparison of many symbols | 16 stocks on one % chart (R7, Ill., demo) | Compare up to 4 symbols, rebased at the first shared bar; % scale (`ws-compare-percent.png`). MAs rebase at their own first value on the % scale (D7, deferred) | Partial | 2 | P2 | M | Fix D7 (one base for every series); consider a higher compare limit. |
| C-04 | Zoom, pan, reset, crosshair | No public description | Wheel zoom at the cursor and drag pan (library); ← → pan, Ctrl/⌘+↑↓ and +/− zoom, Alt+R reset; crosshair readout with OHLC and pane values | Unverified | — | — | — | — |
| C-05 | Scroll back through all history | No public description | A range loads only its own bars, so panning stops at the range start; MAX loads all | Unverified | — | P1 | M | Gap against the common charting convention: load full history once and make ranges visible windows (backlog BL-01). |

## D. Chart types, intervals and scales

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| D-01 | Intraday and real-time timeframes | "Any timeframe"; 04:00–16:00 demo axis; real-time US equities on Cloud (R5, R7) | Daily, weekly, monthly only | Out of scope | — | — | — | Excluded by A1 §4. Not a defect. |
| D-02 | Daily, weekly, monthly bars | Not documented | D, W, M; drawings keep their dates across intervals | Unverified | — | — | — | — |
| D-03 | Bars, line, area, Heikin-Ashi | Not documented | All four, plus candles; saved per chart | Unverified | — | — | — | — |
| D-04 | Log and percent scales | Not documented | Log and % buttons; chart context menu | Unverified | — | — | — | — |

## E. Indicators and technical studies

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| E-01 | Many indicators, no plan cap | "Unlimited indicators" (R1, R7, Doc) | 36 studies in 8 groups; overlays uncapped; sub-panes capped at 4 by design | Partial | 3 | — | — | Keep the pane cap; it protects the price pane's height. |
| E-02 | RSI | Named (R7, Ill.) | RSI (14) from the backend; the period cannot change | Partial | 2 | P2 | S–M | Offer a browser RSI with a period field; keep the backend RSI(14) for alerts (NFR-1a). |
| E-03 | MACD | Named; Tea example with EMA/SMA choice (R7, Ill.) | MACD (12,26,9) from the backend; parameters fixed | Partial | 2 | P2 | S–M | As E-02. |
| E-04 | Stochastic | Named (R7, Ill.) | Stochastic %K/%D, parameters editable | Full | 3 | — | — | — |
| E-05 | Keltner Channels | Named (R7, Ill.) | Keltner Channels | Full | 3 | — | — | — |
| E-06 | Anchored VWAP | Named (R7, Ill.) | Anchored VWAP and ±σ bands, anchor date field (daily bars, stated in the dialog) | Full | 3 | — | — | — |
| E-07 | Volume Profile | "Add indicators and Volume Profile" (R1, Doc) | None | Missing | 0 | P2 | M | Build a visible-range volume-by-price histogram from daily bars; label it daily-bar approximate. Needs a design-record entry. |
| E-08 | Squeeze Momentum | Named (R7, Ill.) | None (Bollinger and Keltner exist separately) | Missing | 0 | P3 | S | Possible later; public definitions vary, so define our own. |
| E-09 | Trend Cloud, Cycle Spectrum | Named (R7, Ill.); no definition published | None | Unverified | — | — | — | No public definition to compare against. |
| E-10 | Custom indicators in a language | Tea (R1, R2, Doc); Pine porting by agent (R7) | None | Out of scope | — | — | — | A1 §4; design record D8. |
| E-11 | Indicator search and grouping | Not documented | Search box, 8 groups, source label (browser/backend); Enter adds the first match (D10 fixed) | Unverified | — | — | — | — |
| E-12 | Legend on the chart for added studies | Not documented | Quick MAs have an on-chart legend; dialog studies show names and values only inside the dialog | Unverified | — | P1 | S | Gap against the common convention: show every study's name and last value above the price pane (backlog BL-03). |
| E-13 | Per-study colour, hide and restore | Not documented | Parameters only; remove, no hide; fixed colours | Unverified | — | P2 | M | Backlog BL-04. |

## F. Drawing and annotation tools

OpenChart names: line, zone, wedge, channels, Fibonacci levels, curves, freehand paths, polyline, curved line (R1, R7, R8). Wickstreet has 12 tools: trendline, ray, extended line, horizontal ray, horizontal line, vertical line, cross line, parallel channel, rectangle, Fib retracement, price range, text note.

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| F-01 | Line | "Draw a line" (R1, Doc) | Trendline, ray, extended, horizontal and vertical lines; full lifecycle passes (below) | Full | 3 | — | — | — |
| F-02 | Zone | "Draw … zone" (R1, Doc) | Rectangle; price range | Full | 3 | — | — | — |
| F-03 | Channel | Channels (R8, Doc) | Parallel channel (3 points) | Full | 3 | — | — | — |
| F-04 | Fibonacci levels | Fibonacci levels (R8, Doc) | Fib retracement, 7 levels | Full | 3 | — | — | — |
| F-05 | Wedge | Wedge, descending wedge (R7, Ill.) | None; two trendlines approximate it | Missing | 0 | P3 | S | A two-line wedge tool fits the existing model. |
| F-06 | Polyline / path | Polyline (R7, Ill.) | None | Missing | 0 | P3 | M | Needs variable point counts in the drawing schema. |
| F-07 | Curved line | Curves (R7, R8) | None | Missing | 0 | P3 | M | Low value for daily-bar analysis. |
| F-08 | Freehand pencil | Freehand paths (R7, R8) | None | Missing | 0 | P3 | M | Low value; many points per drawing. |
| F-09 | Drawing style | "Drawing style" menu item (R7, Ill.) | Six colours, four widths in the context menu; no dash style, no fill opacity | Partial | 2 | P2 | S | Add dash style; consider fill opacity for zones. |
| F-10 | Lock drawing | "Lock drawing" (R7, Ill.) | None | Missing | 0 | P2 | S | Prevents accidental moves; a boolean on the drawing. |
| F-11 | Hide drawing | "Hide drawing" (R7, Ill.) | None | Missing | 0 | P2 | S | A visibility flag, plus "show all". |
| F-12 | Delete drawing | "Delete drawing" (R7, Ill.) | Context menu, Delete/Backspace, rail bin | Full | 3 | — | — | — |
| F-13 | Alert from a drawing | "Create alert" on the drawing; price crossing a line, wedge, zone, channel, Fib level, curve or path (R1, R7, R8, Doc) | None. Alerts exist for close and five indicator series only | Missing | 0 | P2 | M–L | Capability gap, **not** authorised by this audit. Daily evaluation of "close crosses a horizontal line / leaves a rectangle" fits the M15 alert model; sloped lines need a price at each date. Needs an ADR-level decision. |
| F-14 | Text annotation | Not documented | Text note via a native browser prompt | Unverified | — | P2 | S | Replace the native prompt with an inline field (backlog BL-05). |
| F-15 | Undo and redo | Not documented | Ctrl/⌘+Z, Ctrl/⌘+Shift+Z, Ctrl+Y for drawing edits | Unverified | — | — | — | — |

Wickstreet drawing lifecycle (trendline, RELIANCE, 1440×900): create ✓ (Alt+T, two clicks), select ✓, move ✓, resize by handle ✓, restyle ✓ (menu), undo ✓, redo ✓, saved ✓ (server revision bumps), reload ✓, delete ✓. Double-click guard ✓ after D6. Persists across D/W ✓ (`ws-draw-weekly.png`). Drawings belong to the symbol, so every panel that shows the symbol shows them ✓ (`ws-layout-4x4.png`). Drawings are stored at traded prices and follow splits and bonuses (ADR-013 §5, M11 E2E).

## G. Multi-chart layouts and synchronisation

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| G-01 | Up to 4×4 grid | "Expand to a 4×4 grid" (R1, Doc); four-panel image (R7) | 1, 2 side by side, 2 stacked, 2×2, 3×3, 4×4; 16 charts in 36 ms after the select | Full | 3 | — | — | — |
| G-02 | Symbol, interval, crosshair sync | Not documented | Three Sync checkboxes; crosshair on by default | Unverified | — | — | — | — |
| G-03 | Per-panel symbols | Four different symbols shown (R7, Ill.) | Click a cell, type, Enter. Before D8, unsaved cells followed the active chart | Full | 3 | — | — | Fixed (D8). |
| G-04 | Resize panels | Not documented | Fixed equal cells; no splitters | Unverified | — | P3 | M | Common convention; low priority. |
| G-05 | Drawing in a grid cell | Not documented | Works by keyboard (Alt+T …) only; the rail is hidden in grids | Unverified | — | P1 | S | Show the drawing rail for the active cell (backlog BL-02). |

## H. Watchlists and symbol management

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| H-01 | Watchlist beside the chart | Watchlist and heat map in the side panel (R7, Ill.); Semantic Watchlist coming soon (R2) | Watchlist tab with last price and change; Alt+W adds or removes; click opens the chart; `/watchlist` page | Full | 3 | — | — | — |
| H-02 | Sort and order lists | "Sort sidebar lists" (R8, Doc) | No sort, no manual order, one list only | Partial | 1 | P2 | S–M | Sort by symbol, change and rank; manual order later. |
| H-03 | Heat map | Illustrated (R7) | None; `/market` has breadth | Missing | — | P3 | M | Not scored: shown only inside an AI dashboard demo, so it may not be a shipped feature. |
| H-04 | Semantic / AI watchlist | Coming soon (R2) | None | Out of scope | — | — | — | Agent feature. |

## I. Alerts

Wickstreet alerts are evaluated once a day on complete bars (M15, ADR-014 scope). OpenChart evaluates while its desktop runtime runs (R3, R4). Real-time monitoring is excluded for Wickstreet and is not scored as a defect.

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| I-01 | Price alerts | "Price … alerts" (R1, R4, Doc) | Close crosses above/below, is above/below; D/W/M; price levels rescale with splits | Full | 3 | — | — | — |
| I-02 | Indicator alerts | "Indicator alerts" (R1, R4, Doc) | RSI, ADX, ATR, MACD line/signal/histogram (backend series only, by design NFR-1a) | Partial | 2 | P3 | M | Keep backend-only sources; add backend series only through ADR. |
| I-03 | Drawing alerts | See F-13 | None | Missing | 0 | P2 | M–L | See F-13. |
| I-04 | Pattern alerts | "Patterns" (R4, Doc) | None; pattern detection exists on the analysis screen | Missing | 0 | P3 | L | Would need deterministic pattern events; research first. |
| I-05 | Create an alert from the UI | "Create alerts from the sidebar" (R4, R8) | Alerts tab; chart menu "Alert at this price…" prefills the level: 3 actions (`ws-alert-created-from-chart.png`) | Full | 3 | — | — | — |
| I-06 | Edit an alert later | "Edit those settings later" (R4) | No edit; delete and create again | Missing | 1 | P1 | S–M | Add edit for armed alerts (needs a `PATCH` endpoint). |
| I-07 | Once / Repeat | Once/Repeat options (R7, Ill.) | One-shot, then "Re-arm" | Partial | 2 | P3 | S | A repeat mode re-arms after each firing. |
| I-08 | Enable / disable | Enabled toggle (R7, Ill.) | None | Missing | 1 | P3 | S | A paused state. |
| I-09 | Notifications | Notification and sounds (R4, R8) | In-app list only; no delivery outside the app | Partial | 1 | P3 | M | Browser notifications on next open; no external delivery (A1). |
| I-10 | Alert history | Feed of alert events (R4) | Fired state on the alert; no history list | Partial | 2 | P2 | S–M | Keep fired events; list them in the Alerts tab. |
| I-11 | Show the alert level on the chart | Not documented | Not shown | Unverified | — | P2 | S | Draw armed price alerts as dashed lines (backlog BL-06). |
| I-12 | Agent research on trigger | (R4, Doc) | None | Out of scope | — | — | — | Agents excluded. |

## J. Workspace saving and restoration

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| J-01 | Saved state | "Stored in a local database on the desktop" (R7, Doc) | Server documents with autosave, "Saved ✓ hh:mm", ETag conflicts, a second browser restores symbol, layout and studies | Full | 4 | — | — | Wickstreet's multi-window conflict protection goes beyond the documented reference. |
| J-02 | Named layouts / several workspaces | Not documented | One workspace (`default`) | Unverified | — | P3 | M | — |

## K. Context menus and keyboard shortcuts

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| K-01 | Drawing context menu | Create alert, Drawing style, Lock, Hide, Delete (R7, Ill.) | Colour, width, edit text, Delete; keyboard: ContextMenu key, Shift+F10 | Partial | — | — | — | Scored through F-09 to F-13. |
| K-02 | Chart context menu | Not documented | Reset view, Indicators…, Alert at this price…, three scales | Unverified | — | — | — | — |
| K-03 | Published shortcuts | None published | 20 shortcuts; `?` shows them | Unverified | — | — | — | — |

## L–M. Visual design, accessibility, performance

No OpenChart evidence beyond the layout of marketing images. All rows **Unverified**. Wickstreet findings are in the [UX audit](OPENCHART_UX_VISUAL_AUDIT.md).

## N. Data providers

| ID | Capability | OpenChart (evidence) | Wickstreet | Class | Cap. | Pri. | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|
| N-01 | Choice of provider | Binance, yfinance, Cloud (R5, Doc) | Authorized NSE CSV import by CLI; direct NSE refresh off by default | Alternative | — | — | — | Keep; NSE terms decide (M16 report). |
| N-02 | Data caveats shown | Provider caveats in docs (R5) | Data version on every chart; freshness; adjusted prices with the schedule; provenance labels in Studio | Alternative | — | — | — | Beyond the reference; keep visible. |

## O. Advanced features

| ID | Capability | OpenChart (evidence) | Class |
|---|---|---|---|
| O-01 | AI agents (Claude Code, Codex, Gemini) | R1, R2, R3 (Doc) | Out of scope |
| O-02 | Tea language, custom indicators and conditions | R1, R2 (Doc) | Out of scope |
| O-03 | Select and Explain (agent research on a range) | R6 (Doc) | Out of scope |
| O-04 | Schedules on a calendar; Copilot | R8 (Doc) | Out of scope |
| O-05 | Broker connection, order proposals | R2 (Soon), R7 (Ill.) | Out of scope |
| O-06 | Custom Index, Newsfeed, Option Tracker, Filing Intelligence | R2 (Soon) | Out of scope |

## Score summary (capability parity)

39 in-scope rows carry a score: C-01–C-03, E-01–E-08, F-01–F-13, G-01, G-03, H-01, H-02, I-01–I-10 and J-01. Each row scores Wickstreet against what OpenChart documents or illustrates, on the 0–4 rubric in the [audit report](OPENCHART_COMPATIBILITY_AUDIT.md#scoring-rubric).

| Area | Rows | Score 0 | 1 | 2 | 3 | 4 | Mean |
|---|---|---|---|---|---|---|---|
| Charts (C) | 3 | 0 | 0 | 1 | 2 | 0 | 2.7 |
| Indicators (E) | 8 | 2 | 0 | 2 | 4 | 0 | 2.0 |
| Drawings (F) | 13 | 7 | 0 | 1 | 5 | 0 | 1.3 |
| Layouts (G) | 2 | 0 | 0 | 0 | 2 | 0 | 3.0 |
| Watchlist (H) | 2 | 0 | 1 | 0 | 1 | 0 | 2.0 |
| Alerts (I) | 10 | 2 | 3 | 3 | 2 | 0 | 1.5 |
| Workspace (J) | 1 | 0 | 0 | 0 | 0 | 1 | 4.0 |
| **All** | **39** | **11** | **4** | **7** | **16** | **1** | **1.8** |

- 17 of 39 rows (44%) score 3 or 4.
- 24 of 39 rows (62%) score 2 or more.
- 11 of 39 rows (28%) are missing. Seven of them are drawing tools or drawing actions.

Not scored, and never counted as parity:
- 12 Out of scope rows: A-03, A-05, D-01, E-10, H-04, I-12, O-01–O-06.
- 4 Alternative rows: A-01, B-02, N-01, N-02.
- 19 Unverified rows: B-01, C-04, C-05, D-02–D-04, E-09, E-11–E-13, F-14, F-15, G-02, G-04, G-05, I-11, J-02, K-02, K-03. Groups L and M are wholly unverified.
- 4 rows reported without a score: A-02 (as H-02), A-04 (as I-10), H-03 (demo only), K-01 (through F-09–F-13).
