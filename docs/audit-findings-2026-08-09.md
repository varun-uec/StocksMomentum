# Full Application Audit — Momentum25 India

**Date:** 2026-08-09  **Type:** diagnosis only — no code was changed.
**Method:** real API (uvicorn on :8000) + real browser (Playwright, Next dev server on :3000)
against the **dev** database (`momentum25-db-1`, port 55432, 3.08M `ohlcv_daily` rows,
3235 securities, 13 strategies).

## Environment & safety

- `backend/tests/conftest.py::_require_test_database` (line 28) refuses any DB whose name
  does not end in `_test`. **Respected**: no pytest DB fixture was run, no `TRUNCATE`, no
  migration, no ingestion script.
- All DB access was read-only `SELECT`. All API calls were `GET`, plus one `POST` to
  `/stocks/{sym}/chart-patterns` (a pure read-model computation that persists nothing).
- **No writes were made**, including the watchlist CRUD and `POST /runs/execute` that the
  earlier plan had pre-approved — the current task scopes this to read-only.

## Live inventory (re-derived from routers + pages, not from any prior list)

44 API operations across 13 routers; 12 frontend routes.

| Area | Endpoints | Frontend |
|---|---|---|
| Screening / rankings | `GET/POST /runs`, `/runs/execute`, `/runs/latest`, `/runs/{id}`, `/rankings/runs/{id}`, `…/explanation` | `/` (dashboard), `MomentumTable`, `RunSummaryCards`, `StrategySelector` |
| Stock research | `/stocks/{sym}`, `/live`, `/history`, `/indicators/series` | `/stock/[symbol]` (8 sections) |
| Symbol search | `GET /securities?q=` | `NavBar` `SymbolSearch` |
| Charting | `/securities/{sym}/ohlcv`, `/stocks/{sym}/indicators/series` | `PriceChart`, `TechnicalWorkbench`, `chart-drawings.ts` |
| Elliott Wave | `GET /stocks/{sym}/elliott-wave` | `/stock/[symbol]/elliott-wave` (+ subwaves toggle) |
| Chart patterns | `POST /stocks/{sym}/chart-patterns` | `PatternCard` |
| Stop-loss (risk-only) | inside `/live` payload | `SuggestedStop` |
| Watchlist | `GET /watchlist`, `/watchlist/detail`, `POST`/`DELETE /watchlist/{sym}` | `/watchlist`, `WatchlistStar` |
| Market context | `GET /market/context` | `/market` |
| Strategies | `GET /strategies`, `/strategies/{name}` | `/strategies` |
| Validation | 6 endpoints (scorecard, alpha, rules, engines, historical, experiment, dashboard) | `/validation`, `/analytics` |
| Research | 7 endpoints (historical screen, CA refresh, compare runs/strategies, determinism, evaluate, contribution, experiment) | `/historical`, `/experiment` |
| Health/ops | `/health`, `/live`, `/ready`, `/startup`, `/data-freshness`, `/metrics` | freshness banner |
| Learn | — | 6 static pages |

Three of the five "preliminary findings" in `docs/2026-08-09-functional-audit-plan.md`
are **already fixed** and should be struck from that document: `securities.py` now routes
through `GetSecurityOHLCV`/`SearchSecurities` use cases, `from`/`to` are honoured end to
end (verified: `?from=2020-01-01&to=2020-06-01` returns 2020 bars, not `[]`), and symbol
normalisation is canonical (`/stocks/reliance` → `"RELIANCE"`).

---

# 1. Functional findings

## 1.1 Working (verified against real data)

