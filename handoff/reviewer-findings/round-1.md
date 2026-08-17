# Reviewer Findings — round 1

Verified against `handoff/brief.md` (FINAL, 2026-08-17) and
`handoff/builder-notes/round-1.md` as a claim, not a summary.

## Checklist results

**Item 1 — Formula matches brief.** [RUN]
Ran an independent hand-calculation not present in Builder's test file:
`price_t=200, 3m ago=180, 6m ago=150, 12m ago=100` → r3=0.111111..., r6=0.333333...,
r12=1.0, composite=0.481481... Computed expected values in a separate Python
one-liner from raw arithmetic, compared to `compute_momentum_signal` output.
Expected: exact match. Observed: exact match (Decimal equality).
No finding.

**Item 2 — Skip-month.** Brief §2 explicitly says "Skip-month: none." Read
`momentum_signal.py`: all three returns are measured against the same
`price_t`, no skip parameter exists. Confirmed by the signature —
`compute_momentum_signal(security_id, price_t, price_3m_ago, price_6m_ago,
price_12m_ago)`, no gap/skip offset anywhere. No finding.

**Item 3 — Look-ahead in the signal.** [RUN]
`inspect.signature(compute_momentum_signal)` shows the function accepts only
four scalar Decimal prices, no date, no series, no clock. There is no channel
through which post-decision-date data could enter — this isn't a
skip-injection test against a series-consuming function, it's a pure
4-scalar-in/1-value-out function. Confirmed no I/O and no hidden state by
reading the module. Ran it twice with identical inputs, got identical output
(determinism). No finding.

**Item 4 — Universe construction.** Not independently runnable this round.
`eligibility.py` is a pure predicate over `EligibilityFacts`, not wired to
any universe-membership data source. Verified Builder's claim by grepping
`src/` for T2T/ASM/surveillance data sources: zero matches outside the new
domain module. No walk-forward/application-layer caller exists yet
(`grep -rl "domain.backtest"` outside `domain/backtest/` → no results), so
there is no injectable pipeline to register a synthetic instrument against.
Classification: not a finding against this round's code — see scope note
below.

