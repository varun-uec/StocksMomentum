# Full UI/UX Audit, Improvement and Enhancement Pass — Momentum25 India (`web/`)

## Context

Momentum25 India has been built feature-by-feature over many increments. The web app now spans 13+ routes: a momentum dashboard, a watchlist, three separate single-stock surfaces, six research tools and a seven-page learn hub. Each was added when it was needed, and each was reasonable on its own.

The concern is what that leaves behind in aggregate. Three things prompted this pass:

1. **A newer unified analysis screen** (`/stock/[symbol]/analysis`) was built separately from the older stock-detail page, then verified and had its indicator drift issues fixed. It now overlaps the detail page substantially — and duplicates several of its sections as copy-pasted JSX.
2. **Elliott Wave and pattern detection** were partially folded into that analysis screen, but their standalone screens still exist. Two surfaces now show the same wave data at different depths.
3. **Nobody has evaluated the product as one product.** Every screen was judged against its own feature request, never against its siblings.

The intended outcome: a coherent, professional research tool with no visible seams from incremental development — verified against the running app with real data, not read off the source. Improvements get implemented, not just listed.

**Presentation layer only.** No backend, scoring, ranking, or data changes.

**One judgment call is explicitly reserved for the user**: whether the analysis screen is ready to be promoted as the default single-stock experience. This pass produces a recommendation with evidence. It does not execute the promotion.

---

## What exploration already established

Confirmed from source before planning — no need to re-derive during execution.

**Stack.** Next.js 14 App Router, TypeScript, React 18, Tailwind (dark mode via `class`). Charts: `lightweight-charts` + `recharts`. Data: `@tanstack/react-query` through one typed client, `web/src/lib/api-client.ts`. No component library — everything is hand-rolled.

**Shared kit is real and already good.** `web/src/components/shared/Card.tsx` exports `Card`, `MetricCard`, `Badge`, `StatusDot`, `LoadingSpinner`, `ErrorMessage`, `EmptyState`, `PageHeader`. Design tokens live in `web/src/lib/theme.ts` (`focusRing`, `typography`, `chartPalette`). Pages import from these consistently rather than re-rolling cards per screen. **This means the audit is polish work, not a design-system rebuild.**

**Layout chain.** `web/src/app/layout.tsx` → `ThemeProvider` → `Providers` (react-query) → `StrategyProvider` → `NavBar` → page.

**Routes.** `/`, `/watchlist`, `/stock/[symbol]`, `/stock/[symbol]/analysis`, `/stock/[symbol]/elliott-wave`, `/historical`, `/strategies`, `/experiment`, `/validation`, `/analytics`, `/market`, `/learn` (+6 sub-pages).

**Nav/IA.** `web/src/components/shared/NavBar.tsx` is the single source of IA: Dashboard + Watchlist top-level, everything else behind a "Research Tools" dropdown, with a code comment explaining the rationale. It also holds `SymbolSearch`, `ThemeToggle`, and the mobile hamburger. **This nav is already well-reasoned — treat restructuring it as report-only.**

**Backend.** `NEXT_PUBLIC_API_BASE`, default `http://localhost:8000/api/v1`. Must be running before any loading/error state can be judged.

### Confirmed defects (found in source, to be verified live then fixed)

