# Prioritised Remediation Register — Round 3

Date: 2026-10-20. IDs: `R3-U-nn` found by the main session (UI, integration, performance), `R3-B-nn` by the backend and data audit, `R3-O-nn` operational. Severity: **P0** critical correctness, security or data integrity; **P1** significant functional, reliability or integration; **P2** usability, maintainability, non-critical correctness; **P3** polish and documentation.

"Fixed" means a regression test exists, it failed before the fix, and the suites pass. **None of the fixes is deployed.** The running container still has the old image (Release Gate G6). Commit hashes are on the local branch `wickstreet/m10-m11`. Nothing was pushed.

**Totals (recounted 2026-10-21): P0 0 · P1 7 (6 fixed; 1 open: R3-B-31, mechanism in source, no verified link data) · P2 27 (25 fixed or closed, of which R3-B-21 is fixed in part; 2 open: R3-R2-09 mitigated, R3-R2-12) · P3 18 (10 fixed, 8 open or awaiting an owner: R3-U-13, R3-B-17, R3-B-18, R3-B-22, R3-B-23, R3-B-24, R3-O-04, R3-B-29). 41 fixed or closed in all. Every fix is in source and none is deployed.**

**2026-10-20 decision review.** R3-B-09 and R3-B-10 are investigated, not resolved. The evidence and the recommended defaults are in [R3-B-09_R3-B-10_DECISION_PACKET.md](R3-B-09_R3-B-10_DECISION_PACKET.md). The review also found R3-B-27, R3-B-28 and R3-B-29. No code, spec or stored result was changed.

**2026-10-20 Stage A (owner direction).** The proposed methodology is in [STAGE_A_FINANCIAL_METHODOLOGY_SPEC.md](STAGE_A_FINANCIAL_METHODOLOGY_SPEC.md): the 15-question matrix mapped to the direction, 13 new owner questions (S-1 to S-13), the execution and ledger contract, the reference universe and RS rules, identity schema 3, sensitivity results, the test plan and the Stage B plan. It found R3-B-30, R3-B-31 and R3-B-32.

**2026-10-20 Stage B (conditional owner authorisation, bounded).** These are implemented in source with local commits `f6ce742` to `8e096b2`:

- engine v2: the reference universe, calendar-aligned RS, the tie-break and indicators v3;
- backtest method v2: causal fills and the fill-driven ledger;
- identity schema 3;
- verified identity links;
- session-bounded forward returns;
- methodology provenance.

Owner answers taken: S-2 same-session settlement, S-3 10% cap, S-4 5-session anchor, and R3-B-32 last bar on or before the exit with staleness stored. Every rule has an independent reference or golden test. Final regression on 2026-10-21:

| Suite | Result |
|---|---|
| Backend `pytest` (isolated test DB) | 1,036 passed |
| `ruff`, `mypy`, `lint-imports` | Clean; 2 of 2 contracts kept |
| Web Vitest | 148 passed |
| `tsc`, ESLint | Clean |
| Playwright, full suite on the isolated `momentum25_e2e` DB | 229 passed, 0 failed, 8 opt-in skipped |

Still open, and visible:

- R3-B-31 has no verified link data (S-5).
- No session-basis forward-return backfill has run.
- No real database was changed. The hold-out was not read. Nothing was pushed or deployed.

Recalculated backtest returns are simulations, not validated investment performance. **Release readiness is not claimed.**

**2026-10-21 Round 4 (engineering).** Commits `7c1fcf5` and `7c008d9`. Fixed or closed: R3-B-13, R3-B-14, R3-B-16, R3-B-19, R3-R2-10; mitigated: R3-R2-09; fixed in part: R3-B-20; investigated: R3-B-18; no reference to fix: R3-B-22. R3-B-09 was re-verified (36 walk-forward and reference tests pass) and stays Fixed in source. Usability: backtest results name symbols and list every fill (new Trades table, `BacktestResponse.symbols`); a backtest with no fills now says why. Suites: see `docs/current/state.md`.

## P1

