# Unified Analysis Screen — `/stock/[symbol]/analysis`

## Context

Three chart surfaces exist today and they feel like three tools:

- **Phase 9** — the multi-pane price chart (`PriceChart` + `useChartShell`), embedded in `/stock/[symbol]`.
- **Phase 8** — pattern detection, a second `PriceChart` instance buried inside `PatternCard` on the same page.
- **Phase 7** — Elliott Wave, a separate route `/stock/[symbol]/elliott-wave`.

A reader verifying a momentum call has to move between them, and each move costs context. The indicator set is also thin: the chart offers five fixed moving averages with no editable periods, and no Bollinger Bands or VWAP anywhere.

This builds a **new, separate screen** that unifies the three into one surface, tuned for one job: *arrive from the top-momentum list and see immediately why the stock is flagged*. The existing `/stock/[symbol]` page keeps working unchanged and gains one link to the new screen. Whether the new screen later replaces the old one is a separate decision.

Presentation only. No backend change, no scoring, ranking, or trend-template change.

### Decisions taken with the user

| Question | Decision |
|---|---|
| VWAP on daily-only bars | Ship **both** Anchored VWAP and Rolling VWAP as separate toggles |
| Screen scope | **Near-full replacement** — carry engines, rules, scores, history, live sections too |
| Existing fixed MA checkbox row | **Keep it visible**; the new picker's SMA section starts empty so nothing double-draws |
| Extra sub-panes | **Refactor `PriceChart`'s pane machinery to a registry** — additive, existing three unchanged |
| Buy/Sell signal constraint | **Removed by the user.** Ship the full strategy layer, including directional signals |
| Target price / profit projection | **Removed by the user.** Ship projections, measured moves and R:R |
| Elliott Wave / pattern "no verdict" | **Removed by the user.** Show a headline call, alternatives still reachable |
| Signals feeding scoring / ranking | **UI-layer score now**; backend engine written up as a separate plan |

### Constraint changes, recorded

The original brief forbade auto-generated Buy/Sell indicators, target prices and profit projections, and required Elliott Wave and pattern detection to stay verdict-free. The user has lifted all of these. The plan below ships:

- a **signal layer** (§ "Strategies and signals"),
- a **price-target layer** (§ "Targets and projections"),
- **headline calls** on Elliott Wave and pattern detection (§ "Verdicts").

The boilerplate "not a recommendation" line is dropped. What stays is the *rule text* on each signal and the *basis* on each target — that is labeling, not hedging, and it is what makes the screen readable rather than mysterious.

One item is still open because it is not a presentation change at all: whether signals should feed scoring and ranking. See that section.

### UX reference

TradingView and Kite both converge on: a persistent top toolbar (symbol, interval, indicator entry point), a left drawing rail, a right info rail, and one canvas that never remounts when you change what is drawn on it. Kite's own charting ships two engines and 100+ indicators ([Kite user manual](https://kite.trade/docs/kite/charting/), [Z-Connect](https://zerodha.com/z-connect/kite/new-charting-features-on-the-kite-app)). We are not matching indicator breadth. We beat both on *one* task by making the momentum evidence the default view rather than something the user must assemble — and the strategy presets below are how a reader gets a second, third and fourth read of the same chart in one click.

---

### Step 0 — commit this plan to the repo

First implementation action: write this document to
`docs/2026-08-10-unified-analysis-screen-plan.md`, matching the existing dated-plan
convention in `docs/` (`2026-08-09-functional-audit-plan.md`). Update it as the build
progresses so the repo, not the chat, holds the record.

---

## Architecture

One `<PriceChart>` instance, mounted once, never keyed or conditionally rendered. Modes swap only annotation props (`markers`, `overlayLine`, `overlayLines`, `priceZone`). Indicator overlays are mode-independent and always drawn. This is what makes the interaction model genuinely unified rather than three tools behind tabs.

### New files

