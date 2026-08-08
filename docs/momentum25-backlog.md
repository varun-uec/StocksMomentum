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

---

## Phase 4 — Prediction (base-rate panel, not a directional call)
*Gated on Phase 3 passing backtest AND on data maturity.*

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

### How to use this
Paste one phase at a time into a fresh Opus 5 (thinking on) session. Ask it to report back after each phase: what changed, what was tested, and what it could not verify — don't let it mark anything "done" that wasn't actually tested.
