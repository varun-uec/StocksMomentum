# Reviewer findings — Loop 3, round 2 (second independent pass)

Purpose of this round per `loop-protocol.md` Termination: confirm round-1's
`PASS` with a second, independent Reviewer pass with zero code changes in
between, verified by `git diff` — not either agent's word. This pass was run
fresh, from scratch, without relying on round-1's findings file as ground
truth; round-1's numbers are cited only afterward, as corroboration.

## Zero-code-change confirmation

What was run: `git log --oneline -8`, `git diff efc48a9 HEAD --stat`,
`git status`.

Observed: `HEAD` is `23ef183` (builder's round-2 commit). The only change
since `efc48a9` (the commit round-1 verified) is the addition of
`handoff/builder-notes/round-2.md` — 46 insertion lines, zero source files
touched. Working tree clean. This satisfies the protocol's mechanical
requirement for a trusted `PASS`.

## Full suite [RUN]

What was run: `cd backend && M25_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:55432/momentum25_test pytest -q`
(test DB was already provisioned on the running `momentum25-db-1` container,
port 55432; only had to export the env var this session — a fresh setup
step, not inherited from round-1's session).

Expected vs. observed: 633 passed, 0 failed — matches round-1's reported
count exactly, obtained independently.

## Item 8 — Survivorship (delisted securities) [RUN]

Classification: no finding (claim re-verified independently).

What was run:
- Fresh scratch script against the prod DB (`momentum25`, not `_test`):
  queried `securities` for `symbol='GRUH'` directly, got
  `(id=9992, delisting_date=2019-10-15)`. Then instantiated the real
  `SqlSurvivorshipEligibilityProvider.load(session)` and called
  `facts_as_of(date(2019,10,15))` vs `facts_as_of(date(2019,10,16))`.
  Observed: `sid in before` → `True`, `sid in after` → `False`. Matches the
  brief's "included up to delisting, excluded after" semantics and
  round-1's finding, reproduced independently rather than re-read.
- Mutation test on `facts_as_of`: changed
  `decision_date > delisted` → `decision_date >= delisted` on the live
  source file, ran `pytest tests/integration/test_walk_forward_market_data_providers.py -k survivorship`.
  Observed: `test_survivorship_provider_includes_delisted_security_before_delisting`
  goes red (`assert 1 in set()`), 1 failed / 2 passed. Confirms the test
  actually exercises the boundary — not vacuous (item 12). File restored
  from backup immediately after; `git status` confirms clean afterward, all
  9 tests in that file pass again.
- Live CLI run: `python -m momentum25.interface.cli.main walk-forward
  2024-01-01 2024-03-01` against the prod DB. Observed: prints
  `SURVIVORSHIP_ELIGIBILITY_WARNING`, 3 rebalances, 103 trades, 7.50% total
  return, 4.52% benchmark return — matches round-1's captured numbers
  exactly, reproduced fresh.
- Forked-safety-net check (item 13's mechanism, applied to this provider):
  monkeypatched `SqlSurvivorshipEligibilityProvider.facts_as_of` with a spy
  wrapping the original, called `_run_walk_forward` directly (the actual CLI
  entry point's async function, not a hand-built harness), same date range.
  Observed: spy fired for exactly 3 decision dates
  (`2023-12-29`, `2024-01-31`, `2024-02-29`) — confirms the provider sits on
  the live execution path, not defined-but-unused.

## Item 13 — Point-in-time Nifty 500 / T2T / ASM membership [RUN]

Classification: Judgment call (accepted) — unchanged from round-1, re-verified.

What was run:
- `grep -rln "total_return_index\|is_survivorship_free\|point_in_time_membership" src/`
  → no hits. No field anywhere falsely claims point-in-time membership.
- `grep -rn StubAllActiveSecuritiesEligibilityProvider src/ tests/` → 6 hits;
  the stub still exists in the codebase and its tests, per the addendum's
  explicit instruction not to delete it.
- Read `walk_forward_market_data.py` module docstring and
  `SURVIVORSHIP_ELIGIBILITY_WARNING`/`ELIGIBILITY_STUB_WARNING` constants
  directly (not relayed from round-1's note): both state plainly that
  membership/T2T/ASM remain stub while survivorship is real, and the CLI run
  above confirms the warning actually prints on a real invocation.

This remains a legitimate documented-attempt outcome under
`brief-addendum-loop3.md` §1 — no new sourcing attempt was required or made
this round (round-2 made no code changes), so there is nothing new to
evaluate on this item beyond re-confirming the documentation still matches
the code, which it does.

## Regression check on frozen paths [RUN]

What was run: `git diff efc48a9 HEAD --stat -- src/momentum25/domain/backtest/ src/momentum25/application/use_cases/walk_forward.py`
→ empty output, zero lines changed.

## Summary

Every item re-verified independently this round reproduces round-1's result
exactly, using fresh commands run in a new session rather than re-reading
round-1's findings file as ground truth. No regression, no new findings, no
disputed judgment calls, nothing recurring from a "previously fixed" state.
This is the confirming second pass the protocol requires: `git diff` between
the two Reviewer passes is empty (only a builder-notes file was added, no
source change), and the independent re-execution agrees with round-1's
result in every particular checked.

---

VERDICT: PASS
