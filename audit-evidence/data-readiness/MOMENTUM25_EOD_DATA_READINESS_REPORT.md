# Momentum25 EOD Data Readiness and Refresh Report

- **Execution date:** 2026-10-20
- **Result:** **Refresh complete; focused end-to-end verification passed.**
- **Target:** the configured local development database `momentum25` (not a production deployment).
- **Refresh authorization:** owner authorized a one-time refresh from the same NSE/BSE sources on 2026-10-20.
- **Implementation revision:** `5961b9c2f74bc41bf3ba5c33101fefc1eda3a6a3`.

## Readiness and before/after state

The initial inventory was performed read-only. It found a latest bar on 2026-08-07, with 49 NSE sessions missing through 2026-10-19. Before import the database had 3,076,892 daily bars across 3,235 security records, 25,864 corporate actions, 2,858 NIFTY500 observations, and Alembic revision `0014_user_documents`. The scheduled screening flag was enabled, but direct exchange downloads were disabled.

Before any migration or data write, a 512 MB custom-format PostgreSQL dump was created, checksummed, listed with `pg_restore`, and restored into an isolated staging database. The staging restore was upgraded and used to validate the import and screening workflow before applying the same migration and transaction to the configured database.

| Measure | Before | After |
|---|---:|---:|
| Latest EOD date | 2026-08-07 | **2026-10-19** |
| Newly covered sessions | — | **49** (2026-08-10 through 2026-10-19) |
| Daily bars | 3,076,892 | **3,206,035** (+129,143) |
| Security records | 3,235 | **3,463** (+228); 3,462 active |
| Symbols trading on latest date | — | **2,698** |
| Corporate actions | 25,864 | **26,562** (+698) |
| NIFTY500 daily observations | 2,858 | **2,907** (+49) |
| Schema | `0014_user_documents` | **`0021_alert_drawing_snapshots`** |

The NSE calendar classifies 2026-10-20 as a holiday. The API freshness endpoint reports `FRESH`, zero missed sessions, and 2026-10-21 as the next session.

## Source, validation, and import

The refresh used the configured NSE/BSE bhavcopy source family: dated NSE UDiFF daily files, the matching BSE files for cross-listing checks, the NSE and BSE instrument masters, source corporate-action records, and NIFTY500 daily closes. No alternate online data source was substituted. Raw inputs stayed in `/private/tmp` and were not committed. Direct exchange downloads remain disabled in the application; this was a one-time, explicitly authorized refresh, not activation of recurring downloads.

The owner's instruction authorized this operational refresh from the same source, but does not itself establish exchange subscription rights. NSE currently presents EOD/historical data through a subscription process; its data-use policy says the applicable subscriber agreement governs permitted handling and redistribution. BSE likewise offers its market data through subscription products. No source agreement was found in the repository, so these extracts remain local and are not redistributed; recurring downloads stay disabled. See [NSE EOD/historical subscription](https://www.nseindia.com/static/market-data/eod-historical-data-subscription), [NSE data-sharing policy](https://www.nseindia.com/static/market-data/nse-data-policy), and [BSE market data](https://marketdata.bseindia.com/).

All 49 source sessions and the supporting files were staged and validated before promotion. The staged payload contained 129,143 bars for 2,858 symbols. Validation found no duplicate security/date keys, non-positive prices, invalid OHLC bounds, zero or negative volume, or missing previous-close/turnover fields in the new window. The promoted window has **zero** populated `adj_close` values differing from `close × adj_factor` by more than 0.0101, and zero rows where `adj_close` is missing while the factor is non-unit.

Cross-listing reconciliation used NSE as the canonical equity screen universe: 2,619 NSE master symbols, 2,430 also present in BSE, 189 NSE-only, and 2,688 BSE-only symbols withheld from NSE screening. The import added 228 security records, including symbols present in the authorized EOD source but absent from the earlier master. It did not mass-deactivate stale securities.

Four listing conflicts were handled conservatively. For JYOTIRES, UDAYJEW, and VTMLTD, source bars and BSE trading evidence predated unsupported future listing dates in the current NSE master; the unsupported dates were cleared rather than asserting a false listing date. LANCER had a pre-existing delisting interval ending in 2023 despite BSE-confirmed 2026 trading under the same ISIN. Its existing interval was retained because the schema cannot represent a second listing interval. One 2026-08-17 LANCER previous close was corrected from the stale NSE value to the BSE-confirmed 10.98. These decisions and the remaining LANCER limitation are intentional and auditable.

The source action file supplied 808 events (786 unique upsert identities); 698 new action rows were added, including 13 price-ratio events across 13 symbols in the refreshed interval. The established adjustment method was rerun for those 13 affected histories: **11,037 bars**. No investment rule or financial methodology changed. No persisted indicator table exists; indicators derive on demand from the updated bars. The NIFTY500 benchmark advanced by exactly 49 sessions.

Replaying the exact import against the isolated staging database left session, bar, action, benchmark, and security counts unchanged. This verifies the refresh upsert keys are repeatable for this payload. Promotion to the configured database completed after staging checks.

## Strategy, charts, and historical verification

Migration through `0021_alert_drawing_snapshots` succeeded. The configured production screening strategy definition was unchanged. Final run **#149** completed for 2026-10-19 using data version `8790a000bd4f` and the unchanged Minervini config hash `1fe19b434a6befb772274368447802abfb1eeb0e1df5e762d8c59a3d708b08d3`:

