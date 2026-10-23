# ADR-017: Mutual Funds, ETFs and Holdings Disclosures

**Status:** Proposed (2026-10-22). Part of the [Wickstreet 2.0 blueprint](../../plans/wickstreet-2/README.md). Requires [ADD Amendment A2](../ADD-amendment-A2.md).
**2.0 realignment:** Accepted 2026-10-23 (owner). Rules MF-1 to MF-14 (last section) are the MF data foundation for the `wickstreet` package under accepted [A3](../ADD-amendment-A3.md), [ADR-022](ADR-022-multilingual-research-agent.md) and [ADR-023](ADR-023-operating-modes.md). They rest on A3, not on A2. The original decision text stays as history; MF-1 says which points apply in 2.0.

## Context
ADD A1 §4 put non-equity assets out of scope. Wickstreet 2.0 makes mutual funds a first-class asset class and adds ETFs. A fund has schemes, plans and options with separate NAVs and costs. Its holdings are known only through periodic disclosures published days after the portfolio date. ETFs already appear in `securities` as if they were equities.

## Decision
1. **Instrument types are explicit.** `securities.instrument_type` (`EQUITY`, `ETF`, `REIT`, `INVIT`, `OTHER`). Only `EQUITY` enters the Momentum25 universe and RS ratings. The migration is gated by a golden test: RS ratings for every stored date stay identical.
2. **Fund model.** `amcs` → `fund_schemes` → `fund_plans` (one row per AMFI plan-option code). Category, benchmark and market-cap bucket are effective-dated (`classification_assignments`, `scheme_benchmarks`). An ETF plan links to its listed `security_id`.
3. **NAV store.** `nav_daily(plan_id, nav_date, nav)`, versioned. NAV for date *d* is known at *d* 23:00 IST. Returns use Growth options. IDCW returns need `fund_distributions`.
4. **Disclosures are snapshots.** `portfolio_disclosures` + `portfolio_holdings`, each with `portfolio_date` and `published_at`. A correction is a new disclosure that supersedes the old one.
5. **Point-in-time rule for holdings.** At *t*, a scheme's visible portfolio is the disclosure with the greatest `published_at ≤ t`. Never chosen by `portfolio_date` alone; never extrapolated backwards. Without a recorded publication time, `published_at` = portfolio date + 10 days (monthly/half-yearly) or + 5 days (fortnightly debt), labelled `reconstructed`.
6. **Benchmarks are TRI.** `benchmark_index_daily.kind` (`PRI`, `TRI`). Fund and ETF comparisons use TRI. A price index is shown only with an explicit "excludes dividends" warning.
7. **ETF metrics** are end-of-day: premium/discount from close and NAV; tracking difference and tracking error on SEBI's definition (annualised SD of daily return differences over one year). No iNAV, no spread.
8. **Formulas** (blueprint 03 §2.5) are owner-approved methodology under `METRIC_VERSION`.

## Consequences
- Fund research, holdings look-through and overlap become possible with honest dates.
- The database grows with NAV history; Growth options are imported by default.
- Disclosure parsing per AMC is costly unless a vendor normalizes it (ADR-021).

## Alternatives considered
- **Treat funds as securities:** rejected. Plans, options, NAV timing and disclosures do not fit, and it would pollute equity universes.
- **Use the latest holdings for all past dates:** rejected. It invents history.
- **Compare funds against price indices:** rejected as a silent default. It flatters every fund by the dividend yield.

## Wickstreet 2.0 realignment (Accepted 2026-10-23)

The decision above predates accepted A3 and ADR-023. It edits Momentum25's `securities` table, and it has no revision or publication model. ADR-023 §2.8 now puts MF in its own package and PostgreSQL schema. ADR-022 §2.12 sets the daily refresh. No accepted record yet defines scheme identity, revisions, corrections or publication. This section does. The text above stays as history.