| Path | Contents |
|---|---|
| `web/src/app/stock/[symbol]/analysis/page.tsx` | The screen. Owns mode state, composes the chart and rail. |
| `web/src/lib/indicators/overlays.ts` | Pure price-pane indicators over `OHLCVBarDTO[]`. No React. |
| `web/src/lib/indicators/oscillators.ts` | Pure sub-pane indicators (Stochastic, OBV, MFI, …). No React. |
| `web/src/lib/indicators/catalogue.ts` | One `INDICATORS` array: id, label, kind (`overlay`/`pane`), default params, compute fn. The picker renders from it; adding an indicator is one entry. |
| `web/src/lib/strategies.ts` | Preset definitions + the pure signal rules. No React. |
| `web/src/lib/overlay-preferences.ts` | `useOverlayPreferences(symbol)`, key `chart-overlays:${symbol}`. |
| `web/src/components/stock/OverlayPicker.tsx` | Searchable indicator list rendered from the catalogue, parameter inputs, and the legend showing each active indicator's latest value. |
| `web/src/components/stock/StrategyPanel.tsx` | Preset selector plus the signal log for the active preset. |
| `web/src/components/stock/useChartPatterns.ts` | Extracted from `PatternCard`. |
| `web/src/components/stock/useElliottWaveChart.ts` | Extracted from the Elliott Wave page. |
| `web/src/components/stock/elliott-wave-panels.tsx` | `Evidence`, `CountSummary`, `WaveDetail` moved out of the page module. |

### Existing files edited

- `web/src/components/stock/PatternCard.tsx` — replace the inlined mutation/overlay logic with the new hook; export `PatternCandidate`. JSX unchanged.
- `web/src/app/stock/[symbol]/elliott-wave/page.tsx` — replace the inlined state/query/memos with `useElliottWaveChart`; import the three panels from their new module. Rendering unchanged.
- `web/src/app/stock/[symbol]/page.tsx` — add one `<Link>` labeled **"Try the new analysis view"** in the `PageHeader`, next to `SymbolActionBar`. Do not touch `SymbolActionBar` itself (it is shared with the Elliott Wave page).

### The one `PriceChart` change: pane registry

Its pane machinery hardcodes `PaneId = 'rsi'|'macd'|'adx'` with a branch per pane (create pane, add series, set data, dashed guide lines, crosshair readout entry). Adding Volume or Stochastic means a fourth branch, then a fifth.

Replace the branches with a data-driven list:

```ts
export type PaneDef = {
  id: string;
  label: string;
  series: { key: string; type: 'line' | 'histogram'; color?: string }[];
  guides?: { value: number; label?: string }[];   // RSI's dashed 30/70
  format?: (v: number) => string;
};
export const PANE_DEFS: PaneDef[] = [ /* rsi, macd, adx, then the new ones */ ];
```

`PaneId` becomes `string`. The pane effect loops `PANE_DEFS`. Pane data comes from a widened `indicatorSeries` bar type — an index signature on top of the existing named fields, so `useChartShell` keeps supplying `rsi14`/`macd_*`/`adx14` from the backend untouched while the new screen merges browser-computed pane values into the same array.

The existing three entries must reproduce their current config exactly: same colors, same 30/70 guides, same histogram sign coloring, same order, same stretch factors. Verified by screenshot diff, not by reading.

`showMaControls` is **not** added — the user chose to keep the built-in MA row visible.

---

## Indicator catalogue

Backend per-bar series carries only `rsi14, atr14, adx14, macd_line, macd_signal, macd_histogram`. Everything else is latest-value-only or absent. Since this is presentation-only work, all of the following are derived in the browser from the fetched OHLCV bars — the same approach `PriceChart`'s existing `rollingMean` already takes.

Every entry below is one row in `catalogue.ts`, so the picker, the legend, and preference validation all come for free.

### Price-pane overlays (render through the existing `overlayLines` prop)

