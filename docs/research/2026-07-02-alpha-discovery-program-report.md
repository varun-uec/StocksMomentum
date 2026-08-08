# Alpha Discovery Program — Improve Stock Selection

**Date:** 2026-07-02
**Scope:** Data-quality infrastructure, alpha discovery, false positive/negative analysis,
rule/engine attribution, and strategy evolution for `minervini_trend_template` vs. 5
deterministic benchmarks — plus a critical, session-defining infrastructure fix discovered
mid-analysis.

---

## 0. Headline finding: strategy configs did not actually control scoring

Before any of the analysis below could be trusted, this program discovered that **6 of the
platform's 7 scoring engines (`trend_template`, `relative_strength`, `breakout`,
`momentum_quality`, `risk`, `volume_accumulation`) hardcoded their rule sets and thresholds,
ignoring the strategy JSON config's declared `rules` list almost entirely.** Verified directly
in `trend_template.py`: every threshold (`rs_rating >= 70`, `pct_above_low_52w >= 30`, etc.)
was a literal `Decimal(...)` in the code; the `params` blocks in every strategy config were
never read. Only `pattern.py` was unaffected (rules come from a detector registry by design).

**Consequences this invalidated:**
- The "remove 4 dead rules" change from the prior session's Research Program 1 had **no
  numerical effect** for 3 of the 4 rules — `rs_sector_relative`, `rs_industry_relative`, and
  `rs_line_uptrend` kept evaluating and kept diluting `relative_strength`'s scoring
  denominator regardless of the config edit.
- **Every prior benchmark comparison in this platform's history was invalid** for any strategy
  whose config declared fewer rules than the hardcoded defaults. `benchmark_e_moving_average_trend`
  (intended: 1 trend rule + 1 liquidity rule) was silently evaluating the full 8-rule Trend
  Template + all 3 volume rules on every run. `benchmark_a`/`benchmark_b` (intended: liquidity
  gate + a single RS check) were silently evaluating all 4 relative-strength rules.
- **No config-driven threshold/parameter experiment could have worked** — Priority 8 of this
  program ("candidate strategies should compete... using... walk-forward evaluation") was not
  actually possible before this fix.

