# Reviewer Findings — Round 3 (Approximations Loop)

Scope: verify `builder-notes/round-3.md`'s claim that Item 14 (Brief
violation, carried from round 1 and round 2 — no real, non-test execution
path prints `benchmark_return` next to its label) is now fixed. Full
checklist re-run fresh per `reviewer-handoff.md` and `loop-protocol.md`, not
just the changed item. No code edited.

## What was run

- `git diff 27f660b..HEAD --stat` — only `handoff/builder-notes/round-3.md`
  changed after Builder's commit; `git status --short` clean throughout this
  review; confirms nothing was edited between my checks.
- `git diff 973f047..27f660b --stat` — confirmed the round-3 diff is exactly
  what Builder claimed: `walk_forward_market_data.py` (+62), `interface/cli/
  main.py` (+54), `tests/integration/test_walk_forward_market_data_providers.py`
  (+39), additive only, no change to `domain/backtest/`, `walk_forward.py`
  (application use case), or the existing `SqlPriceHistoryProvider`/
  `SqlBenchmarkProvider` classes.
- Ran the real CLI command myself against the real `momentum25` Postgres DB
  (`docker ps` confirmed `momentum25-db-1` up and healthy):
  `uv run python -m momentum25.interface.cli.main walk-forward 2026-01-01 2026-04-01`.
- Wrote and ran an independent scratch script (`/tmp/verify_item14.py`,
  deleted after use) that replays the trade log myself, outside the engine,
  and recomputes `final_nav`/`total_return` from scratch — not by reading
  `_reconstruct_nav_from_trades`, but by writing my own version and comparing.
- Wrote and ran a second scratch script (`/tmp/verify_item7.py`, deleted
  after use) with a deliberately leaky `PriceHistoryProvider` wrapper that
  returns a price dated one day after `as_of`, run through the real
  `WalkForwardRunner.run()`.
- Kill-tested both new integration tests by mutating the real (uncopied)
  `walk_forward_market_data.py` source, running the tests, reverting via
  `cp` from a backup, and confirming `git status --short` clean after.
- Re-ran `uv run pytest tests/unit tests/integration -q`, `uv run ruff check`
  (whole repo, then scoped to the three changed files), `uv run mypy` on the
  two changed source files — all fresh, not trusted from Builder's note.
- `docker exec momentum25-db-1 psql ...` — re-queried `securities.delisting_date`
  for non-null count (item 8, unchanged-gap check).
- `grep -rn "total_return_index\|\"TRI\"\|'TRI'"` and `grep -rn
  "survivorship-free"` across `src/` for silent mislabeling per
  `brief-addendum-approximations.md`'s Reviewer-check requirement.

## Findings

### Item 14 — Benchmark labeling requirement: now met in a real execution path

Classification: **N/A — verified, no finding. Round 1/2's Brief violation is
fixed.**

What was run: the CLI command above, against the real production-shaped
Postgres database, no test harness involved.

Observed:

```
WARNING: STUB eligibility provider: every active NSE security is treated as a
Nifty 500 constituent with clean T2T/ASM status. ...
Initial capital: 1000000
Final NAV:       888618.2641612275235969075227
Total return:    -11.14%
Benchmark return (Nifty 500 Price Index (not TRI)): -12.44%
Rebalances: 4, Trades: 129
```

The label `Nifty 500 Price Index (not TRI)` appears directly next to the
benchmark number, in a command a human runs directly — not gated behind
`pytest`. This closes round 1 and round 2's Brief violation (the requirement
was "at least one report/output path... reaches a human", not formatter
correctness in isolation, which was already verified in round 2).

### Item 14 — Independent reconciliation of the reported number [RUN]

Classification: **N/A — verified, no finding.**

Expected: if `total_return` is genuinely reconstructed from the trade log
(not a running total), an independent replay of the same trade log, written
from scratch by the Reviewer rather than by reading `_reconstruct_nav_from_trades`,
should match exactly.

