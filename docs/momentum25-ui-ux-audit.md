# Momentum25 UI/UX Audit

Date: 2026-08-15
Repo HEAD: `81220db`
Scope: `web/` frontend (Next.js 14.2.0, React 18, Tailwind 3.4.19, TanStack Query/Table, lightweight-charts 5, recharts 3)
Method: read-only source review at `web/src/**`, confirmed live against the running dev server (`localhost:3000`, API `localhost:8000`). All 11 routes return HTTP 200. No code was modified; no mutating endpoint was called.

Note on the screenshots: this audit did not visually inspect any external Investing.com screenshots. The reference is "Investing.com-quality information architecture, density, navigation, chart presentation and usability, with a distinct Momentum25 identity." Findings rest on source code and rendered HTML, not on those images.

---

## 1. Executive Summary

### Overall UX assessment

Momentum25 is a **competent, disciplined, methodology-loyal** single-page-application that ranks Indian momentum stocks. It is not production-grade as a research product. The information architecture is too flat for an investor, the design system is half-built, the stock detail reads bottom-up instead of top-down, and several secondary screens are quant/developer tools exposed at investor level.

### Current strengths

1. **Methodology honesty in copy.** Empty qualified sets, "—" vs "0", `Measurability` flags, risk-only stop-loss captions, and Elliott-Wave separation disclaimers are written in plain English. No false claims ("Momentum25 never lowers its screening bar to populate a list").
2. **Audit-driven accessibility on the primary table.** `scope="col"`, `aria-sort`, `tabIndex`, Enter/Space sort handlers (F17 fix), `aria-label` on icon-only pagination, full combobox pattern on `SymbolSearch`.
3. **Real table primitives on the screener.** TanStack Table v8 with client sort, global filter, pagination and a defensive in-browser "Signal score" overlay.
4. **Clean separation of Elliott Wave.** `/stock/[symbol]/elliott-wave` calls only `getElliottWave`; no momentum-score, composite-score or gate import. The projected completion zone is rendered with an explicit cross-link to the analysis screen and a standing caption: "Elliott Wave analytical projection; not part of the Momentum25 score or ranking."
5. **Risk-only stop-loss.** `SuggestedStop.tsx` shows level, method and distance. The docstring and footer both forbid target/reward/R-multiple. The dashboard's `MetricCard` labels the eighth tile "Suggested Stop (risk only)" with a JSX comment: "Risk-only. Deliberately carries no reward/target counterpart."
6. **Three-mode theme** (light/dark/system) with a pre-hydration script that prevents FOUC.
7. **Live-fallback presentation** for symbols outside the latest run, with an amber banner and a `data_as_of` timestamp.

### Biggest weaknesses

1. **Information architecture mismatch.** The investor sees 7 top-level destinations under "Research Tools" but only 2 are investor-grade (`Market`, `Learn`); 4 are quant/developer instruments (`Strategies`, `Lab`, `Research`/`Validation`, `Analytics`); 1 (`Historical`) is a researcher's toy. The flagship experience (`/stock/[symbol]/*`) is hidden behind search and an in-page action bar.
2. **No design system.** `tailwind.config.js theme.extend` is `{}`. `lib/theme.ts` defines tokens as TypeScript string constants but they are advisory; components reimplement utilities inline. `PageHeader` uses `text-xl` while `typography.pageTitle` prescribes `text-2xl`.
3. **Stock detail reads bottom-up.** The page answers "why does it rank" last. Rank, percentile and historical score charts appear in the middle. The dense "live analysis" block is the longest section but it lives at the bottom.
4. **Two metric-card siblings.** `validation/page.tsx` declares a local `MetricCard` (API `good/bad: boolean`, `text-sm font-mono`, `bg-slate-50 … rounded-lg p-3`) that shadows the shared `MetricCard` (API `color: string`, `text-xl tabular-nums`, `rounded-xl`).
5. **Research pages are inconsistent with the primary palette.** Five of six ("Historical", "Strategies", "Lab", "Research", "Analytics") use `bg-white dark:bg-slate-900` page chrome; only `Market` matches the dashboard's `bg-slate-50 dark:bg-slate-950`. The Card `dark:bg-slate-800/50` reads on a different tone behind each.
6. **Accessibility gaps on shared atoms.** `StatusDot`, `ScoreGauge`, `LoadingSpinner`, `ErrorMessage` lack `role`/`aria-live`. `NavBar` active links lack `aria-current`. Strategy chips, date tiles and filter buttons omit `aria-pressed`.
7. **No skeletons.** Every loader is a centred `LoadingSpinner`. Large tables, stock detail and the validation dashboard shift layout when data arrives.
8. **Watchlist has no sort, no filter, no search.** The dashboard sets the bar. The watchlist does not meet it. Errors render as `EmptyState` (no retry, no error specificity).

### Overall redesign recommendation

**Targeted redesign, not a rewrite.** Three pillars:

