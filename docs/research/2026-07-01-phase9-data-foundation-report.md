# Phase 9 — Institutional Research Data Foundation

**Date:** 2026-07-01
**Milestone:** Phase 9 (per user prompt), continuing the approved Data Foundation plan
(`/Users/varunagarwal/.claude/plans/rustling-tinkering-pike.md`, Phases 0–5).

---

## 1. Gap Analysis (ground truth, evidence-based)

| # | Objective | Before this milestone | Evidence |
|---|---|---|---|
| 1 | Corporate Actions | Schema stub; no ingestion, no adjustment applied anywhere | `CorporateActionModel` unused; `adj_factor` always 1; `IndicatorPipelineImpl._to_dataframe` read raw OHLC directly |
| 2 | Historical Universe | Real bug: survivorship bias | `HistoricalScreeningUseCase._evaluate_universe` used `list_active()` regardless of `as_of_date` |
| 3 | Security Metadata | Schema present, never populated | `Security.sector`/`industry`/`listing_date` always `None`; `ExecuteScreening._upsert_securities` built bare placeholders |
| 4 | Research Feature Store | Partial | `screening_results`/`rule_results` already captured scores/rules/rankings/explanations; forward returns/drawdown/volatility did not exist |
| 5 | Data Quality Framework | Missing entirely | No gap/duplicate/anomaly/calendar-integrity checks anywhere |
| 6 | Walk-Forward Research | Fake | `HistoricalValidationUseCase._execute_window` only queried pre-existing runs, never executed anything; comment: *"For now, return summary based on existing run data"* |
| 7 | Benchmark Library | Partial, broken | 4 benchmark JSON strategy configs existed (correct per ADR-005); but `AlphaMeasurementUseCase._get_benchmark_return` was a hardcoded stub returning `Decimal("0")`, and `benchmark_index_daily` was **never written to by anything** |
| 8 | Statistical Platform | Partial | Sharpe/Sortino/Alpha/Beta/drawdown/win-rate/ranking-stability/FPR/FNR already computed, but always over full run history with no train/test separation |
| 9 | Research Metadata | Partial | `config_hash`/`data_version` already real and stable; no git-commit or code-provenance capture anywhere |

External-data-source findings (already established, re-confirmed): `nsemine` has zero
corporate-actions or historical-constituents/sector-classification endpoints. A real,
scrapable NSE corporate-actions endpoint was found and used (Objective 1). No equivalent
source exists for historical index constituents or sector/industry classification —
both remain disclosed limitations, not silently guessed.

---

## 2. Implementation Summary

**Objective 1 — Corporate Actions (complete).**
`RawCorporateAction` port type + `MarketDataProvider.fetch_corporate_actions`;
`BhavcopyProvider` implementation against NSE's real corporate-actions endpoint with a
conservative regex parser (Bonus X:Y, Face Value Split — everything else disclosed with
`ratio=None`, never guessed); pure domain `compute_adjustment_factors`;
`SqlCorporateActionRepository` (upsert/list); `SqlOHLCVRepository.update_adjustment_factors`
(Core-table executemany, `adj_close = close * factor` computed atomically);
`IndicatorPipelineImpl._to_dataframe` now applies `adj_factor` to OHLC/volume — this was
the critical missing link, since it bypasses the domain `OHLCVSeries` accessor entirely.
Wired via a new `RefreshCorporateActions` use case (deliberately **not** inline with daily
screening — NSE's per-symbol endpoint would mean 500+ external calls per day against a
source that already 403s on its handshake request; documented as a periodic/weekly job).

**Objective 2 — Survivorship Bias (complete).**
`HistoricalScreeningUseCase` now filters the universe by `listing_date <= as_of_date`.
Discovered and fixed the reason this would have been a no-op: `RawInstrument` never carried
`listing_date`, and `ExecuteScreening._upsert_securities` built bare placeholder securities
from symbol strings alone. Added `listing_date` to `RawInstrument`, populated it from
nsemine's `date_of_listing` column, and wired the real instrument-master lookup into
`_upsert_securities` — with a `COALESCE`-based upsert so a symbol-only upsert never clobbers
an already-known listing date. New `UniverseMembership` value object + repository method
persist eligible/excluded-with-reason for every security in every run (live and historical).
Residual bias (later delistings/index removals) is explicitly disclosed in `run.stats`, not
hidden.

**Objective 3 — Security Metadata (complete, partially bounded by data availability).**
`listing_date` is now real and end-to-end wired. `sector`/`industry` remain `None`:
confirmed no free NSE source (current or historical) publishes this classification.
Guessing from company names was rejected as fabricated certainty.

**Objective 4 — Research Feature Store (complete).**
New `forward_returns` table (migration `0002_forward_returns`, applied and verified
reversible against the dev DB). Pure `compute_forward_return` (return/drawdown/volatility
over a fixed horizon from a close-price path). `ForwardReturnsBackfill` use case: idempotent,
append-only, only computes horizons whose forward bars actually exist (never revises).
Existing `screening_results`/`rule_results` already covered rankings/rule-results/engine
scores/explainability — confirmed via audit, not rebuilt.

**Objective 5 — Data Quality Framework (complete, one disclosed approximation).**
Pure `detect_gaps`/`detect_duplicates`/`detect_price_anomalies`/`detect_volume_anomalies`.
`DataQualityReport` use case cross-references flagged price anomalies against persisted
corporate actions so a real split/bonus isn't reported as a data defect. Trading-calendar
gap detection is a **weekday approximation** (no free NSE holiday calendar exists) —
disclosed in the report output itself, not hidden.

