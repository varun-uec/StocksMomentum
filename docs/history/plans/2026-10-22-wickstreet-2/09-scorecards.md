# 09 — Explainable Scorecard Methodology (Proposal)

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: **Proposed methodology — not approved.** Governing decision: ADR-020. Nothing here changes Momentum25.

## 1. What a scorecard is, and is not

- A scorecard says **where an instrument sits among its peers** on one dimension, at one date, from named inputs. It is descriptive.
- It is **not** a forecast, a buy signal or a rating. No scorecard claims that a high score predicts returns. Such a claim needs a research proposal with walk-forward and hold-out validation under the existing research rules, and that is not part of this blueprint.
- There is **no composite score**. Dimensions are shown side by side. A composite needs an explicit formula, a calibration method and owner approval (prompt §7), and none is proposed.
- **Momentum25 stays independent.** The Momentum dimension on a stock scorecard *displays* the existing Momentum25 result (qualified, rank, momentum score) from the production run. It computes nothing new and changes no weight.

## 2. Common method

For instrument *i*, dimension *D* with metrics *m₁…mₖ*, date *t*, peer set *P*:

1. **Peer set.** Stocks: industry at *t* (widen to sector if < 5 members with data). Funds: SEBI category at *t*, same plan type (Direct or Regular). ETFs: no scorecard in this proposal (too few peers per index).
2. **Metric percentile.** pᵢ,ⱼ = percentile rank of i's metric j within P, with average rank for ties, 0–100. Direction is fixed per metric (lower PE → higher valuation percentile; lower volatility → higher risk-dimension percentile). Values `NM`/`NA` are left out.
3. **Coverage rule.** A dimension is scored only if at least ⌈k/2⌉ of its metrics have values for i, and P has at least 5 members with values for each metric used. Else the dimension is `NA` with the reason.
4. **Dimension score** = arithmetic mean of the available metric percentiles, shown as a number 0–100 and a band: **Low** (< 33.3), **Middle** (33.3–66.7), **High** (> 66.7). Equal weights, because no calibration supports any other weighting.
5. **Explanation.** The card lists every metric: raw value, peer median, percentile, direction, and the peer-set size. A metric left out is listed with its reason.
6. **Determinism.** Inputs come from the metric snapshot for *t* and `data_version`; `SCORECARD_VERSION` joins the engine identity.

## 3. Stock dimensions

| Dimension | Metrics (direction) | Templates |
|---|---|---|
| **Financial quality** | ROCE ↑, ROE ↑, operating margin ↑, cash conversion (CFO/PAT 3Y) ↑, D/E ↓, interest coverage ↑ | general |
| | ROA ↑, ROE ↑, net margin ↑, GNPA ↓ (when available) | bank, nbfc |
| **Growth** | Sales CAGR 3Y ↑, profit CAGR 3Y ↑, sales growth TTM ↑, profit growth TTM ↑ | all |
| **Valuation** | PE ↓, PB ↓, EV/EBITDA ↓, price/sales ↓ | general |
| | PE ↓, PB ↓ | bank, nbfc |
| **Momentum** | Display only: Momentum25 qualified, rank, momentum score, RS rating from the production run | all |
| **Risk** | 1Y volatility of daily returns ↓, max drawdown 3Y ↓ (shallower is better), D/E ↓ (general), beta 3Y vs Nifty 500 ↓ | all |

**Watch points** (the rule list in [03 §1.6](03-product-specs.md#16-strengths-and-watch-points)) sit beside the cards, never inside a score.

## 4. Fund dimensions

| Dimension | Metrics (direction) |
|---|---|
| **Performance consistency** | Rolling 3Y beat-category % ↑, rolling 3Y beat-benchmark % ↑ (if TRI), rolling 3Y median CAGR ↑, calendar-year returns in top half of category (count of last 5) ↑ |
| **Risk** | Volatility 3Y ↓, max drawdown 5Y ↓, downside capture 3Y ↓ (if TRI) |
| **Cost** | TER ↓, Regular-minus-Direct gap ↓ (Regular plans only) |
| **Diversification** | Effective number of holdings ↑, top-10 weight ↓ (equity and hybrid only) |

Debt funds need credit-quality and duration metrics (rating mix, modified duration, YTM). Those come from disclosures not covered in [04](04-data-sources.md). Until then, debt funds get Performance consistency, Risk and Cost only, and the card says why.

## 5. Calibration and approval gate

Before any scorecard ships:

1. **Owner approval** of the metric lists, directions, peer rules, coverage rule and bands above.
2. **Stability check (descriptive, not predictive).** On the in-sample period only, report how often a stock's band changes month to month. A band that flips for more than 40% of instruments each month is too noisy to show; the dimension is redesigned. The sealed hold-out is not read.
3. **Sanity cases.** A hand-checked list of 10 well-known companies and 10 funds, with expected bands written down before the run, reviewed by the owner.
4. **Language review.** Every card's text passes the CLAUDE.md writing rules: no "strong buy", no "undervalued"; say "PE in the lowest fifth of its industry".

## 6. Display

```text
┌ Scorecard · ABC Ltd · Industry: Specialty Chemicals (23 peers) · 21 Oct 2026 ┐
│ Financial quality  ██████████░  High   82   ROCE 31% (median 18%) …   [Why] │
│ Growth             ██████░░░░░  Middle 55   Sales 3Y 14% (median 12%) …       │
│ Valuation          ██░░░░░░░░░  Low    21   PE 48 (median 31) …               │
│ Momentum           Momentum25: qualified · rank 4 · RS 93       (display only)│
│ Risk               ███████░░░░  Middle 61   Volatility 28% …                  │
│ Watch points: Cash from operations is less than half of profit over 3 years   │
│ Descriptive comparison with industry peers. Not a recommendation.             │
└───────────────────────────────────────────────────────────────────────────────┘
```

Bars use the sea-green accent at three steps; no red/green "good/bad" colouring.
