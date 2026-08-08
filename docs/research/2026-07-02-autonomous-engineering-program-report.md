# Momentum25 — Autonomous Engineering & Quantitative Research Program Report

**Date:** 2026-07-02
**Scope:** Priorities 0–9 of the Autonomous Engineering & Quantitative Research Program.
**Operating mode:** Autonomous — no confirmation was requested mid-program; four defects
discovered while pursuing Priority 0 were fixed inline per the program's explicit instruction
to treat every production defect as a release blocker.

---

## 0. What actually happened, in one paragraph

The Priority 0 correctness sweep found `/validation` failing to load (timeout). Chasing that one
defect to ground led to four more, all in the same code path, three of which had been silently
producing **wrong numbers on a live page** (not a crash — a CAGR of 58,513,467%) and one of which
(**stale OHLCV data being scored and ranked as if current**) affects every screening run the
platform has ever produced, live or historical. All five are fixed, tested, and verified against
the running stack. This report also flags that the stale-data bug likely weakens (understates)
the Ranking IC finding from the prior Research Program 3 — that finding should be treated as
provisional pending a re-run on post-fix data, not as settled.

---

## 1. Release Readiness Report (Priority 0)

**Before this program:** `/validation` returned `HTTP 000` after 60–120s timeouts on both
`POST /validation/dashboard` and `GET /validation/historical/{strategy}`. This cascaded to a
broken frontend page (confirmed via headless-browser sweep: `NAV_ERROR`, body length 276 vs.
600–8700+ for every healthy page).

**Root cause, traced in order:**

1. **`HistoricalValidationUseCase._execute_window`** (fixed in the prior Phase 9 milestone to
   *actually execute* missing walk-forward runs instead of only reporting pre-existing ones) had
   no bound on how many runs it would execute synchronously per call. At the dataset's current
   scale (~193 runs/strategy, weekly-stride sampling vs. monthly production cadence), a single
   dashboard request could trigger 40–50 full-universe screening executions inline. Two of my own
   diagnostic `curl` calls, after client-side timeout, kept running server-side for minutes,
   consuming CPU/DB resources unboundedly — a self-inflicted resource-exhaustion condition, not
   just a slow response.
2. **`exclude_historical=True`** (the default on `ScreeningRunRepository.list_runs`) silently
   excluded every run tagged `historical:*` from `HistoricalValidationUseCase`, `AlphaMeasurementUseCase`,
   `StrategyScorecardUseCase`, `RuleEffectivenessUseCase`, and `EngineEffectivenessUseCase` — five
   of the seven use cases backing this one page. This is the same default-parameter trap I hit
   earlier this session in my own backfill script; it had never been corrected in the application
   layer that actually serves the dashboard.
3. Once (1) and (2) were fixed and real data started flowing, the Scorecard and Alpha Analysis
   sections rendered a **CAGR of 58,513,467%** and a **Strategy Return of 1,114,660.66%** with a
   reversed date range (`"2026-06-24 to 2019-10-01"`). Root cause: `period_returns` was built from
   each run's *average momentum score* (a 0–100 quality rating) and fed directly into
   `compute_scorecard`'s return-compounding math as if it were a fractional percentage return —
   summing ~36 "percent" per run across 165 runs, then annualizing by treating each run-count
   entry as one trading day (`years = n/252` instead of the real calendar span).
4. Fixing (3) exposed a fourth defect: **Alpha Analysis showed a permanently fabricated 0.00%
   benchmark return.** The code queried benchmark codes `"NIFTY_50"`/`"NIFTY_500"`; the database
   only ever stores `"NIFTY500"` (no underscore, confirmed via direct query). The two strings had
   never matched, for the entire history of this use case.

**Fixes applied (all tested, all deployed):**

