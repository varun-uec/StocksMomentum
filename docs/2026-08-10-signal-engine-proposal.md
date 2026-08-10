# Signal engine — proposal, not an implementation

Companion to `docs/2026-08-10-unified-analysis-screen-plan.md`, § "Signals and the
scoring engine". That task shipped **(a)**: a view-layer signal score on the analysis
screen and an off-by-default column on the momentum table, computed in the browser from
the displayed bars. Nothing it produces is stored, and no screening run changed.

This document is **(b)**: what it would take to make signals a real scoring input. No code
is written. It exists so the decision is made against the evidence bar the repo already
enforces, not retrofitted to it afterwards.

## What is being proposed

A `signal` domain engine that contributes to the composite score, alongside
`trend_template`, `relative_strength`, `pattern`, `breakout`, `risk` and
`volume_accumulation`.

Its rules are the ones now living in `web/src/lib/strategies.ts`: Stage 2 alignment, SMA 200
slope, new 252-session high, Donchian breakout, band squeeze then expansion, volume surge,
Stochastic cross out of oversold, EMA 21 reclaim, cloud and Supertrend state, ADX with ±DI,
golden/death cross, MACD signal cross, RSI 30/70, OBV confirmation, CMF sign, pocket pivot.

## Why it cannot simply be lifted from the browser

Five reasons, each of which is a work item.

1. **Determinism contract.** The browser version reads whatever bars the chart's timeframe
   loaded. An engine must read a fixed, declared lookback from the stored series, or the
   same symbol scores differently depending on who is looking at it.
2. **Duplicated maths.** The browser recomputes Stochastic, Williams %R, CCI, ROC, ±DI and
   ATR that the backend indicator pipeline already produces. The engine must consume the
   existing `IndicatorSnapshot` and per-bar series, not a second implementation. Anything
   genuinely missing (Donchian, Bollinger width, OBV, CMF, Supertrend, Ichimoku) is a new
   indicator function in the existing pipeline, with its own unit tests.
3. **Config hash.** Adding an engine changes the strategy configuration, so the config hash
   changes, so `strategy_id=30` is no longer the strategy that produced today's stored runs.
   That is a new strategy row and a re-screen, not an edit.
4. **Explainability.** Every engine emits `rule_explanations` with `passed`,
   `actual_value`, `threshold` and `contribution`. A signal rule fires on a date, not on a
   level. The rule contract has to express "fired 6 sessions ago" in those fields, or the
   score gains a component no reader can check.
5. **Weights.** The composite weights currently sum over the six engines. Introducing a
   seventh either dilutes all of them or takes weight from named ones. Which, and why, is a
   research question with an answer that must be measured, not chosen.

## Where it would sit

- `backend/.../domain/engines/signal_engine.py` — pure, no I/O, same port as the other
  engines; registered in the engine registry.
- Rules as domain rule objects, one per condition, each with an id, a weight and an
  explanation string.
- Inputs: the stored OHLCV series for a declared lookback, plus the existing indicator
  snapshot and per-bar series. No new external data.
- Config: engine weight, per-rule weights, the recency window, and the lookback — all in the
  strategy configuration, so the hash covers them.

## The gate it must pass

The repo's record is 8 research proposals, 0 promoted, 6 rejected on hold-out. This proposal
gets the same gate, stated up front:

1. **Hypothesis, stated before the run.** Signal-derived features add information the six
   existing engines do not already carry. The obvious failure mode is redundancy: RP-007
   showed the gates and the ranker are redundant in one direction already, and most of these
   rules are functions of the same moving averages the trend template gates on.
2. **Contribution IC first, ranking effect second.** RP-000's lesson: a low-weight
   contribution IC is not a composite-ranking effect. Measure the ranking effect directly.
3. **Walk-forward improvement** on Precision@25, Recall@25, mean and median forward return,
   Top-25 alpha, IC, Rank IC and ranking stability, against `strategy_id=30` on identical
   windows.
4. **Hold-out improvement** on a fold the design was not tuned on. Same sign as in-sample.
   RP-003 died on exactly this.
5. **Statistical significance**, with the sample size stated. RP-006 was underpowered and
   was recorded as underpowered rather than as a result.
6. **No regression** in the Golden Regression Suite, in max drawdown, or in explainability.
7. **Reproducibility**: a re-screen from the backend alone reproduces every score.

Failing any one of these means the existing methodology is retained. That is a correct
outcome, not a failed task.

## Known blocker

MEMORY records the standing constraint: ranking-remedy research is frozen until 2026-H1
120-day forward returns mature and a determinate benign/correction-spanning fold exists. The
binding constraint on the last programme was **data, not methodology**. This proposal is
subject to that freeze. It is written now because the rules are now specified precisely
enough to test, not because the data is ready to test them.

## Recommendation

Hold. Ship (a), which is already shipped and touches nothing stored. Revisit (b) when the
fold exists. If it is taken up, run it as a milestone with its own architecture approval per
CLAUDE.md — not as an increment on a charting task.
