# UX Validation Report — Round 3

Date: 2026-10-20. Branch `wickstreet/m10-m11`. Scope: every route, at desktop (1440), tablet (768) and phone (390), in light and dark themes, on the real application (read-only) and on synthetic fixtures (writes).

## Method

| Surface | What ran | Data |
|---|---|---|
| Real app, `localhost:8000` | Chromium via Playwright MCP. All non-GET API calls blocked by a route handler. | Real database, run #149, data through 2026-10-19 |
| Fixture app, isolated `*_e2e` databases | Full serial Playwright suite (232 tests), axe-core 4 sweep, 48 screenshots | Marked synthetic fixtures |
| Accessibility | axe-core with tags `wcag2a, wcag2aa, wcag21a, wcag21aa` (+ `best-practice` on the real app) | 25 routes × 2 themes |
| Not done | A real screen reader (VoiceOver, NVDA). Firefox and Safari. A moderated usability test with people. | — |

Screenshots: `audit-evidence/audit-r3/ui/screens/` (48 files: 12 screens × light 1440, dark 1440, light 768, dark 390), plus `real-home-1440.png`, `real-chart-reliance-1600.png`, `real-429-backtest.png`, `e2e-assessment-tcs.png`.

## Result by screen

PASS means: renders with content, no document-level horizontal overflow, no axe WCAG 2.x A/AA violation after the Round 3 fixes, empty/stale state is readable.

| # | Screen (route) | Desktop | Tablet | Phone | Light | Dark | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Screener `/` | PASS | PASS | PASS | PASS | PASS | Stale-data banner shows "49 trading sessions behind" on the fixture. Table scrolls inside its own region on phone. |
| 2 | Chart workspace `/chart/:symbol` | PASS | PASS | PASS | PASS | PASS | Phone moves the drawing rail and range bar into overflow controls. Data-source text truncates ("261…") on phone; Round 7: a tap opens it (R3-U-13). |
| 3 | Stock `/stock/:symbol` | PASS | PASS | PASS | PASS | PASS | |
| 4 | Analysis `/stock/:symbol/analysis` | PASS | PASS | PASS | PASS | PASS | |
| 5 | Elliott Wave | PASS | PASS | PASS | PASS | PASS | Fixed: scrollable region is keyboard-focusable (axe `scrollable-region-focusable`) was seen on phone for `/strategies` and `/data` before; see R3-U-12. |
| 6 | Watchlist | PASS | PASS | PASS | PASS | PASS | |
| 7 | Market | PASS | PASS | PASS | PASS | PASS | Sector panel empty by design (no sector data). |
| 8 | Strategies | PASS | PASS | PASS | PASS | PASS | |
| 9 | Strategy Studio | PASS | PASS | PASS | PASS | PASS | |
| 10 | Validation | PASS | PASS | PASS | PASS | PASS | Strategy picker offers one hard-coded strategy (R3-U-07). |
| 11 | Backtest / Historical / Experiment / Analytics | PASS | PASS | PASS | PASS | PASS | Labels fixed (R3-U-02). |
| 12 | Data | PASS | PASS | PASS | PASS | PASS | |
| 13 | Learn hub and 6 guides | PASS | PASS | PASS | PASS | PASS | |
| 14 | About, not-found | PASS | PASS | PASS | PASS | PASS | |
| 15 | `/lab/chart-grid` (unlisted engineering route) | PASS | — | — | PASS | — | No `h1`; not in navigation. |

Overflow check: 150 real-app states (25 routes × 3 sizes × 2 themes) and 48 fixture screenshots. Zero root-level horizontal overflow. The R2 sweep (208 states) passed again inside the full suite.

## Accessibility findings

axe-core on the real app before the fixes: 70 of 150 route states had a violation. Many came from the API rate limit (HTTP 429) during my fast sweep, not from the pages. The page-level defects were:

| ID | Severity | Finding | Status |
|---|---|---|---|
| R3-U-02 | P2 | `select` and `input[type=date]` with no accessible name on `/validation`, `/historical`, `/experiment`, `/stock/:s/analysis` (axe critical; WCAG 1.3.1, 4.1.2). | Fixed, verified by `r3-axe-routes.spec.ts` |
| R3-U-03 | P2 | No `main` landmark on 14 of 25 routes; duplicate banner on stock pages. | Fixed. Shell renders the one `main`. Verified. |
| R3-U-04 | P2 | Text contrast below 4.5:1. Light: emerald-600 3.76, amber-600 3.18, slate-400 2.53, emerald-400 1.92. Dark: slate-500 3.05, slate-600 2.17. 84 nodes on the home screen alone. | Fixed, verified in both themes |
| R3-U-05 | P3 | 25 screener buttons "Checklist for SBC" showing "8/8" (WCAG 2.5.3 label in name). | Fixed ("8/8 checks passed for SBC") |
| R3-U-12 | P3 | `scrollable-region-focusable` on `/strategies` (runs table), `/data` (command block) and the Elliott Wave list. | Fixed `fa5d000`. The regions take keyboard focus and have names. `r3-axe-routes.spec.ts` checks it at 390 and 1440 px. |

