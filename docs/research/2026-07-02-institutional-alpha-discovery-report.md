# Research Program 3 — Institutional Alpha Discovery & Strategy Evolution

**Date:** 2026-07-02
**Scope:** Winner/failure profiling, ranking-quality research, feature discovery, portfolio
research, and strategy evolution for `minervini_trend_template` V1, using the corrected
(post cfg.rules-fix) dataset from the prior Alpha Discovery Program.

**Executive summary up front (Deliverable 10), because it governs how to read everything below:**
**Retain Strategy V1 in production.** This program found one strong, coherent, actionable
signal (extension/acceleration predicts failure — §2, §7) and several genuinely negative
results (RS acceleration and volatility contraction do *not* work as hypothesized; ranking
quality is weak). None has been walk-forward validated as a config change, so none is
promoted. The single highest-priority next step is a validated experiment tightening
`risk_extension`'s threshold — proposed, not implemented, in §9.

---

## 1. Dataset Quality / Coverage / Confidence / Readiness Report (Phase A)

**Coverage ceiling — read this before anything else:** this program's brief asked for
15-20 years of history (minimum 10). **That is not achievable with this platform's only
verified data source.** NSE's bhavcopy archive (the endpoint `BhavcopyProvider` uses) was
empirically tested against dates back to 2016 during the prior session's backfill work and
returns HTTP 404 for any date before **2019-10-01** — confirmed by direct API calls, not
assumed. The dataset used throughout this report — **1,663 trading days, 2019-10-01 to
2026-06-30, 2,736 securities, 2.42M bars** — is the maximum obtainable from this source, not
a processing shortcut. Reaching 10+ years would require a different, currently unidentified
and unverified data vendor — out of scope to acquire in this program.

- **Data Confidence Score** (built in the prior program): 99.90% of observations are
  "high confidence" (coverage + gap/duplicate/anomaly check). Not a material constraint.
- **Corporate actions, historical constituents, sector/industry:** still unavailable from any
  free source (unchanged, disclosed in every prior report this session).
- **Research readiness verdict:** the dataset supports research at the "several years,
  multiple regimes" tier (pre-COVID close, COVID crash, 2020-21 recovery, 2022 correction,
  2023-24 bull) but **not** the "multi-decade, multi-cycle" tier the brief's target
  presupposed. Every regime-robustness claim below (Phase where relevant) should be read
  against that ceiling — one bear episode, one COVID-style crash, is what's available, not
  five of each.

---

## 2. Winner Profile Report (Phase B)

11,734 qualified observations (production strategy, 80 runs, corrected engines, 120-day
horizon), classified into 6 fixed tiers (not fit to this dataset):

| Tier | n | % |
|---|---|---|
| Exceptional Winner (≥75%) | 1,112 | 9.5% |
| Strong Winner (40-75%) | 1,580 | 13.5% |
| Moderate Winner (15-40%) | 2,383 | 20.3% |
| Neutral (-10-15%) | 3,236 | 27.6% |
| Underperformer (-25--10%) | 1,790 | 15.3% |
| Failure (<-25%) | 1,633 | 13.9% |

**The headline finding of this entire program is not what distinguishes Exceptional Winners
from the average pick — it's what distinguishes Failures.** Comparing Failure-tier mean
characteristics against Winner-tier (Exceptional + Strong pooled) means:

| Characteristic | Failure mean | Winner mean | Difference |
|---|---|---|---|
| `risk_extension_pct` (extension above SMA50) | **27.5%** | 17.9% | **+54% relative** |
| `pct_above_52w_low` | **402.7%** | 252.6% | **+59% relative** |
| `mq_acceleration_ret20` (20d return accel.) | **29.1%** | 16.6% | **+75% relative** |
| `breakout_pct_of_range` | 71.1% | 67.6% | +5% relative |
| `rs_rating` | 86.3 | 84.9 | +2% relative (weak) |

**Failures are, on average, the most extended, most accelerated, furthest-from-their-lows
stocks the strategy selects — not the weakest.** This is the opposite of what a naive
"weaker momentum signals predict failure" hypothesis would suggest, and it's a coherent,
economically sensible pattern: stocks already up ~400% from their 52-week low, extended 27%+
above their 50-day average, and accelerating at 29%/20-trading-days, are plausible candidates
for blow-off-top exhaustion, not early-stage momentum. (By contrast, the naive "exceptional
winner vs. everyone else" comparison is much noisier — pooling failures in with neutrals and
moderate winners as "the rest" washes out this signal; the failure-specific comparison is
where the real evidence is.)

