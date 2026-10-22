# ADR-020: Descriptive Scorecards, No Composite Score

**Status:** Proposed (2026-10-22). Methodology; needs owner approval. Part of the [Wickstreet 2.0 blueprint](../../history/plans/2026-10-22-wickstreet-2/README.md).

## Context
Research products show stock and fund "scores". An opaque score invites trust it has not earned. The Momentum25 research record shows how hard predictive ranking is: 11 proposals, none passed hold-out. Any scorecard Wickstreet shows must be deterministic, traceable and honest about what it claims.

## Decision
1. **Dimensions, not verdicts.** Stocks: Financial quality, Growth, Valuation, Momentum, Risk. Funds: Performance consistency, Risk, Cost, Diversification. No ETF scorecard.
2. **Method.** Each metric → percentile within a declared peer set (industry; SEBI category and plan type for funds), average rank for ties. Dimension = mean of available metric percentiles, if at least half its metrics and at least 5 peers have values; else `NA` with the reason. Bands: Low, Middle, High at thirds. Equal weights.
3. **Momentum displays Momentum25** results from the production run. It computes nothing and changes no Momentum25 weight or rule.
4. **No composite score.** None is proposed. One would need an explicit formula, a calibration method and owner approval.
5. **No predictive claim.** Scorecards are labelled "Descriptive comparison with industry peers. Not a recommendation." A predictive claim needs a research proposal with walk-forward and hold-out evaluation.
6. **Ship gate.** Owner approval of metric lists and directions; a month-to-month band stability check on in-sample data only (sealed hold-out unread); a written set of sanity cases.
7. `SCORECARD_VERSION` joins the engine identity.

## Consequences
- Users see where an instrument sits among peers and why.
- Scorecards may not ship if the stability check fails. That is an acceptable outcome.

## Alternatives considered
- **A single 0–10 score per instrument:** rejected without calibration.
- **Star ratings:** rejected. They imply a forecast.
- **Weights tuned on returns:** rejected. That is research, not display, and needs hold-out evidence.