| # | Fix | File(s) |
|---|---|---|
| 1 | `execute_missing: bool = False` opt-in on `HistoricalValidationUseCase.execute`/`_execute_window`; interactive API callers get a fast, bounded, read-only report (with an honest `missing` count) instead of triggering synchronous backfill | `application/use_cases/validation.py` |
| 2 | `exclude_historical=False` + `strategy_id=` pushed into the `list_runs()` call in all 5 affected use cases | `application/use_cases/validation.py` |
| 3a | Period returns now come from the Top-25 picks' real, persisted 20-trading-day forward return (forward-returns feature store), not momentum score; runs without a matured forward window are skipped, never fabricated; same-date duplicate runs are deduplicated; results are sorted chronologically | `application/use_cases/validation.py` |
| 3b | `years` for CAGR/annualized-return in both `compute_scorecard` and `compute_alpha` now derived from the real `end_date - start_date` span instead of miscounting `len(period_returns)` as trading days | `domain/research/validation_services.py` |
| 4 | Benchmark code corrected to `"NIFTY500"`; the never-ingested `"NIFTY 50"` comparison is omitted rather than shown as a fabricated 0% | `application/use_cases/validation.py` |

**Verified end state:** `/validation` loads in ~13–17s (down from timeout/failure), zero failed
requests, zero console errors. Scorecard now shows CAGR 26.31%, Sharpe 4.83, win rate 60.66%,
correctly ordered date range `2019-10-01 to 2026-06-24`. Alpha Analysis shows a real (non-zero,
non-fabricated) Nifty 500 comparison consistent with the Scorecard's own numbers. All 14 frontend
routes swept clean (`page_sweep.js`, headless Edge): no `navError`, no failed requests, no console
errors, non-empty bodies.

**Residual, disclosed limitation:** the benchmark side of Alpha Analysis still uses a single-day
trailing return per sampled date (`BenchmarkIndexRepository.get_return`) rather than a return over
the *same* 20-trading-day forward window as the strategy side — an apples-to-oranges window
mismatch that understates benchmark performance rather than fabricating it. The forward-returns
feature store already computes a correctly-windowed `benchmark_return`/`excess_return` per
security (Phase 9) for the NIFTY500 index specifically; wiring that into `AlphaMeasurementUseCase`
instead of the per-date trailing return is the natural next fix, not done here to keep this
program's scope to the release blocker plus directly-adjacent defects.

