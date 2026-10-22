# ADR-017: Mutual Funds, ETFs and Holdings Disclosures

**Status:** Proposed (2026-10-22). Part of the [Wickstreet 2.0 blueprint](../../history/plans/2026-10-22-wickstreet-2/README.md). Requires [ADD Amendment A2](../ADD-amendment-A2.md).

## Context
ADD A1 §4 put non-equity assets out of scope. Wickstreet 2.0 makes mutual funds a first-class asset class and adds ETFs. A fund has schemes, plans and options with separate NAVs and costs. Its holdings are known only through periodic disclosures published days after the portfolio date. ETFs already appear in `securities` as if they were equities.

## Decision
1. **Instrument types are explicit.** `securities.instrument_type` (`EQUITY`, `ETF`, `REIT`, `INVIT`, `OTHER`). Only `EQUITY` enters the Momentum25 universe and RS ratings. The migration is gated by a golden test: RS ratings for every stored date stay identical.
2. **Fund model.** `amcs` → `fund_schemes` → `fund_plans` (one row per AMFI plan-option code). Category, benchmark and market-cap bucket are effective-dated (`classification_assignments`, `scheme_benchmarks`). An ETF plan links to its listed `security_id`.
3. **NAV store.** `nav_daily(plan_id, nav_date, nav)`, versioned. NAV for date *d* is known at *d* 23:00 IST. Returns use Growth options. IDCW returns need `fund_distributions`.
4. **Disclosures are snapshots.** `portfolio_disclosures` + `portfolio_holdings`, each with `portfolio_date` and `published_at`. A correction is a new disclosure that supersedes the old one.
5. **Point-in-time rule for holdings.** At *t*, a scheme's visible portfolio is the disclosure with the greatest `published_at ≤ t`. Never chosen by `portfolio_date` alone; never extrapolated backwards. Without a recorded publication time, `published_at` = portfolio date + 10 days (monthly/half-yearly) or + 5 days (fortnightly debt), labelled `reconstructed`.
6. **Benchmarks are TRI.** `benchmark_index_daily.kind` (`PRI`, `TRI`). Fund and ETF comparisons use TRI. A price index is shown only with an explicit "excludes dividends" warning.
7. **ETF metrics** are end-of-day: premium/discount from close and NAV; tracking difference and tracking error on SEBI's definition (annualised SD of daily return differences over one year). No iNAV, no spread.
8. **Formulas** (blueprint 03 §2.5) are owner-approved methodology under `METRIC_VERSION`.

## Consequences
- Fund research, holdings look-through and overlap become possible with honest dates.
- The database grows with NAV history; Growth options are imported by default.
- Disclosure parsing per AMC is costly unless a vendor normalizes it (ADR-021).

## Alternatives considered
- **Treat funds as securities:** rejected. Plans, options, NAV timing and disclosures do not fit, and it would pollute equity universes.
- **Use the latest holdings for all past dates:** rejected. It invents history.
- **Compare funds against price indices:** rejected as a silent default. It flatters every fund by the dividend yield.