| Indicator | Default params |
|---|---|
| SMA | any period, repeatable |
| EMA | any period, repeatable |
| WMA | any period |
| Bollinger Bands | 20, k=2 — upper/mid/lower |
| Keltner Channels | EMA 20, ATR 10, mult 2 |
| Donchian Channels | 20 and 55 |
| Ichimoku Cloud | 9 / 26 / 52, chikou 26 |
| Supertrend | ATR 10, mult 3 |
| Parabolic SAR | step 0.02, max 0.2 |
| Anchored VWAP | anchor date, default = first visible bar |
| Rolling VWAP | 20 |
| VWAP ±1σ bands | on the anchored VWAP |
| Pivot points | classic, weekly and monthly |
| 52-week high / low | horizontal lines |
| Linear regression channel | lookback 100, ±2σ |
| Prior swing high / low | reuses the pivots the pattern and Elliott Wave endpoints already return — no new math |

Both VWAP variants ship. Each label states its window (*"Anchored VWAP (from 2026-02-14)"*, *"Rolling VWAP (20d)"*) so neither reads as intraday session VWAP, which daily bars cannot produce.

### Sub-panes (need the registry refactor)

| Pane | Default params | Source |
|---|---|---|
| Volume + volume SMA | 20 | browser |
| RSI | 14, guides 30/70 | backend series (existing) |
| MACD | 12/26/9 | backend series (existing) |
| ADX + ±DI | 14, guide 20/25 | backend series (existing) + browser ±DI |
| ATR / ATR% | 14 | backend series (existing) |
| Stochastic %K/%D | 14, 3, 3, guides 20/80 | browser |
| Stochastic RSI | 14 | browser |
| Williams %R | 14 | browser |
| CCI | 20, guides ±100 | browser |
| ROC / Momentum | 12 | browser |
| OBV | — | browser |
| Chaikin Money Flow | 20 | browser |
| Money Flow Index | 14, guides 20/80 | browser |
| Relative strength vs benchmark | ratio line + its SMA 50 | second `getOhlcv` call for the benchmark symbol |

The relative-strength pane is the one entry needing an extra fetch. It reuses `getOhlcv` with the benchmark symbol already named in `LiveStockAnalysis.benchmark_index` — no backend change, one more query key.

**Duplicate-math risk, and the guard.** The backend indicator pipeline already computes Stochastic, Williams %R, CCI, ROC, ±DI and ATR as latest-value snapshots. The browser now computes the same things independently. That is real duplication, accepted because moving them server-side would mean new endpoints and a backend change this task explicitly excludes. The guard is a test that asserts each browser-derived series' **final value matches the backend's `IndicatorSnapshot`** for the same symbol within a tolerance — a drift alarm on both implementations. See Verification, item 2.

**Avoiding duplicate MA lines:** the built-in row stays and keeps its persisted `activeMas` default of `[50, 200]`. The catalogue's SMA section therefore starts **empty**, and its header reads *"Add a custom SMA — 50 and 200 are already on via Quick MAs above."*

---

## Strategies and signals

The user removed the no-Buy/Sell constraint. Presets are the "strategies" layer: each one configures the chart in a click **and** contributes a rule set that marks the bars where its conditions turned true.

### Presets

| Preset | Chart setup | Rules it evaluates |
|---|---|---|
| **Momentum / Stage 2** (default from the momentum list) | SMA 50/150/200, 52-week range lines, RSI pane | Price > 50 > 150 > 200, SMA 200 rising, distance from 52w high/low, RS line at new high |
| **Breakout structure** | Donchian 20/55, Bollinger, volume pane | Donchian 20 breakout, Bollinger squeeze then expansion, volume > 1.5× SMA 20 |
| **Pullback / mean reversion** | EMA 10/21, Bollinger 20/2, anchored VWAP from last swing low, Stochastic pane | Touch of lower band, Stochastic cross out of oversold, hold above EMA 21 |
| **Trend quality** | Ichimoku, Supertrend, ADX pane | Price vs cloud, Tenkan/Kijun cross, Supertrend flip, ADX > 25 with +DI > −DI |
| **Classic crossovers** | SMA 50/200, MACD pane | Golden and death cross, MACD signal cross, RSI 30/70 crossings |
| **Volume / accumulation** | OBV, CMF, MFI panes, volume | OBV at new high with price, CMF > 0, pocket-pivot volume day |

