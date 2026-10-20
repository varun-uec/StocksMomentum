# Prioritised Remediation Register — Round 3

Date: 2026-10-20. IDs: `R3-U-nn` found by the main session (UI, integration, performance), `R3-B-nn` by the backend and data audit, `R3-O-nn` operational. Severity: **P0** critical correctness, security or data integrity; **P1** significant functional, reliability or integration; **P2** usability, maintainability, non-critical correctness; **P3** polish and documentation.

"Fixed" means a regression test exists, it failed before the fix, and the suites pass. **None of the fixes is deployed.** The running container still has the old image (Release Gate G6). Commit hashes are on the local branch `wickstreet/m10-m11`. Nothing was pushed.

**Totals: P0 0 · P1 3 (2 fixed, 1 open blocker) · P2 21 (11 fixed, 10 open) · P3 17 (3 fixed, 14 open).**

## P1

| ID | Component | Finding | Status | Evidence | Verification when closed |
|---|---|---|---|---|---|
| R3-B-02 | EOD import (`import-eod`) | One holiday, weekend or future-dated row became the latest date. The next screen made run 162 COMPLETED with 1 scored and 1,853 dropped, and `/runs/latest` served it. Expected: the row is rejected. Root cause: no date check against the exchange calendar and the clock. **Risk: the live screener shows an empty list after one bad row.** | **Fixed** `9a32526` (4 test cases); not deployed | worker `eod/` | The four cases fail without the fix. Rebuild the image. |
| R3-B-08 | `/stocks/{s}/live`, watchlist RS | Ranked RS across ETFs and funds, unlike every run path. 2,679 equities got another rating; 101 crossed RS ≥ 70 (RELIANCE 30 against 34). Root cause: `list_active()` unfiltered. | **Fixed** `51f3239`; **owner to confirm** (it moves displayed numbers; run output unchanged, hashes byte-identical). Revert the commit to undo. | `rs_live_vs_run*.out` | Live RS equals the stored run RS for all 1,338 scored names |
| **R3-B-09** | Walk-forward backtest | **27% of notional (176 of 649 trades) filled and marked at the last earlier bar** when a name had no bar on the fill date. Code docstring says skip. Example: 3PLAND bought 2025-01-01 at 81.50, last bar 2024-12-18. Expected by the docstring: skip. **Risk: backtest results are biased toward illiquid names and cannot support any claim.** | **OPEN. Methodology: audit stopped.** Owner picks the policy (skip, next-available bar, carry cash). | `walkforward/stale_fills.txt`, `trades.csv` | Zero fills on dates without a bar; backtest re-baselined; quoted figures refreshed |

**Release blocker:** R3-B-09, for any backtest claim. The live screener is not affected.

## P2

