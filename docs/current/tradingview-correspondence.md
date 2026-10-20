# TradingView correspondence and capability ledger

Plan: [2026-10-19 workstation plan](../history/plans/2026-10-19-tradingview-workstation-plan.md). Rule: TradingView structure, Wickstreet skin (design record D23).

The screen matrix follows. The capability ledger below starts at phase A1.3 from the baseline pass: on 2026-10-19 the full Playwright suite at `b3baee1` passed 164 tests on a fresh synthetic database, with 6 opt-in benchmark tests skipped (`M13_BENCH`). BL-01..BL-15 and the OpenChart fixes pass where each one is built today. Each relocation phase updates its rows in the same commit. A phase is not done while a row it touched is unverified.

Columns: **Prev** = location before the transformation. **Now** = current primary place. **No-nav** = the user finishes the task without leaving the view. **Verified** = the spec that proves it, or a manual check.

## Screen matrix

References are TradingView's public rendered pages, observed at 1440×900 on 2026-10-19 (structure only; screenshots stay outside the repository). Evidence is `audit-evidence/tradingview-clone/` (32 screenshots: four screens × 1920, 1440, 768, 390 × light, dark; `geometry.json`), made by `e2e/tradingview-clone-evidence.spec.ts`. Measured at 1440×900: header 38 px, rail 52 px, strip 45 px, range bar 30 px, no document overflow at any width. Plot: 1,031×796 px at 1440 (Codex 1,076×676), 378×698 px at 390 (Codex 334×544).

| Reference | Route | Structure | Behaviour | Changes from Codex | Limits | Evidence |
|---|---|---|---|---|---|---|
| Supercharts chart | `/chart`, `/chart/:symbol` | One toolbar row in the shell header: ☰, symbol `h1`, price, Compare, D/W/M, chart type, fx Indicators, Alert, undo/redo, layout and sync, Save, settings gear. Grouped rail (Select, Lines, Fibonacci, Shapes, Annotation, Measure, Remove objects). Overlay legend. Strip with Watchlist, Assessment, Alerts and Object tree. Range bar with footnote, scales, Fit, EOD · NSE and credit. Bottom panel | Toolbar, rail, range bar and Object tree act on the active chart through portals (D25). Lower-priority controls fold into ⋯ below 1280 and 1024 px. The rail becomes one Draw sheet below 640 px | Was a page header with inline per-chart controls; grid cells had their own toolbars | No Replay (B2), no intraday intervals, rail lacks brushes, icons, patterns and projections (B3); bottom panel has no script editor or strategy tester (Phase C) | `chart-*.png` |
| Stock Screener | `/` | Title and strategy picker in the header, provenance line, stat strip, column-set tabs, filter pills, dense table with sticky header and symbol column | A row opens the Assessment panel; `?run=` opens a historical run with its label | Was "Live Momentum Dashboard" with summary cards and a side detail card | Filters cover existing fields only (B1 adds ranges and saved screens). The picker lists production strategies only | `screener-*.png` |
| Symbol page | `/stock/:symbol`, `/analysis`, `/elliott-wave` | Header: initial badge, name, `SYMBOL · NSE`, close and change, EOD as of, badges; tab row Overview, Analysis, Elliott Wave, Open in chart ↗ | Each "Why it ranks" item links to and focuses its evidence section; Back link with `?from=` | Was a page banner, an action bar and a section nav | No financials or news (no data source) | `symbol-*.png` |
| Strategy tester (closest) | `/strategies`, `/studio`, `/backtest`, `/experiment`, `/validation`, `/historical`, `/analytics` | Research workspace: left strategy list, one tab row, flat sections | Strategy and `?from=` carry across tabs; Studio's hold-out flow and the Screening Result / In-Sample / Out-of-Sample labels are unchanged | Was seven separate pages behind a menu | Studio families stay inside Studio | `research-*.png` |
| Symbol search | dialog | Title with close, search field, All · Stocks chips, rows symbol · name · stock · NSE | ↑↓, Enter, Esc; opens from typing, `/`, Ctrl/⌘+K | Was a smaller list without chips | NSE stocks only | m11-slice "Find" |
| Indicators | dialog | Left category list from the catalogue, right searchable list, active studies below | Enter adds the first match | Was one grouped list | — | m13-charting "Alt+I" |

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
| R9 | `/about` | footer link | shell status edge link; ☰ app menu | m10-stack "route /about" | moved |
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

## Phase B charting-parity additions

| # | Capability | Place | How found | Verified | Status |
|---|---|---|---|---|---|
| B1a | Range filters (Momentum, Buy setup, RS, Rank, Δ Rank; inclusive bounds) and a Sector filter, combined with the M4 pills; "Matches: N of M" | Screener, bottom panel | Pill ▾ opens From/To | `screener.test.ts`; b1-screener "reference filter over the whole run" | new |
| B1b | The screeners read every row of the run (pages of 200), not the first 100. The rankings API breaks rank ties by security id, so pages never overlap | Screener, bottom panel | — | `api-client.test.ts`; `test_rankings_pages_never_overlap_on_tied_ranks` | fixed |
| B1c | Saved screens: name, column set and filters in the `saved_screens` user document (ETag/412/428); open, save changes, save as new, delete; the open screen survives a reload and is shared with the bottom panel | Screen menu ▾ | Screen name button | `test_user_documents_api.py` (round trip, 412, validation, cap); b1-screener "saved screen" | new |

| B2a | Bar replay (EOD): Replay button; replay date, Play/Pause, Step forward (Shift+→), 1×/3×/10×, Exit. Every chart on the page replays one date | /chart toolbar (⋯ menu on phones); replay row above the range bar | Replay | b2-replay "replay cuts the chart…" | new |
| B2b | No look-ahead: the server serves bars and pane indicators `as_of` the date. Later bars are dropped, later corporate actions are not applied (prices are as known then), and a weekly or monthly bar holds only its sessions to the date. Compare lines, benchmark closes and browser studies read the cut series | price, panes, compare, studies | — | `test_period_bars.py` (as-of factors, partial week, no-look-ahead property for 1D/1W/1M); b2-replay (bar count, `as_of` on every series request, weekly bar) | new |
| B2c | Drawings saved with an anchor after the date hide; ones drawn during replay save normally and stay; hidden ones are never changed. Exit restores the viewport from before replay | chart, Object tree | — | `replay.test.ts`; b2-replay "replay hides drawings…", "exit restores the viewport" | new |
| B2d | Momentum25 context in replay uses the newest live or historical run dated on or before the date (`/runs/latest?on_or_before=`), else "Not available in replay". There is no live fallback, no later-bar note, and no Full analysis link. The legend chip and bottom screener follow the same run. The watchlist hides prices and ranks. Alerts are paused: none are created, alert lines hide, and their history hides | Assessment, legend chip, bottom panel, Watchlist, Alerts | — | `test_latest_run_on_or_before_a_replay_date`; b2-replay "Assessment, legend chip…" | new |

Limits (B2): Step forward moves one stored daily session at every interval, so a weekly bar forms day by day. Replay runs on /chart only; leaving the page ends it. Steps land on the active chart's sessions. The server still evaluates alerts on real data in the background; replay only stops showing or creating them. Pattern detection and Elliott Wave are not on /chart, so replay has nothing of theirs to disable. Their own pages always show the full series.

Limits (B1): filters read fields a run already stores; there is no price or volume filter, because the rankings rows carry no price. A row with no value for a bounded field (no RS, or no rank because it did not qualify) never matches that bound. A screen applies to any run and does not remember a strategy. Screens have no rename; save as new and delete cover it.

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