Selecting a preset writes the whole overlay+pane config in one action. The user can then change anything; the preset chip goes to "Momentum (edited)".

### Signal engine

`strategies.ts` holds pure rules. Each returns `{ date, direction: 'long' | 'short' | 'exit', ruleId, label, detail }[]`, computed strictly from bars up to and including that date — no lookahead, so a signal never moves once printed.

Rendering reuses props that already exist:
- **Markers** on the price pane via `PriceChart`'s existing `markers` prop — `belowBar` green triangles for long, `aboveBar` red for short, `size: 0.7`.
- **Signal log** in the rail: newest first, each row showing the date, the direction, and the exact condition that fired (*"MACD line crossed above signal, 2026-07-18"*). Clicking a row sets `visibleRange` to that neighbourhood, reusing the Elliott Wave zoom mechanism.

Each signal row names the rule that fired and the values that made it fire. The generic disclaimer is dropped.

---

## Targets and projections

Now permitted. Four sources, all computable from data already on the screen.

| Target | Basis | Draw |
|---|---|---|
| **Elliott Wave projection** | `count.projection` — the backend already returns it per candidate | Two dashed bounds *plus a labeled midpoint*, at **every degree**, not just the top one (this is the constraint being lifted) |
| **Fibonacci extensions** | 1.0 / 1.272 / 1.618 / 2.618 of the prior impulse leg, anchored on selected wave or swing | Horizontal levels with price and ratio in the label |
| **Pattern measured move** | Pattern height projected from the breakout point; height comes from the `geometry` points the endpoint already returns | Level plus a ghost line from breakout to target |
| **ATR objective** | Last close ± N × ATR(14), N configurable | Level |

**Risk / reward.** The app already computes `suggested_stop` and `trailing_stop` in `LiveStockAnalysis`. Pair whichever target is active with that stop and show `R:R = (target − close) / (close − stop)` in the rail, plus the implied % move. This is the single most useful addition of the three lifted constraints — it turns a target from a number into a decision input.

Every target carries its basis in the label (*"1.618 extension of wave 3 — ₹1,842"*), because a target whose derivation is invisible cannot be checked.

---

## Verdicts

Both analyses already rank their own output; the UI was simply not showing the conclusion.

**Elliott Wave** — headline card at the top of the rail: the top-ranked count, its `current_position`, and its `labelling_confidence` as a percentage with the confidence `basis` and `components` on expand. The existing `ranking_rationale` and `ranking_method` become the "why this count" body. Alternative candidates stay one click away in a collapsed list, ordered by rank, each with its own confidence — showing the winner does not mean hiding the field.

**Patterns** — the detection result leads with the highest `completion_score` candidate as the headline: *"Cup with handle — 81% complete"*, with the `PatternCriterion` list beneath it showing which criteria are met and which are not. Other candidates stay listed below.

No new inference layer. Both headlines are the backend's own ranking, surfaced instead of suppressed.

---

## Signals and the scoring engine — open question

The other three lifts are display changes. This one is not, so it is called out separately rather than assumed.

Wiring signals into scoring means one of two very different things:

**(a) View-layer only.** A signal-derived column on the analysis screen and the momentum table that the user can sort and filter by, computed in the browser from the displayed bars. No backend change, no change to what a screening run stores. Fits inside this task.

