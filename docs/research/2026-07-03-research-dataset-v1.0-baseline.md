# Research Dataset v1.0 — Baseline Specification & Freeze Decision

**Prepared by:** Head of Quantitative Research, Momentum25
**Date:** 2026-07-03
**Status:** VERIFIED — FROZEN (see §9)
**Verification method:** Direct read-only SQL against live production DB (`momentum25-db-1`, postgres:16), not prior summaries. Every headline number was re-queried at authoring time.

---

## 1. Dataset Version, Scope, and Date Range (verified)

| Table | Rows (verified) | Date range (verified) | Distinct securities |
|---|---|---|---|
| `legacy_ohlcv_daily` (deep NSE archive) | **6,349,369** | **1994-11-03 → 2024-07-05** | 2,516 |
| `ohlcv_daily` (production/current provider) | **3,065,966** | **2019-10-01 → 2026-06-30** | 2,770 |
| `historical_universe` (reconstructed eligibility) | **1,984,159** | **2019-09-30 → 2024-07-05** | 2,497 (1,184 distinct dates) |
| `securities` (instrument master) | **3,072** | — | — |
| `forward_returns` | 3,886,471 | 570 runs × 6 horizons | — |
| `benchmark_index_daily` (NIFTY500) | 2,846 | 2015-01-01 → 2026-07-01 | 1 index |

**Effective research spine:** deterministic daily OHLCV from **1994-11-03 to 2026-06-30**, joined via the 3,072-row `securities` master (ISIN-first identity). Legacy archive and current provider overlap cleanly across 2019-10-01 → 2024-07-05.

## 2. Data Sources & Derivation Methods

1. **Deep history (1994–2019):** Legacy NSE bhavcopy archive → `legacy_ohlcv_daily`. ISIN-first identity resolution; symbol↔security↔ISIN strictly 1:1 in the current master (rename chains collapsed in-place).
2. **Current/production history (2019-10-01→):** Current EOD provider, repaired via RP-012 Phase 2 `CurrentProviderGapBackfill` (58-equity in-place-rename survivorship gap). Legacy ISIN used only as a lookup key; prices always sourced from the current provider (keeps Gate 4a an independent cross-check).
3. **Corporate-action inference:** `corporate_action_inference_log` — 4,895 rows, all flagged, 1995-09-05 → 2024-07-01, inferred deterministically from prev-close divergence. Canonical `corporate_actions` table is empty; the inference log is the operative record.
4. **Survivorship detection:** `survivorship_gap_event` — 9,900 events / 1,354 securities; T_gap=60 rule applied at delisting-inference time. `delisting_date` populated for 518 securities.

## 3. Validation Results — Four Gates (final accepted numbers)

| Gate | Definition | Result | Status |
|---|---|---|---|
| 4a | Overlap cross-provider reconciliation | 0.9887 forward-estimator; close/volume byte-fidelity ~perfect | **QUALIFIED PASS** (threshold revised 0.99→0.9887, user-approved) |
| 4b | Corporate-action audit | 42 independently-verified events, exact ex-dates, <8% ratio deviation | **PASS** |
| 4c | Regime coverage | Six corrections (2000, 2008, 2011, 2013, 2015-16, 2018) gap-free, ≥200-security floor cleared on all (re-verified independently) | **PASS** |
| 4d | Universe calibration/containment | Recall 0.6273 vs 0.95 target | **NOT cleanly passed — accepted open item** (explicit user direction) |

## 4. Known Limitations