Regression guard: `web/e2e/r3-axe-routes.spec.ts` — 23 routes × 2 themes, zero WCAG 2.x A/AA violations, exactly one `main` landmark each. It passes.

R2 limit R2-LIMIT-03 (accessibility evidence gap) is **partly closed**: automated contrast and semantics now pass on every route in both themes. Screen-reader flows remain **NOT VERIFIED**.

## Interaction and state findings

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| R3-U-10 | P2 | A stored strategy the workspace no longer offers left the chart Assessment on "loading run…" and caused 404s on `runs/latest`, `watchlist/detail`, `indicators/series`. Only the Screener page reset it. | `integrated-workflows` journey 4 (failed, then fixed) | Fixed in `StrategyProvider`, commit `db6cfc3` |
| R3-U-06 | P3 | Expected-empty GETs (`/screens/default`, `/drawings/{symbol}`) answered 404, so every first page load logged a console error. | Real-app console log | Fixed `333f80c` + `57a37b4`: 200 at revision 0 with a null body. The E2E fixture no longer allows a 404 on these reads. |
| R3-U-08 | P3 | The API capped each client at 200 requests a minute. A page load makes 7 to 15 requests, so about 13 fast navigations a minute returned 429 and pages degraded without a message. | Real-app sweep | Fixed `1cd25eb` (1,200 a minute, `Retry-After`, problem body) and `51645b7` (the client retries a read twice, with unit tests). |
| R3-U-11 | P3 | "Δ Rank" drew a green ↓ for an improved rank (rank 144 → 1 read "↓ 143"). The two arrow icons were swapped. | Real screener, SBC | Fixed `c6a65cd`: improvement points up, with a title ("Rank improved by 143 places since the previous run"). The screener API uses `rank − previous` and the watchlist API `previous − rank`; the UI shows each correctly (accepted limitation). |
| R3-U-07 | P2 | `/validation` offered one hard-coded strategy. Saved user strategies could not be validated there. | `validation/page.tsx` | Fixed `4c8962a` + `57a37b4`. One option per workspace strategy version. The page sends `config_hash` and names strategy, version, config hash and window above the evidence. The version with no run reads as an empty report and never borrows another version's evidence. Spec: `strategy-integration.spec.ts`. |
| R3-U-13 | P3 | Phone chart cuts the data-source line ("261…"). | `chart-dark-390.png` | Fixed in Round 7: a tap on `ⓘ 2…` opens the full line; `r3-axe-routes.spec.ts` |

## Visual and information-architecture assessment

- **TradingView-familiar layout.** Left drawing rail, top symbol/interval/type/indicator/alert/replay bar, right watchlist/assessment/alerts panel, bottom range bar and screener dock. All present at 1440 and 1600 px. At 768 and 390 px the rail and panel collapse into controls and a bottom navigation. Verified in screenshots.
- **Paper-and-ink, sea-green identity.** Brand token `#278c76`; light and dark themes share the palette. Consistent across the 12 screens captured.
- **Chart-space efficiency.** At 1600×1000 the price pane plus two sub-panes (RSI, MACD) fit with legend and crosshair readout and no collisions (`real-chart-reliance-1600.png`).
- **Contextual Momentum25.** The chart legend carries a rank chip ("Not qualified"), the watchlist names its run and config hash, and the Assessment panel states strategy, run, config hash, as-of date and data version.
- **Empty, loading, error and success states.** Stale-data banner, "no run" selector suffix, "Not ranked / Gate failed" Assessment, "Not saved. Retry" save state (seen on the real app while writes were blocked). All readable.

## Not verified

- Real screen reader behaviour, focus order beyond the keyboard tests in `final-accessibility` and `r2-accessibility`.
- Safari and Firefox.
- Print styles, high-contrast mode (`forced-colors`).
- Usability with real users. M11's owner usability assessment is a separate record.
