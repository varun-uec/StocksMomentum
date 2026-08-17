# Reviewer Findings — Round 1 (Approximations Loop)

Scope: verify Builder's `builder-notes/round-1.md` claims for
`brief-addendum-approximations.md` — real Postgres-backed price/benchmark
providers, and the approximation-labeling requirements. Full checklist
re-run fresh, per `reviewer-handoff.md` and `loop-protocol.md`. No code
edited.

## What was run

- `docker exec momentum25-db-1 psql -U momentum25 -d momentum25` — direct
  queries against the real database (not the test DB) to independently
  verify Builder's data claims.
- A throwaway script (`/tmp/verify_price.py`) loading `SqlPriceHistoryProvider`
  and `SqlBenchmarkProvider` against the real DB and calling their public
  methods directly.
- A source mutation + revert against the real (not copied) source file to
  kill-test the new integration suite, mirroring loop2 round-2's method.
- `pytest`, `ruff`, `mypy` re-run fresh against the current tree.

## Findings

### Item 9 — Corporate actions [RUN]

Classification: **N/A — verified, no finding.**

Picked `security_id=1428` (NARMADA), a real 1-for-2 split (`ratio=0.5`) on
`ex_date=2026-07-31`, independently of Builder's own claim (Builder verified
a different, unnamed security). Queried `ohlcv_daily` directly:

```
date        close    adj_close  adj_factor
2026-07-30  36.1900  18.0950    0.50000000
2026-07-31  17.0200  17.0200    1.00000000
2026-08-03  16.2600  16.2600    1.00000000
```

Expected: `adj_close` continuous across the ex-date (no fake jump/crater)
even though raw `close` roughly halves. Observed: `adj_close` moves
18.095 → 17.02 → 16.26, a smooth ~5-6%/day drift, not a ~50% step. Then
called `SqlPriceHistoryProvider.price_on_or_before(1428, d, d)` for the same
three dates and got back the identical `adj_close` values the raw SQL
query produced. Matches.

### Item 3 — Look-ahead in the provider itself [RUN]

Classification: **N/A — verified, no finding.**

Called `price_on_or_before(1428, target=2026-08-05, as_of=2026-07-29)` —
`target` deliberately dated after `as_of`. Expected: result must not reach
past `as_of`. Observed: returned the 2026-07-29 price (adj_close 17.16),
not the 2026-08-05 or later price. No leak.

Then deliberately broke the guard by editing the real source file
(`horizon = min(target, as_of)` → `horizon = target`) and re-ran
`test_price_provider_never_looks_past_as_of_even_when_target_is_later`.
Expected: red. Observed: `AssertionError: assert date(2024,1,10) ==
date(2024,1,2)` — test correctly fails once the guard is broken. Reverted
via file restore, confirmed `git status --short` clean. Test is not vacuous
(covers checklist item 12 for this specific test).

### Item 14 — Benchmark labeling requirement not satisfied anywhere a human reads a number

Classification: **Brief violation** (of `brief-addendum-approximations.md`
§"What Builder must do this round" / §"What Reviewer checks this round").

What was run: `grep -rln "WalkForwardResult" src/` (outside
`walk_forward.py` itself) and `grep -n "walk_forward\|WalkForward"
src/momentum25/interface/cli/main.py`.

Expected (per addendum, verbatim): "Label every report/output that shows
the benchmark return with 'Nifty 500 Price Index (not TRI)' ... This label
must appear next to the number itself (report, CLI summary, chart legend if
any), not only in a README."

Observed: `benchmark_label` exists only as a field on the
`WalkForwardResult` dataclass. No file in the codebase — CLI, report
generator, or otherwise — consumes `WalkForwardResult` or prints
`benchmark_return`/`benchmark_label` anywhere. There is currently no report
or CLI summary path at all for walk-forward results. The addendum's
requirement is written as an instruction to label an existing output
surface; Builder's round note documents adding the field but does not
claim, and did not build, an output surface that surfaces it. As written,
the requirement is unmet — a human running this code today has no path to
see `benchmark_return` next to its label. This is not a hypothetical: it's
directly checkable and fails.