**Ranking stability:** unchanged from the prior program — ~25% month-over-month top-25
Jaccard overlap, ~52% for the broader qualified set.

---

## 3. False Positive Analysis (Phase C)

1,633 Failure-tier observations (13.9% of all qualified picks). Extending the prior program's
finding: false positives pass the gates legitimately (the gates are binary pass/fail and
don't encode "how extended" or "how fast", only "extended enough" / "fast enough"). **The
gates have no mechanism to distinguish a stock in the early stage of a qualifying move from
one in its final, most extreme stage** — §2's extension/acceleration finding is the concrete,
actionable version of this: two stocks can both pass every current rule while one is 15% above
its 50-day average and the other is 40% above it, and the current strategy treats them
identically (or, since `risk_extension`'s contribution formula rewards *smaller* extension,
the 40%-extended stock still passes as long as it's under the 25% threshold cap, and the
threshold itself doesn't reject aggressively enough — 27.5% average among failures, only
2.5pp over the 25% cap, meaning most failures narrowly clear the existing bar rather than
grossly violating it).

---

## 4. Missed Winner Analysis (Phase C)

61,512 non-qualified observations with valid 120-day forward data; **10,807 (17.6%) became
Strong or Exceptional Winners despite never qualifying** — a real, material miss rate.

Top exclusion reasons (count of missed winners that failed each rule — a missed winner
typically fails multiple rules simultaneously, so these are not mutually exclusive):

| Rule | Missed winners excluded by this rule |
|---|---|
| `pattern_flat_base` | 10,527 |
| `pattern_ascending_base` | 9,209 |
| `risk_rr` | 9,178 |
| `pattern_cup_with_handle` | 8,898 |
| `vol_breakout_confirm` | 8,700 |
| `tt_rs_rating_min` / `rs_rating` | 8,573 |
| `mq_acceleration` | 8,052 |

**The 4 pattern rules dominate the exclusion list** — consistent with, and reinforcing, the
prior program's finding that all 4 pattern rules show *negative* return-deltas among stocks
that pass them. Put together: the pattern engine excludes a huge number of eventual winners
**and** doesn't clearly add value when it does pass a stock. This is the strongest
"simplify" candidate identified across all research programs this session, though — per this
program's own "no promotion without walk-forward validation" rule — it is not promoted here.

`tt_rs_rating_min` excluding 8,573 missed winners is expected and, per the false-negative
analysis in the prior program, largely definitional (a stock becomes a strong performer partly
*because* it wasn't yet showing RS strength when it was passed over — waiting for confirmed
strength is the strategy's design, not a flaw, though it does trade recall for precision by
construction).

---

## 5. Alpha Attribution Report (Phase D)

No material change from the prior program's rule/engine attribution (§6/§7 of the 2026-07-02
Alpha Discovery Program report) — that analysis used the same corrected dataset. Restating the
ranked verdict for completeness:

**High-value, keep:** all 8 Trend Template rules, all 3 Breakout rules, `vol_breakout_confirm`,
`vol_accumulation_days`, `relative_strength` (`rs_rating`) — engine-level, `relative_strength`
now shows the single strongest engine signal (+6.50% vs +2.41% forward return gap).

**Negative-delta, not yet promotable for removal:** `risk_atr`, `risk_extension` (large
negative deltas, small "fail" samples — but see §2's *independent*, dataset-wide confirmation
that high extension correlates with failure, which raises confidence these deltas are real,
not noise), all 4 pattern rules (consistent negative deltas + high missed-winner exclusion
count, §4), `mq_acceleration`.

**New in this program:** §2's extension/acceleration finding gives the `risk` engine's
negative correlation a coherent causal story it lacked before — it's not that risk-averse
gates are randomly excluding good stocks, it's that **the specific thresholds are too loose**
to catch the blow-off-top pattern before it's already at ~28% extension on average.

---

## 6. Ranking Quality Report (Phase E)

Computed across the full evaluated universe (not just qualified stocks), 60 runs with ≥20
observations each, 120-day forward return:

