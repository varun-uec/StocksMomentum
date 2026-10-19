# Wickstreet Design Record

> Kept under [ADD Amendment A1](./ADD-amendment-A1.md) §1a (Proposed). Append only: add entries, never rewrite them. A correction is a new entry that names the one it corrects.

Wickstreet is an independent implementation. TradingView and OpenChart are references for usability and capability, not sources of code. This record shows where each design idea came from, so anyone can check that independence later.

## Exposure log

Every contact with reference material, with its date and scope. It states what was seen honestly; it never claims that nothing was seen.

| # | Date | Who | Material | Scope | Frontend source read? |
|---|---|---|---|---|---|
| X1 | 2026-10-18 | Owner and Claude (assistant) | OpenChart README on GitHub | Capability list, licence summary | No |
| X2 | 2026-10-18 | Claude | OpenChart `LICENSE` file | Licence terms (logo clause, multi-tenant clause) | No |
| X3 | 2026-10-18 | Claude | openchart.co/docs/getting-started | Setup flow, data providers, alert behaviour | No |
| X4 | 2026-10-18 | Claude | TradingView Charting Library docs: keyboard shortcuts | Documented shortcut set | No |
| X5 | before 2026-10-17 | Owner | TradingView as an everyday user | Observable behaviour of tradingview.com | No |
| X6 | 2026-10-18 | Claude | TradingView Lightweight Charts™ `README` and `NOTICE` (Apache-2.0, a dependency) | Licence and attribution terms | Library code is a declared dependency, used under its licence |
| X7 | 2026-10-19 | Claude | OpenChart README; openchart.co docs index, getting-started, alerts, data-providers, select-and-explain pages | Capability claims and documented behaviour for the parity audit ([clean-room record](../../OPENCHART_CLEAN_ROOM_RECORD.md)) | No |
| X8 | 2026-10-19 | Claude | openchart.co home page and changelog; chart.chat (redirects to openchart.co) | Product claims, drawing context-menu item names, screenshot layout described in words | No. The desktop app was not installed or run. |
| X9 | 2026-10-19 | Claude | tradingview.com public chart, stock screener and symbol pages, signed out, 1440×900 | Rendered structure only: bar heights, rail and strip widths, control order and grouping. Screenshots kept outside the repo. | No. No CSS, JS or DOM was read. |

## Decisions

Each entry: the Wickstreet decision, the reference that prompted it (if any), and our own reason.