1. **Promote the analysis screen to the flagship stock route** (per the prior audit's logged recommendation) and reorganise the stock-detail hierarchy top-down: what is happening → how strong → why it ranks → supports → downside risk → deeper research.
2. **Wire `lib/theme.ts` into `tailwind.config.js`** as the single source of truth; retire the second `MetricCard`, the duplicated `focusRing` CSS class, and the raw `Card.badge` class strings.
3. **Split navigation into investor vs research** so a user lands on `Dashboard → Watchlist → Market → Stock → Learn` and never sees the strategy-engineer views unless they ask.

No methodology, scoring, ranking, strategy configuration, gates, thresholds, stop-loss or Elliott-Wave logic is touched.

---

## 2. Current Product Assessment

### Stack and shape

Next.js 14 App Router, almost entirely client-rendered (`'use client'` directives on every page that fetches data). One shared `NavBar` at the root `layout.tsx`. No route group layouts; the three stock routes (`/stock/[symbol]`, `/stock/[symbol]/analysis`, `/stock/[symbol]/elliott-wave`) share state through a custom `useChartShell` hook and the `SymbolActionBar` component, not through a Next layout.

State: React Query 5 (`staleTime: 30_000`, retry 1) + React Context for theme and strategy. Charts come from two libraries: recharts for gauges and time-series summaries, lightweight-charts for the price/indicator panes.

### What the investor actually sees

Routing fan-out:

```
NavBar (sticky, h-14) ── /  /watchlist   ── search ─→  /stock/[symbol]*  ── SymbolActionBar ─→
                                   Research Tools dropdown                                /analysis  /elliott-wave
                                   (7 items, flat)                                        learn/* sidebar
```

The dashboard is dense and honest but score-centric, not price-centric: the ranked table omits price and daily change. Price appears only on `MomentumOverview` (stock detail) and the watchlist.

The stock detail is a long single-page scroll with eight anchored sections. The analysis page is a pivot view with a chart-first layout, segmented control and indicator picker. Elliott Wave is its own page with a degree breadcrumb and a labelling-confidence ranking panel. None of these three is in the NavBar; all are reached through search and the action bar.

### What an investor cannot find

- A discount to a single stock from the dashboard without first clicking a row.
- A way to switch strategy on the watchlist without walking back to the dashboard.
- A way to switch strategy on `/strategies` or `/analytics` (both hardcode `minervini_trend_template` in local `useState` and ignore `useStrategy()`).
- A bone-fide investor research hub beyond `/market` and `/learn`. `/validation`, `/historical`, `/experiment` and `/analytics` are quant surfaces.

### Overall status

| Area | Status |
|---|---|
| Navigation / IA | **MAJOR REDESIGN** |
| Screener (dashboard) | **NEEDS IMPROVEMENT** |
| Stock detail | **MAJOR REDESIGN** |
| Watchlist | **NEEDS IMPROVEMENT** |
| Chart experience | **NEEDS IMPROVEMENT** |
| Technical workbench | **NEEDS IMPROVEMENT** |
| Momentum25 explanation | **PASS with gaps** |
| Elliott Wave separation | **PASS** |
| Stop-loss risk-only framing (component layer) | **PASS** |
| Stop-loss / targets (analysis page layer) | **NEEDS IMPROVEMENT** — see §16 |
| Market screen | **PASS** |
| Strategies / Lab / Validation / Analytics / Historical | **NEEDS IMPROVEMENT** (one or more: **NEEDS IMPROVEMENT** each; `/experiment` is **MAJOR REDESIGN** for investor exposure) |
| Learn hub | **PASS** |
| Visual design | **NEEDS IMPROVEMENT** |
| Information density | **NEEDS IMPROVEMENT** |
| Responsive / mobile | **NEEDS IMPROVEMENT** |
| Accessibility | **NEEDS IMPROVEMENT** |
| Performance UX (perceived) | **NEEDS IMPROVEMENT** |
| Empty / error / loading states | **NEEDS IMPROVEMENT** |
| Product coherence | **NEEDS IMPROVEMENT** |

---

## 3. Information Architecture Assessment

### Current structure

Top bar (`components/shared/NavBar.tsx:90-103`):

- Primary, always visible: `Dashboard` (`/`), `Watchlist` (`/watchlist`).
- `Research Tools` dropdown (7 items, order): `Historical`, `Strategies`, `Lab` (`/experiment`), `Research` (`/validation`), `Analytics`, `Market`, `Learn`.

Hidden routes (no nav entry, reached via `SymbolSearch` + `SymbolActionBar`): `/stock/[symbol]`, `/stock/[symbol]/analysis`, `/stock/[symbol]/elliott-wave`.

Secondary navigation patterns:

- `Learn` has its own left sidebar (`app/learn/layout.tsx`): Overview, Momentum Investing, Minervini Methodology, Momentum25 Methodology, Scoring Guide, Rule Guide, FAQ.
- Stock detail has an in-page scroll-spy tab strip (`SectionNav`) — sticky, below the NavBar.
- Stock sub-routes use `SymbolActionBar`: Chart / Analysis / Elliott Wave / Patterns + `WatchlistStar`.

### Hierarchy assessment

- **Too many top-level destinations.** 9 if you count the 2 primary + the 7 dropdown items, plus 7 learn sub-pages. The Research Tools umbrella hides the investor's daily needs (Market) behind quant tools (Lab, Strategies).
- **Naming collision.** The umbrella is "Research Tools"; one item inside is also "Research". Two things named Research invite confusion. `NavBar.tsx:99` points `/validation` to label `Research`; the umbrella label is at `:332`.
- **Wrong grouping.** `Market` (investor-grade) sits between `Analytics` (quant) and `Learn` (investor). `Learn` is hidden last inside a research-tinted dropdown despite being an onboarding surface.
- **The flagship experience has no nav entry.** An investor opens the app, sees a dashboard, but to "research a stock" they must use a search box that occupies a 28-pixel slot (`w-28 lg:w-44`) on desktop and is hidden on mobile until the drawer opens.
- **Redundancy.** `/analytics` calls the same two endpoints as `/strategies` (`evaluateStrategy`, `getContributionAnalysis`) with identical disclaimer copy. `/analytics` re-renders `/strategies`' numbers as charts.
- **Dead ends.** `/validation`'s strategy `<select>` has one hardcoded option (`:458`). `/analytics` declares `selectedStrategy` and destructures away the setter (`:13`) — non-functional state. `/historical` "Replay Controls" and "Available Historical Runs" both express "pick a date" twice.
- **Misleading labels.** `Lab` for `/experiment` is opaque. `/validation` "Research" duplicates the umbrella. `/analytics` PageHeader promises "win rates, drawdowns" — it does not show them.
- **Untracked destinations.** No breadcrumb, no `aria-current` on the main nav (only `SymbolActionBar` sets `aria-current="page"`).

### Recommended structure (do not implement)

Two top-level groups. Investor above the line; researcher below.

```
Investor (top bar, primary)
  Dashboard        /                       ranked qualified set
  Watchlist        /watchlist               tracked names
  Market           /market                  breadth, sector strength
  Learn            /learn                   methodology hub (sidebar)

Researcher (secondary, after a submissive visual separator)
  Strategies       /strategies              evaluate / compare
  Validation       /validation              forward-returns scorecard  (rename Research → Validation)
  Historical       /historical              date replay
  Analytics        /analytics               run-history charts         (or merge into Strategies)
  Lab              /experiment              parameter overrides        (or hide behind /validation)

Stock (no top bar entry; reached only via search + row clicks)
  /stock/[symbol]            analysis-first flagship (see §6)
  /stock/[symbol]/elliott-wave   separate research screen (see §10)
```

Suggested label fixes: `Research Tools` → `Research`, `Research` item → `Validation`, `Lab` → `Experiment Lab` (or hide). Group the 5 quant surfaces under a single suppressible menu.

The Learn hub should escape the Research Tools dropdown and join Market as a first-class investor destination.

---

## 4. Design System Assessment

### Tokens

`lib/theme.ts` exports `colors`, `chartPalette`, `chartColorList`, `spacing`, `typography`, `focusRing`, `transitions`. The file is flagged "Centralized design tokens for Momentum25" (`:2`).

But `tailwind.config.js` is:

```js
theme: { extend: {} }   // EMPTY
```

So every consumer imports a token string and concatenates it into `className`. There is no Tailwind theme. The result:

- `PageHeader` uses `text-xl font-bold tracking-tight` (`Card.tsx:148`) while `typography.pageTitle` is `text-2xl font-bold tracking-tight` (`theme.ts:122`). They diverge.
- `spacing.page` (`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`) is re-typed inline on every page instead of imported.
- `focusRing` exists both as a TS export (`theme.ts:131`) and as a CSS class `.focus-ring` (`globals.css:24`). The CSS class is unused. Dead code.

### Typography

Inter via `next/font/google` (`layout.tsx:9`), applied as a className on `<html>`. No Tailwind `fontFamily`. No display/heading/body text scale. Heading sizes are picked per component:

- `PageHeader` title: `text-xl`.
- `Card` title: `text-sm font-semibold`.
- `MetricCard` value: `text-xl font-bold tabular-nums`.
- Local `MetricCard` in `/validation`: `text-sm font-semibold font-mono` — a different rhythm.
- `ScoreGauge` value: `text-lg font-bold`.
- Section nav / cards / lists default to `text-xs`.

Three different "primary value" sizes (`text-xl`, `text-lg`, `text-sm`), two fonts for numbers (`font-mono` vs `tabular-nums`), and no fixed typographic scale.

### Spacing and layout

Consistent container: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6`. Card padding `p-4`, header `px-4 py-3`. Grids `gap-4` (cards) and `gap-3` (validation's dense tiles). Section spacing `space-y-6`. Vertical rhythm is uniform across the investor surfaces and `/market`; research pages drop to `gap-3` and `space-y-6` only inside `Card` bodies.

### Color

Palette is consistent: slate for chrome, indigo for primary/active, emerald/rose/amber for semantic states (passed/failed/warn), cyan/violet for chart accents. The `chartPalette` (`theme.ts:87`) and `Badge` `colorMap` (`Card.tsx:80`) share the same key set.

Holes:

- `PageHeader.subtitle` uses `text-slate-500` with no `dark:` variant (`Card.tsx:148`).
- `LoadingSpinner` caption: `text-slate-500` no `dark:` variant (`Card.tsx:109`).
- `ScoreGauge` sub-caption: `text-xs font-semibold text-slate-500` no `dark:` variant (`ScoreGauge.tsx:52`).
- `Card.badge` prop accepts a raw class string. `page.tsx:442,453` passes dark-only pairs (`bg-emerald-900/50 text-emerald-300`) — the badge renders without a light-mode colour pair, a real light-mode regression.
- `useChartColors.ts:7` sets `tick` to a fixed `#64748b` in both light and dark — minor axis-label inconsistency.

### Borders / radius / shadow

- Cards: `rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 shadow-sm` (`Card.tsx:18`).
- Pills, inputs, buttons: `rounded-md` / `rounded-lg`.
- Badges, status dots: `rounded-full`.
- `FloatingPanel`: `rounded-lg shadow-2xl` (`FloatingPanel.tsx:90`) — different from `Card`'s `rounded-xl shadow-sm`. Minor.

### Buttons / tabs / tables / badges / icons

- **Buttons.** No `Button` primitive. Buttons are built inline. Primary variant: `bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 rounded-lg text-sm font-medium`. Secondary: `border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300`. Three slightly different sizes across pages.
- **Tabs.** Two patterns: `SegmentedControl` (analysis page) and `SectionNav` scroll-spy (stock detail), plus the strategy chips on `/strategies`. No shared component. The chips' selected state (`bg-indigo-600 text-white border-indigo-600`) uses different indigo treatment than the `SymbolActionBar` active button (`bg-indigo-50 text-indigo-700 border-indigo-300`).
- **Tables.** Hand-built per page. `MomentumTable` is react-table v8 with `aria-sort`; `WatchlistTable` is plain HTML without `scope="col"`; `SectorStrengthTable` is plain HTML with `aria-pressed` sort pills; the page-local tables on `/strategies`, `/experiment`, `/validation` reproduce the same `<table>` skeleton without sharing a component.
- **Badges.** `Badge` has a 6-colour `colorMap` (`slate/emerald/rose/amber/blue/indigo`). The `Card` header `badge` prop does not use it (raw class string).
- **Icons.** Inline SVGs only, no icon library. Each `NavBar` icon is a 20×20 viewBox path (`NavBar.tsx:12-83`); charts and indicators reuse a `ChartIcon` catalog. Consistent `w-4 h-4` for nav.

### Empty / loading / error states

- `LoadingSpinner` (`Card.tsx:105`): centred 6×6 spinner, no `role="status"`, no `aria-live`.
- `ErrorMessage` (`Card.tsx:114`): rose-bordered card with an inline warning SVG, no `role="alert"`, no `aria-live`. Decorative SVG lacks `aria-hidden`.
- `EmptyState` (`Card.tsx:131`): bell icon + caption, no ARIA. Decorative SVG lacks `aria-hidden`.
- No skeleton screens anywhere. Every loader is the same spinner.

### Charts

- `useChartColors.ts` theme-aware values for recharts (grid, tooltip bg, tooltip border, tick).
- `lightweight-charts` is themed through inline option calls in `PriceChart.tsx` (candle up/down colours, MA colours, pane colours). No central theme hook.
- `ScoreGauge` uses `chartPalette` and a theme-aware track colour, but no `role="meter"`.

### Status

- **Visual design: NEEDS IMPROVEMENT.** Palette and chrome are consistent. Tokens are half-wired. Typography has no scale. Loading/empty/error atoms lack ARIA. Two `MetricCard`s, two table idioms, two tab idioms, no `Button` primitive.

---

## 5. Screen-by-Screen Audit

### 5.1 Dashboard `/` — `app/page.tsx`

**Current state.** `Live Momentum Dashboard`. Header carries `StrategySelector`, a run badge (`Run #N` + `Latest screening: <date>`), an on-demand `Refresh` button (`This re-evaluates the universe; it usually takes a few minutes`), and a `StalenessBanner` (`FRESH` invisible, `MARKET_CLOSED` slate, `STALE` amber). Body: `RunSummaryCards` (Universe / Qualified / Filtered Out / Duration), a small "Last refresh" box, and `MomentumTable` titled "Ranked Universe".

**What works.**

- The 5-second scan: strategy, freshness, qualified count, ranked list — all visible without scrolling.
- `StalenessBanner` is trading-calendar-aware. Market-closed reads as neutral, not as failure.
- Empty qualified set copy: "No stocks currently satisfy the {strategy} methodology. This is expected behavior, not an error — Momentum25 never lowers its screening bar to populate a list." Excellent microcopy.
- 60-second auto-refresh on `latest-run`, `rankings`, `data-freshness`; 5-second status poll during an on-demand run.
- `MomentumTable` is a real react-table v8 with sort, global filter and pagination.
- `StrategySelector` self-heals a stale `localStorage` selection back to the first available option (`StrategySelector.tsx:23-29`). Only lists strategies with a completed run, so every option renders real stocks.

**Problems.**

- No price, no daily change in the table. Defensible (ranking is the point), but an investor expecting a "stock list with prices" finds none. There is no setting to add price columns.
- No percentile column. RS rating is absolute only.
- Default sort has no visible arrow until a header is clicked; the API order is implicit.
- "Signal score" overlay runs `getOhlcv` per visible row (steppers over the page-set). Hidden by default; the tooltip explains it is in-browser only. Correct, but a casual user cannot tell what a "Signal" is without reading the tooltip.
- `Refresh` runs a full screening pass (minutes). No background affordance, no progress bar beyond the amber badge.
- `RunSummaryCards` "Duration" tile is an engineer metric, not an investor one.

**Severity.** NEEDS IMPROVEMENT.

**Recommendation.** Keep the structure; add price / daily change as optional default-on columns (the data is already in `/live`); default-sort `[{ id: 'rank', asc: true }]` so the arrow conveys intent; move "Duration" into a debug popover or remove from the 4-up summary.

### 5.2 Watchlist `/watchlist`

**Current state.** `watchlist/page.tsx` (18 lines): `PageHeader` title `Watchlist`, subtitle `Tracked symbols · <strategy>`, no header controls, then `WatchlistTable`. The page has **no `StrategySelector`**: the strategy is sticky from the dashboard.

`WatchlistTable.tsx` (197 lines) renders 9 columns: Symbol, Close, Change, Momentum, RS rating, Rank, Rank Δ, Below 52w high, Remove. One server call `getWatchlistDetail`.

- Symbol: indigo `Link` to `/stock/{symbol}?strategy=…` + `live` superscript pill when `!in_latest_run`.
- Rank cell distinguishes three states: `#N` (ranked), `not qualified` amber pill with tooltip (in-run but failed a gate), `—` slate (not in run). Audit U6 fix.
- Rank Δ colour-coded emerald/rose/neutral, `new` pill when `rankChange == null`.
- Remove button: `aria-label="Remove {symbol} from watchlist"`, ${focusRing}, neutral until hover turns rose.
- `Card` subtitle: "scores from the latest run, live-evaluated where outside it."

**What works.**

- Three-state Rank cell — precise, each state tooltip-explained.
- One server call. No per-row fan-out.
- Provenance stated in the Card subtitle.
- Accessible Remove buttons; per-row `removing` gate (`remove.variables === item.symbol`).

**Problems.**

- No sort. No filter. No search. The dashboard sets the bar; the watchlist does not meet it. A user tracking 15 names cannot click "Rank Δ" to see risers/fallers.
- No in-place strategy switch.
- No `refetchInterval`. The watchlist loads once and only updates via mutation invalidation. A long-open tab can go stale; the dashboard auto-refreshes every 60s.
- Error renders as `EmptyState`, not `ErrorMessage`. A backend failure looks identical to "no data". No retry control.
- `<th>`s lack `scope="col"` (the dashboard has it).
- No columns hidden on mobile. All 9 columns present, `overflow-x-auto`, cells `whitespace-nowrap`. The Remove column scrolls off-screen on phones.

**Cross-file hazard.** `rank_change` is signed opposite on the watchlist endpoint vs the rankings endpoint (`use_cases/watchlist.py:176` returns `prev - rank`; `use_cases/rankings.py:92` returns `rank - prev`). Both front ends render green = improved, so the visible UX is correct. The contract is split — a future component reusing the field could invert green/red. (See §16.)

**Severity.** NEEDS IMPROVEMENT.

**Recommendation.** Add column sort (Rank, Rank Δ, Change, Below 52w high); add an in-page `StrategySelector`; switch error to `ErrorMessage` with retry; add a 60s `refetchInterval`; auto-hide the Remove column on small screens or move it to a row long-press menu; add `scope="col"` to headers.

### 5.3 Stock Detail `/stock/[symbol]` — `page.tsx` (flagship)

**Current state.** PageHeader with symbol, three badges (qualification, investment-readiness, run id), `SymbolActionBar current="chart"`. Sticky `SectionNav` with 8 sections: overview, chart, trend, engines, rules, scores, history, live. The page renders top-down:

1. **Overview** — two `ScoreGauge` (Momentum, Buy Setup) + `RulePassMatrix` (heatmap of all rules, `role="img"` + per-swatch `aria-label`), then a `grid-cols-2 md:grid-cols-4` of 8 `MetricCard`s: Momentum Score, Buy Setup Score, Composite Score, RS Rating, Rank, Percentile, Hard Filters (failures), **Suggested Stop (risk only)**. Two prose cards: Executive Summary (`overall_rationale`) and Momentum Thesis.
2. **Chart** — single `Card title="Price history"` with `PriceChart`. No analysis rail.
3. **Trend Template** — `TrendTemplateCard` with grouped rules (price position / trend structure / relative strength), plain-language labels, gate pass/fail, weights, "What Would Improve This Ranking" hints (`IMPROVEMENT_HINTS`), "Other conditions" for any rule the component does not yet list.
4. **Historical Scores** — recharts `LineChart h-72` of momentum and buy-setup over 90d of run history (only when `chartData.length > 1`).
5. **Engines** — 2-col text cards for relative_strength, pattern, breakout, risk, volume_accumulation; "Engine Contributions" card with `EngineContributionBars`; per-engine tiles.
6. **Rules** — Strengths card / Weaknesses card; "Complete Rule Evaluation" listing every rule with `StatusDot`, engine_id, actual_value, threshold, contribution.
7. **Historical Rankings** — recharts rank-over-time chart with `<YAxis reversed>` so rank 1 sits at the top.
8. **Live Analysis** — verdict badge, `MomentumOverview` (close / 52w high / 52w low / distances / score), `MomentumView` (Trend Template checklist with `sr-only "Met/Not met"` + engine sub-scores), `TechnicalWorkbench` (six indicator groups: oscillators/volatility, trend strength, MACD, MAs, stochastic/momentum, distance-from-levels), `VolumeAccumulation`, a 2-col grid of `SuggestedStop` + `RelativeStrengthVsIndex`, `#patterns` block (PatternCard), `WhyItRanks`.

**What works.**

- Complete coverage. Every aspect of the audit brief is present: what is happening (overview, momentum thesis), how strong (gauges), why it ranks (`WhyItRanks` + rule matrix + strengths/weaknesses), what supports (Trend Template, engine cards, Technical Workbench, patterns, RS-vs-index), downside risk (`SuggestedStop` risk-only), deeper research (`SymbolActionBar` → Analysis, Elliott Wave).
- `RulePassMatrix` carries `role="img"` per swatch with the rule id and pass/fail. Native `title` tooltip.
- `IMPROVEMENT_HINTS` convert each failed rule into an actionable next step. A unique value-add.
- `investmentReadiness()` distinguishes "Qualified" from "passed but breakout not confirmed" from "not qualified" (emerald / amber / rose).
- `TechnicalWorkbench` deliberately has no signal/verdict column (docstring: "the platform does not produce a per-indicator interpretation and inventing one here would be a fabricated number").
- `SuggestedStop` risk-only (see §15).
- `usingLiveFallback` amber banner for symbols outside the latest run.
- `Scroll-mt-32` on every section so sticky-nav clicks land below the NavBar.

**Problems.**

- **Order reads bottom-up against the audit brief.** Rank + percentile + historical score charts are mid-page. "Why it ranks" (`WhyItRanks`, the clearest single answer) is the last thing on the page. The audit brief asks the page to answer "why does it rank" early and "deeper research" last; the page inverts both.
- **Eight scroll-heavy sections on one URL.** `SectionNav` mitigates this, but the page is a long vertical canvas. The analysis screen (`/stock/[symbol]/analysis`) is a denser pivot.
- **Two `MetricCard` rows differ across routes.** Detail: 8 cards. Analysis: 4 cards. Prior audit (R2) flagged this as a real information-scope difference.
- **`#patterns` anchor only exists after the live evaluation resolves** (prior audit R1). An early click on Patterns in `SymbolActionBar` lands at nothing.
- **`SectionNav` sticky offset `top-[4.5rem]`** is a magic number calibrated to the 56px NavBar. Brittle if the NavBar changes.
- **`IntersectionObserver` with `rootMargin: '-140px 0px -55% 0px'`** — another magic number; sections near the bottom (live) can lose sync.
- **No skeleton.** A centred spinner holds the whole page until all three queries (`live`, `explanation`, `history`) resolve.
- **No price/daily change at the top.** `MomentumOverview` is in section 8, at the bottom. Price is the investor's first question; it appears last.
- **Hard Filters tile shows failures count.** Useless when 0; investor reads "Hard Filters: 0 failures" as a negative. The Trend Template badge already conveys pass/fail.
- **Composite Score separate from Momentum Score.** Three scores (Momentum, Buy Setup, Composite) can confuse users without an inline definition. No tooltip explains the difference in plain language.

**Severity.** MAJOR REDESIGN.

**Recommendation.** Reorder top-down (see §6). Render an in-place price+change+52-week-range header in the page header area, not the footer "live" block. Render `WhyItRanks` above the engine workbench. Move the historical score and rank charts into the existing "Chart" tab as overlays or a side rail, not as separate scroll sections. Always render the `#patterns` anchor even before the live evaluation resolves (prior audit R1).

### 5.4 Stock Analysis `/stock/[symbol]/analysis`

**Current state.** `analysis/page.tsx` (985 lines). `useChartShell` + `useOverlayPreferences` + `useElliottWaveChart` + `useChartPatterns`. Three-way segmented control `MODES = chart | patterns | elliott` mirrored in the URL (`?mode=…`). Sticky toolbar with segmented control + scroll-spy + indicator/pane counters + `Indicators` toggle (`aria-expanded`). Two-thirds/one-third grid: chart + `OverlayPicker` on the left, `TrendTemplateCard` + `StrategyPanel` + mode-specific cards + `WhyItRanks` on a sticky right rail. Below the grid, the page mirrors the detail page's overview / engines / live blocks "lifted as-is" (per prior audit I1).

A "Targets and risk / reward" card at lines 597-652 lists targets built from:

- Elliott Wave projection zone low/mid/high (per candidate, per degree).
- Fibonacci extensions (1.0, 1.272, 1.618, 2.618).
- Pattern measured move.
- ATR objective (`atrMultiple × ATR(14)` above last close; `atrMultiple` is a 0.5–10 step-0.5 input).

Each target prints price, % move from last close, and `R:R = (target.price − lastClose) / (lastClose − stop)` where `stop` is `live?.suggested_stop.level`. Footnote spells out the formula.

**What works.**

- One persistent `PriceChart` (mounted once, never keyed). Docstring bars re-mount on mode switch.
- Indicator/pane catalogue with serializable `uid`s allows duplicate indicators with different params.
- `Steppers, not drag sliders` (`OverlayPicker.tsx:171-172`) — every edit commits once.
- `Indicators` toggle `aria-expanded`.
- `StrategyPanel` shows trend-template preset signals (`lib/strategies.ts`) with directions and ages.
- `usingLiveFallback` parity with the detail page (closed by prior audit F1b).
- Reroutes for `TypeError` (backend down) vs genuine not-found are distinct.

**Problems.**

- **Targets card uses the risk-only stop to compute R:R** — methodologically mixing the stop with reward estimates (see §16). The page-level docstring stresses "nothing on this page feeds the composite score" (true) but the visible UI exposes reward and R-multiple derived from `suggested_stop.level`.
- **Elliott Wave projection zone rendered as a "target"** with an R:R derived from the stop. CLAUDE.md: "The Elliott Wave projection must NOT be presented as a Momentum25 target." The labelling "EW zone low/mid/high — …" inside a Targets card bends that rule at the UI layer.
- **Heavy duplication of detail-page blocks.** Prior audit I1 confirmed textual identity after drift fixes; the maintenance hazard remains. Two files import the same dozen components and arrange them differently.
- **Patterns mode shares the same chart but the toolbar's segmented control consumes vertical space** that could be chart on a single dense screen.
- **No keyboard support on lightweight-charts crosshair.** The O-H-L-C + pane readout is `pointer-events-none` (`PriceChart.tsx:957`), so keyboard-only users get no price readout.
- **Indicator picker is a `FloatingPanel`/popover**, not a real drawer; on narrow viewports it can clip or scroll.

**Severity.** NEEDS IMPROVEMENT (headed for MAJOR REDESIGN if the promotion in §6 is accepted).

**Recommendation.** See §6 and §10 for the resolved structure. Reframe the Targets card: separate the Elliott Wave projection zone presentation from "value target with R:R"; reconsider whether a single target-style card should derive R:R from the risk-only stop. Do not introduce new targets; this is a presentation/coherence question, see §16.

### 5.5 Elliott Wave `/stock/[symbol]/elliott-wave`

**Current state.** Dedicated route (`elliott-wave/page.tsx`, 401 lines). Calls only `getElliottWave`. Page-level docstring: "Every label, pivot, ratio, personality check and confidence number comes from `GET /stocks/{symbol}/elliott-wave`; nothing is computed or inferred here. This screen annotates a chart and explains a labelling. It produces no buy/sell verdict and no score, and nothing it displays is an input to the Momentum25 score, ranking or gates."

Standing caption (line 178): "Chart annotation only — this view produces no buy/sell verdict and no score."

Renders:

- Threshold range `<input min=2 max=20 step=1>` labelled "Finest Degree (reversal threshold)".
- "Competing counts" group (`role="group" aria-label="Competing counts"`) — one button per candidate.
- Degree breadcrumb nav with `▸` separators.
- `<Card title="chart">` with `PriceChart height={620}` carrying `markers` (own + finer-degree parenthesised), `overlayLine` (candidate colour), `overlayLines` (dashed finer subdivisions), `priceZone` (**only at top degree**), `visibleRange`. Footnote summarises the active count.
- Top-ranked count / Alternate count cards (`CountSummary`).
- "Waves" card with per-label buttons (`aria-pressed`); clicking expands `WaveDetail` (personality corroboration with `Evidence ✓/✕/–` and fibonacci relationships).
- "Ranking" card (`RankingPanel`) — labelling-confidence score `X/100` with the caveat: "How cleanly the price action fits this labelling — a measure of fit to Elliott Wave theory, not a forecast and not a probability of profit." All weighted confidence components, ranking-rationale bullets, expandable `analysis.ranking_method`.
- "Pivots and notes" card with notes + pivot `<table>` (Date / Type / Price).

**Projected completion zone.** Rendered two ways:

1. As dashed `PriceLine`s on the chart at `low`/`high` from `count.projection`, with `axisLabelVisible: true` and title "Projected zone high/low".
2. Textually inside `CountSummary` as `Projected completion zone`: `<low> – <high>`, a `basis` line from the backend, and the separating caveat: "Elliott Wave analytical projection; not part of the Momentum25 score or ranking."

When `!count.is_current`, an amber sentence: "This structure ended before the latest confirmed pivot, so no completion zone is projected."

**Separation verified.** `elliott-wave/page.tsx`, `components/stock/useElliottWaveChart.ts`, `components/stock/elliott-wave-panels.tsx` import no momentum-score / composite-score / overall_passed / hard_filter_failures. The only cross-link to the analysis screen is the "Full ranking panel and pivot table →" link (analysis page → elliott-wave page) and `SymbolActionBar`.

**What works.**

- Clean separation, no leakage into scoring.
- Disclaimers are present and unambiguous.
- Threshold and degree-path state link the panels and the chart.
- Pivot table, fibonacci relationships, personality evidence all explicit.
- Projected completion zone preserved with the caveat.
- Cross-link from analysis to the full Elliott Wave page.

**Problems.**

- The page repeats the live/overview/engines analysis blocks lifted from the detail page when rendered inside the analysis route's `elliott` mode — duplication cost.
- No `aria-live` region for `selectCount` / `setDegreePath` transitions.
- The threshold slider has no `aria-valuetext` describing the units, just a numeric readout.
- The wave-label buttons are `aria-pressed` but the chart annotation does not update a live region — a screen-reader user does not know which wave was selected.
- No keyboard way to inspect the chart markers; the labels in the chart canvas are not in DOM order.

**Severity.** PASS.

**Recommendation.** Preserve as a separate first-class screen. Keep the projected wave path and the projected completion zone. Small refinements: live region for selected wave, `aria-valuetext` for the threshold slider, `aria-pressed` on wave buttons (already present). Do NOT recommend removing the projected completion zone — it is an intentional Elliott Wave analytical projection.

### 5.6 Market `/market`

**Current state.** `market/page.tsx` (50 lines) + `components/market/MarketBreadthPanel.tsx` (90) + `components/market/SectorStrengthTable.tsx` (161). Header subtitles adapt to data ("`breadth.as_of`"). Only research-tier page matching the primary palette (`bg-slate-50 dark:bg-slate-950`).

- `MarketBreadthPanel`: two big-number + progress-bar rows (% of universe above 50- and 200-day average), with "X of Y measurable" denominators. Three `MetricCard`s underneath (new highs, new lows, measurable-for). Footer copy explains "a new 52-week high means the latest close is the highest of the trailing 252 sessions" and "Descriptive context for the market as a whole — not a signal for any individual stock, and not an input to the ranking."
- `SectorStrengthTable`: equal-weighted mean excess return per sector, client-side sortable, `aria-pressed` on sort pills (the only `aria-pressed` usage in research pages). Empty-case `UNAVAILABLE_COPY` distinguishes `no_sector_classification` from `no_benchmark_history` (referencing the 2026-08-09 audit §1.2.8 sector-null finding).

**What works.**

- Investor-grade language. % above 50-/200-day, new highs/lows.
- Honest footnotes. Equal-weighting caveat ("platform ingests no market-cap data").
- `aria-pressed` on sort pills — best in show across research pages.
- Distinct empty-case copy for the two unavailability reasons.

**Problems.**

- Sectors panel is empty until sector classification is ingested (no free NSE source). The page defaults to one card with one empty card. The empty copy handles it gracefully, but the page reads as a one-card screen in practice.
- Sector table headers lack `scope="col"`.
- Sort pills are `aria-pressed` but the active-state class (`bg-indigo-100 …`) lacks `aria-current`.

**Severity.** PASS.

**Recommendation.** Promote to top-level navigation directly (not under Research Tools). Add `scope="col"` to headers. Consider adding a "Top 10 / Bottom 10 stocks" panel for breadth leadership.

### 5.7 Strategies `/strategies` and Analytics `/analytics`

**Current state.** `strategies/page.tsx` (341) and `analytics/page.tsx` (331). Both call the same two endpoints (`evaluateStrategy`, `getContributionAnalysis`). Both surface identical disclaimer copy about Sharpe-/Sortino-/profit-factor-shaped metrics that "carry no profit or return meaning":

- **`/strategies`**: strategy chips, 12-MetricCard grid (Score mean/stability/volatility/gain-loss/downside/max drawdown/recovery/risk-adjusted/etc.), Recent Runs table, Contribution Analysis (BarChart + Top Rules + Redundant Rules + Least Impactful Rules), Strategy Comparison table.
- **`/analytics`**: same 12 metrics inside `StatBox`es, then 7 chart cards: Screening Frequency (Bar), Run Status Distribution (Pie), Pass Rate Over Time (Line), Engine Contribution Share (Pie), Rule Pass Rates (horizontal Bar), Score Statistics and Ranking Stability (text cards).

`/strategies` and `/analytics` both hardcode `selectedStrategy` in local `useState` and ignore `useStrategy()`. `/analytics` destructures away the setter (`:13`) — dead state. `/analytics` subtitle advertises "win rates, drawdowns" — neither is shown.

Both use the off-palette wrapper `bg-white dark:bg-slate-900`. Neither surfaces errors (`/strategies` imports `ErrorMessage` but never uses it; `/analytics` imports `Badge` / `ErrorMessage` unused).

**What works.**

- `/strategies` Contribution Analysis is the most useful "is my strategy any good?" view in the app.
- `/analytics` charts render cleanly; PieCells and Bars use `chartColorList`.
- Consistent `h-64` chart heights.

**Problems.**

- Redundant. Two routes, same data, different presentation. Verbatim duplicate disclaimer copy.
- `strategies/page.tsx:7` imports `Badge` and `ErrorMessage` but never uses them (dead imports).
- `analytics/page.tsx:6` imports `Badge` and `StatusDot` but never uses them.
- `StatBox` class string `dark:bg-slate-900/50 dark:bg-slate-700/40` (`:300`) — second dark bg shadows the first; dead Tailwind text.
- No error UI on either page — failed fetches silently show nothing.
- No `aria-pressed` on strategy chips. No `aria-label`s on the 12-metric grid.
- Subtitle on `/analytics` overclaims.

**Severity.** NEEDS IMPROVEMENT.

**Recommendation.** Merge `/analytics` charts into a "Charts" tab on `/strategies`; retire `/analytics` as a top-level destination. Read `useStrategy()`. Surface errors with `ErrorMessage`. Drop dead imports.

### 5.8 Validation "Research" `/validation`

**Current state.** `validation/page.tsx` (496). Largest research page. Calls `getResearchDashboard` (single POST). Header carries a strategy `<select>` (one hardcoded option) and a window-years select (1/3/5/10), Refresh button.

Sub-components (all inline, no `components/research/` library despite the umbrella): `MeasurabilityNotice`, local `MetricCard` (`good/bad: boolean` API, shadows the shared one), `ScorecardSection`, `MetricGroup`, `AlphaSection`, `RulesSection`, `EnginesSection`, `ValidationSection`, `QualityMetric`, `QualityMetrics`.

Imports `getStrategyScorecard, getAlphaAnalysis, getRuleEffectiveness, getEngineEffectiveness, getHistoricalValidation, runParameterExperiment` (`:5-13`) — none called (dead imports); only `getResearchDashboard` is used.

Default state (no forward returns ingested): the entire Return/Win-Loss/Risk/Risk-Adjusted/Market-Relative grid shows `—`, an amber `MeasurabilityNotice` explains why, and the top `QualityMetrics` strip is the only panel that renders real numbers (Stability/FPR/FNR). Sparse in practice.

No charts on a page labelled "Alpha Research" — purely tabular.

**What works.**

- `MeasurabilityNotice` is the most carefully designed empty state in the app. Sections early-return `null` rather than render fake numbers (prior audit S6: "withhold, not zero-fill").
- Genuine `<h4>` sub-headings — the only research page with a real heading hierarchy below `h1`.
- 2/3/4/6 responsive metric grid.
- Most metric grids step `2 → 3 → 4 → 6` by breakpoint — the most responsive grid logic.

**Problems.**

- Vocabulary-dense: "Calmar", "Sortino", "Information Ratio", "R-Squared", "False Positive Rate", "Drawdown Duration", "Profit Factor". No inline glossary. `/learn` defines them separately.
- Default state reads as a wall of dashes with one amber notice — sparse.
- Strategy select has one hardcoded option — vestigial control.
- Local `MetricCard` shadows the shared `MetricCard` (different API and size). Readability and maintenance hazard.
- No empty state inside sections when data exists but a section is null (silently disappears).
- No `aria-live` for the "Running…" → "Scorecard ready" Refresh transition.
- `aria-busy` absent throughout.

**Severity.** NEEDS IMPROVEMENT.

**Recommendation.** Rename label `Research → Validation` (avoid collision with the umbrella). Inline-glossary tooltips on the metric labels. Render `EmptyState` inside sections that early-return `null`. Retire the local `MetricCard`. Drop dead imports.

### 5.9 Historical Replay `/historical`

**Current state.** `historical/page.tsx` (164). Date `<input type="date">`, existing-run `<select>`, Replay button. Replay result grid (Run ID, Evaluated, Passed). Card listing available historical runs as date tiles. Rankings rendered through the shared `MomentumTable`.

Off-palette wrapper. Replay error rendered as a bare `<div class="text-rose-600">` (`:112`) — not `ErrorMessage`. `runsData` has no error UI. `runsLoading` captured but never surfaced.

Labels on `<input>` lack `htmlFor`/`id` association.

Date tiles are real `<button type="button">` but no `aria-pressed`.

**What works.**

- Repurposes `MomentumTable` so the replay result has the same sort/filter/pagination.
- Date tiles fix one of the few places the app reveals a run history.

**Problems.**

- "Replay Controls" and "Available Historical Runs" both express "pick a date" twice.
- Error handling inconsistent (raw div).
- No empty state when the replay result is empty.
- Researcher-grade audience ("what would the screener have said on date X").

**Severity.** NEEDS IMPROVEMENT.

**Recommendation.** Consolidate the two date selectors into one. Use shared `ErrorMessage`. Surface `runsLoading` with a spinner on the dropdown. Add `aria-pressed` to date tiles.

### 5.10 Experiment Lab `/experiment`

**Current state.** `experiment/page.tsx` (258). Base strategy select, run-dates input (comma-separated ISO dates), dynamic parameter-overrides list with +/- buttons, Run button. 4 MetricCards including "Verdict: BETTER/WORSE". One BarChart comparing base momentum vs variant momentum. Per-date results table.

Inputs expect raw config paths (`engines.trend_template.weight`) and values (`1.5`). The remove-override icon button is the only properly-labelled icon button across the research pages (`aria-label="Remove override"` `:146`).

No `LoadingSpinner` during a run. Button shows "Running Experiment…" but no spinner, no `aria-busy`, no result-area placeholder — long runs look frozen.

Labels lack `htmlFor`/`id` association.

**What works.**

- Most accessible icon button in the research tier (`aria-label`).
- Real `ErrorMessage` rendered.

**Problems.**

- Developer-grade: config-string contract, ISO date strings, bare "BETTER/WORSE" verdict without confidence bands.
- No explanatory copy. An investor cannot use this page.
- Long runs look frozen.
- Placeholder text exposes the YAML path (`engines.trend_template.weight`) — the platform's internal schema leaks through.

**Severity.** MAJOR REDESIGN (for investor exposure) / NEEDS IMPROVEMENT (as a researcher tool).

**Recommendation.** Keep as a researcher/developer tool. Hide from the investor-facing navigation (move behind `/validation` or label clearly as a tuning surface). Add spinner + `aria-busy` during runs; add `aria-live` for the verdict transition; add input validation (reject non-ISO dates, reject unknown config paths) before submit.

### 5.11 Learn hub `/learn` and children

**Current state.** `learn/layout.tsx` (99) renders a left sidebar (`lg:w-56`, `sticky top-20`) with 7 sections: Overview, Momentum Investing, Minervini Methodology, Momentum25 Methodology, Scoring Guide, Rule Guide, FAQ. Mobile collapses into a bordered dropdown (`aria-expanded`, `aria-label="Toggle learning sections"`).

Inner pages use `MethodologyNote` (`components/learn/MethodologyNote.tsx`) to tag content as published / approximation / implementation choice. `SectionHeading` (`h2`), `SubHeading` (`h3`), `Prose` define the only reading-mode rhythm in the app (`text-sm leading-relaxed space-y-3`).

Page chrome uses `bg-white dark:bg-slate-900` — different from the dashboard's `bg-slate-50 dark:bg-slate-950`. Navigating from the dashboard to Learn repaints the background tone.

**What works.**

- The only place that distinguishes "what Minervini published" from "what Momentum25 implemented".
- Real heading hierarchy (`h1` `h2` `h3`).
- Mobile toggle has good ARIA.

**Problems.**

- Hidden inside the Research Tools dropdown — Learn is the onboarding surface; it should be at investor level.
- Chrome discontinuity vs primary surfaces.
- Sidebar has no `aria-current` on active links (only `font-medium` styling).

**Severity.** PASS (with gaps).

**Recommendation.** Promote to top-level navigation. Match the primary palette. Add `aria-current="page"` on active sidebar links.

---

## 6. Stock Detail Redesign Recommendation

### Current order (top-down)

1. Overview (gauges + matrix + 8 cards + executive summary + thesis)
2. Chart
3. Trend Template gate
4. Historical Scores chart
5. Engines
6. Rules (strengths/weaknesses + complete rule table)
7. Historical Rankings chart
8. Live Analysis (price header, workbench, volume, stop, RS-vs-index, patterns, WhyItRanks)

### Recommended order (top-down)

The audit brief lists six questions in order: what is happening → how strong → why it ranks → what supports → downside risk → deeper research. The page should answer them in that order.

1. **Header strip** (one row, always visible)
   - Symbol + name + sector
   - Price + daily change + 52-week range (the `MomentumOverview` top row, lifted here)
   - Rank + percentile (the `MetricCard`s)
   - Investment-readiness badge + run id
   - `StrategySelector` (in-page, read from `useStrategy()`)
   - `WatchlistStar` and `SymbolActionBar` (today's labels)

2. **Why it ranks** (front-loaded)
   - `WhyItRanks` two-card grid (top passing / top failing, gates first). This is the single clearest answer to the audit brief's third question.
   - Executive Summary + Momentum Thesis directly below.

3. **How strong** (single block)
   - Two `ScoreGauge` (Momentum, Buy Setup).
   - `RulePassMatrix` heatmap with the legend.
   - 4 `MetricCard`s only: Momentum Score, Buy Setup Score, Composite Score, RS Rating. (Drop Rank, Percentile, Hard Filters, Suggested Stop from this grid — they belong to §1 strip or §5 risk block.)
   - Engine contributions (`EngineContributionBars`).

4. **Chart** (the largest surface)
   - `PriceChart` with the existing timeframe selector, candles/line toggle, MAs, indicator panes, drawing tools.
   - Historical rank-over-time and historical score `LineChart`s as **overlays or a toggle inside the chart Card** — not separate scroll sections. Use the existing recharts instances but bind them to chart sub-tabs (Price / Rank / Score).

5. **What supports the assessment**
   - `TrendTemplateCard` (with `IMPROVEMENT_HINTS`).
   - `TechnicalWorkbench` indicator groups.
   - `VolumeAccumulation`.
   - `RelativeStrengthVsIndex` 4-row table.
   - `PatternCard` + the optional chart-patterns detection.
   - Complete Rule Evaluation table (every rule with `StatusDot`, actual, threshold, contribution).
   - Strengths / Weaknesses cards (move above the Complete Table for the fast read).

6. **Downside risk**
   - `SuggestedStop` risk-only card (fixed + chandelier stops, with the method badge and distance). No targets, no R:R on this surface. Risk-only contract preserved.
   - Disclaimer footer exactly as today.

7. **Deeper research** (the only place that reaches beyond the core)
   - `SymbolActionBar` end-state: Analysis, Elliott Wave, Patterns.
   - The Analysis page keeps its "Targets and risk / reward" card **but reframed** to not present the EW projection zone as a Momentum25 target and not derive R:R from the risk-only stop on the same surface (see §16).
   - The Elliott Wave screen stays separate (see §10).

### Principle

Order answers the six questions in order. The detail page becomes a dense single screen with section anchors, not a long scroll. Price is the first thing the investor sees. Rank is the first thing he compares. "Why it ranks" is front-loaded. The risk card is unmistakably risk-only. Deeper research sits last.

This matches the prior audit's promotion recommendation: the analysis screen and the detail screen share the same dozen components; unifying the order makes either route a safe entry point for an investor.

---

## 7. Screener Redesign Recommendation

### Keep

- `RunSummaryCards` 4-up.
- `MomentumTable` react-table v8 with sort, filter, pagination.
- `StrategySelector` self-healing selection.
- `StalenessBanner` calendar-aware.
- 60-second auto-refresh on `latest-run`, `rankings`, `data-freshness`.

### Change

1. **Default sort arrow visible.** Set initial `sorting` to `[{ id: 'rank', asc: true }]` so the Rank header carries an arrow from the first render. Today `sorting: []` reads as "not sorted".
2. **Add price + daily change columns (default on).** The data already exists in `/live`. An investor expecting a "stock list with prices" finds none.
3. **Drop "Duration" from `RunSummaryCards`.** Engineer metric, not investor. Replace with "Average RS Rating of qualified set" or a "Top RS Rating" figure.
4. **Re-evaluate the "Signal score" overlay's prominence.** It runs per-row `getOhlcv` calls and is off-by-default. Keep, but move the toggle into a "Columns" menu rather than a header-link checkbox.
5. **Add a "Columns" menu** to `MomentumTable` so investors can hide columns they do not want (Trend, Risk, Volume, Breakout, Pattern, Δ Rank, Rules popover). Today all 13 columns are always present and the table scrolls sideways on mobile.
6. **Add a row count summary** ("Showing 25 of N qualified") consistently above the table.

### Do not change

- Methodology, ranking, gates, column sources from the `/rankings/runs/{id}` endpoint.

### Density

Screener density is good for desktop. On mobile, the table scrolls horizontally with no columns hidden. A 13-column horizontal scroll on a phone is not usable. Two options:

- Card transform: render rows as cards on `< sm` with symbol + rank + momentum + daily change, and a "details" expander for the rest.
- Smart column set: hide non-essential columns on `< sm` (pattern, breakout, Δ rank, rules popover), keep symbol + rank + momentum + RS + trend + change + price.

Recommend the smart column set — it preserves the table paradigm and avoids a parallel card layout to maintain.

---

## 8. Watchlist Redesign Recommendation

The watchlist is small and tracked. It should beat the screener on scannability, not match it. Today it falls short of both.

### Add

1. **Column sort.** Rank, Rank Δ, Change, Below 52w high, Momentum. Today the table is a static grid.
2. **Search.** Filter by symbol — useful for a 20+ watchlist.
3. **In-page `StrategySelector`.** Today the strategy is sticky from the dashboard; switching requires leaving the page.
4. **`Evidence` status column.** Consolidate `live` / `not qualified` / `—` into one column with a coloured dot + tooltip (the precision is already there; consolidate visually).
5. **60-second `refetchInterval`.** Match the dashboard.
6. **Empty-row distinction.** For symbols in the latest run that failed a gate, show the failing-rule badge directly in the row (top failing rule), not only in a tooltip.
7. **Comparison row.** A bottom "Average" row showing the mean momentum, mean RS, mean change — lets a user gauge the list at a glance.

### Change

1. **Error → `ErrorMessage`.** Today's error renders as `EmptyState`, no retry, no error specificity.
2. **`scope="col"` on `<th>`s** to match the dashboard.
3. **Mobile: hide Remove into a row long-press / trailing action menu** so it is reachable but does not consume a column on narrow screens.
4. **Star toggle in-row.** Allow quick-removal by tapping the same star that added the symbol (parity with the stock page).

### Do not change

- The single server call `getWatchlistDetail`. No per-row fan-out.
- The risk-only scope of the data presented.
- The "Tracked symbols · <strategy>" PageHeader subtitle.

---

## 9. Chart Experience Recommendation

`PriceChart.tsx` (981 lines, lightweight-charts v5) is the most complete chart in the app. It supports candles/line toggle, MAs (10/20/50/100/200), indicator panes (RSI / MACD / ADX), Elliott Wave markers and overlay polylines, pattern overlays, projection zones, drawing tools, crosshair OHLC readout, drawing persistence in `localStorage`, visible-range sync.

### What works

- One persistent chart instance per symbol. `useChartShell` shares the chart state across routes (prior audit fix).
- Sub-pane stretch factor `3:1:1` (price gets 3× weight).
- Drawing tools: trendline / horizontal / rectangle / fibonacci with `localStorage` persistence.
- Timeframe presets 1W/1M/3M/6M/1Y/MAX.
- Theme-aware candles (up #10b981 / down #ef4444), MA colours `[#f59e0b, #10b981, #6366f1, #ec4899, #94a3b8]`.

### Problems

1. **No keyboard interaction.** lightweight-charts canvas is opaque to screen readers. The crosshair OHLC readout is `pointer-events-none` (`PriceChart.tsx:957`), so keyboard-only users get no readout.
2. **No legend on the chart.** Active MAs are checkboxes in the toolbar but the chart shows lines without on-chart labels (a user cannot tell indigo from pink at a glance without the toolbar visible). Pane indicators have `lastValueVisible: false` and live only in the crosshair readout.
3. **Chart size fixed per route.** Detail page chart default `height={380}`; analysis page `height={560}`; elliott-wave page `height={620}`. No user resize.
4. **No pan beyond `visibleRange` once it is set** by selecting a wave in Elliott Wave mode. The "Show full range" button is the only escape.
5. **No compare/overlay of another instrument** (index or peer) on the same price pane, despite `getIndexCloses` being available for the analysis rail.
6. **Mobile interaction.** The toolbar wraps (`flex flex-wrap`). The chart container auto-resizes via `ResizeObserver`. No pinch-zoom, no double-tap reset, no horizontal scrub.
7. **Crosshair readout disappears on touch.** No touch-friendly fallback.
8. **No volume pane.** Volume is computed as a separate `VolumeAccumulation` block off-chart, despite the data being in the bars.
9. **Default timeframe 1Y.** The investor's most common ask is "what happened this month"; 1Y is a reasonable default but no recent-bar jump shortcut.
10. **Tooltip is a single readout box at top-right; no anchoring to the crosshair.**

### Recommendations

- **Live legend bar** under the toolbar showing the active MAs as coloured chips with their latest values; highlight on crosshair hover.
- **Volume pane toggle** in the toolbar (volume is already in `bars`); show as a faint histogram in the price pane or a thin sub-pane.
- **Index overlay** (`getIndexCloses`) on the price pane; the data already exists.
- **Keyboard crosshair.** Add arrow-key handlers on the chart container that move a virtual crosshair and announce O/H/L/C through an `aria-live` region.
- **Mobile:** double-tap to reset zoom; long-press to show the crosshair; show latest price/daily change statically when no crosshair is active.
- **Add chart resize affordance**
 (a grab handle) so the investor controls the price pane height.

Do not change the candle/MA/pane colours; they are consistent.

---

## 10. Elliott Wave Screen Recommendation

### Preserve

- **Separate route.** `/stock/[symbol]/elliott-wave` must stay a distinct first-class research screen, reachable only via `SymbolActionBar` and the cross-link from analysis. It must NOT join the core Momentum25 detail page.
- **Wave analysis.** Threshold slider, competing counts, degree breadcrumb, `WaveDetail` (personality corroboration + fibonacci relationships), pivot table.
- **Projected wave path.** The `overlayLine` solid polyline through each labelled pivot, with dashed finer-degree subdivisions.
- **Projected completion zone.** The dashed `PriceLine`s on the chart + the textual "Projected completion zone" block inside `CountSummary`, with the explicit caveat "Elliott Wave analytical projection; not part of the Momentum25 score or ranking."
- **The `is_current` amber sentence** when the structure has ended.
- **The standing caption** "Chart annotation only — this view produces no buy/sell verdict and no score."
- **The labelling-confidence ranking panel** framed as fit-to-theory, not profitability.

### Refinements (do not change methodology)

1. **Sep} Keep the projected completion zone visibly distinct from any price-target framing on the chart and in the panel. The "Projected zone high/low" axis labels on the chart already do this; the panel caveat should remain exactly as worded.
2. **Make the analysis-page `elliott` mode a true subset of this screen.** Today the analysis rail reuses `useElliottWaveChart` and renders a condensed panel; the full pivot table and ranking rationale live only here. Keep that split — the standalone page is the canonical surface, the analysis rail is a quick view.
3. **Do not present the projected completion zone as a Momentum25 target.** On the analysis page, remove (or visually separate) the "EW zone low/mid/high" entry from the "Targets and risk / reward" card so the EW projection is clearly analytical, not a value target derived from the stop (see §16).
4. **Cross-link parity.** Both directions should carry a clear label: from analysis → "Full ranking panel and pivot table →"; from the standalone page → "Back to analysis ←" (today it says "← Back to research"). Match the wording.
5. **Accessibility.** Add an `aria-live` region for `selectCount` / `setDegreePath` transitions. Add `aria-valuetext` on the threshold slider. The wave-label buttons are already `aria-pressed`. Add a `role="table"` is not required (native `<table>` is fine), but add `scope="col"` to the pivot-table headers.

### Do not remove

The projected completion zone is an intentional forward-looking Elliott Wave analytical projection. Do not remove it. Do not collapse it into a "current price" read. Do not present it as a Momentum25 score input. The existing separation is correct; this audit validates it.

---

## 11. Mobile UX Recommendation

### Current state

- Single top bar (h-14, sticky). Hamburger toggles an inline collapsible drawer that **pushes page content down** (`NavBar.tsx:410-425`). Not a slide-over, not a bottom nav. Contains `SymbolSearch` + 2 primary links + a divider + 7 flat research links.
- `SymbolSearch` is `hidden sm:block` in the bar — invisible on mobile unless the drawer opens.
- Tables (`MomentumTable`, `WatchlistTable`, `SectorStrengthTable`, research tables) all wrap in `overflow-x-auto`. No columns hidden on any breakpoint.
- Stock detail `SectionNav` is `sticky top-[4.5rem]` — calibrated to the NavBar. On mobile, the section tabs horizontal-scroll (`overflow-x-auto no-scrollbar`), so users cannot see all 8 sections at once.
- Charts: chart toolbar wraps (`flex flex-wrap`). Sub-panes stack at fixed 3:1:1.
- No bottom navigation. No `safe-area-inset` handling. No touch-specific gestures beyond native scroll.

### Concrete problems

1. **Hamburger drawer pushes content.** A scroll-memory hazard: opening the drawer shifts the page; closing shifts back. Users lose their scroll position.
2. **Symbol search hidden on mobile** until the drawer opens. An investor's primary cross-stock navigation is search; on mobile it is two taps away.
3. **13-column table horizontal-scroll** with the remove/relevant columns off-screen to the right.
4. **Stock detail 8-section scroll-spy** collapses to a horizontal strip; the active section indicator (`aria-current`-driven styling) is the only hint of position.
5. **No bottom nav.** An investor on a phone has no quick Dashboard / Watchlist / Market switch.
6. **Card padding does not shrink on mobile.** `max-w-7xl mx-auto px-4 …` is the only horizontal padding; cards keep `p-4`.
7. **No touch-friendly crosshair** on the chart.
8. **`PageHeader` actions stack `flex-col sm:flex-row`** — fine, but the actions cluster on dashboards (Strategy selector + run badge + Refresh button) can wrap onto 3-4 lines on a 360px screen.

### Recommended mobile information hierarchy

```
Bottom nav (3 destinations, icon + label)
  Dashboard        Watchlist         Market
(Floating action) search (opens full-screen sheet)
(Slideover)        more: Learn / Strategies / Validation / Historical / Lab / Analytics
```

1. **Bottom nav** for the three investor destinations. Eliminates the inline drawer's content-shift.
2. **Search as a floating action** (bottom-right) opening a full-screen typeahead sheet. Restores mobile search parity with desktop.
3. **Slide-over "More" drawer** (right edge) holding the 5 researcher destinations + Learn. Never pushes content.
4. **Table column hiding** on `< sm`: keep Symbol + Rank + Momentum + Change + Close on `MomentumTable`; hide Risk / Volume / Breakout / Pattern / Δ Rank / Rules popover behind a "more" expander icon.
5. **Card padding `p-3` on `< sm`** to recover screen real estate.
6. **Stock detail becomes tabbed:** replace the scroll-spy with a real `<Tab>` strip showing 5 tabs (Why / Strength / Chart / Supports / Risk) — never all 8 — and convert the long scroll to a tabbed navigation. Keep all content reachable, two taps at most.
7. **Touch crosshair on the chart:** long-press shows the OHLC readout anchored to the finger; release hides it.
8. **`safe-area-inset-bottom`** padding on the bottom nav so it does not collide with phone gestures.

### Do not remove

Any desktop feature. Hide or relocate, do not delete.

---

## 12. Accessibility Findings

### Shared atoms (highest impact — fix once, fix everywhere)

| Atom | File | Gap | Fix |
|---|---|---|---|
| `StatusDot` | `Card.tsx:95` | No `role="img"` / `aria-label`. Pass/fail invisible to SR. | `role="img" aria-label={passed ? "Passed" : "Failed"}`. (Used in `MomentumView`, `WhyItRanks`, `RulePassMatrix`, `TrendTemplateCard`, `PatternCard`.) |
| `LoadingSpinner` | `Card.tsx:105` | No `role="status"`, no `aria-live`. | `role="status" aria-live="polite"` on the wrapper. |
| `ErrorMessage` | `Card.tsx:114` | No `role="alert"`, no `aria-live`. Decorative SVG not `aria-hidden`. | `role="alert" aria-live="assertive"`; `aria-hidden="true"` on the SVG. |
| `EmptyState` | `Card.tsx:131` | No `aria-live` region. Decorative SVG not `aria-hidden`. | `role="status"`; `aria-hidden="true"` on the SVG. |
| `ScoreGauge` | `ScoreGauge.tsx:7` | No `role="meter"` / `aria-valuenow/min/max`. | `role="meter" aria-valuenow aria-valuemin={0} aria-valuemax={100} aria-label={label}`. |
| `PageHeader` subtitle | `Card.tsx:148` | `text-slate-500` no `dark:` variant. | Add `dark:text-slate-400`. |
| `LoadingSpinner` caption | `Card.tsx:109` | No `dark:` variant. | Add `dark:text-slate-400`. |
| `ScoreGauge` caption | `ScoreGauge.tsx:52` | No `dark:` variant. | Add `dark:text-slate-400`. |
| `Card.badge` prop | `Card.tsx:13` | Raw class string. Callers pass dark-only pairs → light-mode regression. | Use the `Badge` `colorMap` or accept a `color` enum. |

### Navigation

| Element | File | Gap | Fix |
|---|---|---|---|
| `NavBar` `NavLink` | `NavBar.tsx:280` | Active links lack `aria-current="page"`. | Set `aria-current={isActive ? 'page' : undefined}`. |
| `ResearchToolsMenu` | `NavBar.tsx:311` | No keyboard arrow navigation; no Escape handler (only `onBlur`). | Add Arrow / Home / End / Escape handlers; match `FloatingPanel`. |
| `ThemeToggle` | `NavBar.tsx:111` | Good: `aria-label`, `aria-pressed`. | Keep. |
| `SymbolSearch` | `NavBar.tsx:141` | Good: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-autocomplete`, keyboard arrows, Escape, Enter. | Keep. |
| Mobile drawer | `NavBar.tsx:410` | Hamburger has `aria-expanded` and `aria-label` (good). Drawer lacks `role="dialog"` / focus trap. | Add `role="dialog" aria-label="Navigation menu"`; trap focus while open. |
| Learn sidebar | `learn/layout.tsx:78` | Active link lacks `aria-current`. | Set `aria-current="page"`. |
| `SectionNav` | `stock/[symbol]/page.tsx:55-152` | `aria-current` set (good). `top-[4.5rem]` magic number brittle. | Replace with `top-14` (matches `h-14` NavBar). |

### Tables

- `MomentumTable` (good): `scope="col"`, `aria-sort`, `tabIndex`, Enter/Space, `aria-label`s on icon-only pagination and `ChecklistPopover` trigger. Search input lacks an associated `<label>` (placeholder only).
- `WatchlistTable` (gap): `<th>`s lack `scope="col"`. Sortable icons/links are fine; symbol `Link` has `${focusRing}`.
- `SectorStrengthTable` (gap): `<th>`s lack `scope`. Sort pills have `aria-pressed` (good).
- Research-page tables: `<th>`s lack `scope`. No `aria-sort`.

### Charts

- `PriceChart` and recharts gauges are opaque to SR. No `role="img"` + `aria-label`. The crosshair readout is `pointer-events-none` and not keyboard accessible.
- `ScoreGauge` lacks `role="meter"`.
- Charts should carry a textual summary region (`aria-live`) for keyboard users.

### Buttons / chips / tiles

- `aria-pressed` is missing on strategy chips, date tiles, chart timeframe buttons (segmented controls use plain `aria-pressed`, which is correct — confirm elsewhere). The only research-tier `aria-pressed` usage is `SectorStrengthTable:102`.
- Icon-only buttons: `WatchlistTable` Remove and `experiment/page.tsx:146` have `aria-label`. Other icon-only toggles (chart toolbar buttons) — verify; `PriceChart.tsx:208-212` `ToggleButton` uses `aria-pressed` (good).

### Forms

- `historical/page.tsx`, `strategies/page.tsx`, `experiment/page.tsx`, `learn/page.tsx` all use `<label>` without `htmlFor`/`id` association. The screen-reader pairing is lost.

### Status indicators

- Badges (`Badge`) render inside `Card` headings; their meaning is contextual (Run #, qualification, verdict). The badge text is plain text, SR-readable. Good.
- `live` / `not qualified` pill distinction in `WatchlistTable` (`:50-86`) — both have `title` tooltips but no `aria-label`. Add `aria-label` so the meaning reaches SR without hovering.
- `StatusDot` (above).

### Color contrast

- Primary chrome (slate-50/slate-950, slate-900/slate-100) and the indigo `bg-indigo-600 text-white` button meet WCAG AA.
- `PageHeader.subtitle` is `text-slate-500` on `bg-slate-50` (light) and on `dark:bg-slate-950` (dark) — the dark variant fails without the `dark:` suffix; once fixed, contrast is fine.
- `text-slate-400 dark:text-slate-500` captions on small print hover near the AA threshold; verify with a contrast check on `text-[10px]` and `text-[11px]` usages.

### Status

- **Keyboard navigation: NEEDS IMPROVEMENT.** Sortable headers reachable (good); dropdown menu keyboard incomplete; chart canvas not keyboard-operable; drawer lacks focus trap.
- **Focus states: PASS.** Every interactive element uses `${focusRing}`.
- **Semantics: NEEDS IMPROVEMENT.** `StatusDot`, `ScoreGauge`, `LoadingSpinner`, `ErrorMessage` lack roles. Tables mostly fine on dashboard, weak elsewhere.
- **Color contrast: NEEDS IMPROVEMENT.** Several missing `dark:` variants and a couple of low-contrast captions to verify.
- **Screen-reader semantics: NEEDS IMPROVEMENT.** Charts and `StatusDot`s opaque.

---

## 13. Performance UX Findings

### Endpoint performance (per the 2026-08-15 functional audit)

- `/stocks/{symbol}/live` cold: 9.37s, warm 0.024s after the F2 Redis RS cache (`backend/.../use_cases/stocks.py:16,533-534`). UX impact: first load of any stock detail is slow; subsequent visits are instant while the cache holds.
- `/research/compare/runs` and `/compare/strategies` previously crashed (F7); fixed in `81220db`. UX impact: the comparison panels were dead; they now return 200.
- `/validation/dashboard` previously 44s; F3 bulk fetch fixes bring it to 6.1s. Still long for a dashboard refresh; do not auto-refresh.
- `/market/context` 1.54s; F14 index `ix_ohlcv_daily_date` (migration `0013`, committed but not applied at audit time) reduces it further. UX impact: market page loads slower than an investor expects for breadth.
- Score-history duplicates (F5) fixed with `DISTINCT ON (run_date)`. UX impact: the historical score/rank charts previously spiked with duplicates; clean now.

### Perceived performance

- **No skeletons.** Every loader is a centred spinner. The stock detail waits for three queries (live, explanation, history) before any UI lands. A skeleton with the page chrome + section headers in place would halve perceived load time.
- **No progressive loading.** `MomentumTable` does not show row placeholders during a sort/filter; the whole table blinks out into a spinner and back.
- **`refetchOnWindowFocus`** defaults to `true` (React Query default). On refocus, dashboard rankings refetch; if the user was mid-page-down, the page shifts when new data arrives. Consider `refetchOnWindowFocus: false` globally, or `keepPreviousData: true` on filter changes.
- **Auto-refresh jank.** Dashboard auto-refreshes `latest-run`, `rankings`, `data-freshness` every 60s. Each refetch can re-render the ranked table with different ordering if the run changed; no animation or `keepPreviousData` so the rows jump. Set `keepPreviousData: true` on `rankings` and on `watchlist-detail`.
- **`StalenessBanner` appears/disappears.** When `FRESH → STALE` during a session the banner inserts a new row, shifting the table down. Render the banner container unconditionally with `aria-live`, then toggle visibility.
- **No layout shift on chart mount.** `PriceChart` has fixed `height` props (380/560/620) — good. Minor shift when `prefsReady` flips (chart appears after `localStorage` prefs validate).
- **Cross-route state preserved through `useChartShell`** — chart preferences, drawings, indicators all persist across `/stock/[symbol]`, `/analysis`, `/elliott-wave`. A user navigating the symbol's trio does not lose their chart state. Good.
- **Watchlist no `refetchInterval`.** A stale watchlist can carry an old price for an entire session. Add a 60s refetch.

### Large tables

- `MomentumTable` paginates (default 25). Good.
- `SectorStrengthTable` is small.
- Research tables are small.
- No virtualization. Fine; the row counts are bounded.

### Slow sections

- `/validation` dashboard refresh takes 6+ seconds. Show a non-blocking progress indicator and allow the rest of the page to remain interactive; today the entire page is gated on the single POST.
- `MomentumTable` "Signal score" overlay fires per visible row `getOhlcv` calls. StaleTime 5 min. Acceptable; each row's chart-key `['stock-ohlcv', symbol, '1Y']` is reused by the chart, so the network cost is mostly cached.

### Recommendations

1. **Skeletons** for the stock detail loader, the watchlist loader, and the validation dashboard loader.
2. **`keepPreviousData: true`** on `rankings`, `watchlist-detail`, and `MomentumTable` filter/sort transitions.
3. **`refetchOnWindowFocus: false`** or expose a "manual refresh" control on the dashboard `Refresh` button (which already exists).
4. **Watchlist 60s `refetchInterval`** to match the dashboard.
5. **Render the `StalenessBanner` container unconditionally** so visibility toggles do not shift the layout.
6. **Do not auto-refresh `/validation`.** It is already slow; refresh only on action.

### Do not change

- The caching logic on `/live` (F2 fix), the bulk fetch paths (F3), the index plan (F14). They are backend concerns; the UX audit notes their effects only.

---

## 14. Design System Recommendation

### Wire tokens into Tailwind

`lib/theme.ts` should become `tailwind.config.js theme.extend`. Today it is an advisory TypeScript module; components reimplement utilities inline. Specific moves:

- Map `colors.indigo` / `emerald` / `amber` / `rose` / `slate` / `cyan` / `violet` (already Tailwind's default scale) into `theme.extend.colors` if any custom shade is needed; otherwise rely on the default palette.
- Map `chartPalette` and `chartColorList` into `theme.extend.colors.chartPalette` so charts can read `text-chartPalette-success` instead of interpolating string constants.
- Map `typography` into `theme.extend.fontSize` keyed by role (`pageTitle: ['2xl', { lineHeight: …, fontWeight: … }]`, `cardTitle`, `cardValue`, `caption`). Replace inline `text-xl` / `text-sm` literals with `text-pageTitle` / `text-cardTitle`.
- Map `spacing.page` / `spacing.section` / `spacing.cardGrid` into reusable component classes via the `@layer components` block in `globals.css` (e.g. `.container-page { @apply max-w-7xl mx-auto px-4 sm:px-6 lg:px-8; }`).
- Delete the unused `.focus-ring` CSS class in `globals.css:24`; keep the `focusRing` TS export (or migrate it to a Tailwind `theme.extend.boxShadow.focusRing` plus a `focus-ring` class via `@apply`).

### Standardize atoms

- **One `MetricCard`.** Retire the local `MetricCard` in `validation/page.tsx`. Unify the API (`color` string + optional `good`/`bad` shortcut).
- **One `Button`.** Today buttons are written inline. Add a shared `Button` with `variant ∈ {primary, secondary, ghost}` and `size ∈ {sm, md}`. Migrate call sites.
- **One `Tabs` / `Segmented Control`.** Merge `SegmentedControl` and `SectionNav` ancestors into a single component with `aria-pressed`/`aria-current` and keyboard support.
- **One `Table` primitive.** Extract the repeated `<table className="w-full text-sm">` skeleton (header `bg-slate-50 dark:bg-slate-800/90 …`, `<th>` `scope="col"`, rows `divide-y`) into a `DataTable` (or two: `DataTable` for sorted tables, `Table` for static). The validation-rule, experiment-results, and strategies-runs tables would share it.
- **One `Badge` API.** `Card.badge` should accept the `Badge` colour enum (and use `Badge`), not a raw class string.
- **Add `Tooltip`.** Inline readouts (`WatchlistTable` "live", "not qualified", `RankChange` "new", `ChecklistPopover`) today use `title`. Add a shared `Tooltip` with keyboard + SR semantics.

### Typography scale

Define a fixed scale. Suggested (Tailwind `fontSize`):

| Token | Size | Usage |
|---|---|---|
| `pageTitle` | `text-2xl` | PageHeader h1 |
| `sectionTitle` | `text-lg` | Section h2 |
| `cardTitle` | `text-sm font-semibold` | Card h3 |
| `subHeading` | `text-sm font-semibold` | Card or section sub-heading |
| `body` | `text-sm leading-relaxed` | Default body |
| `cardValue` | `text-xl font-bold tabular-nums` | MetricCard value |
| `caption` | `text-xs` | Labels, tooltips |

### Color and dark mode

- Audit every `text-slate-500` for a missing `dark:` variant (PageHeader subtitle, LoadingSpinner caption, ScoreGauge caption are known gaps).
- Standardize semantic success / warning / danger / info tokens at the Tailwind level so `Badge`, `Card.badge`, `ErrorMessage`, `StalenessBanner`, and chart palettes share one source.
- Fix `useChartColors.tick` to be theme-aware (`#64748b` light, `#94a3b8` dark).

### Spacing and rhythm

- One container class. One card padding (`p-4`). One card-grid (`gap-4`). One section rhythm (`space-y-6`). Retire ad-hoc `gap-3` in `validation/page.tsx` and align to `gap-4`.

### Icons

- Keep inline SVGs; they are consistent. Add `aria-hidden="true"` to every decorative SVG (they are missing in `LoadingSpinner`, `ErrorMessage`, `EmptyState`, and chips).

### Charts

- Theme `lightweight-charts` through a shared hook (today `useChartColors` only themes recharts). Add `useLwcTheme()` returning candle colours, MA colours, pane colours, axis tick colours, grid colours.
- Add `role="img"` + `aria-label` (summary) on every chart container.

### Status

Design system status: **NEEDS IMPROVEMENT**. The pieces exist; they are not authoritative.

---

## 15. Product Coherence Findings

The application feels like one product on chrome, but the seams show in the secondary surfaces.

### Inconsistencies

1. **Two page backgrounds.** Investor surfaces use `bg-slate-50 dark:bg-slate-950`; research pages (Historical, Strategies, Lab, Research, Analytics) and the Learn hub use `bg-white dark:bg-slate-900`. The `Card` `dark:bg-slate-800/50` reads on a different tone behind each.
2. **Two `MetricCard`s.** Shared `MetricCard` (`text-xl tabular-nums`, `rounded-xl`) vs `/validation` local `MetricCard` (`text-sm font-mono`, `rounded-lg`).
3. **Two tab idioms.** `SegmentedControl` (analysis page) vs `SectionNav` scroll-spy (detail) vs strategy chips (`/strategies`). Different selected styles.
4. **Two button idioms.** No `Button` primitive; primary and secondary variants repeated with slight class drift across pages.
5. **Two error idioms.** `ErrorMessage` (rose) vs `EmptyState` (used for errors in `WatchlistTable`) vs raw `<div class="text-rose-600">` (`historical/page.tsx:112`) vs silent failure (`/strategies`, `/analytics`).
6. **Two disclaimer copies.** `/strategies` and `/analytics` carry the same Sharpe-/Sortino-/profit-factor-shaped disclaimer verbatim.
7. **Two heading hierarchies.** Most pages jump `h1` → `h3` (no `h2`). `/validation` has `h4` sub-sections. `/learn` is the only place with `h1 → h2 → h3`.
8. **Strategy selection.** Dashboard, watchlist, stock detail read `useStrategy()`. `/strategies` and `/analytics` ignore it and hardcode the strategy in local state.
9. **Elliott Wave candidate colours.** Clamp fix (prior audit I2) applied to analysis; verify the standalone page also clamps (`useElliottWaveChart.ts` clamps via `Math.min(index, …)`).
10. **Crosshair tooltip rendering.** recharts uses `useChartColors`; lightweight-charts reads from a different code path.
11. **Status indicators.** `StatusDot` (shared, emerald / slate) vs `Evidence` (`elliott-wave-panels.tsx`, ✓/✕/– coloured emerald-600 / rose-600 / slate-400) vs `RankChange` (custom `text-emerald-600 dark:text-emerald-400` for gains). Same semantic, three implementations.

### What should become standardized

- Page background: one palette. Pick the investor's `bg-slate-50 dark:bg-slate-950`.
- `MetricCard`: one component, one API.
- Tabs / segmented controls: one component.
- Buttons: one component.
- Tables: one primitive (`DataTable`) with `scope`, `aria-sort`, default sort arrow.
- Error / empty / loading: shared atoms; nothing ad-hoc.
- Disclaimer copy: one place (e.g. on `/strategies`); other pages link to it.
- Heading hierarchy: `h1` → `h2` (Card or section) → `h3` (sub-heading).
- Strategy selection: every page reads `useStrategy()` or does not show a strategy.
- Charts: one theme hook for both library families.
- Status indicators: one shared `StatusDot` with `role="img"`; the `Evidence` semantics map to it.

### Status

- **Product coherence: NEEDS IMPROVEMENT.** No severe dissonance; many small drifts.

---

## 16. Methodology / Research Questions

These are kept separate from UI defects. They ask the product owner to clarify methodology and product-scope decisions. The audit does not recommend changing any of them.

### Q1 — The analysis page "Targets and risk / reward" card

The card (analysis `page.tsx:597-652`) presents four target constructions:

- Elliott Wave projection zone low/mid/high.
- Fibonacci extensions (1.0, 1.272, 1.618, 2.618).
- Pattern measured move.
- ATR objective (`atrMultiple × ATR(14)` above last close).

Each target prints % move from last close and `R:R = (target.price − lastClose) / (lastClose − stop)`, where `stop` is `live?.suggested_stop.level`. The footnote explains the formula. The page-level docstring stresses "nothing on this page feeds the composite score" (true).

Two concerns to surface:

1. **Cross-methodology mix at the UI layer.** CLAUDE.md says: "The Elliott Wave projection must NOT be presented as a Momentum25 target." Listing "EW zone low/mid/high" inside a "Targets" card with a single R:R formula derived from the risk-only stop arguably presents the projection as a Momentum25 value target. The detail page's `SuggestedStop.tsx` is explicitly risk-only; the analysis page derives reward (and an R-multiple) from that same stop. The stop is intended as a risk cap, not a basis for R:R.
2. **Domain mismatch.** Thefibonacciextension and pattern measured-move methodologies overlap with the Elliott Wave methodology but live in different analysis code; the analysis UI presents them together as a unified "targets" list. Users may read them as confirming each other when they are alternative readings.

This is not a UI bug. It is a question for the product owner:

- Should the analysis page surface "targets" at all, given the risk-only stop-loss methodology?
- If yes, should the targets card keep Elliott Wave projection zone separate from price-target constructions, and stop deriving R:R from `suggested_stop.level`?
- Should the title "Targets and risk / reward" be reframed as "Scenario levels and distance-from-stop" so it does not frame the stop as a reward input?

The audit does not specify an answer. The audit specifies that, today, the page is closer to "presentation only" than to "Momentum25 verdict," but the visible framing bends the risk-only contract at the UI layer.

### Q2 — `rank_change` sign convention

`backend/.../use_cases/rankings.py:92` returns `rank - prev_rank` (new − old). `backend/.../use_cases/watchlist.py:176` returns `prev - rank` (old − new). Both front ends render "green = improved" correctly (the dashboard treats `change < 0` as improved; the watchlist treats `change > 0` as improved). The contract is split.

This is a methodology/contract decision, not a UI one. Recommend: pick one sign convention (new − old = negative means improved, matching the Minervini "rank fell" sense on the dashboard) and rename the field on the watchlist endpoint, or document the convention in an ADR. Do not touch the rendering; it is already correct in both.

### Q3 — "Composite Score" vs "Momentum Score" vs "Buy Setup Score"

The stock detail surfaces three scores. No inline definition distinguishes them. The audit does not propose changing the scoring. The product owner should decide whether the investor needs to see all three on the metric strip or only Momentum (the headline) plus Buy Setup (the secondary). Composite could move to the engine contributions block.

### Q4 — "Signal score" overlay on `MomentumTable`

`MomentumTable` exposes an opt-in "Signal score" column computed in-browser from `getOhlcv` per visible row (`signalScore(bars, DEFAULT_PRESET_ID)`). It is explicitly a view-layer construct (`lib/strategies.ts:9-12`: "never touches the screening run, the composite score or the ranking"). Should it remain in the screener table, or move to the per-stock analysis page where the chart already evaluates the same presets? Keeping it in the table adds per-row network load and risks an investor conflating "Signal" (chart construct) with "Momentum" (the methodology score).

### Q5 — `/analytics` overlap with `/strategies`

`/analytics` calls the same two endpoints as `/strategies` and renders the same numbers as charts plus a couple of universe-level charts. Should `/analytics` merge into `/strategies` as a Charts tab? The product owner decides. No UI fix can resolve redundancy that is by design.

### Q6 — `/experiment` investor exposure

`/experiment` exposes raw config paths (`engines.trend_template.weight`) and ISO date strings with no validation. Should this surface remain in the investor-facing app at all, or move behind a developer flag? Today it sits under "Research Tools" alongside `/market` and `/learn`, suggesting parity of audience.

### Q7 — `/validation` strategy select

`/validation` ships a `<select>` with one hardcoded option. Should it list the same strategies `listStrategies()` returns, or be removed until the platform supports more than one strategy? Today it is a vestigial control.

### Q8 — Daily change on the screener

The screener deliberately omits price and daily change. The product owner may want to keep it score-centric. If price and change are added (UI recommendation in §7), confirm the screen does not begin to compete with the watchlist.

---

## 17. Prioritized Recommendations

Each priority uses: Problem · Why it matters · Proposed solution · Affected screens · Priority.

### P0 — Critical usability problem

**P0-1 — Stock detail hierarchy reads bottom-up.**
- Problem: The flagship page answers "why it ranks" last and "what is happening" requires scrolling to section 8.
- Why it matters: Investors see the summary, spend the longest on first impressions. A bottom-up hierarchy loses them.
- Proposed solution: Reorder to the §6 hierarchy (header strip with price + rank; Why It Ranks front-loaded; gauges and supports; risk-last; research-link last).
- Affected: `/stock/[symbol]`, `/stock/[symbol]/analysis`.
- Priority: **P0**.

**P0-2 — Mobile navigation: inline hamburger drawer pushes content, hides search.**
- Problem: Opening the mobile drawer shifts the page; `SymbolSearch` is invisible on mobile until the drawer opens.
- Why it matters: Mobile is the dominant Indian-investor surface; search parity is essential.
- Proposed solution: Bottom nav (Dashboard / Watchlist / Market) + floating Action search + slide-over "More" (per §11).
- Affected: All routes.
- Priority: **P0**.

**P0-3 — No skeletons; long loads render a centred spinner.**
- Problem: Stock detail, validation dashboard, and watchlist wait on multiple queries before any UI lands.
- Why it matters: Perceived load is the bulk of the experience on cold `/live` (9.37s) and `/validation/dashboard` (6.1s).
- Proposed solution: Skeleton loaders matching the destination layout; `keepPreviousData: true` on sort/filter transitions.
- Affected: `/stock/[symbol]`, `/validation`, `/watchlist`, `/`.
- Priority: **P0**.

### P1 — Major UX problem

**P1-1 — Information architecture mismatch.**
- Problem: 7 destinations under "Research Tools" mix investor and quant screens; `Market` and `Learn` are buried; the flagship stock routes have no nav entry.
- Why it matters: Investors cannot find the daily-use surfaces without scanning the dropdown.
- Proposed solution: Two-level nav (Investor primary: Dashboard / Watchlist / Market / Learn; Researcher secondary: Strategies / Validation / Historical / Analytics / Lab); rename dropdown "Research" → "Validation". Promote `Market` to the top bar.
- Affected: `NavBar.tsx` across all routes.
- Priority: **P1**.

**P1-2 — Watchlist no sort/filter/search; no in-page strategy switch; errors render as `EmptyState`.**
- Problem: Small tracked list, no reorder, no error specificity.
- Why it matters: Watchlists compete on scannability; the dashboard's table sets a bar the watchlist misses.
- Proposed solution: Column sort (Rank, Rank Δ, Change, Below-52w-high), search filter, in-page `StrategySelector`, error → `ErrorMessage` with retry, 60s `refetchInterval`, `scope="col"` on headers. Mobile: hide Remove into a trailing action menu.
- Affected: `/watchlist`.
- Priority: **P1**.

**P1-3 — Shared atoms lack ARIA roles.**
- Problem: `StatusDot`, `LoadingSpinner`, `ErrorMessage`, `EmptyState`, `ScoreGauge` have no `role` / `aria-live` / `aria-label`; `Card.badge` breaks light mode.
- Why it matters: These atoms appear on every screen; one fix propagates everywhere.
- Proposed solution: Add roles per §12 table; replace `Card.badge` raw class strings with the `Badge` colour enum; add `dark:` variants where missing.
- Affected: `Card.tsx`, `ScoreGauge.tsx`, every consumer.
- Priority: **P1**.

**P1-4 — No design tokens wired into Tailwind; duplicated `focusRing`; two `MetricCard`s.**
- Problem: `tailwind.config.js` is empty; `lib/theme.ts` is advisory; `PageHeader` title size drifts; `validation/page.tsx` shadows `MetricCard`.
- Why it matters: Every new component reinvents utilities; drift accumulates.
- Proposed solution: Wire tokens into `theme.extend` per §14; retire the local `MetricCard`; delete the unused `.focus-ring` CSS class; standardize typography scale.
- Affected: Tailwind config, `lib/theme.ts`, every page.
- Priority: **P1**.

### P2 — Meaningful improvement

**P2-1 — Screener default sort arrow invisible.**
- Problem: `sorting: []` reads as "not sorted" even though order is rank.
- Why it matters: A clicked sort should show intent immediately.
- Proposed solution: `sorting: [{ id: 'rank', asc: true }]` initial; add price + daily-change columns default on; add a "Columns" menu.
- Affected: `/`.
- Priority: **P2**.

**P2-2 — Research pages inconsistent with the primary palette; redundant copy; dead imports; dead state.**
- Problem: 5 of 6 research pages use `bg-white dark:bg-slate-900`; `/analytics` duplicates `/strategies`' disclaimer and setter; dead imports in `/strategies` and `/validation`.
- Why it matters: Coherence and maintenance cost.
- Proposed solution: Unify page backgrounds to `bg-slate-50 dark:bg-slate-950`; drop dead imports; drop dead `selectedStrategy` setter in `/analytics`; merge disclaimer copy to one source.
- Affected: `/historical`, `/strategies`, `/experiment`, `/validation`, `/analytics`, `/learn`.
- Priority: **P2**.

**P2-3 — Tables on research pages and `WatchlistTable` lack `scope="col"`; charts lack `role="img"`.**
- Problem: Heading semantics incomplete; charts opaque to SR.
- Why it matters: Accessibility consistency.
- Proposed solution: `scope="col"` everywhere; `role="img"` + `aria-label` summary on charts; keyboard crosshair + `aria-live` region on `PriceChart`.
- Affected: All tables, all charts.
- Priority: **P2**.

**P2-4 — Charts lack a live legend and volume pane.**
- Problem: Active MAs shown only as toolbar checkboxes; no on-chart labels; volume is a separate off-chart block.
- Why it matters: Equity research tools show legend + volume on the chart; investors expect this.
- Proposed solution: Live legend bar under the toolbar with MA values; volume pane toggle; index overlay using the existing `getIndexCloses` data.
- Affected: `/stock/[symbol]`, `/stock/[symbol]/analysis`, `/stock/[symbol]/elliott-wave`.
- Priority: **P2**.

**P2-5 — `/validation`_reads as a wall of dashes by default.**
- Problem: `MeasurabilityNotice` is excellent, but the page reads sparse without forward returns.
- Why it matters: Investors instinctively distrust dash-heavy tables.
- Proposed solution: Inline glossary tooltips on the metric labels; render `EmptyState` inside sections that early-return `null`; surface a sample narrative summary even without forward returns ("This strategy's screening stability and FPR are X and Y. Forward-return metrics will populate once returns are ingested.").
- Affected: `/validation`.
- Priority: **P2**.

**P2-6 — `ResearchToolsMenu` keyboard incomplete.**
- Problem: No Arrow / Home / End / Escape handlers.
- Why it matters: Keyboard users cannot navigate the dropdown properly.
- Proposed solution: Match the `FloatingPanel` keyboard pattern; focus first item on open; restore focus to trigger on close.
- Affected: `NavBar.tsx`.
- Priority: **P2**.

**P2-7 — `NavBar` active links lack `aria-current`.**
- Problem: Active detection styles visually but does not announce.
- Why it matters: SR users cannot identify the current page.
- Proposed solution: `aria-current={isActive ? 'page' : undefined}` on `NavLink` and learn sidebar.
- Affected: `NavBar.tsx`, `learn/layout.tsx`.
- Priority: **P2**.

**P2-8 — Watchlist error renders as `EmptyState`; no retry.**
- Problem: Backend failure looks identical to "no data."
- Why it matters: Investors cannot distinguish an outage from a genuinely empty list.
- Proposed solution: Switch to `ErrorMessage` with a retry button.
- Affected: `/watchlist`.
- Priority: **P2**.

### P3 — Polish

**P3-1 — `SectionNav` magic number `top-[4.5rem]`.**
- Problem: Calibrated to the 56px NavBar; brittle.
- Proposed solution: `top-14` (Tailwind 56px) or read the NavBar height via a CSS variable.
- Affected: `/stock/[symbol]`, `/stock/[symbol]/analysis`.
- Priority: **P3**.

**P3-2 — `useChartColors.tick` not theme-aware.**
- Problem: Fixed slate-500 in light and dark.
- Proposed solution: Light `#64748b`, dark `#94a3b8`.
- Affected: All recharts charts.
- Priority: **P3**.

**P3-3 — `#patterns` anchor only exists after live evaluation resolves.**
- Problem: Early `SymbolActionBar` clicks land at nothing.
- Proposed solution: Render the anchor container unconditionally (prior audit R1).
- Affected: `/stock/[symbol]` Patterns action.
- Priority: **P3**.

**P3-4 — Dead Tailwind class in `StatBox`.**
- `analytics/page.tsx:300` has `dark:bg-slate-900/50 dark:bg-slate-700/40` — second dark bg shadows the first.
- Proposed solution: Drop the redundant class.
- Affected: `/analytics`.
- Priority: **P3**.

**P3-5 — `Card.badge` raw class strings cause a light-mode regression on the stock detail `Strengths` / `Weaknesses` cards.**
- Problem: `page.tsx:442,453` pass dark-only class pairs.
- Why it matters: Light-mode readers see a transparent/floating badge.
- Proposed solution: Use `Badge color="emerald|rose"`.
- Affected: `/stock/[symbol]` Strengths/Weaknesses cards.
- Priority: **P3** (low visual impact, but real).

**P3-6 — Learn sidebar active links lack `aria-current`.**
- Affected: `/learn/*`.
- Priority: **P3**.

**P3-7 — Elliott Wave threshold slider `aria-valuetext`.**
- Problem: Numeric readout without unit context.
- Proposed solution: `aria-valuetext={n% reversal threshold}`.
- Affected: `/stock/[symbol]/elliott-wave`.
- Priority: **P3**.

**P3-8 — Inconsistent icon-button `aria-label`s on research pages.**
- Problem: Only `/experiment` remove-override icon has `aria-label`.
- Proposed solution: Audit and add `aria-label` on all icon-only buttons.
- Affected: `/historical`, `/strategies`, `/validation`, `/analytics`.
- Priority: **P3**.

---

## 18. Proposed Future UI Architecture

The target is a single product with two audience layers. No methodology changes.

### Top bar (sticky)

```
M25  Dashboard  Watchlist  Market      Learn   [search]  [theme]   [more ▾]
```

- Primary: Dashboard, Watchlist, Market, Learn.
- "More" slide-over: Strategies, Validation, Historical, Analytics, Experiment Lab.
- Search: full-width sheet on mobile, inline on desktop.
- Theme: 3-mode segmented (today's component).
- Strategy selector: moved onto each page that affects it (dashboard, watchlist, stock detail), not into the NavBar.

### Bottom nav (mobile only)

```
[Dashboard]   [Watchlist]   [Market]   [More]
```

Replaces the inline drawer.

### Investor routes

- `/` Dashboard. Screener with optional price/change columns, "Columns" menu, sort arrow visible.
- `/watchlist` — sortable, searchable, strategy-switchable in-page, with retry on error.
- `/market` — breadth + sectors (today's, promoted to top-level).
- `/stock/[symbol]` — analysis-first flagship. Order per §6. Skeletons. `WhyItRanks` front-loaded. Price header strip on top.
- `/stock/[symbol]/elliott-wave` — separate research screen. Preserved.
- `/learn` (and children) — promoted to top-level; matches the primary palette.

### Researcher routes (under "More")

- `/strategies` — evaluate, compare, contribution. Reads `useStrategy()`.
- `/validation` — forward-returns scorecard. Inline glossaries. Renamed from "Research".
- `/historical` — date replay. Consolidated single date picker.
- `/analytics` — either merged as a Charts tab on `/strategies`, or refocused on universe-orthogonal run statistics.
- `/experiment` — parameter overrides. Hidden behind a clear "developer tool" label; spinner + `aria-busy` on runs.

### Stock routes' cross-linking

- `SymbolActionBar` stays (Chart / Analysis / Elliott Wave / Patterns + WatchlistStar). Adjust labels: on the analysis screen "Chart" is an in-page mode; on the detail screen "Patterns" anchors below; "Elliott Wave" navigates to the dedicated route.
- Analysis page keeps the "Targets and risk / reward" card **but reframed** per Q1 in §16 — separate the EW projection zone presentation from the value-target constructions, and reconsider deriving R:R from the risk-only stop.

### Design system

- `tailwind.config.js theme.extend` wires `lib/theme.ts` (colors, typography, spacing, focusRing, transitions, chartPalette).
- Shared atoms: `Button`, `Badge`, `Card` (+ `MetricCard`), `StatusDot`, `LoadingSpinner`, `ErrorMessage`, `EmptyState`, `Tooltip`, `DataTable`, `Tabs`.
- All atoms carry ARIA + dark variants.
- One chart theme hook for recharts and lightweight-charts.

### Information density target

- Page-level: header strip (single row) → summary metrics → primary surface → supporting sections → risk → research.
- Card-level: title + subtitle + body, `p-4`, consistent header; badges standardized.
- Table-level: 25 rows per page, sort arrow visible, columns hideable, "Showing 25 of N" footer, `scope` + `aria-sort` everywhere.
- Mobile: column hiding, bottom nav, full-screen search, slide-over "More".

### What stays separate

- Elliott Wave screen.
- Methodology, scoring, ranking, gates, thresholds, strategy configuration, stop-loss methodology.

---

## 19. Final Assessment

### Is the current UI production quality?

**No. Not yet.** It is competent, methodology-loyal, and accessible in the primary table, but it is not production quality as a research product. Three blockers:

1. The flagship stock detail reads bottom-up against the investor's question order.
2. The design system is half-built (tokens not wired, two `MetricCard`s, `Card.badge` light-mode bug, missing ARIA on shared atoms).
3. The information architecture mixes investor and quant surfaces at the same navigation level.

These are resolvable in a focused redesign — no rewrite, no methodology change.

### The 5 biggest improvements needed

1. **Reorder the stock detail** (and promote the analysis screen) so the page answers what is happening → how strong → why it ranks → supports → risk → research, in that order. Price header strip on top, `WhyItRanks` immediately below, risk-last.
2. **Wire the design tokens into Tailwind.** Retire the second `MetricCard`, the unused `.focus-ring` CSS class, and the raw `Card.badge` strings. One typography scale, one button, one table, one tooltip.
3. **Split navigation into investor and researcher layers.** Bottom nav on mobile (Dashboard / Watchlist / Market / More); slide-over "More" holds the 5 researcher surfaces; Learn promotes to top-level; `Research` item renames to `Validation`.
4. **Add skeletons and `keepPreviousData`.** Stop hiding entire pages behind a centred spinner; preserve previous data on sort/filter and on auto-refresh.
5. **Fill the accessibility gaps on shared atoms.** `StatusDot`, `ScoreGauge`, `LoadingSpinner`, `ErrorMessage`, `EmptyState` are one fix each with cross-product impact; `aria-current` on `NavBar` and learn sidebar; `scope="col"` on every table; `aria-pressed` on every chip, date tile, sort pill; keyboard handlers on `ResearchToolsMenu`.

### What should be redesigned first?

The stock detail page. It is the flagship. It is where an investor decides the platform is worth using. Every other screen can be tightened around it. The analysis screen's promotion (per prior audit recommendation) is ready once the §6 hierarchy unifies both.

### What should NOT be changed?

- The methodology: scoring, ranking, gates, thresholds, strategy configuration, Trend Template, Relative Strength, Volume, Pattern, Setup Quality.
- The risk-only stop-loss methodology and its component-layer presentation (`SuggestedStop.tsx`).
- The Elliott Wave methodology, its projected wave path, and its projected completion zone.
- The `RulePassMatrix` heatmap, the `IMPROVEMENT_HINTS` actionability, the `Measurability` flag's "withhold, not zero-fill" pattern, the `StalenessBanner`'s calendar-aware copy, the `StrategySelector`'s self-healing selection, and the `SymbolSearch` combobox semantics. These are already good.
- The chart-canvas library choices (lightweight-charts for price panes, recharts for gauges and summaries).
- The honest microcopy across empty states, footers and disclaimers.

### What should remain separate?

- **Elliott Wave** — `/stock/[symbol]/elliott-wave` stays a distinct first-class research screen. The projected wave path and the projected completion zone stay. The "Chart annotation only" disclaimer stays. The labelling-confidence ranking panel, framed as fit-to-theory, stays. The cross-link to the analysis page stays. This audit confirms the existing separation and explicitly does not recommend removing the projected completion zone on the grounds that it is forward-looking. It is an intentional Elliott Wave analytical projection.

- **Stop-loss risk-only framing** — `SuggestedStop.tsx` stays risk-only. The analysis page's "Targets and risk / reward" card should either separate the EW projection zone from value-target presentation or stop deriving R:R from `suggested_stop.level`, but the component-layer stop-loss presentation is unchanged (see Q1 in §16).

- **Researcher surfaces** — `/strategies`, `/validation`, `/historical`, `/experiment`, `/analytics` keep their methodology work; they move behind a "More" affordance rather than competing for investor attention.

### Final status by area

| Area | Status |
|---|---|
| Dashboard | NEEDS IMPROVEMENT |
| Stock detail | MAJOR REDESIGN |
| Watchlist | NEEDS IMPROVEMENT |
| Chart experience | NEEDS IMPROVEMENT |
| Technical workbench | NEEDS IMPROVEMENT |
| Momentum25 explanation | PASS with gaps |
| Elliott Wave | PASS |
| Stop-loss component | PASS |
| Stop-loss / targets UI (analysis page) | NEEDS IMPROVEMENT (methodology question, see §16) |
| Market | PASS |
| Strategies / Analytics | NEEDS IMPROVEMENT (redundant) |
| Validation | NEEDS IMPROVEMENT |
| Historical | NEEDS IMPROVEMENT |
| Experiment Lab | MAJOR REDESIGN (audience) |
| Learn | PASS with gaps |
| Navigation / IA | MAJOR REDESIGN |
| Visual design / tokens | NEEDS IMPROVEMENT |
| Information density | NEEDS IMPROVEMENT |
| Responsive / mobile | NEEDS IMPROVEMENT |
| Accessibility | NEEDS IMPROVEMENT |
| Performance UX | NEEDS IMPROVEMENT |
| Empty / error / loading | NEEDS IMPROVEMENT |
| Product coherence | NEEDS IMPROVEMENT |

No code was modified in producing this audit. No methodology, scoring, ranking, strategy configuration, gate threshold, stop-loss, or Elliott Wave logic is recommended to change. Elliott Wave remains a separate first-class research screen; the projected completion zone is preserved.