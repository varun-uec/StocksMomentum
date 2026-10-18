# Reviewer Handoff — Momentum Signal & Backtest Integrity

## Evidentiary bar

Don't trust Builder's status note as ground truth — it's a claim to verify, not
a summary to relay. Inferring correctness from *reading* the code is not
sufficient for any item below marked [RUN]. You must actually execute
something and observe the result.

General principle: for every mechanism the code claims to have (no look-ahead,
handles missing data, excludes delisted names correctly, matches a
hand-computed number), find the cheapest way to falsify it, and try to
falsify it. If you can't break it after a real attempt, that's evidence for
PASS — not the absence of an attempt.

## Checklist — Signal / Indicator Correctness

1. **Formula matches brief.** [RUN] Hand-calculate the momentum score for 2–3
   specific (ticker, date) pairs independently — pull the raw price series
   yourself, do the arithmetic by hand or in a scratch script, and compare to
   the code's output. Do not trace the code's internal intermediate values and
   call that verification; the point is an independent computation.
2. **Skip-month / formation-lag handling.** [RUN] If the brief specifies a
   skip period (e.g. exclude the most recent month to avoid short-term
   reversal contamination), pick a date and confirm which exact price window
   the code actually used, by instrumenting or logging, not by reading the
   slicing code and reasoning about what it "should" do.
3. **Look-ahead in the signal itself.** [RUN] Deliberately feed the signal
   function data that includes information dated after the "as-of" date being
   scored (e.g. extend a price series past the decision date) and confirm the
   score does *not* change. If it changes, that's a leak.
4. **Universe construction.** [RUN] Register/inject a synthetic instrument
   with known properties (e.g. a ticker with a data gap, a recent IPO with
   short history, a delisted ticker) and confirm it's included/excluded per
   the brief's stated rule — don't just read the filter condition.
5. **NaN / missing-data behavior.** [RUN] Deliberately corrupt or blank out a
   chunk of one ticker's price history and confirm the pipeline fails closed
   (excludes/flags that ticker) rather than silently propagating a NaN into
   rankings or, worse, silently defaulting to a 0 or forward-filled value that
   changes rank order.
6. **Ranking / tie-break logic.** [RUN] Construct a small synthetic input with
   a known tie and confirm the tie-break resolves the way the brief specifies
   (or, if unspecified, confirm it's deterministic and logged as a judgment
   call).

## Checklist — Backtest Integrity

7. **Look-ahead bias, portfolio-construction level.** [RUN] Pick a rebalance
   date. Confirm every input used to form that rebalance's weights (prices,
   fundamentals, index membership, corporate actions) has a timestamp
   strictly before the decision point — check the actual data pulled at
   runtime for that date, not the intent of the code.
8. **Survivorship bias.** [RUN] Confirm the price/universe data source
   actually includes delisted/bankrupt/acquired names for historical dates.
   Pull one known-delisted ticker for a date before its delisting and confirm
   it appears in that historical universe snapshot.
9. **Corporate actions.** [RUN] Pick one known split or large special dividend
   in the test period and confirm the return series is adjusted correctly
   across that event — hand-check the return doesn't show a fake jump/crater
   on the ex-date.
10. **Rebalance timing vs. fill assumption.** [RUN] Confirm the code's
    assumed fill price/date matches its stated assumption (e.g. "decide on
    close t, fill at close t+1" vs. actually filling at close t). Trace one
    real trade through the backtest engine's logs/state, don't just read the
    order-generation function.
11. **Transaction costs / slippage.** [RUN] Force a scenario with a known
    turnover and confirm the cost deducted matches the stated cost model by
    hand-calculating expected costs and comparing — don't trust the reported
    P&L attribution.
12. **Vacuous or self-fulfilling tests.** [RUN] For any test Builder added,
    check it can actually fail — temporarily break the underlying logic on a
    scratch copy and confirm the test goes red. A test that passes
    unconditionally (asserts something trivially true, or never actually
    calls the code path it claims to cover) is a finding, not a pass.
13. **"Forked safety net" check.** Hunt specifically for a check that appears
    to validate correctness but is wired to a code path that never actually
    executes in the real run (e.g. a validation function defined but not
    called, or called only in a branch that's dead given current config).
    [RUN] Instrument with a spy/log statement and confirm it fires during a
    real backtest run, not just in isolation.
14. **Benchmark / attribution consistency.** [RUN] Recompute total return over
    the full backtest period independently from the raw position history
    (not from the engine's own summary stats) and confirm it matches the
    reported number within a small tolerance.

## Filing findings

Each finding in `reviewer-findings/round-N.md` must include:
- Checklist item # it maps to (or "unlisted" if novel).
- Classification: Brief violation / Judgment call / Reviewer overreach.
- What was actually run to produce this finding (command, script, or
  instrumentation used) — not just a description of the bug.
- Expected vs. observed result.

End the file with exactly one line: `VERDICT: PASS|FAIL|ESCALATE`