| Feature | Evidence |
|---|---|
| Dashboard auto-load | `/` renders run #11 (227 qualified of 3235) on first paint with no user action. |
| Rankings + pagination | `/rankings/runs/11?limit=5` and the table's 4-page pager both correct. |
| Stock explanation | `/stocks/SANSERA` returns 24 rule explanations, 7 engines, coherent scores. |
| Live on-demand analysis | `/stocks/{sym}/live` re-evaluates from stored bars; RS measured vs 3218 symbols. |
| Indicator series | 277 bars, warm-up nulls only (RSI/ATR 263 non-null, ADX 250, MACD 243), last bar matches `/live`. Docstring claim holds. |
| OHLCV / charting | Candles, line, MA10/20/50/100/200, RSI/MACD/ADX panes, 4 drawing tools all render. |
| Elliott Wave | Pivots, count, subwave toggle all functional (but see 1.2.1 and 1.2.6). |
| Chart patterns | `POST` returns structured candidates; empty list when nothing qualifies. |
| Symbol search | `?q=REL` → 10 ranked matches, debounced + abortable in the UI. |
| Watchlist read | `GET /watchlist` and `/watchlist/detail` return TCS enriched server-side in one call, as the docstring claims. |
| Market breadth | 2795 securities, differing denominators explained honestly in the UI copy. |
| Error handling | Every bad symbol / run / strategy returns a correct RFC-7807 404 — no silent 200s on the lookup surface. |
| Data freshness | `FRESH`, `sessions_missed: 0`, next session 2026-08-10, XBOM calendar. |
| Health / readiness | `/health/ready` ok (db + redis). |

## 1.2 Broken — with recommendation

### 1.2.1 [CRITICAL] Prices are not corporate-action adjusted; every long-window number on affected symbols is wrong

`corporate_actions` is empty (0 rows), `corporate_action_inference_log` 0 rows, and
**every one of 3,076,892 `ohlcv_daily` rows has `adj_factor = 1` and `adj_close = NULL`.**

RELIANCE (`security_id` 1741) shows `2024-10-25 close 2655.70` → `2024-10-28 close 1334.35`
— the 1:1 bonus, recorded as a **-49.8% single-session move**. The API surfaces this
directly: `/stocks/RELIANCE/elliott-wave` reports a pivot from ₹3066.95 (2024-09-27) to
₹1217.25 (2024-11-21) as genuine price action.

Everything computed over a window spanning a corporate action is therefore wrong for the
affected symbols: 52-week high/low distance, RS rating (blended 63/126/189/252-day
returns), SMA150/SMA200 and their slope, ATR, the whole Trend Template gate, Elliott Wave
pivots and chart patterns. RELIANCE currently scores 40.1 with RS 27 — that number is an
artefact.

The system *knows*: `research.py:104` documents "Until this runs, every bar's `adj_factor`
is 1, so splits and bonuses corrupt long-window indicators", and
`indicator_pipeline.py:797` applies the factor correctly. The refresh has simply never been
run on this database, and **nothing in the product tells the user.**

**Recommendation.** (a) Operational: run `POST /research/corporate-actions/refresh` for the
active universe and re-run screening — this is a write operation and is out of scope here.
(b) Product: add a hard data-quality precondition. `GET /health/data-freshness` should
report adjustment coverage (`securities with ≥1 corporate action` / `bars with adj_factor ≠ 1`)
alongside bar freshness, and the dashboard's `StalenessBanner` should raise a distinct
`UNADJUSTED` state when coverage is zero. (c) Engineering: a screening run whose universe
has zero adjustment records should record that fact in `screening_runs.stats` so any
historical run is self-describing.
**Do not silently "fix" scores** — see §3, this changes every score.

### 1.2.2 [HIGH] `hard_filter_failures` contradicts `overall_passed` on the same payload

`GET /stocks/SANSERA` returns `overall_passed: true`, `rank: 1`, **and**
`hard_filter_failures: ["risk_rr"]`. The stock detail page therefore renders, on one screen:

- header: "Passes the Trend Template gate" · "Rank #1" · "Qualified — Actionable Now"
- rule matrix: `risk_rr: failed, blocks qualification` (red ring)
- metric tile: "Hard Filters — **1 failures**"
- Momentum Thesis: "**It is blocked by the hard gate on acceptable risk profile.**"

Root cause: `domain/scoring/explainability.py:260`

```python
def _is_hard_filter(rule_result: RuleResult) -> bool:
    return rule_result.engine_id in {"trend_template", "risk"} and not rule_result.passed
```

