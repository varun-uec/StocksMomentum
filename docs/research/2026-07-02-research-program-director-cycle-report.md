# Research Program Director — Cycle Report (RP-000 → RP-011)

**Date:** 2026-07-02
**Orchestrator:** Research Program Director (autonomous loop between `quant-researcher` and `engineering-lead`)
**Outcome:** Program paused program-wide. Hypothesis-testing frozen pending a data-acquisition decision. Production unchanged and safe across all eleven research cycles.

## Addendum — Reverse Engineering World-Class Momentum Investing (RP-009 → RP-011)

A separate research initiative (`docs/research/2026-07-02-reverse-engineering-world-class-momentum-report.md`) produced a behavioral taxonomy of momentum investing and 11 candidate deterministic characteristics (C1–C11). Program Director review caught that its top-ranked candidates duplicated already-closed work:

- **C9** (cross-sectional extension percentile cap, ranked #1) — functionally identical to **RP-005** (closed, rejected on hold-out, blocked pending correction-spanning data). The source report misattributed this failure mode to "RP-000."
- **C1** (trend smoothness, 50-day log-price R², ranked #4) — functionally identical to **RP-004** (closed, rejected — sign-unstable). A different lookback window is not a new mechanism.
- **C10** (multi-metric exhaustion score, ranked #2) — 80% of its weight is on the blocked C9 mechanism plus the already-weak `mq_acceleration` axis (RP-003).

These three were reclassified as closed/blocked, not reopened. The three remaining non-blocked, untested candidates were run through in-sample observational screening (per-run cross-sectional Spearman IC, sign-robustness by year, orthogonality checks) before any engineering hold-out ask — consistent with this program's discipline of not consuming engineering cycles on weak in-sample evidence:

| ID | Candidate | Result |
|---|---|---|
| RP-009 | C2 — Volume dry-up score | Closed in-sample: wrong sign at all horizons (60d mean IC −0.045, t=−1.35), sign-unstable across years |
| RP-010 | C8 — Breakout retest/failure test | Closed in-sample: literal spec was mathematically degenerate (provably always zero); corrected construction gave a significant but wrong-signed IC (60d mean IC −0.0696, t=−4.90, p<0.0001) and turned out to be another negative-IC member of the already-known breakout cluster (~0.18 correlated with `bo_false_breakout`) |
| RP-011 | C5 — Risk-adjusted momentum (return / ADR%) | Closed in-sample: wrong sign at all horizons (60d mean IC −0.050), ~0.5 collinear with existing `rs_rating`/`risk_extension` — not new signal, just a volatility-scaled re-expression of momentum the platform already ranks on |

**Finding:** every testable candidate in this report that reduces to a monotone function of the medium-term momentum/extension axis reproduces the same negative sign as the standing RP-002 ground truth (qualified-set ranking IC is negative). None added orthogonal signal. This is independent corroboration — via an entirely different research initiative and methodology (literature-driven characteristic discovery, not rule attribution) — of the original program's conclusion: linear/monotone recomposition of momentum-axis signals within the qualified pool is exhausted, and the binding constraint is data (regime diversity), not unexplored methodology.

**C6 (crowding proxy)** and **C11 (capacity score)** remain nominally open in the source report (C6 speculative/untested, C11 operational/non-alpha) but were deprioritized by research's own recommendation rather than run, since the pattern across three independent candidates makes a fourth in the same family low-expected-value. **C7 (breadth participation)** remains blocked as regime-conditional, same as RP-005/006.

This reinforces rather than changes the freeze recommendation in §11 below — no new data has arrived, no new stopping criterion is newly met beyond what was already documented, but the freeze is now corroborated by a second, independent research effort.

## Addendum 2 — The data floor was not real (supersedes §10's paid-vendor-only framing)

An engineering investigation (read-only, no code changed, no bulk data pulled) into the "hard NSE bhavcopy floor at 2019-10-01" cited throughout this program as the reason RP-005/006/009/010/011 could not be resolved found that **the floor is an artifact of the current ingestion code's URL choice, not a genuine NSE data-availability limit.**

The platform's `BhavcopyProvider` fetches NSE's "Full Bhavcopy and Security Deliverable data" report, which NSE only began publishing around October 2019 — hence the floor. But NSE's **legacy bhavcopy archive** (`archives.nseindia.com/content/historical/EQUITIES/{YYYY}/{MON}/cm{DD}{MON}{YYYY}bhav.csv.zip`) hosts genuine daily OHLCV **back to at least November 1994**, confirmed by direct probes (200 responses with valid, correctly-formatted OHLCV data at sample dates in 1994, 1996, 2000, 2005, 2010, 2015, and 2018) and remained reachable through July 2024, when NSE deprecated that legacy format in favor of a newer UDiFF endpoint (which the probes also confirmed working for 2024-2025 dates).

**This means ~25 additional years of free, real historical data (Nov 1994 → Sep 2019) are reachable from the same source without any paid vendor** — directly reopening the regime-diversity constraint that blocked RP-005, RP-006, and the reverse-engineering candidates. RP-008's Priority 1 recommendation (a paid Norgate-class vendor) is **not the only path** and may not be necessary at all for the core regime-diversity problem.

**This is not free — real work remains, and it is a research decision, not pure plumbing:**
- **Corporate-action adjustment fidelity** is the single biggest risk: 30 years of unadjusted splits/bonuses would corrupt long lookbacks (SMA150/200, 252d RS) if not handled correctly. The existing adjustment path's historical depth is unverified.
- **Universe/survivorship construction** for pre-2019 windows has no existing index-constituent history to lean on (NIFTY 500 membership history doesn't reach that far back in the platform); this requires a methodology decision on how the historical qualifying universe is defined, not just a data fetch.
- **Schema reconciliation**: the legacy format lacks delivery-volume/percentage columns present in the current provider (2019+), so delivery-dependent features (if any are added later) can't extend pre-2019; pure OHLCV/momentum characteristics can.
- **Overlap validation**: legacy and current-provider data overlap 2019-2024, which should be used to cross-validate the legacy ingestion before trusting it for the pre-2019-only window.

**Recommendation:** route this to `quant-researcher` to scope a formal data-acquisition research proposal (universe-construction methodology, corporate-action validation plan, overlap-reconciliation design) before `engineering-lead` builds the legacy-archive ingestion adapter. This is a materially cheaper and faster path than RP-008's paid vendor for the specific problem (regime diversity for walk-forward validation) that has blocked this program, though it does not replace RP-008's other recommendations (India VIX, point-in-time index membership, delivery-volume data) which remain relevant on their own merits.

## Addendum 3 — RP-012 executed and closed: historical data foundation extended to 1994

RP-012 ran through 3 engineering phases (adapter/schema, overlap-window validation, deep backfill) with multiple rounds of gate failures, root-cause diagnosis, and fixes — full detail in session transcripts. Final state:

- **Gate 4a (overlap reconciliation):** QUALIFIED PASS at 0.9887 (revised target, user-approved) — byte-fidelity perfect (close 1.0, volume 0.9999995+); coverage gap traced to a genuine current-provider limitation (delisted/merged names no longer in any provider's record) plus a disclosed, unresolved 18,392-occurrence active-security gap (separate open item, not blocking).
- **Gate 4d (universe calibration):** recall 0.6273 vs 0.95 target — not cleanly passed; disclosed as an open item, accepted as-is per user direction to proceed.
- **Gate 4b (corporate-action audit):** PASS — 42 independently-verified split/bonus events, exact ex-date match, <8% ratio deviation.
- **Gate 4c (regime coverage):** PASS — six correction regimes (2000 dot-com, 2008 GFC, 2011, 2013 taper tantrum, 2015-16, 2018 mid-cap crash) all gap-free with ≥200-security universe depth.
- **Backfill result:** `legacy_ohlcv_daily` now spans 1994-11-03 → 2024-07-05 contiguously, 6,349,369 rows.

**This resolves the core constraint that froze RP-005/RP-006**: regime diversity goes from 1 determinate correction fold (2022) to 6. Data is ready for research to reopen those walk-forward tests, with one disclosed caveat: the reconstructed historical universe is survivorship-limited to securities present in the current 3,072-row master (the deferred active-security-gap item), so it is not yet fully survivorship-free for pre-2019 windows. Several small items remain deliberately deferred as separate tickets (GTLINFRA production data defect, ETF/fund exclusion needing a proper instrument-type field, `SINGLE` test-fixture removal, rename-linkage map for cross-rename trailing-return continuity, gate 4d recall decomposition).

---

## 1. Accepted research proposals

**None.** Zero of eight proposals cleared out-of-sample validation and were promoted to production.

## 2. Rejected research proposals

| ID | Proposal | Mechanism | Verdict basis |
|---|---|---|---|
| RP-000 | Tighten `risk_extension` gate threshold 25%→18-20% | Absolute threshold on qualification gate | No effect on any North Star metric on hold-out |
| RP-001 | Re-weight `momentum_score` engines toward RS/risk | Engine-level linear re-composition | Pre-registered winning arm significantly regressed Rank IC OOS |
| RP-003 | Rank-neutralize the breakout-rule cluster | Rule-level linear re-composition | Wrong-sign point estimate on hold-out; 2 of 3 fix mechanisms mathematically degenerate |
| RP-004 | New characteristic: 63-day trend smoothness (`TREND_R2_63`) | New deterministic indicator | Hold-out IC indistinguishable from zero; sign unstable across quarters |
| RP-005 | Relative extension cap on Top-25 selection | Selection-stage exclusion filter | In-sample effect (2022-correction-driven) did not replicate in a benign hold-out regime |
| RP-007 | Admit near-miss (single-gate-failure) names into the qualified pool | Qualification-boundary inclusion | Null as pre-registered: admitted names entered the new Top-25 only 0.28×/run; no significant metric change |

## 3. Non-rejection outcomes

| ID | Type | Outcome |
|---|---|---|
| RP-002 | Methodology audit | Corrected a standing institutional error: qualified-set ranking IC is **negative**, not the previously-reported +0.028 (which conflated full-universe gating separation with actual within-pool ordering skill) |
| RP-006 | Diagnostic | **Underpowered** — established that the RP-002 inversion's structural-vs-regime-conditional nature cannot currently be resolved: only 2022 is statistically determinate; every benign-year stratum is indeterminate or has unmatured forward returns |
| RP-008 | Data-acquisition recommendation | Identified the single highest-leverage data acquisition (survivorship-free, corporation-action-adjusted NSE history with delisted names) that would reopen RP-005 and RP-006 simultaneously |

## 4. Production methodology evolution

**No production changes were made across the entire program.** `minervini_trend_template` v3 (strategy_id 30) remains the active, unchanged production configuration. Every proposal that reached implementation-stage evaluation was tested via deterministic exact-recomputation against persisted data in isolated research contexts — none touched the live scoring pipeline or dashboard.

## 5. Engineering validation summary

- Eight proposals independently walk-forward validated by `engineering-lead` with pre-registered acceptance gates, Bonferroni-corrected significance thresholds, and selection/hold-out splits research never touched during candidate selection.
- Two proposal-design flaws caught and corrected mid-loop: RP-003 initially had research self-grading its own hold-out (corrected to hand off execution); RP-005's fix candidates included mathematically degenerate mechanisms, caught by independent verification.
- No ruff/mypy/pytest regressions introduced; no tracked repository files modified by any proposal.
- RP-007's independent hold-out count (0.284 admitted names/run into Top-25) confirmed research's structural pre-check (0.07/run in-sample) directionally and in magnitude — cross-validation between research's in-sample analysis and engineering's independent out-of-sample recomputation held up consistently across the program.

## 6. Remaining research backlog

**Blocked on data acquisition (do not retry until the RP-008 dataset, or equivalent, is acquired and validated):**
- RP-005-class regime-conditional exclusion filters (needs a hold-out spanning an actual correction).
- RP-006: structural-vs-regime-conditional diagnosis of the qualified-set ranking inversion (needs 6+ statistically determinate correction strata, currently has 1).
- RP-007's deprioritized simplification lead (gate/ranker redundancy) — gated behind the same correction-spanning-fold prerequisite, since a gate's real value is drawdown protection, unfalsifiable in a benign window.

**Exhausted, closed without reopening triggers:** linear re-composition of the existing 17 scoring rules (threshold/engine/rule granularity, RP-000/001/003), one new-characteristic attempt (RP-004), and missed-winner-via-gate-relaxation (RP-007) — the qualification gates and the ranker are redundant in that direction; names the gates would admit are names the ranker rejects anyway.

**Open, unvalidated lead:** per-run cross-sectional dispersion of `risk_extension` correlates with per-run ranking IC (ρ=-0.231, p=0.0018) — exploratory, regime-confounded, parked pending data.

## 7. Remaining engineering backlog

- `ExperimentUseCase._run_variant` / `ParameterResearchUseCase.execute` remain broken stubs — every walk-forward test this program required a bespoke exact-recomputation harness. A general parameter/threshold walk-forward capability is a legitimate future task.
- Baseline ruff (~102) / mypy (~23) findings, concentrated in `interface/api/routers/research.py` — pre-existing, out of scope throughout, unresolved.
- **New: Data Acquisition Spec (RP-008 §4)** — vendor evaluation (Norgate-class survivorship-free NSE panel, India VIX history), format/schema requirements, and a five-step validation gate before any walk-forward reuse. Fully scoped, ready for engineering once a spending decision is made — **see §10**.

## 8. Current methodology maturity assessment

**Production is safe and defect-free** — no regressions across eight cycles; every exact-recomputation harness independently confirmed the scoring pipeline behaves exactly as specified.

**Ranking quality remains the platform's acknowledged weak point**, now materially better understood: the qualified-set ranking IC is confirmed negative (RP-002); three independent re-composition remedies and one new-characteristic attempt have failed cleanly; the qualification-boundary (missed-winner) angle is also closed; and the inversion's regime-dependence is diagnosed as genuinely unresolvable with current data (RP-006), not unexplored.

## 9. Estimated remaining improvement potential

**Low under current data (~5%, unchanged from the prior cycle's estimate).** Every avenue not gated on regime-diverse data has now been tested and closed (ranking recomposition at all granularities, one characteristic-discovery attempt, missed-winner analysis). The estimate would materially increase — research's own framing is that RP-008's dataset is "the master key" — if the recommended data acquisition proceeds, since it would reopen the two most information-rich open threads (RP-005, RP-006) with an adequately powered sample for the first time in the program's history.

## 10. Data acquisition recommendations

**Priority 1 (critical):** Survivorship-bias-free, corporate-action-adjusted NSE daily OHLCV with delisted constituents and point-in-time index membership (Norgate-class vendor). Extends clean regime coverage from 1 correction (2022) to 6-8 (2000, 2004, 2008 GFC, 2011, 2013, 2015-16, 2018). Reopens RP-005, RP-006, and the RP-007 simplification lead simultaneously. Cost tier: medium (subscription, not institutional-grade pricing).

**Priority 2 (cheap enabler):** India VIX historical series (free, NSE, 2008+) — supplies a deterministic, point-in-time regime label, converting RP-005-class filters from hindsight-labeled to contemporaneously-testable. Multiplies Priority 1's value; not standalone.

**Priority 3-4:** Point-in-time index constituent history (likely bundled with Priority 1) and security-wise delivery volume (free, NSE, feeds the new-characteristic bucket rather than the regime constraint).

Full engineering-ready acquisition and validation spec (vendor evaluation steps, schema requirements, a five-step data-integrity validation gate) is in `docs/research/` under this cycle's RP-008 record — not repeated here in full; see §7.

## 11. Final recommendation

**Freeze Methodology, program-wide, pending a data-acquisition decision.** This extends the prior cycle's ranking-specific freeze (RP-000→006) to the whole hypothesis-testing program, now that missed-winner analysis (RP-007) and the simplification lead have also been tested/assessed and closed for the same underlying reason: every remaining high-value question requires regime-diverse data the platform does not currently have.

This is **not** "no remaining high-value deterministic research opportunities exist" (stopping criterion 5) — RP-008 identifies exactly what would reopen the two most valuable open threads. It **is** stopping criterion 2: engineering and research both conclude further progress requires new data, not new methodology.

**Action required from the Director's principal (the user), not from either subagent:** the Priority 1 data acquisition is a real commercial decision (vendor subscription, licensing terms, cost) that neither `quant-researcher` nor `engineering-lead` has authority to execute autonomously, and the Director does not authorize spending on the principal's behalf. This is the natural handoff point — the program has done everything it can do with existing data and correctly identified the next dependency is a human business decision, not further agent work.

---

*Prepared by the Research Program Director orchestrating `quant-researcher` and `engineering-lead` per the autonomous research-loop mandate. Institutional memory persisted in the auto-memory system (`research_closed_and_backlog.md`, `MEMORY.md`) for continuity across future sessions.*
