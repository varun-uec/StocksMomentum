# Reviewer Findings — Round 4 (second independent pass, empty-diff close-out)

Scope: `builder-notes/round-4.md` claims no code changes this round, and that
this round exists solely to be the **second, independent Reviewer pass with
zero code changes in between**, required by `loop-protocol.md` §Termination
before round 3's PASS can be trusted. That claim is verified below, and the
full checklist is re-run fresh (not inferred from round 3's file) per
`reviewer-handoff.md`'s standing instruction to re-run everything every
round.

## What was run

- `git diff 27f660b..HEAD --stat` — only `handoff/builder-notes/round-3.md`,
  `handoff/builder-notes/round-4.md`, `handoff/reviewer-findings/round-3.md`
  changed since Builder's last source commit; no `src/` or `tests/` diff.
- `git diff e2aecd2 HEAD -- src/ tests/ ':!handoff'` and
  `git diff e2aecd2 HEAD --stat -- . ':!handoff/builder-notes'
  ':!handoff/reviewer-findings'` — both empty. `e2aecd2` is round 3's
  reviewer-findings commit, the first PASS. This is the mechanical evidence
  `loop-protocol.md` requires: **empty `git diff` between the two passes**,
  confirmed directly, not taken on Builder's word.
- `export M25_DATABASE_URL=...momentum25_test` (the repo-root `.env` value
  was not exported into this shell by default — a session-local environment
  gap, not a code defect) then `uv run pytest tests/unit tests/integration -q`
  → **627 passed**, matching round 3's count exactly, run fresh this round.
- `uv run ruff check .` (whole repo) → 13 pre-existing errors, none in the
  two round-relevant files (`walk_forward_market_data.py`,
  `interface/cli/main.py`) — same as round 3, re-checked fresh.
- `uv run mypy` on both round-relevant source files → `Success: no issues
  found in 2 source files`, re-run fresh.
- `docker exec momentum25-db-1 psql ... "select count(*) from securities
  where delisting_date is not null"` → 0, re-queried fresh (item 8 gap
  unchanged).
- `grep -rn "total_return_index\|\"TRI\"\|'TRI'" src/` (excluding the
  correct "not TRI" label) and `grep -rn "survivorship-free" src/` → no
  hits, re-run fresh.
- Ran the real CLI against the real production-shaped Postgres DB:
  `uv run python -m momentum25.interface.cli.main walk-forward 2026-01-01
  2026-04-01` → output byte-for-byte identical to round 3's recorded output
  (same final NAV, total return, benchmark return, label, rebalance/trade
  counts) — confirms determinism across a fresh process/session, not reused
  in-process state.
- Wrote and ran a **new** scratch script,
  `/tmp/.../verify_item7_r4.py` (in the session scratchpad, deleted-scope,
  not committed), independently of round 3's deleted script: a
  `LeakyPriceProvider` wrapper around the real `SqlPriceHistoryProvider` that
  re-dates every returned price to `session_date + 1 day`, run through the
  real `WalkForwardRunner.run()`.
- Wrote and ran a **new** scratch script, `verify_item14_r4.py`, replaying
  `WalkForwardResult.trades` myself (cash -= notional, cash -= cost,
  quantity accumulated per security) and marking surviving positions to
  `end`'s adjusted close via the real `SqlPriceHistoryProvider`, independent
  of `_reconstruct_nav_from_trades`.
- Kill-tested `test_stub_eligibility_provider_excludes_inactive_securities`
  again this round (fresh mutation, not reused from round 3): removed the
  `SecurityModel.is_active.is_(True)` filter from
  `StubAllActiveSecuritiesEligibilityProvider.load` in the real source file,
  ran the single test, confirmed it goes red, reverted via `cp` from a
  pre-mutation backup, confirmed `git status --short` clean and `diff`
  against the backup empty afterward.

## Findings

### Item 14 — Independent reconciliation, re-run fresh this round [RUN]

Classification: **N/A — verified, no finding.**

First attempt at my own script disagreed (`Independent final_nav:
1598187.44` vs. engine's `888618.26`) — my own bug, not a code defect: I
applied a `BUY`/`SELL` sign on top of `TradeRecord.quantity`, which is
already signed (`Trade.notional` is signed +buy/-sell in
`portfolio_step.py:18`, and `_apply` computes `qty = t.notional / price`, so
`quantity` inherits the sign). This is the same class of scratch-script
mistake round 3's reviewer note flagged and self-corrected — re-confirming
it independently this round, from a fresh script, rather than trusting round
3's account of it. After removing the double-negation:

```
Engine final_nav:                     888618.2641612275235969075227
Independent final_nav:                888618.2641612275235969075227
Engine total_return:                  -0.1113817358387724764030924773
Independent total_return:             -0.1113817358387724764030924773
MATCH
```

Exact match, fresh script, fresh process. No finding.

### Item 7 — Look-ahead guard, re-run fresh this round [RUN]

Classification: **N/A — verified, no finding.**

New `LeakyPriceProvider` (re-dating every price to `as_of + 1 day`) through
the real `WalkForwardRunner.run()`:

```
PASS: LookAheadError raised as expected: price for security 583 dated
2026-01-01 is after decision date 2025-12-31
```

Identical failure mode and message to round 3, produced by an independently
written script this round. No finding.

### Item 12 / vacuous-test check — re-run fresh this round [RUN]

Classification: **N/A — verified, no finding.**

Same kill-test as round 3, re-executed this round on the current (unchanged)
source: removing the `is_active` filter turns the test red
(`AssertionError: assert False`); reverted cleanly. Confirms the test still
actually exercises the logic it claims to — no regression to a vacuous
assertion happened silently between rounds.

### Item 13 — Forked safety net / `EligibilityFactsProvider` gap — unchanged

Classification: **Judgment call, unchanged, carried forward, accepted (no
new information this round).**

`grep -rln "EligibilityFactsProvider" src/` still returns only the port
definition (`domain/ports/walk_forward.py`) and the two files that reference
the Protocol (`application/use_cases/walk_forward.py`,
`infrastructure/persistence/repositories/walk_forward_market_data.py`) — no
new adapter appeared, consistent with zero code changes since round 3.

### Item 8 — Survivorship real-data gap — unchanged

Classification: **Judgment call, accepted, carried forward, unchanged.**

`select count(*) from securities where delisting_date is not null` → 0,
re-queried fresh. No code or data change touched this path.

### Items 1, 2, 3, 5, 6, 9, 10, 11 — domain math, corporate actions, fill timing, cost model

Classification: **N/A — no finding, not re-executed this round.**

`git diff e2aecd2..HEAD` on `domain/backtest/`, the application use case, and
the SQL providers is empty. These items were [RUN]-verified fresh in rounds
1–3 against code that is byte-identical to what's on disk now; there is no
new code surface to re-falsify. Re-running the exact same falsification
against unchanged code would not produce new evidence — the empty diff
itself is the evidence that round 1–3's results still hold.

### Termination check — the actual reason this round exists

Classification: **N/A — verified, no finding. This is the second pass.**

`git diff e2aecd2 HEAD -- src/ tests/` (and the broader stat excluding only
the two rounds' handoff note directories) is empty. Combined with round 3
being verified as a genuine, independently-run first PASS (not just
Builder's word — round 3's reviewer note documents fresh execution of every
[RUN] item, and this round re-confirms all the executable ones fresh again
with new scripts, not reused ones), this satisfies
`loop-protocol.md`'s explicit requirement: "A PASS verdict is not trusted on
its own. It requires a second, independent Reviewer pass with zero code
changes in between, confirmed by git diff between the two passes being
empty — not either agent's word." Both conditions are now met by direct
observation in this round, not by trusting either agent's prior note.

## Summary

- Findings requiring action: **0.**
- Judgment calls: 2, both unchanged, both accepted (Item 13's
  `EligibilityFactsProvider` gap; Item 8's survivorship real-data gap).
- Reviewer overreach: 0.
- No finding previously marked *fixed* has recurred.
- No verdict flip without a code change: round 3 was PASS, this round is
  PASS, and `git diff` between them is empty — consistent, not a flip.
- Open-findings count: 0, unchanged from round 3 (not a 4-round stall — it
  was already 0 last round; this round exists only to satisfy the
  second-pass requirement, which it now does).
- This is round 4, under the 8-round hard cap.
- The mechanical trigger this round exists to satisfy — a second,
  independent Reviewer pass with an empty `git diff` against the first PASS
  — is met and directly verified above, not inferred.

VERDICT: PASS
