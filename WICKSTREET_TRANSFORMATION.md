# Wickstreet product transformation

Local implementation, 2026-10-19 to 2026-10-20. No push or publication. Financial scoring, screening, immutable research results, EOD data architecture, traded-price drawing anchors and conflict-safe document persistence remain intact.

Current delivery: Phase A and B1–B4 are implemented. Phase B visual sign-off evidence and final verification are in [the evidence index](audit-evidence/phase-b/README.md). B5 Volume Profile remains deferred by the owner; Phase C has not started. The local progress dashboard is maintained at `.dashboard/index.html`.

## Working experience

- **Chart foundation:** full-width workstation; compact symbol/context controls; light/dark paper-and-ink surfaces with sea-green focus/action states; readable chart colours; full stored history behind each initial range; fit/reset and stable comparison anchors.
- **Studies:** on-chart names and latest values; colour, parameters, hide/show, removal and immediate restoration in one searchable inspector. Configurable RSI/MACD are display-only and have separate keys; authoritative backend studies remain available. Percentage mode hides price studies to avoid misleading independent rebasing.
- **Workspace and drawings:** one-row grid headers; stable cell identity during activation; per-cell symbol/interval and synchronisation; active drawing rail in grids; shared drawing rail on research pages; object visibility/locking/dashes; inline notes; per-drawing undo/redo and restoration. Symbol changes discard unfinished annotation state, while saved drawings retain their established basis and merge rules.
- **Analysis:** selected-symbol Analyse and Research transitions; Momentum25 scores, reasons, gate failures and expandable evidence; sortable watchlist; global command search; Strategy Studio explains hypothesis → evidence → hold-out without changing methodology or claims.
- **Monitoring:** edit armed conditions with optimistic revisions; visible EOD price levels; armed/history organisation and last-session feedback; saved horizontal-line and rectangle snapshots. Drawing/data preconditions prevent capturing stale coordinates. Re-arm and edit preserve adjustment semantics. [Accepted ADR amendment](docs/architecture/adr/ADR-013-alert-amendment.md).
- **Responsive/accessibility:** search no longer floats over the plot; contextual inspector on smaller screens; bottom-navigation clearance; touch targets; keyboard inspector dismissal and tab navigation; unique search IDs; reduced-motion behavior and equivalent reflow regression.

Design tokens, geometry and interaction rules: [workstation design system](docs/current/workstation-design.md).

## Before and after

| Surface | Before | After |
|---|---|---|
| Desktop | [Baseline](audit-evidence/transformation/before/chart-desktop.png) | [Light](audit-evidence/transformation/after/chart-1440-light.png) · [Dark](audit-evidence/transformation/after/chart-1440-dark.png) |
| Phone | [Baseline](audit-evidence/transformation/before/chart-mobile.png) | [Transformed](audit-evidence/transformation/after/chart-390-light.png) |
| Sixteen charts | [Baseline](audit-evidence/transformation/before/chart-grid-16.png) | [Transformed](audit-evidence/transformation/after/chart-grid-16.png) |
| Screening | [Baseline](audit-evidence/transformation/before/dashboard.png) | [Transformed](audit-evidence/transformation/after/dashboard.png) |
| Strategy Studio | [Baseline](audit-evidence/transformation/before/studio.png) | [Transformed](audit-evidence/transformation/after/studio.png) |
| Data management | [Baseline](audit-evidence/transformation/before/data.png) | [Transformed](audit-evidence/transformation/after/data.png) |
| Stock research | [Baseline](audit-evidence/transformation/before/stock-detail.png) | [Transformed](audit-evidence/transformation/after/stock-detail.png) |
| Tablet / reflow | — | [768px](audit-evidence/transformation/after/chart-768-light.png) · [720px, 200% equivalent](audit-evidence/transformation/after/chart-720-dark.png) |

At 1440×900, the plot changed from 1068×600 at y=198 to 1076×676 at y=163: 13.5% more plot area. At 390×844, the plot begins at y=215 rather than 345, with the entire 544px plot clear of bottom navigation. Before measurements are the completed compatibility audit's recorded geometry; after measurements and zero horizontal-overflow checks are in [geometry.json](audit-evidence/transformation/after/geometry.json). Native Chrome 200% zoom was also exercised on the working preview. Screenshots use synthetic data.

## Audit backlog integrated

BL-01 seamless history; BL-02 drawing access in grids; BL-03 on-chart study legends; BL-04 study colour/visibility; BL-05 inline notes; BL-06 armed price levels; BL-07 armed-alert editing; BL-08 drawing lock/hide/dash; BL-09 readable triggered history; BL-11 configurable display RSI/MACD; BL-12 safe percentage-study policy; BL-13 watchlist sorting; BL-14 compact/mobile/grid chrome; BL-15 bounded EOD drawing snapshots with an ADR.

The ten audit fixes remain covered. In particular, `server-document.ts`'s load/edit merge protection was retained unchanged. The earlier full-suite reflow failure was explained and confirmed fixed by a baseline-only 3/3 accessibility/reflow run before UI changes.

## Five quality dimensions

| Dimension | Before evidence | Delivered evidence |
|---|---|---|
| Visual | Existing audit screenshots and geometry | Both themes, compact controls, more useful plot area, responsive screenshots |
| Interaction | Browser prompt notes; shortcut-only grid drawings; price-study values inside dialog | Inline notes, active-cell rail, legends, object inspector, stable cell activation |
| Productivity | Open/close indicator dialog to read values; delete/recreate an alert to correct it | Values visible without those two dialog actions; edit and save an armed rule; selected security retained across analysis/research/chart |
| Functional | Audit backlog | Integrated workflows and new journey tests; all prior routes remain available |
| Technical | Existing unit/E2E/performance baselines | Financial/corporate-action/merge regressions plus new lifecycle and stale-input protection; final results below |