**(b) A real scoring input.** A new backend engine contributing to the composite score. That means: new domain engine, config-hash change, a re-screen of production, and — by the repo's own research discipline — walk-forward and hold-out validation before promotion. It changes what `strategy_id=30` produces, which is the live product. It is a milestone, not a section of a charting task, and CLAUDE.md requires it be approved as an architecture change rather than arrived at incrementally.

**Decision: both.** Ship (a) in this task. Write (b) up as a separate plan for independent approval.

### (a) — in scope here

`strategies.ts` gains `signalScore(bars, presetId)`: a deterministic 0–100 roll-up of the active preset's rules — how many fired, how recently, and in which direction. Surfaced in two places:

- **Analysis screen** — a card in the rail: the score, the rules contributing to it, and each rule's own state.
- **Momentum table** — an optional column, sortable and filterable, computed for the visible rows only. Off by default behind a toggle, so the default dashboard is unchanged. Needs bars for each visible symbol; batch them through the existing `getOhlcv` query with a shared key so the table does not fire 25 uncoordinated requests.

It is a **view** over the same bars. `screening_runs`, `screening_results` and every stored score are untouched, so a run remains reproducible from the backend alone.

### (b) — separate plan, written but not built

Deliverable at the end of this task: `docs/2026-08-10-signal-engine-proposal.md`, covering the new domain engine, where it sits in the engine registry, its config and weights, the config-hash and re-screen consequences, and the walk-forward plus hold-out gate it must pass before promotion. No code. Given the standing record — 8 research proposals, 0 promoted, 6 rejected on hold-out — this one gets designed against that gate up front rather than retrofitted to it.

---

## Screen layout

**Header** — `PageHeader`: `SYMBOL — Analysis`, badges for `Rank #n`, `Trend Template PASS/FAIL`, `Momentum nn`. `SymbolActionBar` reused. Back link to the research list.

**Sticky toolbar** — segmented control `Chart | Patterns | Elliott Wave` on the left; preset dropdown, `OverlayPicker` trigger and active-indicator chips on the right. Timeframe and candle/line pills stay inside `PriceChart`'s own toolbar directly above the canvas, where they already live.

**Chart block** — `lg:grid-cols-3`. Chart `Card` at `lg:col-span-2`, `height={560}`, with a one-line mode footnote (Chart: bar count and data-as-of; Patterns: which geometry is drawn; Elliott Wave: the existing ambiguity footnote, verbatim).

**Sticky right rail** (`lg:col-span-1`) — in order: `TrendTemplateCard`, `WhyItRanks`, `StrategyPanel` (preset selector + signal log), then the active mode's panel:
- *Chart* — indicator legend with each active indicator's latest value.
- *Patterns* — "Detect patterns" button, `PatternCandidate` list, ambiguity note. Never auto-runs.
- *Elliott Wave* — threshold stepper, candidate buttons, degree breadcrumb, wave list, `CountSummary`.

**Below the chart** (the near-full-replacement scope) — reuse the existing components as-is, in the detail page's order: overview metrics (`ScoreGauge`, `RulePassMatrix`, `MetricCard`), engines (`AnalysisSection`, `EngineContributionBars`), rules table, score history, and the live-analysis block (`MomentumOverview`, `MomentumView`, `TechnicalWorkbench`, `VolumeAccumulation`, `SuggestedStop`, `RelativeStrengthVsIndex`). A `SectionNav` with the same `IntersectionObserver` scroll-spy ties them together. These are lifted, not rewritten — the new screen's value is the chart and the ordering, not new analytics.

Mobile: rail stacks below the chart.

---

## State and persistence