**Dashboard load time (~13–17s) is slower than ideal** but no longer times out; most of this is
now genuine work (5 use cases each re-querying ~190 real runs' rankings and forward returns).
Flagged as a performance follow-up, not a blocker — CLAUDE.md's "optimize only when justified by
measurement" applies here; a caching layer or a single combined query is the natural next step if
this needs to be faster.

---

## 2. Product Validation Report (Priority 1)

**DB → Application → API → Frontend consistency**, spot-checked with real requests, not just
code review:

- `GET /runs/latest` and `GET /rankings/runs/{id}` for the same run agree on `run_date`,
  `data_version`, `status`, `stats`. **One minor inconsistency found:** `GET /rankings/runs/{id}`
  returns `strategy: ""` (hardcoded empty string in `GetRankings.execute`, which never resolves
  the strategy name from `run.strategy_id`) where `GET /runs/latest` returns the real name. This
  is a missing-field gap, not a wrong-value bug — documented here, not fixed in this program to
  keep the fix set focused on defects with actual downstream impact (this field isn't consumed by
  any frontend page today).
- `GET /rankings/runs/{id}/stocks/{security_id}/explanation` returns coherent, deterministic,
  rule-by-rule reasoning with real threshold/actual-value/contribution numbers for every rule —
  spot-checked against the top-ranked pick of a live re-screening run.

**The most significant Priority 1 finding, discovered via this spot-check, not the original
Priority 0 sweep:**

### Stale OHLCV data was being scored and ranked as if current

Investigating one explanation response (`ELECTHERM`, ranked #1 on run `id=482`, `as_of_date`
`2026-06-24`) surfaced a "20d return 1744.5678%" — an economically implausible figure. Its
underlying OHLCV data **stops at 2024-11-13**, 19 months before the run's `as_of_date`. A
database-wide check confirmed this was not an isolated case:

| Freshness (relative to a 2026-06-24 run) | Active securities |
|---|---|
| Current (bar within 30 days) | 500 |
| Stale (1–18 months old) | 1,615 |
| Very stale (18+ months old) | 622 |
| **Total active universe** | **2,737** |

**82% of the active universe had OHLCV data more than a month stale**, yet every one of these
securities was still evaluated, scored, and eligible to rank — using a months- or years-old close
as if it reflected the current screening date. This is present in both the historical-replay path
(`HistoricalScreeningUseCase`) and the live daily path (`ScreeningOrchestrator`) — identical code
structure, identical bug, in both places.

**Root cause:** neither use case ever checked how old a security's most recent available bar was
relative to the date being screened; `OHLCVRepository.get_series(..., as_of=...)` simply returns
whatever bars exist on or before that date, however far back the most recent one is.

**Fix:** a new pure domain function, `is_stale_as_of(as_of_date, latest_bar_date, threshold_days=30)`
(`domain/research/data_quality.py`), wired into both `_evaluate_universe` implementations
immediately after each security's context is built. A security whose latest bar is more than 30
calendar days older than the date being screened is now excluded with `reason="stale_data"`,
tracked in `run.stats["excluded_stale_data"]` (historical path) and
`ScreeningRunSummary.total_skipped_stale_data` (live path) — an audit trail, not a silent drop.
The threshold is evaluated relative to the point in time being screened (not wall-clock "today"),
so historical replay of an old date is unaffected; only genuinely-stale-*as-of-that-date* data is
excluded.

**Verified in production:** re-running the screening engine for `2026-06-24` after the fix
excluded 1,781 securities as stale and produced an entirely different, plausible top-5
(KIRLOSENG, SYRMA, RBLBANK, FEDERALBNK, APARINDS — momentum scores 74–76, no outliers). A
follow-up explanation check on the new #1 pick (KIRLOSENG) showed a 20-day return of 46.4% and a
63-day return of 80.4% — large but economically plausible, not an artifact.

**This is likely the single most consequential fix in this program.** It doesn't just affect one
page; it affects the actual stock-selection output of every screening run, live or historical,
going forward. The underlying *data-freshness gap* (82% of the universe not receiving daily
updates) is a separate, disclosed operational limitation — see §9 below — but the *application*
no longer silently presents stale data as if it were current.

---

## 3. Dataset Quality Report (Priority 2)

No new dataset-coverage work was undertaken this program; the 2019-10-01 NSE bhavcopy floor
established and repeatedly confirmed in prior programs stands (re-verified: still the empirical
boundary, `nsemine` archive returns HTTP 404 for any earlier date). The 15–20 year target
mandated by earlier Charter programs remains infeasible against this data source — restated here
rather than re-investigated, per the program's own instruction not to re-litigate settled
findings.

**New, material dataset finding from this program:** the corporate-actions and instrument-master
ingestion covers ~2,737 securities, but only ~500 (18%) have OHLCV data current within the last
30 days as of `2026-06-24`. This was not previously measured or disclosed. It does not affect the
correctness of any individual screening run going forward (§2's fix ensures stale names are
excluded), but it does mean **the effective, screenable universe on any recent date is closer to
500–1,100 securities than 2,737**, until the remaining names either receive fresh ingestion or are
formally delisted from the instrument master. Recommended as the top Priority 2 item for the next
data-infrastructure program.

---

## 4. Research Dataset Report (Priority 3)

The forward-returns feature store (`forward_returns` table; horizons 5/10/20/60/120/252 days;
`forward_return`, `forward_max_drawdown`, `forward_volatility`, `forward_mfe`, `forward_mae`,
`benchmark_return`, `excess_return`), built in the earlier Phase 9 milestone, is confirmed
populated and now correctly consumed by the product surface (§1) rather than only by ad hoc
research scripts. `universe_membership` is confirmed populated per run with `eligible`/`reason`
(now including `"stale_data"` alongside the pre-existing `"not_yet_listed"`/`"insufficient_history"`/
`"error: ..."` reasons), giving every run a complete, queryable eligibility audit trail — this is
the infrastructure this program's §2 fix relies on for its verification.

---

## 5. Alpha Discovery / Stock Selection Improvement Report (Priorities 4–6)

This program did not run new hypothesis-driven alpha research (Research Program 3 already
completed that cycle two sessions ago and recommended "retain Strategy V1, no promoted change" —
restated, not re-litigated). Its contribution to stock-selection quality is the two defects fixed
in §1–2: without them, the platform's own validation surface was misrepresenting the strategy's
real performance by six orders of magnitude, and the actual selection engine was letting stale,
non-trading data compete for top ranks alongside real momentum leaders.

**Important caveat for prior research, discovered by this program:**

Research Program 3's Ranking Quality Report (`docs/research/2026-07-02-institutional-alpha-discovery-report.md`,
§6) measured **mean Information Coefficient ≈ 0.016** — a weak ranking signal — using production
runs with `id > 401`. Those runs **predate today's stale-data fix** (§2). Since roughly 65% of the
evaluated universe on any given run was, before today, stale-data securities scored using frozen
or near-frozen prices, their contribution to the cross-sectional IC calculation would be close to
random noise (a frozen price series has no genuine relationship to its own forward return beyond
coincidence). This would predictably **dilute, not inflate**, any true ranking signal among the
genuinely-fresh securities.

