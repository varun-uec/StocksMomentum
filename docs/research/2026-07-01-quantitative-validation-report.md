# Momentum25 India — Quantitative Validation & Benchmark Report

**Date:** 2026-07-01
**Author:** Engineering (automated quantitative review, Release Readiness Review 2)
**Status:** Final for this review cycle. Superseded by any future report with more historical data.

---

## Executive Summary

Momentum25's production strategy (`minervini_trend_template`) was benchmarked against four
simpler, deterministic momentum strategies (pure trailing-return momentum, RS-only, Trend-Template-only,
and equal-weight composite) using real NSE price data and a real NIFTY 500 benchmark, via
forward-return backtesting over 10 overlapping snapshots.

**The honest finding: on this sample, the production strategy did not clearly outperform the
simplest RS-only benchmark.** Benchmark B (rank solely by blended RS Rating, with only a liquidity
gate) produced a higher average return, higher Sharpe ratio, and higher alpha than the full
production strategy. Benchmark C (Trend Template gate with no additional scoring) also modestly
outperformed production. This is reported plainly because the mandate for this review is evidence
over intuition — the data does not currently support a claim that Momentum25's additional engines
(Pattern, Breakout, Momentum Quality, Risk) as currently weighted create measurable alpha beyond
what the Trend Template gate and RS ranking alone already capture, **in this specific short,
strongly bullish window.**

Two significant, previously-undiscovered engineering defects were found and fixed as a
precondition for this analysis being possible at all (Section "Defects Found & Fixed"). Before
these fixes, historical backtesting was completely non-functional (always zero qualifying stocks)
and the existing rule-effectiveness analysis was methodologically circular (correlating rules
against the same score they help compute, not real returns).

**The central limitation governing every conclusion in this report: only 335 real trading days
(2025-02-17 to 2026-06-30) of stock-level price history are backfilled.** Indicators need ~277
days of lookback, leaving a valid backtest window of only ~48 trading days (2026-04-06 to
2026-06-25) — a single, single-regime (bullish) window with no bear or sideways period
represented. All CAGR/Sharpe/Alpha/Beta figures below are **directional evidence from a small,
overlapping sample, not statistically powered conclusions.** The user explicitly acknowledged and
accepted this constraint rather than pursuing a multi-hour, multi-year re-backfill (documented in
the review conversation); genuine 2015-present validation requires that re-backfill as dedicated
follow-up work.

---

## Defects Found & Fixed (precondition for this analysis)

### 1. Historical screening was completely non-functional

`HistoricalScreeningUseCase` (the only tool capable of replaying the strategy at a past date without
lookahead — required for any backtest) never computed or injected `rs_rating` into the indicator set
it builds. Since `tt_rs_rating_min` is part of the mandatory 8-rule Trend Template gate, and a `None`
RS rating always fails that rule, **every historical run, at every date, for every stock, always
returned zero qualifying stocks.** Verified empirically before the fix (`2026-05-15`: `passed=0`)
and after (`passed=66`).

**Fix:** extracted the RS-rating computation (already correctly implemented in the live daily
`ScreeningOrchestrator`) into a shared function, `application/services/rs_ratings.py`, and wired it
into `HistoricalScreeningUseCase` too. This both fixes the bug and removes a duplicated-business-logic
violation (the same computation previously existed only in one of the two call sites).

### 2. Rule/engine effectiveness analysis was circular

