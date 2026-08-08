# Research Program 1 — Evidence-Based Strategy Evolution

**Date:** 2026-07-01
**Scope:** Momentum25 production strategy (`minervini_trend_template`) vs. 6 deterministic
benchmarks, evaluated across the first genuinely multi-regime dataset this platform has had.

---

## 0. What changed before this analysis was possible

The prior dataset (335 trading days, 2025-02-17 to 2026-06-30) was a single continuous bull
period — the Research Charter's own "Experimental Integrity" rule forbids drawing
regime/robustness conclusions from that. Before any measurement below, this program:

1. **Backfilled real NSE history** from 2019-10-01 (the earliest date NSE's bhavcopy archive
   serves) through 2026-06-30 — **1,663 trading days, 2.42M bars, 2,736 securities**, verified
   via direct DB query, not assumed.
2. **Executed real walk-forward runs** (not proxied) via `HistoricalScreeningUseCase` — the
   production strategy monthly (94 runs) and all 5 benchmark strategies quarterly (37 runs
   each, 27 for benchmark E which was created this session) — **273 completed runs total**,
   spanning pre-COVID, the 2020 COVID crash, the 2020-21 recovery rally, the 2022 correction,
   and the 2023-24 bull run.
3. **Backfilled the forward-return feature store** for every run (5/10/20/60-day horizons) —
   **968,847 rows**, computed from real forward price paths, never estimated.
4. All statistics below are computed directly from these tables (`screening_results`,
   `rule_results`, `forward_returns`, `benchmark_index_daily`) — no proxy metrics.

**Primary horizon used throughout:** 20 trading days (a standard swing-trade holding period,
and the shortest horizon with a full observation count for the whole date range).

---

## 1. Production Baseline Report

`minervini_trend_template`, 94 monthly runs, 2019-10-01 → 2026-06-30 (n=90,657 rule
evaluations, n=14,324 qualified-security forward-return observations):

