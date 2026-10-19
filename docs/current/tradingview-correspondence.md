# TradingView correspondence and capability ledger

Plan: [2026-10-19 workstation plan](../history/plans/2026-10-19-tradingview-workstation-plan.md). Rule: TradingView structure, Wickstreet skin (design record D23).

The screen matrix (reference screen ↔ Wickstreet route) is added in phase A9.2. The capability ledger below starts at phase A1.3 from the baseline pass: on 2026-10-19 the full Playwright suite at `b3baee1` passed 164 tests on a fresh synthetic database, with 6 opt-in benchmark tests skipped (`M13_BENCH`). BL-01..BL-15 and the OpenChart fixes pass where each one is built today. Each relocation phase updates its rows in the same commit. A phase is not done while a row it touched is unverified.

Columns: **Prev** = location before the transformation. **Now** = current primary place. **No-nav** = the user finishes the task without leaving the view. **Verified** = the spec that proves it, or a manual check.

## Chart toolbar and chart controls

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| C1 | Symbol title (`h1`), opens search | /chart header | chart toolbar in the shell header bar (route slot) | Click symbol, type, `/`, Ctrl/⌘+K | y | `searchSecurities` | m11-slice "Find", transformation "folds lower-priority controls" | moved |
| C2 | Company name, last close, change % | /chart header | chart toolbar (name ≥1536 px; price and change ≥640 px) | Next to symbol | y | `getOhlcv` | transformation "global command search" | moved |
| C3 | Compare (+), chips with remove | /chart header | chart toolbar ≥1024 px; ⋯ menu below | "+ Compare" | y | `getOhlcv` | m13-charting "compared symbol", transformation "folds lower-priority controls" | moved |
| C4 | Interval D / W / M | chart controls row | chart toolbar, after Compare (active chart) | `Interval` group | y | `getOhlcv` | m11b-weekly, m13-charting "monthly" | moved |
| C5 | Range presets 1W 1M 3M 6M 1Y MAX | chart controls row | bottom range bar, left | Range buttons | y | — | m13-charting "every visible range", transformation "range presets" | moved |
| C6 | Chart type (candles, bars, line, area, Heikin-Ashi) | chart controls `select` | chart toolbar ≥1024 px; ⋯ menu below | `Chart type` | y | — | m13-charting "every chart type" | moved |
| C7 | Log and % scale | chart controls `Price scale` group; chart menu | bottom range bar; chart menu | `Log scale`, `Percent scale` | y | — | m13-charting "every chart type" | moved |
| C8 | Volume pane toggle | chart controls | settings gear ("Chart settings"); ⋯ menu below 1280 px | `Volume` button | y | — | transformation "settings gear holds volume" | moved |
| C9 | MA 10/20/50/100/200 quick toggles; RSI/MACD/ADX pane row | "Studies" popover | settings gear ("Chart settings"); ⋯ menu below 1280 px | `Studies` | y | `getIndicatorSeries` | openchart-parity D3, m11-slice "Analyse → Draw → Restore" (`openChartSettings`) | moved |
| C10 | Fit all history | chart controls `Fit` | bottom range bar | `Fit`, Alt+R | y | — | m13-charting "chart menu resets" | moved |
| C11 | Indicators dialog | /chart header; chart menu | chart toolbar "fx Indicators" ≥640 px, ⋯ menu below; chart menu | `Indicators`, Alt+I | y | — | m13-charting "Alt+I", transformation "folds lower-priority controls" | moved |
| C12 | Layout 1…4×4 | /chart header `Layout` select | chart toolbar Layout popover (radios); ⋯ menu below 1024 px | Grid icon | y | server document | m13-layouts "all documented" (`chooseLayout`) | moved |
| C13 | Sync symbol / interval / crosshair | /chart header (multi only) | Layout popover (multi only) | Grid icon → Sync | y | server document | m13-layouts "sync" (`openLayoutMenu`) | moved |
| C14 | Save state | /chart header | chart toolbar, right end | `Saved ✓` status | y | — | m11-slice "Restore" | moved |
| C15 | Keyboard shortcuts dialog | /chart header `?` | shell: `?` on every route; ☰ app menu | `?` key, ☰ → Keyboard shortcuts | y | — | m12-shell "? lists" | moved |
| C16 | Panel toggle | /chart header `Panel` | right icon strip (click the open tab to collapse); `Panel` header button below 1024 px | Strip icons | y | server document | m12-shell "panel is saved", transformation "touch controls" | moved |
| C17 | Analyse (opens Details panel) | /chart header | strip **Assessment** tab; the legend chip "#N · Qualified" opens it | Strip icon, legend chip | y | `getStockExplanation` (run in view), `getLiveStockAnalysis` (outside the run) | m12-shell "Assessment tab", momentum25 "legend chip" | moved |
| C18 | Research (symbol page) | /chart header link | Assessment "Full analysis →" with `?from=`; the symbol page offers "Back to chart · SYMBOL" | Strip → Assessment | n | — | m12-shell "Assessment tab", momentum25 "Full analysis" | moved |
| C19 | Undo / Redo drawings | Objects popover; Ctrl/⌘+Z/Y | chart toolbar Undo/Redo icons ≥1280 px; ⋯ menu below; keys | toolbar icons, keys | y | server document | m13-charting "undo and redo" | moved |
| C20 | Study legend: MAs, panes, dialog studies with value; remove pane ×; click configures | above plot | overlay legend at plot top-left: title, OHLC + change, one line per study with × and ⚙ (research pages keep the row above the plot) | Legend | y | — | transformation "study legends", "overlay legend" | moved |
| C21 | Crosshair readout (date, OHLC, pane values) | plot top-left | inside the overlay legend on the active chart; plot top-left elsewhere | Hover | y | — | openchart-parity D4, transformation "overlay legend" | moved |
| C22 | Footnote "N daily bars from the stored NSE series", data version | below plot | /chart: bottom range bar, truncated, full text in `title`; research pages: below plot | Read, hover | y | — | m11b-weekly | moved |
| C23 | Chart context menu: reset, indicators, scale, alert at price | plot right-click | same | Right-click, Shift+F10 | y | — | m13-charting "chart menu" | pass |
| C24 | Pan / zoom by wheel, drag, keys | plot | plot | Mouse, keys | y | — | m13-charting "mouse wheel" | pass |
| C25 | Grid cells: per-cell symbol button, compare chips, range select, active border | each cell | cell label over the plot (symbol button, compare chips); range, interval and tools in the top toolbar, rail and range bar act on the active cell; `--ws-accent` border | Click cell | y | — | m13-layouts, transformation "grid activation", "rail portal gate" | moved |
| C26 | Chart library credit | site footer | shell status edge (`footer`) on every route except /chart, where the range bar carries it at ≥640 px; ☰ app menu | Page bottom | y | — | m10-stack "credited on every page" | moved |
| C27 | Alert button (new): opens the Alerts panel for the chart's symbol | — | chart toolbar ≥1024 px; ⋯ menu below | `Alert` | y | `/alerts` | transformation "folds lower-priority controls" | new |

