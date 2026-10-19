# Wickstreet UX, Visual, and Accessibility Audit — Round 2

**Date:** 2026-10-19 · **Browser:** Chromium 153.0.8010.12 · **Viewports:** 1440×900, 1920×1080, 768×1024, 390×844 · **Themes:** light and dark.

## Overall assessment

The chart workspace remains recognizable to a TradingView-familiar user: symbol and interval controls sit above the chart, drawing tools are grouped in a rail, studies are available in a dialog, the crosshair has a readout, and chart layouts can sync symbols, intervals, and crosshair positions. A first-time user can finish symbol search, core drawing, and saved chart workflows in the tested paths. They still need to discover Wickstreet-specific shortcuts and use **More** to reach several Momentum25 research screens. This is a workflow assessment from browser exercises, not a moderated user study.

Round 2 rendered every one of the 26 named routes in both themes at four requested sizes (208 states). Measurements show no root horizontal page overflow after the tablet fix. Forty-six screenshots cover selected route and state combinations; a focused subset cannot prove that every tooltip, dialog, chart, error, and long-label arrangement looks correct at every size.

## Visual findings

| Surface/state | Round 2 observation | Disposition |
|---|---|---|
| 768 px tablet navigation | Initial layout used desktop navigation and forced 1120 px document width across routes. | **Fixed P1.** Mobile/tablet nav breakpoint moved to `lg`; verified across all route/theme states. |
| 390 px mobile navigation | Mobile More menu is keyboard-operable and focus returns to trigger on Escape. | Pass for tested menu. Core chart toolbar still occupies several rows and reduces chart height; an interaction/touch density refinement remains useful. |
| 1440/1920 desktop | Chart and dashboard fit the viewport width; chart remains dense but readable. 1920 provides more whitespace than the 1440 layout. | Pass for sampled route states; no full visual baseline comparison by pixel. |
| Strategy Studio long labels | Long family/version labels could force wide buttons and labels were not correctly associated with comparison selects. | **Fixed P2.** Text wraps/breaks and controls have explicit label associations. |
| Strategy Studio empty family state | Still leaves substantial empty space around the create-family action. | Open polish issue; no workflow failure. |
| 4×4 chart grid | All 16 charts fit; controls and plotting area are necessarily compact at smaller sizes. Diagnostic route now scrolls internally rather than expanding the page. | Functional; detailed use on mobile is not recommended. |
| Dashboard/table | Existing horizontal-scroll cue remains; route widths no longer expand the entire tablet/mobile page. | Pass for the sampled states; table content still requires horizontal exploration on narrow screens. |
| Light/dark theme | Both were applied to every route in the viewport sweep. | No root clipping observed. No ratio-based contrast measurement was completed. |
| Network save failure | Drawing style edit displayed “Not saved”, preserved last persisted color, and exposed Retry; screenshot and trace retained. | Pass; retry restored Saved state. |
| Unknown API route/method | Errors remained JSON rather than SPA HTML. | Pass; error state is actionable at HTTP layer. |

## Interaction and accessibility

- Tested keyboard use of More: focus trigger, Enter, dialog focus, Tab to first route, Escape, and focus restoration.
- Tested reduced-motion preference. The initial browser check found smooth scrolling still enabled; the new CSS override now reports `scrollBehavior: auto` and near-zero transition duration.
- Tested selected chart keyboard behavior in drawing workflows: Escape closes the context menu, focus returns to chart, Shift+F10 opens context menu, arrow keys move selected drawing, and Control+Z/Control+Shift+Z undo/redo.
- Comparison selects now expose their visible labels to accessibility queries.
- At a 720×450 viewport representing a 1440×900 desktop at 200% zoom, dashboard, chart, and Studio remained within document width. This is a viewport-equivalent test; the browser's actual zoom setting was not changed.

Not completed: screen-reader reading order/announcements, actual 200% browser zoom, measured WCAG contrast ratios, high-contrast mode, full keyboard-only workflows on every route, touch-only drawing, all tooltip/dropdown/dialog combinations across themes and dimensions, and reduced-motion checks on every animation. No WCAG conformance claim is made.

## TradingView-familiarity review

Core chart conventions are discoverable for the experienced-user persona: symbol search, interval/range controls, types/scales, indicator dialog, drawing rail, context menu, multi-chart grid and crosshair synchronization. Differences that need clear in-product help include Wickstreet’s keyboard bindings, the separate **More** area for Momentum25 analysis/research, lack of real-time feed, and limited scripting/custom indicators. The audit did not copy proprietary code or branded assets. It did not assert parity with TradingView.

## Prioritized follow-up

1. **P2:** Run screen-reader and contrast audits before any accessibility conformance claim.
2. **P2:** Reduce mobile chart toolbar height while preserving explicit names and reachable controls.
3. **P2:** Improve Studio’s empty state and expose short descriptions for advanced Momentum25 routes under More.
4. **P3:** Analyze bundle split opportunities; main web JS remains 565.81 kB raw despite NFR-11 passing.

Evidence: [`viewport-audit.json`](audit-evidence/r2/viewport-audit.json), `viewport-*.png`, `zoom-equivalent-chart-720x450.png`, `drawing-save-failed.png`, `studio-reopened-version-comparison.png`, and the trace index in [`audit-evidence/r2/README.md`](audit-evidence/r2/README.md). Round 1 visual details remain in [`UX_USABILITY_AUDIT.md`](UX_USABILITY_AUDIT.md).
