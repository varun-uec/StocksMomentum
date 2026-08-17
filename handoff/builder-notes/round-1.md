# Builder Notes — round 1

## Precondition: brief was completed before this round

`brief.md` was still DRAFT (8 `[FILL IN]` sections) when Reviewer escalated
in `reviewer-findings/round-1.md` / `escalations/round-0.md`. Per
loop-protocol.md this is a fixed-point issue only a human can resolve, so no
code was written until the human filled in `brief.md` sections 1-8 (universe,
skip-month/weights, portfolio size/tie-break/weighting, rebalance mechanics,
exit/re-entry buffer, transaction costs, benchmark). That version of
`brief.md` is what this round implements against. Round number is 1 — no
`builder-notes/` existed before this file.

## What changed

New package `backend/src/momentum25/domain/backtest/` (pure domain, no I/O):

- `momentum_signal.py` — `compute_return`, `compute_momentum_signal`: brief §2
  composite score, no skip-month, equal weights (w3=w6=w12=1/3). Rejects
  non-positive prices (data-integrity fault, not a valid score input).
- `eligibility.py` — `EligibilityFacts`, `is_eligible`: brief §1 (Nifty 500
  membership, >=252 trading days history, not T2T, not under ASM/surveillance).
- `rebalance.py` — `rank_signals` (brief §3 tie-break: composite score desc,
  then 12M, then 6M, then 3M return, all deterministic), `select_portfolio`
  (brief §6 buffer/hysteresis: existing holdings survive to rank 45, new
  entries need rank <=30).
- `portfolio_step.py` — `plan_equal_weight_rebalance`: brief §4 equal
  weighting and brief §7 transaction cost (30bps on each trade's notional,
  buy and sell, on traded notional not NAV).

`backend/tests/unit/test_momentum_backtest.py` — 9 tests, all with
hand-computed expected values in the test body (not traced from the
implementation):

- `test_compute_return_hand_calculated`, `test_composite_score_equal_weight_hand_calculated`
  — arithmetic worked out in the test comment (e.g. price 110 vs {100,100,55}
  → (10%+10%+100%)/3).
- `test_compute_return_rejects_non_positive_price` — fail-closed on bad data.
- `test_eligibility_requires_all_conditions` — each of the 4 brief §1
  conditions independently flips eligibility to False.
- `test_rank_signals_tie_break_by_12m_then_6m_then_3m` — three signals with
  equal composite score, cascading tie-break verified by hand.
- `test_select_portfolio_buffer_keeps_existing_holding_outside_top_30` +
  `test_select_portfolio_hard_cutoff_would_be_a_brief_violation` — the buffer
  is brief §6's explicit non-negotiable; I ran a hand-rolled `rank <= 30`
  hard-cutoff version of `select_portfolio` outside the test suite and
  confirmed it goes red on the regression test (not a vacuous test — see
  command in this round's session, reproducible: swap `select_portfolio`'s
  body for `{r.signal.security_id for r in ranked if r.rank <= PORTFOLIO_SIZE}`
  and rerun).
- `test_plan_equal_weight_rebalance_cost_hand_calculated` +
  `..._sells_dropped_holding_in_full` — cost hand-calculated as
  `abs(notional) * 0.003`, no-op trades omitted, dropped holdings sold in full.

Look-ahead (brief §9, checklist item 3): `compute_momentum_signal`'s
signature only accepts `price_t` and three lookback prices — there is no
parameter through which a later-dated price can enter. Verified by calling it
twice with identical inputs and confirming identical output (determinism),
and by inspection that no clock/date-range/database access exists in the
module (it's pure, no I/O per CLAUDE.md domain-layer rules).

All: `ruff check` clean, `mypy` clean (0 issues, 5 source files), `pytest`
9/9 pass.

## Scope boundary (flagging as a judgment call)

This round implements the **signal, eligibility rule, ranking/tie-break, and
per-rebalance trade-and-cost step** as pure domain functions. It does not
wire a full walk-forward loop against real price/universe data (application
use case + infra data providers: historical adjusted-close series, Nifty 500
membership history, ASM/T2T status feed, benchmark TRI series).

Reason: no ASM/T2T/surveillance data source exists anywhere in this
codebase today (confirmed by grep — zero matches for ASM/surveillance/T2T in
`infrastructure/`). Brief §1 requires excluding these; I am not fabricating
that data or defaulting it to "always clean," per CLAUDE.md's "Don't Guess"
(never invent business rules/config for missing information). `eligibility.py`
models the fields so the rule is correct the day that data exists, and its
docstring states this gap explicitly rather than hiding it.

Given that, a full historical backtest run (checklist items 7-10, 13, 14)
isn't executable yet — those items need real historical universe/price data
that this round doesn't have a source for. I've implemented and tested
everything that's checkable without that data source: signal correctness
(item 1), look-ahead absence in the signal (item 3), tie-break determinism
(item 6), and the transaction-cost formula (item 11), all with hand-computed
expected values per reviewer-handoff.md's evidentiary bar.

If Reviewer judges this scope split unreasonable — e.g. expects a runnable
end-to-end backtest this round even without a surveillance data source (using
a documented stub/injectable port instead of leaving it unbuilt) — that's a
disputed judgment call I'm open to on rebuttal, but brief.md itself doesn't
mandate a specific data-source or infra-wiring milestone for round 1, and
CLAUDE.md's Scope Discipline says "implement only the current milestone" /
"do not implement speculative features."

## Git

Not committed — no commit made this round (repo convention: only commit when
explicitly asked). Working-tree diff for this round:

```
A  backend/src/momentum25/domain/backtest/__init__.py
A  backend/src/momentum25/domain/backtest/eligibility.py
A  backend/src/momentum25/domain/backtest/momentum_signal.py
A  backend/src/momentum25/domain/backtest/portfolio_step.py
A  backend/src/momentum25/domain/backtest/rebalance.py
A  backend/tests/unit/test_momentum_backtest.py
M  handoff/brief.md
```
