# Brief Addendum — Loop 2: Walk-Forward Engine & Historical Data

This extends `brief.md` (unchanged, still the ground truth for signal/ranking/
portfolio logic). This addendum defines what Loop 2 must build so that
checklist items 4, 7, 8, 9, 10, 13, 14 in `reviewer-handoff.md` become
runnable instead of "not executable." Loop 1's domain module
(`domain/backtest/`) is frozen — Loop 2 wires it up, it does not re-litigate
signal/ranking/buffer logic already tagged `loop-pass-round-2`.

## Why this loop exists

Loop 1 verified the math. It verified nothing about running that math against
real historical data over real time. Every backtest-integrity failure mode
(look-ahead, survivorship, corporate actions, fill timing) only exists at the
seam between "correct formula" and "correct data, correctly timed." That seam
doesn't exist in the codebase yet. This loop builds it.

## 0. Data sourcing is in scope for round 1

Unlike Loop 1 (which correctly refused to fabricate a missing surveillance
data source and stopped), Loop 2 round 1 includes **finding and fetching**
the underlying NSE data, not just building providers against data that's
already sitting in the repo. Specifically in scope for round 1:

- Fetching NSE bhavcopy (daily raw OHLC) for the backtest date range.
- Fetching NSE corporate-action data (splits/bonuses/dividends) to derive
  adjusted close from bhavcopy's raw close.
- Fetching NSE's historical index-constituent files (point-in-time Nifty 500
  membership) — not today's constituent list.
- Fetching NSE's ASM/GSM/T2T surveillance lists.

