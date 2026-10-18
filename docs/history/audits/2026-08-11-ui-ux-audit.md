# UI/UX Audit Report — Momentum25 India (`web/`)

Date: 2026-08-11
Plan: `docs/2026-08-10-ui-ux-audit-plan.md`

## How this was verified

Every state in this report was checked against the running app with real data,
not read off the source. Method: Playwright was installed in a scratch
directory (outside the repo, no dependency added to the product) and drove
headless Chromium against the dev server. Each route was exercised for console
messages, page errors, failed requests and slow requests; states were forced
with real API failures and with browser-level route abortion to simulate a
backend down. Screenshots were captured for the record; structural judgment was
made from DOM probes because the running model cannot inspect images. The three
audit symbols: `SANSERA` (ranked #2, qualified), `RELIANCE` (in-run, gate
failed), `ORIENTBELL` (not in run; stock endpoint 404s, live endpoint serves —
the live-fallback path).

Baseline: `tsc --noEmit` and `next lint` clean before and after the pass.

---

## Per-screen sections

### Dashboard (`/`)

- **Checked**: strategy selector, run history, Refresh trigger, row → detail
  navigation (`SANSERA` row lands on `/stock/SANSERA?strategy=…`).
- **Changed**: nothing.
- **Console/network**: clean.
- **Mobile/dark**: no overflow after the shared `PageHeader` wrap fix; dark
  pass clean.

### Watchlist (`/watchlist`)

