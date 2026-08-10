# Validation Report: Momentum Ranking Fixes (P-1, P-2, P-4)

**Status:** Research output. **No code change is proposed for implementation.**
**Date:** 2026-08-10
**Tests the proposals in:** [2026-08-09-momentum-selection-methodology-review.md](2026-08-09-momentum-selection-methodology-review.md) §5
**Verdict up front:** **No improvement found.** Every configuration failed on the locked hold-out fold. The one apparent winner is a data-quality artefact, not alpha.

---

## 1. What was tested and on what data

### 1.1 Dataset

| Item | Value |
|---|---|
| Run series | `strategy_id=8` (`minervini_trend_template` v3), `data_version = historical:*:adjfix-recheck` |
| Runs with matured 120d forward returns | **63** monthly runs, 2020-11-27 → 2026-01-30 |
| Qualifier rows scored | 14,193 (mean 225/run, range 43–436) |
| Target | `forward_returns.excess_return`, horizon 120d, benchmark-relative |
| Metric | Spearman rank IC within the qualified set, per run |

The 2026-02-27 run exists but its 120d window has not matured, so 63 runs are usable, not 64. The `adjfix-recheck` series is the one recomputed after the corporate-action adjustment fix; the superseded `monthly-backfill` series was not used.

**Baseline reproduction.** Baseline `momentum_score` over all 63 runs: mean IC **−0.0384**, t(iid) **−2.43**. The established record says −0.0351 / t=−2.27. The small gap comes from the corrected adjustment data; the sign, magnitude, and significance are unchanged. The negative within-pool ranking IC is confirmed on clean data.

### 1.2 Hold-out split

| Fold | Runs | Dates |
|---|---|---|
| Construction | 43 | 2020-11-27 → 2024-05-31 |
| **Hold-out (locked)** | **20** | **2024-06-28 → 2026-01-30** |

Split at 43/20 (68%/32%). Reasons: the hold-out is contiguous and terminal, so no forward information leaks into construction; 20 monthly runs is the smallest fold that still gives a usable t-test on run-level ICs; and it keeps the 2022 correction inside the construction fold rather than spending the only stress period on the hold-out.

**Protocol followed.** All eight configurations were defined and scored on construction data only. The hold-out fold was read once, after the configuration list was closed. Nothing was re-mined and no configuration was added, dropped, or retuned after hold-out results were seen. Every configuration attempted appears in §2 — there are no unreported runs.

**Multiple testing.** Eight configurations were judged against the same hold-out fold, so p-values are Bonferroni-corrected at ×8. Raw p-values are reported alongside. Run-level ICs from monthly runs with a 120d horizon overlap by ~5 runs, so t-statistics use a Newey-West correction at lag 5; the naive iid t is shown for comparison and is uniformly more generous.

### 1.3 The eight configurations

| # | Configuration | Idea tested |
|---|---|---|
| C0 | `momentum_score` as shipped | baseline |
| C1 | 12-1 total return (t−252 → t−21) | RS skip-month (P-4) |
| C2 | 12-2 total return (t−252 → t−42) | RS skip-month, wider skip |
| C3 | Composite with `breakout` weight 1.5 → **0** | remove breakout engine (P-1) |
| C4 | Composite with `breakout` weight 1.5 → **0.75** | halve breakout engine |
| C5 | z(C3) + z(12-1) | ex-breakout composite blended with skip-month |
| C6 | 12-1 return ÷ realised 252d volatility | vol-scaled momentum (P-2) |
| C7 | 12-0 total return, **no skip** | control — isolates the value of the skip itself |

C3/C4 rebuild the composite from stored `rule_results` contributions and the config's `momentum_weights`. C7 is a control, not a proposal: it separates "does raw 12-month return beat the composite" from "does skipping the recent month help".

---

## 2. Results

### 2.1 Construction fold (43 runs) — where the configurations were chosen

| Config | mean IC | t(NW5) | p(raw) | runs IC>0 |
|---|---|---|---|---|
| C2 skip-2 | **+0.0582** | +2.09 | 0.042 | 70% |
| C1 skip-1 | +0.0457 | +1.60 | 0.118 | 74% |
| C6 vol-scaled | +0.0407 | +1.45 | 0.154 | 60% |
| C7 no-skip (control) | +0.0271 | +0.83 | 0.409 | 65% |
| C5 blend | +0.0132 | +0.43 | 0.671 | 63% |
| C3 no breakout | −0.0203 | −0.65 | 0.520 | 49% |
| C4 half breakout | −0.0264 | −0.94 | 0.355 | 44% |
| C0 baseline | −0.0274 | −1.13 | 0.264 | 42% |

