# Wickstreet 2.0

> Part of the [Wickstreet 2.0 blueprint](README.md). **Approved by the owner on 2026-10-22 for Stage A (W0–W1) only**, with amendments 1–5 incorporated. Stages B and C, real-data import, push and deploy are not authorised.

## Context

The Wickstreet 2.0 blueprint (commit `de02a57`: `docs/plans/wickstreet-2/`, ADD Amendment A2, ADR-016 to ADR-021, all Proposed) adds company intelligence, a unified screener, funds and ETFs, holdings intelligence and portfolio intelligence to the existing chart workstation.

The owner's review (2026-10-22) approved the **direction**. It asked for **staged authorisation** and five corrections:

1. Keep engineering readiness and data readiness separate.
2. Isolate Momentum25 run identity rigorously.
3. Make point in time a platform invariant, with estimated dates always visible as estimates.
4. Specify portfolio accounting before W5.
5. Integrate everything into the TradingView-style workspace rather than building separate apps.

It recommends authorising Gate 0, W0 and the W1 vertical slice, then a review of that slice before W2–W5 are committed.

This revision does that. Stage A is specified to execution detail. Stages B and C stay outlined until the slice review passes.

**Unchanged constraints:**
- Momentum25 methodology, strategy files, `strategy_id=30` and the API contracts do not change (NFR-13).
- The sealed hold-out stays unread.
- No push, no deploy.
- No real-data import without a recorded supplier and rights decision.
- No repository change until the Gate 0 decisions for that stage are recorded.

---

## Platform invariants (apply to every stage)

### I-1 Two readiness gates per capability
- **Engineering-complete:** built and accepted on synthetic fixtures. The dashboard and docs say "engineering-complete, no licensed data". No screen claims coverage.
- **Data-ready:** a supplier is recorded, and the rights are confirmed explicitly in writing:
  - storage, retention and history depth;
  - automated retrieval;
  - use in historical evaluation (the NSE "simulation" clause);
  - display;
  - redistribution, including the self-hosted user case.

  After that, real data is imported, reconciled and reviewed.
- **Rights register, checked per use (amendment 4).** A new file, `docs/operations/data-rights.md`, has a machine-readable twin, `docs/operations/data-rights.json`, loaded at startup like the strategy files. One row per (dataset, source). Each row holds five separate permissions, each `yes`/`no`/`unknown`, plus the document, the date and the owner's sign-off: `store`, `display`, `historical_evaluation`, `automated_retrieval`, `redistribution`. Each code path declares the use it needs, and a permission never implies another:
  - an import needs `store`;
  - research pages and API reads need `display`;
  - historical screens, `as_of` reads, Studio and any evaluation need `historical_evaluation`;
  - a fetcher needs `automated_retrieval`;
  - CSV export and anything leaving the instance need `redistribution`.

  A read that lacks a permission excludes those rows. The value becomes `NA (source not licensed for <use>)`. It never falls back to another source silently. Tests: for each use, a row that has every other permission but not this one is refused.
- **Synthetic exemption is narrow (amendment 1).** `synthetic` passes the register only when both of these hold:
  - the process runs with `M25_ENV` set to `test` or `development`; the default and production values refuse it;
  - the file's SHA-256 appears in the committed fixture manifest, `backend/tests/fixtures/w2/MANIFEST.sha256`.

  Any other file labelled `synthetic` is refused. Synthetic rows carry `provenance = synthetic` and never enter production universes or production runs. Guard tests: the default settings refuse a fixture; a test setting refuses an unlisted file; a listed fixture is accepted only in test or development.

### I-2 Momentum25 run-identity isolation
Verified in code: `current_revision()` (`infrastructure/persistence/point_in_time.py:43`) takes the maximum over **`ALL_VERSIONED`** (`infrastructure/persistence/history.py:57`). `DataManifest.identity()` (`domain/value_objects/manifest.py`) hashes that revision. So if a new versioned table joined `ALL_VERSIONED`, every fundamentals import would give the next Momentum25 run a new `data_version` on unchanged market data. That is the R3-U-09 duplicate-snapshot defect again.