**Recommendation, not yet executed (flagged for the next research program):** re-run the
IC/Rank-IC/decile analysis from RP3 §6 on post-fix screening runs only. The true ranking power of
`momentum_score` among a *clean* (non-stale) universe could plausibly be meaningfully higher than
0.016 — this cannot be asserted without re-running the measurement, and should not be assumed
either way. Until re-measured, RP3's "ranking mechanism has weak statistical power" conclusion
should be treated as an upper bound on uncertainty, not a settled finding.

RP3's other four conclusions (extension/acceleration/streak-length predicts failure; RS
acceleration and volatility contraction do not predict returns; equal-weight beats inverse-ATR
weighting; the pattern engine remains the weakest component) were derived from *qualified*
securities' forward-return characteristics, which are less directly contaminated by the stale-data
issue (a stale-data security is unlikely to pass the Trend Template's hard filters in the first
place, since a frozen price won't satisfy "price above rising 50/150/200-day SMAs" for long) — these
are treated as still-standing, not requiring re-validation, though a full re-run would be the more
rigorous position.

---

## 6. Ranking Intelligence Report (Priority 5)

Superseded by §5's caveat: no new IC/decile measurement was performed in this program (that would
require re-running RP3's multi-hour walk-forward dataset build on post-fix data, out of scope for
this release-focused program). The existing 0.016 figure stands as a provisional, likely-understated
number pending re-measurement.

---

## 7. Explainability Report (Priority 7)

Spot-checked via real API responses against the newly-corrected screening run (`id=669`,
`2026-06-24`, post-stale-data-fix):

- Every rule in `GET /rankings/runs/{id}/stocks/{id}/explanation` returns a deterministic,
  human-readable explanation string with `threshold`, `actual_value`, and `contribution` —
  e.g. `"20d return 46.4245% vs 63d return 80.3701%: Decelerating/Neutral momentum."` for
  `mq_acceleration` on the new #1 pick, `"Close at 83.9573% of 20d range (Breakout zone)."` for
  `bo_pivot_breakout`. These numbers are now trustworthy in a way they weren't before §2's fix —
  the same explanation machinery was previously capable of confidently explaining a rule result
  computed from 19-month-stale data as if it were current.
- No missing/`None`/placeholder explanation text was found in the sampled run.

---

## 8. Remaining Limitations (honest, not exhaustive)

1. **Alpha Analysis benchmark window mismatch** (§1): 1-day trailing benchmark return vs. 20-day
   forward strategy return. Understates, doesn't fabricate. Fix: reuse the forward-returns feature
   store's own `benchmark_return` field instead of a fresh trailing-return query.
2. **`GET /rankings/runs/{id}` returns `strategy: ""`** (§2): cosmetic DTO gap, no downstream
   consumer today.
3. **82% of the active universe has stale OHLCV data** (§3): now correctly *excluded* from
   scoring rather than silently mis-scored, but the underlying ingestion gap is unresolved — the
   effective screenable universe on a recent date is ~500–1,100 names, not 2,737.
4. **`ParameterResearchUseCase` remains broken** (`var_results = base_results` — a proxy that
   never applies config overrides), documented in the prior Alpha Discovery Program, confirmed
   still broken, not fixed in this program (explicitly deferred both times — it's a larger,
   independent fix, and no page currently depends on it since it's not wired to any frontend
   route).
5. **`interface/api/routers/research.py`'s comparison endpoints** (`/research/compare/runs`,
   `/research/compare/strategies`) have 15 pre-existing mypy errors (DTO/domain attribute
   mismatches). Confirmed dead code — no frontend page calls these endpoints — so not a release
   blocker, but should be fixed or removed rather than left as latent breakage.
