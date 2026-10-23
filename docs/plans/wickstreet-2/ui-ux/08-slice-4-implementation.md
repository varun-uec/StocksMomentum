# 08 · Slice 4 implementation: the MF research workstation

**23 October 2026 · Built on branch `wickstreet/m10-m11`, local commits only.**

This report records what was built from docs 01–05 and the owner's two visual references, how it was checked, and what still waits for a service or dataset. It does not change financial methodology. Every number on screen comes from the method v5 research API.

## What ships

| Route | Screen | Built from | API reads |
|---|---|---|---|
| `/mf` | Discover: hero with the six presets, registry facts, category explorer, research ideas, watchlist, market context | D01 / M01 | `fields`, `presets`, `screener/run`, `regimes`, `risk-free`, `metrics` |
| `/mf/screen` | Screener: preset and saved screens, quick filters, a searchable browser of all 160 fields, typed condition editor, ALL/ANY, formulas, columns, sort, cursor paging, zero-match relaxations, missing-value counts, full CSV export, save | D02 / M02 / S01 | `fields`, `presets`, `screener/run` |
| `/mf/funds/:code` | Fund intelligence with six tabs: Overview, Performance, Risk, Peers & rankings, Holdings, Data & profile | D03 / M03 / S02 | 14 fund reads, `regimes`, `risk-free` |
| `/mf/studio` | Analytics studio: rolling returns, drawdowns, peer rankings, risk–return frontier, rank persistence, market regimes, selection backtest | D04 / M04 / S04 | `rolling`, `underwater`, `rank-history`, `peers/*`, `regimes`, `backtests` |
| `/mf/compare` | Compare 2–5 funds: common start, rebased growth, aligned metrics, correlation matrix, save as watchlist | D05 / M05 | `compare` |
| `/mf/simulate` | Investment lab: SIP, lump sum, SWP, STP, XIRR, tax by financial year, rolling-SIP start months, save scenario | D06 / M06 | `calculators/*`, `rolling-sip` |
| `/mf/workspace` | Watchlists, saved screens, notes, scenarios; alerts shown as planned | D08 / M08 | `workspace/records` (new) |
| `/mf/portfolio`, `/mf/ask` | Planned capabilities: what they will do, what they need, and links to the tools that answer the same questions today | D07, D09 | none |

The MF tree has its own shell (`MfShell`): a left rail on desktop, a top bar with fund search (`/` focuses it), a bottom bar and a "More" sheet on phones, and a compare tray. The stock workstation's chrome does not mount on `/mf`. Momentum25 routes are unchanged; its app menu gains one "Mutual funds" entry, and the MF rail links back to "Momentum25 · Stocks".

## Theme architecture

All colour lives in one file, `web/src/features/mf/theme/themes.ts`.

- A theme is a `Theme` object with `light` and `dark` `ColorTokens`. The roles are grouped as surfaces and ink, brand, semantic (gain, loss, warning, info, focus) and chart (five series, band, grid).
- `themeCss()` turns the active theme into `--mf-*` CSS variables on `.mf-root` (light) and `.dark .mf-root` (dark). `tailwind.config.ts` maps every role to an `mf-*` colour (`bg-mf-surface`, `text-mf-loss/70`).
- Charts read the same variables through `token()`, `seriesColor()` and `heat()`. `heat()` caps tints at 0.40 alpha, so ink text on a heatmap cell keeps AA contrast in both modes.
- Typography, radii and shadows are separate exports in the same file.
- Components name no colour. `grep` for a hex value under `features/mf` finds only the theme file.

To add a theme, add one entry to `THEMES`. It appears in Appearance settings with no component change. Two themes ship: **Paper & ink** (default, forest and sea green) and **Monsoon**, which proves the swap. Light and dark follow the app-wide setting.

## Workspace persistence (W1)

Doc 04 lists W1 as a Slice 4 dependency, so it was built: context `wickstreet.workspace` (domain, application, infrastructure, interface), table `research_record` with forced tenant row-level security (migration 0005), and routes `GET/POST /workspace/records` and `GET/PUT /workspace/records/{id}`. A `PUT` needs `If-Match` (428 without it); a stale version gets 412. Archive is a flag, so it can be undone. The tenant isolation suite covers the new table. Migration 0005 was applied to the local database on 23 October 2026; it only adds an empty table.

