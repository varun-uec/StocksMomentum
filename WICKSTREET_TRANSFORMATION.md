# Wickstreet product transformation

Local implementation, 2026-10-19. No push or publication. Financial scoring, screening, immutable research results, EOD data architecture, traded-price drawing anchors and conflict-safe document persistence remain intact.

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

Final production-build results and performance measurements are recorded after the serial validation run. Commands use dedicated `*_e2e` PostgreSQL databases and a disposable Redis service, with scheduler and direct exchange downloads disabled. Existing production database records were not changed.

Backend: 874 tests, strict mypy on 263 files, Ruff and layer-import contracts passed. Web: 110 unit tests, zero-warning ESLint and TypeScript passed. Browser results are pending final serial verification.

Automated axe checks cover dashboard, chart and Studio in both themes. Keyboard, native modal focus, reduced motion, 200% equivalent reflow, touch drawing/panels and viewport overflow have explicit regression coverage. Native zoom was manually inspected. This is not a complete screen-reader or WCAG-conformance certification.

## Intentional limits

- Daily completed-bar alert evaluation, not continuous intraday monitoring. No external delivery.
- Drawing alerts snapshot a saved horizontal line or the rectangle's inclusive **price band**; the rectangle's date extent does not terminate the future condition. Close-to-close entries/exits are deterministic; no assumption about intraday paths or gaps through an entire band. Edits refresh a snapshot only explicitly. Sloped/path alerts remain excluded.
- Configurable display studies never feed screening, ranking or alerts. Price studies are hidden on percentage axes; comparisons remain available.
- Volume Profile, extra advanced drawing types, scripting, AI agents, brokerage execution, intraday feeds and hosted tenancy were not introduced. Named workspaces/resizable docking remain optional follow-up capabilities; the existing default workspace and independent chart settings persist.
- Touch drawing uses the established date/price anchors; dense desktop grids remain a desktop workflow. Production-scale data/performance will vary from synthetic fixtures.

## Local commits

- `f76ada7` — armed-alert editing, captured drawing rules, presentation schema and ADR.
- `677b41b` — adjustment-safe re-arm and stale-input protection.
- `350b91a` — chart-first workstation and integrated workflows.
- `f8436f1` — chart lifecycle, cross-symbol, accessibility and regression hardening.
- `a62822c` — cumulative keyboard navigation between frames.
- `c275f2b` — context-menu keyboard focus and stale-alert recovery.

Final verification/evidence commit and repository state follow validation. [Concise progress record](TRANSFORMATION_PROGRESS.md).