## Drawing tools and objects

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| T1 | Select (Esc) | left rail | page rail column, serving the active chart (D25) | Rail | y | — | m12-shell "rail", transformation "rail portal gate" | moved |
| T2 | Trendline (Alt+T), Ray, Extended line, Horizontal ray (Alt+H), Horizontal line, Vertical line (Alt+V), Cross line, Parallel channel, Price range, Text note, Rectangle (Alt+Shift+R), Fib retracement (Alt+F) | left rail, flat | grouped rail (A4.1): Lines, Fibonacci, Shapes, Annotation, Measure; each group shows its last-used tool; the corner arrow opens a flyout with name and shortcut; below 640 px one "Draw" button opens the groups as a bottom sheet | Rail, flyout, shortcuts | y | server document | m13-charting "every M13 tool", transformation "grouped rail" | moved |
| T3 | Clear (remove all) | left rail | "Remove objects" below a separator at the rail's end | Rail | y | server document | m11-slice, m11b-weekly | moved |
| T4 | Objects inspector: list, show/hide, lock/unlock, undo/redo | `Objects` popover | /chart: **Object tree** right-panel tab for the active chart (undo/redo in the toolbar and keys); research pages keep the `Objects` popover | Strip icon "Object tree" | y | server document; `right_panel: "objects"` (additive enum value) | transformation "inline notes and drawing lock", "Object tree tab" | moved |
| T5 | Drawing menu: colour, width, dash, text, delete | right-click drawing | same | Right-click, Shift+F10 | y | server document | m13-charting "drawing menu", transformation "drawing menu arrows" | pass |
| T6 | Select, drag, arrows move, Delete | plot | plot | Click a drawing | y | server document | m13-charting "supports move, edit" | pass |
| T7 | Inline text-note editor | plot | plot | Text tool | y | server document | transformation "inline notes" | pass |
| T8 | Touch anchors (tap places, swipe never) | plot | plot | Touch | y | — | transformation "touch controls" | pass |

## Right panel