| ID | Component | Finding | Status |
|---|---|---|---|
| R3-B-10 | Screening vs spec §8 | Four differences: RS ranked over all equities (1,253 of 1,338 ratings change, 39 cross 70); `rel_volume` 49-session prior mean; EMA first-value seed; rank tie-break by `security_id`. | **OPEN. Methodology: audit stopped.** Owner: amend spec or change code, per item. |
| R3-B-01 | Backend tests | 6 period-bar unit tests failed at HEAD (fake still had `get_active`). Docs claimed green. | Fixed `4d485aa` |
| R3-B-03 | Run API and CLI | Returned the newest completed run by date, not the run just written. | Fixed `f3e9110` |
| R3-B-04 | Screening | Two identical concurrent screens gave HTTP 500, not 409. | Fixed `45bbd83` |
| R3-B-05 | Scheduler | Scheduled runs stored as `MANUAL`. | Fixed `dab5b56`, not deployed |
| R3-B-06 | Logging | Database and Redis URLs with passwords logged at every start. | Fixed `e3b67dd`, not deployed |
| R3-B-11 | Scheduler | No catch-up after downtime (`MemoryJobStore`); docs claim recovery. | OPEN. Owner: engineering. Persistent job store or catch-up on start; fix docs. |
| R3-O-02 | Compose | Container restart policy `no`; the in-process scheduler stays down after any crash, OOM or reboot. | OPEN. Owner: engineering. `restart: unless-stopped`. |
| R3-B-12 / R3-U-09 | Manifest | `git rev-parse HEAD` per capture: `null` in the container (tonight's job writes a duplicate snapshot of 2026-10-19), and a new `data_version` per commit on a host. One fix: a code version that does not move per commit. | OPEN. **Owner decision** (ADR-014 §7). |
| R3-B-13 | `/live` | `data_as_of` = today and `data_sufficient` = true for stale stocks; the web reads it. | OPEN. Owner: contract decision. |
| R3-B-14 | RS cache | Keyed by name and date, 6 h TTL; same-day corrections ignored on the read path. | OPEN. Owner: engineering. |
| R3-B-15 | Schema | Migrations, ORM and dev database disagree (`alembic check` ~45 ops; nullable FKs on fresh install; missing `(run_id, rank)` index). Tests use `create_all`. | OPEN. Owner: engineering. Reconcile, add a CI `alembic check`. |
| R3-B-16 | Architecture | 17 application → infrastructure imports in 11 files; contract omits the layer. | OPEN. Owner: engineering. Add the contract, move the imports behind ports. |
| R3-U-04 | Web | Text contrast below 4.5:1 in both themes (84 nodes on the home screen). | **Fixed** `db6cfc3`, verified |
| R3-U-03 | Web | No `main` landmark on 14 of 25 routes. | **Fixed** `db6cfc3`, verified |
| R3-U-02 | Web | Unlabelled `select` and date input (axe critical). | **Fixed** `db6cfc3`, verified |
| R3-U-10 | Web | A stored strategy the workspace no longer offers left the Assessment on "loading run…" with 404s. Root cause: only the Screener page reconciled the stored choice. | **Fixed** `db6cfc3`; journey 4 |
| R3-U-07 | Web `/validation` | One hard-coded strategy; saved strategies cannot be validated. | OPEN. Owner: web. |
| R3-U-01 | Web bundle | Main chunk 1,009.9 kB raw / 315.6 kB gzip (R2: 565.8 / 182.1). | OPEN. Owner: web. Route-level splitting of the chart libraries. |
| R3-B-21 | Docs | Stale counts and claims (migrations, tables, tests, ADR index, readiness, ADR-003/007/009/012/014 text). | OPEN. Owner: engineering. |
| R3-O-03 | Test suite | The committed browser suite was red at HEAD: 4 specs still expected the pre-`cecb3e5` UI and one test asserted removed behaviour. | **Fixed** `2f311af` |
| R3-R2-09 | Research harness | `apply_parameter_overrides` is never called (inherited R1-P2-09). | OPEN. Owner: engineering. Not re-tested. |
| R3-R2-10 | Strategy catalogue | `rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend` still registered; v3 text names a detector that does not exist (inherited). | OPEN. Owner: engineering. |
| R3-R2-12 | Tooling | Eleven development-only npm advisories (inherited). Dependency audits not run this round. | OPEN. Owner: owner approval for `npm audit` and `pip-audit`. |

## P3

| ID | Finding | Status |
|---|---|---|
| R3-U-05 | 25 screener buttons "Checklist for X" with visible text "8/8" (label in name). | **Fixed** `db6cfc3` |
| R3-B-07 | `list_active` had no ORDER BY; equal-return RS ratings depended on heap order. | **Fixed** `f9a7ad4` |
| R3-B-25 | Audit tmpfs Postgres exhausted the Docker VM and the owner's API was OOM-killed at 10:59 UTC. | Closed (mitigated); API restarted, dev database untouched. Related: the API container has no memory limit. |
| R3-U-06 | Expected-empty GETs (`/screens/default`, `/drawings/{symbol}`) answer 404, logging a console error on every first load. Whitelisted in the E2E fixture. | OPEN. Owner: web and API. Prefer 200 with `null`. |
| R3-U-08 | 200 requests per minute per client; a page load costs 7 to 15; about 13 fast loads give 429, shown as partial data. E2E raises the cap to 100,000. | OPEN. Owner: engineering. Raise the cap for loopback or show a notice. |
| R3-U-11 | "Δ Rank" shows a green ↓ for an improvement (rank 144 → 1 reads ↓ 143). | OPEN. Owner decision (convention). |
| R3-U-12 | `scrollable-region-focusable` on `/strategies`, `/data` at 390 px and on Elliott Wave. | OPEN. Owner: web. |
| R3-U-13 | Phone chart cuts the data-source line. | OPEN. Owner: web. |
| R3-U-14 | Docs say 12 drawing tools; source has 21. | OPEN. Owner: engineering. |
| R3-B-17 | Historical `data_version` uses a wall-clock suffix. | OPEN |
| R3-B-18 | 22,328 `adj_close` rows differ from `close × adj_factor` (max 0.25%); 925 in the current RS window. | OPEN. **Owner**: needs a real-data write. |
| R3-B-19 | `/runs/<huge int>` gives 500. | OPEN |
| R3-B-20 | CLI prints raw tracebacks on database errors; APScheduler lines are not JSON. | OPEN |
| R3-B-22 | ADR-056 does not exist. | OPEN. **Owner**: name the intended document. |
| R3-B-23 | Unclosed httpx client; 20 unclosed test connections; no body-size cap. | OPEN |
| R3-B-24 | Ad hoc research tables and views in the application database. | OPEN |
| R3-O-04 | `/strategies` hard load lost its `h1` once in the 234-case run; did not reproduce on four reruns. | NOT VERIFIED (root cause). Re-check in the final run. |

## Decisions needed from the owner

1. **R3-B-09** — backtest fill policy for names with no bar on the fill date.
2. **R3-B-10** — for each of four spec differences, amend the spec or change the code.
3. **R3-B-08** — confirm (or revert `51f3239`) the read-path RS universe.
4. **R3-B-12 / R3-U-09** — what code version the manifest records.
5. **R3-B-13** — the `/live` `data_as_of` contract.
6. **R3-B-18** — authorise repair of the `adj_close` rows in the development database.
7. Approve `pip-audit` and `npm audit` (they send the dependency list off-machine).
8. Accept ADR-012 and ADR-015; add LICENSE and NOTICE; clear the name; legal review of NSE and BSE terms.
9. **R3-B-22** — which document "ADR-056" means.
10. Rebuild and redeploy the image, and set `restart: unless-stopped`.