| # | Finding | Location |
|---|---|---|
| D1 | Analysis page has **no top-level loading or error guard**. Its two core queries (`live`, `runExplanation`) failing or pending leaves `explanation === null`, and every section is gated on `explanation && (...)` — so the page silently renders a chart above a void. No spinner, no error, no empty copy. `LoadingSpinner`/`ErrorMessage` are already imported and unused for this. | `analysis/page.tsx:24-25, 166-177, 862+` |
| D2 | Elliott-wave standalone page guards **only** its "Top-ranked count" card. The Waves and Ranking cards render blank during load or failure with no messaging. | `elliott-wave/page.tsx` (~268-270) |
| D3 | **The analysis page is nearly undiscoverable.** Exactly one link points to it in the entire app: a small text link in the detail page header reading *"Try the new analysis view →"*. It is not in nav, not in `SymbolActionBar`, not reachable from dashboard rows, watchlist rows, or symbol search. Its label also frames the flagship screen as a beta experiment. | `stock/[symbol]/page.tsx:275-280` (sole reference, confirmed by grep) |
| D4 | **`SymbolActionBar` contradicts itself on the analysis page.** It is rendered there with `current="chart"`, but its "Chart" and "Patterns" actions link to *detail page* anchors (`/stock/SYM#chart`, `#patterns`). So on a page that has its own Patterns mode, the action bar's Patterns button navigates away to a different page. It also has no "Analysis" action at all. | `SymbolActionBar.tsx:26-30` |
| D5 | Overview, Engine Contributions and Live-analysis blocks are **copy-pasted JSX** between the detail and analysis pages — same markup, same components (`MomentumOverview`, `MomentumView`, `TechnicalWorkbench`, `VolumeAccumulation`, `SuggestedStop`, `RelativeStrengthVsIndex`). The analysis page's own comment admits it: *"Everything below the chart is lifted from the detail page as-is."* Drift risk. | `analysis/page.tsx:860-941` vs `stock/[symbol]/page.tsx:296+` |
| — | Watchlist states: **already fully handled, no change needed.** `WatchlistTable.tsx` (lines 143/156/157/162) covers loading, error and empty. Verify visually, then leave alone. | `WatchlistTable.tsx` |

D3 and D4 together are the clearest evidence of the seam the user suspects: a screen was built, but the product around it was never rewired to know it exists.

---

## Phase 0 — Pre-flight

1. Start backend: `make api-dev` (or `docker compose up`). **`curl` the base URL to confirm it is live before judging any state as broken** — a down backend makes correct error handling look like a bug and vice versa.
2. Start frontend: `make web-dev` (or `cd web && npm run dev`).
3. Pick **one real, currently-ranked symbol** from the live dashboard and use it across all three single-stock routes, so the surfaces are directly comparable.
4. Also pick **one symbol that did *not* qualify** in the latest run — the detail page has a `usingLiveFallback` amber banner path (`page.tsx:286-292`) that only appears for these, and the analysis page's handling of the same case is unverified.
5. Baseline: `cd web && npx tsc --noEmit` and `npm run lint`, so any error at the end is known to be mine.

---

## Phase 1 — Click-through audit

Playwright MCP: `browser_navigate`, `browser_snapshot` (primary — structured and cheap), `browser_take_screenshot` (only where visual judgment is needed), `browser_resize`, `browser_console_messages` (**after every navigation**, not only when something looks wrong), `browser_network_requests` (for anything that looked stuck).

### Desktop pass — full coverage, in this order

| # | Route | Exercise |
|---|---|---|
| 1 | `/` | Every strategy in the selector, run-selector history, "Refresh" screening trigger, row → detail navigation |
| 2 | `/watchlist` | With a symbol starred; unstar to see the empty state, then restore |
| 3 | `/stock/[symbol]` | All 8 sections, scroll-spy nav, the `#chart`/`#patterns` anchors that `SymbolActionBar` targets |
| 4 | `/stock/[symbol]/analysis` | All three modes, indicator picker, preset switching, targets/R:R panel, ATR multiple input, scroll-spy |
| 5 | `/stock/[symbol]/elliott-wave` | Degree drill-down, candidate switching, pivot table, threshold input |
| 6-11 | `/historical`, `/strategies`, `/experiment`, `/validation`, `/analytics`, `/market` | Full walkthroughs, not glances — these are the least-recently-polished screens |
| 12 | `/learn` + `/learn/faq`, `/learn/scoring-guide` | Check the static content is not visually orphaned from the app |
| 13 | `/stock/NOTASYMBOL` | The invalid-symbol path end to end |
| 14 | The non-qualifying symbol on routes 3, 4, 5 | The `usingLiveFallback` path and its analysis-page equivalent |

### Responsive pass

`browser_resize` to **390×844** (mobile): dashboard, watchlist, detail, analysis, elliott-wave, and one research tool (`/analytics`) — the research tools were likely never mobile-tested.