1. 2019-2024 active-security gap (~18,392 occurrences / ~1,836 securities), root cause untriaged.
2. Gate 4d recall (0.6273) not decomposed into artifact-vs-genuine-disagreement buckets.
3. Pre-2019 survivorship incompleteness — `historical_universe` reconstruction bounded by the current 3,072-row master; not fully survivorship-free pre-2019.
4. GTLINFRA production defect (2020-07-13 volume ~3,900× inflated) — isolated, unfixed.
5. ETF/fund contamination — symbol-pattern heuristic with known false positives (PNBGILTS, JETFREIGHT, GOLDIAM confirmed still present); no instrument-type field exists.
6. `SINGLE` test fixture (security_id=1) confirmed still present in production `securities`.
7. No rename-linkage map for cross-rename trailing-return continuity.
8. 147 securities have NULL ISIN (one is SINGLE); 146 real names cannot be ISIN-resolved into legacy history.
9. `termination_reason` 0% populated; delisting semantics rest solely on `delisting_date` + `survivorship_gap_event`.
10. `legacy_ohlcv_daily_bak` (1,731,889 rows) exists as a pre-backfill snapshot — not a research table.
11. `corporate_actions` canonical table is empty — the inference log is authoritative instead.

## 5. Accepted Technical Debt (deliberate, signed-off trade-offs)

- Gate 4a threshold revised 0.99→0.9887 (user-approved).
- Gate 4d recall 0.6273 accepted as a disclosed containment ceiling, not a blocker (explicit user direction).
- SINGLE fixture, ETF false positives, GTLINFRA — bounded, enumerable, separate deferred cleanup tickets.
- `listing_date` redefined to earliest-observed-bar (true IPO date lost, equivalent for survivorship-screening).
- Period-correct-split rule implemented but not wired for identity-resolution paths that don't need it (provable no-op given collapsed rename chains).

## 6. Assumptions of Record

- Current-provider prices are the price-of-record; legacy ISIN used only as a join key.
- T_gap = 60 sessions for delisting inference (gap events logged more permissively from ~6 sessions).
- Liquidity floor L eligibility encoded in `historical_universe.eligible`/`reason` — researchers read the boolean, don't re-derive L.
- Regime floor: ≥200 securities required per correction window (all six clear it).
- Identity model: symbol↔security↔ISIN strictly 1:1 in the current master.

## 7. Readiness for Research

Dataset is materially stronger than the RP-000→RP-007 baseline and directly relaxes the binding constraint (regime diversity) that killed that program. Six gap-free correction regimes back to 2000, each clearing the ≥200-security floor — exactly what RP-005/RP-006 required to reopen.

- **RP-005** (relative extension cap): now has 2000/2008/2011/2018 correction folds. **Authorized to proceed.**
- **RP-006** (structural vs regime-conditional qualified-set IC inversion): now has ≥6 determinate regimes. **Authorized to proceed.**

Caveats shaping *how* research runs: pre-2019 work is not fully survivorship-free (disclose, don't claim survivorship-free results); the 146 NULL-ISIN names and ETF/SINGLE contamination must be screened out at query time by every study; `historical_universe` only covers 2019-09-30→2024-07-05, pre-2019 eligibility must be reconstructed from `legacy_ohlcv_daily` + L and inherits the survivorship limitation.

## 8. Remaining Blockers

**No disqualifying blocker.** Gate 4d's recall shortfall is a completeness gap, not a correctness defect (Gate 4a byte-fidelity confirms data quality where present) — it must be decomposed before any absolute breadth/recall/missed-winner-completeness claim is published, but does not block relative, contained-set, or regime-stratified studies (i.e., what RP-005/RP-006 actually need). The active-security gap, survivorship limitation, and contamination items are all enumerable/screenable, not corrupting.

## 9. Formal Recommendation & Freeze Decision

**FROZEN as Research Dataset v1.0.**

**Authorizations:** RP-005 and RP-006 are authorized to proceed against Research Dataset v1.0, subject to two standing conditions in every study: (1) apply the standard contamination pre-filter (exclude SINGLE id=1, NULL-ISIN names, ETF/fund heuristic hits) at query time; (2) for any pre-2019 fold, disclose the survivorship limitation and do not make survivorship-free or recall-denominated completeness claims until Gate 4d is decomposed.

**Deferred engineering backlog (not blockers, prioritized):**
1. Decompose Gate 4d recall into artifact vs genuine-disagreement buckets (highest priority — gates completeness-denominated research).
2. Triage the 18,392-occurrence active-security gap.
3. Deterministic instrument-type field (replace ETF heuristic); remove SINGLE fixture from production.
4. Rename-linkage map for cross-rename trailing-return continuity.