a hardcoded engine-name heuristic that contradicts the config-driven authority,
`scoring_engine.py::_compute_hard_filters_passed`, which reads `EngineConfig.gate` /
`RuleConfig.gate`. In `minervini_trend_template.json` the risk engine is `"gate": false`;
the only gates are trend_template (engine) and `vol_liquidity_min` (rule). So the
explainer both **invents** a gate (risk) and **misses** a real one (`vol_liquidity_min`).

**Recommendation.** Delete `_is_hard_filter` and derive gate membership from the same
`StrategyConfig` the scoring engine uses — pass the engine/rule gate id set into
`ExplanationBuilder` at construction. Add a golden test asserting
`hard_filter_failures == () ⇔ overall_passed` for any ranked security. This is an
explanation-layer fix and does not move any score, but it *encodes* gate composition —
see §3.

### 1.2.3 [HIGH] `/validation/*` and `/research/evaluate` report fabricated zeros as measurements

`forward_returns` is empty (0 rows). Consequences, all HTTP 200:

- `GET /validation/scorecard/minervini_trend_template` →
  `total_runs: 0`, `cagr: "0"`, `win_rate: "0"`, `sharpe_ratio: "0"`, `max_drawdown: "0"`,
  `profit_factor: "0"`, `beta: "0"`, `period_label: "2026-08-07 to 2026-08-07"`,
  `total_trading_days: 0` — while a COMPLETED run demonstrably exists.
- `/validation` renders all of it as a full scorecard: "Win Rate 0.00%", "Max Drawdown
  0.00%", "Sharpe Ratio 0.00", "Profit Factor 0.00". A reader cannot distinguish
  *"measured, and the strategy earned nothing"* from *"never measured"*.
- `/strategies` repeats the pattern (Sharpe 0, Sortino 0, Profit Factor 0, Max Drawdown
  0.0000%).
- `/validation/alpha/…` is the one honest endpoint: `period_label: "no_returns"`, empty
  `comparisons`.

**Recommendation.** Make un-measurable explicitly un-measurable. Change the metric fields
to `Decimal | None` and emit `null` with a top-level `measurability` block
(`{"forward_returns_available": false, "reason": "..."}`), following the `"no_returns"`
convention `/validation/alpha` already sets. In the UI, render `—` plus a single
"not yet measurable — no forward returns ingested" note per card, never `0.00%`.

### 1.2.4 [HIGH] Rule/engine "effectiveness" uses the momentum score as a stand-in for return

`application/use_cases/validation.py:627`:

```python
# Avg momentum score as period return proxy
avg_score = sum((r.momentum_score for r in rankings), Decimal("0")) / len(rankings)
period_returns.append(avg_score)
```

The value then leaves the system as `avg_return_when_passes`, `avg_return_when_fails` and
`return_delta`. Observed: `/validation/rules/…` reports `avg_return_when_passes: 39.4118`
for `bo_false_breakout` — that is exactly the run's average momentum score, not a return.
`/validation` renders it in a **green** column headed **"Return Delta"** and uses it to
label two rules "High-Value Rules (2)". Same proxy drives `standalone_performance: 39.4118`
on `/validation/engines/…`.

This is also the sharpest breach of the product constraint in §2: a setup-quality score
presented to the user as a percentage return.

Second, independent defect in the same path — `validation_services.py:684`:
`period_returns` has one element **per run**, while `evals` is one element per
(rule × security × run); the code aligns them by list index
(`if i < len(period_returns)`). With 1 run, exactly one of 25 evaluations per rule receives
a "return" and the remaining 24 are silently dropped. The alignment is meaningless at any
run count.

**Recommendation.** Remove the proxy. Source per-security forward returns from
`forward_returns` keyed by `(run_id, security_id)` and join on that key rather than list
position; when the join yields nothing, return `null` per §1.2.3 rather than a number.
Until then the `/validation` "Rule Effectiveness", "Engine Effectiveness" and "High-Value
Rules" panels should be hidden behind the same measurability flag. Findings derived from
these numbers must not be used for methodology decisions (§3).

### 1.2.5 [MEDIUM] `research/contribution` reports a wrong `run_count`