The fix:
- New tables use the same `Versioned` mixin and the same `data_revision_seq`, so revisions stay globally ordered. They register in a **separate set, `REFERENCE_VERSIONED`**, with its own `current_reference_revision()`. `ALL_VERSIONED` stays unchanged.
- `DataManifest` gains an **optional** `reference` block: `{reference_revision, metric_version}`. The block enters `identity()` **only when present**. A consumer attaches it only if it reads the metric engine or reference data (a screen, a scorecard, a Studio strategy with a fundamental rule). A Momentum25-only manifest is byte-identical to today's.
- `METRIC_VERSION` lives in that block, **not** in the engine block. So `engine_identity` and the RS cache key (`application/services/rs_ratings.py:72`) never move because of metric work.
- **Reference snapshot semantics (amendment 3).** A read at `as_of` D captures the reference revision R at request time (`current_reference_revision()`, the same committed-row rule as `current_revision()`). It serves only rows visible at revision R **and** with `available_at ≤ D`. Each (D, R) pair is a reproducible snapshot:
  - the reference block `{reference_revision: R, metric_version}` is stored in `data_manifests`;
  - the snapshot cache key is `(asset_class, D, market data_version, R, METRIC_VERSION)`;
  - replaying with the stored R rebuilds the same rows even after later imports;
  - a later import, even a backfill of an old filing, gives a new R and so a new key. It is never served under the old key.

  Tests: run a historical screen, import a backfilled filing that was available before D, then (1) replay with the old R and get identical bytes, (2) issue a new request and get a new R and key, (3) confirm the Momentum25 manifest is unchanged.
- This amends an accepted ADR, so it becomes **ADR-014 §13**, and it needs owner approval (Gate 0).
- **Golden tests:**
  - (a) every stored `data_manifests` body re-hashes to its stored key;
  - (b) on the fixture DB, capture the Momentum25 manifest, import fundamentals, capture again: identical `data_version`, `market_data_version`, `engine_identity`;
  - (c) a manifest with the `reference` block has a different key, and it changes when only reference data changes;
  - (d) the RS cache key is unchanged;
  - (e) a full production-strategy screen before and after the W0/W1 migrations gives byte-identical results and reuses the same run.

### I-3 Point in time as a platform invariant
- Every source fact carries `available_at` and **`availability_basis`**: `recorded` (exchange or AMC receipt time, or our own capture time) or `estimated` (statutory deadline: +45/+60 days for results, +10/+5 days for disclosures).
- An `estimated` row always has provenance `reconstructed`. The UI shows "estimated availability" wherever it is used. A result that reads one carries "Incomplete historical provenance" (ADR-014 §7 wording). An Out-of-Sample Evaluation whose window is mostly estimated cannot run (the existing ADR-014 rule).
- **Estimates never count as verified (amendment 2).**
  - `availability_basis` is carried per value through `MetricValue.inputs` up to the API. Provenance summaries count `recorded` and `estimated` separately.
  - The words "verified", "point-in-time correct" and "recorded" are never applied to a result with any estimated input.
  - No code path upgrades a row from `estimated` to `recorded`. Only a new import with receipt-time evidence can, as a superseding row whose `source_ref` names the evidence.
  - A reader option `require_recorded=True` excludes estimated rows as `NA (availability estimated)`. Every path whose label claims verified history uses it, and so will the W2 historical-screen "recorded only" toggle.
  - Tests: a summary with one estimated input never reports verified; `require_recorded` excludes it; no update statement changes `availability_basis`.
- **One shared look-ahead harness** (`backend/tests/pit/`) runs the same scenario against every point-in-time reader:
  - publish a fact at T+1 and assert it is invisible at T;
  - restate at T+2 and assert the original is shown at T+1;
  - read past the cutoff and assert `LookAheadError`.

  Fundamentals use it in W1. Holdings, screening and scorecards plug into the same harness later. A reader cannot merge without it.
- ADR-016 and ADR-017 are amended in place (still Proposed) to name `availability_basis`.