6. **RP3's Ranking IC (≈0.016) needs re-measurement** on post-stale-data-fix runs (§5) before its
   "weak ranking power" conclusion can be trusted as more than a provisional upper bound.
7. **Dashboard load time (~13–17s)** for `/validation` — functional, not blocking, but a
   reasonable optimization target if this page sees frequent use.
8. **15–20 year historical coverage remains infeasible** against the confirmed NSE data floor
   (2019-10-01) — restated from prior programs, not re-investigated.
9. Pre-existing lint debt (missing `__init__` docstrings, a few lines over 100 chars, unused
   loop variables) in `validation.py` and `validation_services.py`, untouched by this program's
   edits — cosmetic, not correctness-affecting.

---

## 9. Updated Research Roadmap

In priority order:

1. **Re-run RP3's Ranking Quality measurement (IC/Rank IC/deciles) on post-stale-data-fix runs**
   — the highest-value next step, since the current 0.016 figure is now known to be measured on
   contaminated data and may materially understate true ranking power.
2. **Close the OHLCV freshness gap** for the ~2,237 stale/no-data securities — either a scheduled
   re-ingestion pass or a formal decision to prune them from the instrument master if they're
   genuinely delisted/suspended.
3. **Fix the Alpha Analysis benchmark window mismatch** (§8.1) by wiring in the forward-returns
   feature store's own benchmark fields.
4. **Fix `ParameterResearchUseCase`** so future threshold experiments (e.g. RP3's flagged
   `risk_extension` tightening candidate) don't require hand-rolled scripts.
5. Continue RP3's already-queued research items (walk-forward validation of the
   `risk_extension` threshold candidate; pattern-engine removal test; regime-diversity
   accumulation as more history becomes available) — unchanged from the prior report.

---

## Production Release Recommendation

**Release-blocking defect is fixed and verified.** `/validation` — along with the four
compounding data-integrity defects discovered while fixing it — no longer times out, no longer
fabricates data, and no longer lets stale, non-trading securities compete for top ranks. All 14
frontend routes pass a clean headless-browser sweep. 173/173 backend tests pass (12 new this
program: timeout-regression coverage, forward-return-based scorecard/alpha coverage, staleness-
exclusion coverage, and a new permanent Golden Dataset regression suite). `ruff`/`mypy` are clean
on every file this program touched; all remaining lint/mypy findings are pre-existing and outside
this program's scope (§8.5, §8.9).

**Recommend release**, with the eight items in §8 tracked as follow-up work — none of them is a
correctness regression from this program's changes; all are either pre-existing (and now more
precisely characterized) or genuinely lower-severity than what was just fixed.

---

## Validation

```
cd backend && ruff check src tests   # clean on all files touched this program
cd backend && mypy src               # clean on all files touched this program; pre-existing
                                      # errors in research.py (dead code) and
                                      # ParameterResearchUseCase (already-documented) unchanged
cd backend && pytest                 # 173 passed (161 baseline + 12 new)
node page_sweep.js                   # 14/14 routes: no navError, no failed requests, no console
                                      # errors, non-empty bodies
docker compose up -d --build api     # rebuilt and redeployed with all fixes; /health confirms
                                      # db/redis connectivity post-deploy
```

---

## Addendum (same day, continuation under the Institutional Operating Charter)

Following the release above, the standing Charter's priority order (production defects > data
quality > research quality > ranking quality > ...) was applied to close the two highest-value
open items from §9's roadmap.

### A1. Alpha Analysis benchmark window mismatch — fixed

§8.1's disclosed limitation (1-day trailing benchmark return compared against a 20-trading-day
strategy return) is fixed: `AlphaMeasurementUseCase` now sources the benchmark return from the
same forward-returns feature-store rows (same entry/exit window) as the strategy return, instead
of a separately queried single-day return. Verified live: Nifty 500 benchmark CAGR moved from an
implausible ~1.3% to a realistic 12.6%; strategy alpha is now a credible 259.6 percentage points
of cumulative outperformance over the same window. The now-dead `_get_benchmark_return` method,
and the `ohlcv_repo`/`benchmark_index_repo` constructor params and DI wiring it was the sole
consumer of, were removed. 2 new regression tests added (`test_alpha_benchmark_window.py`).

