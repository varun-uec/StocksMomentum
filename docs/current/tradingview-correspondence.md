# TradingView correspondence and capability ledger

Plan: [2026-10-19 workstation plan](../history/plans/2026-10-19-tradingview-workstation-plan.md). Rule: TradingView structure, Wickstreet skin (design record D23).

The screen matrix (reference screen ↔ Wickstreet route) is added in phase A9.2. The capability ledger below starts at phase A1.3 from the baseline pass: on 2026-10-19 the full Playwright suite at `b3baee1` passed 164 tests on a fresh synthetic database, with 6 opt-in benchmark tests skipped (`M13_BENCH`). BL-01..BL-15 and the OpenChart fixes pass where each one is built today. Each relocation phase updates its rows in the same commit. A phase is not done while a row it touched is unverified.

Columns: **Prev** = location before the transformation. **Now** = current primary place. **No-nav** = the user finishes the task without leaving the view. **Verified** = the spec that proves it, or a manual check.

## Chart toolbar and chart controls

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| C1 | Symbol title (`h1`), opens search | /chart header | /chart header | Click symbol, type, `/`, Ctrl/⌘+K | y | `searchSecurities` | m11-slice "Find" | pass |
| C2 | Company name, last close, change % | /chart header | /chart header | Next to symbol | y | `getOhlcv` | transformation "global command search" | pass |
| C3 | Compare (+), chips with remove | /chart header | /chart header | "Compare" button | y | `getOhlcv` | m13-charting "compared symbol" | pass |
| C4 | Interval D / W / M | chart controls row | chart controls row | `Interval` group | y | `getOhlcv` | m11b-weekly, m13-charting "monthly" | pass |
| C5 | Range presets 1W 1M 3M 6M 1Y MAX | chart controls row | chart controls row | Range buttons | y | — | m13-charting "every visible range", transformation "range presets" | pass |
| C6 | Chart type (candles, bars, line, area, Heikin-Ashi) | chart controls `select` | chart controls `select` | `Chart type` | y | — | m13-charting "every chart type" | pass |
| C7 | Log and % scale | chart controls `Price scale` group; chart menu | same | `Log scale`, `Percent scale` | y | — | m13-charting "every chart type" | pass |
| C8 | Volume pane toggle | chart controls | chart controls | `Volume` button | y | — | manual | pass |
| C9 | MA 10/20/50/100/200 quick toggles; RSI/MACD/ADX pane row | "Studies" popover | "Studies" popover | `Studies` | y | `getIndicatorSeries` | openchart-parity D3 | pass |
| C10 | Fit all history | chart controls `Fit` | chart controls `Fit` | `Fit`, Alt+R | y | — | m13-charting "chart menu resets" | pass |
| C11 | Indicators dialog | /chart header; chart menu | same | `Indicators`, Alt+I | y | — | m13-charting "Alt+I" | pass |
| C12 | Layout 1…4×4 | /chart header `Layout` select | same | `Layout` | y | server document | m13-layouts "all documented" | pass |
| C13 | Sync symbol / interval / crosshair | /chart header (multi only) | same | `Sync` group | y | server document | m13-layouts "sync" | pass |
| C14 | Save state | /chart header | same | `Saved ✓` status | y | — | m11-slice "Restore" | pass |
| C15 | Keyboard shortcuts dialog | /chart header `?` | shell: `?` on every route; ☰ app menu | `?` key, ☰ → Keyboard shortcuts | y | — | m12-shell "? lists" | moved |
| C16 | Panel toggle | /chart header `Panel` | same | `Panel` | y | server document | m12-shell "panel is saved" | pass |
| C17 | Analyse (opens Details panel) | /chart header | same | `Analyse` | y | `getLiveStockAnalysis` | m12-shell "details tab" | pass |
| C18 | Research (symbol page) | /chart header link | same | `Research` | n | — | manual | pass |
| C19 | Undo / Redo drawings | Objects popover; Ctrl/⌘+Z/Y | same | `Objects`, keys | y | server document | m13-charting "undo and redo" | pass |
| C20 | Study legend: MAs, panes, dialog studies with value; remove pane ×; click configures | above plot | above plot | Legend row | y | — | transformation "study legends" | pass |
| C21 | Crosshair readout (date, OHLC, pane values) | plot top-left | plot top-left | Hover | y | — | openchart-parity D4 | pass |
| C22 | Footnote "N daily bars from the stored NSE series", data version | below plot | below plot | Read | y | — | m11b-weekly | pass |
| C23 | Chart context menu: reset, indicators, scale, alert at price | plot right-click | same | Right-click, Shift+F10 | y | — | m13-charting "chart menu" | pass |
| C24 | Pan / zoom by wheel, drag, keys | plot | plot | Mouse, keys | y | — | m13-charting "mouse wheel" | pass |
| C25 | Grid cells: per-cell symbol button, compare chips, range select, active border | each cell | each cell | Click cell | y | — | m13-layouts, transformation "grid activation" | pass |
| C26 | Chart library credit | site footer | shell status edge (`footer`) on every route; ☰ app menu | Page bottom | y | — | m10-stack "credited on every page" | moved |