This is genuinely different from Loop 1's "don't invent data" rule: Loop 1
had no data source at all and no path to get one without a scope decision.
Here, real public sources exist (NSE's own site/archives) — the task is
integration work, not invention. If Builder discovers a specific data piece
genuinely isn't obtainable (e.g. NSE stopped publishing historical index
constituents beyond some date, or ASM lists aren't archived historically),
that's a legitimate scope-limiting discovery — document it in the round note
as a judgment call with what was actually tried, not a silent skip.

**Known practical risk, flag early rather than discover mid-round:** NSE's
site is not always straightforward to fetch programmatically (session
cookies, rate limiting, occasional anti-automation measures), and Claude
Code's network access may be restricted to an allowlist that doesn't include
nseindia.com by default. If Builder's environment can't reach NSE directly,
options are: (a) the human downloads the files manually and drops them in a
known repo path for Builder to parse, or (b) network access to NSE's domains
gets added to the allowlist first. Builder should check reachability early
in round 1 and report back immediately if this is the blocker, rather than
spending the round on it.

## 1. Data providers required (infrastructure layer)

Each of these is a port + at least one real implementation. Mock/fixture data
is fine for unit tests, but Reviewer's [RUN] checks need at least one real
historical pull to work against — see §4.

- **Adjusted-close price history provider.** Given a security + date range,
  returns daily adjusted-close prices (split/dividend/bonus adjusted).
  Must expose whether a given date's data was actually available *as of*
  that date (i.e. no silent forward-fill from future data).
- **Historical universe/membership provider.** Given a date, returns the set
  of securities that were actually in the Nifty 500 (or your chosen index)
  **as of that date** — not today's constituent list applied retroactively.
  This is the single most common source of survivorship bias; if this
  provider only has current membership, item 8 cannot pass.
- **Delisting/corporate-action provider.** Splits, bonuses, dividends
  (already implied by "adjusted close," but corporate action *dates* and
  *ratios* need to be independently queryable so Reviewer can pick one known
  event and hand-check the adjustment — see checklist item 9).
- **Surveillance/ASM/T2T provider.** Flagged in Loop 1 as missing. If it's
  still not available, Loop 2 must explicitly decide: (a) build it, (b) stub
  it with a documented "always clean" assumption that brief.md is updated to
  state outright (this becomes a Brief violation risk if silently assumed),
  or (c) exclude the surveillance eligibility check from this loop's scope
  and say so in the round note. Don't let this stay an implicit gap a second
  time.
- **Benchmark TRI series provider.** Nifty 500 TRI (or whatever brief.md §8
  specifies), for reporting only — not for stock selection.

## 2. Walk-forward runner (application layer)

A use case that, given a start date and end date:

1. For each monthly rebalance date in range:
   a. Pulls the historical universe as of that date (not today's universe).
   b. Pulls prices as of that date only (no data dated on/after the decision
      date may be visible to this step — this is the mechanism item 7
      checks).
   c. Applies eligibility (`domain/backtest/eligibility.py`, unchanged).
   d. Computes momentum signals (`domain/backtest/momentum_signal.py`,
      unchanged) using only price data available as of the decision date.
   e. Ranks and selects the portfolio (`rebalance.py`, unchanged, including
      the buffer rule).
   f. Plans trades against the *prior* rebalance's holdings
      (`portfolio_step.py`, unchanged), applying the fill-timing assumption
      from brief.md §5 explicitly (decide at close t, fill at close t+1, or
      whatever brief.md specifies — this must be a real date offset in the
      code, not an implicit same-day fill).
   g. Records the executed portfolio, trades, and costs.
2. After the last rebalance, reconstructs the full equity curve from the
   recorded trade history (not from any internal running-total the engine
   kept along the way — see checklist item 14).

This is the single piece of new code where items 4, 7, 10, and 13 actually
become testable, because it's the first place "as of date X" becomes a real,
enforced constraint rather than a documented intention.

## 3. Output the run must produce

For Reviewer to check items 9 and 14 without re-deriving the whole engine:

- A per-rebalance log: date, universe size, eligible count, selected
  portfolio, trades, costs.
- A trade-level log: security, side, quantity/notional, price, fill date.
- A final summary: total return, CAGR, and the benchmark's return over the
  same period, computed independently from the trade log (not from a
  cumulative variable incremented during the loop).

## 4. What Reviewer needs to actually run items 7-10, 13, 14

Once §1-3 exist, here's the concrete falsification test per item — this
replaces the "not executable" note in `reviewer-handoff.md` for this loop:

- **Item 7 (look-ahead, portfolio level):** Pick a rebalance date. Feed the
  price provider a version of itself that has a bug: return a price dated
  one day after the decision date when queried "as of" the decision date.
  Confirm the walk-forward runner either rejects it or the resulting
  portfolio doesn't change — if it silently uses that price, that's a leak.
- **Item 8 (survivorship):** Pick a real ticker delisted during the backtest
  window. Confirm it appears in the historical universe provider's output
  for a date before its delisting, and confirm the walk-forward runner
  actually includes it in eligibility evaluation for that date (not just
  "the provider has the data" but "the runner used it").
- **Item 9 (corporate actions):** Pick one known real split/bonus in the
  window. Hand-check the adjusted return across the ex-date doesn't show a
  fake jump/crater.
- **Item 10 (fill timing):** Trace one real trade through the trade-level
  log. Confirm the fill date matches brief.md §5's stated assumption exactly
  (off-by-one here is a classic silent look-ahead — filling at close t
  instead of t+1 means the trade "knew" close t's price before it should
  have been actionable).
- **Item 13 (forked safety net):** Instrument the "as of date" enforcement
  in the price/universe providers with a spy. Confirm it's actually called
  on the real code path the walk-forward runner uses — not just present in
  a provider class that's never invoked from the runner.
- **Item 14 (benchmark/attribution):** Take the trade-level log, recompute
  total return independently (outside the engine, in a scratch script), and
  compare to the engine's own reported total return.

## 5. Explicitly out of scope for Loop 2

- Live execution / broker integration (per earlier scoping decision).
- Optimizing the strategy itself (weights, buffer size, universe) — that's a
  brief.md change, not a Loop 2 code task.
- Anything not listed in §1-3. If Builder finds itself building something
  not named here, that's a scope-creep flag for Reviewer, not a free pass.

---
**Before Loop 2's round 1 starts:** confirm real data source access exists
(API keys, data vendor, or a static historical dataset checked into the repo
or reachable in your environment) for at least: adjusted-close prices,
historical index membership, and one known delisting + one known corporate
action to test against. Without at least one real historical fact to check
against, Loop 2 will hit the same "not executable" wall Loop 1 did, just one
layer up.