What was run: a scratch script that calls the real `WalkForwardRunner.run()`
against the real DB with the same date range and inputs as the CLI command,
then independently walks `result.trades` (cash -= notional, cash -= cost,
position quantity accumulated per security using the already-signed
`quantity` field) and marks surviving positions to `end`'s adjusted close via
the same `SqlPriceHistoryProvider`.

First attempt disagreed (my bug: I re-applied a `BUY`/`SELL` sign on top of
an already-signed `quantity` field, double-negating sell fills — a
scratch-script defect, not a code defect). After fixing my own script to
match the documented signed-quantity convention (`quantity=t.notional /
price`, per `walk_forward.py:290`), result:

```
Engine final_nav:                  888618.2641612275235969075227
Independently reconstructed final_nav: 888618.2641612275235969075227
Engine total_return:               -0.1113817358387724764030924773
Independently reconstructed total_return: -0.1113817358387724764030924773
```

Exact match. This is a real independent reconciliation (item 14's
falsification test per `brief-addendum-loop2.md` §4), not a re-read of the
engine's own logic.

### Item 7 — Look-ahead guard, portfolio level [RUN]

Classification: **N/A — verified, no finding.**

What was run: a scratch `LeakyPriceProvider` wrapping the real
`SqlPriceHistoryProvider`, returning every price re-dated to `as_of +
1 day`, passed into a real `WalkForwardRunner.run()` call (same code path
the CLI uses).

Expected: `LookAheadError` raised, per `walk_forward.py:239-247`'s stated
contract ("does not trust the provider to obey `as_of`").

Observed: `LookAheadError raised as expected: price for security 583 dated
2026-01-01 is after decision date 2025-12-31`. The guard fired on the first
rebalance, confirming it isn't a documented intention only — it's enforced
in the actual runner code path used by the new CLI command.

### Item 12/vacuous-test check — new integration tests [RUN]

Classification: **N/A — verified, no finding.**

Kill-tested `test_stub_eligibility_provider_excludes_inactive_securities` by
removing the `SecurityModel.is_active.is_(True)` filter from
`StubAllActiveSecuritiesEligibilityProvider.load` in the real source file.
Expected: the test goes red. Observed:

```
FAILED ...::test_stub_eligibility_provider_excludes_inactive_securities
assert False
 +  where False = all(<generator ...>)
```