| # | Date | Decision | Reference | Our reason |
|---|---|---|---|---|
| D1 | 2026-10-18 | Typing on the chart, `/` or `Ctrl/⌘+K` opens symbol search | X4, X5 (typing changes symbol; `Ctrl+K`) | Users with TradingView habits expect it. Search is the first step of every workflow. |
| D2 | 2026-10-18 | Drawings belong to the symbol, not to one chart | X5 | One analysis per symbol is visible at every range and on every chart that shows the symbol. ADR-013 §5. |
| D3 | 2026-10-18 | Click selects a drawing; drag moves it; Delete removes it; Esc cancels | X4, X5 | Standard direct manipulation. Without it, drawings cannot be corrected. |
| D4 | 2026-10-18 | Autosave with a visible "Saved ✓ hh:mm" state, no Save button in M11 | Own | A self-hosted app has no account flow to save into. Visible state builds trust. |
| D5 | 2026-10-18 | A conflict notice, never a silent overwrite | Own | ADR-013 §5. Two windows on one instance are a normal case. |
| D6 | 2026-10-18 | Chart in the centre, drawing tools on the left, details on the right | Common terminal convention (X5) | Layout convention shared by most charting tools; Wickstreet uses its own visual style |
| D7 | 2026-10-18 | *(Superseded by D9.)* `/` opens search in M11, and moves to the indicator dialog in M13 | X4 (`/` opens indicators) | M11 has no indicator dialog. The move keeps TradingView habits once the dialog exists. |
| D8 | 2026-10-18 | No scripting language and no AI agents | X1 (OpenChart offers both) | A1 §4. Momentum25's configurable, explained rules are the differentiator. |
| D9 | 2026-10-18 | `/` stays symbol search in every milestone. Supersedes D7. M13 gives the indicator dialog its own shortcut. | X4 (`/` opens indicators) | Owner decision at the M11 review. Search is the first step of every workflow, and one key should keep one meaning. |
| D10 | 2026-10-19 | A range preset (1W … 1Y) is a slice of the stored bars, counted back from the last bar, not from today | Own (parity audit defect D1) | Stored data can lag the calendar; a range must never show an empty chart while bars exist. |
| D11 | 2026-10-19 | Moving averages use the stored closes before the range as warm-up | Own (D2) | An MA200 that starts 200 bars into the chart misleads. |
| D12 | 2026-10-19 | The crosshair readout sits at the top left of the chart | Own (D4) | The right edge holds the price-axis labels. |
| D13 | 2026-10-19 | A grid cell opened by a layout keeps its own symbol, starting from the active chart's | Own (D8) | With symbol sync off, one search must change one chart. |
| D14 | 2026-10-19 | A click within the handle radius of the last anchor does not place a new anchor | Own (D6) | A double-click must not save a zero-length drawing. |
| D15 | 2026-10-19 | Enter in indicator search adds the first match that can be added | Own (D10) | Matches Wickstreet's symbol search, so one key keeps one meaning across dialogs. |
| D16 | 2026-10-19 | An edit made while a saved document loads is kept and merged onto the loaded version | Own (parity audit defect D11) | ADR-013 §5: never lose or silently overwrite the owner's work. |
| D17 | 2026-10-19 | Workstation surfaces use ink, paper and sea-green accents, fine separators, compact labelled controls, a quiet study strip and contextual inspectors | Own; owner transformation brief and audit findings only | Analytical hierarchy follows symbol → chart → evidence; whitespace belongs to the plot. Both themes use the same geometry. |
| D18 | 2026-10-19 | Workspace presets set the initial visible window over all stored bars; research windows remain explicit | Own (BL-01) | Panning must reveal earlier history without fetching or losing warm-up. Compare anchors are explicit and remain stable during panning. |
| D19 | 2026-10-19 | Indicator instances retain colour and visibility; a chart legend opens the shared study inspector | Own (BL-03/04/11) | Identify every plotted study at its point of use; keep display studies separate from authoritative backend studies. |
| D20 | 2026-10-19 | Grid cells keep stable chart instances when activation changes, with drawing tools for the active cell only | Own (BL-02/14) | Selecting a panel should not rebuild its chart; dense layouts share controls instead of repeating a dashboard. |
| D21 | 2026-10-19 | Drawing object management provides lock, visibility, dash, undo, restore and an inline note editor | Own (BL-05/08) | Everyday annotations need reversible editing and precision, while retaining traded-price anchors and conflict-safe persistence. |
| D22 | 2026-10-19 | A single-chart plot measures its responsive toolbar/header geometry and reserves bottom-navigation space; keyboard repeats accumulate before paint | Own; transformation browser journey evidence | Enlarged touch controls must not cover the plot. Rapid analytical navigation must not discard inputs between frames. |
| D23 | 2026-10-19 | TradingView structure, Wickstreet skin. Screen layout, control placement, grouping, density and interaction follow TradingView: one-row top toolbar, grouped left drawing rail, right icon strip with a panel, bottom range bar, overlay legend. Colours, tokens (`--ws-*`, sea-green accent), Inter and series colours stay Wickstreet's in both themes. One design language on every route. | X5, X9 | A TradingView user finds each control where they expect it. The look stays ours, so the product is not a copy. Plan: `docs/history/plans/2026-10-19-tradingview-workstation-plan.md`. |
| D24 | 2026-10-19 | The right panel moves into the workstation shell with a 45 px icon strip on every route. /chart keeps the panel state saved with the workspace and shows the panel inline at 1280 px and wider; dense layouts (9+ charts), laptops and every other route open it as an overlay that starts closed on each visit. Clicking the open tab collapses the panel. Details shows only when the route has a context symbol; Alerts lists only when it has none. | X5, X9 | The panel follows the user's task on every route without reflowing pages that were not built around it. |
