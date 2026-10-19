# ADR-014: Strategy Studio — Configured Rules, Three Result Classes, Sealed Hold-Out

**Status:** Accepted (2026-10-18, by the owner, with the amendments below already folded in: families by hypothesis and lineage, one official independent hold-out evaluation per family, a 36-month hold-out subject to sufficient historical evidence, and no out-of-sample result presented as validated future performance).

## Context
Strategy Studio (FR-25) lets a user change a screening strategy and judge it. Users will read any number the Studio shows as a claim about future returns. So the Studio must be correct about what each number means.

Facts from the code:

1. **The walk-forward backtest is a different method.** It ranks on 3/6/12-month blended momentum with a monthly rebalance and "does not use the screener's engines" (`docs/current/design.md:8`). It cannot evaluate a user strategy.
2. **A strategy-aware path exists.** `HistoricalScreeningUseCase` (`application/use_cases/research/historical_screening.py`) runs the real `StrategyEngine` for a past date. `HistoricalValidationUseCase` (`application/use_cases/validation.py:72`) runs it across a window.
3. **Rules declare no parameter bounds.** `RuleConfig.params` is `dict[str, Any]` (`domain/entities/strategy.py:16`).
4. **`ParameterResearchUseCase` overrides are stubs.** Variants do not yet change engine behaviour.
5. **Point-in-time gaps in today's historical path:**
   - **Price adjustment uses today's knowledge.** `IndicatorPipeline._fetch_bars` reads bars with `date <= reference_date`, which is correct for an end-of-day decision. But `_to_dataframe` multiplies by the stored `adj_factor`, which includes every corporate action up to *today*. A later split rescales earlier prices. That affects price-level and value-level gates.
   - **Delisted names may be dropped.** `_fetch_bars` filters `SecurityModel.is_active.is_(True)`, and `SecurityRepository.deactivate_symbols` sets `is_active=False` when a name leaves the provider list. A name delisted after the decision date may get no bars in a historical run. **To verify in M14:** the effect on past research runs, and whether another path compensates.
6. **History is overwritten.** `ohlcv.py:62` and `corporate_actions.py:49` upsert with `on_conflict_do_update`. A price or corporate-action correction replaces the old value, and nothing records when we learned it. Most history was backfilled in 2026, long after the sessions it describes.
7. Research history (RP-000 to RP-007) shows how easy it is to fool ourselves. 8 of 8 ranking changes failed on hold-out. RP-006 found the hold-out underpowered.

## Decision

### 1. Scope of v1
A user can:
- enable or disable registered engines and rules
- mark rules or engines as gates
- change thresholds and weights within declared bounds
- name, save and version configurations

Out of scope: scripting, user-defined executable rules, new indicators, AI agents (ADD §4).

### 2. Prerequisite: rule parameter schemas
- Each registered rule declares a parameter schema: name, type, unit, bounds, default and a one-line meaning.
- `StrategyConfig` validation enforces it. An out-of-range value is rejected at the boundary and never clamped silently.
- The Studio UI is generated from the schemas.

### 3. A user strategy is an ADR-005 strategy
- It is versioned JSON, identified by `config_hash`, immutable once run, and deterministic under ADR-009.
- User strategies get their own `kind` (migration `0009_strategy_kind`).

### 4. Strategy families: hypothesis plus lineage
- **A user creates a family by stating its hypothesis** in one sentence. Example: "A tighter liquidity gate improves 120d returns of the qualified set."
- **Lineage:** every config records its parent `config_hash`. A config derived from a family member belongs to that family. It cannot leave the family by changing the hypothesis text.
- **A new family needs a new hypothesis and a new root.** The root is either the built-in strategy or a config created from scratch. The system records the root and the hypothesis immutably at creation.
- The Studio shows each family's hypothesis, its lineage tree and the state of its hold-out (§6).

### 5. Three result classes
The exact labels are fixed. Every API response and screen uses them, and no screen mixes classes without them.

| Label | What it is | What the UI may show |
|---|---|---|
| **Screening Result** | What the configured rules select on the latest session | The selection and its explanation. No performance figure. |
| **Historical Research — In-Sample** | Evaluation inside the research window. A user may run it many times. | Figures, the number of research runs in the family, the regime warning and the provenance label (§7). The text "Not evidence of future returns." |
| **Out-of-Sample Evaluation** | The family's single evaluation on the sealed hold-out (§6) | Figures with confidence intervals, a power statement, the number of families already evaluated on the same window, and the provenance label. Never the word "validated". |

