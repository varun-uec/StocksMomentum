# Strategy Brief — Multi-Timeframe Momentum (3/6/12M, Monthly Rebalance)

This is the ground truth. Reviewer checks the code against this file, not
against what the code currently does. If code and brief disagree, code is
wrong until this file is updated.

Style reference: blended multi-period momentum, similar in spirit to
Weekend Investing's "Mi Evergreen" smallcase — rules-based, no manual
discretion, monthly rebalance, winners kept running, laggards cut.
(Their exact internal weighting formula is proprietary and not copied here —
this brief defines our own version.)

## 1. Universe

- NSE, Nifty 500 constituents as of each rebalance date.
- Minimum criteria to be eligible: at least 12 months of adjusted-close
  price history as of the rebalance decision date.
- Exclude: stocks in the trade-to-trade (T2T) segment, stocks under
  surveillance/ASM (Additional Surveillance Measure) as of the rebalance
  date, and newly listed IPOs with less than 12 months of price history.

## 2. Momentum score

For each stock, as of the last trading day before the rebalance date:

- **3-month return**: price(t) / price(t - 3 months) - 1
- **6-month return**: price(t) / price(t - 6 months) - 1
- **12-month return**: price(t) / price(t - 12 months) - 1

Skip-month: **none**. All three lookbacks run through the decision date `t`
with no skip. Any skip-month logic added unprompted is a brief violation,
not a judgment call.

**Composite score** = weighted blend of the three returns:
```
score = w3 * return_3m + w6 * return_6m + w12 * return_12m
```
Weights: **equal weight**, `w3 = w6 = w12 = 1/3`.

All returns should be computed on **adjusted close prices** (adjusted for
splits, bonuses, and dividends) — not raw close.

## 3. Ranking and selection

- Rank all eligible stocks by composite score, descending.
- Portfolio size: **top 30 stocks** (N = 30).
- Tie-break rule: higher 12M return wins ties. If still tied, higher 6M
  return, then higher 3M return. This must resolve deterministically —
  no residual tie may be broken arbitrarily (e.g. by insertion order).

## 4. Weighting within portfolio

Equal weight across all holdings (1/30 of portfolio value each, when the
portfolio is full).

## 5. Rebalance mechanics

- Frequency: **monthly**, on the first trading day of each calendar month.
- Decision point: score computed using adjusted-close prices through close
  of the last trading day of the prior month.
- Execution: trades placed at the **next trading day's open** — i.e. decide
  at close of the last trading day of month M-1, fill at open of the first
  trading day of month M. "Decide at close t, fill at close t" is a
  look-ahead bug under this brief.

## 6. Exit / re-entry rule ("survival of the fittest")

- Buffer multiplier: **1.5x** (N * 1.5 = 45).
- A stock already in the portfolio is **removed** if its rank falls outside
  the top 45 (N*1.5) at a rebalance.
- A stock outside the portfolio is **added** if it ranks in the top 30 (N)
  at a rebalance and a slot is free (portfolio below 30 holdings, or an
  existing holding was removed this rebalance).
- This asymmetric in/out band is intentional — it keeps monthly turnover
  low. A hard cutoff with no buffer (remove anything outside top 30) is a
  **brief violation**, not a judgment call.

## 7. Transaction costs / slippage (for backtest)

- Cost per trade: **30 bps** total (brokerage + assumed slippage combined),
  applied as a single flat rate — no separate breakdown between the two
  components is required.
- Applied to: every buy and every sell at rebalance, on the traded notional
  (price × quantity traded, not portfolio NAV).

## 8. Benchmark

- **Nifty 500 TRI** (Total Return Index — includes dividends, matches the
  Nifty 500 universe used for stock selection).
- Used for: relative performance reporting only, never for stock selection.

## 9. Look-ahead — explicit statement

No information dated on or after the rebalance decision date may influence
that rebalance's stock selection or weights. This includes: prices,
corporate action data, index membership/reconstitution data, and delisting
information. This is the single most important rule in this brief and the
basis for checklist items 3, 7, 8, and 9 in `reviewer-handoff.md`.

---
**Status: FINAL.** All sections completed by human decision, 2026-08-17, in
response to the round-1 escalation (`handoff/escalations/round-0.md`). This
is now the fixed point for the loop.