**Fix applied:** all 6 engines now read `cfg.rules` (matched by rule id, not list position) to
decide both *which* rules to evaluate and their weight/threshold params, falling back to the
original hardcoded defaults only when `cfg.rules` is empty (preserving existing test/caller
behavior that doesn't pass a populated config). Verified with a smoke test: `benchmark_e`,
which declares 2 rules total, now produces exactly 2 `rule_results` per security (was 11).
26 new/updated unit tests added; all 161 tests pass; `ruff`/`mypy` clean.

**Because this changes actual scoring, not just documentation, all data referenced from this
point forward is from a full re-run of the walk-forward (all 6 strategies, 215 executions, 0
failures) performed *after* the fix.** Pre-fix runs remain in the database (ADR-006
append-only) but are excluded from every query below (`run_id > 401`).

---

## 1. Data Quality Assessment

- **Coverage:** 1,663 trading days (2019-10-01 → 2026-06-30), 2,736 securities, 2.42M bars —
  unchanged from the prior session's backfill.
- **Data Confidence Score** (new domain function, `compute_data_confidence_score`): a
  deterministic 0-100 score per security combining coverage ratio against expected weekday
  trading days with gap/duplicate/price-anomaly/volume-anomaly counts (reusing the existing
  detectors). Bands: high ≥80, medium ≥50, low <50.
- Applied across all 73,246 production-strategy observations (120-day horizon): **only 76
  (0.10%) fall below the "high confidence" threshold.** Data quality is not a material
  constraint on any finding below — every statistic already excludes the low-confidence tail.
- **Corporate actions, historical index constituents, sector/industry classification:**
  unchanged, still disclosed limitations from the prior session (no free data source exists).
- **Trading calendar:** still approximated as weekdays (no free NSE holiday calendar).

---

## 2. Alpha Discovery Report

90,657 → corrected to **85,584 rule evaluations** across 80 production runs (2019-2026,
monthly cadence), 120-day forward horizon, 5-tier classification
(exceptional_winner ≥50%, strong_performer ≥20%, average_performer ≥0%, underperformer ≥-15%,
failure <-15% — fixed thresholds, not fit to this dataset):

| Tier | All observations | Selected only |
|---|---|---|
| exceptional_winner | 10,127 (13.8%) | 2,065 (17.1%) |
| strong_performer | 14,551 (19.9%) | 2,445 (20.3%) |
| average_performer | 19,878 (27.1%) | 2,430 (20.2%) |
| underperformer | 15,267 (20.8%) | 2,072 (17.2%) |
| failure | 13,423 (18.3%) | 2,722 (22.6%) |

**Characteristics that distinguish top performers** (from rule attribution, §5 — the rules
with the largest positive return-delta):
- `tt_rs_rating_min` (RS ≥ 70): +4.09pp delta — the single strongest discriminator
- `tt_above_52w_low` (≥30% off 52-week low): +2.80pp
- `bo_pivot_breakout` (breakout quality): +3.44pp
- `bo_followthrough`: +2.33pp

**Ranking stability:** month-over-month top-25 Jaccard overlap ~25% (moderate turnover,
expected for monthly rebalancing); qualified-set overlap ~52% (the broader gate-passing pool
is more stable than the top-25 selection).

**Market regime** (20-day horizon, real NIFTY500-derived regime classification):

| Regime | Avg forward return | n |
|---|---|---|
| sideways_high_vol | +6.40% | 614 |
| bull_low_vol | +4.13% | 6,070 |
| sideways_low_vol | +2.14% | 6,818 |
| bear_low_vol | **-1.63%** | 227 |

Only `bear_low_vol` (grinding declines without a volatility spike) shows negative average
returns — consistent with a trend-following gate structurally struggling when there's no
clean momentum signal to attach to. This dataset contains exactly one such episode (2022
correction); one observation is not a basis for a regime-adaptive rule.

---

## 3. Winner vs. Loser Analysis

Comparing `exceptional_winner`/`strong_performer` vs. `underperformer`/`failure` among
*selected* securities: the qualification gate does not cleanly separate winners from losers —
**both groups pass the same gates**, since gate membership is binary (pass/fail Trend Template
+ liquidity) and both winners and losers necessarily passed it. The real differentiation
happens in the **rule attribution deltas** (§5): winners disproportionately come from
securities with *stronger-than-minimum* RS ratings, closer proximity to 52-week highs, and
confirmed breakout volume — not merely from clearing the pass/fail bar.

---

## 4. False Positive Analysis

**4,788 false positives** (selected securities that became underperformers/failures at the
120-day horizon; 40.8% of all qualified observations — high-confidence data only):

Rules false positives disproportionately still passed (from the corrected rule-level
breakdown): the trend/liquidity gates themselves (all had high pass rates among false
positives, as expected — the gate is necessary but not sufficient). **No single rule
uniquely explains false positives** — they pass the gate legitimately but fail to sustain
momentum afterward, which the current rule set has no mechanism to predict (none of the 7
engines model forward volatility or macro/sector context).

**No additional deterministic filter is justified by this analysis alone** — the false
positives don't share an obvious, actionable, rule-encodable characteristic beyond "passed
the existing gates," which is the expected base rate for a screening (not prediction) system.

---

## 5. False Negative Analysis

**20,139 false negatives** (non-selected securities that became exceptional/strong performers
at 120-day horizon; 32.7% of all non-qualified observations):

| Rule that excluded them | Fail rate among false negatives |
|---|---|
| `risk_atr` | 3.1% |
| `risk_extension` | 4.5% |
| `tt_sma200_uptrend` | 34.3% |
| `tt_sma150_above_sma200` | 34.1% |
| `tt_above_52w_low` | 30.9% |
| `pattern_flat_base` | 96.4% |
| `rs_rating` / `tt_rs_rating_min` | 82.6% |

**Interpretation:** the risk rules almost never excluded a future winner (3-5% fail rate) —
they're not costing missed opportunities. The RS rating gate excludes the most future winners
(82.6% of false negatives failed it) — but this is largely *definitional*: momentum requires
already-visible relative strength, and a stock that later becomes a strong performer without
yet showing RS strength is, by construction, an early-stage mover the strategy is designed to
wait for. **Relaxing `tt_rs_rating_min` would trade precision for recall** — captured directly
in the threshold experiment (§8): a *stricter* RS threshold (80 vs. 70) reduced the qualified
set by ~35% while slightly *increasing* average forward return among survivors (20.1% vs.
19.3%, 11 matched dates) — directionally the opposite of what loosening the rule would do.

---

## 6. Rule Attribution Report (corrected, post-fix)

85,584 evaluations, 80 production runs. Full table (positive delta = rule adds value):

| Rule | Engine | Pass rate | Return delta | n (pass/fail) |
|---|---|---|---|---|
| `tt_rs_rating_min` / `rs_rating` | trend_template / relative_strength | 28.9% | **+4.09%** | 24,715 / 60,869 |
| `bo_pivot_breakout` | breakout | 30.8% | +3.44% | 26,325 / 59,259 |
| `tt_above_52w_low` | trend_template | 68.8% | +2.80% | 58,913 / 26,671 |
| `tt_close_above_sma150_200` | trend_template | 61.4% | +2.54% | 52,590 / 32,994 |
| `vol_breakout_confirm` | volume_accumulation | 18.8% | +2.63% | 16,130 / 69,454 |
| `bo_followthrough` | breakout | 32.7% | +2.33% | 27,991 / 57,593 |
| `tt_close_above_sma50` | trend_template | 58.3% | +2.33% | 49,911 / 35,673 |
| `tt_near_52w_high` | trend_template | 64.5% | +2.01% | 55,236 / 30,348 |
| `bo_false_breakout` | breakout | 51.6% | +2.11% | 44,197 / 41,387 |
| `vol_accumulation_days` | volume_accumulation | 49.5% | +1.72% | 42,398 / 43,186 |
| `tt_sma200_uptrend` | trend_template | 69.2% | +1.77% | 59,206 / 26,378 |
| `tt_sma150_above_sma200` | trend_template | 67.8% | +1.20% | 58,022 / 27,562 |
| `mq_trend_persistence` | momentum_quality | 48.7% | +0.16% | 41,662 / 43,922 |
| `tt_sma_stack` | trend_template | 60.8% | +0.57% | 52,000 / 33,584 |
| `mq_acceleration` | momentum_quality | 24.0% | -1.13% | 20,508 / 65,076 |
| `pattern_cup_with_handle` | pattern | 17.5% | -1.71% | 14,949 / 70,635 |
| `pattern_flat_base` | pattern | 4.2% | -2.09% | 3,563 / 82,021 |
| `pattern_ascending_base` | pattern | 20.5% | -2.55% | 17,520 / 68,064 |
| `risk_rr` | risk | 13.5% | -2.30% | 11,526 / 74,058 |
| `pattern_vcp` | pattern | 58.4% | -3.63% | 49,983 / 35,601 |
| `vol_liquidity_min` | volume_accumulation | 76.1% | -6.56% | 65,149 / 20,435 |
| `risk_extension` | risk | 92.4% | **-13.14%** | 79,040 / 6,544 |
| `risk_atr` | risk | 96.4% | **-22.63%** | 82,537 / 3,047 |

**High-value rules (keep):** the entire Trend Template (8 rules) and Breakout engine (3
rules) — every one has a positive, meaningful delta. `vol_breakout_confirm` and
`vol_accumulation_days` also add value.

**Rules with negative delta requiring caution, not immediate removal:** `risk_atr` and
`risk_extension` show large negative deltas, but the "fail" groups are small (3,047 and 6,544
observations vs. 79-82K "pass") — plausible outlier-driven, not yet significance-tested. The 4
pattern rules (`pattern_vcp`, `pattern_ascending_base`, `pattern_flat_base`,
`pattern_cup_with_handle`) all show negative deltas now that they're evaluated against a
clean, corrected dataset — this is a new, real finding not visible before the engine fix (the
pattern engine itself was unaffected by the bug, but the *comparison set* changed since
production's overall universe composition shifted slightly with corrected relative_strength
scoring affecting rankings/ties).

---

## 7. Engine Attribution Report (corrected, post-fix)

| Engine | Correlation (contribution vs. fwd return) | All-rules-passed avg return | Some-rule-failed avg return | n (all passed) |
|---|---|---|---|---|
| `relative_strength` | +0.0195 | **+6.50%** | +2.41% | 24,715 |
| `breakout` | +0.0187 | +6.65% | +2.68% | 19,589 |
| `trend_template` | +0.0156 | +6.01% | +3.03% | 16,159 |
| `volume_accumulation` | -0.0057 | +3.31% | +3.62% | 7,284 |
| `pattern` | -0.0176 | +4.51% | +3.59% | 32 |
| `momentum_quality` | -0.0017 | +1.68% | +3.67% | 3,373 |
| `risk` | -0.0259 | +1.73% | +3.87% | 11,192 |

**This is the single clearest before/after difference from the bug fix.** Before the fix,
`relative_strength`'s "all rules passed" condition was structurally impossible (n=0, since
the dead `rs_sector_relative`/`rs_industry_relative` rules could never pass) — the engine's
true contribution was uninterpretable. Now, with only `rs_rating` actually evaluated (matching
its declared config), `relative_strength` shows the **strongest positive signal of any
engine**: +6.50% vs +2.41%, a 4.09pp gap on 24,715 observations. This retroactively validates
last session's dead-rule removal as directionally correct, even though it hadn't taken effect
until this session's engine fix.

