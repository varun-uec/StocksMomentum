# Reviewer findings — Loop 3, round 1

Verified against commit `8b12e58` (builder note: `handoff/builder-notes/round-1.md`),
diffed against `d37cbb5` (last Approximations-loop commit). Full checklist
re-run fresh per protocol, not just the items Builder claims changed.

## Item 8 — Survivorship (delisted securities) [RUN]

Classification: no finding (claim verified).

What was run:
- `pytest tests/integration/test_walk_forward_market_data_providers.py -q`
  against `momentum25_test` → 9 passed, including the 3 new survivorship
  tests, fresh in this session (not relayed from Builder's note).
- Mutation test on item 12 (vacuous-test check): edited
  `SqlSurvivorshipEligibilityProvider.facts_as_of` to change
  `decision_date > delisted` to `decision_date >= delisted`, re-ran the 3
  survivorship tests. `test_survivorship_provider_includes_delisted_security_before_delisting`
  went red (`assert 1 in set()`) as expected; reverted the file afterward.
  Confirms the test is not vacuous — it actually exercises the boundary.
- Queried `momentum25` (prod) DB directly:
  `select symbol, listing_date, last_trade_date, delisting_date, is_active
  from securities where symbol in ('GRUH','IL&FSENGG','IL&FSTRANS')`.
  Independently confirmed (not from Builder's note): GRUH delisting_date
  2019-10-15, IL&FS Engg 2018-10-15, IL&FS Transportation 2019-03-29 — all
  match public record. `count(*) filter (where delisting_date is not null)`
  = 596, matching Builder's reported `delisted=596`.
- Ran the real `SqlSurvivorshipEligibilityProvider` against the prod DB in a
  scratch script, looked up GRUH's `security_id`, and called
  `facts_as_of(date(2019,10,15))` vs `facts_as_of(date(2019,10,16))`.
  Expected: present in the first, absent in the second. Observed: exactly
  that (`in before? True`, `in after? False`).
- Ran `python -m momentum25.interface.cli.main walk-forward 2024-01-01
  2024-03-01` against the prod DB directly (not via Builder's captured
  output) — completed, printed the new warning, 3 rebalances / 103 trades,
  7.50% return, matches the builder note's numbers.
- Checklist item 13 ("forked safety net") applied to this same provider:
  monkeypatched `SqlSurvivorshipEligibilityProvider.facts_as_of` with a spy
  wrapping the original, ran `_run_walk_forward` directly (not through the
  CLI wrapper) for the same date range. Spy fired for all 3 decision dates
  (`2023-12-29`, `2024-01-31`, `2024-02-29`) — confirms the provider is
  actually on the live code path, not defined-but-unused.

Expected vs. observed: all match. `delisting_date` in this schema is
documented (`domain/research/survivorship.py`) as the inclusive last
observed trading date, not the effective delisting date, so inclusion on
that date and exclusion the day after is the correct semantics per that
definition — verified this isn't an off-by-one bug before ruling it out.

## Item 13 — Point-in-time Nifty 500 / T2T / ASM membership [RUN]

Classification: Judgment call (accepted).

What was run:
- `grep -rn "in_nifty_500\s*=\s*True\|is_t2t\s*=\s*False"
  src/momentum25/infrastructure/persistence/repositories/walk_forward_market_data.py`
  — confirms both `StubAllActiveSecuritiesEligibilityProvider` and the new
  `SqlSurvivorshipEligibilityProvider` hardcode membership/surveillance as
  stub values, discoverable directly from code, not just from this addendum
  or the module docstring.
- `grep -rln "total_return_index\|is_survivorship_free\|point_in_time_membership"
  src/` — no hits. No field/output claims real point-in-time membership
  anywhere.
- Confirmed via the CLI run above that `SURVIVORSHIP_ELIGIBILITY_WARNING` is
  printed to stdout on every `walk-forward` invocation, and states plainly
  that membership/T2T/ASM remain stub while survivorship is real — the two
  gaps are no longer bundled under one blanket "stub" label as in the prior
  loop, per `brief-addendum-loop3.md`'s requirement that this not be a
  silent skip a second time.
- `StubAllActiveSecuritiesEligibilityProvider` still exists and is still
  covered by its own two tests (`grep -rn
  StubAllActiveSecuritiesEligibilityProvider src/ tests/`) — not deleted, per
  the addendum's explicit instruction to keep it as a fallback/dev tool.

This is a judgment call, not a violation, because `brief-addendum-loop3.md`
§1 explicitly allows "still not obtainable, documented attempt" as a
legitimate outcome for this round. Builder's round note documents nine
concrete endpoint guesses tried and their `404` results, and states plainly
that blind endpoint-guessing was abandoned rather than continued
indefinitely — this is the kind of documented attempt the addendum asks for,
not a silent skip. I could not independently reproduce the nine endpoint
attempts (my own `curl -sS --max-time 8 https://www.nseindia.com/` from this
review session timed out / returned no response — exit 92 — a different
result from Builder's claimed "TCP/TLS reachable with a warmed session"),
but a difference in network path or tooling (curl vs. a scripted
cookie-jar session Builder describes) is plausible and doesn't contradict
the claim; I'm not treating an unreplicated network result as grounds to
reject a documented-attempt judgment call the addendum already accepts as a
legitimate round-1 outcome. Accepted.

## Items 1–7, 9–12, 14 [RUN where applicable]

Classification: no finding.

- `git diff d37cbb5 --stat -- src/momentum25/domain/backtest/
  src/momentum25/application/use_cases/` → 0 lines changed. Regression
  requirement from `brief-addendum-loop3.md` §2 ("Regression on everything
  frozen") holds: `domain/backtest/`, `walk_forward.py`,
  `SqlPriceHistoryProvider`, `SqlBenchmarkProvider` untouched this round.
- Full suite: `pytest -q` against `momentum25_test`, run fresh in this
  session → 633 passed, matching Builder's reported count. Items 1-7, 9-12,
  14 (formula, skip-month, look-ahead, universe, NaN handling, tie-break,
  corporate actions, fill timing, transaction costs, benchmark/attribution)
  were all previously verified [RUN] in Loops 1-2 and the Approximations
  loop against code that is unchanged this round (confirmed by the zero-diff
  check above), so re-verifying via full-suite pass is the correct scope for
  this round rather than repeating every hand-calculation against unchanged
  code.

## Vacuous-test check (item 12), applied to this round's new tests specifically

Classification: no finding (see Item 8 above — mutation test performed,
tests are not vacuous).

---

VERDICT: PASS