| ID | Component | Finding | Status | Evidence | Verification when closed |
|---|---|---|---|---|---|
| R3-B-02 | EOD import (`import-eod`) | One holiday, weekend or future-dated row became the latest date. The next screen made run 162 COMPLETED with 1 scored and 1,853 dropped, and `/runs/latest` served it. Expected: the row is rejected. Root cause: no date check against the exchange calendar and the clock. **Risk: the live screener shows an empty list after one bad row.** | **Fixed** `9a32526` (4 test cases); not deployed | worker `eod/` | The four cases fail without the fix. Rebuild the image. |
| R3-B-08 | `/stocks/{s}/live`, watchlist RS | Ranked RS across ETFs and funds, unlike every run path. 2,679 equities got another rating; 101 crossed RS ≥ 70 (RELIANCE 30 against 34). Root cause: `list_active()` unfiltered. | **Fixed** `51f3239`; **owner to confirm** (it moves displayed numbers; run output unchanged, hashes byte-identical). Revert the commit to undo. | `rs_live_vs_run*.out` | Live RS equals the stored run RS for all 1,338 scored names |
| **R3-B-09** | Walk-forward backtest | **27% of notional (176 of 649 trades) filled and marked at the last earlier bar** when a name had no bar on the fill date. Code docstring says skip. Example: 3PLAND bought 2025-01-01 at 81.50, last bar 2024-12-18. Expected by the docstring: skip. **Risk: backtest results are biased toward illiquid names and cannot support any claim.** | **Fixed in source** `371af70` (backtest method v2, brief-addendum-execution-v2.md): a fill needs a valid bar dated on its session (buys within 5 sessions, sells until filled), fills are capped at 10% of traded value, the ledger changes only through fills, and the trade-log replay must equal it. An independent reference agrees fill for fill (`tests/reference/`). On real data: 0 stale fills in 2,823. Not deployed. Recalculated returns are simulations, not validated performance. | `walkforward/stale_fills.txt`, `trades.csv`, `backend/decision-packet/` | Packet §8.1 (11 criteria) |
| **R3-B-27** | Walk-forward backtest universe | **New (decision review).** The universe provider loads `exchange == 'NSE'` only, so all 2,431 dual-listed names (`exchange = 'BOTH'`: RELIANCE, TCS, INFY, HDFCBANK) are excluded. Expected by brief §1: Nifty 500 constituents. **Risk: the backtest runs on 1,018 mostly small names; this drives most of R3-B-09.** | **Fixed in source** `371af70`, `79a4e99`: one reference equity universe (NSE and `BOTH`, `domain/universe.py`) for the backtest, screener, RS and research. Not deployed. | `backend/decision-packet/` | RELIANCE present in the universe; re-baselined result |
| **R3-B-28** | Walk-forward backtest universe | **New (decision review).** No equity filter: 353 of 1,018 names are ETFs or fund units; EBBETF0425 was held. Expected by brief §1: equities. | **Fixed in source** `371af70`, `79a4e99`: fund and ETF units (`INF…`) are out of the reference universe. Not deployed. | `backend/decision-packet/` | No non-equity ISIN in the universe |

| **R3-B-30** | Walk-forward backtest prices | **New (Stage A).** The price provider drops every bar with `adj_close` NULL: 553,534 bars (17%; 42% of 2026). All have `adj_factor = 1`, so `close × adj_factor` prices them exactly. Names that traded look absent. With the corrected universe over 2021–2026, the result moves from +334% to +281%. | **Fixed in source** `371af70`, `79a4e99`, `3a30583`, `230e0e6`: every price is `close × adj_factor`. The stored `adj_close` is not an input. Reconciled read-only (`stage-b/adjustment_reconciliation.txt`): stored factors match the actions on all 3,206,035 bars, with 0 factor steps without an action and 0 actions without a step. 55,271 bars (98 names) store an `adj_close` from a 4-dp factor (median gap 0.01%, max 0.28%). No engine reads it. The repair stays with R3-B-18. Not deployed. | `backend/decision-packet/stage-a/` | No bar with a valid `close` and `adj_factor` is dropped |
| **R3-B-31** | Security master identity | **New (Stage A).** Renames are split across unlinked rows (TWL → TITAGARH on 2023-06-19; MAGMA → POONAWALLA; MEGASOFT and SIGMAADV share one ISIN). The backtest froze MAGMA at its 2021 price for 1,269 sessions. The screener and RS treat successors as new listings. A heuristic finds up to 334 candidate pairs (not verified). **Risk: wrong holdings in backtests; successors excluded from screening for about a year.** | **Mechanism in source** `688631c`: the versioned `security_identity_links` table (migration 0022), the import CLI with SHA-256 evidence, backtest carry-over and history stitching. **OPEN for data:** the table is empty, because no authoritative rename evidence exists on disk and downloads are prohibited. Every renamed holding (MAGMA, TWL and the 334 heuristic candidates) stays flagged "no verified identity link". **Owner action S-5:** supply an evidence file. | `stage-a/stuckA.json` | TWL → TITAGARH carries a position 1:1; successor RS uses predecessor history |

