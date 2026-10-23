# Wickstreet 2.0 — Complete MF platform: scope and slice sequence

> **Status: Accepted (owner decisions, 2026-10-23).** This is the governing scope and roadmap for Wickstreet 2.0. Build the complete personal-use application first; future SaaS requirements do not obstruct it ([ADR-023 U13](../../architecture/adr/ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23)).

## 1. Owner decisions (2026-10-23)

- **Product.** Wickstreet 2.0 is a local, single-user, personal MF research and investment intelligence workstation. SaaS is a future phase, not the current target.
- **Scope.** Everything for mutual funds belongs in 2.0, including Tickertape's MF feature set and capabilities beyond it. Nothing moves to 3.0 because it needs more development. 3.0 is stocks, equity fundamentals, Momentum25 integration and cross-asset research.
- **Personalised guidance.** Personal mode has AI-driven fund recommendations, best-fund rankings, composite scores, suggested allocations, rebalancing, portfolio optimisation and actionable insights. This is the owner's own tool, not a publicly offered advisory service.
- **Real data.** Product workflows use actual MF data and the owner's real CAS statements, analysed locally. Synthetic data is only for automated tests and benchmarks.
- **Privacy.** CAS files, passwords and portfolio records stay on the owner's machine and never enter the repository, logs, test fixtures or telemetry.
- **Modes.** SaaS licensing, regulatory and commercial requirements apply before public deployment in SaaS mode. They are not blockers to personal-mode development.
- **Completion criterion.** A polished MF research workstation that matches Tickertape's relevant MF capabilities and surpasses them in analytics, usability and AI assistance.

## 2. Capabilities, specs and gaps

