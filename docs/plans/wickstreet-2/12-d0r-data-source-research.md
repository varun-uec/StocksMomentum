# Wickstreet 2.0 — D0-R: Data Source Research and Feasibility

> Desk research, 2026-10-22. Builds on blueprint [04-data-sources.md](04-data-sources.md) and the [M16 NSE data-use check](../../audits/2026-10-19-m16-nse-data-use.md).
> Status: research for owner review. **This is not legal advice.** No code was changed. No charges were incurred, no paid dataset was opened and no market data was imported.

**Historical scope; current SaaS boundary:** Sections A–H and the final answers record the earlier personal/self-hosted sourcing exercise. Their per-instance costs, bring-your-own-key recommendations and owner-decision defaults are historical, not a data-supply model approved for centrally hosted Wickstreet 2.0. The proposed ADRs cited below remain proposed; no personal licence, user's download or public endpoint establishes Wickstreet's commercial retrieval, shared storage, derived-use, free/paid display or redistribution rights. The [canonical release plan](13-wickstreet-2.0-mf-first-release-plan.md), [Stage B permissions gate](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate) and [B0 cost envelope](15-stage-b0-product-and-value-specification.md#6-data-rights-and-199-cost-envelope) control current decisions.

No commercial MF supplier, permission or quotation has been established. Before committing to a dependent feature, verify the contracting entity, coverage and corrections, shared caching, derived analytics, free and paid users, reports/exports, historical retention/replay and termination/deletion rights. Separate fixed licence minimums from usage/subscriber charges, including free-user load. A ₹0 licence remains conditional; unknown costs are not zero. No vendor contact, procurement or ingestion is authorized by this reconciliation.

**Regulatory currency:** disclosure references below were checked against the June 2024 MF circular only. The [20 March 2026 MF Master Circular](https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html), effective 1 April 2026, replaced it. Recheck the selected fields against that circular and subsequent changes before implementation/publication; this note does not revalidate the historical deadlines or grant commercial data rights.

**Confidence labels used throughout**
- **V** = verified during the original dated research on the supplier's own page or the regulator's own text; not a fresh verification for SaaS use.
- **C** = conditional: the evidence supports it, but it depends on a term not yet read, a test not yet run, or an interpretation that needs confirmation.
- **U** = unverified: secondary sources only, or no evidence found.

**What is new since blueprint 04** (read today for the first time):
- BSE's disclaimer, NSE Indices' terms of use and disclaimer, NSE's Data Sharing & Usage Policy and NSE's 2026 tariff. All were unreadable on 2026-10-22 morning (403/timeout); a real browser read them.
- The SEBI Master Circular for Mutual Funds (2024-06-27) text, so the disclosure deadlines are now verified.
- `casparser` is now MIT on `pypdfium2`, with no GPL backend. Blueprint row S16 is out of date.
- Asia Index became BSE Index Services on 2025-08-01. `asiaindex.co.in` is now a parked domain.
- Retail-priced options: EODHD, Trendlyne, broker APIs.

---

## A. Data Requirements Inventory

**Have** = an existing Wickstreet pipeline gives it. **Derive** = computable locally from other datasets. **Need** = needs a new source.

| # | Dataset | Used by | Fields | Depth | Frequency | Point in time | Status |
|---|---|---|---|---|---|---|---|
| R1 | Daily equity bars | All (exists) | OHLCV | 1994 → today | Daily | Trade date | **Have** (`ohlcv_daily`, legacy tables). The source itself carries the open NSE licence question from M16. |
| R2 | Corporate actions | W1, W5 | Split, bonus, rights; **cash dividends** (ex, record, pay dates, amount) | 10y+ | Event | Announcement date | **Partly have**: splits, bonuses and rights exist; dividends are skipped (gap G11) |
| R3 | Security master | All | Symbol, ISIN, name, listing and delisting, **instrument type** | Full | On change | Effective date | **Partly have**: no instrument type, no CIN |
| R4 | Company master | W1 | CIN, legal name, ISIN ↔ company link | Full | On change | Effective date | **Need** |
| R5 | Industry classification | W1, W2, W4 | 4 levels (macro-sector, sector, industry, basic industry) | Since 2022 structure | Annual review | `valid_from` | **Need**. `securities.sector` is empty (gap G2) |
| R6 | Financial statements | W1, W2 | P&L, balance sheet, cash flow; quarterly, half-yearly, annual; standalone and consolidated; bank and NBFC templates | 12 quarters, 10 FY | Event | **Filing receipt time**; restatements append | **Need** |
| R7 | Shares outstanding | W1, W2 | Share count per ISIN | 10y | Quarterly (shareholding pattern) | Filing date | **Need** (gap G4) |
| R8 | Market cap, PE, PB, ROCE, … | W1, W2 | Metric dictionary 03 §1.4 | As R6 | Daily | Inherits R1/R6/R7 | **Derive** from R1 + R6 + R7 |
| R9 | MF scheme master | W3, W4, W5 | Plan code, ISINs, AMC, category, benchmark, launch date, plan/option, index-fund and ETF flags | All schemes | On change | Effective date | **Need** |
| R10 | NAV history | W3, W5 | Plan code, date, NAV | Since 2006 for `si` returns | Daily | NAV date | **Need** |
| R11 | AUM | W3 | Scheme AUM, date | 5y+ | Monthly | Month end + lag | **Need** |
| R12 | Costs | W3 | TER per plan (daily), exit load, minimums | History | On change | Effective date | **Need** |
| R13 | Managers, riskometer | W3 | Names, start dates; riskometer level | Current + history | On change | Effective date | **Need** |
| R14 | IDCW distributions | W3, W5 | Record date, amount per unit | History | Event | Record date | **Need** |
| R15 | Benchmark **TRI** | W3 | Index code, date, TRI close | 10y+ | Daily | Date | **Need**. Only price indices exist (gap G8) |
| R16 | Risk-free rate | W3 | 91-day T-bill yield | 10y+ | Weekly | Auction date | **Need** |
| R17 | Size buckets | W1, W3 | Large/Mid/Small per company | Since 2017 | Half-yearly | List date | **Need** (AMFI list) or **Derive** from R1 × R7 (an approximation) |
| R18 | Fund holdings | W4, W5 | Scheme, portfolio date, ISIN, quantity, value, % of NAV, industry, rating | 3y+ | Monthly (debt fortnightly) | Portfolio date + publication date | **Need** |
| R19 | ETF bars | W3 | OHLCV | As R1 | Daily | Trade date | **Have**: ETFs trade on NSE and sit in `ohlcv_daily` |
| R20 | ETF NAV | W3 | As R10 | As R10 | Daily | NAV date | Same source as R10 |
| R21 | Tracking error, tracking difference | W3 | TE 1y, TD 1y/3y | 3y+ | Daily / monthly | Date | **Derive** from R10 + R15, or read the AMC/AMFI disclosure |
| R22 | iNAV | — | Intraday | — | Intraday | — | **Out of scope** (ADD A2 §4: no intraday) |
| R23 | User transactions | W5 | Date, instrument, kind, quantity, price, charges | User's history | On import | Trade date | **Need**, from the user's own statements |
| R24 | Category medians, overlap, look-through, sector exposure | W3–W5 | — | — | — | Inherits | **Derive** from R9, R10, R18, R5 |

**Requirements from open-source, self-hosted distribution** (ADR-012, ADR-015, ADR-021):
- The project ships no data and runs no shared service.
- Each user's instance must get data the user is entitled to use. The project must not ship a tool built to breach a supplier's terms.
- Each use needs its own right: `store`, `display`, `historical_evaluation`, `automated_retrieval`, `redistribution` (Stage A invariant I-1).
- Point-in-time use needs a publication time per fact (I-3). A source without receipt times gives `estimated` rows only.
- Every dependency must be Apache-2.0-compatible (ADR-015).

---

## B. Data Source Feasibility Matrix

### B1. Exchanges, index providers, regulators and industry bodies

| Source | Datasets | Coverage | Retrieval | Cost | PIT | Reliability and maintenance | Self-hosted fit | Conf. |
|---|---|---|---|---|---|---|---|---|
| **NSE website and archives** ([terms](https://www.nseindia.com/static/nse-terms-of-use)) | Bhavcopy (R1, R19), corporate actions (R2), equity list with ISIN (R3), results PDF + XBRL (R6), shareholding XBRL (R7) | All NSE listings | Download pages and files | Free to view | XBRL carries exchange receipt time | High uptime. Format and URL drift. | **Poor**: automation and simulation are barred (§C) | V (terms), C (XBRL receipt time) |
| **NSE Data & Analytics** (licensed) ([tariff, effective 2026-04-01](https://www.nseindia.com/static/market-data/products-tariff)) | EOD Capital Market data; EOD Corporate Data; Corporate Data feed ("company fundamentals, corporate announcements, and shareholding pattern"); Master Data; historical trade data | Full NSE | Online server or leased line; agreement | EOD CM ₹1,00,000/yr per site per medium. EOD Corporate Data ₹5,00,000/yr. Corporate Data feed ₹10,60,000/yr. Master Data ₹2,15,000/yr. Historical trade data ₹1,10,000/yr. Students/researchers: historical trade data ₹22,000/yr. All exclude tax. | By product | Official, low format risk | **Poor**: priced per site for firms. No individual tier is published. | V |
| **BSE website** ([disclaimer](https://www.bseindia.com/disclaimer)) | Bhavcopy, corporate filings and XBRL, corporate actions | All BSE listings | Download | Free to view | Receipt time on filings | As NSE | **Poor**: reproduction barred (§C) | V |
| **NSE Indices** ([terms](https://www.niftyindices.com/terms-of-use), [disclaimer](https://www.niftyindices.com/disclaimer), [data subscription](https://www.niftyindices.com/offerings/data-subscription)) | Index levels, **TRI** (R15), constituents, 4-level industry classification (R5) | All Nifty indices | Web reports; licensed EOD constituent files via `indices@nseids.co.in` or Bloomberg, FactSet, IHS Markit, MSCI, Rimes, Thomson Reuters | Quote only | Dated | Stable | **Poor** without a licence | V (terms), U (price) |
| **BSE Index Services** (ex Asia Index, renamed 2025-08-01) | Sensex family levels and TRI | BSE indices | Web; licence | Quote only | Dated | `asiaindex.co.in` is parked (seen 2026-10-22); new terms page not found | Unknown | V (rename, parked domain), U (terms) |
| **AMFI** ([terms](https://www.amfiindia.com/terms-of-use)) | NAV daily and history (R10, R20), scheme master (R9), TER (R12), market-cap list (R17), tracking error/difference (R21), AUM (R11), mirrored AMC portfolios (R18) | All schemes; NAV since 2006 | Flat files, web reports | Free | NAV date; no revision log | Official and stable | **Poor** without written permission (§C) | V |
| **AMC websites** (≈45 AMCs) | Monthly and half-yearly portfolios (R18), TER (R12), TE/TD (R21), SID/KIM (R13), IDCW history (R14), factsheets | Per AMC | Spreadsheets and PDFs | Free | Portfolio date; publication time must be captured at download | **High** effort: each AMC has its own layout | **Fair** for manual, personal download, AMC by AMC (§C) | V (SEBI mandate, HDFC terms), U (other AMCs) |
| **SEBI** ([MF master circular 2024-06-27](https://www.taurusmutualfund.com/sites/default/files/downloads/SEBI_Master_Circular_for_MF_27_6_2024.pdf)) | Rules only: categories, disclosure deadlines, TE/TD formulas | — | Circular text | Free | — | — | **Good**: encode rules by hand with citations | V |
| **MCA21 V3** | Annual statutory financials (AOC-4, XBRL), company master (R4) | All companies | Per company document view; no bulk API | ₹100 per company (U) | Filing date; lag of months | Slow portal | **Poor** for financials; fair for single lookups | U |
| **data.gov.in (OGD)** | MCA company master by RoC: CIN, name, status, class, capital (R4) | ≈3.6 M companies | CSV and API with a free key | Free | Snapshot | Government portal | **Good** for R4 if the dataset page names GODL-India | C |
| **RBI DBIE** | 91-day T-bill yields (R16) | Decades | Download | Free | Auction date | Stable | **Good** if the current terms match the old DBIE disclaimer | C |
| **FBIL** | T-bill benchmark rates | Daily | Web | Free to view | Date | Stable | Redistribution needs a licence (secondary source) | U |

### B2. Brokers (the user's own account and API key)

| Source | Datasets | Cost | History | Notes | Conf. |
|---|---|---|---|---|---|
| **Zerodha Kite Connect** ([charges](https://support.zerodha.com/category/trading-and-markets/kite-api/articles/what-are-the-charges-for-kite-apis)) | **Personal**: orders, portfolio (holdings, positions), no market data. **Connect**: adds historical candles and WebSocket data | Personal free. Connect ₹500 per app per month. From October 2026, ₹500 in credits if the user pays ₹2,000+ brokerage in a month | Not stated on the pricing page | `kite.py` exists. The instruments dump has no ISIN. Data-use terms not read. | V (price), U (terms) |
| **ICICI Direct Breeze** ([home](https://api.icicidirect.com/apiuser/home)) | Orders, portfolio, historical data | Free, "including historical data" | 3 years per ICICI; 10 years per a third party | — | V (price), U (depth, terms) |
| **Fyers API v3** ([page](https://fyers.in/fyers-api/)) | Orders, portfolio, history | Free | 20+ years daily per an older Fyers post | — | V (price), U (depth, terms) |
| **Angel One SmartAPI** | Orders, portfolio, historical candles | Free | Not stated; per-request candle caps reported | — | V (price), U (depth, terms) |
| **DhanHQ** ([FAQ](https://dhan.co/support/platforms/dhanhq-api/is-the-dhanhq-data-api-subscription-free-if-i-execute-a-minimum-number-of-trades-every-month/)) | Data API | ₹499 + tax per month | Intraday up to 5y | — | V (price) |
| **Upstox** | Orders, portfolio, historical candles | Free per third parties; some features behind "Upstox Plus" | Daily since 2000 per a community post | — | U |

No broker API found offers fundamentals, fund NAV history, fund holdings or TRI.

### B3. Commercial vendors

| Vendor | Datasets | Price | Licence for an individual | PIT | Conf. |
|---|---|---|---|---|---|
| **EODHD** ([pricing](https://eodhd.com/pricing), [terms](https://eodhd.com/financial-apis/terms-conditions)) | Global EOD (incl. NSE/BSE), fundamentals | Free: 20 calls/day, 1y, **no fundamentals**. Fundamentals plan $59.99/mo or $599.90/yr. All-in-one $99.99/mo or $999.90/yr | Non-professional users "are permitted to store, manipulate, and analyze the data for private, non-commercial purposes". Bars "displaying, or granting access" and account sharing. | No filing timestamps seen. Assume `estimated` rows. | V (price, terms), **U (India fundamentals depth and quality)**: some Indian listings show blank fields |
| **Trendlyne MCP connector** ([plans](https://trendlyne.com/subscription/mcp/plans/)) | Financials, quarterly results, shareholding, filings, EOD prices. **No mutual funds.** | Pro ₹299/mo (400 calls/day); Max ₹499/mo | "Individual use only". It is a tool-call connector for AI clients, not a bulk data licence. Storage rights not stated. | Unknown | V (price), U (storage) |
| **Screener.in** ([terms, 2018-08-01](https://www.screener.in/guides/terms)) | Financials, ratios, Excel export | Free / premium | "Personal, non-commercial transitory viewing only". Bars copying. Downloads must be destroyed when the licence ends. | — | V. **Not usable** as a stored source. |
| **CMIE Prowess, CMOTS, Accord (AceEquity), Capitaline, Morningstar India, Value Research** | Fundamentals, MF data, holdings, classifications | Quote only | Contract | Varies. Ask for `published_at` and restatement history. | U |
| **BharatStock API** | Financials, shareholding, corporate actions | Not found | Unknown | Unknown | U |

### B4. Open-source projects

| Project | Function | Licence | Data rights | Verdict | Conf. |
|---|---|---|---|---|---|
| **casparser** ([GitHub](https://github.com/codereverser/casparser)) | Parses CAMS and KFintech (detailed and summary) and NSDL/CDSL CAS PDFs | **MIT**, on `pypdfium2` (Apache-2.0/BSD-3). No GPL/AGPL dependency. | The user's own data | **Use**. MFCentral CAS is not supported. Maintained "in spare time". | V |
| **mftool**, AMFI scrapers | Fetch AMFI NAVs | MIT | A code licence does not grant AMFI's data rights | Do not ship as a fetcher | V |
| **mfapi.in** ([site](https://www.mfapi.in/)) | Free NAV JSON API | Terms links are `#` placeholders; source not named; "All rights reserved" | None stated | **Reject** (ADR-021 §6) | V |
| **captn3m0/historical-mf-data, mf-portfolio** | Republish AMFI data; parse AMC portfolios | — | Same AMFI and AMC questions | Use as format references only | C |
| **yfinance** | Yahoo prices and fundamentals | Apache-2.0 | README: Yahoo's API "is intended for personal use only" | **Reject** as a default | V |
| **nsepython, jugaad-data, bsedata, nselib** | Scrape NSE/BSE | Various | Breach NSE's automation clause | **Reject** | V |

### B5. User-portfolio channels

| Channel | What it gives | Access | Conf. |
|---|---|---|---|
| **CAMS/KFintech CAS** | All MF folios, transactions | Password-protected PDF by email | V |
| **NSDL/CDSL CAS** | Demat holdings + MF units across depositories. Monthly if there is activity, else half-yearly. | Password-protected PDF | C |
| **MFCentral CAS** | Summary or detailed, up to 365 days | PDF; no parser | C |
| **Broker tradebook / holdings export** | Equity trades, charges | CSV/XLSX | C |
| **Broker API with the user's key** (e.g. Kite Personal, free) | Holdings, positions | API | V |
| **Account Aggregator** | Consent-based statements | A Financial Information User must be a regulated entity (RBI/SEBI/IRDAI/PFRDA) | **Not available** to a self-hosted individual tool | C |

---

## C. Licensing Compatibility Matrix

✅ permitted · ❌ prohibited · ⚠️ restricted or unclear · ? not found. "Personal self-hosted use" means one user analysing on their own machine.

| Source | Automated retrieval | Local storage | Display in own app | Historical analysis / backtest | Redistribution / export | Via user's own key | Key wording (verbatim) | Conf. |
|---|---|---|---|---|---|---|---|---|
| **NSE website** | ❌ | ⚠️ copying allowed only for content "available for download" | ⚠️ | ❌ "simulation" barred | ❌ | n/a | "prohibited to conduct any systematic or automated data collection"; "shall not … use … for any gaming, virtual trading or simulation activities" | V (2026-10-19) |
| **NSE Data (licensed)** | ✅ by contract | ✅ by contract | By contract, "per medium" | By contract | ❌ "except as agreed" | n/a | "Market Data" includes "end of day data, historical data and corporate data". "The Board of NSE Data may also consider introducing reduced fee arrangements or waivers for Non-Commercial Users." Non-commercial users are "accredited academic institutions, members of academia and not for profit institutions/entities, Researchers, Students". | V |
| **BSE website** | ? (no clause) | ❌ on a plain reading | ⚠️ | ? | ❌ | n/a | "Any reproduction, redistribution or transmission, for consideration or otherwise … is strictly prohibited"; "No part of the information … may be reproduced or transmitted in any form by any means, without the express written consent of BSE." | V |
| **NSE Indices** | ❌ without written consent | ❌ "stored in a retrieval system" barred | ⚠️ | ❌ without a licence | ❌ | n/a | "personal, non-commercial use only"; "may not conduct any systematic or automated data collection … without our express written consent"; "Aggregate, copy or duplicate in any manner" barred; "Use or distribution of … index data … require[s] a license" | V |
| **BSE Index Services** | ? | ? | ? | ? | ❌ (old Asia Index disclaimer, secondary) | n/a | Terms page not found | U |
| **AMFI** | ? (no clause) | ❌ "any significant portion" | ⚠️ personal | ⚠️ "derivative works" barred | ❌ | n/a | "for your personal and non-commercial use only"; "You shall not store electronically any significant portion of any part of the Site"; "No other use … is authorised unless you and we have agreed otherwise in writing." No licensing contact is given. | V |
| **AMC sites** (HDFC read) | ? (no clause) | ✅ personal download | ✅ personal | ⚠️ not addressed | ❌ | n/a | "may download materials, data etc displayed on the Site for non-commercial and/or personal use only"; may not "reproduce, transmit, sell, display, distribute" | V (HDFC), U (≈44 other AMCs) |
| **SEBI rules** | n/a | ✅ | ✅ | ✅ | ✅ cite | n/a | Public regulation | C |
| **data.gov.in (GODL-India)** | ✅ API | ✅ | ✅ | ✅ | ✅ with attribution | ✅ free key | Licence page unreadable; secondary sources: commercial and non-commercial use, attribution required | C |
| **RBI DBIE** | ? | ✅ | ✅ | ✅ | ✅ with acknowledgement | n/a | Old DBIE disclaimer: "Reproduction is permitted provided an acknowledgement of the primary source is made." | C |
| **EODHD** | ✅ API | ✅ "store, manipulate, and analyze" | ⚠️ "displaying" barred; reads as display to others | ✅ "analyze" | ❌ | ✅ one key, no sharing | Quoted above | C |
| **Trendlyne MCP** | ✅ tool calls | ? | ? | ? | ? | ✅ "individual use only" | — | U |
| **Screener.in** | ❌ by implication | ❌ | ❌ | ❌ | ❌ | n/a | "transitory viewing only" | V |
| **Broker APIs** | ✅ own account | ? | ✅ (own use) | ? | ❌ (assumed) | ✅ | Broker data terms not read | U |
| **CAS / broker exports** | n/a | ✅ own data | ✅ | ✅ | User's choice | n/a | The user's own records | C |

**Unresolved questions that need supplier confirmation or legal review**
1. **NSE:** does a self-hosted, single-user backtest count as "simulation"? Does a person's manual download of the bhavcopy or results XBRL for personal analysis fall within "available for download"? (Affects R1, which Wickstreet already uses.)
2. **NSE Data:** is there a personal, non-display, single-user tier? Does the "reduced fee … for Non-Commercial Users" clause cover an individual investor, or only academia and not-for-profits?
3. **AMFI:** is a local NAV database "a significant portion of the Site"? Will AMFI grant written permission for personal, self-hosted storage? AMFI gives no licensing contact.
4. **NSE Indices / BSE Index Services:** a personal TRI licence, and its price.
5. **AMC sites:** do the other ≈44 AMCs permit personal download and storage of portfolio spreadsheets, as HDFC does?
6. **EODHD:** does "displaying" bar showing data to the subscriber in their own private app? Does EODHD license NSE/BSE fundamentals from the exchanges? How deep and how timely is its India coverage, and does it hold filing dates?
7. **Brokers:** do Kite Connect, Breeze, Fyers and SmartAPI terms allow local storage of historical candles and their use in backtests?
8. **GODL-India:** does the MCA company-master dataset carry GODL? (Read the dataset page.)
9. **RBI:** do the current DBIE terms keep the old reproduction clause?
10. **Project exposure:** does publishing an importer for a format (e.g. AMFI's NAV layout) carry risk when the code contains no fetcher? Legal view needed; the M16 reading suggests low risk.

---

## D. Cost Comparison (recurring, per self-hosted instance)

Prices exclude GST. GST on these services is assumed at 18% (not verified per product). USD prices are converted at an **assumed ₹85/USD** for illustration only.

| Model | What the user gets | Annual cash cost | Legal position | Coverage |
|---|---|---|---|---|
| **M0 — Own data only** | CAS + broker exports + manual entry; prices the user already holds | ₹0 | Clean | W5 direct equity only; no research data |
| **M1 — Free, manual official downloads** | User downloads NSE/BSE files, AMFI NAV, AMC portfolios by hand and imports them | ₹0 | **Exposed**: NSE simulation clause, AMFI storage clause, NSE Indices storage clause. AMC downloads are clean where terms match HDFC's. | Broad, but no lawful TRI and no lawful bulk NAV store |
| **M2 — Broker key** | M0 + prices through the user's broker API | ₹0 (Breeze, Fyers, SmartAPI) to ₹6,000 (Kite Connect, ₹500 × 12) or ≈₹5,988 (Dhan, ₹499 × 12) | Better for prices; broker terms unread | Prices only |
| **M3 — Hybrid personal (recommended start)** | M2 + EODHD Fundamentals + AMC spreadsheets by hand + RBI rate + local derivations | ₹0–6,000 + $599.90 (≈₹51,000) = **≈₹51,000–57,000** | Prices C; fundamentals C; holdings C; NAV and TRI still blocked | W1, W2, W4, W5 usable. W3 partial (no NAV store, no TRI) |
| **M4 — Hybrid + permissions** | M3 + written AMFI permission + a personal TRI licence | M3 + TRI licence (unknown) | Clean if granted | Full W1–W5 |
| **M5 — Institutional licences** | NSE Data EOD CM (₹1,00,000) + EOD Corporate Data (₹5,00,000) + Master Data (₹2,15,000) + NSE Indices (quote) + an MF vendor (quote) | **≥ ₹8,15,000** + quotes | Clean | Full. Not viable for an individual. |

---

## E. Recommended Suppliers

| Dataset | Primary | Fallback | Trade-off |
|---|---|---|---|
| **R1 prices, R19 ETF bars** | The user's broker API with the user's own key: Kite Connect (adapter exists, ₹500/mo) or a free broker (Breeze, Fyers, SmartAPI) | Manual bhavcopy download into `import-eod`, after NSE answers question 1 | NSE's policy says trading members get live feed data "as a part of their ongoing membership" (V). That brokers may pass stored history to clients for backtests is an inference (C). It is still the cleanest retail route. Each broker needs a new adapter except Kite. Depth varies. |
| **R2 corporate actions, dividends** | Vendor feed (EODHD's India split and dividend coverage not checked, U) | Manual NSE corporate-actions download (question 1) | No clean free source |
| **R3 security master** | Broker instrument dumps + ISIN from NSE's equity list (manual) | Vendor | Kite's dump has no ISIN (noted in `kite.py`) |
| **R4 company master** | data.gov.in MCA company master (GODL, C) | Vendor | Gives CIN and names only; the ISIN ↔ CIN link still needs a source |
| **R5 classification** | Owner-maintained or user-maintained mapping CSV (`classification-v1`) | NSE Indices licence; vendor sector fields | The 4-level NSE structure is proprietary. A vendor's sector scheme may differ. |
| **R6 financials, R7 shares** | **EODHD Fundamentals**, user's own key, after a one-month coverage test | Quote from CMOTS / Accord / CMIE; or NSE permission for personal XBRL import | EODHD is the only priced, personal-licence fundamentals feed found. Its India quality is unverified and it shows no filing times, so every row is `estimated` (+45/+60 days). Out-of-Sample Evaluation on fundamentals would then be refused under the existing ADR-014 rule. |
| **R9–R14 fund data** | **Written AMFI permission** (owner requests it) | Per-AMC personal downloads for the funds the user holds; a quoted MF vendor | No priced personal MF data licence was found. Without AMFI permission, W3 research across all funds has no lawful bulk source. |
| **R15 TRI** | NSE Indices licence (quote) | Price index with the "excludes dividends" warning (blueprint default) | No free lawful TRI. Tracking error, beta and benchmark comparisons stay `NA` or carry the warning. |
| **R16 risk-free rate** | RBI DBIE | Leave Sharpe `NA` | Low risk once the current terms are read |
| **R17 size buckets** | Derive from R1 × R7 using SEBI's rank rule (top 100 / 101–250 / 251+), labelled "derived" | AMFI list with permission | Derivation uses Wickstreet's own mcap, not AMFI's 6-month average. It is an approximation and must say so. |
| **R18 holdings** | AMC spreadsheets the user downloads for personal use (HDFC terms permit this) | Vendor | ≈45 layouts. Per-AMC terms to check. Publication time is the download time (`recorded`) or portfolio date + 10 days (`estimated`). |
| **R21 TE/TD** | Derive from R10 + R15 | AMC/AMFI disclosed figures, entered by hand | Derivation needs TRI |
| **R23 user transactions** | **casparser** (MIT) for CAMS/KFintech/NSDL/CDSL CAS; broker CSV exports; manual entry | Broker API holdings with the user's key | Clean. MFCentral CAS needs its own parser. |

---

## F. Coverage Gap Analysis

| Gap | Effect | Why no source | Status |
|---|---|---|---|
| **F1 Benchmark TRI** | W3 benchmark comparison, beta, tracking error, `roll_3y_beat_bm_pct` | NSE Indices bars storage and automated collection; licence price unknown; BSE terms not found | **No practical free source** |
| **F2 Bulk NAV history and scheme master** | W3 fund screener, category medians, SIP simulation for any fund | AMFI bars storing "a significant portion" | **Blocked** until AMFI permission or a vendor quote |
| **F3 Fundamentals with recorded publication times and restatement history, at a personal price** | W1 "recorded" provenance; W2 historical screens on recorded data | EODHD shows no filing times; exchange XBRL (which has them) is under NSE/BSE terms | **No supportable source**; estimated dates only |
| **F4 4-level industry classification** | Peers, sector exposure | Proprietary to NSE Indices | **No free lawful bulk source**; manual mapping only |
| **F5 Managers, tenure, exit loads, riskometer, IDCW history** | W3 overview and costs tabs | Scattered across ≈45 AMC sites in SID/KIM PDFs | **No structured free source** |
| **F6 Dividends history** | Stock total return, dividend yield, W5 income | No clean free source | Vendor only |
| **F7 MFCentral CAS parsing** | W5 import for MFCentral users | Not in casparser | Engineering gap, not a data gap |
| **F8 Existing price data** | Everything, including Momentum25 | M16 found NSE's automation and simulation clauses | **Open** since 2026-10-19; broker route reduces it |
| **F9 iNAV** | — | Intraday; NSE iNAV feed ₹2,00,000/yr | Out of scope by design |

---

## G. Research Confidence

| # | Conclusion | Label | Missing evidence |
|---|---|---|---|
| G1 | NSE, NSE Indices, BSE and AMFI terms each bar at least one of automated retrieval, storage or reuse | **V** | — |
| G2 | NSE Data publishes no individual or personal tier; its cheapest EOD product is ₹1,00,000/yr per site | **V** | Whether NSE Data would grant a waiver to an individual |
| G3 | SEBI requires portfolios within 10 days (debt: fortnightly within 5 days), daily TER, daily TE and monthly TD on AMC and AMFI sites, in downloadable spreadsheets | **V** on the 2024-06-27 master circular | Whether a later master circular changed these |
| G4 | AMC portfolio downloads for personal use are permitted | **C** | Verified for HDFC only |
| G5 | EODHD permits personal storage and analysis of its data | **V** (terms) / **C** (India coverage) | One-month paid test, or a sales answer on India depth and filing dates |
| G6 | Broker APIs are the cleanest retail price route | **C** | Each broker's data-use terms |
| G7 | casparser is MIT with no GPL dependency | **V** | — |
| G8 | No free lawful TRI exists | **C** | A licence quote; BSE Index Services' current terms |
| G9 | Account Aggregator is closed to a self-hosted individual tool | **C** | The RBI master direction text |
| G10 | data.gov.in MCA company master is GODL-licensed | **C** | The dataset page's licence field |
| G11 | RBI T-bill data may be reused with acknowledgement | **C** | Current DBIE terms |
| G12 | CMIE, CMOTS, Accord, Capitaline, Morningstar and Value Research costs | **U** | Quotes |
| G13 | MCA document view costs ₹100 per company | **U** | MCA's fee schedule |

---

## H. Owner Decisions (needed before technical planning)

| # | Decision | Options | Default I would take |
|---|---|---|---|
| H-1 | **Acquisition model** for 2.0 | M0 … M5 (§D) | **M3 hybrid personal**, moving to M4 as permissions arrive |
| H-2 | **Send permission requests** (outward-facing; owner sends) | AMFI (NAV, scheme master, market-cap list); NSE Data (personal EOD + corporate data, and whether the non-commercial fee clause covers individuals); NSE Indices (personal TRI); BSE Index Services | Send all four. Draft text exists in blueprint 04 §6. |
| H-3 | **Fundamentals supplier** | EODHD (one-month test, $59.99, owner pays) · vendor quotes · NSE permission | Run the EODHD test on 20 named companies (general, bank, NBFC), checking depth, restatements and dates. Ask CMOTS/Accord/CMIE for quotes in parallel. |
| H-4 | **Estimated-only fundamentals** | Accept `estimated` availability for vendor rows (I-3 allows it) · require recorded times | Accept. Studio Out-of-Sample Evaluation on fundamentals stays refused, as today's rule says. |
| H-5 | **Default price source for public release** | Broker API (user's key) · manual bhavcopy · wait for NSE | Broker API, with manual bhavcopy kept as the user's choice. This also addresses the open M16 release block. |
| H-6 | **TRI absence** | Ship with the "excludes dividends" warning · hide benchmark features · wait for a licence | Ship with the warning (blueprint default) |
| H-7 | **Size buckets** | Derive locally, labelled · AMFI list with permission | Derive locally until AMFI answers |
| H-8 | **Classification** | Owner-maintained mapping · vendor sectors · NSE Indices licence | Owner-maintained mapping for the universe the owner uses |
| H-9 | **Budget ceiling per user** | ₹0 · ≈₹6,000/yr · ≈₹60,000/yr | Design for ₹0 core + optional ≈₹60,000/yr; never require it |
| H-10 | **Legal opinion** | None · narrow (NSE simulation, AMFI storage, AMC downloads, importer exposure) | Narrow opinion, if the owner wants a public release |

---

## Final Answers

**1. Can Wickstreet 2.0 operate meaningfully on free data?**
Partly. The portfolio core (W5 direct equity, CAS import) runs on the user's own data with no licence question. Everything else needs either a paid personal licence or a written permission. No free source both allows storage and covers fundamentals, NAV history or TRI. Free manual downloads work technically, but NSE, AMFI and NSE Indices terms restrict them (V).

**2. Which features are supported fully, partially or not at all?**

| Feature | Free (M0–M2) | Hybrid (M3, ≈₹51–57k/yr) | With permissions (M4) |
|---|---|---|---|
| W1 Company intelligence | ❌ | ⚠️ estimated dates only; quality to test | ✅ |
| W2 Unified screener | ⚠️ price and Momentum25 fields only | ⚠️ + fundamentals (estimated) | ✅ |
| W3 Funds and ETFs | ⚠️ ETF price only | ⚠️ the user's own funds via AMC downloads; no TRI | ✅ (TRI if licensed) |
| W4 Holdings and overlap | ⚠️ AMC downloads by hand | ⚠️ same | ✅ |
| W5 Portfolio | ✅ direct equity; ⚠️ fund valuation needs NAV | ✅ except look-through gaps | ✅ |

**3. Most promising sources per dataset** — §E. In short: broker API for prices; EODHD for fundamentals (to test); AMFI permission for fund data; AMC spreadsheets for holdings; casparser for CAS; RBI for the risk-free rate; NSE Indices licence for TRI.

**4. What each self-hosted user must configure or provide**
- A broker API key (free, or ₹500/mo for Kite Connect), or price files they are entitled to use.
- Optionally an EODHD Fundamentals key ($59.99/mo or $599.90/yr).
- Their CAS PDFs and broker exports.
- AMC portfolio spreadsheets they download for the funds they care about.
- Any permission they obtain themselves. A permission granted to the owner covers the owner's instance only (C).

**5. Unavoidable costs and limits**
- No lawful free TRI. Benchmark comparisons stay approximate until someone pays for a licence.
- Bulk fund data needs AMFI's written permission. AMFI publishes no licensing route.
- Fundamentals at a personal price arrive without filing times, so point-in-time history is `estimated`.
- The exchanges' own licensed products start at ₹1,00,000/yr per site. They are not individual products.
- The reviewed personal-use terms do not establish Wickstreet's commercial redistribution or shared-service rights. Whether a supplier will grant suitable commercial rights, and at what price, remains unverified; this is not evidence that such contracts are unavailable.

**6. Most viable long-term strategy**
Keep ADR-021: source-neutral import contracts, no default fetchers. Build on three layers:
1. **Own data** (CAS, broker exports): clean today.
2. **Bring-your-own key** (broker for prices, a personal-licence vendor for fundamentals): each user holds their own licence, so the project redistributes nothing.
3. **Permissions** (AMFI, NSE Indices, NSE Data): pursued by the owner. If granted for personal self-hosted use, they become a documented path every user can follow under their own name.

Derive everything derivable locally (mcap, ratios, TE/TD, size buckets, overlap) so each new source unlocks the most features. Avoid any design that needs a single supplier.

---

## Sources (accessed 2026-10-22 unless noted)

Primary:
- NSE terms of use (read 2026-10-19): <https://www.nseindia.com/static/nse-terms-of-use>
- NSE Data Sharing & Usage Policy (updated 2025-12-11): <https://www.nseindia.com/static/market-data/nse-data-policy>
- NSE Products Tariff, domestic, effective 2026-04-01: <https://nsearchives.nseindia.com//web/mediaattachment/2026-04/Download_Pricing_file_-_Domestic_clients_20260424122229.pdf>
- NSE Paid Corporate Data: <https://www.nseindia.com/static/market-data/corporate-data-subscription>
- BSE disclaimer: <https://www.bseindia.com/disclaimer>
- NSE Indices terms of use: <https://www.niftyindices.com/terms-of-use>; disclaimer: <https://www.niftyindices.com/disclaimer>; data subscription: <https://www.niftyindices.com/offerings/data-subscription>
- AMFI terms of use: <https://www.amfiindia.com/terms-of-use>
- SEBI Master Circular for Mutual Funds, 2024-06-27 (AMC-hosted copy): <https://www.taurusmutualfund.com/sites/default/files/downloads/SEBI_Master_Circular_for_MF_27_6_2024.pdf> — §3.6.3 (TE/TD), §3.6.5 (iNAV), §5.1.1 (portfolio), TER daily disclosure
- HDFC AMC disclaimer: <https://www.hdfcfund.com/disclaimer>
- Zerodha Kite API charges: <https://support.zerodha.com/category/trading-and-markets/kite-api/articles/what-are-the-charges-for-kite-apis>
- ICICI Breeze: <https://api.icicidirect.com/apiuser/home>
- Fyers API: <https://fyers.in/fyers-api/>
- Dhan Data API FAQ: <https://dhan.co/support/platforms/dhanhq-api/is-the-dhanhq-data-api-subscription-free-if-i-execute-a-minimum-number-of-trades-every-month/>
- EODHD pricing: <https://eodhd.com/pricing>; terms: <https://eodhd.com/financial-apis/terms-conditions>
- Trendlyne MCP plans: <https://trendlyne.com/subscription/mcp/plans/>
- Screener.in terms: <https://www.screener.in/guides/terms>
- casparser: <https://github.com/codereverser/casparser>
- mfapi.in: <https://www.mfapi.in/>

Secondary (used only where labelled C or U):
- Asia Index renamed BSE Index Services: <https://www.exchange4media.com/announcements-news/asia-index-renamed-as-bse-index-services-145990.html>
- Account Aggregator FIU rule: <https://sahamati.org.in/financial-information-user-fiu>
- RBI old DBIE disclaimer: <https://dbieold.rbi.org.in/DBIE/doc/disclaimer.html>
- MCA public documents fee: <https://taxroutine.com/how-to-download-public-documents-in-mca21-portal/>
- MCA company master on data.gov.in: <https://org-id.guide/list/IN-MCA>
- Upstox pricing: <https://apis.io/plans/upstox/upstox-plans-pricing/>
- yfinance disclaimer: <https://pypi.org/project/yfinance/>
- AMC portfolio parsing (format reference): <https://github.com/captn3m0/historical-mf-data>