This looked like a confirmation of the diagnosis. Plain skip-month momentum flipped the IC positive; the wider the skip, the better (C2 > C1 > C7); removing the breakout engine did *not* fix the composite on its own, consistent with "the ranking is measuring the wrong horizon, and re-weighting cannot repair that."

All eight were carried into the hold-out rather than pre-selecting the top two, so the correction factor is ×8 and no configuration is quietly discarded.

### 2.2 Hold-out fold (20 runs) — the locked test

| Config | mean IC | t(NW5) | p(raw) | **p(Bonferroni ×8)** | runs IC>0 | vs construction |
|---|---|---|---|---|---|---|
| C6 vol-scaled | **+0.0921** | +2.43 | 0.025 | **0.202** | 80% | +0.041 → +0.092 |
| C2 skip-2 | −0.0346 | −1.75 | 0.096 | 0.764 | 40% | **sign flip** |
| C1 skip-1 | −0.0613 | −2.44 | 0.025 | 0.196 | 35% | **sign flip** |
| C0 baseline | −0.0623 | −2.52 | 0.021 | 0.165 | 20% | −0.027 → −0.062 |
| C4 half breakout | −0.0852 | −3.55 | 0.002 | 0.017 | 25% | worse |
| C7 no-skip (control) | −0.0920 | −3.27 | 0.004 | 0.032 | 20% | **sign flip** |
| C5 blend | −0.1004 | −3.56 | 0.002 | 0.017 | 20% | **sign flip** |
| C3 no breakout | −0.1087 | −4.10 | 0.001 | 0.005 | 20% | worse |

Read plainly:

- **Skip-month reversed sign.** C1 and C2 were the two strongest construction results and are *negative* on hold-out, C1 significantly so at raw p. This is the fourth in-sample/out-of-sample sign reversal this program has produced on ranking recomposition.
- **Removing breakout weight made the ranking worse, not better,** and did so with the strongest statistics in the table (C3: −0.109, Bonferroni p=0.005). Dropping the breakout engine survives multiple-testing correction as a *harm*. The §2 diagnosis of the methodology review — that breakout dominance causes the negative IC — is contradicted by this. Whatever the breakout engine is doing on the hold-out fold, taking it out leaves something worse.
- **Only C6 is positive, and it fails Bonferroni** (p=0.202). §3 shows it is not a real result at all.

A common-support recomputation (restricting every run to the rows where all eight scores are finite, so configs are compared on identical names) moves nothing material: C6 +0.090, C2 −0.045, C0 −0.048, C3 −0.096. The rankings and conclusions are unchanged.

### 2.3 Practical effect — the Top-25 that would actually have been bought

Rank IC is not the deliverable; the Top-25 is. Mean realised 120d excess return of each configuration's Top-25, averaged over the 20 hold-out runs, with a paired test against baseline:

| Config | Top-25 mean excess | Δ vs baseline | t | p(raw) | p(Bonf) | mean overlap with baseline Top-25 |
|---|---|---|---|---|---|---|
| C6 vol-scaled | +3.69% | **+5.46pp** | +1.64 | 0.118 | 0.94 | 4.5 / 25 |
| C0 baseline | −1.77% | — | — | — | — | 25 / 25 |
| C4 half breakout | −2.10% | −0.32pp | −0.18 | 0.856 | 1.00 | 21.6 / 25 |
| C3 no breakout | −4.39% | −2.62pp | −1.16 | 0.259 | 1.00 | 13.8 / 25 |
| C2 skip-2 | −4.68% | −2.90pp | −1.07 | 0.298 | 1.00 | 6.1 / 25 |
| C7 no-skip | −4.87% | −3.10pp | −1.08 | 0.295 | 1.00 | 7.5 / 25 |
| C1 skip-1 | −5.63% | −3.86pp | −1.39 | 0.181 | 1.00 | 5.8 / 25 |
| C5 blend | −6.41% | −4.64pp | −1.80 | 0.087 | 0.70 | 8.8 / 25 |

These are large changes in the list, not marginal reorderings — skip-month keeps only ~6 of the baseline's 25 names. So this is a genuine test of a genuinely different portfolio, and the different portfolio was **worse by 3–4pp over 120 days**. No configuration beats baseline at any corrected significance level.

Three sample dates, showing the first eight names each configuration would have bought:

**2025-07-31** (146 qualifiers)

| Config | Top-25 realised 120d excess | First 8 names |
|---|---|---|
| C0 baseline | −23.5% | SIMPLEXINF, GALLANTT, CARTRADE, IRIS, HUBTOWN, SHANKARA, SPMLINFRA, FORTIS |
| C1 skip-1 | −9.6% | JSWHL, 63MOONS, AIIL, GODFRYPHLP, LLOYDSME, DEEPAKFERT, MANORAMA, CARTRADE |
| C6 vol-scaled | +30.9% | JSWHL, 63MOONS, **GOLDETF, EGOLD, GOLD1**, CHOICEIN, AIIL, **TATAGOLD** |