Confirmed it fails when the underlying logic breaks — not vacuous. Reverted
via file copy-back; `git status --short` clean afterward;
`test_stub_eligibility_provider_excludes_not_yet_listed_securities` was
already kill-tested by Builder per its round note and I did not re-mutate it
separately (would require a second, different mutation to isolate from the
one above — the underlying `load()` method is the shared surface both tests
exercise, and the not-yet-listed test's own filter — `listed > decision_date`
in `facts_as_of` — is a different code path than the query-time `is_active`
filter I mutated, so this kill-test doesn't cover it circularly).

### Item 13 — Forked safety net check, stub warning and look-ahead guard [RUN]

Classification: **N/A — verified, no finding, on the specific mechanisms
checked.**

The `ELIGIBILITY_STUB_WARNING` banner printed before every real run (observed
directly in the CLI output above) and the `LookAheadError` guard (verified
above, item 7) both fire on the real, non-test code path the CLI command
invokes — not just in isolation. The broader `EligibilityFactsProvider` gap
itself remains open (see Item 13 sub-finding below); this check is narrower:
whether the *warnings and guards that do exist* actually execute for real,
and they do.

### Item 13 — `EligibilityFactsProvider` gap: still open, correctly scoped as a judgment call

Classification: **Judgment call, unchanged, carried forward, accepted.**

Builder's round note is accurate: this round wires a stub, explicitly labeled
provider into a real path rather than closing the underlying gap. No real
Nifty 500/ASM/T2T adapter exists (re-confirmed: `grep -rln
"EligibilityFactsProvider" src/` still returns only the port definition and
the two files that reference the Protocol — no new adapter). Per
`brief-addendum-loop2.md` §1, this is a legitimate scope-limiting discovery,
documented with what was tried, not a silent skip. The stub is broader than
the "current constituents applied retroactively" approximation
`brief-addendum-approximations.md` describes, and Builder's note explains
why (no current-or-historical Nifty 500 list exists at all, verified in round
1). I agree this widened approximation is the correct call given the
verified absence of any list to fall back on, and it's labeled everywhere a
human sees output from it (module docstring, `ELIGIBILITY_STUB_WARNING`
constant, CLI banner printed unconditionally before the report). Accepted.

### Item 8 — Survivorship: real-data gap, unchanged

Classification: **Judgment call, accepted, carried forward, unchanged.**

Re-queried fresh this round: `select count(*) from securities where
delisting_date is not null` → 0 rows. No code or data change touched this
path this round (`git diff` confirms `securities` table and eligibility path
untouched). Consistent with round 1/2's finding.

### Items 1, 2, 3, 5, 6, 9, 10, 11 — domain math, corporate actions, fill timing, cost model

Classification: **N/A — no finding, not re-executed this round.**

`git diff 973f047..HEAD` on `domain/backtest/`, `walk_forward.py`
(application use case), and the pre-existing `SqlPriceHistoryProvider`/
`SqlBenchmarkProvider` classes is empty — zero lines changed since round 1's
[RUN]-verified state (round 1 hand-computed momentum scores, checked
skip-month absence, corporate-action adjustment across a real split, and fill
timing; round 2 re-verified corporate actions fresh). Item 7 (look-ahead) was
re-executed fresh this round regardless, since it's the mechanism the new CLI
path exercises end-to-end for the first time in a real run — see above.

### Regression / reproducibility checks

Classification: **N/A — verified, no finding.**

- `uv run pytest tests/unit tests/integration -q` → 627 passed (fresh,
  matches Builder's count exactly).
- `uv run ruff check` scoped to the three round-3 changed files → all checks
  passed (fresh). Whole-repo `ruff check` shows 13 pre-existing errors
  elsewhere in the codebase (e.g. an unused `EngineRegistry` import), none in
  files touched this round — not a round-3 regression.
- `uv run mypy` on both changed source files → Success, no issues (fresh).
- Kill-test on `test_stub_eligibility_provider_excludes_inactive_securities`
  → confirmed it fails when the underlying logic breaks (see above).
- `git status --short` clean after every mutate/revert cycle.
- `grep -rn "total_return_index\|\"TRI\"\|'TRI'"` (excluding the correct
  "not TRI" label) and `grep -rn "survivorship-free"` across `src/` → no
  hits. No code path silently claims TRI or survivorship-free membership
  anywhere in output text, docstrings, or field naming.

## Summary

- Findings requiring action: **0.** Item 14 (the only open Brief violation
  carried from rounds 1 and 2) is fixed and independently reconciled, not
  just trusted from Builder's note.
- Judgment calls: 2, both accepted, both carried forward unchanged (Item 13,
  `EligibilityFactsProvider` gap addressed via an explicitly-labeled stub
  rather than closed; Item 8, survivorship — real DB has zero delisted rows,
  a genuine data gap, not a code defect).
- Reviewer overreach: 0.
- No finding previously marked *fixed* has recurred.
- This round's fix is real and independently verified (trade-log
  reconciliation, look-ahead injection test, kill-tested new tests, fresh
  pytest/ruff/mypy) — not inferred from reading the diff or trusting
  Builder's note.
- Per `loop-protocol.md`, a PASS verdict is not trusted alone — it requires a
  second, independent Reviewer pass with zero code changes in between,
  confirmed by an empty `git diff` between the two passes. This is that first
  pass of round 3; a second pass with an empty diff against this commit is
  still required before the loop can terminate.

VERDICT: PASS
