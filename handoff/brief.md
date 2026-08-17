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

- [FILL IN: index/exchange, e.g. "NSE, Nifty 500 constituents as of each
  rebalance date"]
- Minimum criteria to be eligible at all: [FILL IN — e.g. min market cap,
  min average daily traded value/liquidity, min listing history e.g. 12+
  months of price data]
- Exclude: [FILL IN — e.g. stocks in trade-to-trade segment, stocks under
  surveillance/ASM, newly listed IPOs with <12 months history]

## 2. Momentum score

For each stock, as of the last trading day before the rebalance date:

- **3-month return**: price(t) / price(t - 3 months) - 1
- **6-month return**: price(t) / price(t - 6 months) - 1
- **12-month return**: price(t) / price(t - 12 months) - 1

Skip-month: [FILL IN — decide whether to skip the most recent 1 week/month
in each lookback to avoid short-term reversal contamination, as academic
12-2 momentum does. If undecided, default assumption for this brief is
**no skip-month** — flag as a judgment call if Builder adds one unprompted.]

**Composite score** = weighted blend of the three returns:
```
score = w3 * return_3m + w6 * return_6m + w12 * return_12m
```
Default weights: [FILL IN — e.g. equal weight w3=w6=w12=1/3, or a scheme
that favors 6M/12M with 3M as a smaller tilt/filter. Weekend Investing's own
weights are not public; pick and document your own here.]

All returns should be computed on **adjusted close prices** (adjusted for
splits, bonuses, and dividends) — not raw close.

## 3. Ranking and selection

- Rank all eligible stocks by composite score, descending.
- Portfolio size: [FILL IN — e.g. top 30 stocks]
- Tie-break rule: [FILL IN — e.g. higher 12M return wins ties; must be
  deterministic]

## 4. Weighting within portfolio

[FILL IN — equal weight across all holdings, or score-weighted, or
volatility-scaled. Equal weight is the simplest default if undecided.]

## 5. Rebalance mechanics

- Frequency: **monthly**, on [FILL IN — e.g. first trading day of the month,
  or a fixed calendar date]
- Decision point: score computed using prices through close of [FILL IN —
  e.g. last trading day of prior month]
- Execution: trades placed at [FILL IN — e.g. next day's open, or same-day
  close]. This must be explicit — "decide at close t, fill at close t" is a
  look-ahead bug; "decide at close t, fill at open/close t+1" is not.

## 6. Exit / re-entry rule ("survival of the fittest")

- A stock already in the portfolio is **removed** if: [FILL IN — e.g. it
  drops out of the top N*1.5 by rank, or its composite score turns negative]
- A stock outside the portfolio is **added** if: [FILL IN — e.g. it ranks in
  the top N at rebalance]
- This asymmetric in/out band (buffer/hysteresis) is intentional — it's what
  keeps monthly turnover low. If Builder implements a hard cutoff with no
  buffer, that's a brief violation, not a judgment call, once this section is
  filled in.

## 7. Transaction costs / slippage (for backtest)

- Cost per trade: [FILL IN — e.g. X bps brokerage + Y bps assumed slippage]
- Applied to: [FILL IN — every buy and sell at rebalance, on the traded
  notional]

## 8. Benchmark

- [FILL IN — e.g. Nifty 500 TRI, or Nifty Smallcap 250 TRI]
- Used for: relative performance reporting, not for stock selection.

## 9. Look-ahead — explicit statement

No information dated on or after the rebalance decision date may influence
that rebalance's stock selection or weights. This includes: prices,
corporate action data, index membership/reconstitution data, and delisting
information. This is the single most important rule in this brief and the
basis for checklist items 3, 7, 8, and 9 in `reviewer-handoff.md`.

---
**Status: DRAFT.** Sections marked [FILL IN] must be completed before round 1
starts — an incomplete brief means Reviewer has no fixed point to check
against, which is exactly the failure mode that caused the "wrong model
provider for two rounds" escalation in the original project.
