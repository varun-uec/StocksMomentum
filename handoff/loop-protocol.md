# Loop Protocol — Momentum Signal & Backtest Integrity

Two Claude Code sessions (Builder, Reviewer), zero shared context, communicating
only through files in `/handoff/`. Scope for this loop: momentum signal/indicator
correctness and backtest integrity (look-ahead bias, survivorship, cost
assumptions). Live execution/order logic is explicitly out of scope for this run.

## Roles

**Builder**
- Implements fixes/changes to signal generation and backtest code.
- Runs its own tests, writes a status note in `/handoff/builder-notes/round-N.md`.
- Never scores its own work as PASS. Builder proposes; Reviewer disposes.
- Must not touch anything under `/handoff/reviewer-findings/`.

**Reviewer**
- Never edits code. Only files findings in `/handoff/reviewer-findings/round-N.md`.
- Re-runs the full checklist (`reviewer-handoff.md`) fresh every round — not just
  the items that failed last time. A clean prior item can regress silently if
  only diffs are checked.
- Ends every round with a machine-parsed line: `VERDICT: PASS|FAIL|ESCALATE`.

## Round structure

1. Builder reads latest `reviewer-findings/round-(N-1).md`, acts on it, writes
   `builder-notes/round-N.md` (what changed, why, which findings addressed,
   commit hash / git diff reference).
2. Reviewer reads the Builder note as a **claim to verify**, not a summary to
   relay. Reviewer independently re-runs the checklist against running code —
   see evidentiary bar in `reviewer-handoff.md`.
3. Reviewer files `reviewer-findings/round-N.md` with every finding classified
   (see below) and a `VERDICT` line.

## Finding classification (non-negotiable)

Every finding gets exactly one label. Nobody may reclassify a finding purely to
make it easier to dismiss.

- **Brief violation** — contradicts the strategy spec / brief (e.g. spec says
  12-1 month momentum with skip-month, code implements 12-0). Builder must fix.
  No debate.
- **Judgment call** — a reasonable implementation choice not dictated by the
  brief (e.g. how ties in ranking are broken, which volatility lookback to use
  for a vol-scaling overlay).
  - Logged as accepted if Reviewer agrees it's reasonable.
  - If Reviewer disputes it: Builder gets **one rebuttal**. If Reviewer still
    disagrees after the rebuttal, Builder must implement Reviewer's preferred
    approach, or escalate to a human. Builder may not simply hold its position
    and move on to the next item.
- **Reviewer overreach** — Reviewer is requiring something the brief doesn't
  ask for. Builder can push back once, citing the specific brief passage. If
  unresolved after that, it escalates to a human — Reviewer does not get to
  unilaterally insist either.

A finding never leaves the list because one agent decided on its own that it
doesn't apply. It leaves the list via: fix + reverification, accepted judgment
call, or escalation.

## Termination

- A `PASS` verdict is not trusted on its own. It requires a **second,
  independent Reviewer pass with zero code changes in between**, confirmed by
  `git diff` between the two passes being empty — not either agent's word.
- Mechanical triggers that force escalation to a human, regardless of what
  either agent thinks:
  - A finding that was marked fixed recurs in a later round.
  - A disputed judgment call survives Builder's rebuttal and Builder still
    hasn't implemented Reviewer's approach or escalated.
  - A verdict flips (PASS→FAIL or FAIL→PASS) between rounds with no code
    change in between.
  - 4+ rounds pass without the open-findings count shrinking.
  - Any finding touching the **fixed point both agents measure against**
    (e.g. which price series is "ground truth," what the benchmark index is,
    what "no look-ahead" means operationally for this codebase) — these can't
    be resolved by more Builder iteration, only by a human clarifying the
    brief. Escalate immediately on discovery, don't wait for round limits.
- Hard cap: 8 rounds. If not resolved by round 8, escalate with full history.

## File layout

```
/handoff/
  brief.md                        # strategy spec, ground-truth definitions
  reviewer-handoff.md             # Reviewer's evidentiary standard + checklist
  builder-notes/round-N.md
  reviewer-findings/round-N.md    # ends with VERDICT: PASS|FAIL|ESCALATE
  escalations/round-N.md          # human-readable summary when escalation fires
```