**2025-11-28** (223 qualifiers)

| Config | Top-25 realised 120d excess | First 8 names |
|---|---|---|
| C0 baseline | +23.3% | ABCAPITAL, LTF, MUTHOOTFIN, IIFL, LUMAXTECH, POWERINDIA, LUMAXIND, AUBANK |
| C1 skip-1 | +8.4% | CUPID, ZOTA, GARUDA, ASHAPURMIN, FORCEMOT, KRISHANA, SHAILY, CARTRADE |
| C6 vol-scaled | +22.8% | CUPID, ZOTA, **TATAGOLD, GOLDETF, HDFCGOLD, GOLDCASE, SETFGOLD, QGOLDHALF** |

**2024-09-30** (287 qualifiers)

| Config | Top-25 realised 120d excess | First 8 names |
|---|---|---|
| C0 baseline | −16.3% | POWERINDIA, SURANASOL, RADHIKAJWE, MSPL, VASWANI, PCJEWELLER, RPOWER, SIMPLEXINF |
| C1 skip-1 | −9.6% | NITCO, PCJEWELLER, POCL, TRENT, SUNDARMHLD, NEULANDLAB, NETWEB, QUICKHEAL |
| C6 vol-scaled | −7.0% | TRENT, PCJEWELLER, NITCO, NETWEB, SUZLON, DIXON, NEULANDLAB, STAR |

The bolded names are the finding of §3.

---

## 3. Why C6 "won", and why it is not a result

C6's hold-out Top-25 is full of gold ETFs.

The universe contains **247 non-equity instruments** — gold and silver ETFs, index and liquid funds — carried in `securities` with no ISIN, no name beyond the ticker, and no instrument-type field to exclude them. They pass the equity trend gate and enter the qualified set. In the hold-out fold they fill **168 of 500 C6 Top-25 slots (34%)**. Their appearance is concentrated in 2025 (252 of 324 flagged qualifier rows), which is exactly the Indian gold rally.

Vol-scaling is what promotes them: dividing return by realised volatility mechanically favours a low-volatility instrument tracking a metal over a mid-cap equity, and in 2025 that instrument also had strong 12-month returns.

Excluding the 247 flagged instruments and rerunning:

| Config | Hold-out IC (all) | Hold-out IC (equities only) |
|---|---|---|
| C6 vol-scaled | +0.0921 (t=+2.43) | **−0.0030 (t=−0.11)** |
| C0 baseline | −0.0623 | −0.0593 |
| C1 skip-1 | −0.0613 | −0.0617 |

**C6's entire edge is the gold ETFs.** On equities alone it is exactly zero. The other configurations are unaffected, because they do not systematically promote low-volatility instruments.

A second decomposition confirms the mechanism. Ranking by **inverse volatility alone**, with no momentum numerator at all:

| Fold | mean IC | t(NW5) |
|---|---|---|
| Construction | −0.0163 | −0.48 |
| Hold-out | **+0.2691** | **+3.63** |
| Hold-out, equities only | +0.1835 | +3.76 |

Inverse volatility on its own scores three times C6's hold-out IC, while being flat in construction. C6 is a *diluted* low-volatility bet — the momentum numerator, which is negative on hold-out, drags it down. So even the equity-only residual of the "vol-scaled momentum" idea is a low-volatility factor showing up in one regime, not a momentum improvement. Barroso–Santa-Clara scaling cannot be credited here.

**Two things follow that are not research findings but production facts:**

1. Non-equity instruments qualify in the live screen today. Run 12's Top-25 is exposed to this. This is a universe-definition defect, and it is the engineering team's to triage.
2. Any future factor work that touches volatility will hit the same artefact until the universe is cleaned.

---

## 4. Survivorship bias — does it inflate any of these numbers?

**It cannot inflate them in the direction that would rescue a configuration, but it does bias every number in this report upward, and it bites the skip-month configurations hardest.**

Three measured facts:

1. **`securities.delisting_date` is NULL for all 3,235 rows.** The database records zero delistings. Whether a name left the exchange is not represented anywhere in the scoring path.
2. **727 of 14,920 qualifier rows (4.9%) have no 120d forward return and are silently dropped from every IC.** Per-run attrition on the hold-out fold runs 5–8%. A name that stops printing prices contributes nothing rather than contributing a loss. Concretely: a qualifier that fell 60% and was suspended is *absent*, not scored at −60%.
3. Attrition is not constant across configurations. C1/C2 additionally drop rows with insufficient price history (7.2% / 9.4% of rows lack a valid 12-1 / 12-2 window). §2.2's common-support recomputation controls for this and changes nothing.