## Drawing tools and objects

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| T1 | Select (Esc) | left rail | left rail | Rail | y | — | m12-shell "rail" | pass |
| T2 | Trendline (Alt+T), Ray, Extended line, Horizontal ray (Alt+H), Horizontal line, Vertical line (Alt+V), Cross line, Parallel channel, Price range, Text note, Rectangle (Alt+Shift+R), Fib retracement (Alt+F) | left rail, flat | left rail, flat | Rail, shortcuts | y | server document | m13-charting "every M13 tool" | pass |
| T3 | Clear (remove all) | left rail | left rail | Rail | y | server document | manual | pass |
| T4 | Objects inspector: list, show/hide, lock/unlock, undo/redo | `Objects` popover | `Objects` popover | `Objects · N` | y | server document | transformation "inline notes and drawing lock" | pass |
| T5 | Drawing menu: colour, width, dash, text, delete | right-click drawing | same | Right-click, Shift+F10 | y | server document | m13-charting "drawing menu", transformation "drawing menu arrows" | pass |
| T6 | Select, drag, arrows move, Delete | plot | plot | Click a drawing | y | server document | m13-charting "supports move, edit" | pass |
| T7 | Inline text-note editor | plot | plot | Text tool | y | server document | transformation "inline notes" | pass |
| T8 | Touch anchors (tap places, swipe never) | plot | plot | Touch | y | — | transformation "touch controls" | pass |

## Right panel

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| P1 | Tabs Watchlist / Details / Alerts, arrows/Home/End, Close panel, saved state | /chart right card | /chart right card | `Panel` | y | server document | m12-shell "panel is saved" | pass |
| P2 | Watchlist rows: symbol, rank, close, change; click opens chart; sort (BL-13); Add/Remove (Alt+W) | Watchlist tab | Watchlist tab | Panel | y | `getWatchlistDetail`, `addToWatchlist`, `removeFromWatchlist` | m12-shell "Alt+W" | pass |
| P3 | Details: Momentum25 summary, all criteria and evidence, Full research link | Details tab | Details tab | `Analyse` or tab | y | `getLiveStockAnalysis` | m12-shell "details tab" | pass |
| P4 | Alerts: create (value, condition, threshold, interval), drawing-linked, edit armed (BL-07), re-arm, delete, unseen count, history (BL-09), other-symbol link | Alerts tab | Alerts tab | Tab, chart menu | y | `/alerts` (create, edit, rearm, evaluate, seen, delete) | m15-alerts, transformation "armed alert editing" | pass |
| P5 | Alert levels as dashed lines (BL-06) | plot | plot | Armed alert | y | — | transformation "armed alert editing" | pass |

## Routes and navigation

Every route keeps its URL. "Prev" is the site `NavBar`. Since A2.1 the desktop entries live in the ☰ app menu (Chart, Screener, Markets, Watchlist; Research: the seven tools; Learn, Data, About). Phones keep the bottom navigation and its More sheet.

