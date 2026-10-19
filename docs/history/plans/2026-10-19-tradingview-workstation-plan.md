# Wickstreet → TradingView-style application (continue Codex)

## Context

Codex left six local commits (`f76ada7..c275f2b`) and uncommitted work: touch
drawing anchors, `autoHeight` plot fitting, and alert-level/basis helpers with
tests. The capability work and audit backlog BL-01..BL-15 are done. The
**design** is not TradingView: Codex built an original "paper-and-ink,
sea-green" workstation inside a website shell. Today /chart has a site NavBar,
a two-row control strip, a flat 13-button drawing column, a text-tab right
card, no right icon strip, no bottom range bar or bottom panel, and a footer.
Every other route is `PageHeader` plus a `max-w-7xl` stack of rounded `Card`s.

Goal: **TradingView's screen layout, control placement, navigation and
interaction behaviour + Wickstreet's existing paper-and-sea-green design
language + every existing capability.** A TradingView user finds each control
where they expect it. Every capability, calculation, API, persistence
guarantee and NFR-11 budget stays. TradingView is the benchmark for product
structure, workflows and relevant charting functionality. Phase A delivers
the workstation. Phase B adds charting-parity capabilities in order of
priority. Phase C covers major future initiatives, which are evaluated, not
built. Phase B never delays Phase A.

**Product framing.** Wickstreet is one TradingView-familiar charting and
market-analysis platform. Momentum25 is the analytical intelligence inside
its workflows: screening, charting, watchlists, symbol overview, alerts and
strategy research.
- It is not a clone with tabs, panels or links bolted on, and the user never
  sees "TradingView features" next to "Momentum25 add-ons".
- Integration follows the user's task, not the legacy page layout.
- Each capability appears where it moves the task forward, using existing
  APIs and calculations only.
- The main chart stays clean. Deeper evidence comes through contextual
  panels, drill-downs, table columns and optional layers.

## Unified workstation shell (all routes)

`RootLayout` (`src/app/layout.tsx`) replaces `NavBar`, the page wrapper and
`SiteFooter` with one `WorkstationShell`. Each region and what it holds:

- **Header bar** (one row):
  - ☰ app menu: every route grouped as Chart · Screener · Markets ·
    Research ▾ · Learn (Help) · Data (Settings) · About; plus theme,
    keyboard shortcuts and the credit
  - Wickstreet mark
  - symbol search pill (Ctrl/⌘+K, `/`, or start typing)
  - a route slot
- **Route slot.** /chart fills it with its chart toolbar, so the chart keeps
  one row like Supercharts. Other routes fill it with section tabs and the
  route's own controls, such as the strategy picker or Run screening.
- **Right icon strip and panel, adapted to the route.** Each route supplies
  its panel context: the symbol and the provenance it is about. Panels with
  no context are hidden, not shown stale.

  | Route | Strip |
  |---|---|
  | /chart | Watchlist · Assessment · Alerts · Object tree |
  | Screener | Watchlist · Assessment (selected row) · Alerts |
  | Symbol pages | Watchlist · Alerts (the page itself is the assessment) |
  | Research, Markets, Data, Help | Watchlist · Alerts |

  `SidePanel` moves from the chart page into the shell and keeps
  `useRightPanel`'s server-saved state. "Assessment" is the user-facing name
  of today's Details tab. The `Details` tab name stays as its accessible
  name until the specs move.
- **Left drawing rail and bottom range bar** on chart surfaces: /chart, and
  the stock pages through the inline `PriceChart`.
- **Bottom panel on /chart:**
  - Stock Screener: embedded
  - Strategy Studio: shell navigation
  - Research: shell navigation
- **Phones:** the existing bottom nav stays as the phone navigation for every
  route.
- **Credit:** shown in the shell's bottom status edge on every route.
## Context model (no forced global selection)

| Context | Owner | Carried by | Never |
|---|---|---|---|
| Active chart symbol, interval, layout, drawings | Workspace document (`useWorkspaceChart`, `useLayout`); active chart is authoritative | server document | overwritten by another route. Only an explicit "Open in chart" sets the active chart's symbol (existing `/chart/:symbol` behaviour); other grid cells are untouched |
| Route selection (screener row, symbol page, Studio family, historical date) | the route | URL (`?symbol=`, path, `?family=`, `?date=`) | leaks into other routes |
| Selected strategy | existing `StrategyProvider` | context + `?strategy=` (already used) | confused with a run |
| Screening run | the run itself (`getLatestRunForStrategy` / `getRun`) | run id in URL when not latest | shown without its run id and completion time |
| Research result / period | research routes | URL | presented as a screening result; Screening Result / In-Sample / Out-of-Sample labels unchanged |
| Data version / last bar | chart footnote, run metadata, `getDataFreshness` | shown in a provenance line | silently mixed: when the chart's last bar differs from the run's as-of date, the assessment says so |
| Return path | originating view | `?from=` (same-origin path only) | lost: research views opened from a chart show "Back to chart · SYMBOL"; the chart restores from its document |

**Provenance line.** It is one shared component, used on every Momentum25
view. It shows strategy · run #N · as-of date · data version, or for
research, period · evaluation label.

## Native Momentum25 integration (by workflow)

Each row is an acceptance contract. "No-nav" means the user finishes the core
task without leaving the current view. The APIs are the existing functions
in `src/lib/api-client.ts`.

### 1. Screen (Screener `/`, plus the /chart bottom-panel Screener)

- **Place:** a TradingView Stock Screener layout.
  - **Screen picker:** the strategy.
  - **Column-set tabs:** Overview, Scores, Explanation and Technical,
    regrouping the existing columns and Columns menu.
  - **Filter pills:** qualified/not, trend pass/fail, and the
    risk/volume/breakout categories. These filter **existing row fields
    client-side** and create no new metric.
  - **Search** and a dense sortable table.