No class claims future returns.

### 6. Sealed hold-out: one independent evaluation per family
- **Window:** a fixed **36 months**, ending at the latest session whose forward returns have matured for the longest horizon in use. The system sets the window. The user cannot move it.
- **Data sufficiency:** the evaluation runs only if the window has 36 months of usable data, with enough qualified-set observations to meet the minimum power the ADR sets in M14. Otherwise the result reads "Out-of-Sample Evaluation unavailable: insufficient data".
- **Independence:** the research window ends before the hold-out starts, with a gap at least as long as the longest forward-return horizon. Historical Research runs never read data inside the hold-out.
- **One evaluation per family.** The user chooses one frozen `config_hash` from the family and submits it. The system records the result permanently, append-only. After that, the family's hold-out is spent. Other family members can still get Historical Research — In-Sample results, but never a second Out-of-Sample Evaluation on the same window.
- **One evaluation is not validation.** Even one test per family can fit the hold-out if many families test on the same window. Each Out-of-Sample Evaluation therefore shows:
  - the number of families already evaluated on that window
  - a multiple-testing adjustment for that number (method fixed in M14)
  - a power statement, which reads "underpowered" when the sample cannot detect a plausible effect (as RP-006 found)
- **Re-sealing:** a new window opens only when 36 new months have matured. Each result keeps the label of the window it used.

### 7. Point-in-time evaluation and the data-version contract
- **`StrategyEvaluation` use case.** It builds on `HistoricalScreeningUseCase`, so it runs the real `StrategyEngine` and the configured rules. It never uses the walk-forward ranker.
- **Shared as-of port: `PointInTimeMarketData(decision_at, data_version)`**. The cutoff is a timestamp, not a calendar date.
  - A bar for session D is eligible if and only if it was available at `decision_at`. For an end-of-day decision after D's bhavcopy is ingested, D's completed bar is eligible. A later session never is. A later bar raises `LookAheadError`. This moves the walk-forward guard into a shared port.
  - Adjustment is computed as of `decision_at` from raw prints and corporate actions known by then, using `compute_adjustment_factors`. The stored cumulative `adj_factor` is never read.
  - The universe is point in time. It uses `historical_universe`, `listing_date` and `delisting_date`, never `is_active`.
- **History tables (system versioning).** Each input table gets an append-only history table: `ohlcv_daily`, `corporate_actions`, `historical_universe`, `universe_membership` and `benchmark_index_daily`.
  - A database trigger copies the old row on every update or delete, with a monotonic `revision_id` and `recorded_at`.
  - The current tables stay as they are, so the live pipeline does not change.
- **`data_version` is a manifest, not a date.** It records:
  - the high-water `revision_id` of each input table
  - the indicator version (`INDICATOR_VERSION`), the rule-registry version and the git commit
  - the trading-calendar version

  The as-of port rebuilds every input exactly as it stood at those revisions. Two evaluations with the same manifest give identical results (ADR-009). The manifest's hash is the short `data_version` string shown in the UI.
- **Information availability is labelled, not assumed.** Each input row carries a provenance class:

  | Provenance | Meaning | Example |
  |---|---|---|
  | `recorded` | We stored it at or before the time it became public | Live daily ingest after the history tables exist |
  | `published` | Taken later from an official archive. We assume the exchange made it public at session close. | Bhavcopy backfill |
  | `reconstructed` | Inferred or rebuilt later. The original information state is unknown. | PREVCLOSE-inferred corporate actions, the stubbed Nifty 500 and T2T eligibility, universe rebuilds |

- **Every result reports its provenance by period.** If any input in a period is `reconstructed`, that period has the label **"Incomplete historical provenance"**. The result as a whole is never described as fully point-in-time correct. An Out-of-Sample Evaluation whose window is mostly `reconstructed` cannot run.
- **This is a hard correctness gate for M14.** The Studio does not ship until the history tables, the manifest, the provenance labels and the look-ahead tests exist and pass.
- **Isolation:** evaluation runs are written to a research namespace. They never appear as production runs, never change `strategy_id=30` snapshots and never feed the default screener screen.
- **Cost:** about 50 full-universe screening runs per evaluated year at 5-day sampling. Evaluations run as background jobs with progress reporting.

### 8. As built (M14)
These fill the gaps the ADR left to M14. The constants live in `EvaluationPolicy` (`domain/research/strategy_evaluation.py`), and every result stores them.