| # | Rule |
|---|---|
| MF-1 | **Scope.** Points 2–6 and 8 apply inside the `wickstreet` MF schema. Points 1 and 7 (`securities.instrument_type`, ETF market metrics) move to Wickstreet 3.0, behind an explicit read contract. 2.0 changes no Momentum25 table. In 2.0 an ETF is an AMFI plan-option with a NAV, nothing more |
| MF-2 | **Identity.** AMC, scheme and plan-option use Wickstreet surrogate ids. The AMFI scheme code is the source key of one plan-option, unique per source. ISINs are effective-dated attributes, never keys: about 800 ISINs map to two codes ([17 §4](../../plans/wickstreet-2/17-mf-free-data-feasibility.md#4-data-quality-and-freshness-findings)). Plan and option come from a tested name parser with an exceptions table (ETFs) |
| MF-3 | **Links, never inferred.** Mergers, code changes and segregated portfolios are curated `plan_option_link` rows (from, to, kind, effective date, evidence). Code never infers a link from names or dates, which is the same rule as Momentum25 identity links. A series never splices across a link silently; linked history is shown only when labelled |
| MF-4 | **Effective-dated reference data.** Name, category, benchmark, riskometer, TER, managers and exit load are assignment rows with `effective_from`. History starts at the first stored snapshot; nothing earlier is invented |
| MF-5 | **Revisions.** One MF-owned revision sequence, separate from Momentum25's `data_revision_seq`. All MF fact rows are append-only and carry `revision_id` and `superseded_revision`. A row is visible at revision R when `revision_id ≤ R` and `superseded_revision` is null or > R. This is Momentum25's visibility rule, re-implemented in `wickstreet` without an import |
| MF-6 | **Atomic publication.** One ingestion run is one database transaction: stage, validate, write revision R, then move the single `published_revision` pointer to R. Any failure rolls the whole transaction back. A short separate transaction records the failed run; its raw files stay for diagnosis. Readers read at the pointer, and every result carries R as `data_revision`. A gated backfill covers the last 10 years ([ADR-023 U4](ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23)) as a series of window runs, each published atomically |
| MF-7 | **Corrections.** Each run re-reads the look-back window (ADR-022 §2.12). A changed value inserts a new row at R and sets `superseded_revision = R` on the old row. An unchanged value writes nothing. An unchanged source content hash is a no-op run with no new revision |
| MF-8 | **Validation.** Blocking checks fail the run: file schema, expected-scheme coverage below a threshold, duplicate keys, future-dated rows. Row anomalies (null, zero or negative NAV, day-over-day jumps, suspected unadjusted splits) are stored as filed, with an anomaly flag. How flagged rows enter metrics is methodology and needs owner approval. Thresholds are configuration, set from observed data |
| MF-9 | **Provenance.** Every fact row links to its ingestion run. The run records source, URL, fetch time, raw-file SHA-256, adapter version and the rights record it ran under (ADR-021 rule 4). Raw files never enter the repository, CI or fixtures (ADR-022 §2.11) |
| MF-10 | **The run record is the "durable job".** `ingestion_run` is unique on (source, dataset, business date) and holds status and checkpoint. A PostgreSQL advisory lock lets one runner execute at a time, in any number of processes. At startup the app runs a missed 11:30 slot once. The same application use case serves the scheduler and a CLI command. Phase 1 needs no job queue or worker |
| MF-11 | **Storage and query plan.** NAV is one table keyed by (plan_option, nav_date, revision_id), NUMERIC values, with a partial index on current rows. The 10-year history, roughly 20 million rows, fits one PostgreSQL table. Partitioning or TimescaleDB waits for measured need (A3 §7.3). After each publish, a deterministic step computes metrics once per (revision, `method_version`) into `metric_snapshot`. Screens, comparisons and agent tools read snapshots and NAV ranges, never an upstream source. Cache keys include revision and method version, so caches never need invalidation |
| MF-12 | **Screening.** [ADR-018](ADR-018-unified-screening.md)'s evaluator rules (filter tree, `NM`/`NA` semantics, tie-break by id, field registry) apply to MF only, inside the `wickstreet` analytics context. The universe is about 8,300 active plan-options, not 1,600. One filter-tree contract serves the workstation, the API and the agent (`funds.search`, `ui.apply`), so the agent builds exactly the screen a user could build (SC-3). Unifying with stocks is 3.0 work |
| MF-13 | **Rights checkpoints.** The rights gate is asked before fetch (`automated_retrieval`), before write (`storage`), at read (`display`), before snapshots (`derived_metrics`) and before any model payload (`ai_processing_*`, ADR-022 §2.8). The adapter applies `amfi.personal_scope`. Unknown means denied |
| MF-14 | **In Wickstreet 2.0 (owner decision, 2026-10-23; replaces "not in Phase 1").** Holdings (points 4–5), TRI series (point 6), TER, AUM and scheme profiles belong to 2.0 ([ADR-023 U13](ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23), [doc 20](../../plans/wickstreet-2/20-wickstreet-2.0-complete-mf-scope.md)). Each dataset enters through an import contract and the rights register, as NAVs did. A price index is never used silently in place of a TRI (03 §2.5 benchmark rule) |