**Item 5 — NaN / missing-data behavior.** [RUN]
`compute_return(Decimal('nan'), Decimal(100))` → raises
`decimal.InvalidOperation` from the `price_t <= 0` comparison itself (Decimal
NaN is unordered, so `<=` raises rather than evaluating False). Effect: NaN
input crashes rather than silently producing a NaN score or defaulting to 0 —
this satisfies "fail closed," but via an uncaught exception type
(`InvalidOperation`) rather than the module's own `ValueError`. Since no
caller/orchestration exists yet to observe how this exception propagates
(item 4's scope gap applies here too), I can't verify end-to-end that a
NaN-poisoned ticker gets excluded rather than crashing the whole batch.
Classification: **Judgment call** (logged, not disputed) — fail-closed intent
is met at the unit the brief can be checked against today; whether it stays
fail-closed at the batch level is undecided until orchestration exists.

**Item 6 — Ranking / tie-break.** [RUN]
Constructed a 3-way synthetic tie independently (not just re-running
Builder's test): signals with composite scores `0.10, 0.10, 0.10`, 12M
returns `0.30, 0.30, 0.10`, 6M returns `0.10, 0.20, 0.90`. Brief §3: tie-break
by 12M desc, then 6M, then 3M. Expected order: id=2 (12M=0.30,6M=0.20) rank 1,
id=1 (12M=0.30,6M=0.10) rank 2, id=3 (12M=0.10) rank 3. Ran
`rank_signals([a,b,c])` — observed exactly this order. Matches Builder's own
test (re-verified independently, not just re-read). No finding.

**Items 7–10, 13, 14 — Backtest integrity (look-ahead at rebalance level,
survivorship, corporate actions, fill timing, forked-safety-net,
benchmark/attribution).** Not executable. No walk-forward loop, no historical
price/universe data provider, no benchmark series exists in this round's
diff — confirmed by grep, matches Builder's own scope note. There is nothing
to falsify yet: no rebalance dates are actually run, no historical universe
snapshot is pulled, no corporate action is applied, no trade fill is logged.
Classification: **Judgment call**, not "Reviewer overreach" and not
"Brief violation" — see Scope discussion below. Accepted.

**Item 11 — Transaction costs.** [RUN]
Independent scenario not in Builder's tests: move `{1: 100}` → equal-weight
`{1, 3}` on portfolio value 300. Target each = 150. Trade for 1: +50 (buy).
Trade for 3: +150 (buy). Expected cost = (50+150) * 0.003 = 0.60.
Ran `plan_equal_weight_rebalance(frozenset({1,3}), {1: Decimal(100)},
Decimal(300))` → `total_cost == Decimal('0.6')`. Matches hand-calc. No
finding.

**Item 12 — Vacuous test check.** [RUN]
Independently re-implemented a hard-cutoff `select_portfolio` (`rank <= 30`
only, no buffer) outside the source tree and ran
`test_select_portfolio_hard_cutoff_would_be_a_brief_violation`'s scenario
(security 7, held, rank 35) against it. Expected: security 7 dropped under
the broken hard-cutoff logic (test should go red if swapped in). Observed:
`7 in result` → `False` under the hard-cutoff version, `True` under the real
`select_portfolio`. Confirms the test is not vacuous — it can fail. No
finding.

**Eligibility boundary (extension of item 4, self-directed).** [RUN]
Brief §1: "at least 12 months of adjusted-close price history." Builder's
`_MIN_LISTING_DAYS = 252` and test only checks 100 (fail) / 300 (pass) —
doesn't hit the boundary. Ran the boundary myself:
`listing_days_as_of_decision_date=252` → eligible=True;
`=251` → eligible=False. Matches "at least 12 months" (inclusive ≥) as the
sensible reading. No finding, but flagging that Builder's own test suite
doesn't cover this boundary — a coverage gap, not a correctness bug.

**Tooling.** `ruff check src/momentum25/domain/backtest
tests/unit/test_momentum_backtest.py` → all checks passed. `mypy
src/momentum25/domain/backtest` → 0 issues, 5 files. `pytest
tests/unit/test_momentum_backtest.py -v` → 9/9 passed. All independently
re-run, not taken from Builder's note.

## Scope discussion (items 4, 7–10, 13, 14)

Builder's round-1 scope is signal + eligibility predicate + ranking/tie-break
+ per-rebalance trade/cost pricing, as pure domain functions with no
orchestration or data-source wiring. This is a genuine gap against the
reviewer-handoff checklist — those items literally cannot be run.

I considered classifying this as a Brief violation (brief.md describes a
full walk-forward strategy) but the brief is a strategy spec, not a
milestone plan — it doesn't mandate what ships in round 1 of an iterative
loop. CLAUDE.md (binding per loop context) explicitly instructs "implement
only the current milestone" and "don't invent... data source[s]... for
missing information." Builder verified by grep that no T2T/ASM data source
exists anywhere in the codebase and declined to fabricate one. That is the
correct call under Don't Guess, not a shortcut.

Logged as: **Judgment call, accepted.** Everything checkable without that
missing data source (items 1, 3, 6, 11, 12, plus the self-directed boundary
check) was checked and passed independent verification. Items 4, 5
(end-to-end), 7–10, 13, 14 remain open for a future round once an
orchestration layer + historical data provider exists — they are not
"resolved," they're "not yet buildable," and should stay on the checklist
for round 2+ once that infrastructure lands. This is not registered as an
open finding requiring Builder rework in round 1; it's carried forward as
known future scope.

## Summary

- Findings requiring action: **0**
- Judgment calls logged: 2 (NaN failure mode at batch level — undecided
  pending orchestration; deferred backtest-integrity items — accepted scope
  split for this round)
- Reviewer overreach: 0
- All executable checklist items (1, 2, 3, 6, 11, 12, eligibility boundary)
  independently re-verified with fresh, non-Builder-authored scenarios and
  passed.
- Tooling (ruff, mypy, pytest) independently re-run and clean.

VERDICT: PASS