- **Timeframe, sub-panes, quick MAs, drawings** — continue to come from `useChartShell` / `useChartPreferences` (`chart-prefs:${symbol}`). They carry across all three screens, which is exactly what that hook was written for.
- **Indicator config, preset choice and signal visibility** — separate hook, separate key `chart-overlays:${symbol}`, mirroring `chart-preferences.ts` (read-once in an effect, `ready` flag, validator that drops unknown shapes). Keeping it separate avoids widening a validated shape that two shipped screens already depend on, and the validator can drop indicator ids the catalogue no longer defines.
- **Mode is not persisted.** Always opens on Chart.
- Defaults with nothing stored: mode `chart`, timeframe `1Y`, quick MAs `[50, 200]`, preset **Momentum / Stage 2**, signal markers on, no extra panes beyond the preset's RSI. That is the momentum-evidence default from requirement 3; the Trend Template card in the rail supplies pass/fail context.
- Gate the chart on `chartReady && overlaysReady`. `PriceChart` seeds `activeMas` and `drawings` once via `useState(initial…)`, so rendering before preferences load bakes in wrong values.

### Three rules that keep mode switching lossless

1. **Stable empty identities.** Module-level `const NO_MARKERS: ChartMarker[] = []` etc. The markers effect (line 607) detaches and recreates the plugin on every identity change; a fresh `[]` literal each render churns it.
2. **`visibleRange` is screen-level state, never derived from mode.** Only the Elliott Wave wave-select and "show full range" write it. The effect at line 653 calls `fitContent()` whenever the value is falsy, so a `null ↔ undefined` flip on a mode switch would silently throw away the user's zoom.
3. Indicator overlays never depend on mode, so nothing is recomputed when the mode changes.

Zoom is still lost on timeframe change and on the candles/line toggle. Both are pre-existing and out of scope.

---

## What still holds

Every content constraint from the original brief has been lifted. Two structural ones remain, and they are not editorial:

- **No backend change, and no change to scoring, ranking or the trend template.** This is the boundary that keeps the task a charting task. Pending your answer on § "Signals and the scoring engine".
- **Nothing invented.** Every target, verdict and signal is derived from data the app already has — backend projections, backend confidence scores, or arithmetic on the displayed bars. Each carries its basis in its label so a reader can check it. Labels stating what a number is are not hedging; they are the difference between a chart and a slot machine.

## Risks

- **`visibleRange` falsy → `fitContent()`** is the single easiest way to break the unified feel. Rule 2 above is mandatory.
- **The pane registry refactor is now the largest regression risk** — it rewrites working code on two shipped screens. Discipline: land the refactor as its own commit with the three existing panes only, screenshot-diff `/stock/[symbol]` and the Elliott Wave page, and add new panes only after that diff is clean.
- **The overlay effect rebuilds every series on any change.** With Ichimoku, Bollinger and channels active, a MAX-timeframe 2000-bar series means ~15 lines and ~30k points recreated per edit. Mitigation: parameter inputs are `<input type="number">` steppers committing on change/blur, not drag sliders; overlay computation is memoized per `(indicatorId, params, bars)`. `ponytail:` ceiling — add per-line keyed diffing inside that effect if it still stutters.
- **Sub-pane stretch factors** (line 742): price gets 3, each sub-pane 1. The catalogue now offers 14 panes; four active would leave the price pane at ~230px. Cap simultaneous panes at four and scale `height` with the count.
- Overlay series set `lastValueVisible: false` and `crosshairMarkerVisible: false`, so they never appear in the crosshair readout box. The picker legend replaces that.
- The two extractions (patterns, Elliott Wave) touch shipped code. They are pure moves; the diff must show no logic change.
- **Indicator math now lives in two languages.** Guarded by the snapshot cross-check, not by hope.

---

## Verification