The existing `RuleEffectivenessUseCase` / `analyze_rule_effectiveness` (built in an earlier
milestone's research platform) used each run's **average momentum score** as a "period return
proxy" to correlate against rule pass/fail. Since several rules directly feed into that same score,
any "this rule correlates with better performance" conclusion was substantially circular (a rule
correlating with the score it contributes to is not evidence of investment performance). Separately,
its index-alignment between per-rule evaluations and per-run "returns" was structurally mismatched
once more than one run was analyzed (list lengths and orderings didn't correspond).

**Not fixed in application code this cycle** (fixing it properly requires the same real
forward-return infrastructure built for this report, and doing so safely deserves its own dedicated
pass rather than a rushed change to shipped analysis code). Instead, a standalone, correct analysis
was built for this report directly from real forward returns (see "Rule Effectiveness Analysis"
below). **Recommendation:** apply the same real-forward-return methodology to
`RuleEffectivenessUseCase` as a follow-up engineering task.

### 3. Benchmark index data was completely absent

`benchmark_index_daily` had zero rows — Alpha, Beta, Information Ratio, and Tracking Error were
never actually computable against a real index, despite API fields existing for them. Fixed by
ingesting NIFTY 500 daily closes back to 2015 (a single fast API call, unlike the slow per-day
stock-level bhavcopy backfill) — 2,846 rows, 2015-01-01 to 2026-07-01.

---

## Methodology

### Benchmark Strategy Definitions

All five strategies were implemented as real, independently reproducible strategy configs (ADR-005:
strategy-as-config), not simulated post-hoc — each was actually screened via
`HistoricalScreeningUseCase` at every snapshot date.

| ID | Name | Gate(s) | Scoring |
|---|---|---|---|
| A | Pure 52-week Momentum | Liquidity only | Rank solely by 252-day trailing return |
| B | Relative Strength Only | Liquidity only | Rank solely by blended RS Rating (63/126/189/252d, weighted 0.4/0.2/0.2/0.2 — same blend as production) |
| C | Trend Template Only | Full 8-rule Trend Template + liquidity | No differentiation among passers (constant score; ranked by RS as tie-break only) |
| D | Equal-Weight Composite | Same gates as production | All 7 engines weighted equally (1.0 each), vs. production's weighted scheme |
| E | Momentum25 Production | Full 8-rule Trend Template + liquidity | Production weights (Trend Template 3.0, RS 2.0, Breakout 1.5, Volume/Pattern/Momentum Quality 1.0, Risk 0.5) |

Configs: `docs/architecture/strategies/benchmark_{a,b,c,d}_*.json`.

**Benchmark F (NIFTY Momentum Index)** was not implemented as a stock-picking comparison — no
historical constituent-level data for a published index like Nifty200 Momentum 30 was available
via the data source used this session. The NIFTY 500 **index return** (not a momentum sub-index)
was used as the market benchmark for Alpha/Beta/Information Ratio instead. This is an explicit,
documented gap, not a silent omission.

### Experimental Design

- **Universe:** live NIFTY 500 constituents (502 securities backfilled), same for every benchmark.
- **Snapshots:** 10 weekly dates within the valid window (2026-04-06 to 2026-06-25), each requiring
  ≥277 trading days of prior history (no lookahead — each screening run only used data available as
  of that date).
- **Holding period:** 10 trading days (~2 calendar weeks) forward return, equal-weighted across each
  strategy's Top 25 qualifying stocks as of the snapshot date.
- **Benchmark return:** NIFTY 500 index return over the identical 10-trading-day window.
- All 10 snapshots for all 5 strategies successfully priced 25/25 stocks — no missing data.

---

## Historical Results — Performance Table

| Strategy | Avg Return/Period | Median | Volatility | Win Rate | CAGR* | Sharpe* | Sortino* | Max DD | Profit Factor | Alpha* | Beta | Info Ratio* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A — Pure Momentum | 1.84% | 2.11% | 4.86% | 70% | 58.3% | 1.90 | 3.88 | -6.72% | 2.60 | 5.1% | 1.18 | 1.01 |
| B — RS Only | **2.96%** | **3.46%** | 4.64% | 60% | **108.5%** | **3.20** | **9.04** | -4.83% | **5.14** | **39.6%** | 1.00 | **2.82** |
| C — Trend Template Only | 2.81% | 3.02% | 4.46% | 70% | 100.9% | 3.16 | 9.10 | -4.16% | 4.89 | 34.7% | 1.03 | 3.06 |
| D — Equal Weight | 1.75% | 1.18% | 3.33% | **80%** | 54.9% | 2.64 | 6.40 | -5.03% | 4.46 | 16.8% | 0.78 | 0.99 |
| **E — Production** | 2.12% | 1.50% | 3.46% | **80%** | 69.8% | 3.08 | 7.36 | **-4.69%** | 4.46→5.52 | 25.0% | 0.81 | 2.00 |
| NIFTY 500 (benchmark) | 1.39% | — | — | — | — | — | — | — | — | — | — | — |

\*Annualized from a 10-observation, overlapping-window sample — directional, not statistically powered (see Limitations).

**Every strategy beat the NIFTY 500 average period return** (1.39%) over this window — including the
loosest benchmark (A). This says more about the strength of the specific 2.5-month window (a
persistently bullish period; every strategy's Beta and Alpha estimates below reflect that single
regime) than about any one methodology's edge.

---

## Strategy Comparison — Does Momentum25 Outperform?

**Not conclusively, on this data.** Ranking by every risk-adjusted metric:

1. **B (RS Only)** — highest return, Sharpe, Sortino, alpha, information ratio, profit factor.
2. **C (Trend Template Only)** — a close second on nearly every metric.
3. **E (Production)** — third on raw risk-adjusted return, but tied for the **best win rate (80%)**
   and second-lowest volatility — i.e., production is the most *consistent*, not the highest-*return*
   strategy in this sample.
4. **D (Equal Weight)** — similar consistency profile to E, slightly lower absolute returns.
5. **A (Pure Momentum, loosest gate)** — weakest risk-adjusted metrics of the five, though still
   beat the index.

### Why might this be?

- **Extension effects in a strong bull window.** The Risk engine's extension check and the Breakout
  engine's "fresh pivot" requirement plausibly excluded some already-running stocks that continued
  to run further in this specific 10-day window — the rule-level evidence below shows `tt_close_above_sma50`,
  `bo_pivot_breakout`, `mq_acceleration`, and `pattern_vcp` all had **negative** return deltas (stocks
  *failing* these rules had *higher* subsequent 10-day returns than stocks passing them). In a
  persistent uptrend, "not yet extended" can mean "earlier in the move," which this short window
  rewards.
- **No drawdown period is represented.** Every strategy's max drawdown in this window is mild
  (-4% to -7%). The Risk/Breakout/Pattern engines exist specifically to protect against poor
  entries and false starts — protection that cannot be measured without a genuine correction or
  bear period in the data, which this window does not contain. **This is the single most important
  caveat to the entire comparison:** the extra engines may earn their complexity precisely in
  conditions this backtest cannot see.
- **Small sample instability.** With N=10 overlapping snapshots spanning ~2.5 months, a Sharpe
  difference of 3.20 vs 3.08 is well within noise. The consistent pattern (B/C > E > D > A on raw
  return, E/D > B/C/A on win rate) is more informative than any single point estimate.

---

## Rule Effectiveness Analysis

Computed from real forward 10-day returns per security per rule evaluation across all 10
production-strategy backtest snapshots (4,611 rule evaluations per rule; not the circular
score-based proxy — see Defects Found & Fixed).

### Confirmed dead rules (0% pass rate — never contribute in this universe)

| Rule | Engine | Why |
|---|---|---|
| `rs_sector_relative` | relative_strength | No sector classification data ingested |
| `rs_industry_relative` | relative_strength | No industry classification data ingested |
| `rs_line_uptrend` | relative_strength | RS-line slope never populated (documented gap from Milestone A) |
| `pattern_high_tight_flag` | pattern | Never detected in this universe/window (may simply be rare; insufficient evidence to call it broken vs. genuinely rare) |

These four rules currently receive weight but contribute zero information, every time, in every
run. **Recommendation: set their weight to 0 (or remove) until the underlying data gap is closed**
(sector/industry classification ingestion), since carrying dead weight with a non-zero weight
silently understates the effective weight of the rules that do contribute.

### Rules with the largest negative return delta (passing correlates with *lower* subsequent returns, in this window)

| Rule | Pass Rate | Return when Pass | Return when Fail | Delta |
|---|---|---|---|---|
| `tt_close_above_sma50` | 60.3% | 1.20% | 3.82% | **-2.62%** |
| `bo_false_breakout` | 57.2% | 1.56% | 3.14% | -1.58% |
| `bo_pivot_breakout` | 39.6% | 1.30% | 2.85% | -1.55% |
| `pattern_vcp` | 76.0% | 1.91% | 3.28% | -1.37% |
| `mq_acceleration` | 36.7% | 1.09% | 2.91% | -1.83% |
| `tt_near_52w_high` | 59.2% | 1.72% | 3.00% | -1.28% |

As discussed above, this is consistent with an "already-extended vs. earlier-in-the-move" dynamic
specific to a short window in a strong trend, not necessarily evidence these rules are wrong over a
full market cycle — but it is real, deterministic evidence that **in this window**, these rules did
not add the value their design intends, and is worth re-testing once longer/more varied history is
available.

### Rules with a positive return delta

| Rule | Pass Rate | Delta | Note |
|---|---|---|---|
| `risk_atr` | ~100% | +8.7% | Based on a very small failing-sample (almost everyone passes) — likely noise, not a reliable signal from this data |
| `risk_rr` | 12.3% | +1.04% | Small pass rate; modest positive signal |
| `risk_extension` | 98.2% | +0.4% | Negligible, same small-failing-sample caveat as `risk_atr` |
| `rs_rating` / `tt_rs_rating_min` | 29.3% | +0.15% | Essentially flat in this sample |

No rule shows a large, reliable *positive* delta with a well-populated failing sample. This is a
genuinely uncomfortable finding worth stating plainly: **in this specific window, no individual
rule demonstrated strong, unambiguous positive predictive value for forward 10-day returns.** The
strategy's real value (evidenced by strong win rates and controlled drawdown at the portfolio
level) appears to come from the *combination and gating* of rules — i.e., from the overall Trend
Template discipline plus RS ranking — rather than from any single scoring rule's marginal
contribution.

---

## Engine Effectiveness Analysis

| Engine | Pass Rate | Return when Pass | Return when Fail | Delta |
|---|---|---|---|---|
| relative_strength | 7.3%* | 2.34% | 2.23% | +0.11% |
| risk | 70.2% | 2.30% | 2.11% | +0.19% |
| volume_accumulation | 56.5% | 2.09% | 2.44% | -0.35% |
| pattern | 28.2% | 1.77% | 2.43% | -0.66% |
| trend_template | 41.3% | 1.78% | 2.57% | -0.79% |
| momentum_quality | 32.6% | 1.51% | 2.59% | -1.09% |
| breakout | 44.8% | 1.57% | 2.79% | -1.22% |

\* `relative_strength`'s low "pass rate" reflects that this is an all-4-rules-pass rate including the
three dead rules above (which never pass) — not a meaningful standalone figure; interpret the
individual `rs_rating` rule figure instead.

Directionally, `risk` and `relative_strength` show small positive deltas; `breakout`, `momentum_quality`,
and `trend_template` show negative deltas in this window, for the same "already-extended" reasons
discussed above. None of these deltas should be read as strongly significant given the sample size.

---

## Sensitivity Analysis

Formal parameter sweeps (systematically varying individual thresholds/weights and re-measuring) were
not run this cycle given time and data constraints. Instead, the A/B/C/D/E comparison itself provides
real sensitivity evidence:

- **Gate sensitivity (A → C):** tightening the gate from "liquidity only" (A) to "full Trend Template"
  (C) improved Sharpe from 1.90 to 3.16 and reduced max drawdown from -6.72% to -4.16% — **the Trend
  Template gate demonstrably adds value over a looser liquidity-only filter**, in this data.
- **Weight sensitivity (D → E):** production's weighted scheme modestly outperformed naive equal
  weighting on Sharpe (3.08 vs 2.64) and average return (2.12% vs 1.75%), but not on win rate (tied
  at 80%) or volatility (D was actually lower). **The production weighting scheme shows a small,
  not dramatic, edge over equal weighting** in this sample.
- **Scoring-complexity sensitivity (B/C → E):** adding Pattern/Breakout/Momentum Quality/Risk scoring
  on top of Trend Template + RS did **not** improve risk-adjusted return in this window (E trails
  B and C on Sharpe, CAGR, and alpha), though it modestly improved consistency (win rate, drawdown).

---

## Robustness

Not meaningfully testable this cycle: the available window is a single ~2.5-month bullish regime
with no sector, market-cap, or multi-horizon variation possible within it (all snapshots draw from
the same 502-stock universe over the same short calendar span). This is a genuine, acknowledged gap
requiring the extended historical backfill discussed in Limitations.

---

## Explainability Validation

Every figure in this report traces to a real, persisted, deterministic artifact:

- Every backtest snapshot is a real `screening_runs` row (`data_version` prefixed `historical:`),
  independently re-queryable via the existing `/rankings/runs/{id}` and stock explanation endpoints.
- Every rule effectiveness observation traces to a real `rule_results` row plus real `ohlcv_daily`
  closes for the forward-return calculation — no synthetic or simulated figures.
- The NIFTY 500 benchmark returns trace to real `benchmark_index_daily` rows (newly ingested this
  cycle, sourced from NSE's own index history).

No performance claim in this report lacks a deterministic, re-derivable source.

---

## Limitations

1. **Data depth is the dominant limitation.** 335 real trading days total; only 48 are usable as
   backtest snapshot dates; only 10 non-degenerate weekly snapshots were drawn from that window.
   This is nowhere near "2015-present" and does not include a single bear or genuinely sideways
   period. Every CAGR/Sharpe/Alpha figure in this report is a small-sample point estimate.
2. **Overlapping snapshots.** Weekly snapshots with a 10-day forward window overlap substantially,
   inflating apparent sample size without adding fully independent information.
3. **Single holding period tested.** Only a 10-trading-day forward window was measured; results may
   differ meaningfully at 21-day, 63-day, or longer horizons (relevant given Momentum25 also ships
   multiple Momentum Horizon strategies).
4. **No regime, sector, or market-cap segmentation was possible** given the data window.
5. **Benchmark F (a genuine NIFTY momentum index) was not available** and was substituted with the
   plain NIFTY 500 index return.
6. **`RuleEffectivenessUseCase`'s existing application-code implementation remains methodologically
   flawed** (circular score-proxy correlation); this report bypassed it with a standalone, correct
   analysis rather than fixing the shipped code this cycle.
7. **No transaction costs, slippage, or capacity constraints** are modeled in any return figure.

---

## Recommendations

Ranked by confidence, given the evidence above:

1. **(High confidence) Zero-weight or remove the four dead rules** (`rs_sector_relative`,
   `rs_industry_relative`, `rs_line_uptrend`, `pattern_high_tight_flag`) until sector/industry
   classification data is ingested. They currently consume weight budget while contributing no
   signal, ever.
2. **(High confidence) Fix `RuleEffectivenessUseCase`** to use real forward returns (the same
   methodology built for this report) instead of the circular score-proxy, so the application's
   own `/validation` endpoints stop producing misleading self-correlation "evidence."
3. **(Medium confidence) Do not remove Pattern/Breakout/Momentum Quality/Risk engines.** Their
   apparent underperformance in this window is plausibly a single-regime artifact (no drawdown
   period to demonstrate their protective value), not proof they are worthless. Removing them on
   the strength of a 10-observation, single-regime sample would be exactly the kind of
   intuition-over-evidence decision this review is meant to prevent in the other direction.
4. **(Medium confidence) Re-test with a longer historical backfill before making any weight or
   threshold change to the production strategy.** The single most valuable next step is extending
   real stock-level history — even to 2-3 years, covering at least one real correction — rather than
   acting on the current single-regime sample.
5. **(Low confidence, worth investigating) Consider whether extension/breakout-timing rules should
   be re-weighted lower during confirmed strong-trend regimes** — the negative deltas on
   `tt_close_above_sma50`, `bo_pivot_breakout`, and `mq_acceleration` are suggestive but require
   validation across a genuine bull/bear/sideways comparison before acting on them.

**No change to production thresholds, weights, or gates is recommended in this cycle.** The
evidence is suggestive, not conclusive, and the review's own standard ("do not modify the screening
methodology unless empirical evidence demonstrates the change improves measurable outcomes") is not
yet met at the confidence level this small a sample can support.

---

## Future Research

1. Extend the real stock-level backfill to at least 2-3 years (ideally to 2015, matching the now-ingested
   benchmark index history), prioritizing coverage of at least one genuine drawdown period.
2. Re-run this exact methodology once extended data lands, with non-overlapping snapshots and
   multiple holding periods (10/21/63 days).
3. Ingest sector/industry classification data to activate the three dead RS rules.
4. Fix `RuleEffectivenessUseCase` in application code using this report's real-forward-return method.
5. Add a genuine NIFTY momentum sub-index (e.g., Nifty200 Momentum 30) as Benchmark F once historical
   constituent data is sourced.
6. Formal parameter sensitivity sweeps (threshold grids for RS minimum, 52-week proximity percentages,
   breakout volume multiplier) once enough history exists to make such sweeps statistically meaningful
   rather than overfit to a single short window.