**Release blocker:** R3-B-09, for any backtest claim. The live screener is not affected. After the fix, G3 can pass for fill correctness only; the backtest still makes no performance claim (stub membership and surveillance, loop-3 Item 13).

## P2

| ID | Component | Finding | Status |
|---|---|---|---|
| R3-B-10 | Screening vs spec §8 | Four differences: RS ranked over all equities (1,253 of 1,338 ratings change, 39 cross 70); `rel_volume` 49-session prior mean; EMA first-value seed; rank tie-break by `security_id`. | **Fixed in source** `79a4e99` (engine v2; ENGINE_VERSION 2, INDICATOR_VERSION 3). RS is calendar-aligned on NSE sessions, with the anchor at most 5 sessions early (S-4). It needs 253 bars and ranks the reference population. `rel_volume` uses the same 50 bars as `avg_volume50`. EMA and MACD are SMA-seeded and match the browser golden fixture to 1e-9. Ties break by symbol, ISIN, then security_id (S-7). Runs before and after are not comparable, and score history marks the break (`ed220b6`). Not deployed. |
| R3-B-32 | Research forward returns | **New (Stage A).** Forward returns count the security's own next *h* bars, so a name with trading gaps gets a longer calendar horizon. In-Sample Top-25 names with gaps: 65.7% stored against 50.3% on exchange sessions (120 sessions). | **Fixed in source** `3a30583`. Horizons count NSE sessions. The exit is the last bar on or before the h-th session, stored with `exit_stale_sessions`. `horizon_basis` is in the key (migration 0023), so old `own_bars` rows are kept and never mixed with new ones. **No session-basis backfill has run** on any real database. The validation surfaces show no matured rows until the owner approves one. Not deployed. |
| R3-B-01 | Backend tests | 6 period-bar unit tests failed at HEAD (fake still had `get_active`). Docs claimed green. | Fixed `4d485aa` |
| R3-B-03 | Run API and CLI | Returned the newest completed run by date, not the run just written. | Fixed `f3e9110` |
| R3-B-04 | Screening | Two identical concurrent screens gave HTTP 500, not 409. | Fixed `45bbd83` |
| R3-B-05 | Scheduler | Scheduled runs stored as `MANUAL`. | Fixed `dab5b56`, not deployed |
| R3-B-06 | Logging | Database and Redis URLs with passwords logged at every start. | Fixed `e3b67dd`, not deployed |
| R3-B-11 | Scheduler | No catch-up after downtime (`MemoryJobStore`); docs claim recovery. | **Fixed in source** `e9ba4ba`: catch-up on start (trading-day aware, fake-clock tests). **Not deployed.** |
| R3-O-02 | Compose | Container restart policy `no`; the in-process scheduler stays down after any crash, OOM or reboot. | **Fixed in source** `8253e97`: `restart: unless-stopped`, memory and CPU caps for db, api, redis. Applies on the next `make up`. **Not deployed.** |
| R3-B-12 / R3-U-09 | Manifest | `git rev-parse HEAD` per capture: `null` in the container (tonight's job writes a duplicate snapshot of 2026-10-19), and a new `data_version` per commit on a host. One fix: a code version that does not move per commit. | **Fixed in source** `8e5922d`, ADR-014 §10: `data_version` hashes market data and engine versions only; build id stored, not hashed; legacy keys preserved. Observed live before the fix: run 150 (13:00 UTC) = same results as run 149, new `data_version`, null commit. **Owner:** add an `ENGINE_VERSION` constant (Q4). Not deployed. |
| R3-B-13 | `/live` | `data_as_of` = today and `data_sufficient` = true for stale stocks; the web reads it. | **Fixed in source** `7c1fcf5`. Contract: `data_as_of` is the stock's own last bar on or before the request date. `data_sufficient` is false when that bar is older than the latest exchange session, or when history is too short. The verdict is still computed and the web says the figures are partial. Test `test_stale_stock_reports_its_last_bar_and_is_not_sufficient`. Owner may veto the contract (Decisions, item 5). Not deployed. |
| R3-B-14 | RS cache | Keyed by name and date, 6 h TTL; same-day corrections ignored on the read path. | **Fixed in source** `7c1fcf5`. The key now carries the committed data revision (`OHLCVRepository.data_revision()`), so a correction moves it and the next read recomputes. Old keys expire by TTL. Tests `test_a_same_day_correction_is_not_served_from_the_cache`, `test_a_same_day_correction_changes_the_basis`. Not deployed. |
| R3-B-15 | Schema | Migrations, ORM and dev database disagreed (`alembic check`: 45 operations on a migrated empty database). | **Fixed in source** (2026-10-21, migration `0024_schema_drift_reconcile`, no applied migration edited). History tables now copy the NOT NULL of their current table (as `LIKE` built them). The model carries the index `(run_id, rank)` and the `securities.symbol` constraint that migration 0001 made. Migration 0024 sets NOT NULL on 11 columns (dev held 0 NULLs, read-only count) and, idempotently, brings the dev database's `create_all` indexes to the migrated shape. The trigram indexes (raw SQL, need `pg_trgm`) are excluded in `env.py`. `alembic check` is clean on a fresh database and on a schema-only clone of dev upgraded 0021 to head. CI job `migrations` and `tests/integration/test_migrations_match_models.py` keep it clean. Remaining on dev: five ad hoc `*_snapshot_*` tables (R3-B-24, not touched). **Not applied to the real dev database.** |
| R3-B-16 | Architecture | 17 application → infrastructure imports in 11 files; contract omits the layer. | **Fixed in source** `7c1fcf5`. New import-linter contract: application never imports infrastructure or interface (3 of 3 contracts kept). Moves: `INDICATOR_VERSION` and the BSE archive dates to the domain; `raw_from_config` and `compute_config_hash` to `domain/strategy/config_codec.py`; the strategy config check behind `StrategyConfigChecker` (port, injected); the calendar and strategy repository injected into `ExecuteScreening`; the data revision read through `OHLCVRepository.data_revision()`; `git_commit` in run stats stamped by the run repository when the run completes (it is a persistence-time fact). Logging uses `structlog` directly, as the rest of the layer did. |
| R3-U-04 | Web | Text contrast below 4.5:1 in both themes (84 nodes on the home screen). | **Fixed** `db6cfc3`, verified |
| R3-U-03 | Web | No `main` landmark on 14 of 25 routes. | **Fixed** `db6cfc3`, verified |
| R3-U-02 | Web | Unlabelled `select` and date input (axe critical). | **Fixed** `db6cfc3`, verified |
| R3-U-10 | Web | A stored strategy the workspace no longer offers left the Assessment on "loading run…" with 404s. Root cause: only the Screener page reconciled the stored choice. | **Fixed** `db6cfc3`; journey 4 |
| R3-U-07 | Web `/validation` | One hard-coded strategy; saved strategies cannot be validated. | **Fixed** `4c8962a` (backend `config_hash` on the dashboard and five GETs) and `57a37b4` (web picker, provenance line). `/validation/experiment/run` and `/research/compare/strategies` still resolve by name: accepted limitation, not trivial. |
| R3-U-01 | Web bundle | Main chunk 1,009.9 kB raw / 315.6 kB gzip (R2: 565.8 / 182.1). | **Fixed** `d062c16`: main chunk 1,010 → 654 kB raw, 316 → 209 kB gzip. The remainder (react-router, lightweight-charts, TanStack) is left whole: splitting it would not help the chart-open benchmarks. |
| R3-B-21 | Docs | Stale counts and claims (migrations, tables, tests, ADR index, readiness, ADR-003/007/009/012/014 text). | **Fixed in part**: migration and table counts, drawing tools, test counts and the Round 3 record are corrected. Still stale: ADR-003, 007, 009, 012 text and the ADR README index. |
| R3-U-15 | Web (introduced and fixed in this audit) | My first R3-U-10 fix set the strategy hash on every first visit. That flipped strategy-keyed query keys just after load; a fast Alt+W wrote to the old key and the watchlist panel never updated. Found by bisecting an order-dependent test failure. | **Fixed**, commit `Provider reset only when invalid`; `m12-shell` and `integrated-workflows` pass together |
| R3-B-26 | Scheduler | **New, found by the worker.** APScheduler 3 counts crontab weekdays from Monday = 0, so `30 18 * * 1-5` fired **Tuesday to Saturday**: Monday's session was screened on Tuesday and Saturday re-screened Friday. Seen live: the job fired Tuesday 18:30 IST with `day_of_week='1-5'`. | **Fixed in source** `e9ba4ba`. **Not deployed.** The running container still fires Tuesday to Saturday. |
| R3-O-03 | Test suite | The committed browser suite was red at HEAD: 4 specs still expected the pre-`cecb3e5` UI and one test asserted removed behaviour. | **Fixed** `2f311af` |
| R3-R2-09 | Research harness | `apply_parameter_overrides` is never called (inherited R1-P2-09). | **Mitigated** `7c1fcf5`; wiring stays open as a feature. Root cause: a variant run needs a persisted variant strategy (the run table has a foreign key to `strategies`), and a design for research strategies does not exist. Until then both experiment use cases ran the base strategy and reported it as a variant (a wrong number). They now refuse any override with a `ValidationError` (HTTP 422). The pure function stays, with its tests. Tests in `test_experiment_refuses_overrides.py`. |
| R3-R2-10 | Strategy catalogue | `rs_sector_relative`, `rs_industry_relative`, `rs_line_uptrend` still registered; v3 text names a detector that does not exist (inherited). | **Closed, retained on purpose** (2026-10-21). No strategy file uses the three rules. They stay registered because stored strategy versions (v1 and v2) name them and ADR-005 keeps a stored strategy readable as it was run, and because removing a rule changes the rule-registry fingerprint, which moves every `data_version`. The `v3` description names rules, not a detector; no detector text was found in the strategy files. Editing a description changes `config_hash`, so the text is not edited. |
| R3-R2-12 | Tooling | Eleven development-only npm advisories (inherited). Dependency audits not run this round. | OPEN. Owner: owner approval for `npm audit` and `pip-audit`. |

## P3

| ID | Finding | Status |
|---|---|---|
| R3-U-05 | 25 screener buttons "Checklist for X" with visible text "8/8" (label in name). | **Fixed** `db6cfc3` |
| R3-B-07 | `list_active` had no ORDER BY; equal-return RS ratings depended on heap order. | **Fixed** `f9a7ad4` |
| R3-B-25 | Audit tmpfs Postgres exhausted the Docker VM and the owner's API was OOM-killed at 10:59 UTC. | Closed (mitigated); API restarted, dev database untouched. Related: the API container has no memory limit. |
| R3-U-06 | Expected-empty GETs (`/screens/default`, `/drawings/{symbol}`) answer 404, logging a console error on every first load. Whitelisted in the E2E fixture. | **Fixed** `333f80c` (API: revision 0, `ETag: "0"`, ADR-013 §5) and `57a37b4` (client). The E2E fixture now fails on any 404 for a saved-document read. |
| R3-U-08 | 200 requests per minute per client; a page load costs 7 to 15; about 13 fast loads give 429, shown as partial data. E2E raises the cap to 100,000. | **Fixed** `1cd25eb` (1,200 per minute, `Retry-After`, problem body) and `51645b7` (client retries reads twice). |
| R3-U-11 | "Δ Rank" shows a green ↓ for an improvement (rank 144 → 1 reads ↓ 143). | **Fixed** `c6a65cd`: improved rank points up, with a title. The screener (`rank − previous`) and the watchlist (`previous − rank`) still use opposite signs in the API; the UI shows each correctly. Accepted limitation. |
| R3-U-12 | `scrollable-region-focusable` on `/strategies`, `/data` at 390 px and on Elliott Wave. | **Fixed** `fa5d000`; axe test at 390 and 1440 px in `r3-axe-routes.spec.ts`. |
| R3-U-13 | Phone chart cuts the data-source line. | OPEN. Owner: web. The line is truncated by design with the full text in a `title`, which touch screens cannot show. Fixing it means changing the fixed-height range bar, so it needs a visual decision. |
| R3-U-14 | Docs say 12 drawing tools; source has 21. | **Fixed**: `capabilities.md` says 21 drawing tools. |
| R3-B-17 | Historical `data_version` uses a wall-clock suffix. | OPEN |
| R3-B-18 | 22,328 `adj_close` rows differ from `close × adj_factor` (max 0.25%); 925 in the current RS window. | **Investigated read-only** (2026-10-21, `backend/decision-packet/stage-b/r3-b-18_adj_close_investigation.txt`). Exact count today: 56,134 rows in 98 securities (2019-10-01 to 2026-07-27), max gap 0.27%. All 56,134 equal `close × round(adj_factor, 4)`: an earlier writer used a 4-dp factor. The current writer uses the 8-dp factor. No engine reads `adj_close` (R3-B-30), so results are unaffected. Repair is one UPDATE; **not run**. **Owner**: authorise the write. |
| R3-B-19 | `/runs/<huge int>` gives 500. | **Fixed in source** `7c008d9`. Database ids in path parameters accept 1 to 2^63-1 (`EntityId`); a larger value answers 422. Test in `test_runs_api.py`. |
| R3-B-20 | CLI prints raw tracebacks on database errors; APScheduler lines are not JSON. | **Fixed in part** `7c008d9`: the CLI entry `main()` prints one line and exits 1 on `OSError` or a SQLAlchemy error. The APScheduler lines stay non-JSON (open). |
| R3-B-22 | ADR-056 does not exist. | **No reference to fix.** Re-checked 2026-10-21: the only mentions of ADR-056 are the audit record's statements that it does not exist (`state.md`, this register, `ADR_COMPLIANCE.md`, `CAPABILITY_VALIDATION_MATRIX.md`, `AUDIT_REPORT.md`). No code or product document cites it. Nothing was invented or renumbered. **Owner:** name the intended document (Q5), or drop the item. |
| R3-B-23 | Unclosed httpx client; 20 unclosed test connections; no body-size cap. | OPEN |
| R3-B-24 | Ad hoc research tables and views in the application database. | OPEN |
| R3-O-04 | `/strategies` hard load lost its `h1` once in the 234-case run; did not reproduce on four reruns. | NOT VERIFIED (root cause). Re-check in the final run. |
| R3-B-29 | **New (decision review).** The scoring engine leaves gate engines out of both weighted scores (`scoring_engine.py:119`); spec §10 sums every engine. The code documents it, and it is rank-neutral among names that pass the gates. | **Spec aligned** `f6ce742`: IMPLEMENTATION_SPEC §10 now leaves gate engines out of both weighted scores, as the code does (B10-7 default). Rank-neutral. Owner to confirm. |

## Decisions needed from the owner

1. **R3-B-31 (S-5)** — supply an identity-link file from authoritative exchange evidence (one row per rename: ids, effective date, ratio, source, and a reference with the document's SHA-256). Load it with `momentum25 import-identity-links FILE.csv`. Until then every renamed holding is flagged and no link is applied.
2. **R3-B-32** — approve a session-basis forward-return backfill on the development database (it writes new rows beside the old ones and rewrites nothing). Until then the validation surfaces show no matured rows.
   **R3-B-29** — confirm the spec amendment (gate engines out of both weighted scores).
   **S-10** — not done: checking the trading gaps against one exchange bhavcopy needs an external download, which this stage prohibits. The EQ-only ingest lead stays unverified.
   The Stage B decisions (S-1 to S-13 as answered) are implemented. See the Stage B note at the top.
3. **R3-B-08** — confirm (or revert `51f3239`) the read-path RS universe.
4. **R3-B-12 / R3-U-09** — what code version the manifest records.
5. **R3-B-13** — confirm the `/live` contract now in source: `data_as_of` is the stock's last bar; `data_sufficient` is false when it is older than the latest session.
6. **R3-B-18** — authorise repair of the `adj_close` rows in the development database.
7. Approve `pip-audit` and `npm audit` (they send the dependency list off-machine).
8. Accept ADR-012 and ADR-015; add LICENSE and NOTICE; clear the name; legal review of NSE and BSE terms.
9. **R3-B-22** — which document "ADR-056" means.
10. Rebuild and redeploy the image, and set `restart: unless-stopped`.