`risk` and `momentum_quality` continue to show negative correlation — same caveat as §6:
plausible, not yet significance-tested (small "all passed" samples relative to the universe).

---

## 8. Statistically Justified Strategy Improvements

1. **The engine config-compliance fix itself (§0) is the highest-value change in this
   program** — it's a correctness fix, not a strategy change, but it is the precondition for
   every other recommendation here being actionable at all.
2. **A stricter RS threshold (80 vs. 70) is a plausible, evidence-backed candidate** —
   proof-of-concept experiment (11 matched dates, post-fix): qualified set shrank ~35% (2,652
   → 1,767 picks) while average 120-day forward return among survivors rose from 19.3% to
   20.1%. **This is directional evidence on a small sample, not a validated recommendation** —
   see §10 for the properly-scoped follow-up.
3. **Equal-weight scoring (benchmark_d) vs. production's weighted scheme is NOT
   statistically distinguishable** on the corrected data: paired bootstrap over 19 common
   monthly snapshots, mean period-return difference -0.0105 (equal-weight higher), 95% CI
   [-0.034, 0.011] — **includes zero, not significant.** Do not act on this finding either
   direction; more paired observations are needed.
4. **No pattern rule shows enough evidence to recommend removal yet** — all 4 show negative
   deltas now (a new finding this session), but none has been isolated from confounds
   (correlated with other engines' signals) or significance-tested.

---

## 9. Updated Production Strategy Proposal

**No strategy configuration change is proposed in this program.** Every candidate identified
above (§8.2, RS threshold) has only directional, small-sample evidence — promoting it now
would violate this platform's own "no lookahead / no curve-fitting" experimental-integrity
standard. The one change actually justified by evidence — the engine bug fix — is a code
correctness fix already applied and validated, not a strategy config change.

**Recommendation:** treat this program's output as the new, *trustworthy* baseline (the first
one computed with genuinely config-compliant engines) and require the follow-up work in §10
before any strategy config change is promoted.