| # | Route | Prev nav entry | Now | Verified | Status |
|---|---|---|---|---|---|
| R1 | `/` Dashboard (screener) | NavBar, phone bottom nav | same | momentum-ranking-display | pass |
| R2 | `/chart`, `/chart/:symbol` | NavBar, phone bottom nav | same | m11-slice | pass |
| R3 | `/watchlist` | NavBar, phone bottom nav | same | m10-stack | pass |
| R4 | `/market` | NavBar; phone More | same | m10-stack | pass |
| R5 | `/learn` and its six guides | NavBar; phone More | same | final-accessibility | pass |
| R6 | `/data` | NavBar; phone More | same | m16-release-hardening | pass |
| R7 | `/strategies`, `/studio`, `/validation`, `/historical`, `/analytics`, `/experiment`, `/backtest` | Research menu; phone More | same | m14-studio, m16-historical-pit, r2-accessibility | pass |
| R8 | `/stock/:symbol`, `/analysis`, `/elliott-wave` | symbol search; links | same | momentum-ranking-display, m11-slice | pass |
| R9 | `/about` | footer link | same | manual | pass |
| R10 | `/lab/chart-grid` | none (diagnostic) | same | m13-bench | pass |
| R11 | Symbol search box (desktop), search dialog (phone, Ctrl/⌘+K, `/` or typing off-chart) | NavBar | shell header bar | transformation "global command search", "unfinished annotations" | moved |
| R12 | Theme light / dark / system | NavBar | ☰ app menu; phone More sheet | audit-visual "dark desktop" (`openAppMenu`) | moved |
| R13 | Screener side detail (`ScreenerDetail`): 1-year close line, badge, rank, momentum and setup scores, gate failures, why it ranks, what could invalidate, Open chart, Full research | Dashboard | same | m12-shell "screener shows the selected row" | pass |

## Keyboard shortcuts (`src/lib/shortcuts.ts`)

| # | Keys | Action | Verified | Status |
|---|---|---|---|---|
| K1 | letter, `/`, Ctrl/⌘+K | Symbol search | m11-slice "Find" | pass |
| K2 | ← → | Pan | m13-charting | pass |
| K3 | Ctrl/⌘+↑/↓, + / - | Zoom | m13-charting | pass |
| K4 | Alt+R | Reset view | m13-charting | pass |
| K5 | Alt+T, Alt+H, Alt+Shift+R, Alt+F, Alt+V | Tools | m12-shell "rail" | pass |
| K6 | Click, drag, Delete | Select, move, delete drawing | m13-charting | pass |
| K7 | Arrows (drawing selected) | Move drawing | m13-charting "drawing menu" | pass |
| K8 | Right-click, ContextMenu, Shift+F10 | Menus | m13-charting, transformation | pass |
| K9 | Ctrl/⌘+Z, Ctrl/⌘+Shift+Z, Ctrl+Y | Undo, redo | m13-charting | pass |
| K10 | Esc | Cancel tool or selection | m12-shell | pass |
| K11 | Alt+I | Indicators | m13-charting "Alt+I" | pass |
| K12 | Alt+W | Watchlist toggle | m12-shell "Alt+W" | pass |
| K13 | `?` | Shortcuts | m12-shell "? lists" | pass |

## Backlog items BL-01..BL-15 and OpenChart audit fixes

| # | Item | Location | Verified | Status |
|---|---|---|---|---|
| BL-01 | Full history; ranges are windows | /chart plot | transformation "range presets" | pass |
| BL-02 | Rail for the active grid cell | grid | transformation "grid activation" | pass |
| BL-03 | Legend for dialog studies | legend row | transformation "study legends" | pass |
| BL-04 | Per-study colour and hide | Indicators dialog | transformation "study legends" | pass |
| BL-05 | Inline note editor | plot | transformation "inline notes" | pass |
| BL-06 | Armed alerts as dashed lines | plot | transformation "armed alert editing" | pass |
| BL-07 | Edit an armed alert | Alerts tab | transformation "armed alert editing" | pass |
| BL-08 | Lock, hide, dash | Objects, drawing menu | transformation "inline notes and drawing lock" | pass |
| BL-09 | Alert history | Alerts tab | m15-alerts | pass |
| BL-10 | Volume Profile | not built (Phase B5) | — | deferred |
| BL-11 | Editable RSI/MACD display studies | Indicators dialog | transformation "study legends" | pass |
| BL-12 | Percent-scale base (price studies hidden on %) | plot | transformation "changing chart type" | pass |
| BL-13 | Watchlist sort | Watchlist tab | m12-shell | pass |
| BL-14 | Dense chrome on phones and grids | /chart | transformation "responsive workspace", "touch controls" | pass |
| BL-15 | Drawing-linked alerts (captured horizontal and rectangle) | Alerts tab | transformation "armed alert editing" | pass |
| OC-D1…D11 | Range from last bar, MA warm-up, one pane definition, readout off axis, keys after checkbox, no zero-length line, cell keeps symbol, synced readout clears, Enter adds indicator, edits during load kept | various | openchart-parity, `server-document.test.ts`, `workspace.test.ts`, `useChartShell.test.ts` | pass |

Status values: **pass** = verified at its current place; **moved** = relocated and verified; **deferred** = not built.
