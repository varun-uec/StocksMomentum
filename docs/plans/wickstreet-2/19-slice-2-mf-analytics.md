# Wickstreet 2.0 — Slice 2: MF analytics engine, screener and read API

> **Status: Built (2026-10-23).** The owner's final plan review of 2026-10-23 approved this plan with four implementation details and directed implementation. As built: [architecture](../../current/architecture.md#wickstreet-20-mf-analytics-slice-2); method: [mf-metrics.md](../../current/mf-metrics.md).

## Final review details (owner, 2026-10-23)
| Priority | Detail | As built |
| --- | --- | --- |
| P0 | `N.A.` and non-numeric NAVs must not break the stream | Null and `NaN` read as floats and are excluded and counted with zero and negative NAVs; nothing raises |
| P1 | Plan-options without NAVs stay discoverable | Every plan-option at the revision is in the snapshot (40,213, of which 18,019 have no valid NAV); search finds them and their metrics are `NA` `no_nav` |
| P1 | `latest_revision` is live metadata | Excluded from the byte-identical guarantee; documented on the routes |
| P1 | Any change to computed results bumps `method_version` | Applied once: the real-data spot check fixed the option rule, so the method in use is v2 ([versions](../../current/mf-metrics.md#versions)) |

## Deviations from the plan below
- The read routes for funds (`/funds`, `/funds/{code}`, `/funds/{code}/navs`) live in the analytics context with the screener. Revision pinning resolves a snapshot first, and MF data must not depend on analytics. So `mf_data/application/reads.py` and `mf_data/interface/http.py` were not built; MF data publishes only the `MfReader` port and its adapter.
- The cursor carries the snapshot's revision, not its id. Under one method version the two keys are equal.
- The reader's array_agg fallback was not needed: the stream met the targets (82 s, 297 MB).

## Context
Slice 1 (`7c5c9d3`) loaded 22.27M current NAV rows (2016-10-16 → 2026-10-22, 40,213 plan-options, 22,397 with NAVs, ~8,800 reporting this month) and runs the 11:30 IST refresh. Nothing reads the data yet. The proposal covers methodology v1 (the pasted table) and the Slice 2 scope: a deterministic metric engine, the screening evaluator and read APIs. The UI is Slice 3, the agent Slice 4. Goal: make the 22.27M rows usable for screening, comparison and research, with every number reproducible from (data_revision, method_version).

Governing rules: ADR-017 MF-3 (curated links, never inferred), MF-8 (flag treatment is methodology), MF-11 (snapshot per revision × method_version; reads use snapshots and NAV ranges only), MF-12 (ADR-018 evaluator: filter tree, NM/NA, tie-break by id, field registry, `wickstreet` analytics context), MF-13 (`derived_metrics` before snapshots, `display` at read); ADR-018 (in-memory evaluator, no SQL builder, `GET /screener/fields`, ≤2 levels, a condition on NM/NA is false, excluded-for-missing counts); doc 06 for the request/response shape; ADR-022 L68 (results carry source, as_of, data_revision, method_version).

Facts checked: `display` and `derived_metrics` grants exist for `amfi` (ids 3, 4) and `tigzig` (8, 9). No evaluator or registry exists anywhere to reuse (Momentum25's rule registry is a pattern only; the independence contract bars imports). `numpy` is installed but Momentum25's domain doesn't use it, so the engine is pure Python with `math.fsum`. AMFI's master file itself sets closure date = launch date on 617 rows, so `closure_date` is not used for activity.

## Methodology v1 (`METHOD_VERSION = 1`, proposed)
- **Observations:** current NAV rows at the snapshot revision. Valid = NAV > 0. Rows with null, zero or negative NAV are excluded and counted (`excluded_navs`). `nav_jump` rows are kept and counted (`jump_flags`).
- **As-of D:** the latest NAV date in the store. **End anchor e:** the fund's last valid NAV on or before D. `active` = D − e ≤ 7 days.
- **Offsets:** calendar months back, day clamped to month end (1Y = 12 months). **Start anchor:** the last valid NAV on or before the target date, and no more than 7 days before it (`MAX_GAP_DAYS = 7`).
- **Trailing returns** (anchored at D): `ret_1m/3m/6m/1y` = e/s − 1. `cagr_3y/5y/10y` = (e/s)^(365.25/days) − 1, with days = calendar days between the two anchors.
- **Since the first valid NAV:**
  - **Start:** the first NAV > 0 (`since_start`). A zero or null opening row is skipped, never used.
  - **End:** e (`since_end`).
  - **Metrics:** `ret_since` and `cagr_since` (needs ≥ 365 days). Both dates go out with the values.
  - **Label:** "since <since_start>, first stored valid NAV, not inception". Never called since-inception.
- **Anchor dates are exposed:** each trailing return also stores the start-anchor date it used. The metrics endpoint returns those dates; they are not screen fields.
- **Rolling 1Y/3Y/5Y** over the full stored history up to e: one annualised point at every valid date t that has a valid start anchor. Summary per window: `count`, `mean`, `median`, `min`, `max`, `positive_share`.
- **Volatility** `vol_1y/3y`: sample standard deviation (n − 1) of simple returns between consecutive valid NAVs in [s, e], × √252.
- **Max drawdown** `mdd_1y/3y/since`: min(NAV_t / running peak − 1), always ≤ 0.
- **States:** a missing value is `NA` or `NM` with a reason. Nothing defaults to 0.
  - `NA` reasons: `no_recent_nav` (inactive fund, trailing metrics only), `history_too_short`, `gap_at_start`.
  - `NM` reason: `gap_in_window` (two valid NAVs more than 7 days apart inside a volatility or drawdown window; it is unreliable after exclusions).
- **Precision:** IEEE double, no intermediate rounding, full precision stored and returned; rounding happens only for display.
- **IDCW:** `option` is classified from the plan-option part of the name, never from the fund name.
  - **Option text:** first, AMFI's listing `option` column, when present and normalised. Otherwise, the NAV name with the scheme-name prefix removed. If the two names are equal (TigZig), use the segments after the scheme name's last " - ".
  - **Fund-name phrases** are removed before matching ("Dividend Yield", "Growth Fund", "Income Fund", …). So "X Dividend Yield Fund - Direct - Growth" is `growth`.
  - **Order:** IDCW/dividend/payout/reinvest/income distribution → `idcw`; bonus → `bonus`; growth/cumulative → `growth`; anything else → `unknown`.
  - **Return basis:** if option ≠ growth, `return_basis = nav_excluding_payouts`, and every response carries the caution "NAV return; excludes payouts; not a total return".
  - **Plan:** `direct` if the option text or name has the word "direct", else `regular`.
  - **Tests:** real-shaped name cases. A real-data report lists counts by option and every `idcw` name that contains "yield" or "growth", for a spot check.
- **Categories:** the canonical names are AMFI's SEBI open-ended labels, as AMFI writes them.
  - **Mapped:** a variant maps only when it names exactly one canonical category. That covers prefix variants such as "Equity Schemes - …", "Income/Debt Oriented Schemes - …" and "Open Ended Schemes ( … )" wrappers, and specific TigZig labels such as Liquid, ELSS and Money Market.
  - **Unclassified:** generic or ambiguous labels: Income, Growth, Balanced, Gilt, and FoF or index labels whose target category is not unique.
  - The raw label is kept as `source_category`. `asset_class` comes from the canonical prefix.
  - Every mapping decision is listed in the method doc, and a test guards each one.
- **Known limits (documented):**
  - √252 understates volatility for funds that publish a NAV every calendar day (liquid, overnight).
  - Categories are as of 2026-10-23, because AMFI restates current labels.
  - No TRI, TER, AUM or risk-free series, so there is no Sharpe, beta or tracking error (MF-14).
  - Series are not spliced across links in v1.

## Design
**New context `wickstreet.analytics`** (domain / application / infrastructure / interface). Add it to `containers` in `backend/pyproject.toml`.
- `analytics/domain/metrics.py`: constants, `Value`/state type, `compute_fund(series, as_of) -> FundMetrics` (pure functions, one per formula).
- `analytics/domain/classify.py`: `plan_of`, `option_of`, `canonical_category`, `asset_class`, and the alias table.
- `analytics/domain/fields.py`: the field registry, generated from the metric definitions. Each field has id, label, group, type (number/boolean/enum/date), unit, description and formula. `registry_version()` is a SHA-256 of the registry.
- `analytics/domain/screening.py`:
  - `parse_filter(json, registry)` raises `FilterError(path, message)` for an unknown field, a wrong type or operator, or depth > 2.
  - Operators: `> >= < <= = != between in not_in is_available is_missing`.
  - Every comparison operator is false on NM/NA, including `!=` and `not_in`.
  - The two state operators test the state directly: `is_missing` is true exactly on NM/NA, and `is_available` is true exactly on a value. A test covers this for every operator.
  - Evaluation counts excluded-for-missing per condition path, with reasons. A row excluded by `is_available` is counted; a row matched by `is_missing` is not.
  - Sort puts missing values last and ends with `plan_option_id`.
  - **Cursor:** encodes `snapshot_id`, a request fingerprint (SHA-256 of the canonical filter + sort JSON) and the offset. A cursor from another snapshot or request gives 422 "cursor does not match this request".
- `analytics/domain/snapshot.py`: the `Snapshot` model; deterministic JSON encode/decode (sorted keys, gzip `mtime=0`, SHA-256 of the JSON); `rebase(series, start)` for comparison.
- `analytics/application/`:
  - `ComputeSnapshot(reader, snapshots, rights)`: reads the pointer revision. It is a no-op if a (revision, METHOD_VERSION) snapshot exists. Otherwise it requires `DERIVED_METRICS` for each NAV source, streams the funds, computes, and inserts.
  - `Research(snapshots, reader, rights)`: `fields()`, `run_screen(req)`, `fund_metrics(code)`, `compare(codes, start)`. Each one requires `DISPLAY` for every source in the snapshot or series. The rights checks sit here, not in HTTP, so Slice 4 agent tools inherit them.
- `analytics/infrastructure/tables.py`: `metric_snapshot` (id, revision_id, method_version, as_of, funds, sources text[], grant_ids bigint[], payload_sha256, payload bytea, created_at; unique (revision_id, method_version)).
- `analytics/infrastructure/snapshots.py`: `SqlSnapshotStore` (insert ON CONFLICT DO NOTHING, `latest(method_version)`, `load(id)` with a small in-process cache keyed by id; MF-11 says these keys never need invalidation). Add `# ponytail:` notes: every snapshot is kept (~2 MB/day compressed; prune later, since a snapshot is a cache), and there is no Redis.
- `analytics/interface/http.py`: `GET /screener/fields`, `POST /screener/run`, `GET /funds/{code}/metrics`, `GET /compare?code=…&start=` (2–5 codes; metrics plus rebased series at 100). `FilterError` → 422 with the node path.

**mf_data additions:**
- `mf_data/domain/reads.py`: the read contract mf_data publishes: `FundSeries`, `FundRecord`, `NavPoint`, `Link`, and the `MfReader` protocol. Analytics consumes it; mf_data never imports analytics.
- `mf_data/infrastructure/reader.py`: `SqlMfReader`.
  - `history()` opens one REPEATABLE READ read-only transaction and reads the pointer revision R and the NAV sources.
  - It streams ordered rows `SELECT plan_option_id, nav_date, nav::float8, anomaly … WHERE superseded_revision IS NULL ORDER BY plan_option_id, nav_date` through a server-side cursor (`connection.stream()` with `yield_per`). It groups the rows in Python, one fund at a time, so memory holds one fund's series plus the finished per-fund results. Attributes come from the master rows visible at R, read in the same transaction.
  - **Fallback**, only if the benchmark misses its target: three separate `array_agg(x ORDER BY nav_date)` columns per plan-option.
  - Every other read takes an explicit revision R and applies the MF-5 visibility rule (`revision_id ≤ R AND (superseded_revision IS NULL OR superseded_revision > R)`). These are `search(q, limit, R)` (name / code / ISIN), `fund(code, R)`, `navs(code, start, end, R)` (with source and revision per row, NAV as the filed string) and `links(id)`.
- `mf_data/application/reads.py`: `FundReads(reader, rights)` with `DISPLAY` checks.
- `mf_data/interface/http.py`: `GET /funds?q=`, `GET /funds/{code}`, `GET /funds/{code}/navs?start=&end=`.
- `plan_option_link` table (MF-3): from, to, kind (merger | code_change | segregated_portfolio), effective_date, evidence, recorded_by, created_at. The owner login writes it; the app role only reads it. CLI: `mf link add|list`. Fund detail shows links. v1 metrics never splice across them.

**Migration `0003_mf_analytics`:**
- Creates `metric_snapshot` (app: SELECT, INSERT) and `plan_option_link` (app: SELECT).
- `env.py` imports the analytics tables.
- `tests/wickstreet/test_schema_rules.py`: add both tables to `SHARED_REFERENCE_TABLES` and bump the head check.

**Composition:**
- `wickstreet/wiring.py`: `build_analytics(settings, database)` returns `Analytics(compute, research, reads)`.
- `wickstreet/app.py`:
  - put a `RightsGate` and the analytics object on `app.state`;
  - include both routers;
  - add problem+json handlers (HTTPException, RequestValidationError, `RightsDeniedError` → 403 `urn:wickstreet:error:rights-denied`) using `platform_common.http.problem_response`;
  - the scheduler `job()` becomes "refresh if due, then compute". The compute step is a no-op when the snapshot is current, and a compute failure is logged and isolated. Startup always calls `run_now()`: it refreshes only when the 11:30 slot is due, and always brings the snapshot up to the pointer.
- **Other publication paths:** in `wickstreet/cli.py`, `_ingest` (used by backfill, archive, reparse and refresh) runs compute after any summary that published something. Reparse corrections and manual publishes therefore produce a new snapshot.
- **Staleness is never silent:** every analytics response carries `data_revision` (the snapshot) and `latest_revision` (the pointer). A test covers both.
- `wickstreet/dependencies.py` gains the dependencies the routes use.
- `wickstreet/cli.py` gains `mf metrics` (compute now; print outcome, time, peak RSS and state counts) and `mf link add|list`.

**Revision pinning:**
- Every read resolves one revision R: the request's optional `data_revision`, which must have a v1 snapshot, or else the latest v1 snapshot's revision.
- Metrics, screens, comparisons, fund detail, search and NAV ranges all read at that R. The NAV and attribute reads use the MF-5 visibility rule, so a compare chart and its metrics always come from the same data even while a refresh publishes.
- Pagination is pinned through the cursor's snapshot id.
- Every response carries `data_revision`, `latest_revision`, `method_version`, `as_of` and `sources`. Same request + revision + method ⇒ byte-identical JSON.

**Performance (the acceptance test):**
- Bounded memory: one fund's series at a time.
- Rolling windows use a forward-moving anchor pointer, O(n) per window, because the target dates only increase. Medians use one sort per window.
- Volatility and drawdown take one pass each, with `math.fsum`.
- In memory, the snapshot keeps per-fund values as tuples in registry order, with states only for missing values.
- Targets on the real 22.27M rows: compute ≤ 5 min wall time and ≤ 1 GB peak RSS; snapshot load ≤ 2 s; screen evaluation ≤ 100 ms at ~22.4k rows. All are measured and reported. If a target is missed, optimise before commit (the array_agg fallback, then profiling).

## Tests (synthetic only in CI)
- `tests/wickstreet/test_mf_metrics.py` (pure):
  - golden values for each formula (hand-computed small series), anchor tolerance, month-end clamping (e.g. 31 Mar → 28/29 Feb);
  - every NA/NM reason; exclusion of zero/missing; jump rows kept and counted;
  - rolling median with an even count; the classifier and category alias cases; deterministic encode (same bytes twice).
- `tests/wickstreet/test_mf_screening.py` (pure):
  - every operator × type; NM/NA false for every operator; excluded-for-missing counts and reasons;
  - depth / unknown field / wrong type → path errors; missing last in sort, id tie-break;
  - `is_missing` is true on NM and NA, and `is_available` is false on them;
  - cursor paging stays on its snapshot after a new snapshot lands; a cursor reused with a changed filter or sort → 422.
- The integration tests also cover:
  - a reparse-style correction published through the CLI path gives a new snapshot;
  - a request pinned to the older `data_revision` still returns the old NAV and metric values, and `latest_revision` shows the newer pointer;
  - a zero or null opening NAV is skipped for `since_start`.
- `tests/wickstreet/test_mf_analytics.py` (DB, as `wickstreet_app`, reusing `FakeSource`, `Pipeline`, the grant fixtures and `amfi_files`):
  - compute after publish; no-op on the same revision; new snapshot after a new revision; no snapshot when `derived_metrics` is denied;
  - every endpoint through `TestClient`; 403 problem+json when `display` is denied; provenance per NAV row; link shown on detail; byte-identical screen responses.
- `tests/wickstreet/test_mf_real_data.py`: opt-in, skipped unless `WICKSTREET_REAL_DATA_URL` is set; read-only.
  - Recomputes `ret_1y`, `cagr_3y` and `cagr_5y` for 50 md5-sampled active funds with independent SQL anchor lookups, and compares them to the snapshot within 1e-12 relative.
  - Checks invariants over the whole snapshot (finite values, mdd ∈ [−1, 0], vol ≥ 0, min ≤ median ≤ max, share ∈ [0, 1], reasons from the known set).
  - Recomputes the payload and asserts its SHA-256 equals the stored one (determinism on real data).
  - Reads one fund's NAVs and metrics at a pinned older revision and checks they match each other.
  - Records compute wall time and peak RSS against the targets above.

## Execution order
1. Start dashboard-builder (CLAUDE.md standing rule) and update it after each step.
2. Domain metrics + classifier + tests. Then build the category alias table from the real distinct labels (read-only query) and record each decision.
3. Registry + screening evaluator + tests.
4. Reader, migration 0003, snapshot store, ComputeSnapshot, CLI `mf metrics`. Integration tests.
5. Application read services, routers, error handlers, rights checks. API tests.
6. Links table + CLI + detail.
7. Real data:
   - apply 0003 (additive) with the owner URL;
   - run `mf metrics` and record time, funds, active count, state counts per field and the share of active funds classified;
   - run the opt-in real-data test;
   - smoke-test the API (fields; a screen such as active direct growth large-cap with cagr_5y ≥ 0.12 sorted desc; one fund's metrics; compare 3 funds; NAVs with provenance);
   - rebuild the API container so the 11:30 job computes snapshots.
8. Full suite + `ruff check` (new files formatted only) + mypy + `lint-imports`. Re-run the tests after any auto-fix.
9. Docs:
   - `docs/current/mf-metrics-v1.md` (the method spec, category decisions and limits);
   - ADR-023 U12 row (owner approval of method v1, 2026-10-23);
   - architecture.md Slice 2 section, state.md row, backend README commands;
   - memory.
10. Commit locally; do not push.

## Review corrections applied (review of 2026-10-23)
| Finding | Where fixed |
| --- | --- |
| `is_missing` vs NM/NA | Screening operators: the state operators test the state, and comparisons stay false |
| Cost over 22.27M rows | Performance section: streaming, O(n) rolling, measured targets |
| Consistency across refreshes | Revision pinning for every read, and the cursor pins its snapshot |
| IDCW misclassified on fund names | IDCW rule: option text only, fund-name phrases removed first |
| Cursor without a request fingerprint | Cursor = snapshot id + request SHA-256 + offset |
| Invalid `array_agg` syntax | Reader streams ordered rows through a server-side cursor; three `array_agg` columns as a fallback |
| Other publication paths | `_ingest` computes after any publish; startup `run_now()`; `latest_revision` exposed |
| Ambiguous labels such as FoF | Category rule: only labels with exactly one target map |
| Invalid opening NAV for since-metrics | `since_start` = first valid NAV; start and end dates exposed |

## Out of scope (named so nothing is half-built)
- Saved research (tenant-owned, RLS): Slice 3, with the UI.
- `top_pct`/`bottom_pct` operators and per-row condition explanations: when the UI or agent needs them.
- Point-in-time screens at past dates.
- Category-relative ranks.
- Splicing across links.
- Snapshot pruning.

## Verification (end to end)
- `M25_DATABASE_URL=<test-infra url> uv run pytest tests/wickstreet` then the full backend suite; ruff, mypy, `lint-imports` clean.
- `set -a; . <scratch>/wickstreet.env; uv run wickstreet mf metrics` prints the snapshot (revision 2769+, ~22.4k funds, ~8.8k active).
- `WICKSTREET_REAL_DATA_URL=… uv run pytest tests/wickstreet/test_mf_real_data.py` passes.
- `curl` against the rebuilt container at `/api/v1/mf/screener/fields`, `/screener/run`, `/funds/{code}`, `/funds/{code}/navs`, `/funds/{code}/metrics` and `/compare` return 200 with `data_revision` and `method_version`. The same POST twice gives identical bytes.
- The completion report covers ingested coverage, metric state counts, the classification share, timings, test results and the remaining gaps.