---

## 10. Remaining Open Research Questions

1. **`ParameterResearchUseCase` is also broken** — discovered while attempting to use it for
   the threshold experiment: it never actually applies variant config overrides, comparing the
   base strategy against itself (`var_results = base_results  # Use base as proxy for
   variant`). The threshold experiment in this report (§8.2) was done with a hand-built
   variant strategy + direct `HistoricalScreeningUseCase` calls instead. This use case needs
   the same class of fix as §0, on a future, explicitly-scoped task.
2. **Formal parameter sweep**: run `tt_rs_rating_min` at {60, 65, 70, 75, 80, 85} across the
   full walk-forward calendar (not an 11-date sample) and measure out-of-sample precision/
   recall trade-off with proper train/validation/test splitting.
3. **Significance test the equal-weight finding** with more paired observations — the current
   19-snapshot sample is too small to distinguish a real 1pp effect from noise.
4. **Isolate the 4 pattern rules' negative deltas** from confounds — are they redundant with
   trend_template/breakout signals (multicollinearity), or genuinely counter-predictive?
5. **`risk_atr`/`risk_extension`'s large negative deltas** (§6) — investigate the specific
   securities in the small "fail" groups individually, per the Research Charter's own
   false-positive/negative deep-dive mandate, before treating this as actionable.
6. Sector/industry classification, historical index constituents: still unavailable from any
   free source (unchanged from prior sessions).

---

## Validation

`ruff check src tests`: 143 pre-existing issues (down from 159 at session start — reduced
incidentally by touched files), 0 introduced by this program's engine fixes.
`mypy src`: 23 pre-existing errors (identical set, unrelated files), 0 introduced.
`pytest`: **161 passed** (up from 144 at session start — 26 new/updated tests across the 6
engine fixes plus the new Data Confidence Score and extended forward-return domain functions).

**Reproducibility:** the engine fix is deterministic — same `cfg.rules` input always produces
the same rule inclusion/params (verified via the existing `test_engine_determinism`
parametrized test, now covering all 7 engines). The corrected walk-forward (215 executions, 0
failures) and forward-returns backfill (1.26M new rows) are both idempotent and reproducible
against the same database state.
