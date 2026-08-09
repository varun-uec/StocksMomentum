# Research Proposal: Momentum Selection Methodology Review

**Status:** Research output. No code changes proposed for immediate implementation.
**Date:** 2026-08-09
**Scope discipline note:** this document deliberately covers **four** ideas with real evidence rather than ten superficially. §8 lists what is explicitly deferred.

---

## Context

The system qualifies stocks through an 8-rule Minervini-style trend gate plus a liquidity gate, then ranks survivors by a weighted `momentum_score`. Eight prior research proposals (RP-000…RP-007) attempted to improve ranking quality; **zero were promoted**, and RP-002 concluded that within-qualified-set ranking IC is *negative*. The program was frozen on the grounds that "the binding constraint is data, not methodology."

This review asks a broader question than the prior RPs did: not "which weight should change" but "is the selection architecture the right shape at all, measured against the momentum literature."

**The headline result is that the freeze conclusion was partly wrong.** There is a structural defect in the ranking composite that is measurable *today, from existing data, with zero forward returns* — and it explains the negative ranking IC that three failed RPs were groping at. That finding is presented in §2.

---

## 1. Data reality check — what is actually validatable today

This section is deliberately first, because it constrains every recommendation below.

| Asset | State | Source |
|---|---|---|
| `forward_returns` | **0 rows** | live DB |
| `screening_runs` | **5 runs, spanning 2026-08-07 → 2026-08-09** | live DB |
| `screening_results` | 6,210 rows (~230 qualifiers/run) | live DB |
| `ohlcv_daily` | 3.08M rows, 3,220 symbols, **2019-10-01 → 2026-08-07** | live DB |
| `adj_close` | 86.2% populated; `adj_factor ≠ 1` on 261,534 rows | live DB |
| `benchmark_index_daily` | NIFTY500, 2015-01-01 → 2026-08-07 | live DB |
| `securities.sector` / `.industry` | **0 of 3,235 populated** | live DB |
| `legacy_ohlcv_daily` | **0 rows** (`_bak` holds 2019-09-30 → 2024-07-05 only) | live DB |

### 1.1 Can `forward_returns` be populated from existing data? Yes — with a prerequisite.

`ForwardReturnsBackfill` ([forward_returns_backfill.py](backend/src/momentum25/application/use_cases/research/forward_returns_backfill.py)) is complete and correct: horizons `(5,10,20,60,120,252)`, benchmark-relative, uses adjusted close with raw fallback. It is empty **only because nothing calls it in a loop** — its single caller is a one-off script.

But it computes forward returns *for a run*, and there are only 5 runs across 3 calendar days. So the real prerequisite chain is:

1. Generate a historical run series via `HistoricalScreeningUseCase` at monthly `as_of_date`s. Usable window is bounded by the 252-day indicator warm-up (start ≈ **2020-10**) and the 120-day forward horizon (end ≈ **2026-02**) → **~65 monthly runs**, or ~280 weekly.
2. Backfill forward returns over those runs.
3. Only then are IC, scorecard, and walk-forward meaningful.

This is a few hours of compute, not a data-acquisition project. **Recommendation: do this before any further ranking research.** It is the single highest-leverage engineering action available.

### 1.2 Three corrections to the standing record

These matter because prior conclusions rest on them.

- **The "Research Dataset v1.0" that authorized unfreezing RP-005/RP-006 is not in this database.** `docs/research/2026-07-03-research-dataset-v1.0-baseline.md` claims 1994–2024 legacy history (6.35M rows) providing 2000/2008/2011/2018 correction folds. `legacy_ohlcv_daily` has **0 rows**; the backup table covers 2019-09-30 → 2024-07-05. There is exactly **one** correction (2022) in the available history. The RP-006 data gate is therefore still closed, contrary to that document.
- **The backlog's S1 item ("`adj_factor` hardcoded to 1") is stale.** 261,534 rows carry a non-unit adjustment factor. Corporate-action adjustment is live. This *removes* one stated blocker.
- **`rs_sector_relative` and `rs_industry_relative` were removed from strategy v3 for the wrong reason.** The v3 config description cites "0% pass rate across 90,657 evaluations." Those rules percentile-rank against peers matching `security.sector`; **sector is NULL for all 3,235 securities**. They failed because the input data does not exist, not because sector-relative strength lacks signal. This is a data defect misdiagnosed as an empirical result.