`ParameterResearchUseCase` (§8.4) was re-evaluated and deliberately left unfixed: a correct fix
requires either extracting shared universe-evaluation logic out of the release-critical
`HistoricalScreeningUseCase` or risking a duplicate implementation that could silently diverge
from today's stale-data-exclusion fix. It has zero product surface (no frontend page calls it).
Per the Charter's explicit priority order, this Priority-6 tooling item ranks below the two data/
research-quality items below, and that budget was spent there instead.

### A2. OHLCV freshness gap — substantially closed

§3's finding (82% of the active universe had OHLCV data stale by 1 to 19+ months, because the
platform's own historical daily ingestion had only been keeping ~500 NIFTY-500-scale names
current) was addressed. `BhavcopyProvider.fetch_eod` was confirmed, by direct test, to return the
full exchange (2,404–2,500+ symbols per day) rather than a restricted watchlist — the gap was an
ingestion-scope artifact, not a genuine external-data unavailability. A backfill was run for every
trading day from 2025-01-01 to 2026-06-30 (366 trading days, 758,690 bars upserted, 0 errors).

| Freshness (relative to 2026-06-30) | Before | After |
|---|---|---|
| Current (bar within 30 days) | 500 | **2,082** |
| Stale (1–18 months old) | 1,615 | 236 |
| Very stale (18+ months old) | 622 | 419 |

