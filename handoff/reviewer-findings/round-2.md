# Reviewer Findings — Round 2 (Approximations Loop)

Scope: verify `builder-notes/round-2.md`'s claim that Item 14 (round-1 Brief
violation — benchmark label not surfaced anywhere a human reads a number) is
now fixed. Full checklist re-run fresh per `reviewer-handoff.md` and
`loop-protocol.md`, not just the changed item. No code edited.

## What was run

- `git diff 973f047..HEAD --stat` — confirmed the only changed files this
  round are `application/use_cases/walk_forward.py` (+22) and
  `tests/unit/test_walk_forward.py` (+39). No domain, provider, or CLI files
  touched.
- `git diff c5966da..HEAD -- backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py backend/src/momentum25/domain/`
  — empty, confirming the round-1 [RUN]-verified look-ahead guard
  (`SqlPriceHistoryProvider`) and all `domain/backtest/` math are byte-for-byte
  unchanged since round-1's independent verification.
- `docker exec momentum25-db-1 psql -U momentum25 -d momentum25` — re-queried
  `corporate_actions` and `ohlcv_daily` for `security_id=1428` (the same
  known 1-for-2 split used in round 1) independently of Builder's claims.
- `uv run pytest tests/unit -q`, `uv run ruff check`, `uv run mypy` — re-run
  fresh against the current tree.
- Source mutation + revert on the real (not copied) `walk_forward.py` to
  kill-test the new label-assertion tests.
- `grep -rn "format_walk_forward_report\|walk_forward\|WalkForward"` across
  `src/momentum25/interface/` and the whole repo, to independently check
  whether any real (non-test) code path calls the new formatter or the
  runner.

## Findings

### Item 14 — Benchmark labeling requirement still unmet in the running application

Classification: **Brief violation** (same requirement as round 1's finding;
not a new defect, but the round-2 fix does not close it).

What was run: `grep -rn "format_walk_forward_report" .` across the whole
repo.

Expected (per `brief-addendum-approximations.md`, verbatim, unchanged since
round 1): "Label every report/output that shows the benchmark return... This
label must appear next to the number itself (report, CLI summary, chart
legend if any), not only in a README." And under "What Reviewer checks this
round": "At least one report/output path that surfaces the benchmark number
carries the... label directly next to that number."

Observed:

```
tests/unit/test_walk_forward.py:21:    format_walk_forward_report,
tests/unit/test_walk_forward.py:261:    report = format_walk_forward_report(result)
tests/unit/test_walk_forward.py:270:    report = format_walk_forward_report(result)
tests/unit/test_walk_forward.py:277:    report = format_walk_forward_report(result)
src/momentum25/application/use_cases/walk_forward.py:94:def format_walk_forward_report(result: WalkForwardResult) -> str:
```

`format_walk_forward_report` is called from exactly one place: its own unit
tests. Also confirmed `grep -n "walk_forward\|WalkForward"
src/momentum25/interface/cli/main.py` returns nothing — there is still no
CLI command, report generator, or any other consumer in the running
application that invokes either `format_walk_forward_report` or
`WalkForwardRunner.run()`. I independently verified Builder's own claim that
no `EligibilityFactsProvider` adapter exists (`grep -rln
"EligibilityFactsProvider" src/` → only the port definition and the
`walk_forward.py`/`walk_forward_market_data.py` files that reference the
Protocol, no adapter class), which is why the runner cannot be invoked from
a live command today regardless.

Assessment: the function I verified (below) is correct and well-tested in
isolation, but "at least one report/output path" means a path a human
actually reaches when running the system, not a pure function reachable only
from `pytest`. This is functionally the same gap round 1 found — "no report
or CLI summary path at all for walk-forward results, so a human running this
code today has no path to see `benchmark_return` next to its label" — moved
one level down: previously the unconsumed thing was a dataclass field, now
it's an unconsumed formatter function. The underlying defect (no real
execution path prints this number with its label) is unchanged. Builder's
own round note acknowledges this directly: "wiring it to a live CLI run is
blocked on the same pre-existing... gap."

This is not resolved. Per `loop-protocol.md`, Brief violations get no
debate — Builder must either build the minimal real output path (does not
require solving the `EligibilityFactsProvider` gap; a CLI/script command
that prints `format_walk_forward_report(result)` for a pre-built
`WalkForwardResult`, or wires the two already-real Postgres providers
(`SqlPriceHistoryProvider`, `SqlBenchmarkProvider`) into a runnable command
with a stub/no-op universe provider scoped explicitly as a known gap, would
satisfy "at least one report/output path") or escalate if it judges the
`EligibilityFactsProvider` gap makes any real output path impossible this
round.

