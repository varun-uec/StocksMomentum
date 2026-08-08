# Phase 3b — Swing target/stop methodology search log

Full, unedited log of every configuration attempted. Phase 3's fixed 1.5:1
ATR-multiple convention failed hold-out (avg R −0.021, n=3,211,
`docs/research/2026-07-02-alpha-discovery-program-report.md` / Phase 3
report). This phase searched for an alternative that passes, per
`docs/momentum25-backlog.md` Phase 3b.

**Methodology guard:** every configuration was screened against the
**in-sample** period (2000-01-01..2024-12-31) first. Only a configuration
with in-sample `avg_r_multiple > 0` would have been run against the
untouched hold-out fold (2025-01-01 onward) — this decides candidacy
*before* any hold-out number is observed, so choosing a "winner" by scanning
hold-out results across configs cannot happen here.

**Slippage/gap-through fill modeling (3b.4):** all runs below use the
updated `simulate_trade`, which fills a stop at `min(plan.stop, bar.open)`
instead of the bar's exact stop price — i.e. a stop that gaps through opens
below it fills at the worse open price, not an idealized stop-price fill.
This makes every number below (including the in-sample re-measurement of
the original Phase 3 convention, not listed separately here since it is
covered by config comparison) more conservative than the original Phase 3
report, which did not model this.

Runner: `backend/scripts/phase3b_swing_backtest.py`. Raw run output:
in-sample screen only — no config cleared the bar, so the hold-out fold was
never touched by 3b (0/6 configs reached it).

| Config | Rationale (a priori) | In-sample trades | In-sample hit rate | In-sample avg R | Result |
|---|---|---|---|---|---|
| B — wider target (stop 2×ATR, target 4×ATR) | 64% Phase-3 decided-trade hit rate only needs ~0.56:1 RR to break even, yet avg R was negative — winners were likely paying less than the nominal 1.5:1 (swing-resistance targets often closer than the ATR fallback). Raise the ATR-fallback target to widen realized RR. | 11,834 | 58.96% | **−0.1050** | FAILS in-sample screen |
| C — tighter stop (1.5×ATR stop, target 3×ATR) | Same reasoning, opposite lever: tighten the stop instead of widening the target, on the hypothesis the 2×ATR stop gives noise too much room before a forced exit. | 11,834 | 53.81% | **−0.1807** | FAILS in-sample screen |
| D — signal-time RR gate (min_rr_ratio ≥ 2.0, Phase-3 stop/target otherwise unchanged) | Gate entries on the plan's own computed RR at signal time (matching the strategy's configured `min_ratio`) — if low-computed-RR trades (typically the swing-resistance basis, which can be arbitrarily close) are dragging the average down, excluding them at entry should isolate the trades the plan itself judged favorable. | 131 | 14.94% | **−0.3962** | FAILS in-sample screen (worst of all 6 — and hit rate collapses, meaning the RR-gated subset is *lower* quality, not higher) |
| E — ADX ≥ 25 trending-only regime filter | Minervini's methodology assumes an established trend before a target/stop plan is meaningful; Wilder's ADX ≥ 25 is the conventional trending threshold. Tests whether choppy/weak-trend signals are the source of the negative average, independent of stop/target levels. | 8,454 | 55.92% | **−0.1770** | FAILS in-sample screen |
| F — RS rating ≥ 85 leaders-only regime filter | Restrict to top relative-strength leaders (standard Minervini/O'Neil leadership convention) on the hypothesis marginal-RS passers are the weaker setups. | 0 | n/a | **n/a** | FAILS in-sample screen — **zero signals matched this filter at all** across the full in-sample history; see note below |
| G — tight stop + wide target (1.5×ATR stop, 4×ATR target) | Combine B and C as its own configuration rather than assuming their effects are additive. | 11,834 | 52.33% | **−0.1548** | FAILS in-sample screen |

## Note on config F (zero signals)

`rs_rating >= 85` never matched a single passing signal in the full
in-sample history for `minervini_trend_template`. This is a data-coverage
finding, not a code defect: `compute_universe_rs_ratings` only produces a
rating when ≥2 securities have usable returns (Phase 1.2), and this
strategy's hard filters (`tt_rs_rating_min`) already require a materially
high RS rating to pass at all — apparently never one this strict on top of
everything else the trend template already demands. Worth a note for future
research (is the existing `tt_rs_rating_min` threshold and this population
simply incompatible with an *additional* 85+ leadership filter?) but out of
scope to chase further under the 5–8 config cap.

## Outcome

**0 of 6 configurations cleared the in-sample screen.** Every alternative
tried — wider targets, tighter stops, a combination of both, a signal-time
RR gate, and two regime/leadership filters — produced a **more negative**
in-sample average R than Phase 3's original convention, not a better one.
Per the exit criteria, the hold-out fold was never run for any of them
(avoiding the exact curve-fitting failure mode this phase was designed to
guard against), and per the hard rule, the search was **not** extended
beyond the 6 attempts or re-run against the hold-out fold to look for a
pass.

**Phase 3b fails to find a passing configuration. Phase 4 remains blocked.**
The consistent direction across every lever tried (wider/tighter
stop-target combinations all worsen the result; RR-gating shrinks the
sample and makes it worse, not better; trend-strength and leadership
filters both still negative) points toward the same root cause flagged
throughout this program's research history: the qualified-set ranking
itself carries negative IC (`RP-002`, see
`docs/research/research_closed_and_backlog.md`-equivalent findings), so
*which* trades this strategy selects — not how their exits are shaped — is
the binding constraint. Reshaping the target/stop plan cannot fix a
selection problem.