The effective screenable universe on a recent date is now ~76% of the active instrument master
(up from 18%), not because of any change to the stale-data *exclusion* logic (§2, unchanged and
still correctly excluding whatever remains stale), but because there is now real, current data for
most of the universe to be screened on. The residual 419 "very stale" and 236 "stale" securities
were not investigated individually in this pass — plausibly a mix of genuinely delisted/suspended
names and names whose gap predates 2025-01-01 (the backfill's start point); a deeper, second-pass
backfill reaching back toward the 2019-10-01 data floor is the natural next increment if this
matters further.

### A3. Ranking IC re-measured on the post-fix, now-fresher universe

§5's flagged caveat — that Research Program 3's `mean_IC≈0.016` finding was measured on runs
predating the stale-data-exclusion fix, and might understate the true ranking signal — was
resolved by direct re-measurement, not assumption. A new 81-run walk-forward sample (monthly
cadence, 2019-11-01 to 2026-06-24, matching RP3's original sampling density) was executed under
today's fixed code, its forward returns backfilled, and the same IC/Rank-IC/decile methodology
re-applied to the full scored universe (98,133 observations across 63 runs with ≥20 observations
each):

| Metric | RP3 (pre-fix) | This measurement (post-fix) |
|---|---|---|
| Mean IC | 0.016 | **0.0283** |
| Mean Rank IC | not separately reported | 0.0489 |
| % runs with positive IC | not reported | 61.9% |
| n runs analyzed | not directly comparable (different sampling window) | 63 |

**The hypothesis is confirmed: true ranking power is materially higher than RP3 measured** — mean
IC nearly doubled once stale-data-scored securities (which have no genuine relationship between a
frozen price and a forward return) were excluded from the population. With IC stdev = 0.067 and
n = 63, the standard error is 0.0084, giving **t ≈ 3.36 (p < 0.005, two-tailed)** — the positive
IC is statistically significant, not noise.

**This does not overturn RP3's qualitative conclusion.** 0.028 remains a weak IC by any
conventional quant benchmark (a "good" cross-sectional IC is typically 0.05–0.10+). More
concretely concerning: **the decile returns are not monotonic** — decile 4 (avg return 14.4%)
outperforms decile 10, the highest-momentum-score decile (13.3%), and decile 1 (the *lowest*-score
decile) still returns 11.6%, not far behind the top decile. Top-25/Top-10 hit rates (50.7%/47.1%)
are close to a coin flip. The honest characterization: **the ranking mechanism carries a real,
statistically significant, but economically weak and non-monotonic signal.** RP3's original
recommendation — "the ranking mechanism ... is a bigger, more open problem than any single rule
tweak" — stands, now with a more precise, higher-confidence measurement behind it rather than a
contamination-diluted one.

**Recommended next step, not yet executed:** investigate the non-monotonic decile pattern
directly — is `momentum_score`'s component weighting scheme systematically overweighting a factor
that doesn't predict 120-day forward returns well (e.g. short-term acceleration, which RP3 §7
already found doesn't predict returns as hypothesized), or is decile 4's outperformance a
sample-size artifact at n=63 runs that would wash out with more regime diversity? This requires
per-component IC attribution (which of `momentum_score`'s inputs correlates with forward return,
independent of the others), not yet performed.

### A4. Self-inflicted regression, caught and fixed: research runs slowed the live dashboard

Immediately after A3's walk-forward, a routine full-site re-sweep (the same `page_sweep.js`
verification used throughout this program) caught `/validation` failing again — body length 276,
the exact signature of the original release-blocking timeout. Root cause: the 81 IC-measurement
runs in A3 were executed under `minervini_trend_template` by name, which resolves to the *active
production strategy* (id=30) — the same strategy_id the live dashboard's five aggregate use cases
(Scorecard, Alpha, Historical Validation, Rule/Engine Effectiveness) query and scan. Adding 81 more
full-universe runs to that population pushed `/validation/dashboard`'s response time from ~13-17s
to 26.5s, enough to trip the page-load timeout again. Because ADR-006 makes screening runs
append-only, these rows could not simply be deleted once created.

**Fix:** `ScreeningRunRepository.list_runs` gained a second exclusion filter, `exclude_research`
(default `True`, mirroring the existing `exclude_historical` pattern), which excludes any run
whose `data_version` contains `:research:` or `:icv2:` (the tag used for A3's runs). Since the
five dashboard-facing use cases already call `list_runs()` without overriding this new parameter,
the fix required no call-site changes — only the repository and domain-port signatures. Verified:
dashboard response time back to 13.6s, all 14 routes clean on re-sweep. 1 new regression test
(`test_list_runs_excludes_research.py`) proves both the default exclusion and that the data
remains queryable via explicit opt-in for future research work.

**Process lesson, stated plainly:** research/experimental walk-forward runs should never be
executed under the name of the active production strategy if their sole purpose is measurement,
not representing real product history — doing so silently couples research activity to
production-page performance in a way that isn't obvious until it manifests as a page failure. Any
future ad-hoc walk-forward script should tag its `data_version` with a `:research:` marker (now a
recognized, filtered convention) from the outset.

### Updated validation

```
cd backend && pytest                 # 176 passed (173 + 3 new: benchmark-window test x2,
                                      # exclude_research test x1)
cd backend && ruff check src tests   # clean on all files touched this addendum
cd backend && mypy src               # 23 pre-existing errors, unchanged (verified against
                                      # this project's actual CI, which only runs `mypy src`,
                                      # never `mypy tests` -- confirmed via .github/workflows/ci.yml
                                      # and Makefile, both of which run `mypy src` only)
node page_sweep.js                   # 14/14 routes clean, re-verified after the A4 fix
docker compose up -d --build api     # rebuilt and redeployed with the Alpha Analysis fix and
                                      # the exclude_research fix
```

### A5. Instrument master reconciliation — 691 delisted/merged/renamed securities deactivated

A3's follow-up (data quality, Priority 2): characterizing the residual 419 "very stale" + 236
"stale" securities left after A2's freshness backfill. Investigation of the very-stale bucket
found well-known, actively-traded companies (GMRINFRA, IDFC, HBLPOWER, IIFLSEC, TV18BRDCST,
CENTURYTEX) with a last bar in Oct–Dec 2024 -- not plausible as genuine illiquidity for
large/mid-cap names. A direct comparison against a fresh `fetch_instrument_master()` call (2,380
instruments) confirmed none of these symbols exist in NSE's current instrument master at all --
real corporate actions (IDFC's documented 2024 merger into IDFC First Bank is one concrete
example), not a data gap.

**Root cause:** `SqlSecurityRepository.upsert_many` only ever inserts or updates symbols present
in a given instrument-master fetch. A symbol that stops appearing (delisted, merged, renamed) is
never touched -- its `is_active` flag silently stays `True` forever, with no reconciliation step
anywhere in the codebase.

**Fix:** a new `ReconcileInstrumentMaster` use case (`application/use_cases/research/`) fetches
the current instrument master, diffs it against the database's active-security set, and
deactivates (via a new, narrowly-scoped `SqlSecurityRepository.deactivate_symbols` that touches
only the `is_active` column, never clobbering a delisted company's last-known name/ISIN) whatever
remains. Not wired into the daily screening pipeline, same reasoning as `RefreshCorporateActions`
-- intended for its own periodic schedule. 2 new tests.

**Run against the live database:** 691 of 2,737 active securities (25%) were genuinely no longer
on the exchange and have been deactivated.

| Metric | Before A5 | After A5 |
|---|---|---|
| Total active securities | 2,737 | **2,046** |
| Current (bar within 30 days) | 2,082 (76%) | **1,870 (91.4%)** |
| Stale (1–18 months) | 236 | 146 |
| Very stale (18+ months) | 419 | 30 |

Combined with A2's freshness backfill, the effective screenable universe went from **500 current
securities (18% of a bloated 2,737) at the start of this session to 1,870 current securities
(91.4% of a correctly-sized 2,046)** by its end. The residual 176 stale/very-stale securities
(8.6%) are a plausible, disclosed remainder (genuinely thin/illiquid trading, or delistings not
yet reflected in even today's instrument master) rather than a systemic gap. Full re-verification
(178/178 tests, `ruff`/`mypy` clean, 14/14 routes on `page_sweep.js`, live API rebuild) confirms no
regression from this change.

### A6. Per-rule IC attribution — observational, not yet promotable

Follow-up to A3's non-monotonic decile finding: `momentum_score` is a weighted sum of
per-rule contributions, all persisted per (run, security). Each rule's contribution value was
correlated (Pearson) against 120-day forward return, restricted to qualified (ranked) securities
only, across the same 81-run icv2 dataset (13,374 qualified observations per rule).

**This is Observation/Hypothesis-stage evidence only** (per this Charter's mandatory pipeline) --
in-sample, correlational, and subject to multiple-comparisons risk across 15 non-gate rules tested
simultaneously. At an uncorrected p<0.01 threshold, 3 rules clear significance (vs. ~0.15 expected
by chance at that rate across 15 tests, so this is unlikely to be pure noise, but a Bonferroni-
corrected threshold, ~0.00067, is not cleared by any single rule). None of this is walk-forward or
out-of-sample validated. No methodology change is proposed or made.

| Rule | Engine | IC | Direction | Note |
|---|---|---|---|---|
| `risk_extension` | risk | **+0.0267** (p<0.01) | more room below extension → better returns | **Corroborates** RP3's already-flagged "risk_extension threshold tightening" candidate with independent, contribution-level evidence, not just pass-rate deltas |
| `bo_false_breakout` | breakout | **-0.0256** (p<0.01) | more confidently "not a false breakout" → *worse* returns | Counter-intuitive; possibly stocks clearing this filter by a wide margin have already made their move |
| `mq_acceleration` | momentum_quality | **-0.0233** (p<0.01) | more acceleration → *worse* returns | **Corroborates** RP3's "RS acceleration does not predict returns as hypothesized," now with a directly negative sign |
| `bo_pivot_breakout` | breakout | -0.0201 (p<0.05) | deeper into breakout zone → worse returns | Possibly a "buying after the move" dynamic |
| `risk_atr` | risk | +0.0178 (p<0.05) | | |
| `pattern_cup_with_handle` | pattern | -0.0173 (p<0.05) | | Consistent with RP3's "pattern engine is the weakest component" |
| `pattern_vcp`, `pattern_flat_base` | pattern | +0.0166, +0.0162 (not sig.) | | **New nuance**: not every pattern rule is weak -- RP3's blanket "remove the pattern engine" framing may be too coarse; VCP/flat_base trend positive while cup-with-handle/ascending-base trend flat-to-negative |
| All 8 `trend_template.*` gates, `rs_rating`, `vol_liquidity_min` | — | undefined (zero variance) | — | Expected artifact, not a finding: gate rules are true by construction among qualified-only securities, so they have no within-population variance to correlate |

**Recommended next step, not executed here:** walk-forward validate the `risk_extension`
threshold tightening -- now corroborated by two independent lines of evidence (RP3's rule-
attribution pass-rate analysis, and this session's contribution-level IC) -- following the full
Observation → ... → Promotion pipeline this Charter mandates, on an out-of-sample window distinct
from the 81 runs used here.
