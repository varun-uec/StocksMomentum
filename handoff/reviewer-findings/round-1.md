# Reviewer Findings — round 1 (re-issued after brief was finalized)

Note: an earlier round-1.md in this file escalated because `brief.md` was
DRAFT and no builder-notes existed. Human filled in `brief.md` (now marked
FINAL) and Builder produced `handoff/builder-notes/round-1.md`. This
supersedes the prior content of this file.

## Scope this round actually covers

Builder implemented pure-domain signal/eligibility/ranking/cost logic only —
no wired walk-forward loop against real historical data (no ASM/T2T/Nifty
500-membership data source exists in `infrastructure/`, confirmed by grep:
zero matches). Checklist items 2, 7, 8, 9, 10, 13, 14 require real historical
data or a running backtest and are **not executable** against this round's
code — see Finding 6 below for how this is classified.

## Finding 1 — Item 1 (formula matches brief)

- Classification: n/a (verification, not a defect)
- What was run: independent script using `Fraction` for an exact
  rounding-free ground truth, fresh numbers not used in Builder's tests
  (price_t=250, 3m/6m/12m-ago = 200/150/100 → r3=25%, r6=66.667%,
  r12=150%, composite=29/36).
- Expected vs observed: code's `Decimal` composite score matched the exact
  fraction to within 4.4e-29 (Decimal's 28-significant-digit context floor —
  not a bug). `compute_momentum_signal` output matches brief §2 formula.
- Result: PASS.

## Finding 2 — Item 3 (look-ahead in the signal)

- Classification: n/a (verification, not a defect)
- What was run: inspected `compute_momentum_signal`'s signature (only
  `price_t` + 3 lookback prices, no date/clock/session/IO parameter);
  called it twice with identical inputs to confirm no hidden global state;
  grepped the module source for `datetime`/`open(`/`requests`/`session` — none
  found.
- Expected vs observed: no channel exists for future-dated information to
  enter the calculation. Matches brief §9.
- Result: PASS. Note this only proves the signal function itself; item 7
  (look-ahead at portfolio-construction level, i.e. did the *caller* actually
  pass a pre-decision-date price) is not yet checkable — no caller/use case
  exists yet.

## Finding 3 — Item 6 (tie-break)

- Classification: n/a (verification, not a defect)
- What was run: fresh synthetic 3-way tie (equal composite_score AND equal
  12M return, distinct 6M/3M) fed to `rank_signals`, independent of Builder's
  test file.
- Expected vs observed: resolved 12M tie via 6M as brief §3 specifies
  (`[12, 11, 13]` order, matching hand-worked expectation). Deterministic,
  no id-ordering fallback. PASS.

## Finding 4 — Item 5 (NaN / missing-data fail-closed)

- Classification: Judgment call (accepted)
- What was run: called `compute_return` with `Decimal('NaN')`, `None`, and
  `0` as `price_t`.
- Expected vs observed: all three raise (`InvalidOperation`, `TypeError`,
  `ValueError` respectively) rather than silently propagating a bad value
  into a rank. Fails closed in all three cases, satisfying item 5's intent.
  Exception *type* is inconsistent (only the zero/negative case raises the
  module's own `ValueError`; NaN and None raise on Decimal/type-comparison
  primitives before reaching the module's explicit check) — this is a
  reasonable implementation choice, not a brief violation, since the brief
  doesn't specify exception types and all three still fail closed. Logging
  as accepted judgment call rather than requiring uniform exception types.

## Finding 5 — Item 4 (universe construction boundary)

- Classification: n/a (verification, not a defect)
- What was run: synthetic `EligibilityFacts` at 251 vs. 252
  `listing_days_as_of_decision_date` (just under / exactly at the brief's
  12-month = 252-trading-day threshold), independent of Builder's test file.
- Expected vs observed: 251 days → ineligible, 252 days → eligible. Matches
  brief §1's "at least 12 months" boundary. PASS.

## Finding 6 — Items 7, 8, 9, 10, 13, 14 (backtest-integration checklist items)

- Classification: Judgment call (accepted, with a condition)
- What was run: `grep -ri 'ASM\|surveillance\|T2T' backend/src/momentum25/infrastructure/`
  — zero matches, confirming Builder's claim that no data source exists for
  brief §1's exclusion rules. Also confirmed no walk-forward use case or
  historical-universe port exists yet (only the pure domain functions).
- Expected vs observed: these items require a running backtest against real
  historical prices/universe/corporate-actions data, which this round
  doesn't build. Builder's scope split (pure domain logic this round,
  infra/application wiring deferred rather than fabricating a T2T/ASM data
  source) follows CLAUDE.md's "Don't Guess" and "Scope Discipline" and is a
  reasonable milestone boundary — brief.md does not mandate a specific
  infra-wiring milestone for round 1.
- Accepted as a judgment call, **conditionally**: these items remain OPEN,
  not closed. They must be re-run against real data the round infra/wiring
  lands — this is not a PASS on those items, it's "not yet applicable."
  Flagging per loop-protocol.md's 4-round rule: if round 4 arrives with
  items 7/8/9/10/13/14 still unexecutable, that becomes an escalation
  trigger regardless of this acceptance.

## Finding 7 — Item 12 (test not vacuous)

- Classification: n/a (verification, not a defect)
- What was run: copied `rebalance.py`, mutated `select_portfolio`'s `kept`
  set to use a hard `PORTFOLIO_SIZE` (30) cutoff instead of `BUFFER_RANK`
  (45), reran the full test suite, then restored the original file and
  reran again.
- Expected vs observed: mutated version turned both
  `test_select_portfolio_buffer_keeps_existing_holding_outside_top_30` and
  `test_select_portfolio_hard_cutoff_would_be_a_brief_violation` red
  (`assert 7 in frozenset()`). Restored version: 9/9 green. Confirms these
  are real regression guards, not vacuous. PASS.

## Finding 8 — items not independently run this round

- Item 2 (skip-month instrumentation): not run as a live instrumentation
  because there is no skip-month logic to instrument — code inspection
  confirms `compute_momentum_signal` takes exactly one `price_t` and three
  lookback prices with no windowing/skip parameter, matching brief §2's
  "skip-month: none." This is a thinner form of verification than item 2
  asks for (which assumes a skip period exists to instrument); logging as a
  gap rather than silently marking PASS. Low risk given the absence of any
  date-range logic in the module.

## Reproducibility check

- `git status --short` in the repo matches Builder's claimed diff in
  `builder-notes/round-1.md` exactly (5 new files under
  `domain/backtest/`, 1 new test file, `brief.md` modified). No undisclosed
  changes.
- `ruff check` and `mypy` on the new module: clean, independently re-run
  (not just trusting Builder's report).
- `pytest tests/unit/test_momentum_backtest.py`: 9/9 pass, independently
  re-run.

## Summary

No brief violations found. One judgment call accepted outright (Finding 4).
One judgment call accepted conditionally, with an explicit open-items list
and a 4-round escalation trip-wire (Finding 6). Everything Builder claimed
as hand-verified was independently reproduced with fresh inputs, plus a
mutation test the Builder note didn't itself run inline (Finding 7).

This round's actual deliverable (signal, eligibility, ranking/tie-break,
cost calc) is sound and matches the brief. It is not a backtest yet — items
7/8/9/10/13/14 stay open pending infra/application-layer work, tracked per
Finding 6.

VERDICT: PASS