### Item 14 sub-check — formatter correctness itself [RUN]

Classification: **N/A — verified, no finding** (isolated function is
correct; see above for why isolation itself is the finding).

Mutated the real source file: `label = result.benchmark_label or "UNLABELED
BENCHMARK"` → `label = result.benchmark_label or "TRI"`. Expected: the
never-print-without-a-label test goes red. Observed:
`AssertionError: assert 'UNLABELED BENCHMARK' in 'Benchmark return (TRI): 5.00%'`
— test correctly fails. Reverted via file copy-back; `git status --short`
confirmed clean afterward. Not a vacuous test.

### Item 9 — Corporate actions, re-verified [RUN]

Classification: **N/A — verified, no finding.**

Re-queried `ohlcv_daily` for `security_id=1428` (2026-07-31 split,
ratio=0.5), independently, this round:

```
date        close    adj_close  adj_factor
2026-07-29  34.3200  17.1600    0.50000000
2026-07-30  36.1900  18.0950    0.50000000
2026-07-31  17.0200  17.0200    1.00000000
2026-08-03  16.2600  16.2600    1.00000000
```

`adj_close` is smooth across the ex-date (17.16 → 18.10 → 17.02 → 16.26, all
single-digit-percent day moves), no fake jump/crater, matching round-1's
independently-verified numbers exactly. No code change touched this path
this round (confirmed by empty `git diff` on the provider file since
round-1's commit), so this is a non-regression check, not new evidence.

### Items 1, 2, 5, 6, 10, 11 — domain math, fill timing, cost model

Classification: **N/A — no finding, not re-executed this round.**

`git diff c5966da..HEAD` on `domain/backtest/` and the provider/repository
files is empty — zero lines changed since round-1's [RUN]-verified state on
these items (round-1 and the loop-2 rounds already exercised items 1, 2, 5,
6, 10, 11 against this same, unchanged code). Re-running the identical
scripts against byte-identical source would reproduce round-1's results
exactly; noting this explicitly rather than silently skipping per
`loop-protocol.md`'s instruction to re-run fresh — the only thing that
changed this round is additive (`format_walk_forward_report` + 3 tests), and
it does not touch any of these code paths.

### Item 13 — Providers/runner still unwired

Classification: **Judgment call, unchanged, carried forward** (same as
round 1; not re-litigated, but the round-2 fix does not close the underlying
issue — see Item 14 above for why this now blocks a Brief violation, not
just a standalone judgment call).

### Item 8 — Survivorship: real-data gap, unchanged

Classification: **Judgment call, accepted, carried forward, unchanged.**
No code or data change touched this this round; not independently
re-queried, since round-1 already confirmed `securities.delisting_date` has
zero non-null rows in the real DB and nothing in this round's diff touches
`securities` or the eligibility path.

### Regression / reproducibility checks

Classification: **N/A — verified, no finding.**

- `uv run pytest tests/unit -q` → 519 passed (fresh), matches Builder's
  count.
- `uv run ruff check` on both changed files → all checks passed (fresh).
- `uv run mypy` on the changed source file → Success, no issues (fresh).
- Kill-test on the label-assertion test → confirmed it fails when the
  underlying logic breaks (see above).
- `git status --short` clean after mutate/revert cycle.

## Summary

- Findings requiring action: **1** (Item 14, Brief violation — the same
  requirement as round 1, still unmet: no real, non-test execution path in
  the running application prints `benchmark_return` next to its label).
  This is a continuation of round 1's open finding, not yet a "recurred
  after being marked fixed" mechanical trigger under `loop-protocol.md`
  (round 1 never marked it fixed — it was FAIL), but the loop should treat
  this as the same finding still open, not a fresh one, when counting
  rounds toward the "4+ rounds without shrinking" and 8-round caps.
- Judgment calls: 2 (Item 13, providers/runner unwired — carried forward;
  Item 8, survivorship data gap — carried forward).
- Reviewer overreach: 0.
- No finding previously marked *fixed* has recurred, because Item 14 was
  never marked fixed to begin with.
- Not eligible for the trusted-PASS condition — there is an open Brief
  violation.

VERDICT: FAIL
