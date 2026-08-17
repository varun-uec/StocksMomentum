# Escalation — cannot start round N

Raised by: Reviewer, first invocation.

## Blockers

1. **Round number unspecified.** The task prompt says "This is round N =
   [FILL IN]" and was never filled in.
2. **`brief.md` is still DRAFT.** Sections 1, 2 (skip-month, weights), 3
   (portfolio size, tie-break), 4 (weighting), 5 (rebalance date), 6
   (exit/re-entry buffer), 7 (cost model), 8 (benchmark) are all `[FILL IN]`.
   The brief itself states this must be completed before round 1 starts,
   and names the exact failure mode this is meant to prevent (the prior
   "wrong model provider for two rounds" incident).
3. **No `builder-notes/` directory exists.** There is no `round-N.md` claim
   from Builder to verify against.
4. **No `reviewer-findings/` directory exists yet** (created empty as part
   of this escalation).

## Why this can't be resolved by Reviewer or Builder alone

The brief is the fixed point both agents measure against (loop-protocol.md
mechanical-escalation trigger: "any finding touching the fixed point both
agents measure against ... can't be resolved by more Builder iteration,
only by a human clarifying the brief"). Filling in universe rules, weights,
portfolio size, tie-break, buffer, cost model, and benchmark are business-rule
decisions — CLAUDE.md prohibits inventing business rules, APIs, or
configuration when information is missing.

## Action needed from human

- Fill in `handoff/brief.md` sections 1, 2, 3, 4, 5, 6, 7, 8.
- Confirm round number N (appears round 1, since no builder-notes exist).
- Have Builder run round 1 and write `handoff/builder-notes/round-1.md`
  before Reviewer is invoked again.

No code was changed. No checklist items were run in this session — running
them against an undefined brief would have meant guessing the ground truth,
which is the failure this loop is designed to prevent.