- **Discover:** the default route; ☰ → Screener; the chart's bottom panel.
- **Interact:**
  - Selecting a row opens its Assessment in the right panel, which replaces
    `ScreenerDetail`.
  - "Open in chart" loads the symbol into the active chart.
  - In the /chart bottom panel, a row click loads the active chart directly.
  - Changing the strategy re-queries its latest run in the screener, the
    Assessment and the watchlist columns.
- **Context:** consumes the strategy and run; carries `strategy`, `symbol`
  and the run into the chart and the symbol page.
- **No-nav:** yes, for screen → inspect → open in chart.
- **APIs:** `getLatestRunForStrategy`, `getRankings`, `getStockExplanation`,
  `listStrategies`, `executeScreening`, `getDataFreshness`.
- **Tests:** filter and sort determinism against the fixture rankings; rank
  `'—'` semantics unchanged; strategy switch updates all three views.

### 2. Understand ranking on the chart (the Assessment panel and legend)

- **Place:** the right-panel **Assessment** for the active chart's symbol.
  - Header: rank, qualified/gate-failed, score.
  - Gates as a pass/fail list.
  - "Why it ranks" and "What could invalidate this" from
    `ExplanationSummary`.
  - The provenance line.
- **Evidence drill-down:** each criterion expands in place to its evidence
  values.
- **Optional chart layers:** a criterion whose evidence is an existing
  chart study shows "Show on chart". Examples: an SMA in the MA set, or a
  detected pattern through `useChartPatterns`. Hiding the layer restores the
  previous study state.