**Objective 6 — Walk-Forward Research (complete).**
`HistoricalValidationUseCase._execute_window` now genuinely executes
`HistoricalScreeningUseCase` for sampled dates without an existing run (weekly stride —
running every trading day in a multi-year window would make the call's runtime unbounded),
using the real ingested trading calendar (`OHLCVRepository.list_distinct_dates`) instead of
a "proxy from existing run dates." A window shorter than ~5 years now carries an explicit
regime-diversity / multiple-comparison-bias warning in its summary.

**Objective 7 — Benchmark Library (complete; found and fixed a second broken invariant).**
The 4 benchmark JSON configs (Pure Momentum, RS-Only, Trend-Template-Only, Equal-Weight)
were already correct per ADR-005 (strategy-as-config; no new engine code needed or built,
consistent with "don't redesign architecture"). The real gap: `benchmark_index_daily` was
**never written to by anything** and `_get_benchmark_return` was a hardcoded stub —
meaning every alpha/beta ever shown in the dashboard was computed against a fabricated flat
benchmark, not the real Nifty 50/500. Added `BenchmarkIndexRepository` port +
`SqlBenchmarkIndexRepository` (real close-to-close return, `None` — never a guess — when
history is insufficient) and wired it into `AlphaMeasurementUseCase`.

**Objective 8 — Statistical Platform.** No separate work item: the train/test-separation
gap is the same gap Objective 6 closed (walk-forward windows now execute real, sampled,
out-of-sample runs rather than reporting over the full history with no held-out set).

**Objective 9 — Research Metadata (complete, bounded).**
`get_git_commit()` (graceful `None` on any failure, never fabricated) now populates
`run.stats["git_commit"]` on every live and historical run. `config_hash`/`data_version`
were already real. `experiment_id`/`dataset_version`/`research_version` were **not**
implemented — no caller in this codebase yet has a well-defined value for them; inventing
one would be exactly the kind of fabricated certainty the research charter forbids.

**A bug caught by mypy, not tests:** while adding `BenchmarkIndexRepository`, an edit
accidentally split `ScreeningRunRepository` into two classes, stranding four of its methods.
No test failed (a `Protocol` isn't runtime-enforced), but `mypy` caught it immediately via
structural typing. Fixed and re-verified before proceeding — the incident itself is evidence
for why "run mypy after every change" is a load-bearing habit here, not a formality.

---

## 3. Validation Results

- `ruff check src tests`: 159 pre-existing errors, **0 introduced** by this milestone (all
  in files untouched by this work — `application/dto/validation.py`,
  `interface/api/routers/research.py`, and test files with long lines).
- `mypy src`: 23 pre-existing errors, **0 introduced**, checked across 153 source files.
- `pytest`: **144 passed**, up from 102 at the start of this milestone (42 new tests: 9 unit
  + integration for corporate actions, 1 for survivorship bias, 2 for security metadata,
  6 + 2 for forward returns, 10 + 2 for data quality, 1 for walk-forward, 3 for benchmark
  index, 3 for git-commit capture, plus the indicator-pipeline adjustment test).
- Alembic: `0002_forward_returns` applied cleanly against the live dev DB
  (`postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25`), verified via
  `\d forward_returns` (correct columns, PK, FKs), and confirmed reversible
  (`alembic downgrade -1` dropped the table cleanly; re-applied to leave the DB at head).

---

## 4. Remaining Limitations (disclosed, not hidden)

1. **Sector/industry classification** — no free NSE source exists (current or historical).
   Permanently undone unless a paid data vendor is approved.
2. **Historical index constituents** — no free source exists. The survivorship-bias fix
   (Objective 2) mitigates only the "not-yet-listed" half of the problem; later
   delistings/index removals are still not excluded. Disclosed in every historical run's
   `stats`.
3. **Trading-calendar holiday awareness** — approximated as weekdays; a real NSE holiday
   will appear as a false-positive gap in the Objective 5 data-quality report.
4. **`experiment_id`/`dataset_version`/`research_version`** — not implemented; no concrete,
   non-fabricated value exists for them yet in this codebase.
5. **`RefreshCorporateActions` / benchmark-index sync** — both built as standalone,
   independently-invokable use cases, **not yet wired into the scheduler** for automatic
   periodic execution. Currently manual/DI-invokable only.
6. **`git_commit` will be `None` in the current environment** — verified live: this
   directory is not yet a git repository (per the session's own environment metadata), so
   `get_git_commit()` correctly and honestly returns `None` until version control is
   initialized. This is the intended fail-safe behavior, not a bug.
7. **No new API endpoint for `DataQualityReport`** — the use case is complete and tested,
   but not yet exposed via `interface/api/routers/`.
8. **Multi-year stock-level historical backfill** remains explicitly deferred (per the
   original plan) — the data-foundation plumbing that would make a backfill actually
   trustworthy (adjustment, survivorship mitigation, feature store, regime-diversity
   warnings) is now in place, which was the stated precondition for revisiting it.

Per the charter's own standard: this milestone closes real, evidenced gaps and discloses
the ones that cannot honestly be closed without a new data source or explicit user
decision — it does not claim more certainty than the evidence supports.