### I-4 Portfolio accounting (spec before any W5 code)
W5 starts with **W5-0, an accounting specification** (an ADR-019 revision) that defines:
- **Cash:** an optional cash account per portfolio. When it is tracked, buys debit it and sells, dividends and redemptions credit it. When it is not tracked, those are external flows.
- **Charges:** brokerage, STT, stamp duty and exchange fees add to cost on a buy and reduce proceeds on a sell.
- **Dividends and IDCW:** income on the pay date, with the ex-date recorded. Reinvested IDCW is a buy.
- **Corporate actions:** split and bonus scale units and keep total cost. Rights is a new buy. Merger and demerger change quantity and split cost only from an owner-supplied ratio file with evidence, never inferred (the R3-B-31 rule).
- **Transfers** between portfolios or demat accounts keep the original cost and date. They are not sales.
- **MF switches** are a redemption plus a purchase on the same date.
- **Missing prices:** the last known price, with "stale since D". Never zero. The position is flagged, and the portfolio return states its stale share.
- **Period reconciliation (amendment 5; replaces the earlier equation, which double-counted charges).** For a period [t₀, t₁]:

  `V₁ − V₀ = F + I − E + R + ΔU`

  - **V** = market value of open positions, plus cash when cash is tracked.
  - **F** = net external flows: deposits − withdrawals when cash is tracked. When cash is not tracked, F = buy costs − net sale proceeds − I + E (the implied flows).
  - **I** = income received: dividends, interest, IDCW paid out. Reinvested IDCW counts as I and also as a buy, so it is not a net flow.
  - **E** = expenses **not** attributed to a trade (account and DP fees).
  - **Trade charges are capitalised:** a buy's cost includes its charges, and a sale's net proceeds are after charges. So they appear only inside R and ΔU, never in E.
  - **R** = Σ (net sale proceeds − FIFO cost of the lots sold).
  - **ΔU** = U₁ − U₀, with U = Σ (market value − remaining cost) over open lots.
  - **Corporate actions** (split, bonus) are zero-flow events: units change, cost is conserved, and V moves only through ΔU.
  - **Transfers** are external flows at market value on the transfer date. Each lot keeps two bases: *tax cost* (original cost and date) and *performance cost* (market value at transfer-in). R and ΔU in the identity use performance cost, so gains made before the transfer never count as this portfolio's P&L.

  W5-0 writes the proof and the edge cases. Tests, to the paisa: the identity on random ledgers (property test); unit conservation across actions; cost conservation across split and bonus; cash = Σ cash flows; one golden ledger per event type.
- **Reconciliation:** imported closing units per holding match the CAS or broker statement closing balance. Mismatches are listed and nothing is adjusted silently.

### I-5 One workspace, not six apps
- Every new page renders inside `WorkstationShell` with the same header, search, dock and theme tokens (`--ws-*`).
- **Dock tabs** extend `PANEL_TABS` (`web/src/components/workspace/SidePanel.tsx:28`): `fundamentals` (W1) and `heldby` (W4). They are filtered by the current symbol's instrument type, as `details` is filtered at `WorkstationShell.tsx:58`.
- The chart's context menu (`PriceChart.tsx`) gains "Company overview" and "Financials". Search results open the company page or the chart, as today (`WorkstationShell.tsx:219`).
- **Acceptance criterion for every capability** (new Playwright spec `web/e2e/workspace-integration.spec.ts`):
  - from `/chart/:symbol`, the user reaches the capability in at most 2 interactions;
  - returning restores the same layout, interval, drawings and replay `as_of`;
  - the existing chart, screener, Studio and alert specs pass unchanged;
  - NFR-11 still holds;
  - the keyboard map adds only Alt+C.

---

## Gate 0 — decisions for Stage A only

| # | Decision | Needed for |
|---|---|---|
| G-1 | Accept ADD A2 **for W0–W1 only** | Any code |
| G-2 | Accept ADR-016 (with I-3 wording) and ADR-021 (with the I-1 rights register) | W0, W1 |
| G-3 | Approve **ADR-014 §13** (I-2: separate reference revision, optional manifest block) | W0 |
| G-4 | Approve the metric dictionary, blueprint 03 §1.4, as methodology v1 | W1.5+ |
| G-5 | Watch-point thresholds (03 §1.6) — or defer increment 1.7 | W1.7 |

A supplier is **not** needed for Stage A engineering-complete. It is needed for W1 data-ready (I-1).

**Recorded 2026-10-22 by the owner: G-1, G-2, G-3, G-4, G-5 all approved. Revision 2 approved for Stage A (W0–W1) only, with amendments 1–5 above incorporated (amendment 5 lands in W5-0 before any Stage C code).** Every increment preserves existing Momentum25 behaviour, strategy identities, historical runs and workspace capabilities. Stage A is authorised to engineering-complete on synthetic fixtures. Not authorised: Stages B and C, any real-data import (no supplier recorded), push, deploy.