- **Checked**: starred rows, Remove action, unstar → empty state ("No stocks
  watchlisted yet…"), row links to the detail page.
- **Changed**: nothing — the plan's source finding held live: loading, error
  and empty states are already fully handled.
- **Note**: the starred state I consumed during the check (TCS) was restored
  via the API afterwards.

### Stock Detail (`/stock/[symbol]`)

- **Checked**: all 8 sections via the scroll-spy nav, `#chart` / `#patterns`
  anchors, fallback banner for `ORIENTBELL`, error message for `NOTASYMBOL`,
  the `TypeError` (backend unreachable) branch, section navigation on mobile.
- **Changed**:
  - Removed the *"Try the new analysis view →"* link. Its purpose — the only
    path to the analysis screen — is now served by the "Analysis" action on
    `SymbolActionBar`, present on every stock route.
  - SectionNav sticky bar margins corrected for mobile (`-mx-4 sm:-mx-6`,
    was `-mx-6`), which left an 8px background overhang at 390px.
- **Report only**:
  - `#patterns` only exists in the DOM after the live on-demand evaluation
    finishes. Clicking "Patterns" before it resolves lands at an empty anchor.
    This is pre-existing; surfacing it would change what the detail page
    renders while loading — see finding R2.

### Stock Analysis (`/stock/[symbol]/analysis`)

- **Checked**: all three modes, indicator picker, preset switching, ATR
  multiple input, targets/R:R panel, scroll-spy, mode links in the action bar,
  invalid-symbol and fallback paths, mobile/tablet/dark.
- **Changed (F1)**: page-level loading and error guard matching the detail
  page pattern, including the `TypeError` (backend unreachable) vs. genuine
  not-found distinction. Before: a failed or pending pair of core queries
  silently rendered a chart above a void. Now: spinner during load, real error
  copy on failure.
- **Changed (F1b)**: the `usingLiveFallback` amber banner for symbols absent
  from the latest run — state-handling parity with the detail page.
- **Changed (F3/F4)**: the mode now lives in the URL (`?mode=chart|patterns|elliott`).
  The action bar on this route shows "Analysis" as the current surface and its
  Chart / Patterns / Elliott Wave actions switch modes in place instead of
  navigating to the detail page's anchors.
- **Verification**: `?mode=patterns` deep-links directly into Pattern mode;
  clicking Chart returns to chart mode; backend-down and invalid-symbol paths
  both render their error states; console clean through a full mode walk.

### Elliott Wave (`/stock/[symbol]/elliott-wave`)

- **Checked**: degree drill-down, candidate switching, pivot table, threshold
  slider, all cards during load and failure.
- **Changed (F2)**: one page-level guard for the whole surface, replacing the
  single guarded card. The Waves, Ranking and Pivots cards previously rendered
  blank during load or failure; the chart card showed an empty frame. All four
  derive from one query, so one guard covers them, with the same `TypeError`
  distinction as the other pages. Dead scoped guards removed.
- **Changed (I2)**: candidate colours clamp to the palette length like the
  analysis rail does (a 4th candidate could previously render without its
  colour).

### Historical (`/historical`)

- **Checked**: run list loads, no console errors.
- **Changed**: nothing.

### Strategies (`/strategies`)

- **Checked**: evaluation + contribution calls resolve, cards populated.
- **Changed**: nothing.

### Experiment Laboratory (`/experiment`)

- **Checked**: loads and fetches cleanly.
- **Changed**: nothing.

### Strategy Validation (`/validation`)

- **Checked**: dashboard POST resolves, page renders.
- **Changed**: nothing.

### Research Analytics (`/analytics`)

- **Checked**: desktop and mobile load, no errors, no overflow.
- **Changed**: nothing.

### Market (`/market`)

- **Checked**: market-context fetch resolves.
- **Changed**: nothing.

### Learn hub (`/learn`, `/learn/faq`, `/learn/scoring-guide`)

- **Checked**: content pages render consistently with the app chrome; scoring
  guide's strategy fetch resolves.
- **Changed**: nothing. Static content is not visually orphaned; it reuses the
  app's layout and theme.

---

## Cross-cutting

### Navigation and IA

The `NavBar` analysis in the plan held up live: Dashboard + Watchlist on top,
everything else under Research Tools, mobile hamburger with the same hierarchy.
No restructuring needed or performed. The single real seam was stock-level:
the analysis screen was reachable from exactly one soft link. The action bar
now carries Chart / Analysis / Elliott Wave / Patterns on every
`/stock/[symbol]/*` route, so the reader can always see each surface and get
to it — the exact purpose the component's docstring states.

### I1 — duplicated Overview / Engines / Live blocks: not extracted

The two pages' lifted blocks were diffed token-by-token. Outcome: the
ScoreGauge + Rule Pass Matrix block, the Engine Contributions card and the
whole live-analysis block (MomentumOverview through RelativeStrengthVsIndex)
are now **textually identical** across both pages. Three drift points were
found and fixed (all presentation-only):

- missing `lg:gap-10` on the analysis gauge wrapper;
- missing `text-right` + "score" caption on the analysis engine cards;
- missing `dark:text-slate-400` on the analysis Rule Pass Matrix label.

But one real difference remains, and it is load-bearing: the metric-card grid
shows 4 cards on the analysis page (Momentum, Buy Setup, Composite, RS Rating)
and 8 on the detail page (adds Rank, Percentile, Hard Filters, Suggested
Stop). That is a genuine information-scope difference, not a seam. Extracting
a shared component now would hide behavioural difference inside a shared file —
worse than the duplication — so nothing was extracted. The drift fixes
removed exactly the risk the plan named: the two copies no longer silently
diverge, and a future extraction is unblocked if the metric-card sets are ever
unified.

### I2 — Elliott Wave consistency

Both surfaces use the same `CANDIDATE_COLORS`, same "Top count / Alternate N"
labels, same `describe()` phrasing, and the same degree-nav interactions.
One colour clamp was fixed (see Elliott Wave above). The condensed rail on
the analysis page vs. the full ranking panel + pivot table on the standalone
page is intentional by design and left as-is, with the cross-link
("Full ranking panel and pivot table →") preserved.

### Shared-kit adherence

All pages reuse the shared kit. The six research tools all import
`LoadingSpinner`/`ErrorMessage`/`EmptyState` and the design tokens; no page
was found re-rolling its own card or spinner. Theme awareness is consistent:
recharts uses `useChartColors()`, `lightweight-charts` renders on a
transparent background with slate-toned text and grids, so both adapt to dark
mode by construction.

---

## Report-only findings (none applied)

| # | Finding | One-line recommendation |
|---|---|---|
| R1 | `#patterns` anchor on the detail page only exists once the live on-demand evaluation resolves; early clicks land at nothing. | Render the anchor container unconditionally so the target always exists. |
| R2 | Detail-page metric row (8 cards) vs. analysis-page metric row (4 cards) is a real information-scope difference. | Decide the canonical set; unify; then extract the shared block (I1 unblocked). |
| R3 | Analysis page omits the detail page's rule-level guidance: `IMPROVEMENT_HINTS`, `investmentReadiness()` nuance, strengths/weaknesses cards, full rule table, historical score/rank charts, Executive Summary and Momentum Thesis. | See the promotion recommendation — these are its named gaps. |
| R4 | Default link targets unchanged (dashboard rows, watchlist rows, symbol search, action-bar defaults all still land where they did). | Leave unless the promotion is approved. |
| R5 | Console logs expected 404 responses for invalid symbols (browser-level noise, not app errors). | Optionally suppress via backend status codes; cosmetic. |
| R6 | Dev environment: two concurrent `next dev` instances were sharing one `.next` cache; the port-3000 server wedged and stopped serving; the backend CORS allow-list is pinned to `http://localhost:3000` (a browser on any other port gets CORS-blocked). | Restart the dev server with `make web-dev` (done this pass); if you ever run on another port, widen CORS first. |

---

## Promotion recommendation — the analysis screen vs. the detail page

**Recommendation: ready once these N named gaps close — not yet, but close.
Confidence: high** (all surfaces verified with live data on desktop, mobile
and tablet, dark mode, and forced failure states).

The evidence, per the plan's criteria:

**Feature parity.** Everything the detail page has that the analysis page does
not, with a load-bearing judgment:

| Detail-only feature | Load-bearing? |
|---|---|
| `IMPROVEMENT_HINTS` (What Would Improve This Ranking) | Yes — it converts a failed rule into an actionable step. |
| `investmentReadiness()` readiness badge (Qualified / breakout-not-confirmed nuance) | Yes — the PASS/FAIL badge on analysis flattens the two-tier qualify state. |
| Strengths / Weaknesses ranking cards | Yes — the fastest read on why a stock ranks where it does. |
| Complete Rule Evaluation table (every rule with contribution) | Mostly — the analysis page has Engine Contributions + Rule Pass Matrix + Trend Template card; the per-rule contribution column is the gap. |
| Historical score and rank charts (`getStockHistory`) | Yes for rank trajectory, the page's only time-series view; moderate for scores (gauge covers the present). |
| Executive Summary + Momentum Thesis cards | Partial — the thesis explains the score; the page carries no narrative. |
| 8-card metric row vs 4-card row | Moderate — Rank/Percentile/Hard Filters are in the header or Rule Pass Matrix already. |
| `usingLiveFallback` banner | **Closed this pass.** |

All gaps are presentation-only ports from the detail page; none touches query
keys, API contracts or scoring.

**State-handling parity.** Closed this pass. After F1 + F1b the analysis page
matches the detail page on slow, failed, empty and backend-down data, and on
the non-qualifying-symbol path (banner now shown).

**Entry points.** Reachability is no longer the blocker: the analysis screen
is now a first-class action on every stock route. A promotion would rewire
dashboard rows, watchlist rows, symbol search and the action-bar default to
land on `/analysis` — that scope was deliberately not executed.

**Redundancy cost.** Two pages importing the same dozen components remains a
standing liability either way. The drift fixes removed the divergence risk;
the remaining difference is one deliberate metric-card set.

**What a promotion would entail** (if approved): re-point the entry points
listed above; port the seven load-bearing items; then either retire the
detail page via redirect or keep it as the legacy surface (recommended:
soft promotion — keep the detail route working, stop advertising it).

**Not executed. No route, default link target or redirect changed in this pass.**