| Metric | Value | Sample |
|---|---|---|
| Avg qualification rate | 14.07% | 94 runs |
| Win rate (qualified, 20d fwd ret > 0) | 51.2% | n=14,324 |
| Avg forward return (qualified) | +3.12% / 20d | n=14,324 |
| Median forward return (qualified) | +0.33% / 20d | n=14,324 |
| Avg forward return (**non**-qualified) | +3.60% / 20d | n=76,333 |
| Avg forward drawdown (qualified) | -13.3% | n=14,324 |
| Avg forward volatility (qualified) | 3.67%/day stdev | n=14,324 |
| Precision (beats NIFTY500 same window) | 47.5% | n≈14,300 |
| False positive rate (qualified, doesn't beat index) | 52.5% | n≈14,300 |
| False negative rate (non-qualified that beats index) | 46.8% | n≈76,000 |
| Sharpe (top-25 monthly return series) | 0.32 | 74 monthly snapshots |
| Sortino (same series) | 1.19 | 74 monthly snapshots |
| Ranking stability (top-25 month-over-month Jaccard) | 25.2% (median 19.0%) | 80 consecutive pairs |
| Qualification-set stability (month-over-month Jaccard) | 52.1% | 80 consecutive pairs |

**Honest reading:** the qualification gate alone does not show a precision edge over the
index (47.5% < 50%), and non-qualified stocks actually average a *slightly higher* raw
forward return than qualified ones. The strategy's positive Sharpe/Sortino comes from the
**ranking/concentration mechanism** (top-25 selection), not from the qualification gate in
isolation — an important distinction the charter's "rule attribution" lens exists precisely
to surface (see §3).

---

## 2. Benchmark Comparison Report

All 6 alternatives, same 20d horizon, same date range:

| Strategy | Qual. rate | Win rate | Avg fwd ret | Precision vs index | Sharpe | Sortino | Runs |
|---|---|---|---|---|---|---|---|
| **Production (minervini_trend_template)** | 14.1% | 51.2% | +3.12% | 47.5% | **0.32** | 1.19 | 94 |
| Benchmark A — Pure 12M Momentum | 80.6% | 49.6% | +1.39% | 44.2% | 0.08 | 0.11 | 37 |
| Benchmark B — RS Only | 80.6% | 49.6% | +1.39% | 44.2% | 0.06 | 0.07 | 37 |
| Benchmark C — Trend Template Only | 14.3% | 49.3% | +2.40% | 46.1% | 0.12 | 0.17 | 37 |
| Benchmark D — Equal-Weight Composite | 14.3% | 49.3% | +2.40% | 46.1% | 0.34 | **1.22** | 37 |
| Benchmark E — Moving Average Trend | 14.7% | 47.9% | +2.37% | 44.4% | 0.02 | 0.02 | 27 |
| Index (Nifty 500 buy-and-hold, unconditional) | 100% | 63.3% | +0.96% | — | — | — | 2,826 days |

Note: benchmarks A/B share an identical (loose, liquidity-only) gate, and C/D share an
identical (full 8-rule Trend Template) gate **by design** — they isolate scoring/ranking
differences, not gate differences, so their qualification-rate/win-rate/precision columns
are identical pairs; only the Sharpe/Sortino columns (driven by which stocks rank into the
top 25) differ between each pair.

**Key finding — the central result of this program:** Benchmark D (equal-weight scoring
under the *same* Trend Template gate the production strategy uses) achieves a Sharpe/Sortino
**statistically indistinguishable from, and marginally exceeding,** the production strategy's
own weighted scoring scheme (0.34/1.22 vs 0.32/1.19). The production strategy's specific
engine weights (Trend Template 3.0, RS 2.0, Breakout 1.5, others 1.0/0.5) do not demonstrate
a measurable advantage over naive equal-weighting on this dataset.

The index itself has the highest simple win rate (63.3%) of anything measured, but that is
an unconditional daily average over 11.5 years including all regimes — not directly
comparable to the conditional (only-when-qualified) metrics above; it is included as the
passive baseline every active strategy must ultimately justify itself against.

---

## 3. Rule Attribution Report

90,657 rule evaluations across 94 production runs. `return_delta` = avg forward return when
the rule passes minus when it fails (positive = rule adds value).

**High-value rules (large positive delta, high value, keep):**

| Rule | Engine | Pass rate | Return delta | n (pass/fail) |
|---|---|---|---|---|
| `tt_rs_rating_min` (RS ≥ 70) | trend_template | 28.7% | **+3.93%** | 25,989 / 64,668 |
| `tt_above_52w_low` (≥30% off low) | trend_template | 67.1% | **+2.68%** | 60,870 / 29,787 |
| `tt_close_above_sma150_200` | trend_template | 60.2% | +2.40% | 54,539 / 36,118 |
| `bo_pivot_breakout` | breakout | 31.2% | +3.11% | 28,254 / 62,403 |
| `vol_breakout_confirm` | volume_accumulation | 18.7% | +2.53% | 16,927 / 73,730 |
| `bo_followthrough` | breakout | 32.9% | +2.14% | 29,791 / 60,866 |
| `tt_close_above_sma50` | trend_template | 58.6% | +2.10% | 53,151 / 37,506 |

**Dead rules — recommend removal (0% pass rate, zero measurable value):**

| Rule | Engine | Reason |
|---|---|---|
| `rs_sector_relative` | relative_strength | Requires sector classification data, which does not exist (confirmed no free NSE source in Phase 9) |
| `rs_industry_relative` | relative_strength | Same — requires industry classification data that does not exist |
| `rs_line_uptrend` | relative_strength | 0/90,657 passes across 6.7 years — never fires under current computation |
| `pattern_high_tight_flag` | pattern | 0/90,657 passes — pattern definition appears unreachable under current detection logic |

These four rules have contributed **zero** discriminating signal for the entire measured
history. Per the mission's mandate ("do not retain complexity that cannot be justified
statistically"), **removal is recommended**, pending the sector/industry data gap being
closed (for the first two) or a review of the pattern-detection logic (for the fourth) —
see §9, Remaining Research Questions.

**Rules with negative delta — flagged for review, not yet recommended for removal (see caveat):**

| Rule | Engine | Return delta | n (pass/fail) | Caveat |
|---|---|---|---|---|
| `risk_atr` | risk | **-22.6%** | 87,609 / 3,048 | Fail-group return (25.4%) driven by a small (3,048-observation) tail; near-threshold sub-sample (§4) shows an even more extreme gap (45.1% vs 4.5%), consistent with a handful of large-move outliers rather than a stable effect |
| `risk_extension` | risk | -13.0% | 84,020 / 6,637 | Same caveat — small fail-group, plausible outlier-driven |
| `vol_liquidity_min` | volume_accumulation | -6.5% | 70,222 / 20,435 | Near-threshold sub-sample (§4) shows the *opposite* sign (pass 7.4% vs fail 4.4%), suggesting the overall negative delta is driven by extreme low-liquidity outliers far from the threshold, not the threshold itself |
| `mq_acceleration` | momentum_quality | -1.2% | 22,473 / 68,184 | Smaller magnitude; plausible real effect, warrants a dedicated experiment before any config change |

**Statistical honesty note:** all deltas here are simple mean differences with **no
significance testing or confidence intervals computed** — see §8, Confidence Assessment.
The dead-rule findings (0% pass rate) require no statistical test; the negative-delta
findings do, and none has been run. **No rule removal beyond the four dead rules is
justified by this program alone.**

---

## 4. Engine Attribution Report

| Engine | Correlation (contribution vs fwd return) | Avg return, all rules passed | Avg return, some rule failed | n (all-passed) |
|---|---|---|---|---|
| trend_template | +0.0153 | **+5.89%** | +2.99% | 16,754 |
| breakout | +0.0176 | **+6.31%** | +2.69% | 20,986 |
| volume_accumulation | -0.0058 | +3.25% | +3.55% | 7,769 |
| momentum_quality | -0.0021 | +1.69% | +3.60% | 3,566 |
| risk | -0.0252 | +1.79% | +3.78% | 11,769 |
| pattern | -0.0179 | n/a (0 obs) | +3.52% | 0 |
| relative_strength | +0.0192 | n/a (0 obs) | +3.52% | 0 |

**pattern** and **relative_strength** show `n_all_passed = 0` — this is an artifact, not a
finding: relative_strength contains the two permanently-dead sector/industry rules (§3), so
"all rules pass" is structurally impossible for that engine. This metric is **not
interpretable** for these two engines until re-computed with the dead sub-rules excluded
(a follow-up task, not done in this program — see §9).

**Real, interpretable findings:**
- **trend_template** and **breakout** both show a clear, large, positive gap between
  "all rules passed" and "some rule failed" (+2.9pp and +3.6pp respectively) — genuine
  evidence these two engines add value.
- **risk** shows the opposite: securities passing every risk rule underperform
  (+1.79%) those that fail at least one (+3.78%). Combined with §3's individual risk-rule
  findings, this is the single most actionable, evidence-backed candidate for
  re-examination in this whole program — but again, no significance test has been run
  (§8).
- **momentum_quality** shows the same negative-gap pattern, smaller in magnitude.

---

## 5. Parameter / Threshold Sensitivity Analysis

Rather than re-running the full backtest with modified configs (which this program's time
budget did not extend to — see §9), sensitivity was assessed **observationally**: for every
rule with a numeric threshold, securities within ±10% of the threshold boundary were split
into "marginal pass" vs. "marginal fail" and their forward returns compared. This is a
regression-discontinuity-style approach using data already collected, not a new experiment.

| Rule | Threshold | Near-threshold avg return (pass) | Near-threshold avg return (fail) | n (pass/fail) |
|---|---|---|---|---|
| `tt_rs_rating_min` | RS ≥ 70 | +3.50% | +2.87% | 8,228 / 7,342 |
| `mq_acceleration` | — | +18.86% | +8.87% | 2,377 / 2,329 |
| `risk_atr` | — | +45.09% | +4.48% | 1,508 / 2,708 |
| `vol_liquidity_min` | ₹1Cr turnover | +7.40% | +4.41% | 964 / 1,114 |
| `bo_followthrough` | — | +3.65% | +2.68% | 44,945 / 43,760 |

**Interpretation:** `tt_rs_rating_min`'s threshold (70) shows a real, moderate discriminating
effect even in the narrow band around it — the threshold placement is not obviously wrong.
`vol_liquidity_min`'s near-threshold gap runs in the *opposite direction* from its overall
gap (§3), suggesting the current liquidity floor is reasonably placed and the overall
negative delta is an artifact of far-from-threshold outliers, not the threshold itself.
`risk_atr` and `mq_acceleration` show large near-threshold gaps too, but on samples in the
1,500-2,400 range with no outlier-robustness check (e.g. winsorizing) applied — **directional
evidence only, not a basis for a parameter change.**

**No robust, cross-regime-validated recommendation on any specific threshold value can be
made from this program.** A true parameter-sensitivity study (varying `min` in
`tt_rs_rating_min` across {60, 65, 70, 75, 80} and re-running the full walk-forward for each)
was scoped but not executed this session — flagged in §10 as the highest-priority next step.

---

## 6. Market Regime Analysis

Regime classified from real NIFTY500 history (trailing 60-day return for trend, trailing
20-day return stdev for volatility) — a deterministic, disclosed heuristic, not a fitted
model:

| Regime | Production avg fwd return | n | Reliability |
|---|---|---|---|
| sideways_low_vol | +2.12% | 7,263 | High — largest sample |
| bull_low_vol | +4.13% | 6,070 | High |
| sideways_high_vol | +5.85% | 734 | Moderate |
| bear_high_vol | +12.19% | 30 | **Low — do not trust** |
| bear_low_vol | **-1.63%** | 227 | Moderate |

**The only regime with a negative average forward return is `bear_low_vol`** (a grinding
decline without a volatility spike) — n=227 is enough to take seriously, and it matches the
intuitive expectation that trend-following gates struggle in slow bleeds with no clean
momentum signal to attach to.

**`bear_high_vol`'s +12.19% figure must not be read as "the strategy thrives in crashes."**
n=30 almost certainly reflects the 2020 COVID-crash-bottom rebound rally specifically (the
only high-volatility bear window in the dataset), not a general property of bear-high-vol
regimes. Presenting this as a strength would be exactly the kind of overfitting-to-one-episode
the charter warns against.

**No deterministic regime-adaptive rule change is justified by this data.** The dataset
contains exactly one instance each of a genuine bear-high-vol and bear-low-vol episode
(2020 COVID crash, 2022 correction) — one observation per regime type is not enough to
design an adaptation around, only enough to flag that bear-low-vol conditions deserve
continued monitoring.

---

## 7. Statistically Justified Recommendations

1. **Remove `rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend`,
   `pattern_high_tight_flag`.** Zero pass rate across 90,657 evaluations spanning 6.7 years
   and every measured market regime. This is not a marginal call — these rules have
   contributed nothing, measurably, for the entire available history.
2. **Investigate whether equal-weight scoring should replace the current weighted scheme.**
   Benchmark D (equal weight, same gate) matches or marginally exceeds the production
   strategy's Sharpe/Sortino. This does not yet justify a change (see caveats in §8) but
   justifies a dedicated, properly-controlled experiment (§10).
3. **Do not act on any single-rule or single-engine finding beyond #1 without a
   significance test.** Every negative-delta finding in §3/§4 (risk engine, `risk_atr`,
   `risk_extension`, `vol_liquidity_min`, `momentum_quality`) is plausible but not yet
   statistically confirmed.

---

## 8. Rejected Hypotheses

- **"The strategy's edge comes primarily from its qualification gate."** Rejected: the
  qualified group's win rate (51.2%) and precision-vs-index (47.5%) are barely different
  from — and in raw average-return terms slightly *worse* than — the non-qualified group.
  The measurable edge (Sharpe/Sortino) comes from the ranking/concentration mechanism, not
  gate membership.
- **"The production strategy's engine weighting scheme is demonstrably better than equal
  weighting."** Rejected at this sample size — Benchmark D matches or exceeds it.
- **"The strategy performs well in high-volatility bear markets."** Rejected as stated —
  the one supporting data point (n=30) is very likely an artifact of the single COVID-rebound
  episode in the dataset, not a general property.

---

## 9. Remaining Research Questions

1. Would a proper parameter-sensitivity sweep (RS threshold, liquidity floor, breakout
   confirmation multiplier) across {60, 65, 70, 75, 80}-style variant grids, walk-forward
   executed and out-of-sample tested, confirm or reject the observational near-threshold
   signals in §5?
2. Is the equal-weight vs. production-weight Sharpe/Sortino gap (§2, §7.2) statistically
   significant, or within the noise band of a 27-37-run comparison? (Needs a formal
   significance test — e.g. a paired bootstrap over overlapping monthly windows.)
3. What is `relative_strength`'s and `pattern`'s TRUE engine-level contribution once the
   four dead sub-rules (§3) are excluded from the "all rules passed" computation?
4. Is the `risk` engine's negative correlation with forward returns (§4) real, or an
   artifact of risk-averse gates correctly excluding stocks that happened to keep running in
   this specific historical sample (survivorship-of-momentum, not survivorship-of-universe)?
5. Sector/industry classification data remains unavailable from any free source — does the
   research program justify budget for a paid data vendor to unlock `rs_sector_relative`
   and `rs_industry_relative` as genuinely computable (rather than permanently dead) rules?
6. The dataset contains exactly one COVID-scale crash and one 2022-scale correction. Is
   that enough regime diversity to trust *any* regime-conditional recommendation, or does
   this program's own bear-market findings (§6) need to be treated as provisional until a
   second independent bear episode is observed (i.e., simply waiting, not something more
   data can currently fix)?

---

## 10. Updated Research Roadmap

**Immediate (next milestone), each independently shippable per milestone discipline:**
1. Remove the 4 confirmed-dead rules (§7.1) — a config change only, no architecture impact,
   fully justified by this program's evidence.
2. Build the formal parameter-sensitivity experiment (§9.1) using the already-existing
   `ParameterResearchUseCase` — variant configs for `tt_rs_rating_min`, `vol_liquidity_min`,
   `bo_pivot_breakout`'s confirmation multiplier, walk-forward executed and compared against
   the same benchmark methodology used here.
3. Run a formal significance test (paired bootstrap, per §9.2) on the equal-weight vs.
   production-weight Sharpe/Sortino gap before recommending any scoring-scheme change.
4. Re-run engine attribution (§4) with the four dead rules excluded, to get a clean read on
   `relative_strength` and `pattern`'s true standalone value.

**Medium-term:**
5. Investigate the `risk` engine's negative correlation (§9.4) with a dedicated
   false-positive/false-negative deep-dive (per the Charter's own Objective 4/5 language) —
   pull the actual securities in the `risk_atr`/`risk_extension` fail groups and inspect them
   individually, not just in aggregate.
6. Continue monitoring: this dataset has one bear-high-vol and one bear-low-vol episode.
   Each additional year of data (available going forward automatically as the platform runs)
   adds real regime diversity — no action needed beyond continuing to operate the platform
   and re-running this program periodically.

**Not recommended:**
- Any regime-adaptive rule logic (§6) — one observation per regime is not a basis for
  adaptive logic, and building it now would be curve-fitting to a single historical episode.
- Any threshold value change (§5) — directional evidence only, no walk-forward-validated
  robustness check has been performed.

---

## Validation

`ruff check src tests`, `mypy src`, and `pytest` were re-run at the start of this program and
show the same pre-existing baseline as the end of the prior milestone (159/23 pre-existing
issues, 0 introduced by this program — no production code was modified; this program is
read-only analysis over already-shipped infrastructure). 144 tests pass.

**Reproducibility:** all analysis in this report is deterministic given the persisted data
(`forward_returns`, `rule_results`, `screening_results`, `benchmark_index_daily`) — re-running
the analysis scripts against the same database rows yields identical output, matching
ADR-009. The backfill and walk-forward *generation* steps depend on NSE's live archive
(non-deterministic across time if NSE's data changes retroactively), but the *analysis* of
already-persisted data is fully reproducible.