**First execution steps on approval of this plan:**
1. Commit this plan as `docs/plans/wickstreet-2/11-wickstreet-2.0.md` and record the Gate 0 decisions in it. Mark A2 "Accepted for W0–W1". Mark ADR-016, ADR-021 and ADR-014 §13 Accepted, with the I-1 and I-3 amendments. Mark the 03 §1.4 metric dictionary and the §1.6 thresholds "approved v1".
2. Update the dashboard: Stage A in progress; W2–W5 shown as gated.
3. W0.1 → W0.7, then W1.1 → W1.7. One local commit per step, with verification each time.
4. Stop at the slice review gate and report.

---

## Stage A — W0 foundation and the W1 vertical slice (authorise now)

### W0 — Shared foundation
| Step | Build | Files |
|---|---|---|
| 0.1 | ADR-014 §13 text; ADR-016/021 amendments (I-1, I-3) | `docs/architecture/adr/` |
| 0.2 | `REFERENCE_VERSIONED` set + `current_reference_revision()`; optional `reference` block in `DataManifest` (schema stays 3; block omitted when absent); golden tests (a)–(e) | `infrastructure/persistence/history.py`, `point_in_time.py`, `domain/value_objects/manifest.py`, `repositories/data_manifests.py` |
| 0.3 | `MetricValue(value, state, reason, inputs)`; `METRIC_VERSION` | `domain/value_objects/metric.py`, `domain/engine_version.py` (constant only) |
| 0.4 | Import framework: parse → validate → preview → commit; `file_sha256`; per-use rights check against `data-rights.json`; narrow synthetic exemption (`M25_ENV` + fixture manifest); `availability_basis` required; `require_recorded` reader option. Modelled on `application/use_cases/import_market_data.py`; CLI next to `import-eod` in `interface/cli/main.py` | `application/use_cases/imports/`, `infrastructure/importers/` |
| 0.5 | Shared PIT harness (I-3) | `backend/tests/pit/` |
| 0.6 | Synthetic fixtures: general, bank and NBFC companies with a restatement, one `estimated` and one `recorded` filing | `backend/tests/fixtures/w2/` |
| 0.7 | `lint-imports` contract: new domain packages reach `domain.engines` only through `domain.ports`; `docs/operations/data-rights.md` skeleton | `backend/pyproject.toml` |

### W1 — Company Intelligence vertical slice
**Reuse:** `Versioned` + `history_table`/`install_on_create` (`history.py`), the `PointInTimeSource` pattern and `LookAheadError` (`point_in_time.py`, `domain/errors.py`), `IdentityLinks` (`domain/identity.py`), the `/stock/:symbol` route, `AssessmentPanel`, `safeReturnPath` (`web/src/lib/return-path.ts`).

| Inc. | Build |
|---|---|
| 1.1 | Migration 0026: `companies`, `company_names`, `classification_*`, `securities.company_id` (additive). `import-classification`. Company header on `/stock/:symbol` |
| 1.2 | Migration 0027: `financial_filings` (with `available_at`, `availability_basis`), `financial_facts`, `line_items` (4 templates seeded from code). `import-financials` (`financials-v1`) with reconciliation (blueprint 05 §9) |
| 1.3 | `PointInTimeFundamentals` on the shared harness |
| 1.4 | Financials tab: grid, basis and period switch, restatement markers, "estimated availability" markers, as-of banner. `GET /companies/{symbol}`, `/financials`, `/filings` |
| 1.5 | `share_count_observations` + `import-shares`; `MetricEngine` (03 §1.4); Overview metric strip; Ratios tab |
| 1.6 | Peers tab; `fundamentals` dock tab on `/chart`; chart context-menu entries (I-5) |
| 1.7 | Strengths/watch points (if G-5); `/data` fundamentals card; freshness entries in `GET /health/data-freshness` |