Then **820×1180** (tablet) on dashboard + analysis: `lg:` is where the analysis page's two-column grid and its sticky right rail collapse, and it is the easiest breakpoint to get wrong.

Known trouble spots to check deliberately: NavBar hamburger, `SymbolSearch` combobox, the analysis page's **stacked sticky headers** (NavBar `top-0` + toolbar `top-[4.5rem]` + `scroll-mt-32` offsets — three magic numbers that must agree), horizontally scrolling tables, and chart containers.

### Dark mode pass

Full pass over dashboard, detail and analysis in dark mode. Look for low-contrast text, borders that vanish, and **chart colors that don't adapt** — `lightweight-charts` and `recharts` take hex strings, not Tailwind classes, so they cannot inherit the theme and are the most likely place a dark-mode bug survives.

### Per-screen findings template

Recorded identically for every screen, so the final report can be organized by screen as requested:

- **Route / symbol used**
- **Consistency** — reuses the shared kit and `theme.ts` tokens the way siblings do, or diverges into ad hoc classes?
- **Information hierarchy** — are trend status, score, momentum, patterns and wave structure surfaced without digging?
- **Navigation flow** — how you arrive, how you leave, whether cross-links are discoverable and honestly labeled
- **Visual polish** — spacing, alignment, truncation, long symbol names, negative numbers, N/A values
- **Loading / empty / error** — present? shared components? page-level guard or only scoped?
- **Accessibility** — focus order, `focusRing` on every interactive element, labelled controls, color never the only signal, sane heading hierarchy
- **Console / network** — errors, warnings, failed or slow requests
- **Mobile** — layout breaks, overflow, tap targets (≥44px), sticky stacking
- **Findings** — each tagged `[fix now]` or `[report only]`

---

## Phase 2 — Fixes

### Fix now — small, local, presentation-only, unambiguous

**F1 — Page-level loading/error guard on the analysis page** (D1).
`analysis/page.tsx`. Add an `isLoading`/`isError` guard before the main render using the already-imported `LoadingSpinner`/`ErrorMessage`, matching the pattern the detail page and dashboard already use — including the detail page's distinction between a `TypeError` (backend unreachable) and a genuine not-found. Additive; touches no data flow.

**F2 — Guards on the elliott-wave page** (D2).
`elliott-wave/page.tsx`. Determine whether the remaining cards share the wave query or have their own; add the minimal guard that covers them. Prefer one page-level guard over several scoped ones.

**F3 — Make the analysis screen reachable** (D3).
Add an **Analysis** action to `SymbolActionBar` so it appears identically on all three `/stock/[symbol]/*` routes — which is exactly what that component's own docstring says it exists to do. Rename the detail page's *"Try the new analysis view →"* to a neutral label; a verified, drift-fixed screen should not be labelled as an experiment.
*This improves discoverability. It does not change any default — every existing link still lands where it lands today. That is the promotion decision, and it stays with the user.*

**F4 — Fix the self-contradicting action bar** (D4).
`SymbolActionBar.tsx`. On the analysis page, "Patterns" must not navigate away from a page that has a Patterns mode. Resolve so the bar reflects the surface it is on — the minimal form is making the bar's targets route-aware rather than always pointing at detail-page anchors. Verify the `#chart`/`#patterns` anchors still resolve correctly on the detail page after the change.

**F5 — Polish items surfaced during the click-through.**
Spacing, alignment, truncation, missing `focusRing`, inconsistent badge/metric formatting, tap targets, contrast. Fixed inline with existing shared components. **No new components, no new dependencies.** Anything larger than a local change gets re-tagged `[report only]`.

### Investigate — fix only if provably safe, otherwise report

**I1 — The copy-pasted Overview / Engines / Live blocks** (D5).
First diff the two blocks precisely. **If near-identical**, extract to shared components under `web/src/components/stock/` as a pure move with no behavior change, and verify both pages render identically before and after via screenshot comparison. **If they have quietly diverged**, stop and report the divergence — a shared component that hides a real behavioral difference is worse than the duplication. The decision follows the evidence, and I will not force the extraction to make the diff look tidier.

