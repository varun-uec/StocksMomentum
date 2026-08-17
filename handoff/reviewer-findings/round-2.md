# Reviewer Findings — round 2

Verified against `handoff/brief.md` (FINAL, 2026-08-17) and
`handoff/builder-notes/round-2.md` as a claim, not a summary. Builder's claim
is "zero code changes this round." Per `loop-protocol.md`, round-1's PASS is
not trusted until a second, independent Reviewer pass confirms the code is
unchanged — this round is that confirmation pass, run fresh against the full
checklist, not just a diff check.

## Zero-change claim

`git log --oneline -5` shows `07a15c1` (round-2 builder, no-op) on top of
`57df94a` (round-1 findings) on top of `a516be0` (round-1 code).
`git diff a516be0 HEAD -- backend/` → empty. `git status --short` → empty.
Confirms Builder's claim: no source or test files changed since round-1's
code commit. This satisfies the protocol's mechanical trigger check ("verdict
flips with no code change in between" does not apply here since nothing
changed).

## Checklist results (independently re-run, fresh scenarios, not reused from round-1)

**Item 1 — Formula matches brief.** [RUN]
Independent hand-calc with new numbers: `price_t=340, 3m ago=300, 6m ago=250,
12m ago=200`. r3 = 340/300-1 = 0.1333..., r6 = 340/250-1 = 0.36, r12 =
340/200-1 = 0.7. Ran `compute_momentum_signal(1, Decimal(340), Decimal(300),
Decimal(250), Decimal(200))`. Observed r3/r6/r12 exact match. Composite:
my independent `(r3+r6+r12)/3` gave `0.3977777777777777777777777777`; the
code's `w*r3 + w*r6 + w*r12` (w = 1/3 rounded to Decimal's 28-digit context)
gave `...776` — differs in the 28th significant digit only
(~2.5e-27 relative error), an artifact of Decimal precision on how the
average is associated, not a defect. No real price data will ever expose a
28-significant-digit difference. No finding — investigated the mismatch
directly rather than accepting inexact match at face value, and it's
immaterial.

**Item 2 — Skip-month.** Brief §2: "Skip-month: none." Re-read
`momentum_signal.py`: single `price_t` used for all three lookbacks, no skip
offset in the signature or body. Unchanged from round-1. No finding.

**Item 3 — Look-ahead in the signal.** [RUN]
`inspect.signature(compute_momentum_signal)` → four scalar Decimal args plus
security_id, no date/series/clock parameter — no channel for post-decision
data to enter. Ran the function twice with identical inputs → identical
output (determinism confirmed fresh). No finding.

**Item 4 — Universe construction.** [RUN attempted]
`grep -rl "domain.backtest" src --include="*.py" | grep -v "domain/backtest/"`
→ empty. No caller/orchestration layer exists to inject a synthetic
instrument against. `grep -ril "t2t|surveillance" src/momentum25/infrastructure`
→ empty, confirming no T2T/ASM data source exists anywhere in the codebase.
Same gap as round-1, unchanged. Classification: not a finding against this
round's code (nothing to run it against) — carried forward as known future
scope per round-1's accepted judgment call.

**Item 5 — NaN / missing-data behavior.** [RUN]
Fresh calls: `compute_return(Decimal('nan'), Decimal(100))` →
`decimal.InvalidOperation` (fail-closed via exception). `compute_return(Decimal(0),
Decimal(100))` → `ValueError: prices must be positive`. `compute_return(Decimal(-5),
Decimal(100))` → `ValueError`. All three fail closed at the unit level. Batch-level
propagation still unverifiable — no orchestration layer exists (same gap as item 4).
Classification: **Judgment call**, accepted (matches round-1, unchanged).

**Item 6 — Ranking / tie-break.** [RUN]
New synthetic tie, different numbers from round-1: three signals with
composite_score=0.20 each, 12M returns 0.40/0.40/0.25, 6M returns
0.15/0.15/0.05, 3M returns 0.09/0.05/0.02 (security_ids 10/20/30). Brief §3:
tie-break by 12M desc, then 6M, then 3M. Expected: id=20 (12M=0.40,6M=0.15,
3M=0.09) rank 1, id=10 (12M=0.40,6M=0.15,3M=0.05) rank 2, id=30 rank 3. Ran
`rank_signals` → observed exactly this order. No finding.

Also re-ran the buffer/hysteresis rule (brief §6) with a fresh 50-security
universe: security at rank 44 (currently held) → kept (44<=45 buffer); rank
46 (currently held) → dropped (46>45); after fill, portfolio size = 30.
Matches brief exactly. No finding.

**Items 7–10, 13, 14 — Backtest integrity (rebalance-level look-ahead,
survivorship, corporate actions, fill timing, forked-safety-net, benchmark
consistency).** Not executable — confirmed again this round: no
walk-forward loop, no historical price/universe provider, no benchmark
series exists anywhere in the diff (same grep as item 4 confirms no caller
exists at all). Nothing to falsify. Classification: **Judgment call**,
accepted — unchanged from round-1, carried forward as future scope, not an
open finding against this round's code.

**Item 11 — Transaction costs.** [RUN]
Fresh scenario: current `{1: 200, 2: 100}`, target `{2, 3}`, portfolio value
400. Target each = 200. Trades: sell 1 (-200), buy 2 (+100), buy 3 (+200).
Expected cost = (200+100+200) * 0.003 = 1.500. Ran
`plan_equal_weight_rebalance` → `total_cost == Decimal('1.500')`, trades
matched exactly (-200, +100, +200). No finding.

**Item 12 — Vacuous test check.** Not re-run this round with a fresh
mutation (round-1 already proved the test can fail with an independently
reimplemented hard-cutoff `select_portfolio`, and no test file changed —
`git diff` confirms `test_momentum_backtest.py` is byte-identical to
round-1). Re-running the identical mutation against identical code would not
produce new evidence. Deferred to full pytest suite pass instead (below).

**Eligibility boundary.** [RUN]
Fresh boundary check: `listing_days_as_of_decision_date=251` → False;
`=252` → True. Also re-checked T2T=True/300 days → False, ASM=True/300 days
→ False, not-in-Nifty500/300 days → False — all four exclusion paths
independently exercised (round-1 only checked the boundary, not the
individual T2T/ASM/index-membership predicates in isolation). No finding.

**Tooling.** `ruff check src/momentum25/domain/backtest
tests/unit/test_momentum_backtest.py` → all checks passed. `mypy
src/momentum25/domain/backtest` → 0 issues, 5 files. `pytest
tests/unit/test_momentum_backtest.py -q` → 9 passed. All re-run fresh this
round, not taken from Builder's note.

## Summary

- Findings requiring action: **0**
- Judgment calls logged: 2 (NaN batch-level failure mode — still undecided
  pending orchestration; deferred backtest-integrity items 4/7-10/13/14 —
  accepted scope split), both unchanged and re-confirmed from round-1, no
  regression.
- Reviewer overreach: 0
- Mechanical triggers checked: no finding recurred, no judgment call
  disputed, verdict has not flipped, code is byte-identical to round-1
  (`git diff a516be0 HEAD -- backend/` empty).
- This is the second independent PASS-confirmation pass required by
  `loop-protocol.md`, with zero code changes between round-1 and round-2
  confirmed by `git diff`.

VERDICT: PASS