| Metric | Value |
|---|---|
| Mean Information Coefficient (Pearson, momentum_score vs. fwd return) | **0.0158** (σ=0.066) |
| Mean Rank IC (Spearman) | **0.0247** (σ=0.077) |
| % of runs with positive IC | 58.3% |
| Top-decile − bottom-decile return spread | +8.85pp |
| Top-25 hit rate (% positive fwd return) | 50.9% |
| Top-10 hit rate | 45.8% |

**This is a sobering, important finding: the ranking signal's discriminative power is weak.**
An IC of 0.016 is close to zero (a "good" quant signal is typically considered to start around
0.02-0.05, with 0.05+ considered strong); positive in only 58% of runs is barely better than a
coin flip; and **the Top-10 hit rate (45.8%) is worse than the Top-25 hit rate (50.9%)** —
the model's highest-conviction picks (by rank) are not outperforming its lower-conviction
picks within the qualified set. The decile analysis shows a *directionally* correct but noisy
pattern (bottom decile 12.0% avg return, top decile 23.4%), so there is *some* signal, but it
is inconsistent and not concentrated where the model has the most conviction.

**Implication:** the gate (which rules to pass) is doing more work than the ranking (which of
the passers to prefer). Improving the ranking mechanism itself — not just the gate — is a
larger, more open research question than anything else in this program, and is not something
this program's evidence is strong enough to propose a specific fix for.

---

## 7. Feature Importance / Discovery Report (Phase F)

Testing the brief's suggested new characteristics against the corrected dataset:

| Characteristic | Result | Verdict |
|---|---|---|
| **Extension from 52w low / SMA50 + acceleration** | Failures average 60-75% higher on both vs. winners (§2) | **Strong, actionable — not yet a rule threshold, current thresholds too loose** |
| RS acceleration (Δ RS rating vs. prior month) | Low-acceleration quartile: 17.8% avg return; high-acceleration quartile: 14.8% | **Rejected as hypothesized** — direction is opposite of "more acceleration is better" |
| Leadership persistence (consecutive qualifying months) | 1 month: 16.9%; 2-3: 17.6%; 4-6: 16.2%; **7+: 8.3%** | **Partial signal, opposite of naive expectation** — long streaks (7+ months) show markedly *worse* forward returns, consistent with the extension/acceleration exhaustion story in §2 |
| Volatility contraction (tight vs. wide ADR% quartile at selection) | Tight: 13.4%; Wide: 14.6% | **No meaningful effect** — direction is even slightly opposite of the classic "contraction precedes breakout" thesis |

**Only one new characteristic cluster survives scrutiny: extension/acceleration/streak-length
all point to the same underlying phenomenon (momentum exhaustion in late-stage movers).**
RS acceleration and volatility contraction — both explicitly named as promising in the
brief — do not show the expected relationship in this dataset and should not be added.
This is exactly the kind of negative result the Research Charter asks to be reported honestly
rather than omitted.

---

## 8. Portfolio Research Report (Phase G)