`GET /research/contribution/minervini_trend_template` returns
`run_count: 398` with `date_range: "2026-08-07 to 2026-08-07"`. There is exactly **1**
completed run. Source: `domain/research/services.py:545`

```python
run_count=len(run_snapshots) // max(len(engine_stats), 1) if engine_stats else 0,
```

`run_snapshots` is one entry per *security per run*; dividing by the engine count is
arithmetic without meaning (2390 ÷ 6 ≈ 398). The docstring on the use case promises
"cross-run statistics".

**Recommendation.** `run_count = len({s["run_id"] for s in run_snapshots})`. Add
`security_count` if the per-security total is what a consumer actually wants.

### 1.2.6 [MEDIUM] `mq_trend_persistence` can report more than 100%

Live output for SANSERA: `"Price above SMA50 on 64/63 days (101.5873%): Persistent trend."`

`domain/engines/momentum_quality.py:135-153`: the loop increments `persistence_count`
for every bar with a full SMA window (up to `len - ma_period + 1` bars), but the
denominator is `valid_days = min(lookback, len - ma_period + 1)`. When the supplied series
is longer than `lookback`, numerator and denominator count different populations and the
ratio exceeds 1, which then flows into `contribution` for failing cases
(`weight * ratio`).

**Recommendation.** Restrict the numerator to the same window as the denominator — iterate
only the final `valid_days` bars — and assert `0 ≤ ratio ≤ 1` in the rule. This changes
scores; see §3.

### 1.2.7 [MEDIUM] `/analytics` run-status tiles are always zero (case mismatch)

`/analytics` shows "Total Runs 3 · **Completed Runs 0** · **Failed Runs 0**" directly above
a pie chart reading "COMPLETED: 2, FAILED: 1". `web/src/app/analytics/page.tsx:84`
looks up `statusCounts['completed']`; the API emits `"COMPLETED"`.

(The earlier audit plan ruled this class of bug out because `screening_run.py:104` applies
`.upper()` on the *backend* — that protects the dashboard, not this page.)

**Recommendation.** Normalise once at the API-client boundary in `lib/api-client.ts`
(uppercase `status` on `RunDTO`), then key off the uppercase constant everywhere. Grep for
other lowercase status literals in `web/src` while doing so.

### 1.2.8 [MEDIUM] `/market` sector panel shows a factually wrong reason for being empty

`SectorStrengthTable.tsx:60` renders *"No benchmark-index history is available, so sector
excess returns cannot be measured."* But `benchmark_index_daily` has 2858 rows and the API
returns `benchmark_index: "NIFTY500"` — the index history **is** present. The real cause is
that `securities.sector` is `NULL` for **all 3235 rows**, so
`compute_sector_relative_strength` has nothing to group by
(`market_context.py:78,108`).

**Recommendation.** Have the endpoint return the reason rather than let the client guess:
add `sectors_unavailable_reason: "no_sector_classification" | "no_benchmark_history" | null`
to `MarketContext` and render that. Note the strategy description already records that
sector classification is unavailable from any free NSE source — so the honest copy is
"sector classification is not available for this universe", and the panel should probably
be removed from the page until it is.

### 1.2.9 [LOW] Dead columns caused by the same missing sector data

`MomentumTable`'s **Sector** column is `—` for all 100 rows and its search placeholder
advertises "Search symbol, name, **sector**…". `securities?q=` returns `sector: null` for
every hit.

**Recommendation.** Hide the Sector column and drop "sector" from the placeholder while
`sector` is universally null (drive it off the data, not a code deletion, so it returns
automatically if classification is ever ingested).

### 1.2.10 [LOW] `percentile` is always `null`

`explainability.py:194` hardcodes `percentile=None` and nothing ever fills it, including on
the ranked path where rank *is* populated (`explainability.py:325` sets only `rank`). The
stock page renders a permanent "Percentile —" tile next to "Rank #1".

**Recommendation.** Either compute it on the ranked path (`percentile = 100 × (1 − (rank−1)/qualified_count)`,
a presentation-only derivation) or delete the field from the DTO and the tile. Do not leave
a permanently blank metric on the highest-traffic panel.