- 3,096 universe records: 1,338 eligible for scoring and 1,758 excluded by eligibility/history/staleness gates.
- 1,338 scored results, 155 qualified and ranked, and 32,112 stored rule-evidence rows.
- Top ranks returned as SBC, UNITEDPOLY, SKYGOLD, OAL, and NITINSPIN.
- Watchlist detail references run #149 and the same configuration hash; TCS is in the run with score 54.6862 and no qualification rank.

Run #148, produced before the narrow listing-date correction, remains an immutable completed record. The final run #149 is the latest run; neither prior runs #146/#147 nor their configuration hashes were overwritten. The application stores manifest `8790a000bd4f` for the final run.

A distinct user-configured strategy was also exercised against the fully refreshed isolated staging copy: `refresh_smoke_rs90` (RS threshold 90) produced 61 qualifications versus 155 for Minervini on the same bars. That test definition and its run remained in the staging copy; no test strategy was added to the configured database, which has no user-authored strategy definition.

Read-only application checks confirmed:

- API health, database, and Redis are `ok`; market data is fresh through 2026-10-19.
- RELIANCE daily, weekly, and monthly chart endpoints all end on 2026-10-19 at close 1202.0000.
- The browser opened `/chart/RELIANCE`, rendered the price chart, and received the 2026-10-19 daily bar. The browser check blocked and recorded an attempted chart-workspace `PUT`; it did not reach the database.
- Replay requested as of 2026-08-07 ends on 2026-08-07 and returns no future bars.
- The only saved document remains `workspace/default` revision 10; the alert table remains empty. No drawing document existed to migrate or modify, so no alert evaluation was applicable.

The browser check used GET-only API access and aborted non-GET API calls. The API and SQL verifications above were read-only. No E2E database, synthetic fixture, golden result, or research result was changed.

## Defect corrected and verification

The dated NSE UDiFF adapter had been looking up the current file through an obsolete filename path. It now uses NSE's dated archive for sessions from 2024-01-02 onward and parses STK/EQ rows with their trade date, previous close, turnover, and ISIN. On 2026-10-19, its output matched the previous supported source for all 2,698 rows and all OHLCV fields.

The adjustment-factor writer also bound repeating ratios at an unintended four-decimal precision for adjusted close while storing factors at eight decimals. The repository now binds the declared numeric precision explicitly. Focused regression coverage checks persisted factors and recomputed adjusted close, including the 1:3 bonus-history case (Aug 10 adjusted close 493.2000; Aug 21 raw/post-action close 490.9000).

Validation results:

- NSE UDiFF/provider and market-data integration tests: **13 passed**.
- Adjustment-factor persistence regression: **passed**.
- Alert, workspace, point-in-time replay, adjusted chart, corporate-action, and legacy adjustment regressions in the isolated provider test database: **117 passed**.
- Ruff for changed backend files and `git diff --check`: **passed**.
- API container build/restart and web TypeScript/Vite production build: **passed**. The frontend build retains the existing large-entry-chunk warning.
- Focused final read-only SQL/API and browser checks: **passed**; no browser JavaScript errors and no writes were allowed.

## Limits and recovery evidence

The original audit found 22,328 populated adjusted closes outside a small spot-check set differing from `close × adj_factor` by more than 0.0101, 425,713 historical missing `adj_close` values, and stale listing metadata. This refresh reconciled the new window and recomputed action-affected histories, but did not globally rewrite unrelated historical prices or listing intervals. Those historical quality findings remain outside this focused refresh. LANCER’s re-listing interval cannot be represented in the current schema. Inactive/stale status was not broadly reconciled, and only the configured Minervini definition was run against the shared database.

The API still reports direct exchange downloads disabled. Recurring source entitlement and any subscription requirements remain governed by the existing provider configuration and applicable NSE/BSE terms; the raw source extracts are local evidence, not redistributable product artifacts.

Pre-refresh full database backup: `/private/tmp/wickstreet-momentum25-before-eod-20261020.dump` (512 MB; SHA-256 `1b944cbfa01bf4cb536d0cc0e6b730cd7dadfbea366108ff04e812c5694b45d2`). It was validated with `pg_restore --list` and restored successfully into the isolated staging database before main-database writes. Keep this file if rollback capability is required.

Input hashes (SHA-256):

| Input | SHA-256 |
|---|---|
| NSE EOD rows, 2026-08-10–2026-10-19 (`.jsonl`) | `3ae99db2a5431086fe164b34cc452d75042b390e31e7eeefcd9b725b24fecd44` |
| Corporate actions, 2026-08-07–2026-10-19 | `6c869fcad5f5aeefabe54d36c0525917d317d58c34e2315c39b90eb1eb2e2b5e` |
| NSE master snapshot | `b6a588b394d1453501ea40d293e1078ea9aa7e3f818bd2b6d7c19d1c1af2e620` |
| BSE master snapshot | `5952439b87287db0f4371c8662ff284744cfd166c263ab0c1440b94c34c64747` |
| NIFTY500 closes, 2026-08-10–2026-10-19 | `2e56fb2fc17c84c6e9e816def9ad7d65ceb76c75cbb7f7d9710c70c6bed68bc0` |

Local implementation commit: `5961b9c2f74bc41bf3ba5c33101fefc1eda3a6a3`. This report is delivered in a separate local documentation commit; no commit was pushed. Phase C was not started.
