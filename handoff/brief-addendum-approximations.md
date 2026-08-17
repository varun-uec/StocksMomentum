# Brief Addendum — Approximations Accepted for This Backtest

This extends `brief.md` and `brief-addendum-loop2.md` (both unchanged). Loop 2
found two real data gaps and stopped rather than fabricate data. This addendum
is the scope decision on those gaps: accept them as documented, bounded
approximations, and move forward. It does not reopen loop-2's domain or
runner code, which stays frozen at its `loop-pass-*` tag.

## Why this loop exists

Loop 2 surfaced two blockers with no free, point-in-time data source:

1. No free source for point-in-time Nifty 500 / ASM / T2T membership and
   surveillance history.
2. The available benchmark feed is Nifty 500 price index, not Total Return
   Index (TRI).

Both are real gaps, not implementation bugs. The decision here is to accept
them as approximations, state them plainly in every place a human reads a
result, and give the exit criteria that would force revisiting them.

## The approximation, stated exactly

- **Universe/surveillance approximation.** The historical universe provider
  uses today's Nifty 500 constituent list and today's ASM/GSM/T2T
  surveillance list, applied retroactively across the whole backtest window,
  instead of the true point-in-time membership and surveillance status on
  each rebalance date.
- **Benchmark approximation.** The benchmark series is Nifty 500 **price
  index**, not Nifty 500 **TRI**. Price index excludes dividends; TRI
  includes them. The reported benchmark return will run below the true TRI
  benchmark return.

## Direction of bias — all three point the same way

State this outright wherever backtest results are reported (README, CLI
output, report headers): **the backtest is optimistic relative to what live
trading would have produced.**

1. Using today's constituents retroactively drops stocks that were once in
   the index and later fell out — typically after underperforming. Survivors
   look better than the true historical universe did.
2. Using today's surveillance list retroactively can admit names that were
   actually under ASM/T2T restriction at the time (understating realistic
   friction/exclusion) or, less often, exclude names that weren't restricted
   then but are now.
3. A price-index benchmark understates the true TRI benchmark, so the
   strategy's reported outperformance over the benchmark is inflated versus
   the TRI-correct comparison.

None of these biases point toward understating the strategy's performance.
Do not net them against each other or claim they roughly cancel out — they
don't; they compound in the same optimistic direction.

## What Builder must do this round

1. **Universe/surveillance provider.** Implement it explicitly as "current
   constituents/surveillance list applied across the full historical range."
   No behavior change is required if this is already what Loop 2 built —
   confirm it, and make the approximation discoverable in code (a doc
   comment on the provider stating the limitation) and in the runner's
   output metadata (a field or log line stating which approximation mode was
   used), not just in this file.
2. **Benchmark provider.** Confirm it returns Nifty 500 price index. Label
   every report/output that shows the benchmark return with "Nifty 500 Price
   Index (not TRI)" — not "Nifty 500" or "benchmark" alone. This label must
   appear next to the number itself (report, CLI summary, chart legend if
   any), not only in a README.
3. Do not attempt to source real point-in-time membership/surveillance data
   or a real TRI feed this round. That is out of scope here — see exit
   criteria below.

## Exit criteria — when to revisit this decision

Revisit sourcing real point-in-time data (paid vendor, direct NSE archives,
or a TRI-licensed feed) when any of the following becomes true:

- Real capital is about to be deployed against this strategy.
- Real, non-simulated data access becomes available at acceptable cost.
- A backtest result comes out close enough to a go/no-go decision line that
  the known optimistic bias could plausibly flip the decision.

Until then, the approximation stands, documented, not hidden.

## What Reviewer checks this round

Reviewer does not re-litigate whether the approximation is acceptable — that
decision is made here. Reviewer confirms:

- The universe/surveillance provider's code and docstring state the
  approximation explicitly (grep for it — it must be readable from the code,
  not only inferred from this file).
- At least one report/output path that surfaces the benchmark number carries
  the "Price Index (not TRI)" label directly next to that number.
- No code path silently claims TRI, "total return," or claims point-in-time
  survivorship-free membership anywhere in output text, docstrings, or
  variable/field naming (e.g. a field named `total_return_index` on
  price-index data would be a Brief violation, not a judgment call).