### 1.2.11 [LOW] `setState` during render in `StrategySelector`

`StrategySelector.tsx:35-37` calls `setStrategyName(...)` in the component body, duplicating
the `useEffect` immediately above it (lines 23-29). Updating another component's provider
state during render is a React anti-pattern that can warn or loop.

**Recommendation.** Delete the render-time call; the `useEffect` already covers the stale
`localStorage` case.

### 1.2.12 [LOW] `/market/context?as_of=<pre-history date>` returns zeros, not an error

`?as_of=2019-01-01` → HTTP 200 with `evaluated: 0`, `pct_above_sma50: null`. Honest-ish
(the nulls help) but the counts read as real zeros.

**Recommendation.** Return 404/422 when `as_of` precedes the earliest stored bar, matching
the crisp 404s the rest of the API already produces.

## 1.3 Not verifiable — and why

| Item | Reason |
|---|---|
| Watchlist `POST`/`DELETE` | Write operations; excluded by this task's read-only scope. Read paths verified; CRUD verified only by code reading. |
| `POST /runs/execute`, `POST /runs`, `POST /research/historical/screen`, `POST /research/experiment/run`, `POST /validation/experiment/run`, `POST /validation/dashboard`, `POST /research/verify/determinism`, `POST /research/corporate-actions/refresh` | All persist runs or price adjustments. Not exercised. |
| `/stocks/{sym}/live?refresh=true` | Hits NSE live and mutates stored bars. Not exercised. |
| Everything downstream of `forward_returns` | Table is empty; see §1.2.3. Cannot be verified without a backfill (a write). |
| Sector relative strength | `securities.sector` 100% null; see §1.2.8. |
| Run comparison / rank-delta / score history | Exactly one COMPLETED run for the production strategy, so "Δ Rank" is `—` everywhere and `/stocks/{sym}/history` returns a single point. Multi-run behaviour unverified. |
| Cross-strategy dashboard behaviour | Only `minervini_trend_template` has a completed run (`/strategies?with_runs=true` returns 1), so the selector cannot be exercised as a selector — see §2.5. |
| Corporate-action correctness of any score | Blocked by §1.2.1. Every score observed in this audit is provisional. |

## 1.4 Dead / stale code and docs

- `docs/2026-08-09-functional-audit-plan.md` "Preliminary findings" 1, 2 and 4 are fixed;
  finding 3 (`getattr(self._ohlcv_repo, "_session", None)`) and 5 (`GetStockHistory` N+1,
  `limit=10000` per run across up to 500 runs) still stand. Recommend updating that file so
  it stops asserting resolved defects.
- `benchmark_index_daily` is populated but reaches the user through nothing except the
  sector panel that cannot render (§1.2.8).
- `legacy_ohlcv_daily_bak` exists alongside `legacy_ohlcv_daily`; confirm it is still needed.

---

# 2. Product-constraint re-check

## 2.1 VIOLATION — Elliott Wave publishes a price projection

`/stock/SANSERA/elliott-wave` displays, in the "Primary count" card:

> **PROJECTED COMPLETION ZONE** — **4636.31 – 5311.41** · *wave 3: 1.618-2.618 extension of wave 1*

and plots a labelled dashed line **"Projected zone low 4636.31"** across the price chart,
with the caption *"Dashed bounds mark the projected completion zone."* Last close is
₹3863.80 — this is a **+20% to +37% price objective derived from a wave count**, on a page
whose own header reads *"Chart annotation only — this view produces no buy/sell verdict and
no score."* The page contradicts its own disclaimer, and the constraint confines targets to
the validated swing-target research module.

**Recommendation.** Remove the projected-completion zone from both the card and the chart
overlay in the Elliott Wave view. If Fibonacci extension levels have analytical value, they
belong in the swing-target research surface where they are validated, or must be re-labelled
as neutral geometry (a Fibonacci grid drawn like any other drawing tool, with no
"projected completion" framing and no default-on rendering). Also drop the zone from the
`ElliottWaveAnalysis` response so it cannot leak to a future consumer.

