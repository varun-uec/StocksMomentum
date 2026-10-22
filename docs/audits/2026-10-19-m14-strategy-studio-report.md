# M14 Report — Strategy Studio

> **Date:** 2026-10-19 · **Branch:** `wickstreet/m10-m11` (local, never pushed) · **Decision record:** [ADR-014](../architecture/adr/ADR-014-strategy-studio.md), including §8 "As built" · **Requirement:** FR-25

## What changed

| Step | Result | Commit |
|---|---|---|
| 14.1 Rule parameter schemas | 23 rules with type, unit, bounds, default and meaning. Strategy files are checked on load. | `d519791` |
| 14.2 History tables | Five versioned input tables, one revision sequence, provenance per row. | `c1975fa` |
| 14.3 Point-in-time port | Bars, factors and universe as one decision saw them. `LookAheadError` on any later read. | `9cca60f` |
| 14.4 Data-version manifest | `data_manifests` (migration 0017). A manifest records the revision, indicator version, rule registry, git commit and calendar. Stored manifests rebuild their inputs. | `6c93e0d`, `2229f0b` |
| 14.5 Families and user strategies | `strategy_families` (0018), append-only. User strategies of kind `user`, with family and parent hash. API for the registry, families and saves. | `4143f89` |
| 14.6 Evaluation | `strategy_evaluations` (0019). Three result classes as background jobs. Newey-West, Bonferroni, power statement, provenance by month, regime note. | `ad3d1c2` |
| 14.7 Re-run of past research | 8 runs re-run point in time; [report](2026-10-19-m14-pit-rerun-report.md). | `986e33e` |
| Defect found in 14.7 | RS ratings now use adjusted closes, on every path. | `18cab43` |
| 14.8 Studio UI | `/studio`: families, lineage, a form built from the registry, the three result classes. | `49ebf33` |

## Exit criteria (ADR-014 hard gate)

| Criterion | Test | Result |
|---|---|---|
| Same `config_hash` and `data_version` give the same result | `test_same_config_and_data_version_give_the_same_result`: every bar is doubled after the first run, and a replay at the old manifest gives identical outcomes, metrics, regime, provenance and window. | Pass |
| A future bar raises `LookAheadError` | `test_no_bar_after_the_decision_is_ever_served`, and `test_historical_screening_lets_a_look_ahead_fail_the_run`, which fails on the old code: the per-symbol handler swallowed it. | Pass |
| A later split does not change an earlier decision | `test_a_later_bonus_does_not_reshape_earlier_prices`, `test_an_action_recorded_after_the_revision_is_unknown` | Pass |
| A period with `reconstructed` inputs is labelled | `test_reconstructed_inputs_label_their_months`: one reconstructed bar in March 2024 labels exactly `2024-03`. | Pass |
| A second Out-of-Sample Evaluation in a family is refused | `test_one_out_of_sample_evaluation_per_family_and_families_are_counted`. A second family on the window gets the Bonferroni factor 2. | Pass |
| Evaluations never write production runs | `test_in_sample_research_is_labelled_and_never_writes_screening_runs` | Pass |
| User strategies never reach live or research paths | `test_user_strategies_never_reach_live_or_research_paths` | Pass |

## Decisions taken
All are recorded in ADR-014 §8. These need the owner's eye:

1. **Hold-out grid:** 36-month blocks from 2020-01-01. The current window is 2023-01-01 → 2025-12-31. It does not slide with each new session.
2. **Plausible effects** for the power statement: 0.03 Rank IC, and 2 percentage points of 120-session excess return.
3. **Multiple testing:** Bonferroni over the families on the window. This is the house protocol of the 2026-08-10 report.
4. **Studio v1 scope:** only what the registry declares. Universe, indicators, ranking and benchmark come from the parent.
5. **The hold-out is spent when queued.** A failed run can be retried on the same window and revision.

## Defects found
- **RS ratings on raw closes** (`18cab43`). This touched the live daily run. MCX's 1:5 split read as −76% over 12 months instead of +20%. On the latest session, 28 names that failed the RS ≥ 70 gate now pass. **Not deployed:** the owner's image `cb0da94` is unchanged.
- **A look-ahead was logged, not raised** in historical screening (fixed in `ad3d1c2`).
- **Known, not fixed:** the trend-template rules compare a raw close with adjusted SMAs. That is correct on the live run and the point-in-time path, where the latest factor is 1. It is wrong on the older historical research path. See the [re-run report](2026-10-19-m14-pit-rerun-report.md).

## Performance
One point-in-time decision over the full universe takes 18–28 s, down from 37 s, because each security is now read once per decision. A 36-month hold-out is about 150 decisions, so roughly an hour. A research window from 2017 to mid-2022 is about 280 decisions; most of the early ones are fast, since the universe has 16 names before 2019.

## Verification
Full run at `49ebf33`:

| Suite | Result |
|---|---|
| Backend `pytest` | 811 passed (31 new since the handoff's 780) |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Generated API types | match the API |
| Web `tsc`, ESLint, build | clean |
| Web Vitest | 96 passed (5 new) |
| Playwright | 66 passed (1 new: create a family, catch an out-of-range value, save a version, cancel the hold-out prompt, run a Screening Result) |
| NFR-11 chart open (30 runs each) | Warm P95 184 ms (target ≤ 1 s); cold P95 223 ms (target ≤ 3 s) |
| Migrations 0017–0019 on the E2E copy | Upgrade, downgrade and upgrade again, each one |

## Not in M14
- Re-routing the older research tools to the point-in-time path (owner decision; see the re-run report).
- Changing the universe, indicators or ranking in the Studio.
- A job queue or worker process. Evaluations run as background tasks in the API process. Several submitted at once share it and slow each other, with no limit. A restart fails unfinished ones, which can be retried.
