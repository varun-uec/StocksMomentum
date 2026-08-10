# RP-014 — Historical Data Extension (crash-era coverage)

**Date:** 2026-08-10
**Objective:** Extend historical price coverage back through the three major
corrections — dot-com (~2000-2001), GFC (2008), COVID crash (2020) — so the
crash-mitigation backtest can be validated over real crashes. Data acquisition
and verification only. No screening runs, no forward-return generation.

---

## 1. Deliverables

| # | Item | Evidence |
|---|---|---|
| 1 | NSE legacy archive backfilled 1994-11-03 → 2019-09-29 into `legacy_ohlcv_daily` | 6,343,469 rows total (incl. overlap era); Phase 3 wrote 4,359,310 rows over 6,197 trading days |
| 2 | BSE legacy archive backfilled 2006-03-01 → 2024-01-01 into `bse_legacy_ohlcv_daily` | 5,779,288 rows over 4,400 trading days |
| 3 | SC_CODE→ISIN junction learned from UDiFF-era sessions | 6,386 junction rows; 2,111 map to canonical securities; 4,275 disclosed unmapped |
| 4 | Corporate-actions dedup verified for old-era duplicate batches | Regression test: duplicate (ex_date, type) in one call collapses to one row (last wins) |
| 5 | Full test suite green; ruff + mypy clean on new code | 573 passed |

## 2. Measured archive boundaries (live probes, not assumed)

| Source | Boundary | Evidence |
|---|---|---|
| NSE legacy archive | starts 1994-11-03 (inception); every earlier date 404 | 1994-11-03 file: 135 rows, schema matches parser |
| NSE ISIN column | appears 2011-06-23 | 2011-06-16 no ISIN → 2011-06-23 has ISIN+TOTALTRADES |
| NSE current provider | starts 2019-09-30 (`_CURRENT_PROVIDER_START`) | measured RP-012 D4 |
| BSE legacy EQ_CSV | 2006-03-01 → 2024-01-01 | 2006-03-01 first real file (ZIP); the backfill's last trading day was 2024-01-01 (EQ010124). Earlier probes had put the last legacy day at 2023-12-29; running the actual backfill over the full range showed 2024-01-01 also exists. |
| BSE UDiFF | starts 2024-01-02 | first date with real `TradDt` CSV; used for junction learning |
| NSE corporate-actions API | hard-capped at 20 rows/symbol | RELIANCE earliest 2011-05-05; TATAMOTORS n=0 |

## 3. NSE coverage

| Year | Distinct securities with bars | Error era note |
|---|---|---|
| 1994 | 104 | first session 1994-11-03 (53 bars resolved of 135 in file) |
| 2000 | 369 | dot-com peak; 2000-02-14 file: 311 bars resolved |
| 2008 | 839 | GFC; 2008-10-10: 798 bars |
| 2012 | 1,189 | post-ISIN era (2011-06-23+) |
| 2015 | 1,319 | |
| 2019 | 1,647 | overlap start 2019-09-30: 1,496 bars |
| 2024 | 2,147 | NSE-only count |

Phase 3 resolution (1994→2019): 1,863,991 ISIN-resolved, 2,495,319
symbol-fallback, 2,480,949 unresolved (14,003 distinct symbols). The unresolved
rows are archived prints of companies that delisted or renamed before the
modern securities table captured them; pre-2011 rows carry no ISIN, so symbol
fallback against current symbols is the only path, and a ticker rename (e.g.
TISCO→TATASTEEL) is not recoverable without a period-correct rename chain.
Confirmed by probe: TATASTEEL has no legacy bars before 2005. This is a
disclosed quality limit, not silent guessing.

Validation-gap logs: 7,100 C2 survivorship events (9,902 total in table incl.
overlap era) and 2,580 flagged C1 PREVCLOSE-inference rows written — flagged,
never applied to any price history.

## 4. BSE coverage

| Year | Distinct securities with bars |
|---|---|
| 2006 | 918 (first session 2006-03-01) |
| 2008 | 1,138 (2008-01-02: 1,080 bars; 2008 GFC window fully present) |
| 2012 | 1,284 |
| 2015 | 1,372 |
| 2019 | 1,578 |
| 2023 | 1,801 (2023-12-29) |

5,779,288 rows written, all ISIN-resolved through the junction. 7,177,275 rows
(6,404 distinct scrips) unresolved — BSE-only scrips and pre-2024
delistings never mapped into the junction. Junction holds 6,386 rows:
2,111 map to canonical securities; 4,275 do not (disclosed, never guessed).
BSE bars resolve strictly SC_CODE→junction→ISIN→securities; no name-based
cross-exchange fallback, per the cross-listing rule.

## 5. Corporate actions

- 25,864 rows persist across ex_dates 2011-01-06 → 2026-08-31.
- NSE's free API cannot serve the 2000-2010 era (20-row cap per symbol).
  Pre-~2011 adjustment factors therefore cannot come from the API.
- The C1 mechanism (PREVCLOSE-inference from the archive itself) logs flagged
  inferred factors for later reconciliation and never applies them.
- Dedup regression verified: duplicate (ex_date, type) rows in one batch
  collapse to one row, last wins, no Postgres multi-row-conflict error.

## 6. Known source gaps

| Date | Evidence |
|---|---|
| 2020-11-30 (NSE) | archive returns 404; both `ohlcv_daily` and `legacy_ohlcv_daily` have 0 bars that day. Genuine NSE publishing gap, not a backfill bug. |

## 7. Storage design

- NSE → `legacy_ohlcv_daily` (existing table, used by the NSE-anchored
  historical-screening surface).
- BSE → new `bse_legacy_ohlcv_daily` + `bse_scrip_junction` (migration
  `0010_bse_legacy_foundation`).
- Both are raw prints: adjustment fields absent (adj_close falls back to raw
  close), matching the existing legacy surface. Never written into live
  `ohlcv_daily`.

## 8. Runbooks

- NSE rerun: `scripts/rp012_phase3_backfill.py` (resumes by year-chunk
  checkpoint; per-day upserts idempotent).
- BSE rerun: `scripts/rp014_bse_legacy_backfill.py` (junction insert-only;
  per-day upserts idempotent).
- Both run with `M25_DATABASE_URL` set explicitly (backend has no .env).

## 9. Verification artifacts

- Per-era coverage, spot checks, junction stats: read-only script
  `verify_backfills.py` (temp tooling outside the repo).
- Sample identity spot checks: RELIANCE 2008 close 2861.75 (NSE) vs 2861.80
  (BSE) on 2008-01-02, volumes differ by venue as expected; RELIANCE 1995
  close 341.20 traded.