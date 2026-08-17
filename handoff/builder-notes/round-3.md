# Builder Notes — Round 3 (Approximations Loop)

Commit: `27f660b`. Diff: `backend/src/momentum25/interface/cli/main.py` (+54),
`backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py`
(+62), `backend/tests/integration/test_walk_forward_market_data_providers.py`
(+39).

## Finding addressed

### Item 14 (Brief violation, carried from round 2) — no real, non-test execution path prints `benchmark_return` next to its label

Round 2's finding was precise: `format_walk_forward_report()` existed and was
correct in isolation, but its only caller was its own unit tests — no human
running the application could reach it. Round 2's builder note explains why a
full CLI command was rejected: it can't call `WalkForwardRunner.run()` without
an `EligibilityFactsProvider`, and none exists (no table anywhere in the DB
carries Nifty 500 constituency or T2T/ASM surveillance status, current or
historical — this is a real, previously-verified data gap, not a code defect).

Reviewer's round-2 note offered the unblocking path directly: "a CLI/script
command that... wires the two already-real Postgres providers into a runnable
command with a stub/no-op universe provider scoped explicitly as a known gap...
would satisfy 'at least one report/output path'." That's what this round
builds.

**What was added:**

1. `StubAllActiveSecuritiesEligibilityProvider` in
   `walk_forward_market_data.py` — loads every active NSE row from
   `securities` and treats each as an eligible, surveillance-clean,
   Nifty-500 constituent (`in_nifty_500=True`, `is_t2t=False`,
   `is_under_surveillance=False`), computing only
   `listing_days_as_of_decision_date` from real data
   (`securities.listing_date`). Its docstring and a module-level
   `ELIGIBILITY_STUB_WARNING` string state explicitly that this is **not**
   Nifty 500 membership or surveillance data, that no such adapter exists in
   this codebase, and that using it does not close checklist item 13 or the
   `EligibilityFactsProvider` gap. This is a wider approximation than the
   "current constituents applied retroactively" one
   `brief-addendum-approximations.md` describes for the benchmark/universe
   gap — that addendum assumed a *current* Nifty 500 list existed somewhere
   to apply backward; round 1 and round 2 already verified no such list
   exists at all, current or historical. I did not fabricate one; the stub
   is a deliberately broader, explicitly-labeled placeholder that exists only
   to give the runner something to execute against end-to-end, not a claim
   about Nifty 500 membership.

2. `walk-forward` command in `interface/cli/main.py` — wires
   `NSETradingCalendar`, `SqlPriceHistoryProvider`, `SqlBenchmarkProvider`
   (real, unchanged since round 1), and the new stub universe provider into a
   real `WalkForwardRunner`, runs it, and prints
   `format_walk_forward_report(result)`. Prints `ELIGIBILITY_STUB_WARNING` as
   a banner *before* the report, so the stub is never silently invisible to
   whoever reads the output — this satisfies
   `brief-addendum-approximations.md`'s Reviewer-check requirement that "no
   code path silently claims... point-in-time survivorship-free membership."

**Verified by actually running it**, not just reading the code (per
`reviewer-handoff.md`'s own evidentiary bar, applied to my own claim before
handing it back):

```
$ M25_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:55432/momentum25 \
  uv run python -m momentum25.interface.cli.main walk-forward 2026-01-01 2026-04-01
WARNING: STUB eligibility provider: every active NSE security is treated as a
Nifty 500 constituent with clean T2T/ASM status. ...
Initial capital: 1000000
Final NAV:       888618.2641612275235969075227
Total return:    -11.14%
Benchmark return (Nifty 500 Price Index (not TRI)): -12.44%
Rebalances: 4, Trades: 129
```

This ran against the real, non-test `momentum25` database — real prices, real
benchmark levels, real trades — with only universe/eligibility approximated
and clearly labeled. The label appears directly next to the number, in a real
command a human can run.

## What this does not do

- Does not close item 13 (providers/runner unwired) as a general claim — it
  wires them for this one specific command, with an explicitly non-real
  universe input. The `EligibilityFactsProvider` gap is unchanged and remains
  a real-data blocker, not a code defect.
- Does not change `domain/backtest/`, `SqlPriceHistoryProvider`,
  `SqlBenchmarkProvider`, or any frozen loop-1/loop-2 code — `git diff` on
  those paths since round 2 is empty (see below).
- Does not claim the resulting numbers are a Nifty 500 backtest — the CLI
  banner and the provider's docstring say so explicitly.

## Tests

- Two new integration tests in
  `tests/integration/test_walk_forward_market_data_providers.py`:
  `test_stub_eligibility_provider_excludes_not_yet_listed_securities`,
  `test_stub_eligibility_provider_excludes_inactive_securities`. Both run
  against a real (test) Postgres database (`momentum25_test`), following the
  file's existing pattern for the other provider tests.
- Kill-tested `..._excludes_not_yet_listed_securities`: mutated the real
  source (`walk_forward_market_data.py`) to remove the listing-date filter,
  confirmed the test goes red (`assert 2 not in {...}` failure with the
  not-yet-listed security present in the facts), reverted via backup-file
  restore, confirmed `git status --short` clean afterward.
- `uv run pytest tests/unit tests/integration -q` → 627 passed (519 unit +
  108 integration, run against `momentum25_test`; no existing test touched,
  removed, or newly failing).
- `uv run ruff check` on all three changed files → all checks passed.
- `uv run mypy` on both changed source files → Success, no issues.

## Diff

```
git diff 973f047..27f660b --stat
 backend/src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py | 62 ++++++++++++++++
 backend/src/momentum25/interface/cli/main.py                                                | 54 ++++++++++++
 backend/tests/integration/test_walk_forward_market_data_providers.py                        | 39 +++++++++
 3 files changed, 155 insertions(+)
```

No file under `domain/backtest/`, `walk_forward.py` (application use case), or
`walk_forward_market_data.py`'s existing `SqlPriceHistoryProvider`/
`SqlBenchmarkProvider` classes changed — only additive new code.