- **Studio v1 configures only what the rule registry declares:** engines, rules, gates, parameters and weights. `universe`, `indicators`, `ranking` and `benchmark_index` are copied from the parent. A request that changes them gets 422.
- **User strategies are fenced off.** `get_active`, the strategy list and the startup prune skip `kind = "user"`, so no live or research path can run one. A strategy file cannot overwrite one either.
- **Families are append-only.** A trigger refuses any update or delete. Two families cannot state the same hypothesis (case and spacing ignored). A config's parent must be its family's root or a member.
- **Hold-out windows sit on a fixed grid:** 36-month blocks from 2020-01-01. The current window is the latest block that the data covers and whose last 120-session forward window has closed. On data to 2026-08 that is 2023-01-01 → 2025-12-31. A new window opens only when the next block matures, so the window does not slide with each new session. 2020 is the first year with a broad universe (1,600+ names) and a year of history behind it.
- **The research window** runs from the first session with 277 sessions of history (what the indicator pipeline needs) to the last decision whose forward window closes before the hold-out. Before any block has matured, it stops before the first block in the data.
- **Decisions and outcomes.** Every 5th session. Each decision runs the real `StrategyEngine` on point-in-time inputs. Outcome per name: the 120-session return from the decision close to the exit close, less NIFTY500's (the strategy's benchmark). Both closes are read at the exit session, so they share one adjustment. A name with no bar at the exit keeps its last close.
- **Metrics per decision:** Top-N mean excess return, qualified-set mean excess return, and Rank IC (Spearman of −rank with excess return, given 10 or more names).
- **Statistics.** These follow the house protocol of the 2026-08-10 ranking report:
  - mean across decisions;
  - Newey-West standard error at lag ⌈120/5⌉ − 1 = 23;
  - a two-sided normal p-value and its unadjusted 95% interval.
  - A metric needs 30 usable decisions. Otherwise it reads "unavailable: insufficient data".
- **Multiple testing:** Bonferroni. The factor is the number of families that submitted an Out-of-Sample Evaluation on the same window, this one included.
- **Power:** the minimum detectable effect at 80% power and the adjusted level. The result reads "underpowered" when that effect is larger than a plausible one. The plausible effects are fixed in advance: 0.03 Rank IC, and 2 percentage points of 120-session excess return.
- **Sufficiency.** An Out-of-Sample Evaluation is refused before it starts, and the hold-out is not spent, in two cases:
  - no block has matured;
  - more than half of the window's months have `reconstructed` inputs.
- **Spending the hold-out.** The hold-out is spent when the evaluation is queued. A failed run can be retried on the same window and revision. If the code changed in between, the retry takes a manifest with the same revision and today's code. A completed evaluation is final, and an Out-of-Sample Evaluation is never deleted (trigger).
- **Provenance by month.** A month with any visible `reconstructed` row in an input table gets "Incomplete historical provenance". For `securities`, the listing or delisting month counts.
- **Regime warning:** the benchmark's return and largest fall over the window, stated plainly.
- **Isolation.** Evaluations are stored in `strategy_evaluations`. They never write `screening_runs`.
- **Jobs.** Evaluations run as in-process background tasks with progress. A restart fails unfinished ones, which can then be retried. One decision takes 18–28 s on the full universe, so a 36-month hold-out (about 150 decisions) takes roughly an hour.

## Consequences
- The Studio judges a strategy with the same code that screens it, on data it can reproduce exactly.
- The as-of port and the history tables also fix the point-in-time gaps for existing research.
- Past research results that used price-level gates may change. M14 re-runs a sample and reports the differences before the Studio ships.
- Most history before the history tables exist is `published` or `reconstructed`. Users see that plainly.
- New work: rule schemas, the as-of port, history tables and triggers, the manifest, provenance labels, evaluation jobs and family tracking.
- Users see fewer, more honest numbers. That is the intent.

## Alternatives considered
- **Reuse the walk-forward backtest:** rejected. It evaluates a different method.
- **Show only in-sample backtests, as most platforms do:** rejected. It invites overfitting.
- **Families by parent links only:** rejected. A user can start a "new" strategy from scratch to escape a spent hold-out. Requiring a stated hypothesis and root makes that deliberate and visible.
- **One hold-out evaluation per `config_hash`:** rejected. Thirty small variants would give thirty tests on one window.
- **User-chosen hold-out windows:** rejected. The user could pick the window that flatters the strategy.
- **Full price-vintage snapshots:** rejected. History tables give the same reproducibility, and they store only what changed.
- **`data_version` as last session plus max correction time:** rejected. It cannot rebuild the universe, the corrections or the code state exactly.