### Slice review gate (decides Stage B)
Shown to the owner on fixtures, with a report in `docs/audits/`:
1. **Import:** preview, commit, rejected rows, reconciliation flags, refusal of an unregistered source.
2. **Provenance:** every metric traces to filing, `available_at`, basis and estimated/recorded status.
3. **Historical correctness:** the harness is green; a restatement shows correctly before and after; replay `as_of` hides later filings.
4. **Identity:** golden tests (a)–(e) are green; production runs are unchanged.
5. **API:** the OpenAPI schema is regenerated in `web/src/lib/api-schema.ts`; contract tests pass.
6. **Interface:** I-5 spec green; screenshots in light and dark at 1440, 1024 and 390 px; keyboard and screen-reader checks.
7. **Performance (warm P95):** overview ≤ 300 ms, financials ≤ 300 ms, peers ≤ 500 ms.
8. **Tests:** backend, Vitest and Playwright fully green; metric golden file hand-checked.

---

## Stage B — after the slice review (outline; detail written then)

| Workstream | Scope | Extra gate |
|---|---|---|
| **W2 Unified screener** | `domain/screening/` registry, AST and evaluator; `POST /screener/run`; `SavedScreensV2`; presets; historical `as_of` | **Parity gate:** server rows equal `applyFilters` (`web/src/components/momentum25/screener.tsx:78`) for every V1 shape before deletion; determinism golden; the screener also lives in the chart's bottom panel (I-5) |
| **W3 Funds and ETFs** | `instrument_type`; schemes, plans, NAV; fund metrics; fund and ETF pages; fund and ETF screener tabs; mixed search | **RS stop gate:** ratings identical for every stored date, else the owner decides; metric parity with an independent spreadsheet to 1e-6; TRI never silently replaced |
| **W4 Holdings and overlap** | Disclosures with `availability_basis`; holdings tab; `heldby` dock tab; signature journey; overlap | Joins the shared PIT harness; journey spec restores context at every step |

W1→W2 is sequential. W3 can start after W0 in parallel with W1 if the owner approves A2 for W3 early.

## Stage C — W5, split into three deliveries

| Delivery | Scope | Gate |
|---|---|---|
| **W5-0** | Accounting specification (I-4) as an ADR-019 revision | Owner approval |
| **W5a** | Direct-equity portfolio: transactions, cash, charges, dividends, corporate actions, transfers, valuation, XIRR (bisection), CSV import with preview and undo. Real data allowed at once: the user's own data, and prices exist | Conservation and reconciliation tests; privacy tests (no outbound call; nothing in logs) |
| **W5b** | Funds and ETFs in the portfolio; CAS import; look-through (2 levels, unit replacement, named residuals); overlap; time-weighted drawdown; drift | Needs W3 and W4; look-through sums to value (property test) |
| **W5c** | Descriptive scorecards (ADR-020) | Owner approval of metric lists; stability check on in-sample data only; sanity cases |

**W6 Broader research** stays deferred. Each item needs its own data decision and plan.

---

## Verification (every increment)
1. `cd backend && uv run pytest`, with PostgreSQL from `scripts/test-infra.sh` (never tmpfs). Then `uv run mypy src`, `uv run ruff check src tests` (format new files only), `.venv/bin/lint-imports`.
2. Migrations on a fresh database: `alembic upgrade head`, then `alembic check`. Not the drifted dev DB.
3. `cd web && npm test && npm run lint && npm run build`.
4. Playwright against the `momentum25_e2e` clone (`make e2e-db`, explicit `E2E_DATABASE_URL`, never export `M25_DATABASE_URL`). Restore rewritten `audit-evidence/` files; never commit them.
5. Identity goldens (I-2) and the PIT harness (I-3) on every increment that touches persistence.
6. Update `docs/current/{capabilities,architecture,state}.md` in the same commit as the code. One local commit per increment. Dashboard update after each increment.

## Risks
| Risk | Mitigation |
|---|---|
| No lawful supplier | I-1: engineering-complete is honest about having no data; data-ready waits |
| Identity drift | I-2 separate revision set; goldens (a)–(e) |
| Estimated dates read as fact | I-3 `availability_basis`; visible labels; OOS refusal |
| Accounting errors | I-4 spec first; conservation and reconciliation tests |
| UX fragmentation | I-5 shell-only pages, dock tabs, the ≤ 2-interaction spec |
| Taxonomy mapping per supplier | One adapter per supplier into `financials-v1`; completeness test |
