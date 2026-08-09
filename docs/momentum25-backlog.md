# Momentum25 India — Phased Backlog

Source: capability audit (Opus 5), run against the existing codebase. Each item below is scoped to be pasted as its own prompt into a fresh Opus 5 (thinking on) session. Do not start a phase until the prior phase is verified working — later phases depend on earlier fixes being correct.

---

## Phase 0 — Correctness fixes
*Nothing downstream can be trusted until these are fixed. These are bugs in code that already ships, not missing features.*

| # | Item | Why it matters | File(s) |
|---|------|-----------------|---------|
| 0.1 | Fix universe cap — currently takes first 500 tickers alphabetically, mislabeled as "Nifty 500" | Invalidates every run and research result that assumed a real Nifty 500 universe | `screening.py:110-112` |
| 0.2 | Fix or confirm dead raw_bars fetch in orchestrator | Currently fetched, logged, and discarded — booby trap for future callers | `screening_orchestrator.py:70-75` |
| 0.3 | Fix RSI(14) — docstring claims Wilder's, code uses simple rolling mean (Cutler's) | Feeds the risk engine with materially wrong values; currently untested | `indicator_pipeline.py:72-91` |
| 0.4 | Fix ATR(14) — same defect as RSI | Feeds stop-loss/risk calculations downstream | `indicator_pipeline.py:94-114` |
| 0.5 | Implement corporate-action adjustment (`adj_factor` hardcoded to 1) | Splits/bonuses currently corrupt all long-window indicators for affected names | `bhavcopy.py:178-201` (parser exists, application doesn't) |

**Exit criteria:** golden tests pass for RSI/ATR against hand-computed values; universe logic documented and honestly labeled; config_hash versioning strategy in place so old runs aren't silently compared against new formulas.

---

## Phase 1 — On-demand lookup
*Mostly wiring against code that already exists but is unused — cheapest real capability gain.*

| # | Item | Why it matters | File(s) |
|---|------|-----------------|---------|
| 1.1 | Wire `MarketSyncService` + `NSEMarketDataClient.fetch_historical_bars` into a new `GET /stocks/{symbol}/live?refresh=true` endpoint | This is the actual "type a stock, get current analysis" feature you want | `market_sync.py`, `nse_client.py:28` |
| 1.2 | Handle single-symbol RS-rating gap explicitly (no universe to percentile against) | Must not silently fail or fake `tt_rs_rating_min` | `trend_template.py` |
| 1.3 | Add rate limiting + Redis caching | NSE will block naive per-request scraping | `redis/cache.py` (available, unused here) |
| 1.4 | Turn on the scheduler — `register_daily_job` has no caller, `scheduler_enabled` defaults false | Currently nothing refreshes automatically at all | `main.py:89`, `settings.py:52-53` |
| 1.5 | Add NSE trading-holiday calendar + staleness banner in UI | Prevents misreading a holiday as "no data" | — |
| 1.6 | Make `/runs/execute` incremental + background task | Currently 345 sequential synchronous fetches inside one HTTP request — will time out | `screening.py:143-151` |

**Exit criteria:** can type a stock symbol and get a fresh (not batch-stale) trend-template result; scheduled job actually runs and is observable in logs; staleness is visible in the UI, never silent.

---

## Phase 2 — Indicators
*Self-contained additions; prerequisite for Phase 3.*

| # | Item | Why it matters | File(s) |
|---|------|-----------------|---------|
| 2.1 | Implement ADX(14) with +DI/−DI, Wilder-smoothed | Currently a dead field name only (`ReplayIndicators.adx14`) | `indicator_pipeline.py`, `validation_models.py:295` |
| 2.2 | Implement MACD(12,26,9) | Not implemented at all currently | `indicator_pipeline.py` |
| 2.3 | Implement swing pivot support/resistance (fractal or N-bar swing highs/lows) | Prerequisite for real target/stop logic in Phase 3 | new |
| 2.4 | (Optional) Add EMA+ADX trend classification as a *new strategy config*, not a replacement | Your original framing assumed EMA+ADX; current trend template is SMA-based and validated — don't overwrite it | `trend_template.py` (config, per ADR-005) |

**Exit criteria:** ADX/MACD covered by tests; support/resistance levels exposed as data, not just used internally by breakout scoring.

---

## Phase 3 — Swing targets & stop-loss
*New domain logic. Must not ship without back-testing.*

| # | Item | Why it matters | File(s) |
|---|------|-----------------|---------|
| 3.1 | Implement entry/stop/target as a separate, pure domain service | Keep it isolated and unit-testable, not folded into scoring | new |
| 3.2 | Fix/replace existing broken `risk_rr` — "reward" is the 20-day high, which collapses to ~zero for exactly the breakout stocks this system selects | Currently a mean-reversion target inside a momentum system | `risk.py:212-294` |
| 3.3 | Back-test against existing walk-forward harness before any UI exposure | 6 of 8 prior research proposals already failed hold-out — assume this one does too until proven otherwise | `test_historical_validation_walk_forward.py` |

**Exit criteria:** hit-rate, average R, and max adverse excursion reported on a hold-out fold. **If it fails hold-out, it does not ship as a live feature** — that's a valid and expected outcome, not a blocker to route around.

**Hard dependency:** Phase 0.5 (corporate-action adjustment) must be done first — untested stop logic on unadjusted prices produces fictitious stop-outs.

**Status: FAILED hold-out.** 3.1 and 3.2 shipped (3.2 kept live — the old `risk_rr` formula was structurally broken, not just unproven, so "no longer broken" beats reverting to it even without validation). 3.3 backtest ran against real production data (15,045 trades full history, 3,211 hold-out from 2025-01-01): hit rate 64.0% but avg R **−0.021** on hold-out — winners aren't paying for losers. No UI/API exposure. Phase 4 not started (was gated on this passing).

| 3.3b | Run a bootstrap CI or t-test on the hold-out avg R (−0.021, n=3,211) to determine if it's distinguishable from zero or just noise | Point estimate alone doesn't say how confidently this is negative | `domain/research/` (extend existing backtest module) — **do not** use this to search for a passing parameter configuration, only to characterize the existing result |

---

## Phase 3b — Improve swing-target methodology
*Phase 3's fixed 1.5:1 ATR-multiple convention failed hold-out (avg R −0.021, n=3,211). This phase tries to find a method that actually passes, rather than shipping the failed one. May also fail — that remains an acceptable outcome, not a problem to route around.*

| # | Item | Why it matters | File(s) |
|---|------|-----------------|---------|
| 3b.1 | Try alternative reward/stop conventions (e.g. wider fixed R multiples, ATR-scaled stops instead of fixed ×2, volatility-adjusted targets) and re-run the same hold-out backtest for each | The current 1.5:1 fallback and ×2 ATR stop were reasonable defaults, not derived from this data — other conventions may hold up better | `domain/research/swing_targets.py` |
| 3b.2 | Try conditioning the target/stop on regime or setup strength (e.g. only trade signals with strong ADX/RS, or only use the swing-pivot target when a *strong* pivot exists, not the fallback case) | The original backtest ran on *all* qualifying trades; a subset may have real edge even if the average doesn't | same, + `trend_template.py` for filter conditions |
| 3b.3 | For every configuration tried, log it (params + hold-out result) in a single running table — do not discard failed attempts | Prevents silently cherry-picking a configuration after the fact; makes it possible to tell a genuine finding from a lucky one | new: `docs/research/phase3b-target-methodology-log.md` or similar |
| 3b.4 | Model slippage/gap-through on stop fills (flagged as missing in the original Phase 3 report) before declaring any configuration a pass | The original avg R was already noted as optimistic due to fills-at-exact-stop assumption; a "passing" number that ignores this isn't trustworthy | `domain/research/swing_targets.py` (`simulate_trade`) |

**Exit criteria:** at least one configuration passes hold-out with slippage modeled, **and** the configuration was chosen before seeing hold-out results (i.e. justified on the full/in-sample history or on first principles, not selected by scanning hold-out outcomes across many attempts — that's curve-fitting a fold you're supposed to only look at once). If nothing passes after a reasonable number of attempts (suggest capping at ~5-8 configurations), report that honestly and stop — Phase 4 stays blocked.

**Hard rule carried over from Phase 3:** the anti-curve-fitting logic still applies — trying more configurations against the same hold-out fold and picking the best one is exactly the failure mode being guarded against. If 3b needs more attempts than the cap, split off a fresh hold-out period rather than re-mining the same one.

**Status: FAILED, closed.** All 6 configurations tried (wider target, tighter stop, both combined, signal-time RR gate, ADX≥25 filter, RS≥85 filter) were screened in-sample first per the exit criteria; 0 of 6 cleared `avg_r > 0` in-sample, so none touched the hold-out fold. Every lever moved avg R further negative (range −0.105 to −0.396 vs. Phase 3's original). This points at the qualified-set ranking itself (negative IC, per the closed research program) as the binding constraint — not the exit-plan shape. Full attempt log in `backend/docs/research/phase3b-target-methodology-log.md`. **Phase 4 remains permanently blocked** unless the ranking/selection methodology itself is revisited — a larger research question outside this backlog's scope.

---

## Phase 3c — Standalone stop-loss suggestion (shipped, no target/reward)
*Different in kind from Phase 3/3b: this is a risk-management figure ("cap your downside if you're in this position"), not a profitability or return claim, so it does not require the backtest gate that sank 3/3b.*

| # | Item | Status |
|---|------|--------|
| 3c.1 | `suggest_stop_loss(entry, atr14, swing_support)` — pure domain function, ATR-based primary (`k` config-driven), swing-low fallback, isolated from `swing_targets.py` with zero shared dependencies | Shipped |
| 3c.2 | Wired into `GetLiveStockAnalysis` / `GET /stocks/{symbol}/live` as `suggested_stop`, with `method` disclosed (not a black box) | Shipped |
| 3c.3 | Unit tests: ATR case, config-driven `k`, ATR-unavailable→swing-low fallback, swing-low-above-entry ignored, both-unavailable | Shipped, 5 tests |

**Permanent scope boundary — do not extend this feature to include:** any target/take-profit level, R-multiple, or risk/reward ratio pairing the stop against an implied reward. That combination is exactly what failed in Phase 3/3b. No backtest is required *for the stop alone*, but the moment a reward figure is paired with it, Phase 3/3b's negative finding applies and the feature reverts to needing hold-out validation.

---

## Phase 4 — Prediction (base-rate panel, not a directional call)
*Gated on Phase 3b passing backtest (with slippage modeled) AND on data maturity. **Currently and likely permanently blocked** — see Phase 3b status above.*

| # | Item | Why it matters |
|---|------|-----------------|
| 4.1 | Implement a conditional base-rate panel: "of N historical instances of this setup, X% were positive at 120d, median Y%, 95% CI [a,b]" | The only defensible forward-looking output given your own repo's evidence (negative IC on qualified-set ranking, 0/8 proposals accepted) |
| 4.2 | Always show N and CI; suppress panel below a stated minimum N | Prevents a small-sample number from looking like a real edge |
| 4.3 | Confirm data maturity gate (2026-H1 120-day returns matured, correction-spanning fold) before enabling | Per your own program closure notes — this is a data constraint, not a coding one |

**Explicitly out of scope, permanently unless evidence changes:** a "this stock will go up/down" directional prediction. Your own backtests argue against it.

---

## Phase 5 — Coverage & licensing (lowest priority, largest scope)

| # | Item | Why it matters |
|---|------|-----------------|
| 5.1 | BSE adapter (new provider, ISIN-based cross-listing reconciliation, exchange dimension on `SecurityModel`) | Explicitly out of MVP scope per your ADD — treat as a scope decision, not a bug |
| 5.2 | Replace spoofed-UA NSE scraping with a licensed feed | Only needed if this ever goes beyond personal use |

---

## Phase 6 — Stock Detail / Research UI
*UX benchmark: Investing.com's mobile stock-detail experience — matched for information density and layout, not for content. Every section below is scoped to what's actually validated in Phases 0-3c/5; nothing here should imply more confidence than the underlying data supports.*

| # | Item | Source | File(s) / Notes |
|---|------|--------|------------------|
| 6.1 | Overview header — price, day change, 52W high/low, distance from each, Momentum25 score | Phase 0-1 (price data, trend template) | new frontend |
| 6.2 | Interactive price chart — 1D/1W/1M/3M/6M/1Y/5Y/MAX, line/candlestick, MA10/20/50/100/200 overlays | Phase 1 (live lookup), MA10/20 already computed | new frontend |
| 6.3 | Momentum View — Trend Template pass/fail, RS, Volume, Pattern, Setup Quality sub-scores with rule-level explanations ("✓ Price > MA20", etc.) | Phase 0 trend_template.py — already produces exactly this | new frontend, existing backend data |
| 6.4 | Technical Workbench — RSI, MACD, ADX, ATR table with values (no "Buy/Sell" signal labels — see note below) | Phase 2 (ADX/MACD) | new frontend |
| 6.5 | Volume & Accumulation section — relative volume, volume vs 20D avg, accumulation score | Existing risk/volume engine | new frontend |
| 6.6 | Pattern Recognition card — pattern type, quality score, breakout status | Existing breakout.py heuristics | new frontend |
| 6.7 | "Why this stock ranks" card — top factors from the rule checklist (already explainable per-rule) | Phase 0 trend_template.py RuleResult objects | new frontend |
| 6.8 | Suggested stop-loss display — level + method, framed as risk cap not trade advice | Phase 3c | already available via `/stocks/{symbol}/live` |
| 6.9 | Watchlist table upgrade — price, %, score, RS, trend, volume, setup, rank change, distance from 52W high | Existing data, new aggregation view | new frontend |

**Explicitly excluded from Phase 6 — do not implement without separate sign-off:**
- **Pivot points / support-resistance table** (classic/Fibonacci R1-R3, S1-S3) — no validated method exists (Phase 3/3b failed); do not ship even as a "passive display," since a level labeled "Key Resistance" or "Breakout Level" implies more than the data supports.
- **Any profit target, R-multiple, or risk/reward ratio** — same reasoning as Phase 3c's boundary above.
- **"Buy/Sell/Strong Buy" signal labels on individual indicators** (as in the Investing.com screenshots) — these imply a validated directional call per indicator. Show raw values only (e.g. "RSI(14): 61.7"), not a verdict.
- **Multi-timeframe momentum grid (5min/15min/30min/hourly)** — out of scope; this system is EOD-only (Phase 0/1), intraday timeframes don't exist in the data.
- **Fundamentals, News, AI event summaries** (doc's Sections 11-12) — separate data sources and scope, not part of this phase.
- **Prediction / base-rate panel** — still gated on Phase 4, which is blocked.

**Exit criteria:** every number and label on the page traces to a validated backend source (Phase 0-3c/5); nothing on the page implies an edge or directional call that hasn't been backtested.

---

## Phase 7 — Elliott Wave Analysis (dedicated screen)
*Wave counting has known ambiguity — the same history can support more than one valid count — so where that happens the UI shows the primary count plus the alternative, rather than hiding it. That's a labeling-accuracy detail, not a reason to hedge the whole feature.*

**This is a separate, dedicated screen** (e.g. `/stock/[symbol]/elliott-wave`), not a panel bolted onto the existing stock detail page — reachable via a clear link/tab from the stock detail screen.

| # | Item | Notes |
|---|------|-------|
| 7.1 | Algorithmic zigzag/pivot detection to identify candidate wave points | Standard technique |
| 7.2 | Apply standard Elliott Wave rules (wave 3 not shortest, wave 2 doesn't retrace past wave 1 start, wave 4/1 non-overlap, etc.) to label the wave structure — impulse 1-5, corrective A-B-C — at whatever degree fits the visible history | Cite the specific rule set/convention used |
| 7.3 | Full-screen price chart with the labeled wave count overlaid, current wave position shown prominently (e.g. "Wave 4 of 5, Intermediate degree") | This is the centerpiece of the screen |
| 7.4 | Projected completion zone for the next wave using standard Fibonacci relationships (wave 3 extension ratios, wave 5 ≈ wave 1 length from the wave 4 low, etc.) | Shown as a shaded/dashed range on the chart |
| 7.5 | Where the rules genuinely support more than one valid count, show the most probable as primary with the alternative available (e.g. a toggle or secondary overlay) rather than hidden | Ambiguity is a property of the theory — show it, don't force a false single answer |
| 7.6 | One clear, standard label identifying this as Elliott Wave pattern analysis | No need for repeated or multi-layered caveats — one clear label is enough |

**Explicitly excluded — same boundary as Phase 3c/6:**
- No Buy/Sell verdict tied to wave position.
- Turning the wave count into a scored trading signal (as opposed to a labeled chart analysis) goes through the same backtest-first gate as Phase 3/3b.

**Exit criteria:** dedicated screen live and linked from the stock detail page; wave count and projection render clearly on the chart; ambiguous counts show the alternative rather than picking one silently.

**Amendment (2026-08-09) — Phase 7 rebuilt to full Wave Principle coverage.** The
delivered feature supersedes the table above on four points, all widening it:

- **7.2** now covers impulses (with extensions and truncated fifths), leading and
  ending diagonals under their own rule set, zigzags, flats (regular / expanded /
  running), contracting and expanding triangles, and double and triple threes —
  each citing Frost & Prechter by lesson in
  `domain/analytics/elliott/patterns.py`.
- **7.3** shows a nested degree hierarchy, not one degree: the top level is
  labelled at a reversal size coarsened from the requested one, then each leg is
  recursively subdivided, and the UI navigates between degrees.
- **7.4** adds Fibonacci *time* relationships between turning points alongside the
  price ratios. No future turning date is projected — a projected date is a
  forecast.
- **7.5** becomes a documented ranking rather than primary-plus-alternative: up to
  three competitive counts, ordered by a published two-stage method (rule
  admissibility, then weighted guideline adherence), each carrying a
  confidence-in-*labelling* score. That score measures fit to the theory and is
  never presented as a probability of profit, never fed into the score, ranking
  or gates. The exclusions above are unchanged and still hold.

---

## Phase 8 — Chart Pattern Recognition (integrated into 6.6, on-demand)
*Classical chart patterns (unlike Elliott Wave) have well-defined geometric criteria and are the closest thing in technical analysis to an actual studied statistical literature (e.g. Bulkowski's pattern statistics work) — so this sits on firmer ground than Phase 7. Still starts as pattern labeling, not a scored signal, consistent with how every other feature in this backlog earned trust incrementally.*

**Integrates into the existing 6.6 Pattern Recognition card** (not a separate screen) — but pattern recognition runs **on demand**, triggered by an explicit UI element (e.g. a "Detect Patterns" button or similar), not automatically on page load.

| # | Item | Notes |
|---|------|-------|
| 8.1 | Detect the full popular set of classical chart patterns: head & shoulders (+ inverse), double top/double bottom, ascending/descending/symmetrical triangles, flags & pennants, cup & handle, wedges (rising/falling) | Reuse/extend existing `breakout.py` heuristics where they already overlap (e.g. base/breakout detection) rather than duplicating logic |
| 8.2 | On-demand trigger UI element on the stock detail page — pattern recognition only runs when the user explicitly requests it | Matches your instruction; also keeps this from silently adding load/latency to every page view |
| 8.3 | For a detected pattern, overlay the pattern geometry on the price chart (e.g. the cup-and-handle curve, the neckline for head & shoulders) — same visual-first approach as Phase 7 | Reuse `PriceChart.tsx`'s marker/overlay-line props added for Phase 7 where applicable |
| 8.4 | Show pattern name, a quality/completion score, and which structural criteria were met (e.g. "✓ volume contraction in handle, ✓ base depth within range") — same rule-level explainability pattern as the trend template | Consistent with Phase 0's explainability discipline |
| 8.5 | Where multiple patterns are plausible for the same price action, or none clearly qualifies, show that honestly rather than forcing a best-guess label | Same ambiguity-handling principle as Phase 7.5 |

**Explicitly excluded — same boundary as Phase 3/3b/7:**
- No target price, price objective, or profit projection derived from the pattern (e.g. no "cup depth projects to ₹X") presented as validated — that is exactly the class of claim that failed backtesting in Phase 3/3b. If you want a projection zone in the *illustrative, clearly-labeled* style used in Phase 7.4, treat it the same way: a range, not a confident number, with the same light-touch single caveat.
- No Buy/Sell verdict tied to a detected pattern.
- Turning pattern detection into a scored trading signal or feeding it into the ranking/screening engine goes through the same backtest-first gate as Phase 3/3b.

**Exit criteria:** pattern recognition is opt-in via the UI trigger (not automatic); the full popular pattern set is covered; detected patterns show geometry + explainable criteria on the existing 6.6 card; ambiguous/no-match cases are shown honestly.

---

## Phase 9 — TradingView-quality charting
*The app already uses `lightweight-charts` — TradingView's own open-source library — since Phase 6. This phase builds up the existing chart toward TradingView's interaction/feature quality rather than switching to TradingView's licensed Charting Library (that path requires an approval process and was deliberately not chosen).*

| # | Item | Notes |
|---|------|-------|
| 9.1 | Multi-pane layout — indicators like RSI/MACD/ADX render in their own sub-panes below the price pane, synced on the same time axis, instead of only as numbers in the Technical Workbench table | Standard TradingView pattern; `lightweight-charts` supports multi-pane |
| 9.2 | Drawing tools — trendlines, horizontal rays, rectangles, Fibonacci retracement/extension, at minimum | User-drawn, saved per symbol (see 9.5) |
| 9.3 | Full indicator overlay picker on the price pane itself (not just the fixed MA10/20/50/100/200 set from 6.2) — let the user toggle any computed indicator series onto the chart | Reuse indicator values already computed server-side where available (Phase 2 ADX/MACD etc.) rather than inventing new client-side math |
| 9.4 | Crosshair with synced OHLC/indicator readout across all panes, plus keyboard/scroll zoom-and-pan polish | Interaction-quality parity with TradingView, not just visual |
| 9.5 | Persist user chart preferences (selected overlays, drawings, timeframe) per symbol, so the chart doesn't reset on revisit | Needs a lightweight persistence layer (could reuse/extend the watchlist's storage pattern) |
| 9.6 | Reconcile with Phase 7/8 overlays — Elliott Wave wave-count overlay and Phase 8 pattern-geometry overlay must continue to render correctly alongside the new multi-pane/drawing-tool layer, not be replaced by it | Both already use this same chart component's marker/priceLine props |

**Explicitly excluded:**
- No new signal, verdict, or scored output — this phase is presentation/interaction quality only. Any indicator shown must already exist as a validated computation elsewhere in the backend (Phase 0-2); this phase does not compute anything new.
- Do not silently start a TradingView Charting Library licensing application as a shortcut to any of the above — the free-library path was the deliberate choice.

**Exit criteria:** multi-pane indicators, drawing tools, and full overlay picker are functional; Phase 7 and 8 overlays still render correctly on the upgraded chart; chart preferences persist per symbol across page reloads.

---

### How to use this
Paste one phase at a time into a fresh Opus 5 (thinking on) session. Ask it to report back after each phase: what changed, what was tested, and what it could not verify — don't let it mark anything "done" that wasn't actually tested.

**Current status:** Phases 0, 1, 2, 3c, 5, 6, 7 shipped and verified. Phase 3/3b closed as a validated failure (target/reward methodology, not the underlying stop logic). Phase 4 blocked, likely permanently absent a deeper ranking-methodology investigation. Phase 8 (Chart Pattern Recognition, on-demand) and Phase 9 (TradingView-quality charting) are queued next — can be run in either order, though 9 touching the shared chart component first may simplify 8's overlay integration.