**Direction of the bias.** Dropping losers raises measured returns and compresses the left tail. Because the missing names are disproportionately recent decliners, a scoring rule that *avoids* recent decliners gains less from their removal than one that *buys* them. The baseline composite — whose dominant term is short-horizon breakout action — is the configuration most likely to have bought a name right before it stopped trading. So survivorship attrition most plausibly flatters **C0**, and the true baseline IC is likely somewhat worse than −0.0623.

**Specific to skip-month, as asked.** The concern is that a skip-month rule is measured on names whose recent reversal is precisely what the skip is designed to ignore, and that those names are the ones most likely to vanish. That mechanism would make C1/C2 look *better* than they are. They still lost. The survivorship caveat therefore reinforces the rejection of skip-month rather than qualifying it.

**Specific to C6.** Survivorship is not the driver here; §3 is. Gold ETFs do not delist.

**Net:** the hold-out ranking of configurations is robust to this bias, because the bias runs against the configurations that already won on construction. The *levels* are not trustworthy in absolute terms. Fixing this needs delisting dates and a scored-at-terminal-value convention for names that stop trading — a data-acquisition task, not an analysis choice.

---

## 5. Recommendation

**No improvement found. Do not change the live ranking composite.**

| Proposal | Verdict |
|---|---|
| P-4 · RS skip-month (C1, C2) | **Rejected on hold-out.** Best construction result (+0.058), negative on hold-out (−0.035 / −0.061), Top-25 worse by 2.9–3.9pp over 120d. |
| P-1 · Reduce/remove breakout weight (C3, C4) | **Rejected.** Removal *harms* the ranking, and the harm survives Bonferroni (IC −0.109, p=0.005). This contradicts the mechanism the methodology review proposed. |
| P-2 · Vol-scaled momentum (C6) | **Rejected as measured.** Positive IC fails Bonferroni (p=0.202) and collapses to −0.003 once non-equity instruments are excluded. Its apparent edge is 34% gold-ETF slots plus a low-volatility regime effect. As the review itself stated, this window cannot validate a crash-mitigation claim; it also does not validate a plain-ranking claim. |

Scorecard update: **11 research proposals, 0 promoted.** Ranking recomposition has now failed on hold-out five times (RP-000, RP-001, RP-003, RP-007, and this report's C1/C2/C3/C4/C5).

### What this changes about the standing diagnosis

The methodology review's §2 measurement stands — ~33% of the composite is constant among qualifiers, and the breakout engine carries ~44% of the remaining variance. That is arithmetic. But the *causal* claim built on it — that breakout dominance produces the negative ranking IC — is now contradicted: removing the breakout engine is the single worst configuration tested. The negative within-qualified-set ranking IC remains **unexplained**, as RP-002 left it.

### Where the leverage actually is

Nothing further should be spent on reweighting the existing engines. The three actions worth doing are all data, and two of them are prerequisites to any honest future test:

1. **Exclude non-equity instruments from the universe** (§3). This is a live production defect, not just a research nuisance, and it is small.
2. **Populate delisting dates and score terminated names at terminal value** (§4). Until then every IC in this repository is measured on survivors.
3. **Populate `securities.sector` / `.industry`** — still NULL for all rows, still blocking P-3 and still the reason `rs_sector_relative` was removed on a false empirical premise.

The prior program froze ranking research on the grounds that the binding constraint is data. This report reaches the same conclusion by a different route, and now names the three specific datasets.

---

## 6. Reproduction

Analysis scripts are session artefacts and were not committed; nothing in the repository was modified. The measurement is reproducible from the live database with:

- run series: `screening_runs` where `data_version LIKE 'historical:%:adjfix-recheck'`, `strategy_id=8`
- qualified set: `screening_results` where `hard_filters_passed`
- target: `forward_returns` at `horizon_days=120`, column `excess_return`
- engine scores for C3/C4: `SUM(contribution)/SUM(weight)` grouped by `engine_id` from `rule_results`, weighted by `strategies.config->'scoring'->'momentum_weights'`
- price-based scores (C1, C2, C6, C7): `COALESCE(adj_close, close)` from `ohlcv_daily`, positional trading-day offsets on the union calendar

If this line of work is reopened, the harness should be built properly first: `apply_parameter_overrides` is still imported and never called, so every variant test remains a bespoke script — which is why the earlier program's numbers were unreproducible, and why this one is documented at query level rather than pointed at a committed module.
