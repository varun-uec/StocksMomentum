#!/usr/bin/env bash
# Autonomous Builder/Reviewer loop driver.
# Requires: claude CLI (Claude Code) available on PATH, run from repo root.
# Usage: ./run-loop.sh
set -euo pipefail

HANDOFF="handoff"
MAX_ROUNDS=8
CONSECUTIVE_PASS=0   # tracks back-to-back PASS verdicts with empty git diff

mkdir -p "$HANDOFF/builder-notes" "$HANDOFF/reviewer-findings" "$HANDOFF/escalations"

builder_prompt() {
  local N=$1
  cat <<EOF
You are the Builder in a Builder/Reviewer loop. Read $HANDOFF/loop-protocol.md,
$HANDOFF/reviewer-handoff.md, $HANDOFF/brief.md,
$HANDOFF/brief-addendum-loop2.md, and
$HANDOFF/brief-addendum-approximations.md fully before doing anything.

This is round $N.

If $HANDOFF/reviewer-findings/round-$((N-1)).md exists, read it and act on every
finding in it. If this is round 1, there are no prior findings — implement the
initial version per brief.md.

Implement your changes, run your own tests, then write a status note to
$HANDOFF/builder-notes/round-$N.md covering: what changed, why, which findings
(if any) you addressed, and the git diff/commit hash for this round.

Do not mark anything as passing or resolved. Do not touch anything under
$HANDOFF/reviewer-findings/. If rebutting a disputed judgment call, cite the
specific brief passage. One rebuttal only; if Reviewer still disagrees after
that, implement Reviewer's preferred approach or flag for escalation.

Begin.
EOF
}

reviewer_prompt() {
  local N=$1
  cat <<EOF
You are the Reviewer in a Builder/Reviewer loop. Read $HANDOFF/loop-protocol.md,
$HANDOFF/reviewer-handoff.md, $HANDOFF/brief.md,
$HANDOFF/brief-addendum-loop2.md, and
$HANDOFF/brief-addendum-approximations.md fully before doing anything.

This is round $N.

Read $HANDOFF/builder-notes/round-$N.md as a claim to verify, not a summary to
relay. Every checklist item marked [RUN] requires you to actually execute
something and observe the result — no inferring correctness from reading code.

Run the FULL checklist fresh, including items that passed in prior rounds.
You may not edit code — only run things and file findings.

Classify every finding as exactly one of: Brief violation / Judgment call /
Reviewer overreach. No reclassifying to dismiss.

Write $HANDOFF/reviewer-findings/round-$N.md. Each finding must state: checklist
item, classification, what you actually ran, expected vs. observed result.

End the file with exactly one line: VERDICT: PASS|FAIL|ESCALATE

Begin.
EOF
}

extract_verdict() {
  grep -oE 'VERDICT:\s*(PASS|FAIL|ESCALATE)' "$1" | tail -1 | awk '{print $2}'
}

write_escalation() {
  local N=$1 reason=$2
  cat > "$HANDOFF/escalations/round-$N.md" <<EOF
# Escalation — round $N

Reason: $reason

Human review needed. See:
- $HANDOFF/builder-notes/round-$N.md
- $HANDOFF/reviewer-findings/round-$N.md
EOF
  echo "ESCALATED at round $N: $reason"
}

commit_round() {
  # Commits whatever Builder + the handoff files changed this round.
  # Reviewer never edits code, so this only ever captures Builder's diff
  # plus the note/findings files written this round.
  local N=$1 tag_suffix=$2
  git add -A
  if git diff --cached --quiet; then
    echo "Round $N: nothing to commit."
    return 1   # signals "no code change" to caller
  fi
  git commit -m "loop: round $N ($tag_suffix)" >/dev/null
  echo "Round $N: committed $(git rev-parse --short HEAD)."
  return 0     # signals "code changed" to caller
}

prev_findings_count=999999
LAST_CODE_COMMIT=$(git rev-parse HEAD)
N=1

while [ "$N" -le "$MAX_ROUNDS" ]; do
  echo "=== Round $N: Builder ==="
  claude -p "$(builder_prompt "$N")" --allowedTools "Read,Write,Edit,Bash" --permission-mode acceptEdits

  # Commit Builder's work (and its note) before Reviewer looks at anything,
  # so "git diff" checks below are against a real, inspectable commit.
  commit_round "$N" "builder" || true
  BUILDER_COMMIT=$(git rev-parse HEAD)

  echo "=== Round $N: Reviewer ==="
  claude -p "$(reviewer_prompt "$N")" --allowedTools "Read,Write,Bash" --permission-mode acceptEdits

  FINDINGS_FILE="$HANDOFF/reviewer-findings/round-$N.md"
  if [ ! -f "$FINDINGS_FILE" ]; then
    write_escalation "$N" "Reviewer did not produce a findings file."
    exit 1
  fi

  # Commit Reviewer's findings file itself (Reviewer never touches code,
  # so this commit is expected to contain no code diff vs BUILDER_COMMIT).
  commit_round "$N" "reviewer-findings" || true

  VERDICT=$(extract_verdict "$FINDINGS_FILE")
  echo "Round $N verdict: $VERDICT"

  findings_count=$(grep -cE '^\s*-?\s*(Brief violation|Judgment call|Reviewer overreach)' "$FINDINGS_FILE" || true)

  case "$VERDICT" in
    ESCALATE)
      write_escalation "$N" "Reviewer explicitly returned ESCALATE."
      exit 1
      ;;
    FAIL)
      CONSECUTIVE_PASS=0
      ;;
    PASS)
      if [ "$CONSECUTIVE_PASS" -ge 1 ]; then
        # This PASS is the confirming second pass. Verify zero code change
        # since the commit right after Builder's LAST actual code round
        # (i.e. no round with real code changes happened in between).
        CODE_DIFF=$(git diff --stat "$LAST_CODE_COMMIT" "$BUILDER_COMMIT" -- . ":(exclude)$HANDOFF")
        if [ -z "$CODE_DIFF" ]; then
          TAG="loop-pass-$(git rev-parse --short "$BUILDER_COMMIT")"
          git tag "$TAG"
          echo "=== PASS confirmed twice with zero code changes in between. Loop complete. ==="
          echo "Tagged as $TAG."
          exit 0
        else
          echo "Round $N was PASS but code changed since last PASS — resetting confirmation counter."
          CONSECUTIVE_PASS=0
        fi
      else
        CONSECUTIVE_PASS=1
      fi
      ;;
    *)
      write_escalation "$N" "Could not parse a VERDICT line from findings file."
      exit 1
      ;;
  esac

  LAST_CODE_COMMIT="$BUILDER_COMMIT"

  # Mechanical triggers
  if [ "$N" -ge 4 ] && [ "$findings_count" -ge "$prev_findings_count" ]; then
    write_escalation "$N" "4+ rounds without open-findings count shrinking ($prev_findings_count -> $findings_count)."
    exit 1
  fi
  prev_findings_count=$findings_count

  N=$((N + 1))
done

write_escalation "$MAX_ROUNDS" "Hard cap of $MAX_ROUNDS rounds reached without resolution."
exit 1
