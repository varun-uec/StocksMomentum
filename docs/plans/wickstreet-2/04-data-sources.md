# 04 — Authorised Data-Source Feasibility Report

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Desk research on 2026-10-22. **This is not legal advice.** Every licence finding must be confirmed by the owner, and by counsel where the owner chooses, before any real data is imported. Governing decision: ADR-021.

## 1. Verdict

**Data, not code, is the critical path.** Every free public source we could read restricts automated collection, bulk storage or reuse:

- **NSE** forbids "systematic or automated data collection" and use for "simulation" (M16 data-use check, 2026-10-19).
- **AMFI** grants only a "personal, non-transferable … limited and revocable right" for "personal and non-commercial use". It says "You shall not store electronically any significant portion of any part of the Site", bars derivative works, and requires a written agreement for any other use ([AMFI terms of use](https://www.amfiindia.com/terms-of-use), read 2026-10-22). A local NAV database built from AMFI's files is, on a plain reading, "storing a significant portion". This holds even when the user downloads the file by hand.
- **BSE** and **NSE Indices** terms could not be read (HTTP 403 and timeout). Treat them as restrictive until read.

So Wickstreet 2.0 is built **source-neutral**: every dataset enters through a documented import contract, and the owner chooses a lawful supplier per dataset. Code, tests and screens can proceed on synthetic fixtures (as every E2E test does today). Importing real data waits for the owner's licence decisions in §5.

The one dataset without a licence question is the **user's own portfolio** (CAS statements, broker exports, manual entry). Phase 5's portfolio core can use real data on day one.

## 2. Source inventory

**Automation** = may a program fetch it? **PIT** = does it carry publication dates for point-in-time use?

| # | Source | What it gives | Depth | Frequency | Access | Cost | Licence and terms | Automation | PIT | Maintenance |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | NSE corporate filings (results PDF + XBRL) | Quarterly and annual results, standalone and consolidated | Years (XBRL era) | Event | Web pages and files | Free to view | Website terms: no automated collection; no simulation use; no redistribution | **No** | Yes: exchange receipt time | High (taxonomy changes) |
| S2 | BSE corporate filings (PDF + XBRL) | Same as S1 | Years | Event | Web | Free to view | Terms unread (403). Assume like NSE | Unknown | Yes | High |
| S3 | NSE Data & Analytics (licensed) | Market data products; fundamentals offering UNVERIFIED | Product-specific | Daily | Licensed feed | Paid | Contract. Portal terms reported to restrict automation even for subscribers ([snippet](https://dotexdata.nseindia.com/TermsAndConditions/TermsofUse.pdf)) | By contract | By product | Low |
| S4 | MCA21 (AOC-4 XBRL) | Annual statutory financials | Since XBRL mandate | Annual, after AGM | Portal, per document | Fee per document (UNVERIFIED) | UNVERIFIED | Unknown | Filing date | High; lag of months |
| S5 | AMFI NAV files (`NAVAll.txt`, NAV history) | Scheme code, ISINs, name, NAV, date | Since 2006 (history report) | Daily | Flat file, web report | Free | Personal, non-commercial; no storing a significant portion; no derivative works; written agreement for other use | **No** without permission | NAV date; no revision log | Low |
| S6 | AMFI average market cap list | Company ranks; Large/Mid/Small | Since Jul–Dec 2017 | Half-yearly (Jan, Jul) | PDF | Free | AMFI terms as S5 | **No** without permission | Yes: dated list | Low (PDF parse) |
| S7 | AMC portfolio disclosures | Holdings with ISIN, quantity, value, % of NAV, industry, rating | Years, per AMC | Monthly within 10 days; half-yearly; debt fortnightly within 5 days (per AMC documents, UNVERIFIED against the current master circular) | Spreadsheet on each AMC site and on AMFI | Free | SEBI mandates a "user-friendly and downloadable spreadsheet format". Each AMC's site terms apply; unread | Unknown, per AMC | Portfolio date; publication date must be recorded at download | **High**: 40+ AMCs, different layouts |
| S8 | AMC/AMFI TER, riskometer, scheme documents | TER per plan, riskometer level, SID/KIM text | Varies | TER on change | AMC sites, AMFI | Free | As S5/S7 | Unknown | Effective dates | Medium |
| S9 | SEBI | Scheme categories (Oct 2017), disclosure rules, tracking-error rule | Static rules | Rare | Circulars | Free | Public regulation | n/a (encode by hand with citation) | n/a | Low |
| S10 | NSE Indices (Nifty) | Index levels, **TRI**, constituents, industry classification | Long | Daily | Web reports; licensed data | Free to view / paid licence | Terms unread (timeout). Index data is normally licensed | Unknown | Yes | Low |
| S11 | BSE / Asia Index | Sensex family levels and TRI | Long | Daily | Web; licence | As S10 | Unread | Unknown | Yes | Low |
| S12 | Exchange industry classification | 4 levels: 12 macro-economic sectors, 22 sectors, 59 industries, 197 basic industries; common NSE–BSE structure since 2022-03-31 ([NSE Indices](https://niftyindices.com/resources/industry-classification)) | Since 2022 | Annual review | Web lists | Free to view | As S10 | Unknown | Effective dates | Low |
| S13 | Commercial vendors (CMOTS, Accord/AceEquity, Capitaline, CMIE Prowess, Morningstar India, Value Research data) | Fundamentals, MF data, holdings, classifications | 10–30 years | Daily | API / bulk | Paid, quote-based | Contract; redistribution usually barred | By contract | Varies; ask for `published_at` and restatement history | Low |
| S14 | Broker APIs (Kite Connect etc.) | Prices; no fundamentals or MF data found for Kite | — | — | API | Kite Connect paid tier ([Zerodha](https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis)) | User's own account | Yes, for the user | — | Low; `kite.py` exists |
| S15 | Unofficial APIs (e.g. mfapi.in) | NAV history | 5+ years | Daily | JSON API | Free | No stated upstream or terms text | — | No | Single-operator risk. **Not used.** |
| S16 | CAS (CAMS/KFintech, NSDL/CDSL) | The user's own folios, transactions, holdings | Full history of the user | On request | Password PDF emailed to the user | Free | The user's own data | n/a | Transaction dates | Medium (PDF layouts). The open-source `casparser` parses all four; its optional PyMuPDF backend is GPL/AGPL, so avoid that backend under Apache-2.0 (ADR-015) |
| S17 | Broker holdings/tradebook exports | The user's own trades | User's history | On request | CSV/XLSX | Free | The user's own data | n/a | Trade dates | Low per broker |
| S18 | RBI 91-day T-bill yields | Risk-free rate for Sharpe | Decades | Weekly auction | RBI DBIE | Free | Terms unread | Unknown | Auction dates | Low |

## 3. Regulatory facts the design depends on

| Fact | Use in Wickstreet | Confidence |
|---|---|---|
| LODR Reg. 33: quarterly results within 45 days of quarter end; annual results within 60 days of year end; filed in PDF and XBRL | Fallback `published_at` for backfilled filings without a receipt time (ADR-016) | Secondary sources agree ([lexplosion](https://lexplosion.in/sebi-clarifies-timelines-applicability-and-disclosure-requirements-for-quarterly-and-annual-financial-results-under-regulation-33-of-lodr-regulations/), [taxguru](https://taxguru.in/sebi/summary-provisions-financial-results-listed-entities.html)). Confirm on the LODR text. |
| AMC portfolio disclosure within 10 days of month or half-year end, with ISIN, in a downloadable spreadsheet, on the AMC and AMFI sites | Fallback `published_at` for disclosures = portfolio date + 10 days (ADR-017) | SEBI circular CIR/IMD/DF/21/2012 text quoted in search results; the 2023+ master circular not read |
| Debt schemes: fortnightly disclosure within 5 days | Same rule, 5 days | AMC documents only. UNVERIFIED |
| SEBI 2017 categorisation: Large Cap = top 100, Mid = 101–250, Small = 251+ by full market cap; AMFI publishes the list twice a year | Size bucket (§1.3 of [03](03-product-specs.md)) | Confirmed by AMFI's own PDFs |
| SEBI "Development of Passive Funds" (May 2022): tracking error = annualised SD of the difference in daily returns between index and NAV over a 1-year rolling window; equity cap 2%; disclosed daily; tracking difference disclosed monthly | `te_1y`, `td_1y` definitions (§2.5 of [03](03-product-specs.md)) | Secondary sources ([Moneylife](https://moneylife.in/article/sebi-tracking-error-of-equity-etfs-and-index-funds-cannot-exceed-2-percentage/67279.html)) |
| Stamp duty 0.005% on MF purchases from 2020-07-01 | SIP simulation | Not verified in this pass. Confirm before release. |

## 4. Recommended supply strategy

| Dataset | Preferred lawful route | Fallback | Phase |
|---|---|---|---|
| Company financials | Licensed vendor with publication dates and restatement history (S13), via the normalized CSV contract | Written NSE/BSE permission for personal-use XBRL import (S1/S2) | 1 |
| Shares outstanding | Same vendor | Shareholding-pattern XBRL under the same permission | 1 |
| Industry classification | Vendor mapping to the exchange 4-level structure (S12) | NSE Indices licence | 1 |
| NAV history, scheme master | Written AMFI permission for personal self-hosted storage (S5) | Licensed MF data vendor (S13) | 3 |
| TER, exit load, managers | Vendor | AMFI/AMC permission | 3 |
| Market-cap list | AMFI permission (S6) | Vendor | 3 |
| Index TRI | NSE Indices / Asia Index licence (S10/S11) | Vendor that sublicenses TRI | 3 |
| Risk-free rate | RBI series, terms to read (S18) | Leave Sharpe `NA` | 3 |
| Fund holdings | Vendor normalized holdings (S13) | AMC spreadsheets the user downloads, if AMC terms permit (S7) | 4 |
| User portfolio | CAS and broker exports (S16/S17), manual entry | — | 5 |
| Shareholding, filings, announcements | Vendor | Exchange permission | 6 |

### By deployment model

| Model | What is feasible |
|---|---|
| **Self-hosted, personal use (today's model)** | Import contracts only. The user supplies files they are entitled to use. The default build contains **no fetcher** for any source in §2. The owner's own instance needs the permissions in §5 for S1/S2/S5/S6/S10. |
| **Open-source distribution** | Ship importers, schemas and synthetic fixtures. Ship a fetcher only for a source whose written terms permit automated personal use, default off (ADR-012, M16 rule). Today that list is empty. Let users plug in their own vendor licence. |
| **Hosted service** | Needs commercial redistribution licences for every dataset, plus authentication (ADR-010). Out of scope. |

## 5. Owner decisions (blocking real-data import)

| # | Decision | Default taken in the blueprint |
|---|---|---|
| D-1 | Which supplier for company financials (vendor quote vs exchange permission) | Build the import contract; no supplier chosen |
| D-2 | Write to AMFI for permission to store NAV, scheme and market-cap data for personal self-hosted use | Draft request text in §6; owner sends it |
| D-3 | Index TRI licence (NSE Indices / Asia Index) or vendor | Benchmarks show "price index (excludes dividends)" with a warning until licensed |
| D-4 | Holdings source: vendor vs AMC spreadsheets | Build the normalized holdings contract plus one AMC-layout parser as a template |
| D-5 | Legal opinion scope (optional) | None assumed |

## 6. Draft permission request (owner to send; not sent)

> Subject: Request for permission — personal, non-commercial, self-hosted storage of AMFI NAV and scheme data
>
> I am building Wickstreet, a self-hosted investment-research tool that runs only on my own computer. I would like to store daily NAV data, the scheme master and the half-yearly market-capitalisation list for my personal, non-commercial analysis. The data would not be redistributed, displayed publicly or used commercially. Your terms of use restrict electronic storage of a significant portion of the site, so I request written permission for this use, or a pointer to a licensed channel.

An equivalent request suits NSE (results XBRL, for personal analysis and historical evaluation, which the "simulation" clause may cover) and NSE Indices (TRI).

## 7. Import contracts (source-neutral)

Each dataset has one normalized format. A vendor or permitted source is converted to it by a small adapter. The contract, not the source, is what the code and tests depend on.

| Contract | Format | Required columns |
|---|---|---|
| `financials-v1` | CSV, one row per fact | `company_key` (ISIN or CIN), `period_start`, `period_end`, `period_type`, `basis`, `audit_status`, `published_at` (ISO 8601 with offset), `line_item` (canonical code), `value`, `scale`, `source`, `source_ref`, `supersedes_ref` |
| `shares-v1` | CSV | `isin`, `as_of_date`, `shares_outstanding`, `published_at`, `source`, `source_ref` |
| `classification-v1` | CSV | `subject_key`, `scheme_code`, `level`, `value`, `valid_from`, `published_at` |
| `schemes-v1` | CSV | `plan_code`, `scheme_key`, `amc`, `scheme_name`, `plan`, `option`, `isin_growth_or_payout`, `isin_reinvest`, `category`, `asset_class`, `benchmark_code`, `launch_date`, `is_index_fund`, `is_etf`, `exchange_symbol` |
| `nav-v1` | CSV, or the AMFI semicolon text layout when the owner has permission | `plan_code`, `nav_date`, `nav` |
| `costs-v1` | CSV | `plan_code`, `effective_date`, `ter_pct`, `exit_load_rule`, `published_at` |
| `holdings-v1` | CSV | `scheme_key`, `portfolio_date`, `published_at`, `isin`, `name`, `asset_type`, `industry`, `quantity`, `market_value`, `pct_of_nav`, `rating` |
| `benchmark-v1` | CSV (extends `import-benchmark`) | `index_code`, `kind` (`PRI`/`TRI`), `date`, `close` |
| `transactions-v1` | CSV | `date`, `instrument` (ISIN, symbol or plan code), `kind`, `quantity`, `price`, `amount`, `charges` |

Every import records `file_sha256` and the importing user's chosen `source` label, so provenance survives.

## Sources (accessed 2026-10-22)

- AMFI terms of use: <https://www.amfiindia.com/terms-of-use>
- AMFI NAV history: <https://www.amfiindia.com/net-asset-value/nav-history>
- AMFI market-cap list example: <https://www.amfiindia.com/Themes/Theme1/downloads/AverageMarketCapitalization31Dec2025.pdf>
- SEBI 2001 NAV on AMFI site: <https://www.sebi.gov.in/legal/circulars/feb-2001/disclosure-of-navs-on-amfi-website_18073.html>
- SEBI portfolio disclosure (2012 circular as quoted): <https://www.sebi.gov.in/sebi_data/attachdocs/jun-2018/1528207366367.pdf>
- NSE terms of use: <https://www.nseindia.com/static/nse-terms-of-use> (see [M16 data-use check](../../audits/2026-10-19-m16-nse-data-use.md))
- NSE Data portal terms: <https://dotexdata.nseindia.com/TermsAndConditions/TermsofUse.pdf>
- Industry classification: <https://niftyindices.com/resources/industry-classification>
- Passive funds tracking error: <https://moneylife.in/article/sebi-tracking-error-of-equity-etfs-and-index-funds-cannot-exceed-2-percentage/67279.html>
- LODR Reg. 33: <https://lexplosion.in/sebi-clarifies-timelines-applicability-and-disclosure-requirements-for-quarterly-and-annual-financial-results-under-regulation-33-of-lodr-regulations/>
- Kite Connect charges: <https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis>
- casparser: <https://github.com/codereverser/casparser>
- mfapi.in: <https://www.mfapi.in/>