| # | Capability | Prev | Now | How a user finds it | No-nav | APIs | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| P1 | Tabs Watchlist / Details / Alerts, arrows/Home/End, Close panel, saved state | /chart right card | shell icon strip, route-adaptive (A5.1): /chart Watchlist · Assessment · Alerts · Object tree; Screener Watchlist · Assessment (selected row) · Alerts; symbol pages and others Watchlist · Alerts. Panel inline on /chart ≥1280 px, overlay elsewhere (D24). The saved value of Assessment stays `details` | Strip icons | y | server document | m12-shell "panel is saved", "panel follows the route" | moved |
| P2 | Watchlist rows: symbol, rank, close, change; click opens chart; sort (BL-13); Add/Remove (Alt+W) | Watchlist tab | shell panel, every route: dense columns Symbol, Last, Chg%, Rank, Qualified; header names the ranking run, and warns when it differs from the view's run | Strip | y | `getWatchlistDetail`, `addToWatchlist`, `removeFromWatchlist` | m12-shell "Alt+W", momentum25 "watchlist rank and qualification" | moved |
| P3 | Details: Momentum25 summary, all criteria and evidence, Full research link | Details tab | **Assessment** panel (`momentum25/AssessmentPanel`): rank, Qualified/Gate failed, momentum score, provenance line, readiness, scores, gate failures, why it ranks, what could invalidate, every criterion expanding to value/threshold/engine/weight/contribution, "Show on chart" for SMA criteria, Open in chart (off /chart), Full analysis, Create alert. Symbols outside the run show a labelled live analysis. Limit: passing gates are not marked, because the API lists only failing gate rules | Strip | y | `getStockExplanation`, `getLiveStockAnalysis`, `getRun`, `getOhlcv` | m12-shell "Assessment tab", momentum25 "Assessment shows the rank", "never shows the previous symbol" | moved |
| P4 | Alerts: create (value, condition, threshold, interval), drawing-linked, edit armed (BL-07), re-arm, delete, unseen count, history (BL-09), other-symbol link | Alerts tab | shell panel, every route; opens on "This symbol" with an "All" toggle; create from the toolbar Alert, the chart menu, the symbol page "Create alert" or Assessment "Create alert" | Strip, chart menu, symbol page, Assessment | y | `/alerts` (create, edit, rearm, evaluate, seen, delete) | m15-alerts, transformation "armed alert editing", momentum25 "alerts open on this symbol" | moved |
| P5 | Alert levels as dashed lines (BL-06) | plot | plot | Armed alert | y | — | transformation "armed alert editing" | pass |

## Routes and navigation

Every route keeps its URL. "Prev" is the site `NavBar`. Since A2.1 the desktop entries live in the ☰ app menu (Chart, Screener, Markets, Watchlist; Research: the seven tools; Learn, Data, About). Phones keep the bottom navigation and its More sheet.

| # | Route | Prev nav entry | Now | Verified | Status |
|---|---|---|---|---|---|
| R1 | `/` Dashboard (screener) | NavBar, phone bottom nav | **Stock Screener**: title and strategy picker in the header bar, provenance line, stat strip, column-set tabs (Overview, Scores, Explanation, Technical), filter pills, dense table with sticky header and symbol column; a row opens the Assessment | momentum-ranking-display, m12-shell "screener opens the selected row", `screener.test.ts` | moved |
| R2 | `/chart`, `/chart/:symbol` | NavBar, phone bottom nav | same | m11-slice | pass |
| R3 | `/watchlist` | NavBar, phone bottom nav | same | m10-stack | pass |
| R4 | `/market` | NavBar; phone More | same | m10-stack | pass |
| R5 | `/learn` and its six guides | NavBar; phone More | same | final-accessibility | pass |
| R6 | `/data` | NavBar; phone More | same | m16-release-hardening | pass |
| R7 | `/strategies`, `/studio`, `/validation`, `/historical`, `/analytics`, `/experiment`, `/backtest` | Research menu; phone More | Research workspace: one tab row over the seven routes (URLs unchanged), a left strategy list from 1024 px, `?from=` kept across tabs. Studio families stay inside Studio (no other natural place) | m14-studio, m16-historical-pit, r2-accessibility, momentum25 "Research workspace" | moved |
| R8 | `/stock/:symbol`, `/analysis`, `/elliott-wave` | symbol search; links | one `SymbolHeader`: name, `SYMBOL · NSE`, close and change, EOD as of, badges, tabs Overview / Analysis / Elliott Wave / Open in chart ↗, Watchlist star, Patterns, Create alert, Back link. SectionNav retired; each "Why it ranks" item links to and focuses its engine's evidence section | momentum-ranking-display, m11-slice, m10-stack, momentum25 "symbol pages share one header" | moved |
| R9 | `/about` | footer link | same | manual | pass |
| R10 | `/lab/chart-grid` | none (diagnostic) | same | m13-bench | pass |
| R11 | Symbol search box (desktop), search dialog (phone, Ctrl/⌘+K, `/` or typing off-chart) | NavBar | shell header bar | transformation "global command search", "unfinished annotations" | moved |
| R12 | Theme light / dark / system | NavBar | ☰ app menu; phone More sheet | audit-visual "dark desktop" (`openAppMenu`) | moved |
| R13 | Screener side detail (`ScreenerDetail`): 1-year close line, badge, rank, momentum and setup scores, gate failures, why it ranks, what could invalidate, Open chart, Full research | Dashboard | **retired** (A8.2). Every field is in the Assessment panel on the Screener: 1-year close line, Qualified badge and rank, momentum and setup scores, gate failures, why it ranks, what could invalidate, "Open in chart", "Full analysis →" | m12-shell "screener opens the selected row", audit-visual "dark desktop" | moved |

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

