# 01 — Competitive Capability and Parity Matrix

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Desk research on 2026-10-22 from public pages, help articles and reviews. Clean-room rule (ADD A1 §1a) applies: observable behaviour and public documentation only; no code, assets, branding or distinctive visual designs.

## 1. Method and limits

- Sources: each product's public pages, help centre and blog, plus third-party reviews (marked **[3P]**). Several first-party pages blocked automated reading (Value Research, TradingView pricing, Tickertape pricing). A claim we could not confirm is marked **UNVERIFIED**.
- This is a capability study, not a hands-on audit. The 2026-10-19 OpenChart audit had the same limit. **Owner action:** a 60-minute hands-on walkthrough of each product closes the UNVERIFIED rows. Use the checklist in §5.
- Prices and plan limits change often. None is used as a design input.

## 2. What each product is best at

| Product | Core strength | Signature journey | What we learn |
|---|---|---|---|
| **TradingView** | Charting and drawing; a chart-first workspace | Symbol → chart → indicators/drawings → alert → layout | Wickstreet already matches its workspace patterns (M11–M15, Phase B). Plans limit *quantity* (charts per tab, alerts, indicators), not feature classes. |
| **Tickertape** | Stock and fund research for retail users; Scorecard | Search → stock page → scorecard → screener | Peer-relative 0–10 cards: Performance, Valuation, Growth, Profitability, plus Entry Point and Red Flags (Pro). Red flags sit apart from quality scores ([Tickertape blog](https://www.tickertape.in/blog/introducing-scorecard-stock-analysis-got-quicker-and-better-with-quantitative-insights/)). |
| **Screener.in** | Dense financial history; query-language screens | Search → one long company page → custom ratio → screen | One page per company with sections: peers, quarterly results, P&L, balance sheet, cash flows, ratios, documents. Screens are text queries over 10+ years of data; users define ratios by formula; machine-generated pros/cons with a caution note ([features](https://www.screener.in/features/), [custom ratios](https://support.screener.in/article/32-how-to-create-custom-ratios-in-screener)). |
| **Value Research** | Mutual-fund analysis and ratings | Category → fund page → compare → portfolio tool | Ratings are category-relative: a return score minus a risk score, weighted 60% 5-year and 40% 3-year for equity funds; refreshed monthly ([methodology](https://www.valueresearchonline.com/fund-rating-methodology/), via search snippet). The Portfolio tool shows stock exposure across funds, overlap, sector and geography ([VRO story](https://www.valueresearchonline.com/stories/224839/mutual-fund-portfolio-diversification/)). |

## 3. Parity matrix

**Status key.** ✅ Implemented · 🔧 Implemented, needs improvement · 🔴 Missing, essential · 🟡 Missing, desirable · 🔒 Depends on external data or licensing. "Ref" names the products that offer the capability (TV TradingView, TT Tickertape, SC Screener.in, VR Value Research). The target phase is from [10](10-roadmap.md).

### 3.1 Search, navigation, workspace

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Global search from anywhere (`/`, Ctrl+K) | TV TT SC VR | Equities only | 🔧 | 3 (all asset types) |
| Watchlists | TV TT SC VR | One watchlist with live detail | 🔧 | 5 (multiple lists, funds/ETFs) |
| Saved workspaces and layouts | TV | ✅ server-side, ETag merge | ✅ | — |
| Context-preserving navigation | — | `?from=` return path, replay `as_of` | ✅ | extend in every phase |
| Keyboard access, dialogs | TV | ✅ shortcuts dialog, keyboard map | ✅ | — |
| Light/dark themes | TV TT SC VR | ✅ | ✅ | — |
| Mobile layout | TV TT SC VR | Desktop-first; chart usable on tablet | 🔧 | each phase's acceptance |

### 3.2 Charting and technical analysis

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Chart types, scales, 1D/1W/1M | TV | ✅ | ✅ | — |
| Indicators | TV | Backend-authoritative set + browser studies | ✅ | — |
| Drawing tools | TV | 21 tools | ✅ | — |
| Multi-chart, sync | TV | Up to 4×4 | ✅ | — |
| Bar replay | TV | EOD replay with server `as_of` | ✅ | — |
| Alerts | TV TT SC | Daily, price and indicator, trendline | ✅ | — |
| Intraday, tick data | TV | None | 🔒 out of scope (A1 §4) | — |
| Scripting language | TV | None | Out of scope (A1 §4) | — |
| Fundamentals on chart (EPS, revenue markers) | TV | None | 🟡 | 2 |
| NAV chart for funds, ETF price vs NAV | TT VR | None | 🔴 | 3 |

### 3.3 Company research

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Company overview with key metrics | TT SC | Score and technical view only | 🔴 | 1 |
| Business description, sector, industry | TT SC | `sector`/`industry` empty | 🔒 classification source | 1 |
| Quarterly and annual P&L | TT SC | None | 🔴 🔒 | 1 |
| Balance sheet, cash flow | TT SC | None | 🔴 🔒 | 1 |
| Standalone vs consolidated | SC (UNVERIFIED) | None | 🔴 | 1 |
| Restatement history, "as published" view | — | None | 🔴 (Wickstreet differentiator) | 1 |
| Ratios over time | TT SC | None | 🔴 | 1 |
| Peer comparison | TT SC | None | 🔴 | 1 |
| Custom ratios by formula | SC | None | 🟡 (needs a formula language: out of scope per A1 §4; revisit) | — |
| Shareholding pattern, pledges | TT SC | None | 🟡 🔒 | 6 |
| Filings and documents | SC | None | 🟡 🔒 | 6 |
| Machine-generated strengths/risks | TT SC | None | 🟡 | 1 (rule-based, §1.6 of [03](03-product-specs.md)) |
| Analyst forecasts | TT | None | Not planned (licensed data, not deterministic) | — |

### 3.4 Screening

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Technical and momentum screen | TV TT | Momentum25 run, client-side filters | ✅ | — |
| Fundamental filters | TT SC | None | 🔴 | 2 |
| Compound AND/OR logic | SC | AND only, fixed fields | 🔧 | 2 |
| Saved screens | TT SC | ✅ server document | ✅ | extend in 2 |
| Presets | TT | None | 🔴 | 2 |
| Point-in-time historical screen | — | Momentum25 only (historical screening, Studio) | 🔧 | 2 (Wickstreet differentiator) |
| Per-row explanation of pass/fail | — | Momentum25 rule matrix | 🔧 | 2 (all fields) |
| Export (CSV) | TT SC | None | 🔴 | 2 |
| Screen alerts ("new stocks entered") | SC | None | 🟡 | after 2 |
| Mutual-fund screener | TT VR | None | 🔴 🔒 | 3 |
| ETF screener | TT | None | 🔴 🔒 | 3 |

### 3.5 Mutual funds and ETFs

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Fund overview (category, AUM, TER, exit load, manager) | TT VR | None | 🔴 🔒 | 3 |
| Trailing and calendar-year returns | TT VR | None | 🔴 🔒 | 3 |
| Rolling returns | VR (UNVERIFIED) | None | 🔴 | 3 |
| Risk ratios | TT VR | None | 🔴 (Sharpe needs a risk-free series 🔒) | 3 |
| Benchmark comparison on TRI | VR | Price index only | 🔒 TRI licence | 3 |
| Category ranking | TT VR | None | 🔴 | 3 |
| Fund ratings (stars) | VR | None | Not planned; scorecards are descriptive ([09](09-scorecards.md)) | — |
| SIP / lump-sum calculator | TT VR (UNVERIFIED) | None | 🔴 | 3 |
| Holdings, sector and size exposure | TT VR | None | 🔴 🔒 | 4 |
| Holdings change across disclosures | VR (UNVERIFIED) | None | 🔴 | 4 |
| Fund overlap | VR; common in Indian tools (pairwise, sum of minimum weights) | None | 🔴 | 4 |
| Fund → stock → chart → Momentum25 | — | None | 🔴 (signature) | 4 |
| "Which funds hold this stock" | TT (UNVERIFIED) | None | 🔴 | 4 |
| ETF premium/discount, tracking error, liquidity | (UNVERIFIED for all four) | None | 🔴 🔒 TRI | 3 |
| Intraday iNAV, bid-ask spread | TV (feeds) | None | Out of scope (EOD) | — |

### 3.6 Portfolio

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Manual holdings, CSV import | TT VR | None | 🔴 | 5 |
| CAS import (CAMS/KFintech/NSDL/CDSL) | common in Indian tools | None | 🔴 (user's own data) | 5 |
| Broker sync | TT [3P] | None | Out of scope (prompt §8) | — |
| XIRR, CAGR, absolute return | TT VR | None | 🔴 | 5 |
| Asset allocation, sector, market cap | TT VR | None | 🔴 | 5 |
| Look-through to underlying stocks | VR | None | 🔴 | 5 |
| Overlap across holdings | VR | None | 🔴 | 5 |
| Drift and rebalancing | — | None | 🔴 | 5 |

### 3.7 Scores and ratings

| Capability | Ref | Wickstreet today | Status | Phase |
|---|---|---|---|---|
| Stock scorecards by dimension | TT | Momentum25 score, explained per rule | 🔧 | 5 |
| Red-flag list separate from scores | TT | Risk engine (technical) | 🔧 | 1 (fundamental flags) |
| Fund ratings | VR | None | Descriptive dimensions only | 5 |
| Composite "buy" score | TT (Entry Point) | None | Not planned without formula, calibration and approval (prompt §7) | — |

## 4. Where Wickstreet should differ

1. **Point-in-time everything.** No reviewed product clearly shows financials "as published on a date", or screens a past date with only then-public data. Wickstreet already has the machinery (ADR-014 §7).
2. **Every number explains itself.** Click any metric → formula, inputs, filing, publication date, state (`NM`/`NA`) and reason.
3. **One workstation.** Fund → holding → chart → Momentum25 → back to the fund, with context kept. The reviewed products split these into separate pages and products.
4. **Local and private.** Portfolios never leave the machine.
5. **No proprietary star rating.** Descriptive dimensions with peer percentiles, not opaque verdicts.

## 5. Hands-on checklist (closes UNVERIFIED rows)

For each product, in a browser, record: (a) the company page sections and history depth; (b) the consolidated/standalone switch; (c) the screener's field count, logic and export; (d) the fund page's returns windows, rolling returns, risk ratios and holdings depth; (e) overlap tool inputs and method; (f) ETF page fields; (g) portfolio import formats. Screenshots stay in `audit-evidence/`, never in the product.

## Sources (accessed 2026-10-22)

- Tickertape Scorecard: <https://www.tickertape.in/blog/introducing-scorecard-stock-analysis-got-quicker-and-better-with-quantitative-insights/>; pricing <https://www.tickertape.in/pricing>; [3P] <https://www.strike.money/reviews/tickertape>
- TradingView plans: <https://www.tradingview.com/pricing/>
- Screener.in: <https://www.screener.in/features/>, <https://support.screener.in/article/32-how-to-create-custom-ratios-in-screener>, <https://support.screener.in/article/15-using-excel>
- Value Research: <https://www.valueresearchonline.com/fund-rating-methodology/>, <https://www.valueresearchonline.com/fund-rating-faq/>, <https://www.valueresearchonline.com/stories/224839/mutual-fund-portfolio-diversification/>
- Overlap method (sum of minimum weights) as used by other tools: <https://stockanalysis.com/tools/fund-holdings-overlap/tutorial/>, <https://primeinvestor.in/mutual-funds-overlap/>