## 2.2 VIOLATION — reward/target logic sits inside the risk gate and reaches the main UI

`risk_rr` produces, on `/stock/[symbol]` in three places (rule matrix, Weaknesses,
Complete Rule Evaluation):

> "Risk-reward ratio 1.5000:1 < min 2.0000:1 (**target via atr_multiple**; Unfavorable)."

and the improvement hint (`page.tsx:66`) reads *"Needs a better estimated reward-to-risk
ratio before this is an attractive entry."* A reward estimate and an explicit target
derivation are being computed and displayed outside the swing-target module, and the
constraint requires risk-only features to stay isolated from reward/target logic —
`SuggestedStop` honours this scrupulously ("Risk caps, not targets… they carry no reward
estimate"), while `risk_rr`, one card away, does not.

**Recommendation.** This one cannot be fixed by copy alone: `risk_rr` is a scoring rule
(weight 0.5 in the risk engine), so removing or re-specifying it changes every score.
Escalate as a methodology decision (§3) with three options: (a) drop `risk_rr` from the
strategy config; (b) re-express it as a pure downside measure with no reward term;
(c) formally extend the swing-target exemption to cover it, with the same validation
evidence. Interim mitigation with no scoring impact: strip "target via atr_multiple" and
"attractive entry" from the user-facing explanation strings.

## 2.3 VIOLATION — the momentum score is presented as a return

See §1.2.4. `/validation` renders the average momentum score (39.4118) in a green column
headed "Return Delta", and `/validation/engines` labels it `standalone_performance`. The
Momentum Score must read as setup-quality confidence, never as a profit or return claim.

**Recommendation.** As §1.2.4 — remove the proxy. If a score-based diagnostic is still
wanted, name it `avg_momentum_score_when_passes` / `score_delta`, never `*_return*`, and
never render it with a `%` or in profit/loss colouring.

## 2.4 BORDERLINE — actionability framing edges toward a verdict

The stock header renders the badge **"Qualified — Actionable Now"**, and the Executive
Summary reads *"Its breakout and volume signals also confirm this as an **actionable setup
today**, not just a qualifying trend."* No Buy/Sell word appears — but "actionable now" is
read by a user as one. (`verdict: PASSED` elsewhere is trend-template PASS/FAIL and is
fine; the Elliott Wave and pattern modules carry explicit no-verdict disclaimers and honour
them apart from §2.1.)

**Recommendation.** Restate as setup quality, not action: "Qualified — all gates passed"
and "…breakout and volume conditions are also met at the latest close". Reserve "actionable"
for nothing.

## 2.5 HOLDS

- `SuggestedStop` — explicitly risk-only, no reward estimate, correct copy.
- `PatternCard` / `chart_patterns.py` — no target, no directional call, verified in the DTO
  and in the rendered page.
- Trend Template — consistently framed as a hard gate ("All 8 conditions must hold — this is
  a hard gate, not a score"), not as a return claim.
- Market context — explicit "not a signal for any individual stock, and not an input to the
  ranking".

---

# 3. Flagged for explicit sign-off before any change

Nothing in this list may be "fixed" as a bug; each moves scores, ranks or gate membership.

| # | Item | Why it needs sign-off |
|---|---|---|
| S1 | **Corporate-action adjustment (§1.2.1)** | Re-adjusting prices changes RS rating, the 52-week rules, all SMAs, ATR and therefore every score, rank and gate outcome, and invalidates comparison against every historical run. Needs a re-baselining plan, not a patch. |
| S2 | **`_is_hard_filter` gate set (§1.2.2)** | Encodes gate composition. The fix is mechanical but the correct gate set (trend_template engine + `vol_liquidity_min` rule, per config) must be confirmed as intended. |
| S3 | **`risk_rr` (§2.2)** | Weight-0.5 scoring rule with a reward/target term. Removing, re-specifying or exempting it all change the ranking. |
| S4 | **`mq_trend_persistence` denominator (§1.2.6)** | Fixing the >100% ratio changes the rule's `contribution` for every partially-passing security. |
| S5 | **Partial credit on failed rules** | Failed rules carry non-zero contribution (`risk_rr` failed → 0.38; `vol_breakout_confirm` failed → 0.51). Deliberate continuous scoring or leakage? Confirm before anyone "fixes" it. |
| S6 | **Rule/engine effectiveness verdicts (§1.2.4)** | `is_weak` / `is_redundant` / `is_high_value` are currently derived from the score-as-return proxy and a broken index join. **No rule may be added, removed or reweighted on the strength of these labels** until the join is sourced from real forward returns. |
| S7 | **RS rating & trend-template thresholds** | Untouched by this audit and unverified end-to-end while S1 stands. Any threshold change needs the standing walk-forward evidence bar. |

Consistent with the standing research freeze (RP-000→RP-007 closed, 0 promoted, binding
constraint is data not methodology), S1 is the item with real expected value here: the
qualified-set ranking IC problem is being investigated on **unadjusted prices**.

---

# 4. UI/UX findings

## 4.1 Checked and good

- **Landing page auto-loads current momentum stocks.** `/` fetches the latest COMPLETED run
  for the selected strategy on mount (60s refetch) and renders the ranked table with no
  "run an iteration" step. "Refresh" is a clearly-labelled optional fallback with an honest
  "usually takes a few minutes" caption. **Confirmed by real interaction.**
- **Nav is user-facing and simple.** Primary = Dashboard, Watchlist, plus a global symbol
  search. Historical, Strategies, Lab, Research, Analytics, Market and Learn are all behind
  a single "Research Tools" dropdown, exactly as asked. Strategies is *not* a primary tab.
- **Symbol search** — debounced 150ms, `AbortController` drops out-of-order responses,
  Enter takes highlighted → best match → raw input. Correct and fast.
- **Loading states** exist and are specific per view ("Loading stock research…", "Computing
  universe breadth…", "Loading analytics…") rather than a generic spinner.
- **Error state** on the dashboard names the likely cause ("Is the backend running?").
- **Theme** — light/dark/system, `aria-pressed`, works.
- **Rule matrix** is genuinely good: engine-grouped, per-rule tooltips, colour + text.
- **Learn** section (6 pages) all 200.

## 4.2 Issues — with recommendation

### U1 [HIGH] The stock detail page contradicts itself in the top 400px
Header says "Qualified — Actionable Now / Rank #1"; the matrix flags `risk_rr` as "blocks
qualification"; a tile says "Hard Filters: 1 failures"; the thesis says "blocked by the
hard gate". A daily user cannot tell whether this stock passed. **Fix §1.2.2**, then assert
in one place: qualified ⇒ zero gate failures shown, anywhere on the page.

### U2 [HIGH] Elliott Wave labels the last 2% of the chart and calls it the count
On SANSERA's 1Y view the entire labelled structure (waves 1, 2 and subwaves (1)–(5)) is
crammed into the final handful of bars near the right edge, while the 1250→3860 advance
that fills the chart is unlabelled. The caption reads "**124 confirmed pivots** at a 5%
reversal threshold" over 365 bars — a pivot every ~3 bars, which is not a 5%-degree zigzag,
and the pivot table shows a swing high *and* a swing low on the **same bar** (2025-02-19,
2025-03-03, 2025-04-04). **Recommendation:** (a) enforce alternation and a minimum bar
separation in the zigzag so two pivots cannot share a date; (b) select the counted swing
set at the *displayed* degree so the labels span the visible range; (c) show the count's
own date range in the caption so a count confined to 3 weeks is visible as such;
(d) tie the analysis `lookback_days` to the selected timeframe — the page requests the
500-bar default while displaying 365.

### U3 [HIGH] Chart interaction is inconsistent across chart-bearing pages
| | Timeframes | Candle/Line | MAs | RSI/MACD/ADX | Drawing tools | Pattern overlay |
|---|---|---|---|---|---|---|
| Stock detail | ✓ | ✓ | ✓ | ✓ | ✓ (4) | ✓ |
| Elliott Wave | ✓ | ✓ | ✓ | **✗** | **✗** | **✗** |

Someone reading a wave count loses the indicators and the drawing tools they were just
using one click earlier, and preferences do not carry over visibly.
**Recommendation:** lift `TechnicalWorkbench` into a single shared chart shell used by both
routes, with wave/pattern annotation as an overlay layer rather than a separate chart, and
persist pane/tool state through the existing `chart-preferences.ts`.

### U4 [MEDIUM] Primary nav links have no accessible name
The Dashboard and Watchlist nav items expose as bare `link` with no text in the
accessibility tree (icon-only, labels hidden at this breakpoint, no `aria-label`). The
brand link and "Research Tools" are labelled; these two are not.
**Recommendation:** add `aria-label` to both `Link`s (and to any icon-only control added
later); keep the visible label from `lg` up.

### U5 [MEDIUM] The strategy selector does not read as a control
`/strategies?with_runs=true` returns exactly one strategy, so the selector renders as a
single indigo pill labelled "Minervini Trend Template" that looks like a pressed button and
does nothing when clicked. Its docstring calls it "the one control that decides which
stocks the dashboard shows" — currently unfalsifiable to the user.
**Recommendation:** render a real `<select>`/listbox with a "Strategy" label even at n=1,
show a caption when only one option qualifies ("1 of 13 strategies has a completed run"),
and disable rather than hide when n=1. Verify selection actually drives the table once a
second strategy has a run — **this could not be verified against real data** (§1.3).

### U6 [MEDIUM] "—" is overloaded and never explained
On the watchlist, TCS shows `in_latest_run: true` but Rank `—`, because it failed the gate.
The same `—` also means "not in the run at all", and on the dashboard it means "no previous
run to diff against" (Δ Rank) and "no data" (Sector, Pattern).
**Recommendation:** distinguish them: `—` for absent data, an explicit "not qualified" chip
where the security was evaluated and failed, and "first run" for an undefined delta. A
tooltip on the column header is not sufficient here; the cell itself must carry it.

### U7 [MEDIUM] `/validation` and `/strategies` present a wall of zeros with no empty state
Six panels of `0.00%` / `0.00` read as measurements. There is no empty state at all for the
"no forward returns" case.
**Recommendation:** pair with §1.2.3 — one page-level notice ("Performance metrics require
forward returns, which have not been ingested for this database") and `—` in every
dependent cell. Hide the Rule/Engine Effectiveness tables entirely while §1.2.4 stands.

### U8 [LOW] `/market` sector panel gives a wrong explanation — see §1.2.8.

### U9 [LOW] Dead Sector column and misleading search placeholder — see §1.2.9.

### U10 [LOW] Permanent blank "Percentile" tile — see §1.2.10.

### U11 [LOW] Navigation flow gaps
- The Elliott Wave page has no watchlist star and no route to pattern detection; the only
  exit is "← Back to research".
- Pattern matching and Elliott Wave have no entry point except from an individual stock
  page — reasonable, since both are per-symbol, but there is no way to ask "which stocks
  show a VCP right now" despite the dashboard already having a Pattern column.
**Recommendation:** put the same symbol-scoped action bar (watchlist star · Chart · Elliott
Wave · Patterns) on every `/stock/[symbol]/*` route; consider making the dashboard Pattern
column filterable as the universe-level entry point.

### U12 [LOW] `favicon.ico` 404s on every page load
The only console error observed across the whole browser sweep.
**Recommendation:** add `web/src/app/icon.svg` (Next.js picks it up automatically).

---

# 5. Summary

- **28 findings**: 12 functional defects, 4 product-constraint issues (3 violations,
  1 borderline), 12 UI/UX issues, plus 7 items flagged for sign-off.
- **The single most important finding is §1.2.1**: this database's prices are not
  corporate-action adjusted, so *every score, rank, gate outcome, wave count and pattern in
  this audit is provisional* for any symbol with a split or bonus in its window.
- **The second is §1.2.4 + §2.3**: the validation surface is presenting the momentum score
  as a return, both breaching the standing constraint and making the rule-effectiveness
  labels unsafe as evidence.
- Everything else is mechanical, and the read paths of the daily-use surface (dashboard →
  stock detail → chart → watchlist) work correctly against real data.
