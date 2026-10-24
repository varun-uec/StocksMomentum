# Architecture — as built

Verified against the code on branch `wickstreet/m10-m11` (M10) on 2026-10-18. The host, enforcement and [Wickstreet 2.0 platform](#wickstreet-20-platform-slice-0) sections were verified on 2026-10-23 (Slice 0), the [MF data](#wickstreet-20-mf-data-slice-1) section on 2026-10-23 (Slice 1), the [MF analytics](#wickstreet-20-mf-analytics-slice-2) section on 2026-10-23 (Slice 2), the [Slice 3](#wickstreet-20-mf-analytics-v3-slice-3) section on 2026-10-23, the [v4](#wickstreet-20-nav-analytics-v4) section on 2026-10-23, the [E2](#wickstreet-20-risk-free-rate-e2-method-v5) section on 2026-10-23, and the [v6–v7](#wickstreet-20-fund-facts-benchmark-holdings-idcw-and-portfolio-e1-e3e5-slice-6-methods-v6v7) section on 2026-10-24.

The approved blueprint is the [ADD](../architecture/ADD.md) and its [ADRs](../architecture/adr/). This page says what the code does today, and where it differs from that blueprint. When this page and the ADD disagree, the ADD still governs. The differences in [Drift from the ADD](#drift-from-the-add) need a decision.

## System

```mermaid
flowchart LR
  user(["Investor / operator"]) -->|"web app and JSON /api/v1, same origin"| api["api — FastAPI + APScheduler<br/>serves the Vite build · 127.0.0.1:8000"]
  api --> db[("PostgreSQL 16")]
  api --> redis[("Redis 7")]
  api -->|optional direct adapter, disabled by default| nse[("NSE archives + API")]
  api -->|optional direct adapter, disabled by default| bse[("BSE archives")]
  operator["operator-authorized CSV"] -->|import-eod / import-benchmark, offline| api
```

Docker Compose runs `db`, `redis` and `api`, and the one-shot `wickstreet-migrate` step before `api` starts. One image (root `Dockerfile`) builds the web app with Node and serves it from the API at `/`, so the browser calls `/api/v1` on the same origin (ADR-013). Every published port binds to `127.0.0.1`; the app has no authentication and is intended for one local user. `APP_BIND` can expose it to a network, but that instance is not secure without an authenticating proxy (ADR-012). `make up-dev` adds Adminer (8080) and RedisInsight (5540). The `api` container runs Momentum25 migrations on start, then `python -m apphost`, which serves Momentum25 at `/` and Wickstreet 2.0 at `/api/v1/mf` from one process. That process serves HTTP and runs the scheduler (ADR-007).

## Layers

Hexagonal architecture (ADR-001). Code lives in `backend/src/momentum25/`.

| Layer | Package | What it holds |
|---|---|---|
| Domain | `domain/` | Entities, value objects, ports, the 8 evaluation engines, pattern detectors, strategy engine, scoring, ranking, explainability, walk-forward backtest math (`backtest/`), Elliott Wave and chart-pattern analytics (`analytics/`), research math (`research/`: forward returns, data quality, stop-loss, swing targets, survivorship). No I/O. |
| Application | `application/` | Use cases (`use_cases/`, `use_cases/research/`), DTOs, two shared services (`services/corporate_actions.py`, `services/rs_ratings.py`). |
| Infrastructure | `infrastructure/` | SQLAlchemy models and repositories, Alembic migrations, NSE/BSE/Kite providers, NSE trading calendar, indicator and RS pipelines (pandas/numpy), Redis cache/lock/refresh gate, APScheduler, settings, structlog, Prometheus metrics, tracing, retry/circuit breaker. |
| Interface | `interface/` | FastAPI routers (15), dependency wiring, error handlers, middleware (including the `Host`/`Origin` guard), web-app serving (`api/spa.py`), input validation, Typer CLI, walk-forward wiring shared by CLI and API. |
| Composition | `main.py`, `app/services/` | App factory, startup/shutdown, daily job. `app/services/` holds the screening job and a bulk market-sync service. |

### Enforcement

`lint-imports` checks nine contracts in `backend/pyproject.toml`. CI runs it in the backend lint job.

1. Momentum25 layers: `interface` → `application` → `domain`.
2. Momentum25 `domain` imports nothing from `application`, `infrastructure` or `interface`.
3. Momentum25 `application` imports nothing from `infrastructure` or `interface`.
4. `momentum25` and `wickstreet` never import each other (ADR-023 OM-11).
5. `platform_common` imports neither application (U2).
6. Nothing imports `apphost` (U1).
7. Every `wickstreet` context is layered `interface` → `application` → `domain` (OM-11).
8. `wickstreet` domain and application code import no infrastructure, interface, wiring or persistence.
9. `wickstreet` domain and application code never import `wickstreet.config`, where the mode lives (OM-1).

All nine pass (2026-10-23). The Momentum25 contracts do not cover `infrastructure` or `app`.

## Wickstreet 2.0 platform (Slice 0)

Implements the platform items of [ADR-023](../architecture/adr/ADR-023-operating-modes.md) §7 (U1–U3, U6, U8). Slice 0 added no MF data; [Slice 1](#wickstreet-20-mf-data-slice-1) adds it and [Slice 2](#wickstreet-20-mf-analytics-slice-2) the analytics and read API. No agent or UI exists yet.

| Package | Holds |
|---|---|
| `platform_common/` | Code both apps use: structured logging (`log.py`), the async engine and unit of work (`database.py`), and the request-context, security-header, body-size and Host/Origin middleware with RFC-7807 problem responses (`http.py`). It imports neither app. Momentum25 imports it through its old module paths, binding its own error namespace, `M25_ALLOWED_HOSTS` and Prometheus metrics, so its behaviour is unchanged. |
| `wickstreet/` | The MF app. `app.py` is the composition root and the only reader of `WICKSTREET_MODE`. `config.py` holds the settings and the loopback rule. `context.py` holds `TenantContext` (tenant and user UUIDs). `dependencies.py` resolves a request's context and opens its tenant-scoped unit of work. `persistence/` holds the schema, roles, unit of work and the MF Alembic environment. `identity/` is the first bounded context, layered `domain` / `application` / `infrastructure` / `interface`. `cli.py` is the `wickstreet` command. |
| `apphost/` | The host. `main.py` mounts the MF app at `/api/v1/mf`, then Momentum25 at `/`, and enters both lifespans (Starlette runs none for a mounted app). `__main__.py` starts uvicorn on the configured address. |

**Modes.** `personal` uses the local identity adapter: one fixed tenant and user (UUIDv5 constants), registered at startup. `saas` refuses to start until the OIDC identity adapter exists (Phase 2). Personal mode refuses a non-loopback bind outside a container. Under Compose it binds `0.0.0.0` inside the container and refuses to start unless `WICKSTREET_PUBLISHED_BIND` (Compose passes `APP_BIND`) is loopback. The MF Host/Origin guard stays on.

**Tenancy.** MF tables live in the `wickstreet` schema. `wickstreet_owner` owns it and runs only the MF migrations. `wickstreet_app` is the runtime login: no superuser, no BYPASSRLS, DML grants on MF tables only. The app refuses to start as a superuser, a BYPASSRLS role or an MF table owner. Each request runs in one transaction that first sets `wickstreet.tenant_id` with `set_config(…, true)`. Every tenant-scoped table has forced row-level security, with one policy comparing its tenant column to that setting; an unset setting matches no row. Repositories also filter by tenant. Tables: `tenant`, `app_user` (migration `0001_identity_tenancy`).

**Migrations.** `backend/alembic-wickstreet.ini` points at `src/wickstreet/persistence/migrations`. Its version table is `wickstreet.alembic_version`, and it compares only the `wickstreet` schema. Setup is two steps, both outside API startup: `wickstreet db-roles` (with `WICKSTREET_ADMIN_DATABASE_URL`, a login that can create roles) creates or updates the roles and schema; `alembic -c alembic-wickstreet.ini upgrade head` runs as the owner. Compose runs both in `wickstreet-migrate`; locally, `make mf-migrate`.

| Criterion | Proven by (`backend/tests/wickstreet/`) |
|---|---|
| OM-1 no mode in domain or application | contract 9; `test_boundaries.py` scans those modules for mode names and values |
| OM-2 loopback only | `test_loopback_only.py`: bind rule, Compose published port, launcher, Host guard |
| OM-8 cross-tenant denial | `test_tenant_isolation.py`: per table in `tenant_cases.py`, as `wickstreet_app`: scan, read, change, delete, move, forge, no tenant, setting lifetime; no grants on Momentum25 tables; API `/me` |
| OM-10 no single-user tables | `test_schema_rules.py`: catalog rule for every MF table, and a probe table that breaks it |
| OM-11 boundaries | contracts 4–8; `test_boundaries.py` requires each context in contract 7 |
| OM-12 MF routes and migrations | `test_boundaries.py` (routes, metadata, `ALL_VERSIONED`); `test_schema_rules.py` (models match migrations; down and up leaves Momentum25's tables and version rows unchanged); `test_host.py` |

## Wickstreet 2.0 MF data (Slice 1)

Implements ADR-017 MF-2 to MF-11, ADR-021 rule 1 and ADR-022 §2.11–§2.12 under the owner's decisions in [ADR-023](../architecture/adr/ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23) U9–U11.

| Package | Holds |
|---|---|
| `wickstreet/data_rights/` | The rights register (`rights_grant`, written only with the owner login) and `RightsGate`, which fails closed. Every run asks it for `automated_retrieval` before a fetch and `storage` before a write, and records both grant ids on the revision. No interface layer. |
| `wickstreet/mf_data/domain/` | The `nav-v1` and `schemes-v1` contracts, blocking checks and anomaly flags (`validation.py`), the series comparison, and the ports: `NavSource`, `ArchiveSource`, `ReferenceSource`, `RawStore`, `MfStore`. |
| `wickstreet/mf_data/application/ingest.py` | `IngestNavDay`, `IngestSchemeMaster`, `Backfill`, `DailyRefresh`, `ImportArchive`, `CrossCheck`. All runners share one PostgreSQL advisory lock. |
| `wickstreet/mf_data/infrastructure/` | `amfi.py`, `tigzig.py`, `mfapi.py` (each over `client.py`: one request at a time, 1 s apart, retries on 429, 5xx and transport errors), `raw_store.py` (gzip files under `WICKSTREET_RAW_DIR`), `store.py`, `tables.py`, `scheduler.py` (11:30 IST), `report.py`. |
| `wickstreet/wiring.py` | Builds the ingestion graph for the CLI and the app. |

**Storage (migration `0002_mf_data_foundation`).** `plan_option` keys each AMFI code on a surrogate id (MF-2). `nav` is append-only: a changed value inserts a row at revision R and marks the old row `superseded_revision = R`; a value is visible at R when `revision_id <= R` and it is not superseded at or before R (MF-5). `plan_option_listing` (from AMFI NAV files) and `plan_option_master` (from a scheme master) hold effective-dated attributes. `revision` records each publication's URL, fetch time, SHA-256, raw file path, adapter version, contract and grant ids (MF-9). `publication` is a one-row pointer to the latest revision (MF-6). `ingestion_run` holds one row per source, dataset and period, with status, counts, anomalies and conflicts (MF-10). MF data is shared reference data, so these tables have no row-level security.

**Sources and precedence (ADR-023 U11).** AMFI direct is the source of record from the first date it serves, 2023-04-01: one run per date, plus the scheme master. Before that date the TigZig archive is the record, one run and one revision per calendar month. From that date on the archive only fills a code and date that AMFI lacks; a different value counts as a conflict on the run and AMFI's value stays. TigZig keeps NAVs to 4 decimals, so a difference of 0.0001 or less is rounding. The TigZig snapshot adds master rows only for codes with none. MFAPI writes nothing: `mf crosscheck` compares a fixed sample of codes with the store.

**Checks.** A file blocks (the run fails and nothing publishes) when its layout is unknown, it has no rows, a row has another date, or a code appears twice with different values. Rows are stored as filed, and missing, zero or negative NAVs and moves beyond 25% of the previous NAV are flagged (MF-8). An unchanged file is a no-op (MF-7).

**Data loaded (local database, 2026-10-23).** 22,267,862 current NAV rows on every calendar date from 2016-10-16 to 2026-10-22 (3,659 dates; no date without a settled run, no weekday without a NAV). AMFI direct holds 7,197,748 rows from 2023-04-01 (1,301 daily runs, no failure). TigZig holds 15,070,114 rows before that (78 monthly runs). 40,213 plan-options have master rows: 16,472 from AMFI's master and 23,741 from the TigZig snapshot; 22,397 have a NAV in the window. Flags: 201,625 `nav_zero` (segregated portfolios filed at 0.00), 681 `nav_jump`, 8 `nav_missing`. Reconciliation: TigZig's 7,180,754 rows from 2023-04-01 on add no code or date that AMFI lacks; 6 values differ, one fund-of-funds on 2026-10-22 at +0.053%, and AMFI's are kept. MFAPI, 100 sampled codes over the window: 82,274 values match, 30 differ (0.036%), and the store holds 5,838 dates MFAPI lacks (mostly 2016–2018). Reconciliation found one parser defect: AMFI writes some NAVs with a bare point (`222.`), which were stored as null. The fixed adapter (`amfi-2026-10-23.2`) re-derived 992 dates from their raw files, so 1,839 values are corrections that keep the nulls as history. Database 7.6 GB (NAV table 2.8 GB); raw files 362 MB. Logs and the full report: `~/.wickstreet/logs/`.

**Known limits.** AMFI's history report restates current scheme names and categories for past dates, so attributes stored from the backfill are those of 2026-10-23, and name history accumulates from the daily refresh on. TigZig's archive has the filed name per row, but it is not stored. Archive NAVs before 2023-04-01 have 4 decimals. MFAPI and TigZig differ on 30 values, mostly before 2023, that no direct AMFI file can settle.

**Operations.** `wickstreet mf backfill`, `mf archive`, `mf crosscheck`, `mf refresh`, `mf reparse` and `mf report` (see `backend/README.md`). `mf reparse` re-derives published AMFI dates from their kept raw files after a parser fix; it checks each file against its recorded SHA-256 and publishes changed values as a new revision under the new adapter version. The daily refresh re-reads the master and the last 7 days, or every date since the last stored one after downtime. With `WICKSTREET_REFRESH_ENABLED=true` (Compose sets it) the app runs it at 11:30 IST, and at startup when the day's run is due. If `SSL_CERT_FILE` points at an older CA bundle, AMFI's Sectigo R46 chain fails; unset it or point it at certifi's bundle.

## Wickstreet 2.0 MF analytics (Slice 2)

Implements ADR-017 MF-3, MF-11 to MF-13 and ADR-018 for MF, under the method in [mf-metrics.md](mf-metrics.md) (v2). Plan: [19-slice-2-mf-analytics.md](../plans/wickstreet-2/19-slice-2-mf-analytics.md).

| Package | Holds |
|---|---|
| `wickstreet/mf_data/domain/reads.py` | The read contract MF data publishes: `FundRecord`, `FundSeries`, `History`, `NavPoint`, `Link` and the `MfReader` port. Analytics reads MF data through it only. |
| `wickstreet/mf_data/infrastructure/reader.py` | `SqlMfReader`. `history()` reads every series in one repeatable-read, read-only transaction and streams the NAV rows through a server-side cursor in (plan-option, date) order, one fund at a time. Every other read applies the MF-5 rule at an explicit revision. Also `record_link` (owner login). |
| `wickstreet/analytics/domain/` | `metrics.py` (method v2, pure functions over date ordinals), `classify.py` (plan, option, category), `fields.py` (the registry, generated from the metric tables; `registry_version` is a SHA-256), `screening.py` (filter tree, operators, sort, cursor), `snapshot.py` (deterministic encoding, the `SnapshotStore` port). |
| `wickstreet/analytics/application/research.py` | `ComputeSnapshot` (requires `derived_metrics` for each source; a no-op when the pointer's snapshot exists) and `Research` (requires `display` for each source of the snapshot it reads). The rights checks sit here, so Slice 4's agent tools inherit them. |
| `wickstreet/analytics/infrastructure/` | `metric_snapshot` table and `SqlSnapshotStore` (keeps the two newest decoded snapshots in process; a snapshot never changes). |
| `wickstreet/analytics/interface/http.py` | `GET /screener/fields`, `POST /screener/run`, `GET /funds?q=`, `GET /funds/{code}`, `GET /funds/{code}/metrics`, `GET /funds/{code}/navs`, `GET /compare?code=…`, under `/api/v1/mf`. |

**Storage (migration `0003_mf_analytics`).** `metric_snapshot` holds one row per (revision, method version): as-of date, fund count, sources, the `derived_metrics` grant ids, the SHA-256 of the JSON body and the gzipped body (5.2 MB for 40,213 funds). `plan_option_link` holds curated merger, code-change and segregated-portfolio links (MF-3); the owner login writes them (`wickstreet mf link add`) and the app only reads them. Method v2 never splices across links.

**Retired snapshots (migration `0010_snapshot_retirement`).** `wickstreet mf retire-snapshot ID --reason … --by …` (owner login) stops serving a snapshot. Its row and payload stay, with `retired_at`, `retired_by` and `retired_reason`. Reads, latest or pinned, never select it, so a pinned request for its revision answers 404 `no-snapshot`. Only one unretired snapshot may exist per (revision, method version), so the revision can be computed again. On 2026-10-24 the owner retired snapshot 12 (revision 3092, v7, computed before the IDCW-window fix `be62c48`). Snapshot 13 (revision 3164, v7, computed before the proxy-gap fix `bed165e`) was retired under the same rule. No saved record pinned either revision, so neither was recomputed.

**Revision pinning.** Every read resolves one snapshot: the caller's `data_revision`, or the latest. Metrics, screens, fund detail, search, NAV ranges and comparisons all read at that revision. A screen cursor carries the snapshot revision and a SHA-256 of the filter and sort, so its pages stay on one snapshot and a cursor reused with another request is refused (422). Every response carries `data_revision`, `latest_revision` (the live pointer), `method_version`, `as_of` and `sources`. The same request at the same revision gives the same bytes, except `latest_revision`.

**When snapshots are computed.** The app's 11:30 IST job refreshes when the day's slot is due, then computes; startup runs the job once. Every CLI publish path (`mf backfill`, `archive`, `reparse`, `refresh`) computes after a run that published. `wickstreet mf metrics` computes on demand. A failed compute is logged and does not stop the app.

**Screens (ADR-018, doc 06).** Operators `> >= < <= = != between in not_in is_available is_missing top_pct bottom_pct`. A percentile threshold is taken over every fund in the snapshot with a value; ties at the threshold pass. Each row carries every condition's outcome and the value it tested (`conditions`). When nothing matches a top-level `all`, `relaxations` gives the count without each part. `GET /screener/fields` marks a field with no value in the snapshot `available: false` with the most common reason.

**Errors.** RFC-7807 `application/problem+json`: `rights-denied` (403), `invalid-request` and `invalid-cursor` (422, with the path of the bad filter node), `no-snapshot` and `unknown-fund` (404).

**Measured on the real store (2026-10-23, revision 2769, 22.27M NAV rows).** Compute: 82 s wall time, 297 MB peak RSS, 40,213 funds (targets 300 s and 1 GB). Snapshot load: 1.2 s. Screen evaluation over 40,213 rows: 17 ms for a 5-condition filter, 18 ms for 10 conditions; `POST /screener/run` 27–41 ms end to end in the container. The opt-in test `tests/wickstreet/test_mf_real_data.py` (`WICKSTREET_REAL_DATA_URL`) recomputes `ret_1y`, `cagr_3y` and `cagr_5y` for 50 fixed sample funds from independent SQL anchors (equal within 1e-12), checks the range of every value, and recomputes the snapshot byte for byte. Coverage of the 8,668 active plan-options: `ret_1y` 7,887, `cagr_3y` 6,366, `cagr_5y` 4,874, `cagr_10y` 3,175; `mdd_since` is `NM` (a gap over 7 days) for 141. Options: 4,551 IDCW, 3,693 growth, 354 unknown, 70 bonus. 1,102 are Unclassified (AMFI's pre-2018 debt labels and broad labels).

**Event loop.** A compute shares the app's event loop. Rows are serialised as they are computed, the loop gets a turn every 256 funds, and gzip and SHA-256 run in a thread. Measured over a full real compute: the loop waits 29 ms at p99 and 51 ms at most. After each compute the job decodes the new snapshot (1.2 s, once), so the first request does not wait for it.

**Known limits.** See [mf-metrics.md](mf-metrics.md#known-limits). Every snapshot is kept; pruning is not built.

## Wickstreet 2.0 MF analytics v3 (Slice 3)

Implements [doc 20](../plans/wickstreet-2/20-wickstreet-2.0-complete-mf-scope.md) §3 and the Slice 3 row of §5, under method v3 ([mf-metrics.md](mf-metrics.md)).

| Module (`wickstreet/analytics/domain/`) | Holds |
|---|---|
| `metrics.py` | Per-fund v3 metrics: status, annual returns, drawdown episodes, worst periods, downside risk, and the month-end rolling 3Y returns for consistency (compact arrays). |
| `peers.py` | Category ranks, percentiles, quartiles and medians, consistency and the composite score, one peer group at a time. |
| `classify.py` | Adds sibling categories. |
| `formulas.py` | Screen formulas: an `ast` whitelist of numbers, number fields, `+ - * /` and parentheses. |
| `presets.py` | Six prebuilt screens. |
| `views.py` | Per-fund views computed on request: annual and monthly returns, rolling series, drawdown episodes, correlation. |
| `calculators.py`, `tax.py` | SIP, lump sum, SWP and STP over real NAVs, FIFO lots, XIRR, and the `in-2024-07-23` capital-gains rules. |

**Routes** (under `/api/v1/mf`, all pinned like Slice 2): `GET /screener/presets`; `POST /screener/run` accepts `formulas`; `GET /funds/{code}/annual`, `/rolling?window=1y|3y|5y`, `/drawdowns?top=`; `POST /calculators/{sip|lumpsum|swp|stp}`; `GET /compare` adds return correlations. A bad simulation gives 422 `invalid-simulation`.

**Compute.** `ComputeSnapshot.encode` runs in three passes. Pass 1 computes each fund's own metrics from the stream. Pass 2 sets sibling categories and runs each peer group. Pass 3 streams the rows through `snapshot.Encoder`, which gzips and hashes them as they come. The registry has 120 fields. A snapshot stores a missing value as `null` plus a small reason code, and it stores its missing counts, so decoding allocates little.

**Measured on the real store (2026-10-23, revision 2769).** Compute: 102 s, 404 MB peak (a recompute in a child process: 101 s, 388 MB). Payload 9.0 MB gzipped. Load 0.6 s; one decoded snapshot holds 219 MB. The loop waits 75 ms at most during a compute. Presets screen in about 18 ms; a formula over all 40,213 funds screens in 132 ms. Of 8,668 active funds, 4,688 have a score and 4,730 a consistency value; 1,102 stay Unclassified, because no sibling plan-option carries a current label. The opt-in real-data test checks the ranges of every v3 field and recomputes the snapshot byte for byte.

**Snapshot rows replaced.** While the encoding changed on 2026-10-23, the v3 snapshot of revision 2769 was recomputed twice; the superseded rows (ids 3 and 4, derived caches) were deleted with the owner login. Snapshots 1 and 2 (v1, v2) stay.

## Wickstreet 2.0 NAV analytics v4

Implements the v4 scope of [doc 21](../plans/wickstreet-2/21-analytics-expansion-v4.md) under method v4 ([mf-metrics.md](mf-metrics.md)). Backend only: the owner paused UI work.

| Module (`wickstreet/analytics/domain/`) | Adds |
|---|---|
| `classify.py` | SEBI 2026 categories and `fund_type`. |
| `metrics.py` | Rolling percentiles, current drawdown and longest time under water; per fund, the month-end NAV, 1Y and 3Y values (`MonthEnds`), the year-ago values, and the 3Y NAVs of active funds for near-duplicates. |
| `peers.py` | Point-in-time groups (members include funds that stopped), monthly ranks, persistence, year-ago ranks and changes, transitions; `rank_all` is the one ranking formula. |
| `relations.py` | Direct–regular pairs and gaps, near-duplicates (numpy screen, then the exact compare correlation), the regime proxy and its windows. |
| `views.py` | Underwater series, recovery spread, rolling SIP, frontier. |
| `backtest.py` | Point-in-time top-N backtests against the group median, in-sample and hold-out. |
| `tax.py` | Rule set `in-2018-04-01`: rules by sale date, indexation, pooled loss set-off. |

**Snapshot.** 151 registry fields. The body adds `tables`: `pairs`, `near_duplicates` (top 10 per fund), `regimes` and `proxy` (label and daily levels). Pass 2 runs each peer group in a worker thread. Rank history, transitions and backtests read the group's series at the pinned revision and recompute month-ends with the same functions as the snapshot.

**Routes** (under `/api/v1/mf`, pinned like Slice 2): `GET /funds/{code}/rank-history`, `/direct-regular`, `/underwater`, `/rolling-sip?tenor=&amount=&day=&step_up=`, `/near-duplicates`, `/score`, `/confidence`, `/regimes`; `GET /peers/transitions` and `/peers/frontier` (`category`, `plan`, `option`); `GET /regimes`; `POST /backtests`. `GET /screener/fields` adds `coverage`; `GET /compare` adds `average_correlation`. Existing routes keep their shape.

**Measured on the real store (2026-10-23, revision 2769), against the Slice 3 baseline.**

| Measure | Slice 3 | v4 |
|---|---|---|
| Compute | 102 s, 404 MB | 118–125 s, 508–574 MB |
| Payload | 9.0 MB gzip | 10.4 MB gzip |
| Load and decode | 0.6 s | 0.8 s |
| Presets | ~18 ms | 30–35 ms |
| Longest event-loop stall during a compute | 75 ms | ~170 ms (full GC passes; per-group work runs in a thread) |
| Rank history, transitions or backtest, largest group (Index Funds direct growth, 409 funds) | — | 0.67 s on the first call, 17–29 ms after (was 1.4 s) |
| Backtest, Flexi Cap direct growth | — | 0.37 s |
| Rolling SIP 5Y, underwater, confidence, regimes, score, frontier | — | 7–94 ms |

Three computes gave the same SHA-256. Of 8,668 active funds, 111 stay Unclassified (v3: 1,102). The opt-in real-data tests check the v4 ranges, current drawdown against SQL, month-end ranks against an independent pandas rebuild, near-duplicates against the compare correlation (1e-12), pair gaps, and a byte-identical recompute.

**Peer-group reads.** `SqlMfReader.series` filters `nav` on `plan_option_id`, so PostgreSQL walks `pk_nav` in order; the earlier filter on `amfi_code` through the join made it scan all 22M rows (1.28 s → 0.26 s in the database). `Research` keeps the month-ends of the last 32 peer groups per snapshot in process; a snapshot never changes, so entries need no invalidation.

**Real-data validation.** Opt-in tests rebuild, with separate code: month-end ranks (pandas from SQL), the backtest month by month (pandas), the rolling SIP (pandas, with XIRR by Newton's method against the code's bisection), and the regime proxy's levels and windows (pandas). All match.

**Not built.** The splice across `plan_option_link` (M16): the table has no rows, and links are curated, never inferred.

**Snapshot row replaced.** The first v4 snapshot (id 6) used an approximate near-duplicate correlation; it was deleted and recomputed as id 7. Snapshots 1, 2 and 5 (v1–v3) stay.

## Wickstreet 2.0 risk-free rate (E2), method v5

Implements dataset E2 of [doc 21](../plans/wickstreet-2/21-analytics-expansion-v4.md) and method v5 ([mf-metrics.md](mf-metrics.md#risk-free-v5)).

- **Source.** RBI's 91-day Treasury Bill auctions: the Handbook of Statistics table "Auctions of 91-Day Government of India Treasury Bills" (editions 2017 to 2026, each about July to June) and the weekly "Treasury Bills: Full Auction Result" press releases for later auctions. DBIE's report viewer failed (its report host serves an invalid certificate), and RBI's file host answers scripts with a bot challenge. So **Wickstreet fetches nothing**: a person downloads the files, and `wickstreet mf import-rates FILE... --url URL...` imports them. Grants 13–16 (`rbi`: storage, display, derived metrics, internal AI processing) record RBI's reuse-with-acknowledgement terms and the owner's direction.
- **Code.** `mf_data/infrastructure/rbi.py` parses both layouts with the standard library (zip and XML for XLSX). `ImportRates` checks the rates (`check_rates`), keeps the raw file, and publishes one revision per file through `SqlMfStore.publish_rates`. A changed value supersedes; nothing is deleted. Migration `0004` adds `rate_point` (shared reference data) and makes `revision.retrieval_grant_id` nullable: an imported file has no retrieval grant. `History.risk_free` and `MfReader.rates` read the series at the revision; `metrics.RiskFree` turns it into the daily-accruing deposit.
- **Loaded (2026-10-23).** 529 auctions, 2016-07-05 to 2026-10-14; overlapping files agreed exactly (0 superseded). The 2026-10-21 auction accepted no bids and has no rate. Snapshot v5 at revision 2801: 126 s, 585 MB.
- **Routes.** `GET /risk-free` (points, method, RBI acknowledgement). Fields `rf_1y`, `rf_3y`, `sharpe_1y`, `sharpe_3y` and `sharpe_3y_cat_*`; `sortino_3y` now measures against the risk-free return.
- **Checks.** Unit tests on synthetic RBI-shaped files; an import test (storage grant needed, no retrieval grant recorded, unchanged re-import, correction supersedes); a real-data test that rebuilds `rf_3y` and `sharpe_3y` with pandas from SQL (1e-9). The v5 recompute is byte-identical.
- **Operation.** Rates go stale 35 days after the last stored auction, then risk-free fields become `NA no_risk_free`. New auctions must be imported until the owner decides whether Wickstreet may fetch the weekly releases itself.

## Wickstreet 2.0 fund facts, benchmark, holdings, IDCW and portfolio (E1, E3–E5, Slice 6), methods v6–v7

Implements datasets E1, E3 (proxy), E4 and E5 of [doc 21](../plans/wickstreet-2/21-analytics-expansion-v4.md) and methods v6 and v7 ([mf-metrics.md](mf-metrics.md#fund-facts-v6)), and the portfolio context (doc 21 C25, C26). Sources and rights: [ADR-023](../architecture/adr/ADR-023-operating-modes.md) U14.

- **Sources.** `mf_data/infrastructure/amfi_facts.py` (`AmfiFactsAdapter`): AMFI's scheme list, scheme summary documents (XML), monthly TER (XLSX), fund performance (JSON gateway, one call per sub-category and date), tracking error, IDCW history and the half-yearly market-cap lists. AMFI's gateway refuses non-browser user agents, so the client sends a compatible user agent that still names Wickstreet. `amc.py` (`AmcPortfolioAdapter`): PPFAS and DSP, whose pages list their monthly files in HTML; the other AMCs build their pages in JavaScript, so their files are imported (`mf import-portfolios`). `portfolios.py` parses any AMC's XLSX, XLS or zip portfolio file; `xlsx.py` reads workbooks with the standard library, and `xlrd` reads binary XLS.
- **Code.** `IngestFacts` (`mf_data/application/facts.py`) and `IngestPortfolios` (`portfolios.py`) follow the NAV ingest: an `ingestion_run`, the retrieval grant before fetch, the raw file kept, the storage grant before publish, one revision per file. Join keys live in `mf_data/domain/facts.py`. Fact days for monthly data are the latest business day of each month (`latest_nav_day`: a day with at least half the NAVs of the busiest day in the 10 before it).
- **Storage (migrations `0006`–`0009`).** `scheme` and `scheme_isin` (scheme ↔ plan-option ISINs), `scheme_fact` (one fact per scheme, name, plan and date), `holding` (one portfolio line), `security_class` (AMFI cap class per ISIN and date) and `distribution` (IDCW per plan-option and record date). All are shared reference data, revisioned like NAVs (MF-5). `FactView` carries them into `History`; `MfReader.scheme_profile` and `scheme_portfolios` read one scheme.
- **Analytics.** `analytics/domain/enrichment.py` (fact, cost-rank, proxy and IDCW fields), `holdings.py` (portfolio summary, changes, overlap, trend). `fieldspec.py` holds `Field`, so the field modules do not import each other. 55 new fields (215 in all).
- **Portfolio context (`wickstreet/portfolio/`).** `infrastructure/cas.py` parses a CAS PDF in memory with `casparser`; it keeps folios, schemes, ISINs, AMFI codes, transactions and closing balances, and drops the investor's name, PAN, email and address. `store.py` (`SqlLedger`) stores imports and transactions in `portfolio_import` and `portfolio_txn` (migration `0008`): tenant- and owner-scoped, forced RLS, one fingerprint per line so an overlapping statement adds only new lines; undo deletes one import and its lines. `domain/analytics.py`: positions, XIRR, unit reconciliation against the statement (0.001 units), allocation, costs, look-through holdings, fund overlap, rebalancing trades. The CAS file and password are never stored, logged or sent to a model provider (U13 b).
- **Routes.** `GET /funds/{code}/profile`, `/funds/{code}/benchmark`, `/funds/{code}/holdings?as_of=`, `GET /holdings/overlap?code=…`; `POST /portfolio/preview`, `POST /portfolio/imports`, `DELETE /portfolio/imports/{id}`, `GET /portfolio?target=Equity:60,Debt:40`.
- **CLI.** `wickstreet mf facts {schemes|ssd|ter|performance|tracking-error|market-caps|idcw}`, `mf portfolios --amc [--refetch | --reparse]` (`--reparse` re-derives published months from the kept files after a parser fix; nothing is fetched), `mf import-portfolios FILE... --amc --month --url`.
- **Loaded (2026-10-24).** Scheme list: 12,631 schemes. SSDs: 1,692 schemes (both layouts). Scheme joins: 8,790 of 8,818 active plan-options (6,683 by ISIN or AMFI code, the rest by unique scheme name). TER: 94 months, 2019-01 to 2026-10. Fund performance: every month-end business day 2019-04 to 2026-09 (90 reports, all full) and 2026-10-22. Tracking error: 32 dates, 2024-10 to 2026-10. Market-cap lists: 6 half-years, Dec 2023 to Jun 2026. Holdings: PPFAS and DSP, Oct 2024 to Sep 2026, 1,720 portfolios, 5 off 100% by more than 2%. IDCW: 20,058 payouts on 634 plan-options; AMFI lists payouts for 196 schemes only. Rate limits: AMFI's gateway answers HTTP 429 to parallel jobs; run them one at a time.
- **Snapshot v7 (revision 3364).** 154 s, peak 999 MB (targets 300 s, 1,024 MB). Coverage over the 1,825 active direct growth plans: TER 99.6%, AUM 97.3%, riskometer and benchmark 98.1%, manager tenure 74.1%, AMFI 3Y return against the benchmark 65.2%, proxy beta and alpha 29.9% (985 have no index fund on their benchmark), holdings 3.9% (72 plans of PPFAS and DSP). IDCW fields: 196 of 2,224 active direct IDCW options.
- **Checks.** 399 Wickstreet tests (parser, holdings, joins, reparse, IDCW, proxy statistics against pandas); 17 real-data tests on the store, including independent rebuilds of TER, proxy statistics, IDCW returns and holdings shares from SQL rows, and the byte-identical recompute; MF E2E 64 on the served app, axe in both themes, phone width on the new tabs.

## Data stores

**PostgreSQL** (ADR-004). 28 tables, 21 Alembic migrations (`0001` → `0021`). `alembic check` still reports drift between the ORM and the migrations (R3-B-15).

| Group | Tables |
|---|---|
| Instruments | `securities`, `bse_scrip_junction` |
| Prices | `ohlcv_daily` (current provider, 2019-09-30 →), `legacy_ohlcv_daily` (NSE archive, 1994-11-03 →, overlaps the current provider to 2024), `bse_legacy_ohlcv_daily` (BSE archive, 2006-03-01 → 2024-01-01), `benchmark_index_daily` |
| Corporate actions | `corporate_actions`, `corporate_action_inference_log` |
| Universe and survivorship | `historical_universe`, `survivorship_gap_event`, `universe_membership` |
| Strategy and runs | `strategies` (`kind`: production, research or user), `screening_runs`, `screening_results`, `rule_results` |
| Strategy Studio (ADR-014) | `strategy_families` (append-only), `strategy_evaluations` (the research namespace; a completed row is final), `data_manifests` |
| History (ADR-014 §7) | `<table>_history` for `securities`, `ohlcv_daily`, `corporate_actions`, `benchmark_index_daily`, `historical_universe`; one sequence `data_revision_seq`; a `provenance` column on each versioned table |
| Validation | `forward_returns` |
| User | `watchlist_items`, `user_documents` (saved workspace and drawings, versioned by `revision`; ADR-013 §5), `alerts` |

Run tables are append-only per `run_id` (ADR-006). Triggers enforce the history tables, the append-only families and the final evaluations.

**Redis.** Universe RS-rating cache, a distributed lock, and a refresh cooldown gate. The API falls back to no cooldown when Redis is down.

**Strategy configs** are JSON files in [`docs/architecture/strategies/`](../architecture/strategies/). The API reads them at startup (`M25_STRATEGY_DIR`, default `../docs/architecture/strategies`) and syncs them into `strategies`. Do not move that folder without changing the setting.

## External data

| Source | Adapter | Use |
|---|---|---|
| NSE EOD bhavcopy (current) | `providers/bhavcopy.py`, `providers/nse_client.py` | Optional direct adapter, explicitly disabled by default; requires operator authorization. |
| NSE legacy archive | research backfill use cases | Prices 1994-11-03 → 2019-09-29 |
| BSE bhavcopy | `providers/bse_bhavcopy.py` | Optional direct adapter, explicitly disabled by default; requires operator authorization. |
| Authorized CSV exports | `momentum25 import-eod`, `momentum25 import-benchmark` | Supported offline daily-bar, corporate-action and benchmark imports. |
| NSE corporate actions API | `application/services/corporate_actions.py` | Optional direct refresh when explicitly enabled. The public data workflow accepts action CSVs. |
| Zerodha Kite Connect | `providers/kite.py` | Adapter exists. Nothing calls it. |

## Configuration

All settings come from `M25_*` environment variables (`infrastructure/config/settings.py`). Key ones: `M25_DATABASE_URL`, `M25_REDIS_URL`, `M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED` (default `false`), `M25_SCHEDULER_ENABLED` (default `false`; `.env.example` also sets `false`), `M25_SCHEDULE_CRON` (default `30 18 * * 1-5`, Asia/Kolkata), `M25_STRATEGY_DIR`, `M25_ALLOWED_HOSTS` (host names the API answers to; default loopback), `M25_WEB_DIST_DIR` (built web app to serve; empty = API only). See [operations/deployment.md](../operations/deployment.md).

## Drift from the ADD

The ADD was written for a greenfield MVP (milestones M0–M8). The code has grown past it. These items differ from the approved blueprint. Each needs either an ADD amendment or a code change. None is decided yet.

| # | ADD / ADR says | Code does | Recommendation |
|---|---|---|---|
| D1 | Indicators are pure domain functions (ADD §10, §17). | Indicator math runs in `infrastructure/pipelines/indicator_pipeline.py` with pandas and reads the database. `domain/indicators/` holds only the port. | Amend the ADD to accept the pipeline as an adapter, or move the math into the domain. The second keeps the "pure core" claim true. |
| D2 | Out of scope: backtesting, BSE, advanced patterns (ADD §4). | Walk-forward backtest, BSE legacy data, cup-with-handle and ascending-base detectors all ship. | Amend ADD §4–§6 and §27 to record them. |
| D3 | Not in the ADD at all. | Elliott Wave analysis, chart-pattern analysis, validation and research APIs, watchlist, market context. | Amend the ADD. They are isolated research surfaces (see [design.md](design.md#research-isolation)). |
| D4 | Redis is a later SaaS step (ADD §24, ADR-007). | Redis is a required service for caching, locking and the refresh gate. | Amend ADR-007 or write a new ADR. |
| D5 | Gate engines count in the momentum score (ADD §21). | `ScoringEngineImpl` drops gate engines from both weighted scores. Rank-neutral for the production strategy only, because the Trend Template scores 1.0 for every qualifier (IMPLEMENTATION_SPEC §10). | Amend ADD §21. |
| D6 | API: `GET /rankings/latest`, `GET /rankings/{run_id}` (ADD §14). | `GET /rankings/runs/{run_id}`; the latest run comes from `GET /runs/latest`. | Amend ADD §14 and IMPLEMENTATION_SPEC §5. |
| D7 | CLI commands `ingest` and `screen` (ADD §10). | `ingest` exits nonzero with the offline `import-eod` replacement; `screen` runs over stored data without downloads. | Resolved in release hardening. |
| D8 | Layers: domain, application, infrastructure, interface. | `app/services/` sits outside all four and no contract covers it. | Move it into `application` or `interface`, and add a contract. |
| D9 | Import contracts run in CI (README claimed this). | CI runs ruff, mypy, pytest, `npm run lint`, `npm run build`. Not `lint-imports`. | Add `lint-imports` to `.github/workflows/ci.yml`. |
| D10 | `POST /runs` triggers a refresh (ADD §16). | `POST /runs` schedules the offline-by-default ingest-and-screen pipeline; direct downloads require explicit opt-in. | Resolved in the 2026-10-19 E2E audit. |

The Wickstreet program ([ADD Amendment A1](../architecture/ADD-amendment-A1.md), ADR-011 to ADR-014) began on 2026-10-17. See [state.md](state.md#in-flight).