The UI re-applies a watchlist add or remove after a 412, because a set edit is safe to repeat. A note or a renamed record that loses a race shows the conflict and keeps the draft.

## Honesty rules the UI keeps

- A missing value shows its reason (for example "History too short"), never zero.
- The Discover and Risk market context is labelled as a NAV-built proxy, not an official index.
- The fund overview shows the score beside the 1Y loss and the current drawdown.
- The score drawer shows the three equal parts and their peer counts. Cost is not a part.
- Correlation is never called holdings overlap.
- The backtest shows in-sample and out-of-sample results in separate cards. Inputs that change after a run mark the old result.
- The lab labels a changed scenario "Previous scenario". Tax is an estimate, and its cautions appear next to it.
- Expense ratio, AUM, benchmark, holdings, alerts, portfolio and agent show as **Planned** with the named dependency. None has an active control or an invented value.

Display arithmetic is limited to rebasing a NAV series to ₹10,000 for a chart, a one-day NAV change, histogram bins and window cuts. No financial metric is computed in the browser.

## Verification

| Check | Result |
|---|---|
| `npm run lint`, `tsc --noEmit`, `npm run build` | Pass |
| Unit tests (`npm test`) | 172 pass; MF adds format, view links, percent round-trip, CSV export, series windows, theme completeness |
| MF Playwright (`npx playwright test -c playwright.mf.config.ts`) | 21 pass against the live snapshot (revision 2801). Workspace calls go to an in-memory mock, so no test writes to the real store |
| Axe WCAG 2.1 A/AA, 19 MF routes, light and dark | 0 violations |
| No page-level sideways scroll at 390, 768, 1024, 1440 px | Pass on all 10 main routes |
| Backend `pytest tests/wickstreet` | 318 pass, 12 skipped; import contracts kept; mypy clean |
| Momentum25 Playwright regression (fresh `momentum25_e2e`) | 236 pass, 8 skipped, 0 fail (19.1 min) |
| Full backend `pytest` | 1,407 pass, 12 skipped |
| Main bundle | 657.6 kB before gzip, against 655.3 kB at e653702; the over-500 kB warning predates this slice. MF code loads per route |

Journeys covered: J1 (collection → screen → fund → Back restores), J2 (fund risk with open drawdown), J3 (compare with service correlation), J4 (SIP equals the calculator API, stale result marked), J5 (studio frontier, transitions, hold-out backtest), workspace save and conflict, theme and palette swap, phone filter sheet and navigation, keyboard fund search.

## Gaps and dependencies

| Area | State | Needs |
|---|---|---|
| Metric alerts | Planned panel; nothing shown as active | W2 evaluator and event log |
| Decision briefs and original/latest replay | Not built; notes and scenarios save today | W3 snapshot diff and a brief schema |
| Revision pinning across views | The CSV export pins its revision; other reads use the latest snapshot and show its date | A shared research context (doc 01) |
| Nested filter groups | The UI edits one ALL/ANY level; nested groups from links display but cannot be edited | A group editor |
| Expense ratio, AUM, manager, riskometer, exit load | Planned | E1 with a rights grant |
| Benchmark-relative risk | Planned; proxy shown instead | E3 licensed TRI |
| Holdings, overlap, sectors | Planned | E4, E7 |
| Portfolio and CAS | Planned page | P1, P2 (Slice 6) |
| Multilingual agent | Planned page with working shortcuts | A1 (Slice 5) |
| Forward goal planner | Planned | S1 approved scenario method |
| Usability study and Tickertape comparison | Not run | People and an authenticated competitor walkthrough (doc 06) |

## Files

- Frontend: `web/src/features/mf/` (theme, api, format, queries, view-spec, workspace, series, csv, components, routes), `web/src/main.tsx`, `web/tailwind.config.ts`, one line in `web/src/components/shared/NavBar.tsx`.
- Tests: `web/src/features/mf/*.test.ts`, `web/e2e/mf/`, `web/playwright.mf.config.ts`. The main Playwright config ignores `e2e/mf`.
- Backend: `backend/src/wickstreet/workspace/`, migration `0005_research_records`, `backend/tests/wickstreet/test_mf_workspace.py`.