## Momentum25 integration and workstation additions (A5–A8)

| # | Capability | Place | How found | Verified | Status |
|---|---|---|---|---|---|
| M1 | Provenance line: strategy · run #N · as of · data version | Assessment, Screener, bottom-panel Screener | Read | momentum25 "Assessment shows the rank" | new |
| M2 | Legend chip "#N · Qualified" / "Not qualified", only for a symbol in the run | /chart overlay legend | Click opens Assessment | momentum25 "legend chip" | new |
| M3 | "Show on chart" evidence layers (SMA criteria): dashed, temporary, never saved; a saved MA is highlighted instead; legend row with remove | Assessment criterion → active chart | Expand a criterion | momentum25 "Show on chart" (zero PUTs, reload clears) | new |
| M4 | Screener column sets and filter pills (qualified, trend, risk, volume, breakout) over existing row fields | Screener, bottom panel | Tabs, pills | `screener.test.ts` (order, determinism) | new |
| M5 | Bottom panel: embedded Stock Screener (row loads the active chart only), Strategy Studio and Research links with `?from=`, collapse and maximise; state per viewer | /chart ≥640 px | Bottom bar | momentum25 "bottom panel" | new |
| M6 | `?from=` return path, same-origin paths only; "Back to chart · SYMBOL" | symbol pages, research routes | Back link | `return-path.test.ts`, momentum25 "Full analysis", "Research workspace" | new |
| M7 | Symbol search dialog: title with close, "All · Stocks" chips (NSE stocks only, so both show the same rows), symbol · name · stock · NSE rows | dialog | `/`, Ctrl/⌘+K, typing | m11-slice "Find", m13-layouts | moved |
| M8 | Indicator dialog: left category list from the catalogue groups, right searchable list | dialog | fx Indicators, Alt+I | m13-charting "Alt+I", openchart-parity "Enter adds" | moved |
| M9 | Data and Markets | flat sections | ☰ | m10-stack | pass |

Limits: Data has one settings section today, so it has no left nav. Markets has no symbol rows (sector rows only), so no row opens an Assessment there.

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
| BL-08 | Lock, hide, dash | Object tree tab, drawing menu | transformation "inline notes and drawing lock" | pass |
| BL-09 | Alert history | Alerts tab | m15-alerts | pass |
| BL-10 | Volume Profile | not built (Phase B5) | — | deferred |
| BL-11 | Editable RSI/MACD display studies | Indicators dialog | transformation "study legends" | pass |
| BL-12 | Percent-scale base (price studies hidden on %) | plot | transformation "changing chart type" | pass |
| BL-13 | Watchlist sort | Watchlist tab | m12-shell | pass |
| BL-14 | Dense chrome on phones and grids | /chart | transformation "responsive workspace", "touch controls" | pass |
| BL-15 | Drawing-linked alerts (captured horizontal and rectangle) | Alerts tab | transformation "armed alert editing" | pass |
| OC-D1…D11 | Range from last bar, MA warm-up, one pane definition, readout off axis, keys after checkbox, no zero-length line, cell keeps symbol, synced readout clears, Enter adds indicator, edits during load kept | various | openchart-parity, `server-document.test.ts`, `workspace.test.ts`, `useChartShell.test.ts` | pass |

Status values: **pass** = verified at its current place; **moved** = relocated and verified; **deferred** = not built.