This is not a "Builder should have built a CLI" scope-creep complaint —
narrower fix available: either (a) the addendum's requirement should be
read as "when such an output exists, it must carry the label" (a scope
note, not unmet yet, since no report/CLI is in `brief-addendum-loop2.md`
§1-3's output list beyond raw logs), or (b) the field satisfies the letter
only if something reads it. Filing as Brief violation rather than judgment
call because the addendum's own "What Reviewer checks this round" section
states plainly: "At least one report/output path that surfaces the
benchmark number carries the... label directly next to that number" — that
is a pass/fail check, not phrased as conditional on a report existing, and
it is currently false. Builder gets the normal one-rebuttal path per
loop-protocol.md.

### Item 13 — Forked safety net: new providers are wired nowhere

Classification: **Judgment call** (carried-forward scope note, not a new
defect).

What was run: `grep -rln "SqlPriceHistoryProvider\|SqlBenchmarkProvider" .`
across `src/` and `tests/`.

Expected: per `reviewer-handoff.md` item 13, hunt for a check/mechanism
that exists but never runs on the real path. Observed: both classes are
referenced only in their own definition file and their own test file —
no composition root, CLI command, or application wiring constructs and uses
them together with `WalkForwardRunner`. They are real, correct adapters
(verified above) but currently inert with respect to the actual walk-forward
use case; nothing in the running system calls
`WalkForwardRunner(price_provider=SqlPriceHistoryProvider(...), ...)`.

Logging as judgment call, not brief violation, because
`brief-addendum-loop2.md` §1-3 scoped this loop to building the providers
and the runner, not a composition root or CLI entry point — no document in
scope says "wire this into a runnable command" for this specific round. But
flagging it because it means every [RUN] verification above (including
Builder's own) required a throwaway script, not the real application path —
consistent with, not contradicting, `reviewer-handoff.md`'s definition of a
forked safety net risk. If a human intends this round's data to actually
back a report before the labeling requirement (item 14 above) can be
satisfied, this is the missing piece.

### Item 8 — Survivorship: real-data gap, re-verified, unchanged

Classification: **Judgment call, accepted (carried forward, no new
decision required).**

What was run: `select count(*) from securities where delisting_date is not
null;` → `0`. `select count(*), count(distinct last_trade_date) from
securities;` → `3235, 0`. Both independently confirm Builder's claim: no
delisted security exists in this database to test survivorship handling
against, contradicting the addendum's framing that `securities.delisting_date`
is "usable to test survivorship handling." This is a data-availability fact,
not a code defect — consistent with loop2 round-1/round-2's accepted
judgment call for the underlying point-in-time-universe gap. No regression:
`EligibilityFactsProvider` was undeveloped before this round and remains so.

### Item 12 — Vacuous test check, full suite

Classification: **N/A — verified, no finding.**

Covered under Item 3 above for the look-ahead test specifically. Did not
additionally kill-test the null-`adj_close`-exclusion or label-presence
tests this round (both are single-assertion equality/None checks against
directly-controlled fixture data with no branching logic to mutate
meaningfully) — same reasoning loop2 round-2 applied to comparably trivial
assertions.

### Regression / reproducibility checks

Classification: **N/A — verified, no finding.**

- `pytest tests/unit -q` → 516 passed (fresh), matches Builder's count.
- `pytest tests/integration/test_walk_forward_market_data_providers.py
  tests/unit/test_walk_forward.py -q` → 11 passed (fresh), matches.
- `ruff check` on both new/changed source files → all checks passed
  (fresh).
- `mypy` on both new/changed source files → Success, no issues (fresh).
- `git diff` confirms the mutate/revert cycle left the source file
  byte-identical to Builder's commit (`git status --short` clean
  post-revert).

## Summary

- Findings requiring action: **1** (Item 14, Brief violation — benchmark
  label not actually surfaced anywhere a human reads a number).
- Judgment calls: 2 (Item 13, providers unwired — scope note; Item 8,
  survivorship data gap — carried forward unchanged from loop2, not
  re-litigated).
- Reviewer overreach: 0.
- No finding previously marked fixed has recurred (this is round 1 of this
  loop; no prior round exists to regress against).
- This is a first-pass verdict, not yet eligible for the trusted-PASS
  condition (`loop-protocol.md` requires a second, independent pass with an
  empty `git diff` in between — not applicable here since there is an open
  finding).

VERDICT: FAIL
