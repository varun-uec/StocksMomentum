# ADR-019: Portfolio Ledger and Look-Through Exposure

**Status:** Proposed (2026-10-22). Part of the [Wickstreet 2.0 blueprint](../../plans/wickstreet-2/README.md). Requires [ADD Amendment A2](../ADD-amendment-A2.md).

## Context
Users want one view of stocks, ETFs and funds they own: value, returns, real exposure through funds, overlap and drift. Broker integration and trading stay out of scope. Portfolio data is the most private data the app would hold.

## Decision
1. **Transactions are the only truth.** `portfolio_transactions` (buy, sell, SIP, switch, dividend, opening balance, fee) per portfolio, grouped by `import_batches`. Holdings, lots, cost and value are derived on read with FIFO lots. No stored holdings table.
2. **Corporate actions scale lots** after the trade date (split, bonus); total cost is unchanged. Equities are valued at traded close, funds at NAV on or before the date.
3. **Returns.** Absolute return; CAGR for single lump sums only; XIRR by bracketed bisection (deterministic; `NM` when no unique root); benchmark XIRR on the same cash flows into the TRI. Drawdown on a time-weighted daily index.
4. **Look-through.** Exposure = direct value + Σ fund value × weight from the disclosure visible at the date (ADR-017), recursing one more level for fund units held by funds, replacing (not adding) the unit line, with cycle cut-off. Debt, cash and unreported residuals are named buckets. Invariant: exposures sum to portfolio value.
5. **Intake.** Manual entry, `transactions-v1` CSV with preview and undo, CAS parsed locally (password in memory once, never stored or logged), broker export adapters. Resolution by ISIN, symbol or plan code; never by name.
6. **Privacy.** No portfolio data leaves the machine. No outbound calls carry holdings. Loopback rule (ADR-012) unchanged.

## Consequences
- Exact, reproducible portfolio numbers; undo by import batch.
- Exposure accuracy depends on disclosure freshness, which every view states.
- The portfolio core works with real data on day one for listed equities, because prices exist.

## Alternatives considered
- **Store holdings snapshots:** rejected. Two sources of truth need reconciliation.
- **Newton's method for XIRR:** rejected as the default. Its result can depend on the starting point.
- **Broker sync:** out of scope.