### 1.3 Parameter overrides do not work

`ExperimentUseCase._run_variant` passes the *base* strategy name to screening and never applies overrides; `ParameterResearchUseCase.execute` literally sets `var_results = base_results`. The pure function `apply_parameter_overrides` ([services.py:753](backend/src/momentum25/domain/research/services.py#L753)) is correct, complete, and **imported but never called**. Until a caller exists, every config-variant backtest requires a bespoke harness — which is exactly why the prior program's numbers are unreproducible.

**Consequence for this proposal: nothing below is back-tested.** Every empirical claim in §2 is a *cross-sectional structural measurement* on existing screening output, which needs no forward returns. Every *return* claim is explicitly marked "not yet validatable."

---

## 2. Finding A — the ranking is a breakout-timing score, not a momentum-strength score

This is the substantive finding of this review, and it is measured, not argued.

### 2.1 Method

For production run 12 (232 qualifiers), reconstruct each engine's contribution to `momentum_score` from `rule_results` (`Σcontribution / Σweight × engine_weight / Σengine_weights × 100`), then measure its cross-sectional dispersion *within the qualified set*. Reconstruction validates: engine means sum to 65.03 vs actual mean `momentum_score` 65.04.

### 2.2 Result

Per-rule dispersion among the 232 qualifiers:

| Rule | sd(contribution) | distinct values | Comment |
|---|---|---|---|
| `rs_rating` | 0.522 | 30 | real signal, but coarse |
| `bo_pivot_breakout` | 0.514 | 185 | continuous |
| `bo_followthrough` | 0.486 | **2** | binary |
| `pattern_vcp` | 0.464 | 17 | |
| `vol_accumulation_days` | 0.450 | **2** | binary |
| … | | | |
| `mq_acceleration` | 0.168 | 34 | mean 0.053 — almost never fires |
| `pattern_cup_with_handle` | 0.189 | 7 | mean 0.038 — almost never fires |
| **all 8 `tt_*` rules** | **0.0000** | **1** | constant by construction |
| `vol_liquidity_min` | **0.0000** | **1** | constant by construction |

Aggregated to engines:

| Engine | mean pts | sd pts | var share | corr with `momentum_score` |
|---|---|---|---|---|
| `relative_strength` | 10.40 | 5.222 | **44.8%** | 0.591 |
| `breakout` | 7.77 | 5.145 | **43.5%** | **0.830** |
| `volume_accumulation` | 7.62 | 1.964 | 6.3% | 0.487 |
| `pattern` | 1.45 | 1.427 | 3.3% | −0.120 |
| `risk` | 2.71 | 0.844 | 1.2% | −0.403 |
| `momentum_quality` | 5.08 | 0.709 | 0.8% | 0.119 |
| `trend_template` | **30.00** | **0.000** | **0%** | undefined |

### 2.3 Interpretation

Three structural facts follow:

1. **~33% of `momentum_score` is a constant among qualifiers.** The trend template is an *engine-level gate*: `passed_gate = all(rules)`, and `engine_score = passed_count/8`. Every qualifier therefore scores exactly 1.0 → exactly 30.00 points. Add the rule-level liquidity gate and ≈33% of the composite carries zero cross-sectional information. Being a gate and being a ranking input are mutually exclusive, and the config uses the same rules for both.

2. **The ranking is dominated by the `breakout` engine** — highest correlation with the final score (0.830) and ~44% of its variance, tied with RS. `bo_pivot_breakout`, `bo_followthrough`, `bo_false_breakout` are all **short-horizon (days-to-weeks) timing signals**.

3. **The remaining engines are near-dead weight.** `momentum_quality` carries 0.8% of variance (its `mq_acceleration` rule has mean 0.053 — it essentially never fires); `pattern` carries 3.3% and correlates *negatively* with the score.

So the production ranking, among stocks that have already passed a 12-month trend gate, orders them primarily by **how close they are to a short-term breakout pivot** — i.e. by very recent price action.

### 2.4 Why the literature predicts this ranks badly

This is precisely the configuration that momentum research has warned about for 35 years:

- **Short-horizon reversal.** Jegadeesh (1990, *JF* 45(3)) and Lehmann (1990, *QJE*) document robust *negative* autocorrelation at the 1-week-to-1-month horizon. This is why the standard academic momentum signal is **12-2** (or 12-1) — the most recent month is *deliberately skipped*, because including it contaminates a positive-autocorrelation signal with a negative-autocorrelation one. Fama & French (2008, "Dissecting Anomalies," *JF*; 2012, *JFE* 105(3)) and Asness, Moskowitz & Pedersen (2013, "Value and Momentum Everywhere," *JF* 68(3)) all use the skip-month convention.
- The system does the opposite twice over: the ranking's dominant term is *pure* recent action, and its RS input (§4.2) also uses windows ending **today** with no skip.

**This is a coherent, mechanism-level explanation for RP-002's negative within-pool ranking IC** — something three prior linear-recomposition RPs (RP-000/001/003) failed to find, because re-weighting engines cannot fix a signal that is measuring the wrong horizon. It also explains the recorded oddity that **Top-10 hit rate (45.8%) was worse than Top-25 (50.9%)**: the more strongly the score is expressed, the more short-horizon reversal it loads.

**Confidence:** the structural measurement is certain (it is arithmetic on live data). The *causal* link to negative IC is a hypothesis consistent with the literature and with the recorded IC sign, but is not itself back-tested — that requires §1.1.

---

## 3. Does `tt_sma_stack`'s claimed equivalence hold rigorously?

**Verdict: it holds under the production config, but the claim as written is false in general, and the rule is redundant.**

`tt_sma_stack` evaluates `sma50 > sma150 AND sma50 > sma200` ([trend_template.py:245](backend/src/momentum25/domain/engines/trend_template.py#L245)); the docstring calls this a "simplified stack."

The full Minervini chain is `sma50 > sma150 > sma200`, i.e. `(50>150) ∧ (150>200)`.

- Rule 4 gives `(50>150) ∧ (50>200)`. Rule 2 (`tt_sma150_above_sma200`) gives `(150>200)`.
- Conjunction of rules 2 and 4 ⟹ `(50>150) ∧ (150>200)` ⟹ the full chain. ✅
- Conversely the chain ⟹ `50>200` by transitivity, so `rule2 ∧ rule4 ≡ chain`. **Equivalence holds — but only as a conjunction, and only because the gate requires *all* rules to pass.**

Two caveats that make the claim unsafe as stated:

1. **It is config-conditional.** Rules are a configurable subset (`cfg.rules`; if empty, all). A config enabling rule 4 without rule 2 gets `(50>150) ∧ (50>200)`, which permits `150 < 200` — a stock in a 150/200 death cross passes the "stack." Several benchmark configs in `docs/architecture/strategies/` select rule subsets. The equivalence is an emergent property of one config, documented as a property of one rule.
2. **The `50>200` clause is redundant** given rule 2, so the MA-configuration information is spread across four collinear rules (1, 2, 4, 5) out of eight. This inflates the trend template's *nominal* rule count without adding independent information — though per §2 it has no ranking effect, since all eight are constant among qualifiers.

**Recommendation: documentation/assertion fix, not a behaviour change.** Correct the docstring to state the equivalence is joint with `tt_sma150_above_sma200`, and reject at config-load any strategy enabling `tt_sma_stack` without it. No score, rank, or gate membership changes → no ADR-009 determinism risk.

---

## 4. Literature assessment of the qualification gate

### 4.1 Where the trend template aligns with academia (better than it gets credit for)

| TT rule | Academic counterpart |
|---|---|
| `tt_near_52w_high` (within 25% of 52w high) | **George & Hwang (2004), "The 52-Week High and Momentum Investing," *JF* 59(5)** — nearness to the 52-week high *dominates* Jegadeesh–Titman momentum in cross-sectional tests and is less prone to long-run reversal. Strong, direct support. |
| `tt_above_52w_low` (≥30% above 52w low) | Same paper's other tail; also Bhootra & Hur (2013) on the recency ratio. |
| MA-stack rules 1/2/4/5 | Trend-following filters; Moskowitz, Ooi & Pedersen (2012, *JFE* 104(2)) on time-series momentum. Weaker cross-sectional pedigree than the 52-week-high pair — these are largely a smoothed restatement of "12-month return is positive." |
| `tt_rs_rating_min ≥ 70` | Cross-sectional relative momentum — Jegadeesh & Titman (1993, *JF* 48(1), 65–91); confirmed out-of-sample in J&T (2001, *JF* 56(2)) and internationally by AMP (2013). Works in India specifically: Sehgal & Balakrishnan; Agarwalla, Jacob & Varma (IIM-A India factor library). |

**Assessment: the gate is defensible.** It is essentially a conjunction of (a) 52-week-high proximity and (b) top-30% relative strength, both of which are among the best-documented cross-sectional momentum signals. The prior program's evidence that "the gate does more work than the ranking" is consistent with this — the gate is the part grounded in literature.

### 4.2 Where it diverges — and where the literature says the divergence costs

**(a) No skip-month.** `RSRatingsService` computes overlapping trailing returns `{63:0.4, 126:0.2, 189:0.2, 252:0.2}` **all ending today**. Academic convention (Fama-French 2008/2012; AMP 2013) measures t-12→t-2 and skips t-1. The system's heaviest RS weight (0.4) is on the 63-day window, which fully contains the reversal-prone recent month. See §2.4.

Note also there are **two divergent RS implementations**: `RSRatingsService` (overlapping, used by screening) and `relative_strength_pipeline.py` (non-overlapping IBD quarters `(2·q4+q3+q2+q1)/5`). Only the former drives qualification. Which one is "the" RS rating is ambiguous in the codebase.

**(b) No volatility scaling anywhere.** Neither qualification nor ranking normalises momentum by risk. See §5 / P-2.

**(c) Volume/accumulation runs *against* the cross-sectional evidence.** `vol_breakout_confirm` rewards relative volume ≥ 1.4, and `vol_accumulation_days` rewards up-days on above-average volume. But **Lee & Swaminathan (2000), "Price Momentum and Trading Volume," *JF* 55(5)** find that *high*-volume winners exhibit **worse** subsequent performance and faster reversal than low-volume winners — volume proxies for over-extrapolation and investor disagreement. The engine encodes the practitioner prior (volume confirms) where the academic evidence points the other way at the ranking horizon. Note the two are not strictly in conflict — L&S measure 3–12 month holding, the engine targets days-to-weeks entries — but the system uses this signal for *ranking* (6.3% of variance, +0.49 correlation), which is the horizon where L&S applies.

**(d) The `fundamental` engine is disabled with weight 0.0.** This is the largest literature-supported gap. CANSLIM's **C** (current quarterly earnings) and **A** (annual earnings growth) are *earnings momentum*, and **Chan, Jegadeesh & Lakonishok (1996), "Momentum Strategies," *JF* 51(5)** show price momentum and earnings momentum (SUE, analyst revisions) are **distinct and complementary** — neither subsumes the other. Adding a quality/profitability screen also reduces crash exposure (Asness, Frazzini & Pedersen, 2019, "Quality Minus Junk," *RAST* 24; Novy-Marx 2013 on gross profitability). The system is **100% price-and-volume**, which caps its achievable information ratio regardless of how well the price signal is engineered.

### 4.3 Practitioner frameworks vs the literature

- **Minervini's Trend Template** is, structurally, a *conjunctive gate* on 52-week-high proximity + relative strength + MA alignment. Its two strongest components have direct academic support (George & Hwang; J&T). Its weakest claim relative to literature is that eight conjunctive binary conditions add information beyond ~2 independent ones — §2.2 shows the eight rules are perfectly collinear *at the gate boundary* by construction, and §3 shows at least one is logically redundant.
- **CANSLIM** (O'Neil, 1988) is broader: C/A are earnings momentum (well-supported, §4.2d), **L** is relative strength (= J&T), **N/S/I/M** are narrative or market-timing components with far weaker cross-sectional evidence. The system has implemented **L** and the trend/volume mechanics, and none of **C/A** — i.e. it has adopted the parts of CANSLIM the literature supports *least differentially* and omitted the parts it supports most.
- **Divergence in kind:** both practitioner frameworks are *entry-timing* systems designed around discretionary position management (stops, pyramiding, exits). Academic momentum is a *portfolio-formation* system with fixed rebalancing. The codebase has imported the entry-timing machinery (breakout pivots, follow-through) into what is architecturally a portfolio-formation ranking — §2 is the direct consequence of that category error.

---

## 5. Proposals

Each carries a recommendation of **Adopt now** / **Promising, needs data** / **Not supported today**.

### P-1 · Separate the gate from the ranker
**Grounding:** §2.2 (measured), plus the general principle that a conjunctive gate has zero within-pool variance by construction.
**Change:** stop computing the ranking score from gate engines. Rank qualifiers on an explicit score built only from signals with cross-sectional variance among survivors.
**Evidence today:** removing `trend_template` from `momentum_weights` is provably **rank-neutral** (subtracting a constant from every qualifier cannot reorder them) — so this is a pure interpretability fix on its own, and `momentum_score` stops having an artificial ~47 floor. The *alpha* comes only when paired with P-2.
**Recommendation: Adopt now as a cleanup** (zero ranking effect, provable); the substantive version depends on P-2.

### P-2 · Rank by volatility-scaled 12-2 momentum
**Grounding:**
- 12-2 formation: Jegadeesh & Titman (1993); skip-month rationale Jegadeesh (1990), Lehmann (1990); convention per Fama-French (2008, 2012), Asness-Moskowitz-Pedersen (2013).
- Volatility scaling: **Barroso & Santa-Clara (2015), "Momentum has its moments," *JFE* 116(1), 111–120** — scaling WML by realised volatility of the prior 6 months roughly doubles Sharpe and removes the crash-driven excess kurtosis. **Daniel & Moskowitz (2016), "Momentum Crashes," *JFE* 122(2), 221–247** — momentum has conditional negative skew concentrated in panic states (bear market + elevated volatility + market rebound); dynamically scaled momentum substantially mitigates it.
- Related: Blitz, Huij & Martens (2011), "Residual momentum," *JEmpFin* 18(3) — momentum on factor-model residuals delivers similar returns with materially lower crash risk. Simpler here: total-vol scaling, since no India factor model is wired in.
**Change:** ranking score = *t*−252→*t*−21 return ÷ realised daily-return volatility over the same window (or ATR%, already computed at [indicator_pipeline.py:217](backend/src/momentum25/infrastructure/pipelines/indicator_pipeline.py#L217)), cross-sectionally z-scored over qualifiers.
**Does it change *qualification* historically?** Only if applied to the gate. `tt_rs_rating_min` is the only gate rule this would touch. **Not yet answerable** — it needs the run series from §1.1. A vol-scaled RS rating will systematically *demote* high-ADR names, which the `risk_atr` rule (max_adr_pct 8) already partly does with a hard threshold; there is likely overlap worth measuring before adding both.
**Recommendation: Promising, needs data.** Strongest literature grounding of anything here, and directly targets the defect measured in §2. Must not ship without the §1.1 backfill and a hold-out fold.

### P-3 · Sector concentration limits
**Grounding:** Moskowitz & Grinblatt (1999, "Do Industries Explain Momentum?" *JF* 54(4)) argue industry momentum accounts for much of individual momentum; Grundy & Martin (2001, *RFS* 14(1)) argue the reverse — that industry- and factor-neutralised momentum is *stronger and more stable*. Either way, an un-capped Top-25 from a single-market trend gate is a concentrated industry bet. Grinold's Fundamental Law (1989, *JPM*) — IR ≈ IC·√breadth — makes explicit that 25 correlated names deliver the breadth of far fewer independent bets.
**Blocker discovered:** **`securities.sector` and `.industry` are NULL for all 3,235 rows.** Sector concentration cannot even be *measured* today, let alone capped. This same defect invalidates the v3 removal of `rs_sector_relative`/`rs_industry_relative` (§1.2).
**Recommendation: Not supported today — blocked on a missing dataset.** The prerequisite is populating industry classification (NSE sector, or a GICS-like mapping). That is a small, deterministic data-acquisition task with an unusually high payoff: it unblocks concentration limits, sector-relative RS, *and* correction of a false empirical conclusion. **This is the second-highest-leverage action after §1.1.**
Note: pairwise return-correlation limits are computable from `ohlcv_daily` without sector data, but a correlation-constrained selection is non-trivially order-dependent and would need care under ADR-009; defer until sector caps (the simpler, better-grounded control) are testable.

### P-4 · Add the skip-month to the RS rating
**Grounding:** as P-2. Narrow, cheap version of the same idea.
**Change:** `RSRatingsService` measures each window ending at *t*−21 rather than *t*. Also resolve the two-divergent-RS-implementations ambiguity (§4.2a).
**Effect on qualification:** this *would* change the qualified set (it moves `tt_rs_rating_min`), unlike P-1. Magnitude unknown; measurable as soon as §1.1 exists.
**Recommendation: Promising, needs data.** Attractive as the cheapest single test of the §2.4 hypothesis: if reversal contamination is real, skipping the month should improve IC on its own.

---

## 6. Validation plan (Phase 3b-compliant)

Nothing above ships without this. Rules carried forward unchanged from the Phase 3b methodology log:

1. **Justify before observing.** Each configuration is registered with its rationale and in-sample screen result *before* the hold-out fold is touched.
2. **Cap 5–8 configurations per idea.** No extension of the search if all fail.
3. **No re-mining a hold-out fold.** One fold, one look, per idea.
4. **Log every attempt** in the running table below, including failures and abandoned configs.

**Prerequisite work, in order (all engineering, all deferred out of this task):**

| # | Action | Unblocks |
|---|---|---|
| 0 | Populate `securities.sector` / `.industry` | P-3, and re-testing the v3 rule removals |
| 1 | Generate monthly historical runs 2020-10 → 2026-02 (~65) | everything |
| 2 | Run `ForwardReturnsBackfill` over that series | IC, scorecard, walk-forward |
| 3 | Wire `apply_parameter_overrides` into `ExperimentUseCase._run_variant` | reproducible config variants |

**Folds.** In-sample **2020-10 → 2024-12**; hold-out **2025-01 → 2026-02** (bounded by the 120-day maturity horizon). Note honestly: this hold-out is a **benign regime with no correction** — the exact condition that made RP-005 and RP-006 indeterminate. Any result here is evidence about benign-regime ranking skill only, and *cannot* validate crash-mitigation claims. P-2's Barroso/Santa-Clara rationale is specifically a crash-regime claim and will therefore remain **partially unvalidatable** even after the backfill. Say so in the write-up rather than over-claiming.

**Primary metric.** Within-qualified-set Rank IC at 120 days (the RP-002 quantity), plus Top-25 vs qualified-pool spread. Per the quant-researcher mandate, IC is supporting evidence — the decision metric is realised Top-25 excess return over NIFTY500.

**Running attempt table** (to be filled by the executing round):

| ID | Idea | Config | In-sample screen | Hold-out | Verdict |
|---|---|---|---|---|---|
| — | — | — | *not yet run* | *not touched* | — |

---

## 7. Recommendation summary

| Proposal | Grounding | Evidence today | Recommendation |
|---|---|---|---|
| §3 `tt_sma_stack` doc/config-guard fix | logical proof | equivalence verified; config-conditional | **Adopt now** (no behaviour change) |
| P-1 Drop gate engines from ranking composite | §2 measurement | 33% of score is constant; removal provably rank-neutral | **Adopt now** as cleanup |
| P-2 Vol-scaled 12-2 ranking | J&T '93; Barroso & Santa-Clara '15; Daniel & Moskowitz '16 | structural defect measured; returns not testable | **Promising, needs data** |
| P-4 Skip-month in RS rating | Jegadeesh '90; Fama-French '12 | not testable | **Promising, needs data** — cheapest test of §2.4 |
| P-3 Sector concentration limits | Moskowitz & Grinblatt '99; Grundy & Martin '01; Grinold '89 | **sector NULL for 3,235/3,235** | **Not supported today** — blocked on data |
| Volume/accumulation in ranking | Lee & Swaminathan '00 | contradicts current prior; 6.3% of variance | **Flagged, not proposed** — needs its own round |
| Fundamental engine (CANSLIM C/A) | Chan-Jegadeesh-Lakonishok '96; AFP '19 | engine disabled, weight 0 | **Deferred** — data acquisition |

**Was the research freeze correct?** Partly. It is correct that *regime-conditional* questions (RP-005, RP-006) remain blocked — and §1.2 shows they are *more* blocked than believed, since the correction-spanning dataset does not exist in this database. But the freeze's premise that "the binding constraint is data, not methodology" does not survive §2: a 33%-constant, breakout-dominated ranking composite is a methodology defect, it was measurable at any point in the last three research cycles with a single SQL query, and no prior RP measured it.

---

## 8. Explicitly deferred to future rounds

Listed so the omissions are on the record rather than silent:

- **Residual / idiosyncratic momentum** (Blitz-Huij-Martens 2011) — needs an India factor model (market/size/value returns). Data-acquisition item.
- **The "echo" question** — whether *t*−12→*t*−7 dominates *t*−6→*t*−2 (Novy-Marx 2012, *JFE* 103(3); disputed by Goyal & Wahal 2015, *JFQA*). Cleanly testable once §1.1 lands; deliberately excluded here to keep P-2 to a single pre-registered hypothesis.
- **Frog-in-the-Pan / information discreteness** (Da, Gurun & Warachka 2014, *RFS* 27(7)) — the academic form of Minervini's "orderly uptrend." Deprioritised because RP-004 already rejected the correlated `TREND_R2_63` characteristic; FIP's ID statistic differs enough to be worth one future attempt, but not ahead of P-2.
- **Holding period and rebalance frequency.** The system produces a daily snapshot with no defined holding period; J&T's framework is formation *and* holding. Cannot be studied until §1.1.
- **Turnover, transaction costs, and India-specific frictions** (STT, impact in mid/small caps). Every proposal above is gross-of-cost; P-2 in particular may raise turnover.
- **Position sizing / risk parity across selected names** — out of scope for a selection system, but the natural companion to P-3.
- **Re-testing the v3 rule removals** (`rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend`) once sector data exists.
- **Re-deriving RP-002's actual numbers.** Its magnitude, horizon, sample size, and pool definition exist nowhere on disk — it is a single unsourced sentence that three subsequent programs treated as settled. §2 offers a mechanism for it, but the finding itself should be re-derived, not cited.

---

## Verification

This document proposes no code changes. To reproduce its empirical claims:

```bash
# Finding A — engine variance decomposition (§2.2)
docker exec momentum25-db-1 psql -U momentum25 -d momentum25 -c "
with w(engine_id,ew) as (values ('trend_template',3.0),('relative_strength',2.0),
  ('volume_accumulation',1.0),('pattern',1.0),('breakout',1.5),('momentum_quality',1.0),('risk',0.5)),
es as (select rr.security_id, rr.engine_id, sum(rr.contribution)/sum(rr.weight) escore
  from rule_results rr where rr.run_id=12 and rr.security_id in
   (select security_id from screening_results where run_id=12 and hard_filters_passed) group by 1,2)
select es.engine_id, round(avg(es.escore*w.ew/10.0*100),2) mean_pts,
       round(stddev(es.escore*w.ew/10.0*100),3) sd_pts
from es join w using(engine_id) group by 1 order by sd_pts desc;"

# §1 data reality
docker exec momentum25-db-1 psql -U momentum25 -d momentum25 -c "
select (select count(*) from forward_returns) fwd,
       (select count(*) from screening_runs) runs,
       (select count(sector) from securities) with_sector,
       (select count(*) from legacy_ohlcv_daily) legacy;"
```

Next action if approved: execute prerequisites 0–3 in §6 (engineering-lead scope), then return for the pre-registered P-2/P-4 test round.