**I2 — Elliott Wave consistency across the two surfaces.**
Compare the analysis page's condensed Elliott mode against the standalone page: same degree colors (`CANDIDATE_COLORS`), same labels, same terminology, same interactions. **Label, color and copy mismatches: fix now** — those are pure seams. **Structural differences: report only** — the condensed/full split is intentional by design, and the standalone page's ranking panel and pivot table are genuinely more than a rail can hold.

### Report only — never executed in this pass

- **The promotion decision** (its own section below).
- **Any change to default link targets** — dashboard rows, watchlist rows, symbol search, `SymbolActionBar` defaults. Adding a new way to reach analysis is in scope; changing where existing links land is not.
- **NavBar / IA restructuring** beyond what is already reasoned through there.
- **Anything requiring non-presentation code** — query keys, API contracts, `api-client.ts` response shapes — even when a UI symptom triggered it.

### Guardrails

- Presentation layer only: components, pages, Tailwind classes, `theme.ts` tokens.
- No new dependencies. No new abstractions beyond the I1 extraction, and only if the evidence supports it.
- No architecture or IA change without flagging it first.
- **The legacy detail page is not deleted, redirected, unlinked or demoted.**
- Each fix stays a small isolated diff — ideally one file.
- No commits unless asked; the diff is presented for review.

---

## Phase 3 — Verification

1. `npx tsc --noEmit` and `npm run lint` — clean, compared against the Phase 0 baseline.
2. Re-walk every touched screen in the browser: desktop, mobile, both themes.
3. **Force the states I claim to have fixed** rather than asserting they work: stop the backend and reload the analysis and elliott-wave pages to confirm the error path renders; throttle to observe the loading path; load the non-qualifying symbol for the empty/fallback path.
4. Console clean on every touched screen.
5. If I1 was applied: screenshot both pages before and after to confirm no visual change.

---

## Phase 4 — Report

Organized by screen, as requested:

1. **Per-screen sections** — Dashboard, Watchlist, Stock Detail, Stock Analysis, Elliott Wave, Historical, Strategies, Lab, Research, Analytics, Market, Learn. Each: what was checked, what changed, and reasoning for anything significant. Mobile and dark-mode notes where they apply.
2. **Cross-cutting** — navigation and IA coherence, the I1 duplication outcome, the I2 Elliott Wave consistency outcome, shared-kit adherence across the app.
3. **Report-only findings** — each with a one-line recommendation, none applied, clearly marked as not-done.
4. **Promotion recommendation** — separate final section.

---

## The promotion recommendation — evaluated against explicit criteria

This is the judgment call the user asked for, and it will be answered with evidence rather than taste. Criteria, all assessed during the audit:

**Feature parity.** Build a checklist of everything the detail page has that the analysis page does not — the `IMPROVEMENT_HINTS` map, `investmentReadiness()`, the strengths/weaknesses ranking, the full rule table, the historical score and rank charts (`getStockHistory` is fetched *only* on the detail page), and the `usingLiveFallback` banner for non-qualifying symbols. For each: is it load-bearing for researching a stock, or safely droppable? A promotion that silently loses the rule table is not a promotion.

**State-handling parity.** After F1, does analysis match or beat the detail page on slow, failed and empty data — including the non-qualifying-symbol path.

**Entry points.** D3 established that analysis is currently reachable by exactly one soft link. Any promotion is really a rewiring of dashboard rows, watchlist rows, symbol search and `SymbolActionBar` — that scope gets stated plainly, not glossed.

**Redundancy cost.** Two pages importing the same dozen components is a standing maintenance liability regardless of the outcome, and gets reported either way.

**Deliverable**: a clear recommendation — *ready now* / *ready once these N named gaps close* / *not yet* — with an explicit confidence level, the concrete work a promotion would entail, and a migration path (redirect vs. alias vs. retire) if approved.

**Flagged for sign-off. Not executed.** No route, default link target or redirect changes ship in this pass.