1. **Indicator self-check** — assert-based, run with `npx tsx`: `sma` matches `PriceChart`'s `rollingMean` including the leading-null window; `ema` seed equals `sma(period)` at index `period-1`; `bollinger(k=0)` gives upper == mid == lower; Donchian upper/lower equal the rolling max high / min low; Stochastic stays in `[0,100]` and Williams %R in `[-100,0]`; both VWAPs stay within `[min(low), max(high)]` and equal typical price on a single bar; zero-volume bars produce no `NaN`; Supertrend flips at most once per bar; every function returns `null` for indices before its warm-up.
2. **Cross-check against the backend** — for a handful of real symbols, fetch `GET /stocks/{symbol}/live` and assert the last value of each browser-derived series matches the corresponding `IndicatorSnapshot` field (Stochastic %K/%D, Williams %R, CCI, ROC, ±DI, ATR 14, EMA 10/21, SMA 50/150/200) within tolerance. This is the guard on duplicated math and the most valuable test here.
3. **Signal determinism and no lookahead** — running the rules over `bars[0..n]` produces the same signals for those dates as running over `bars[0..n+50]`. A signal must never move or vanish when new bars arrive.
4. **Pane registry regression** — land the refactor alone, then load `/stock/[symbol]` and `/stock/[symbol]/elliott-wave` and screenshot-diff RSI, MACD and ADX against the pre-refactor build: same colors, same 30/70 guides, same histogram sign coloring, same order and heights. MA checkboxes, drawings, wave overlays and the projection zone must also render identically.
5. **Zoom persistence** — zoom in, cycle Chart → Patterns → Elliott Wave → Chart, assert the visible logical range is unchanged (Playwright `browser_evaluate`).
6. **Indicator / mode independence** — enable Ichimoku plus Bollinger plus two panes, switch to Patterns, detect, confirm indicator lines, signal markers and pattern geometry all draw together and survive every mode.
7. **Preset behaviour** — applying a preset sets exactly its documented config; editing one setting flips the chip to "(edited)"; switching presets does not leak the previous one's panes.
8. **Preference isolation** — set indicators, reload, confirm restored; confirm `chart-prefs:${symbol}` was not written by the new screen; corrupt `chart-overlays:${symbol}` by hand and confirm a clean fallback to defaults; remove an indicator id from the catalogue and confirm stored config referencing it is dropped, not crashed on.
9. **Entry point** — from the dashboard momentum table, click a symbol, follow "Try the new analysis view", confirm the default view makes the trend case readable without any further clicks.
10. **Targets and R:R** — Elliott Wave projection bounds match `count.projection` exactly at every degree; Fibonacci extension levels match hand-computed ratios on a fixed leg; the pattern measured move equals pattern height added to the breakout point; `R:R` matches `(target − close) / (close − stop)` against `suggested_stop` from the live endpoint. Every target label states its basis.
11. **Verdicts match the backend's own ranking** — the Elliott Wave headline is `candidates[0]` with its unmodified `labelling_confidence`; the pattern headline is the highest `completion_score`. No re-ranking in the browser, and the alternatives list is complete.
12. **Boundary check** — nothing in `web/src/lib/strategies.ts` is imported by backend code or by any screening path; `git diff` on `backend/` is empty.
13. `npm run build` and lint clean.

## Build order

1. Pane registry refactor alone, verified by item 4.
2. Indicator catalogue + picker + legend, verified by items 1 and 2.
3. The new screen with the three modes and the shared hooks, verified by items 5 and 6.
4. Presets and the signal layer, verified by items 3 and 7.
5. Targets, R:R and the two verdict headlines, verified by items 10 and 11.
6. The UI-layer signal score, on the analysis screen then as an off-by-default momentum-table column.
7. The link on the detail page, verified by item 9.
8. Write `docs/2026-08-10-signal-engine-proposal.md` — the backend engine plan, no code.

Each step leaves the repo deployable.

## Cut

Skipped: a first-class `priceOverlays` prop with crosshair readout (add when hover values on indicator lines are asked for); the Elliott Wave ranking panel and pivot table on the new screen (link out instead); mode persistence; URL-encoded config sharing; Bollinger band fill; multi-symbol comparison overlay; alerts on signal conditions; any backtest or hit-rate statistic on the presets — that is research work under the existing walk-forward discipline, not a chart feature.
