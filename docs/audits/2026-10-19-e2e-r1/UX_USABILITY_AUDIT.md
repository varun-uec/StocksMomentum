# Wickstreet UX and Visual Usability Audit

**Audit date:** 2026-10-19 · **Initial audit revision:** `e7fd455`; see the focused release-hardening update below.

Screens were rendered by Chromium at 1440×1000, 1280×720 (benchmarks) and 390×844, then visually inspected. Screenshots are evidence, not substitutes for inspection. See the [evidence index](../../../audit-evidence/README.md).

## Overall assessment

The desktop chart feels familiar to someone who has used TradingView: symbol and interval controls sit above a central chart, drawings are in a left rail, the legend follows the crosshair, indicators have a dedicated dialog, and the workspace supports saved drawings and synchronized multi-chart layouts. The find → analyse → draw → restore workflow is understandable without assistance once the chart route is open.

The full TradingView mental model is not reproduced: Wickstreet uses `Ctrl/⌘+K` and printable-key search, `/` is not indicator search, there is no scripting or real-time feed, and some chart toolbar shortcuts are Wickstreet-specific. The comparison was made against public documentation and observable product states only. No proprietary frontend source or assets were inspected or copied. The prior [M9 reference study](../../plans/shipped/2026-10-18-m9-reference-study.md) records the clean-room sources, including the [TradingView shortcut docs](https://www.tradingview.com/charting-library-docs/latest/getting_started/Shortcuts) and [OpenChart public README](https://github.com/longsurf-ai/openchart).

## Visual inspection findings

| Screen/state | Observed result | Usability consequence | Status |
|---|---|---|---|
| Dashboard, desktop | Ranked table and explanation panel establish a clear hierarchy. A wide table has more columns than the available viewport. | Some columns require horizontal scroll; without a cue, users may miss them. | Fixed in audit: a visible horizontal-scroll hint was added. [Screenshot](../../../audit-evidence/screenshots/dashboard-desktop.png) |
| Dashboard, mobile 390×844 | Page remains usable and primary nav is available; the stock table is wider than the viewport. | Horizontal swipe is needed to read all columns. | Hint added; horizontal layout remains by design. [Screenshot](../../../audit-evidence/screenshots/dashboard-mobile.png) |
| Chart, desktop | Dense but consistent controls, visible drawing rail, controls and save state; chart receives the dominant area. | Experienced chart users can find common actions; small labels and numerous controls reward familiarity. | No blocking defect observed. [Screenshot](../../../audit-evidence/screenshots/chart-desktop.png) |
| Chart search | Centered search dialog gives a clear entry point and result list. Fast keyboard input originally raced focus/close timing. | Lost first characters or an unexpectedly closed dialog could make search feel unreliable. | Fixed focus and redundant close handler; 20 fast repetitions passed. [Screenshot](../../../audit-evidence/screenshots/chart-search-desktop.png) |
| Indicators | Centered dialog with visible catalogue and separate pane/overlay choices. | Familiar enough for common studies; the catalog is less search-oriented than TradingView’s `/` flow. | No clipping observed. [Screenshot](../../../audit-evidence/screenshots/chart-indicators-desktop.png) |
| Chart, mobile initial viewport | Toolbar wraps to several rows and the chart loses vertical height; content still scrolls. | Chart analysis starts below a large control stack and needs more scrolling than desktop. | Open P2 visual refinement. [Viewport](../../../audit-evidence/screenshots/chart-mobile-viewport.png) |
| Chart, mobile bottom | Fixed bottom navigation initially competed with lower chart status/footer content. After scrolling, the status now clears the nav. | Could have hidden useful status text. | Fixed with safe-area-aware trailing space; browser bounds assertion passes. [Screenshot](../../../audit-evidence/screenshots/chart-mobile-bottom-content.png) |
| Studio, desktop | Family creation and help text render cleanly, but the empty state leaves substantial whitespace. | The create-family next step is visible; a long blank area can make the page feel unfinished. | Open P2 polish. [Screenshot](../../../audit-evidence/screenshots/studio-desktop.png) |
| Studio, mobile | Family area is reachable after choosing a family; create form and selected details remain usable by scrolling. | Longer than desktop and not a one-screen form. | Previously adjusted to scroll to the selected family. [Viewport](../../../audit-evidence/screenshots/studio-mobile-viewport.png) |
| Market API unavailable | Error message is centered, legible and actionable enough to establish that data is unavailable. Large surrounding blank space remains. | Failure state is not mistaken for a blank chart. | Pass. [Screenshot](../../../audit-evidence/screenshots/market-api-unavailable.png) |
| Data, desktop | The default state clearly says exchange downloads are disabled, shows the authorized import commands and uses a visible code block. Visual review found the original snippet omitted loading `.env`, which could point CLI imports at the default database. | A customized Compose database might not be the target of the import commands. | Fixed: the instructions now export `../.env` before running the import commands; the updated state is captured and browser-checked. [Screenshot](../../../audit-evidence/screenshots/data-authorized-import-desktop.png) |
| Dark dashboard | Contrast and surface hierarchy remain coherent in dark mode. | No major theme-specific issue observed. | Pass. [Screenshot](../../../audit-evidence/screenshots/dashboard-dark-desktop.png) |
| Mobile More menu | Advanced Momentum25/research routes are available under a labeled More menu. | The route inventory is preserved, although a new user may not realize how many legacy screens exist. | Pass with discoverability cost. [Screenshot](../../../audit-evidence/screenshots/mobile-more-menu.png) |
| 4×4 chart grid | All 16 charts mount within the page; at 1280×720 each cell is necessarily compact. | Useful for scanning, not comfortable for detailed interaction on small displays. | Functional; dense layout is expected. [Screenshot](../../../audit-evidence/screenshots/chart-grid-16-desktop.png) |

## Interaction consistency and accessibility observations

- Search, range selection, chart types, indicators, alerts and panel tabs have explicit labels/roles used by the browser checks. Dialogs close through Escape; search returns focus appropriately after the audit fix.
- Drawing selection and manipulation use pointer actions; delete/undo/redo and arrow movement are keyboard-capable. Layout and shortcut help are reachable; `?`, `Alt+W`, drawing shortcuts and the indicator shortcut were checked.
- Crosshair synchronization and chart focus are visually legible on desktop. Multi-chart keyboard navigation was not exhaustively assessed with screen readers or a complete keyboard-only task script.
- Dark and light dashboard states were inspected. A page-by-page contrast-ratio audit, screen-reader audit, reduced-motion audit and touch-accessibility audit were not performed.
- There is no login or user profile boundary. This is consistent with private loopback deployment, not appropriate for an exposed multi-user service.

## Focused release-hardening update — 2026-10-19

The Data page now starts with an offline authorized-data path. Its rendered desktop state was captured and inspected after adding the `.env` loading lines to the CLI snippet. Direct refresh controls appear only when the operator explicitly enables downloads; this control does not grant source permission. See [release-hardening evidence](../../../audit-evidence/benchmarks/release-hardening.md).

## Reference usability comparison

The comparison evaluates observable conventions and documentation; it does not claim feature parity or test every reference product path.

| Task / convention | Wickstreet | TradingView (public docs/observable conventions) | OpenChart (public docs/README) |
|---|---|---|---|
| Find a symbol quickly | Type on chart or `Ctrl/⌘+K`; direct `/chart/:symbol` links work | Keyboard quick search and typing workflow documented | Public getting-started docs describe instrument search |
| Chart structure | Central chart, left tool rail, top controls and optional right workspace panel | Familiar chart-first workspace and keyboard shortcuts | Public capability list includes charts and multi-chart workspace |
| Draw and restore | 12 drawing types; server-backed per-symbol state, reload and second-browser restore | Rich drawings/workspaces are a mature core workflow | Public README lists drawings |
| Multi-chart | 1/2/4/9/16, with symbol/interval/crosshair sync | Layout and sync conventions are documented | README describes up to 4×4 |
| Momentum research | Explainable Top-25, rule breakdown, patterns, Elliott Wave and legacy research routes | Not the same product concept | Not evidenced as a public README capability |
| First-use discoverability | Main chart/screener are clear; research screens are under More; several advanced terms remain domain-specific | Mature, familiar conventions help experienced users | Public product onboarding/docs are separate from the Wickstreet UI |

**Can an experienced TradingView user complete core workflows without help?** Yes for symbol search, chart settings, basic indicators, common drawing interactions, saved state and multi-chart scanning. They may need to inspect shortcut help for Wickstreet-specific key mappings and to find advanced Momentum25 research under More. This is an informed assessment of the tested flows, not a user study.

## Prioritized UX actions

1. **P2 — Improve small-screen chart density.** Consider collapsing secondary controls into a labeled overflow or horizontally scrollable toolbar while preserving chart height. No behavior change was made because a responsive redesign would exceed the straightforward defect fix.
2. **P2 — Reduce Studio empty-state whitespace.** Keep the family create action and explain next step closer to the viewport's first focal area.
3. **P2 — Improve advanced-route discoverability.** More preserves screens but offers limited preview of the Momentum25 analysis/research taxonomy. Add small descriptive labels or a grouped navigation panel after owner review.
4. **P3 — Accessibility completion.** Add audited screen-reader, contrast, reduced-motion, and touch-only passes before claiming WCAG conformance; no conformance claim is made here.

## Evidence

All screenshot artifacts are under [`audit-evidence/screenshots`](../../../audit-evidence/screenshots/). Browser traces for the restore and slow-response states are under [`audit-evidence/traces`](../../../audit-evidence/traces/). The route/state results are listed in the [coverage matrix](E2E_COVERAGE_MATRIX.md).