Top-25 (by rank) portfolio simulation, 57 runs with complete data, monthly rebalancing (the
production strategy's own cadence):

| Weighting scheme | Avg period return | Volatility (period-to-period) |
|---|---|---|
| Equal weight | 8.55% | 23.69% |
| Score weight (momentum_score-proportional) | 8.49% | 23.71% |
| Inverse-ATR weight (favor low-volatility names) | 6.79% | 23.64% |

**Equal weight and score weight are statistically indistinguishable** (0.06pp difference on
23%+ period volatility — noise). **Inverse-ATR weighting underperforms both** by ~1.7-1.8pp
with no volatility reduction to compensate — the intuitive "size down volatile names" strategy
does not pay off here, plausibly because the volatile/extended names it downweights include
both failures (§2) and some of the exceptional winners (RS-strong movers are often also
higher-ADR%), netting out to a worse trade-off than simple equal weighting.

**Holding period** (avg return by horizon, same Top-25 population): monotonically increasing
from 5d (-0.02%) through 252d (22.05%) — expected for a momentum strategy and not, by itself,
informative about the *right* holding period without risk-adjusting each horizon (out of
scope for this program's time budget — flagged in §10).

**Recommendation:** no change to weighting scheme is justified — equal weight remains the
simplest, statistically-indistinguishable-from-best choice, consistent with "prefer simpler
models whenever predictive performance is statistically equivalent."

---

## 9. Strategy V2 Proposal — evidence exists for ONE candidate change, not promoted yet

Per the mandate ("no promotion without statistically significant, reproducible, walk-forward
validated improvement"), **this program does NOT propose implementing Strategy V2.** It does,
however, have enough coherent evidence to name a specific, well-scoped candidate for the next
validation cycle:

**Candidate: tighten `risk_extension`'s `max_pct` threshold from 25% to ~18-20%.**

- **Supporting evidence:** Failures average 27.5% extension (barely over the current 25% cap)
  vs. 17.9% for winners (§2); this is corroborated independently by the leadership-persistence
  finding (§7) that long-qualifying streaks — which correlate with high cumulative extension —
  show markedly worse returns.
- **Expected benefit:** tighter extension cap should reduce Failure-tier admission by
  excluding late-stage, blown-off names, without needing new rules (uses the existing
  `risk_extension` mechanism — the config-driven param is already there and, after this
  session's engine fix, actually works).
- **Potential drawback:** would also exclude some fraction of Exceptional/Strong Winners that
  happen to be legitimately extended (winners average 17.9% extension — a cap at 18-20% would
  be right at the boundary of the winner population's own average, risking meaningfully
  increased false negatives, not just filtering failures).
- **Statistical confidence:** correlational only — not walk-forward tested with an actual
  threshold change and out-of-sample evaluation. The extension/acceleration finding is
  observational (§2), same class of evidence as the prior program's `risk_atr`/`risk_extension`
  deltas, now independently corroborated but still not causally validated.
- **False positive/negative impact:** unknown until tested — this is exactly why it's a
  candidate for the next program, not a promotion today.
- **Walk-forward validation:** not performed in this program (would require re-running the
  full walk-forward with a new threshold across all regimes, plus the `ParameterResearchUseCase`
  fix flagged as still-broken in the prior program).

**No other characteristic tested in this program (§7) has strong enough or correctly-directed
evidence to be a V2 candidate.**

---

## 10. Executive Summary & Remaining Research Roadmap

**Retain Strategy V1.** No change is promoted by this program.

**What this program found that's real and useful:**
1. Failures are characterized by extreme extension + acceleration + long qualifying streaks —
   a coherent, three-way-corroborated pattern pointing at momentum exhaustion, not weak
   momentum.
2. RS acceleration and volatility contraction — both plausible-sounding hypotheses from the
   brief — do not work as expected in this dataset. Reporting this negative result is as
   important as reporting the positive one.
3. The ranking mechanism (which stocks get top rank among those that qualify) has weak
   statistical power (IC≈0.016) — a bigger, more open problem than any single rule tweak.
4. Equal-weight portfolio construction remains the right default; ATR-inverse weighting does
   not help.
5. The pattern engine remains the strongest simplification candidate across all research this
   session (negative rule-level deltas + largest missed-winner exclusion count), still not
   promoted for removal without walk-forward validation.

**Recommended next research program, in priority order:**
1. Walk-forward validate the `risk_extension` threshold tightening (§9) — the single
   highest-confidence candidate this program produced.
2. Fix `ParameterResearchUseCase` (flagged broken in the prior program) so threshold
   experiments like #1 don't require hand-rolled scripts.
3. Investigate *why* the ranking mechanism has weak IC (§6) — is it the momentum_score
   formula's weighting scheme, or a more fundamental limit on how predictable this universe's
   forward returns are from any deterministic, publicly-observable signal at selection time?
4. A proper, walk-forward-validated (not correlational) test of removing the 4 pattern rules,
   given their consistent negative signal across two independent programs now.
5. Continue operating the platform to accumulate more regime diversity — this dataset's
   ceiling (2019-10 onward, one COVID-style crash, one 2022 correction) is a real constraint
   on every regime-robustness claim in this and prior reports, and no amount of further
   analysis of the *same* data resolves it.

---

## Validation

`ruff check src tests`: 143 pre-existing issues, 0 introduced (no production code was
modified this program — read/analysis-only, using infrastructure already built and validated
in the prior two programs). `mypy src`: 23 pre-existing errors, identical set. `pytest`: 161
passed, unchanged from the prior program's end state.

**Reproducibility:** every statistic in this report is computed deterministically from
already-persisted, immutable data (`forward_returns`, `rule_results`, `screening_results`) —
re-running the analysis scripts against the same database state reproduces identical output.
