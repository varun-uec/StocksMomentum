# Reviewer Findings — Loop 2, Round 2

Verified against `handoff/brief.md` + `handoff/brief-addendum-loop2.md` (both
FINAL) and `handoff/builder-notes/round-2.md` as a claim to verify, not a
summary to relay. Builder's claim this round is "nothing changed"; that claim
is itself checked below, not assumed.

## Precondition check — empty code diff since round-1 PASS

[RUN] `git diff 63c8ff0 HEAD -- backend/src | wc -l` → **0**. Only
`handoff/builder-notes/round-2.md` changed between the two Reviewer passes
(confirmed via `git diff 63c8ff0 HEAD --stat`). `git status --short` at
session start → clean. This satisfies loop-protocol.md's requirement for a
trusted PASS: "a second, independent Reviewer pass with zero code changes in
between, confirmed by `git diff` between the two passes being empty."

## Checklist re-run (fresh, full — not just prior failures)

**Item 7 — Look-ahead, portfolio level.** [RUN]
Wrote a third, independent leaky-provider variant (`SneakyPrices2`, distinct
from both Builder's `LeakyPrices` and round-1's `SneakyPrices`): returns a
price 2 days after `as_of` only on same-day ("current price") queries, and a
plausible dated price otherwise. Different securities (ids 1–9), different
date range (2023-05-01 to 2023-08-31), different base price. Expected:
`LookAheadError`. Observed: raised — `price for security 1 dated 2023-04-30
is after decision date 2023-04-28`. No finding.

**Item 10 — Fill timing.** [RUN]
Built a fresh linearly-trending price series (5 securities, daily from
2022-01-01 to 2024-01-01) and ran 7 rebalances (2023-03-01 to 2023-09-30).
Expected: `fill_date > decision_date` for every rebalance, matching brief §5
(decide close t, fill open/close t+1). Observed: true for all 7, including
month-boundary/weekend cases (e.g. decision `2023-06-30` → fill `2023-07-03`,
decision `2023-08-31` → fill `2023-09-01`). No finding.

**Item 14 — Benchmark/attribution consistency.** [RUN]
Using the same fresh trend-price scenario above, independently reconstructed
final NAV via `_reconstruct_nav_from_trades` fed a second, freshly
constructed `TrendPrices()` instance (not the one the runner used) and
compared to `result.final_nav`. Observed: exact match. No finding.

**Item 12 — Vacuous test check.** [RUN]
Mutated the real source file (not a copy): changed the look-ahead guard
`if point.session_date > as_of:` to `if False:` in
`application/use_cases/walk_forward.py`. Ran
`pytest tests/unit/test_walk_forward.py -k look_ahead` →
`test_look_ahead_provider_is_rejected` went PASS → **FAIL** ("DID NOT RAISE
LookAheadError"). Reverted with `git checkout --`, confirmed
`git status --short` clean afterward. Test is not vacuous. No finding. (This
targets a different line/condition than round-1's item-12 kill tests, which
mutated the raise itself via `if False:` on the raise statement and mutated
`facts_as_of` — this round mutates the comparison guard instead.)

**Full regression.** [RUN]
`pytest tests/unit/test_walk_forward.py -q` → 7/7 passed (fresh).
`pytest tests/unit -q` (full suite) → 516 passed (fresh), matches Builder's
and round-1's counts exactly.
`ruff check` on both walk-forward source files + test file → all checks
passed (fresh).
`mypy` on both new source files → Success, no issues (fresh).

**Items 4, 8, 9 (real-data gap) — regression check.** [RUN]
`grep -rl "EligibilityFactsProvider\|BenchmarkProvider\|PriceHistoryProvider"
backend/src/momentum25/infrastructure` → still empty. No real adapter has
appeared; this remains the same documented, human-decision-blocked gap
(vendor vs. manual dated-snapshot) recorded in round-1, not newly discovered.
Consistent with Builder's round-2 claim of zero changes. Classification:
**Judgment call, accepted** — carried forward unchanged, not re-litigated,
since nothing about the underlying blocker changed this round.

**Item 3 (signal-level look-ahead, frozen code) — regression check.** [RUN]
`git diff a516be0 HEAD -- backend/src/momentum25/domain/backtest/momentum_signal.py`
→ empty. No finding.

## Summary

- Findings requiring action: **0**
- Judgment calls: 3, all carried forward unchanged from round-1 (items 4, 8,
  9 — real point-in-time membership/surveillance/corporate-action adapters,
  blocked on the same documented human decision). None re-opened, none newly
  disputed.
- Reviewer overreach: 0
- Empty-diff precondition for a trusted PASS: **confirmed** via `git diff`
  between this pass and round-1's pass.
- All re-run [RUN] items used fresh, independently constructed scenarios
  (different securities, dates, price series, and mutation targets) rather
  than re-executing Builder's or round-1's own test code.
- No finding that was previously marked fixed has recurred. No judgment call
  is newly disputed. No verdict flip without a code change.

Per loop-protocol.md, this round's empty-diff second pass, combined with
round-1's clean checklist result, satisfies the trusted-PASS condition.

VERDICT: PASS