| Capability | Spec | Built | To build |
|---|---|---|---|
| Fund discovery, curated collections, advanced search | [03 §2.2](03-product-specs.md#22-fund-discovery-and-screening), [06](06-unified-screener.md) | Search by name, code, ISIN (Slice 2) | Collections (presets), synonyms |
| Screening: 60+ filters, custom formulas, saved and prebuilt screens | [06](06-unified-screener.md), [ADR-018](../../architecture/adr/ADR-018-unified-screening.md) | 46 fields, filter tree, sort, cursor (Slice 2) | Fields from §3; formula language; saved screens |
| Fund research: profiles, managers, AUM, TER, riskometer | [03 §2.3](03-product-specs.md#23-fund-page-sections-fundplanid) | Attributes from AMFI's master | Data E1 |
| Performance: CAGR, rolling, annual, consistency, comparisons | [03 §2.5](03-product-specs.md#25-fund-metric-dictionary) | Trailing, since-first-NAV, rolling summaries, compare (Slice 2) | Annual returns, rolling series, consistency |
| Risk: drawdowns, volatility, Sharpe, Sortino, beta, alpha, VaR | [03 §2.4–2.5](03-product-specs.md#24-plain-language) | Volatility, max drawdown | Drawdown dates and recovery, downside deviation, VaR/CVaR, Sortino; Sharpe with E2; beta and alpha with E3 |
| Benchmark analysis: TRI, tracking error, category ranks | [03 §2.5](03-product-specs.md#25-fund-metric-dictionary) | — | Category ranks (Slice 3); TRI work with E3 |
| Portfolio holdings: securities, sector, allocation, concentration | [08 §1](08-holdings-overlap-portfolio.md#1-holdings-intelligence-per-fund), [ADR-019](../../architecture/adr/ADR-019-portfolio-look-through.md) | — | Data E4 |
| Peer comparison across performance, risk, cost, holdings | [03 §2.7](03-product-specs.md#27-compare-comparefundsplans) | Compare of 2–5 funds on NAV metrics | Costs (E1), holdings (E4) |
| Portfolio intelligence: CAS import, XIRR, diversification, overlap | [08 §3–§6](08-holdings-overlap-portfolio.md#3-overlap), [ADR-019](../../architecture/adr/ADR-019-portfolio-look-through.md) | — | Slice 6 |
| Investment guidance: recommendations, best-fund rankings, allocations, rebalancing, optimisation | [ADR-023 U13](../../architecture/adr/ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23), [ADR-020](../../architecture/adr/ADR-020-descriptive-scorecards.md) point 4 | — | Slices 3, 5, 6 |
| Calculators: SIP, SWP, STP, lump sum, tax, simulations | [03 §2.6](03-product-specs.md#26-sip-and-lump-sum-simulation) | — | Slice 3 |
| Personal workspace: watchlists, saved screens, alerts, notes, exports | [06 §5](06-unified-screener.md#5-saved-screens-and-presets), ADR-023 tenancy | Tenancy and RLS harness (Slice 0) | Slice 4 |
| AI agent: English, Hindi, Hinglish, across all MF capabilities | [18](18-multilingual-research-agent.md), [ADR-022](../../architecture/adr/ADR-022-multilingual-research-agent.md) | — | Slice 5 |

## 3. NAV analytics to add (method v3)

These need no new data. Each choice below is the method default; the method version records it, and a later change bumps the version.

| Group | Fields | Method |
|---|---|---|
| Annual | Calendar-year and April–March financial-year returns; monthly return heatmap | Partial first and last years shown, labelled "partial" |
| Rolling | Full 1Y/3Y/5Y rolling series for charts; `roll_3y_beat_cat_pct` | Consistency = share of rolling 3Y windows above the category median on the same dates |
| Drawdown | Peak, trough and recovery dates, drawdown duration, time to recover, worst 1M/3M/1Y periods | "Not recovered" when the NAV has not regained the peak |
| Downside risk | Downside deviation, Sortino, historical daily VaR and CVaR at 95% | Threshold 0% until the risk-free series (E2) arrives, then the T-bill yield; labelled |
| Peers | Category percentile, median, quartile and rank ("4 of 31") for each return and risk field | Peer group = canonical category × plan × option, active funds only |
| Scores | Composite scores and best-fund rankings by category | Versioned formula over registry fields; the owner sets the weights; default equal weights over consistency, risk-adjusted return, drawdown and (with E1) cost |
| Comparison | Daily-return correlation; return-per-risk comparisons | Common dates only |
| Status | `status` = active, historical or no NAV | No view shows the three as equal |
| Categories | Fewer Unclassified funds | First from stored evidence, such as another plan-option of the same scheme with a current AMFI label |

Snapshot fields are those a screen filters on. Per-fund views (rolling series, heatmaps, simulations, correlations) compute on request from one fund's series.

**Calculators.** An instalment buys at the first NAV on or after its scheduled day. Stamp duty 0.005% from 2020-07-01, checked against the notification before use. Exit loads apply once E1 supplies them. Tax follows the capital-gains rules in force on each sale date, with the rule set versioned.

## 4. Data enrichment

Each dataset follows the Slice 1 pattern: an import contract, raw files kept, append-only revisions, reconciliation, and a grant in the rights register (which fails closed).

| # | Dataset | Unlocks | Candidate source |
|---|---|---|---|
| E1 | TER, AUM, exit load, minimum amounts, managers, riskometer, benchmark name | Costs, fund profile, cost screens and scores | AMFI's TER and AUM disclosures; AMC factsheets and scheme documents |
| E2 | Risk-free series (91-day T-bill yield) | Sharpe, Sortino against risk-free, alpha | RBI data |
| E3 | Benchmark TRI history, each scheme's benchmark over time | Beta, alpha, capture ratios, tracking error and difference, beat-benchmark | NSE Indices, BSE indices |
| E4 | Monthly portfolio disclosures | Holdings, sector and asset mix, concentration, overlap, look-through | Each AMC's monthly files |

## 5. Slice sequence

| Slice | Delivers |
|---|---|
| 3 | NAV analytics v3 (§3), composite scores and best-fund rankings, screener v2 (60+ fields, presets, custom formulas over registry fields), calculators (SIP, SWP, STP, lump sum, tax), the status field |
| 4 | Research workstation UI: screener, fund page tabs, compare, calculators; personal workspace (watchlists, saved screens, notes, alerts, exports) |
| 5 | Multilingual agent over every service, including recommendations and allocations with their evidence |
| E1–E4 | One slice per dataset; each adds its fields to the registry, fund page, compare, scores and agent tools |
| 6 | Portfolio intelligence: real CAS import (parsed locally, password in memory only), transactions, XIRR, allocation, overlap, concentration, suggested allocations, rebalancing and optimisation |
| 7 | Release polish: the parity check against Tickertape's MF features, performance, accessibility, docs |

Slices 3 to 6 need no SaaS work. 2.0 is complete when every row of §2 is built.

## 6. Open items

| Item | Why it is open |
|---|---|
| Sources for E1–E4 | Each dataset needs a chosen source and a grant recorded in the rights register before ingestion. NSE Indices' TRI terms could not be read before |
| Method v2 review | The Slice 2 option-rule fix is in use; the owner may review it |
| SaaS phase | Commercial data permissions, regulatory classification, the CAS isolation worker and security review apply before public deployment (A3, doc 13); not now |
