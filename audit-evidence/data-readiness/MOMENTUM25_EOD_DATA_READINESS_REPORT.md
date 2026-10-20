# Momentum25 EOD Data Readiness Report

**Audit date:** 2026-10-20  
**Result:** Stage 1 read-only audit complete; **refresh blocked**. No ingestion, database migration, derived-data update, or screening run was performed.

## Audited target and source

The repository’s effective `.env` selects `M25_ENVIRONMENT=development` and the non-test database `localhost:55432/momentum25` (PostgreSQL server address `172.18.0.3`, database size about 4.76 GB). Each audit connection ran with `transaction_read_only=on`. This is the configured local development market database, not an asserted production deployment. It contains no known `E2ECANDLE` or `SINGLE` E2E marker. The separate synthetic E2E database was not queried or changed.

The configured provider is `bhavcopy`; direct exchange downloads are **disabled** by the setting default. The scheduler flag is enabled for 18:30 IST weekdays, but it schedules screening; with direct downloads disabled it does not supply new exchange data. The API’s market refresh dependency rejects direct refresh while the flag is off. No network market-data request was made.

The repository’s NSE use review records that automated collection from NSE’s site is restricted and recommends waiting for permission/licensing or changing the provider. Current NSE materials likewise say automated website collection is prohibited and that EOD/historical data usage is governed by a subscriber agreement. BSE presents EOD and historical data through its data products and subscription flow. I found no authorization or data agreement in the configured environment. [NSE Terms of Use](https://www.nseindia.com/static/nse-terms-of-use), [NSE Data Sharing & Usage Policy](https://www.nseindia.com/static/market-data/nse-data-policy), [NSE EOD/Historical subscription](https://www.nseindia.com/static/market-data/eod-historical-data-subscription), [BSE Market Data](https://marketdata.bseindia.com/).

No authorized EOD, benchmark, corporate-action, or current instrument-master CSV export was present in the repository or configured import path; the only CSV files found were test fixtures. No Kite credentials are set in `.env`. The database rows do not have the post-migration per-row provenance fields, so the original authorization and source of every stored row cannot be proven from this database alone. The configured source and recovery script indicate NSE/BSE bhavcopy adapters, but that is not a substitute for evidence of authorization.

## Data inventory and quality

| Measure | Read-only finding |
|---|---|
| Latest stored EOD bar | **2026-08-07** |
| Latest completed session at audit | 2026-10-19; **49 expected sessions** absent after the stored latest date (2026-08-10 through 2026-10-19), using XBOM calendar `exchange_calendars 4.13.2` |
| Stored range and session coverage | 2019-10-01 through 2026-08-07; 1,690 stored market dates and 1,690 expected sessions within that range; no market-wide missing session in the stored range |
| EOD rows / securities represented | 3,076,892 bars across 3,220 symbols |
| Security master | 3,235 rows: 2,233 `BOTH`, 1,002 `NSE`; 459 lack ISIN; 22 duplicate-ISIN groups |
| Listing consistency | All 3,235 rows say active; 596 also have a delisting date, 3,229 have a last-trade date, 482 last-trade dates are over 250 calendar days before the latest bar, and 819 active rows lack a bar on 2026-08-07. Current listing status needs reconciliation against an authorized instrument master. |
| Raw bar checks | 0 duplicate `(security_id,date)` keys, 0 nonpositive OHLC prices, 0 invalid high/low bounds, 0 zero-volume bars and 0 negative-volume bars; 1,497 bars have missing or zero turnover |
| Adjusted price fields | 425,713 bars (13.8%) have no `adj_close`; 22,328 populated rows differ from `close × adj_factor` by more than 0.0101, with maximum absolute difference 0.590040987 and 2,808 differences above 0.10. This requires reconciliation before relying on the adjusted series. |
| Corporate actions | 25,864 rows, dated 2011-01-06 to 2026-08-31: 482 splits and 443 bonuses, all with ratios; 24,939 `other` rows have no ratio. That last group is documented as non-price-adjusting actions such as dividends/demergers, but source completeness after 2026-08-31 is unknown. |
| Benchmark | NIFTY500 has 2,858 rows, 2015-01-01 through 2026-08-07; it is also stale for the missing sessions. |

A spot check of the documented RELIANCE bonus dates (2019-10-01, 2024-10-25 and 2024-10-28) found adjusted close present and consistent with the stored factor. That confirms the sample case only; it does not resolve the 22,328 mismatches elsewhere.

## Derived data, runs, and schema freshness

There is no persisted indicator table in this database; the indicator pipeline derives values from stored bars. The run history has 136 rows (135 completed, one failed). The latest non-historical production run is **#146**, as of 2026-08-07, with 2,882 evaluated securities and 218 passed. The latest run ID, **#147**, is explicitly historical and dated Sunday 2026-08-09; it has no start/finish timestamps and is not evidence of a fresh EOD session. The database has one production strategy, six research strategies and no user strategy rows.

The database is at Alembic revision `0014_user_documents`; the checked-out application head is `0021_alert_drawing_snapshots`. Revisions 0015–0021 are not applied. In particular, this database lacks the history/provenance tables, data manifests, user-strategy families/evaluations, and the current alert drawing/revision schema. New Strategy Studio integration was verified in an isolated E2E database, but is not present in this configured database. Running the current screening/research workflow here would not provide the current manifest and persistence contracts.

## Refresh pipeline and rollback readiness

- The one-session refresh service chooses the latest completed calendar session and uses `(security_id,date)` upserts. Repeating the same source payload is idempotent. It writes each exchange separately and does not stage and validate the full market before promotion; it does not itself refresh corporate actions/benchmark data or create a screening run.
- The ordinary screening path fetches only after the latest stored date when external ingestion is enabled. With the current flag off, it can only use persisted bars. Forced download is also guarded by the same opt-in.
- The local CSV importer parses and validates bars/actions before persistence and commits bars plus those actions as a transaction; the benchmark import is a separate operation. No authorized files were available to test a staged import.
- The database has partial same-database snapshots dated 2026-08-10 and legacy research tables, but they are not a complete rollback snapshot. `pg_dump`/`pg_restore` are not available in PATH and the Docker daemon could not be reached, so a verifiable full backup/restore path was not established. The historical recovery script is not appropriate for this incremental refresh: it re-fetches broad history through exchange adapters and includes a destructive synthetic-`SINGLE` cleanup.

## Controlled refresh decision

**No refresh was safe to perform from the available inputs.** The direct provider is disabled, no authorized local export or licensed Kite configuration is present, no whole-database backup path is available, the target schema is seven revisions behind, and the existing adjustment/listing anomalies are unresolved. I did not use an unapproved online data source.

| Requested action | Result |
|---|---|
| Imported EOD sessions | 0 |
| Recalculated indicators/adjustments | 0 |
| Newly created screening or research runs | 0 |
| Mutations to production/non-test data | 0 |
| Changes to E2E fixtures/goldens, replay, drawings, or alerts | 0 |

## Verification and next action

Read-only SQL inventory and integrity checks were run against the configured target with the database transaction explicitly set read-only. The bounded unit suite `tests/unit/test_import_market_data.py` and `tests/unit/test_refresh_latest_market_data.py` passed: **14 passed**. No ingestion E2E was attempted because there was no authorized source, no refresh, and the target schema is behind.

To proceed, provide or configure an **authorized** normalized export covering the missing EOD sessions (including turnover), the matching NIFTY500 closes, the current instrument master with ISIN/listing status, and complete price-affecting corporate-action history for affected symbols. Confirm whether `localhost:55432/momentum25` is the intended database (it is currently labeled `development`). Establish a working full backup/restore procedure, then plan and verify migrations 0015–0021 and reconcile the adjusted-price/listing discrepancies before any import. Only then should an isolated staged import, invariant checks, derived-data update, and new production/user-config runs be performed. No financial methodology change is indicated or proposed.