- **Discover:** one compact legend chip "#3 · Qualified" (or "Not
  qualified"), shown only when the symbol is in the selected run. Clicking
  it opens Assessment. Otherwise the chart is plain.
- **Context:** active chart symbol plus selected strategy; it follows
  active-cell switches in grids.
- **No-nav:** yes. "Full analysis" opens the symbol page with `?from=`.
- **APIs:** `getStockExplanation`, `getLiveStockAnalysis` for symbols
  outside the run (labelled as live analysis, not a ranking),
  `detectChartPatterns`.
- **Tests:** the chip appears and disappears with run membership; layer
  toggle on and off leaves the saved document unchanged unless the user
  saves; the assessment follows the active cell.

### 3. Watchlist (right panel)

- **Place:** dense rows: Symbol, Last, Chg%, Rank, Qualified. The rank
  columns come from the existing `getWatchlistDetail(strategy)`.
- **Interact:** a click loads the active chart on /chart and selects the row
  on the Screener. Sort by any column (BL-13 kept). Alt+W adds the current
  symbol.
- **APIs:** `getWatchlist`, `getWatchlistDetail`, `addToWatchlist`,
  `removeFromWatchlist`.
- **Tests:** rank and qualification match the screener for the same
  strategy and run; a click changes only the active cell.

### 4. Symbol overview (`/stock/:symbol`, `/analysis`, `/elliott-wave`)

- **Place:** a TradingView symbol-page layout.
  - **Header:** name, `SYMBOL · NSE`, last close, change, "EOD as of",
    provenance.
  - **Tabs:** Overview · Technicals (today's analysis) · Elliott Wave. The
    Chart tab hands off to /chart.
- **Native sections:** Momentum25 thesis, score gauge, trend template,
  engine contributions, RS vs index, patterns, volume accumulation and
  suggested stop. Each is a native section, not a stacked card.
- **Criterion → evidence:** each "Why it ranks" item anchor-links to its
  evidence section on the same page.
- **Interact:** "Open in chart" and "Back to chart" (when `?from=`), the
  watchlist star, and creating an alert for this symbol.
- **APIs:** unchanged page queries.
- **Tests:** each criterion link scrolls to and focuses its section; the
  existing heading and number assertions hold.

### 5. Strategy research (one strategy-analysis area)

- **Place:** "Research" is one workspace with a left list of strategies and
  Studio families, a top tab row, and dense report panes.
  - **Strategies:** overview of a strategy's runs and contributions.
  - **Studio:** hypothesis → evidence → hold-out, unchanged flow.
  - **Backtest:** Overview · Performance · Rebalances · Properties.
  - **Experiment, Validation, Historical (point-in-time), Analytics:** the
    other tabs.

  Each tab keeps its own route and URL, so direct links keep working. The
  distinct semantics stay labelled with the existing Screening Result /
  Historical Research — In-Sample / Out-of-Sample Evaluation labels.
- **Interact:**
  - The selected strategy carries across tabs.
  - A symbol in any research table opens Assessment in the right panel,
    with "Open in chart".
  - Historical runs open the screener table at that date with provenance,
    labelled as historical.
- **APIs:** unchanged (`evaluateStrategy`, `getContributionAnalysis`,
  `compareStrategies`, `runExperiment`, `getHistoricalValidation`,
  `historicalScreen`, `runWalkForwardBacktest`, …).
- **Tests:** strategy context survives tab switches; hold-out spend flow
  unchanged (`m14-studio`); labels intact.

### 6. Alerts (right panel)

- **Place:** the Alerts panel opens on "This symbol", with an "All" toggle,
  for the route's context symbol.
- **Create:** from the toolbar Alert button, the chart context menu at a
  price, the symbol page, or the Assessment panel. Each prefills the symbol
  and price basis.
- **Navigate:** triggered and armed rows open their chart, which keeps the
  existing other-symbol link. EOD semantics and conditions are unchanged.
- **Tests:** existing `m15-alerts` plus panel scope switching.

### 7. Markets, Data, Help

- **Markets:** breadth and sector tables; a sector or symbol row opens its
  Assessment.
- **Data and Help:** settings and help-centre layouts.
- No new data or analysis.

### Final implementation clarifications

**A. Assessment availability (all routes).** The Assessment strip icon
appears when the route supplies a context symbol. Otherwise it is hidden.

| Route | Context symbol |
|---|---|
| /chart | the active chart |
| Screener, Research tables, Markets rows | the selected row |
| Symbol pages | none: the page is the assessment |

- Selecting a row in Research or Markets sets the route's context symbol
  and opens Assessment. This fixes the earlier strip table, which left
  Assessment out of those routes.
- Leaving the route, or clearing the selection, clears the context. The
  panel then hides that tab and falls back to Watchlist.
- A panel never renders data for a symbol, strategy or run that differs from
  the current context. Queries key on `(symbol, strategy, runId)`. While a
  new key loads, the panel shows a loading state, never the previous
  result. Use react-query keys, not `keepPreviousData`.

**B. Run-level consistency.** Each Momentum25 view has one "run in view".

| View | Run in view |
|---|---|
| Screener | `getLatestRunForStrategy`, or the `?run=` id for historical / older runs |
| /chart | the latest run for the selected strategy |
| Research | the run or period it shows |

- Assessment calls `getStockExplanation(symbol, runId, strategy)` with that
  run id. The API already accepts `run_id`, so the screener and Assessment
  always match.
- `getWatchlistDetail(strategy)` returns its own `run_id`, which is always
  the latest. The watchlist rank columns show that run id. When it differs
  from the view's run (a historical screener), they show "Watchlist ranks:
  run #M (latest)" and are not presented as the screener's ranks. No
  backend change.
- Historical point-in-time screens (`historicalScreen`) carry their date
  and label. Assessment on such a row says "Historical — as of DATE" and
  never shows latest-run text.
- Every view shows its provenance line, so a mismatch is always visible.
  Journey test 4 covers the strategy switch. New journey test 8 covers a
  historical screener + watchlist mismatch notice + matching Assessment
  run id.

**C. Temporary evidence layers ("Show on chart").**
- Layers live in page-level React state keyed by `chartId` (in
  `chart/page.tsx`, passed to `PriceChart` as a new `evidenceLayers` prop).
  They are rendered as separate series, so they never touch
  `useChartShell`, the indicator catalogue, drawings or any document field.
- They are not persisted: a reload clears them, and so does a change of
  that chart's symbol or a layout change that removes the chart.
- Activating another grid cell keeps the layer on its own chart.
  Assessment shows "Shown on chart c2" when that chart is not active.
- If the same study is already enabled and saved, "Show on chart" only
  highlights it, and "Hide" does not remove the saved study.
- The legend marks layers "Evidence · temporary" with a remove ×. A user
  who wants to keep a layer uses the normal Indicators flow.
- **Verification** (in `integrated-workflows.spec.ts`):
  - zero document PUTs while showing or hiding a layer;
  - after reload: no layer, and the indicator, drawing and workspace
    documents are byte-identical to before;
  - grid activation and the symbol change cases above;
  - the `save-state` text stays "Saved" throughout.

**D. Capability preservation before any move.**
- Before `ScreenerDetail` retires, or anything moves into Assessment, the
  ledger lists every field and action of the source component. For
  `ScreenerDetail`, that is:
  - the 1-year close line;
  - qualification badge, rank, momentum score, setup score and gate
    failures;
  - "Why it ranks" and "What could invalidate this";
  - "Open chart" and "Full research".

  Also list everything in today's Details tab, and in the chart-header
  Analyse and Research buttons.
- Each item gets its new location and a check: a spec assertion where the
  item is functional, or a ledger note with a screenshot where it is
  display-only.
- The source component is deleted only when every row passes in the same
  commit. Anything with no natural new place stays where it is.

### Extension convention (for Value25 and other future engines)

Momentum25's UI integration code lives in one folder,
`src/components/momentum25/`. It holds the Assessment panel, legend chip,
screener column sets and filters, watchlist columns, chart-layer mapping and
provenance line. It plugs into named shell points: the panel context, the
legend chip slot, the screener column-set and filter props, the watchlist
column hook and the chart layers. A second engine adds a sibling folder at
the same points. No registry or interface is built until that second engine
exists (ponytail + "extension points only where the architecture requires
them"). The design record (D22) documents the points.

### End-to-end journey tests (new `web/e2e/integrated-workflows.spec.ts`)

1. **Screener → Chart → Ranking → Evidence → Research → Return:**
   - Screener: pick a strategy, filter "Qualified", select row #1.
   - Assessment shows the rank, and its provenance names the run id.
   - "Open in chart": the active chart shows the symbol, and the legend chip
     shows the same rank.
   - Expand a criterion, then "Show on chart": the layer is visible.
   - "Full analysis": the symbol page focuses the criterion's evidence
     section.
   - Open the strategy in Research: the strategy context matches.
   - "Back to chart": the same symbol, layout and drawings are back, and no
     other grid cell has changed.
2. **Grid integrity:** in 2×2 with four symbols, "Open in chart" from the
   screener changes only the active cell. Assessment follows activation.
3. **Watchlist parity:** watchlist rank and qualification equal the
   screener's for the same run. A row click moves only the active chart.
4. **Strategy switch:** changing the strategy updates the screener, the
   Assessment and the watchlist columns, and each shows the new run id.
5. **Provenance mismatch:** a chart whose last bar is newer than the run
   shows the as-of notice (fixture via `db.py`).
6. **Alert from context:** create an alert from Assessment or the chart
   menu, see it scoped under "This symbol", follow the triggered row back to
   the chart.
7. **Historical labelling:** a historical run opened from Research shows the
   historical label and date and never the latest-run label.

## Ground rules

- **The skin stays Wickstreet's.** Keep the paper/ink surfaces, the sea-green
  accent, Inter, the `indigo`→sea-green token scale, the `--ws-*` variables
  and the current candle and series colours in both themes. TradingView
  supplies structure, geometry, grouping, density and behaviour only. Every
  new component uses the existing tokens and classes (`.workstation-button`,
  `--ws-line`, `focusRing`). There is one design language on every route.

- Clean room: observe TradingView's public rendered pages and support docs
  only. Never read its CSS/JS. Own SVG icons, own token values, Wickstreet
  brand. Reference screenshots stay in the scratchpad; never commit them.
- Keep accessible names that ~108 E2E tests use (`toolbar "Drawing tools"`,
  `Horizontal line`, `Weekly bars`, `Log scale`, tabs `Watchlist/Details/
  Alerts`, `h1` = symbol, `price-chart`, `crosshair-readout`, footnote
  "N daily bars from the stored NSE series"). Where a control moves behind a
  flyout or popover, add one E2E helper rather than weakening assertions.
- `globals.css` selects by `aria-label` in places; keep those labels or move
  the rules to classes in the same commit.
- Lightweight Charts runs with `attributionLogo: false`, so the "Charts by
  TradingView Lightweight Charts™" credit must stay visible on /chart once the
  footer goes (put it in the bottom bar).
- Leave the modified `audit-evidence/**` files from Codex's E2E runs out of
  every commit (memory: full E2E rewrites them). Don't discard them.
- At most two agents: `dashboard-builder` (per global CLAUDE.md) and, from
  step 8 only, one `engineering-lead` worker on non-chart pages in a worktree.
  No shared files between me and the worker after step 1.

- Commit only named paths (`git add <path>…`), never `-A` or `.`. Review
  each file's diff before staging it.

## Core technique: chart chrome slots

TradingView has one top toolbar, one left rail and one bottom range bar that
act on the **active** chart. Today each `PriceChart` renders its own toolbar,
rail and legend, holding the state inside (1,729 lines). Lifting that state is
a large refactor. Instead, add one optional prop to `PriceChart`:

```ts
chrome?: { toolbar: HTMLElement | null; rail: HTMLElement | null; rangeBar: HTMLElement | null }
```

When `chrome` is set, `PriceChart` renders its interval/type/undo-redo group,
its `DrawingRail` and its range/scale group through `createPortal` into the
page's slots. The chart page passes `chrome` only to the active chart; grid
cells stay compact. State stays where it is. Stock, analysis, Elliott Wave and
lab pages pass nothing and keep the inline toolbar.

The slot elements are stable page-level nodes held in state (callback refs),
so a portal target never changes identity. Only the portal **source** moves
when the active chart changes. The chart canvas, its `IChartApi` and its
document subscription are never inside a portal and never remount.

**Portal validation gate (step 3a, before any more chrome moves).** First
port only the rail, in a 2×2 grid. Proceed only if all of these pass:

1. **Active switch.** Clicking cells activates them. The rail always drives
   the active cell's tool. Arming a tool in cell A, then activating B, leaves
   A unarmed. This uses the existing cancel-on-deactivate path.
2. **Focus retention.** If focus is inside a portalled control when the
   active cell changes, it moves to the same control in the new active cell,
   falling back to its `price-chart`. Focus never drops to `body`. Assert
   with `document.activeElement` in an E2E test.
3. **Persistence.** Activation alone causes no document PUT except the
   accepted `active_chart_id` write, counted with `page.on('request')`.
   `save-state` stays "Saved". Drawings, indicators and tool settings
   round-trip after reload in the active and inactive cells.
4. **Render stability.** The chart instance survives activation and portal
   moves. Prove it with a test-only `data-chart-generation` counter on the
   container, which must not change. There are no console errors. The 4×4
   `M13_BENCH` P95 and pan FPS stay within 10% of Codex's 1,348 ms and 61 fps.
5. **Rapid switching.** Twenty cell activations in under 2 s, by click and by
   keyboard. The rail ends on the last cell, with no stale portal or
   duplicate rail in the DOM, and the generation counters are unchanged.
6. **Layout changes.** 1×1 → 2×2 → 4×4 → 1×1 while a tool is armed and
   focus is in the rail. The slots re-target to the surviving active chart,
   the armed tool is cancelled, and no React "unmounted portal" warnings
   appear.
7. **Chart removal.** Removing the active cell (layout shrink) or changing
   its symbol leaves the slots empty for one frame at most, then the new
   active chart fills them. No handler from the removed chart fires.
8. **Keyboard shortcuts.** Alt+T/H/V/F, Alt+Shift+R, Esc, Ctrl/⌘+Z/Y,
   Delete, the arrow keys, Alt+R and Alt+I act only on the active chart
   after each kind of switch.

If any criterion fails and a fix is not small and clearly correct, take the
fallback. Do not force portals.

**Fallback if the gate fails:** lift only `drawingTool` and `interval` into
`useChartSlot`, which already owns per-chart settings, and render page-level
controls from it. Record the result in the design record.

## Steps (one local commit each)

0. **Continuity (no blind commits).** First, copy this plan to
   `docs/history/plans/2026-10-19-tradingview-workstation-plan.md` and
   commit it alone. Start `dashboard-builder` in the background.
   - Review Codex's uncommitted diff file by file: `PriceChart.tsx`,
     `AlertsTab.tsx`, `useChartSlot.ts`, `chart/page.tsx`,
     `traded-prices(.test).ts`, the new `alert-levels*` and
     `alert-editor-basis*` files, `transformation.spec.ts`,
     `design-record.md`, `TRANSFORMATION_PROGRESS.md` and the untracked
     `WICKSTREET_TRANSFORMATION.md`.
   - Fix only real defects. Then run `npm test`, lint, typecheck and the
     specs these files touch (`transformation`, `m15-alerts`, `m11-slice`).
   - Stage those named paths only. Keep the doc files out of this commit if
     their "pending results" claims are not yet true.
   - Leave `audit-evidence/**` unstaged and untouched.

1. **Baseline verification and reference.** Do not re-implement anything yet.
   - Run the app on the synthetic `*_e2e` database. Exercise BL-01..BL-15
     and the ten OpenChart audit fixes in the browser, at their current
     locations, and note pass or fail for each. Fix only actual regressions.
     Each one's location becomes a row in the step-9 matrix, so the
     relocation steps carry it over and don't rebuild it.
   - Capture public TradingView chart, screener and symbol pages at 1440×900
     into the scratchpad. Measure only **structure**: bar heights, rail and
     strip widths, control order and grouping, panel proportions and density.
   - **No token or colour changes.** Chart styling changes only where it is
     behaviour, not look. One example: a dashed crosshair with the
     price/date labels on the axes. These use the existing palette.
   - Record the "TradingView structure, Wickstreet skin" rule as D22 in
     `docs/architecture/design-record.md`. Amend, don't rewrite,
     `docs/current/workstation-design.md` with the new geometry.

2. **Workstation shell, then the Supercharts layout.**
   - **2a:** add `WorkstationShell` (see "Unified workstation shell") in
     `layout.tsx` for every route. It holds the header bar with the ☰ menu,
     the route slot and the right strip with `SidePanel` lifted from the
     chart page, plus the shell-level selected-symbol context.
   - `NavBar` keeps only its phone bottom nav and `SymbolSearch` parts, which
     move into the shell. Every nav entry maps to the ☰ menu or the header.
   - **2b:** rebuild `src/app/chart/page.tsx` inside the shell as a CSS
     grid: top toolbar 38px,
   left rail 52px, chart, right icon strip 45px plus a 300px panel, bottom
   range bar 30px, and an optional bottom panel. Top toolbar, left to right:
   - ☰ app menu: all site routes, theme, keyboard shortcuts, About, credit
   - symbol button (stays `h1`, opens search)
   - Compare (+)
   - [interval D W M]
   - chart-type icon menu
   - fx Indicators
   - Alert
   - Undo/Redo
   - spacer
   - layout grid-icon popover, which also holds the Sync options
   - Save state
   - settings gear: Volume, the MA quick toggles from "Studies", scales

   "Analyse" and "Research" move to the Details panel and the symbol context
   menu. Replace `CHROME_HEIGHT` and `useChartHeight` with the plot's measured
   grid cell. Use the existing `autoHeight` ResizeObserver path.

   **Adaptive layout.** The CSS grid uses container breakpoints, so the chart
   always gets the space left after the chrome:

   | Width | Top bar | Left rail | Right sidebar | Bottom |
   |---|---|---|---|---|
   | ≥1280 desktop | full toolbar | 52px rail with flyouts | 45px strip + 300px panel, inline | range bar + optional bottom panel |
   | 1024–1279 laptop | lower-priority controls fold into a "⋯" overflow menu (gear, Undo/Redo) | 44px rail | strip inline; panel opens as an overlay above the chart, without resizing it | range bar; bottom panel overlays |
   | 600–1023 tablet | symbol, interval, Indicators, ⋯ | 40px rail | no strip; one header button opens the panel as a right sheet | range bar wraps to one scrollable row |
   | <600 phone | symbol, interval, ⋯ | rail collapses to one "Draw" button that opens the groups as a bottom sheet | panel as a full-width bottom sheet | range bar scrolls horizontally; app menu replaces the site's bottom nav |

   - Sheets and overlays never take layout width from the plot.
   - No horizontal document overflow at 390×844, 720×450 (200% reflow),
     768×1024, 1440×900 and 1920×1080. `r2-viewport-audit` asserts this.
   - Touch targets stay at least 32px (`pointer: coarse`).
   - The plot keeps at least Codex's measured phone area (334×544) and gains
     area on desktop.

3. **Chart chrome slots and legend.**
   - **3a:** pass the portal validation gate above. The gate's tests become
     permanent specs in `transformation.spec.ts`.
   - **3b:** add the full `chrome` prop and move the remaining chrome. Move the
   `crosshair-readout` and study legend into one top-left overlay in the
   familiar order: symbol · interval · NSE, then O H L C and change, then one
   line per study with hover eye/settings/remove buttons that call the
   existing handlers. Bottom range bar:
   - left: 1W 1M 3M 6M 1Y MAX
   - right: footnote (truncated, with the full text in `title`), `%`, `log`,
     Fit, "EOD · NSE", and the credit

   Grid cells: a small overlay legend in each cell, and the existing
   Wickstreet selection colour (`--ws-accent`) as the active-cell border,
   as `.grid-cell[aria-current='true']` does today. There is no per-cell
   toolbar. The top toolbar and rail act on the
   active cell. Update the E2E specs that click per-cell controls.

4. **Grouped drawing rail.** In `DrawingRail` (`PriceChart.tsx:124-165`), use
   TradingView's group order:
   - Cursor
   - Lines: Trendline, Ray, Extended line, Horizontal line, Horizontal ray,
     Vertical line, Cross line, Parallel channel
   - Fibonacci: Fib retracement
   - Shapes: Rectangle
   - Annotation: Text note
   - Measure: Price range
   - a separator, then Remove objects (existing Clear)

   Each group button shows its last-used tool and has a corner arrow that
   opens a flyout listing name and shortcut. Arrow keys and Esc work in the
   flyout, and `aria-pressed` stays on tools. Move the "Objects" inspector
   (visibility, lock, undo list) into an **Object tree** right-panel tab.
   Add the E2E helper `pickTool(page, name)`.

5. **Right sidebar and native Momentum25 core** (me, before the worker
   starts).
   - Turn `SidePanel` into the route-adaptive vertical icon `tablist` strip
     described in the shell section. Clicking the active icon collapses the
     panel. Keep the tab names, "Close panel" and `useRightPanel`.
   - Build `src/components/momentum25/`:
     - the provenance line;
     - the Assessment panel, with criterion drill-down and "Show on chart"
       layers (workflow 2);
     - the legend chip;
     - watchlist Rank and Qualified columns (workflow 3);
     - screener column sets and filter pills (workflow 1).
   - Add the alerts scope "This symbol / All" and contextual create
     (workflow 6). Give the alerts list the alert manager's row structure.
     EOD semantics stay.
   - Add the context-model pieces: `?from=` handling and "Back to chart".

6. **Bottom panel.** **Stock Screener** reuses `MomentumTable` with the
   step-5 column sets and filters, in compact mode. A row click loads the
   active chart, and Assessment updates without leaving the chart.
   **Strategy Studio** and **Research** switch the centre to those routes
   inside the same shell, with `?from=` set. Add collapse and maximise
   chevrons. Save open/closed in localStorage, because it is a per-viewer
   convenience.

7. **Dialogs** (structure only, existing skin). Restructure
   `SymbolSearchDialog` like TradingView: large centred dialog, search field
   on top, "All · Stocks" chips, and rows of symbol | name | NSE with
   keyboard navigation. Restructure `IndicatorDialog` and `OverlayPicker`
   with a left category list from the existing catalogue categories and a
   right searchable list. Keep the dialog names.

8. **Routes as native workflow surfaces** (worker, in parallel with steps
   6–7, after step 5 lands). The worker touches only these route files and
   consumes `src/components/momentum25/` without editing it. Requests for
   changes there come back to me.
   - Each route renders in the shell's centre and fills the route slot. None
     keeps its own site header or footer.
   - Each implements its workflow contract from "Native Momentum25
     integration" (1, 4, 5, 7), not only a layout.
   - TradingView supplies the structure; every surface keeps today's
     Wickstreet tokens. The worker may not edit `theme.ts` or the `--ws-*`
     variables.
   - `PageHeader` stops being a page banner. It renders the route's title
     and controls into the shell's route slot.
   - `Card`, `PageHeader`, `MetricCard` (`src/components/shared/Card.tsx`):
     TradingView's flat-section structure (bold headings, `--ws-line`
     dividers, key-stat grids) in the existing paper and sea-green skin. This
     restyles all routes at once.
   - `/`: a TradingView Stock Screener (workflow 1).
     - The title row "Stock Screener" with the strategy as the screen picker
       and the provenance line.
     - Summary cards fold into a stat strip.
     - Column-set tabs and filter pills.
     - A full-width dense table with a sticky header and symbol column and
       single-line names.
     - The selected row opens the shell's Assessment panel, which retires
       `ScreenerDetail`.
   - `/stock/:symbol` (+ analysis, Elliott Wave): a symbol-page header with
     initial badge, name, `SYMBOL · NSE`, price and change, and an
     "EOD as of" line. A tab row Overview | Analysis | Elliott Wave | Chart
     ↗ replaces `SectionNav`.
   - `/backtest`, `/experiment`, `/studio`: strategy-tester tabs (Overview |
     Performance summary | List of trades/rebalances | Properties). Keep the
     Screening Result / In-Sample / Out-of-Sample labels and Studio's
     hold-out flow untouched.
   - `/data` and `/learn`: settings and help-centre layouts with a left nav.
     `/market`, `/strategies`, `/validation`, `/analytics`, `/historical` and
     `/watchlist` inherit the flat sections and dense tables.

   Update the heading assertions this changes (`r2-accessibility`,
   `momentum-ranking-display`, `m10-stack`).

8b. **Integrated workflow tests** (me). Write
    `web/e2e/integrated-workflows.spec.ts` with journeys 1–7. These, not
    route smoke tests, are the acceptance gate for steps 5–8. Fix defects
    they find at the root.

9. **Evidence and docs.** Wickstreet screenshots at 1920, 1440, 768 and 390,
   in light and dark, under `audit-evidence/tradingview-clone/`. Add the
   correspondence matrix `docs/current/tradingview-correspondence.md`. It has
   two parts:
   - **Screen matrix:** reference, route, structure, behaviour, changes,
     limits, evidence.
   - **Capability ledger:** one row per existing capability, with columns:
     - capability
     - previous UI location
     - new primary place
     - how a user finds it
     - context consumed and preserved
     - task done without navigation (y/n)
     - APIs used
     - verified working (spec name or manual check)
     - status

   Seed the ledger in step 1 from the baseline pass: every control in the
   chart map, every side-panel and alert function, every route and nav
   entry, every keyboard shortcut in `src/lib/shortcuts.ts`, and BL-01..15.
   Update it in the same commit as each move. A step is not done while any
   row it touched is unverified.

   Every existing route keeps its URL and stays reachable: from the site
   header or the Research menu, and on /chart from the ☰ app menu.

   Update `WICKSTREET_TRANSFORMATION.md` and `TRANSFORMATION_PROGRESS.md`.

## Scope phases

### Phase A — immediate transformation (steps 0–9 above)

Phase A delivers the workstation architecture, navigation, interactions,
native Momentum25 integration and every existing capability. Its acceptance
is steps 0–9, journeys 1–8 and the full regression, performance and
accessibility suite. `lab/chart-grid` stays a diagnostic tool but inherits
the shell and tokens, so it matches the rest of the app.

### Backend policy (all phases)

- Narrow, backwards-compatible API, persistence and calculation-support
  changes are allowed where native integration or a Phase B capability
  needs them. Typical cases are an optional query parameter, a new document
  type or a new alert-source kind.
- Each one comes with:
  - backend tests;
  - strict mypy, Ruff and the layer-import contracts (domain stays pure);
  - an Alembic migration when there is a schema change (additive only);
  - regenerated `api-schema.ts`.
- Momentum25 scoring, gates, ranking, research semantics, provenance and
  stored historical results do not change.
- Any change to alert evaluation semantics gets an ADR amendment, following
  `ADR-013-alert-amendment.md`.
- A change to investment methodology stops for owner approval (standing
  rule).

### Phase B — charting-parity milestones (after Phase A is accepted)

Phase B is ordered by user value, then by dependency. Each milestone is its
own set of local commits with its own ledger rows and acceptance tests. If
one stalls, skip to the next; none blocks Phase A.

| # | Capability | Depends on | Data correctness | Acceptance |
|---|---|---|---|---|
| B1 | **Richer screener filters + saved screens** | step 5 filter pills | Filters use existing run fields only (scores, RS, rank, gate status, categories, Δ rank) | Numeric range and category filters. Results equal a reference filter over `getRankings` for the same run. Saved screens persist as a new `user_documents` kind with ETag/412 like other documents. Deterministic order. |
| B2 | **Bar Replay (EOD)** | step 3 chrome slots (toolbar Replay button) | Daily bars are exact. Causal studies (MAs, RSI, MACD, ADX) need only past bars. Pattern detection and Elliott Wave may use later pivots, so they are disabled during replay with a notice. | Replay date picker, step, play and speed, and exit. No series, compare line, study or legend value shows a bar after the replay date (unit test plus E2E bar-count check). Assessment shows "Not available in replay" unless a historical run dated ≤ the replay date exists, in which case it shows that run with its provenance. Alerts are not evaluated or created in replay. Drawings made in replay save normally. Exiting restores the viewport. |
| B3 | **Additional drawing tools** | step 4 grouped rail | Anchors are stored at traded prices (`price_basis: 'traded'`) like the existing tools | Batch 1: arrow, date range, date-and-price range, ellipse, triangle. Batch 2: Fib extension, pitchfork, callout, price label. Each tool passes create, select, drag, resize, style, lock/hide, undo/redo, persistence round-trip, corporate-action rescale and the flyout and shortcut checks. Additive `DrawingKind` values only; old documents still load. |
| B4 | **Drawing-linked alerts: trendline/ray crossing at EOD close** | existing captured-drawing alerts (BL-15); B3 not required | The line's value on each session date is a linear function of the date index in traded-price space, rescaled by `factor(armed_after)` as horizontal alerts are. Close-to-close only, with no intraday-path claims. | ADR amendment. A backend evaluator for the new source kind. Golden tests for deterministic triggers, the corporate-action case, and the snapshot freeze (editing a drawing never silently changes the rule). UI from the drawing context menu, "Alert on this line…". |
| B5 | **Volume Profile (estimated)** | step 3 legend and layers | **Only daily OHLCV exists.** Any per-price distribution is an estimate: each bar's volume is spread evenly across its high–low range into price bins. It is never presented as traded volume at price. | Visible-range profile through a Lightweight Charts series primitive. The permanent label reads "Estimated from daily bars — not traded volume at price", and "point of control" and "value area" carry "est.". A unit test checks allocation and determinism. It is off by default and is a display layer only (never feeds screening or alerts). If the owner rejects estimate-based profiles, B5 is dropped. |

Phase B rows join the capability ledger with their limitations stated.

### Phase C — major future initiatives (evaluation only, no code, no placeholder controls)

Write `docs/history/plans/2026-10-phase-c-evaluations.md`, with one section
per initiative:

- **Pine-style scripting:** sandboxing (a WASM or worker isolate),
  determinism, a resource budget, clean-room language design, and the
  security review.
- **Intraday market data:** exchange data rights. The NSE terms blocker
  already found in the M16 data-use audit applies. Also licensing, storage
  and EOD-architecture impact, and NFR-11.
- **Broker/trading integrations:** credentials and security, regulatory
  exposure, order-safety design, and independence from analytics.

Each section names its dependencies, risks, owner decisions and a go/no-go
recommendation. No UI ever shows controls for these capabilities.

## Verification (each step, final run serial)

- `cd web && npm test && npm run lint && npm run build`.
- When the backend changes: the full backend pytest suite, strict mypy,
  Ruff on the touched files only (memory: no repo-wide format) and the
  layer-import contracts. Migrations are tested only against the `*_e2e`
  clone.
- Focused Playwright specs per step, then the full suite serially against a
  `*_e2e` database (`make e2e-db`, `E2E_DATABASE_URL`; never export
  `M25_DATABASE_URL`; keep port 8766 free for the NFR-11 cold test).
- Render-and-compare each screen with the Playwright MCP against the
  scratchpad reference at the same viewport. Check toolbar heights, rail and
  strip widths, control order, and no horizontal overflow at 720×450 and
  390×844.
- Exercise the workflows by hand:
  - symbol search → chart
  - draw, edit and undo every tool, then reload
  - 2×2 and 4×4 grids with the active chart and the rail
  - indicators: add, configure and hide
  - compare
  - an alert from the chart, then edit and re-arm it
  - screener row → chart
  - the Studio hold-out flow
- Axe checks (`final-accessibility`, `r2-accessibility`) in both themes.
- NFR-11 (`nfr11-chart-open.spec.ts`) warm P95 ≤ 1 s, cold ≤ 3 s, and
  `M13_BENCH=1` 16-chart bench, recorded in the matrix.
- Final report: commits, `git status`, results, limits; no pixel-perfect or
  superiority claims.

## Phase breakdown (tracking)

Each phase is one local commit with its own gate. A phase is done only when
its gate passes and its ledger rows are verified. IDs map to the steps above.

### Phase A — workstation

| ID | Phase | Gate |
|---|---|---|
| A0 | Continuity: plan, Codex diff review, docs (done: `28d0fcc`, `ca9d838`, `1413583`) | unit, lint, typecheck, `transformation`, `m15-alerts`, `m11-slice` |
| A1.1 | Baseline: BL-01..15 and the ten OpenChart fixes in the browser on `*_e2e`; fix regressions only | pass/fail noted per item |
| A1.2 | TradingView structure reference at 1440×900 (chart, screener, symbol page) in the scratchpad | measurements noted, nothing committed |
| A1.3 | Seed the capability ledger; D22 in the design record; amend `workstation-design.md` | every chart-map control, panel, alert, route, shortcut, BL item has a row |
| A2.1 | `WorkstationShell`: header bar, ☰ menu, search pill, route slot, credit edge; `NavBar` keeps the phone nav only | every nav entry reachable; build green |
| A2.2 | Lift `SidePanel` and `useRightPanel` into the shell; route-supplied context symbol | panel state survives reload; no stale panel |
| A2.3 | /chart CSS grid (38 / 52 / 45+300 / 30) and toolbar order; Analyse and Research move; `autoHeight` replaces `CHROME_HEIGHT` | chart specs green; plot area ≥ baseline |
| A2.4 | Adaptive layout at the four breakpoints; sheets and overlays | `r2-viewport-audit` at 5 viewports; touch ≥ 32px |
| A3.1 | Portal validation gate: rail only, 2×2 | all 8 criteria as permanent specs, or fallback recorded |
| A3.2 | Full `chrome` prop: toolbar and range-bar groups (or fallback) | criteria 1–8 still green |
| A3.3 | Top-left overlay legend: readout plus study lines | eye/settings/remove call existing handlers |
| A3.4 | Bottom range bar; compact cell legends; active-cell border; per-cell specs updated | `M13_BENCH` within 10% |
| A4.1 | Grouped drawing rail with flyouts; `pickTool` helper | keyboard and `aria-pressed` specs |
| A4.2 | Object tree right-panel tab | visibility, lock, undo list work |
| A5.1 | Route-adaptive icon strip `tablist` | tab names and "Close panel" kept |
| A5.2 | `momentum25/` provenance line and run-in-view keys `(symbol, strategy, runId)` | no previous-key render while loading |
| A5.3 | Assessment panel with criterion drill-down; ledger rows for `ScreenerDetail`, Details, Analyse, Research | every source field has a verified new place |
| A5.4 | "Show on chart" evidence layers and legend chip | zero document PUTs; reload clears layers |
| A5.5 | Watchlist Rank and Qualified columns; run mismatch notice | parity with the screener for the same run |
| A5.6 | Screener column sets and filter pills (components) | filter and sort determinism on fixtures |
| A5.7 | Alerts "This symbol / All" scope and contextual create | `m15-alerts` plus scope specs |
| A5.8 | `?from=` handling and "Back to chart" | same-origin paths only |
| A6 | Bottom panel: embedded Screener, Studio and Research navigation, collapse and maximise | row click moves only the active chart |
| A7.1 | `SymbolSearchDialog` structure | keyboard navigation; dialog name kept |
| A7.2 | `IndicatorDialog` and `OverlayPicker` structure | category list from the catalogue |
| A8.1 | Worker: `Card`, `PageHeader`, `MetricCard` flat sections; `PageHeader` fills the route slot | all routes build |
| A8.2 | Worker: `/` Stock Screener; `ScreenerDetail` retires | workflow 1 contract |
| A8.3 | Worker: symbol pages header and tabs | workflow 4 contract |
| A8.4 | Worker: Research workspace tabs | workflow 5 contract; `m14-studio` green |
| A8.5 | Worker: Markets, Data, Help, Watchlist, lab grid | workflow 7 contract |
| A8.6 | Worker: heading assertions (`r2-accessibility`, `momentum-ranking-display`, `m10-stack`) | specs green |
| A8b | `integrated-workflows.spec.ts` journeys 1–8 | all journeys green |
| A9.1 | Screenshots at 1920, 1440, 768, 390 in both themes | files under `audit-evidence/tradingview-clone/` |
| A9.2 | Finish the correspondence matrix and capability ledger | no unverified row |
| A9.3 | Final serial run: full E2E, axe, NFR-11, `M13_BENCH`; progress docs; final report | Phase A accepted |

A8.x runs in parallel with A6–A7, only after A5 lands.

### Phase B — charting parity (after Phase A is accepted)

| ID | Phase | Gate |
|---|---|---|
| B1.1 | Numeric range and category screener filters | equal to a reference filter over `getRankings` |
| B1.2 | Saved screens as a `user_documents` kind with ETag/412 | backend tests, migration on `*_e2e`, `api-schema.ts` regenerated |
| B2.1 | Replay series truncation | unit test: no bar after the replay date |
| B2.2 | Replay UI; studies, Assessment and alerts rules | E2E bar-count check; viewport restored on exit |
| B3.1 | Drawing batch 1: arrow, date range, date-and-price range, ellipse, triangle | full per-tool checklist |
| B3.2 | Drawing batch 2: Fib extension, pitchfork, callout, price label | full per-tool checklist |
| B4.1 | ADR amendment for trendline/ray crossing alerts | owner review |
| B4.2 | Backend evaluator for the new source kind | golden tests, corporate-action case, snapshot freeze |
| B4.3 | "Alert on this line…" UI | E2E create and trigger |
| B5.0 | Owner decision on estimate-based Volume Profile | accept or drop B5 |
| B5.1 | Volume Profile (estimated) display layer | allocation and determinism unit test; label permanent |

### Phase C — evaluations (no code)

| ID | Phase | Gate |
|---|---|---|
| C1 | Pine-style scripting section | dependencies, risks, owner decisions, go/no-go |
| C2 | Intraday market data section | same |
| C3 | Broker/trading integrations section | same |