No measured superiority over TradingView or OpenChart is claimed. No competitor source, styling or artwork was copied; provenance is recorded in D17–D21.

## Validation

Final production-build results and performance measurements are recorded in [Phase B evidence](audit-evidence/phase-b/README.md). Commands use dedicated `*_e2e` PostgreSQL databases and a disposable Redis service, with scheduler and direct exchange downloads disabled. Existing production database records were not changed.

Latest continuation on `1ed0dd8`: 921 backend tests, strict mypy on 263 source files, Ruff and both layer-import contracts passed. Web: 141 unit tests, zero-warning ESLint and TypeScript passed. The full serial browser run passed all 227 cases, including all six opt-in grid benchmark cases. NFR-11 warm P95 was 166 ms and cold P95 was 505 ms. Both meet their 1 s / 3 s limits. Raw logs and measurements are retained under `audit-evidence/phase-b/final/`.

Automated axe checks cover dashboard, chart and Studio in both themes. Keyboard, native modal focus, reduced motion, 200% equivalent reflow, touch drawing/panels and viewport overflow have explicit regression coverage. Native zoom was manually inspected. This is not a complete screen-reader or WCAG-conformance certification.

## Intentional limits

- Daily completed-bar alert evaluation, not continuous intraday monitoring. No external delivery.
- Drawing alerts snapshot a saved horizontal line or the rectangle's inclusive **price band**; the rectangle's date extent does not terminate the future condition. Close-to-close entries/exits are deterministic; no assumption about intraday paths or gaps through an entire band. Edits refresh a snapshot only explicitly. Phase B subsequently added trendline, ray and extended-line EOD snapshots under the accepted line-alert ADR; arbitrary paths remain excluded.
- Configurable display studies never feed screening, ranking or alerts. Price studies are hidden on percentage axes; comparisons remain available.
- Volume Profile remains deferred. Phase B added nine drawing tools. Scripting, AI agents, brokerage execution, intraday feeds and hosted tenancy were not introduced. Named workspaces/resizable docking remain optional follow-up capabilities; the existing default workspace and independent chart settings persist.
- Touch drawing uses the established date/price anchors; dense desktop grids remain a desktop workflow. Production-scale data/performance will vary from synthetic fixtures.

## Local commits

- `f76ada7` — armed-alert editing, captured drawing rules, presentation schema and ADR.
- `677b41b` — adjustment-safe re-arm and stale-input protection.
- `350b91a` — chart-first workstation and integrated workflows.
- `f8436f1` — chart lifecycle, cross-symbol, accessibility and regression hardening.
- `a62822c` — cumulative keyboard navigation between frames.
- `c275f2b` — context-menu keyboard focus and stale-alert recovery.

Later verification and delivery commits are recorded in the Phase B evidence index. [Concise progress record](TRANSFORMATION_PROGRESS.md).

## Workstation plan, Phase A (2026-10-19 to 2026-10-20)

Plan: [2026-10-19 workstation plan](docs/history/plans/2026-10-19-tradingview-workstation-plan.md). Rule: TradingView structure, Wickstreet skin (D23). Every capability's old and new place is in the [correspondence matrix and capability ledger](docs/current/tradingview-correspondence.md).

- **Shell (A2):** one header bar on every route (☰ app menu, search pill, route slot), a right icon strip with the panel (D24), and a status edge with the chart credit.
- **Chart (A2–A4):** the toolbar sits in the header bar. Lower-priority controls fold into ⋯ below 1280 and 1024 px. One grouped drawing rail with flyouts serves the active chart through portals (D25). It has an overlay legend, a bottom range bar and an Object tree panel tab. Grid cells keep no toolbars of their own.
- **Momentum25 (A5):** the Assessment panel shows rank, qualification, provenance and per-criterion evidence, keyed on (symbol, strategy, run). Temporary "Show on chart" layers and a legend chip. Watchlist Rank and Qualified columns with a run notice. Screener column sets and filter pills. Alerts scoped to "This symbol" or "All". Same-origin `?from=` return paths.
- **Surfaces (A6–A8):** the /chart bottom panel with an embedded screener. Restructured search and indicator dialogs. Flat sections everywhere. `/` is the Stock Screener, with a `?run=` historical mode. Symbol pages share one header and tab row. Research is one workspace. `ScreenerDetail`, `SymbolActionBar` and the section nav are retired, each field moved first.

Evidence: [`audit-evidence/tradingview-clone/`](audit-evidence/tradingview-clone/) (32 screenshots, `geometry.json`). At 1440×900: header 38 px, rail 52 px, strip 45 px, range bar 30 px. The plot is 1,031×796 px at 1440 and 378×698 px at 390 (Codex: 334×544). No document overflow at 1920, 1440, 768, 390 or 720×450.

Final serial run on a fresh synthetic `*_e2e` database: see [TRANSFORMATION_PROGRESS.md](TRANSFORMATION_PROGRESS.md). NFR-11 chart open: warm P95 166 ms, cold P95 474 ms. 16-chart grid: warm P95 1,288 ms (Codex 1,348 ms), pan P5 61 fps.

Limits: the Screener's picker lists production strategies only. The Assessment does not mark passing gates, because the API lists only failing gate rules. Data has one settings section, so it has no left nav. Markets has no symbol rows to open an Assessment from. Phase B1–B4 subsequently delivered filters and saved screens, Replay, more drawings and line alerts. B5 Volume Profile remains deferred; Phase C has not started. No pixel-level or superiority claim is made.
