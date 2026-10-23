# Wickstreet 2.0: E1–E7 Source Research

> Status: Proposed, research only. 2026-10-23. Not legal advice.
> No code, fetchers, migrations or commits. No fetcher is proposed for NSE or BSE.
> Builds on [12](12-d0r-data-source-research.md), [17](17-mf-free-data-feasibility.md), [20 §4](20-wickstreet-2.0-complete-mf-scope.md) and [21 §4](21-analytics-expansion-v4.md). It does not repeat their term quotes. It cites them.

## 1. Method and limits

- Labels: **V** = read on the primary page today. **P** = read earlier in doc 12 or 17. **U** = unverified.
- Web access this session was thin. Four AMFI pages I guessed (TER, portfolio disclosure, scheme performance) returned HTTP 404. The AMFI scheme-wise disclosure page loaded but showed only filters. niftyindices.com timed out. I did not open any NSE or BSE data page. Where I could not read the exact page, I say so.
- The owner works in personal mode: one user, one machine. Rights grants in the table are therefore personal-use, local-storage grants. Terms already read in 12 and 17 say "personal and non-commercial use only". They bar storing "any significant portion" (AMFI). Each dataset needs a rights-register entry before ingestion. Silence in terms is not permission.
- Terms quotes below are only new ones. For AMFI, NSE Indices, BSE Indices, RBI DBIE, AMC sites and Screener, see [17 §3](17-mf-free-data-feasibility.md) and [12 §C](12-d0r-data-source-research.md).

## 2. E1: TER history, AUM, exit loads, minimums, managers, riskometer, benchmark name

| Item | Finding |
|---|---|
| Rule that forces publication | SEBI MF Master Circular, 2026-03-20: daily TER "in a downloadable spreadsheet and a machine readable format" (§11.2.2, §11.2.4); monthly riskometer (§6.16). P ([17 §3](17-mf-free-data-feasibility.md)) |
| AMFI scheme-wise disclosure | https://www.amfiindia.com/otherdata/scheme-wise-disclosure. Page title: "Scheme wise disclosure of investments in terms of SEBI Circular dated 25-Aug-2022". Filter: fund and quarter. V (page loaded). It does not show TER, manager or exit load. Do not treat it as the E1 source. |
| AMFI other pages | The AMFI TER, AAUM and scheme-details (SSD) pages exist per 17 (sourced from TigZig's data dictionary). I could not open them today. Exact URLs: U. |
| TigZig MF API | https://api.tigzig.com/mf/v1/ . Joins AMFI NAV, scheme master, SSD, TER, riskometer and AUM. Terms: "No rights in the underlying data are claimed here, and none are granted" (P, [17 §3](17-mf-free-data-feasibility.md)). Chain of title is AMFI. |
| AMC factsheets, SID/KIM | PDF, per AMC, about 45 layouts. Source of exit load, minimum amount and manager start dates. Hard to parse at scale. HDFC and PPFAS bar more than personal download (P). |
| History depth | TER daily series: AMFI shows current and recent values. Deep history: U. TER before and after April 2026 is not comparable. The definition changed (17). Manager and riskometer history: no source. History starts at the first stored snapshot (17 G6). |
| Frequency | TER daily. AUM monthly or quarterly (AAUM). Riskometer monthly. Manager and exit load change on event. |
| Machine readable | AMFI: yes for TER and AUM (the circular says so). Managers and exit loads: AMFI SSD only, as filed. AMC PDFs: no. |

Recommendation: **AMFI direct** for TER, AUM, riskometer, benchmark name, current manager and exit load. Reason: primary source, one layout, the circular makes it machine readable. Start the snapshot archive on day one, because history is not published. Use AMC factsheet PDFs only for gaps (minimums, manager start date). Do not build E1 on a mirror. A mirror cannot show chain of title. Manager history stays a known gap (21 C15).

Blocker: AMFI written permission for personal local storage (P1 in 17). Open question: does one-user storage count as "a significant portion of the Site"?

Note added 2026-10-23 (main session): the owner's authorisation [ADR-023 U10](../../architecture/adr/ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23) covers AMFI NAV history and the AMFI scheme master in personal mode, as the owner's decision and risk acceptance, not a permission from AMFI. It does not name TER, AUM or scheme details. The owner can extend it to E1 in the same way, or wait for AMFI's written permission. The rights register keys grants by source and use, not by dataset, so the existing `amfi` rows would let E1 ingestion pass the gate. E1 must not start on them without the owner's extension.

## 3. E2: dated 91-day T-bill yield

| Item | Finding |
|---|---|
| Primary | RBI. DBIE: https://data.rbi.org.in/DBIE/ . I found no direct export path for the auction series. Exact DBIE table name: U. |
| RBI Handbook of Statistics | Table "Auctions of 91-Day Government of India Treasury Bills" with cut-off price and implicit yield at cut-off. Annual PDF/XLSX. Listed on the RBI publications page, dated 2025-08-29. Found by search. Page not opened by me. |
| RBI auction press releases | One per auction. Example: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=48293 (found by search; its date I did not confirm). HTML. Cut-off price and yield per auction. |
| Old bulletins | Weekly Statistical Supplement tables, e.g. https://rbidocs.rbi.org.in/rdocs/Bulletin/PDFs/62234.pdf (found by search; not opened). |
| History depth | Decades in the Handbook and DBIE (secondary claim). U for exact start. |
| Frequency | 91-day bills auction weekly (RBI, per search result). Press release same day. |
| Machine readable | DBIE: yes, SDMX/CSV claimed in 17 (P). Press releases: HTML, parseable but fragile. |
| Terms | "Reproduction is permitted provided an acknowledgement of the primary source is made." https://data.rbi.org.in/DBIE/#/dbie/disclaimer (P, 17). No automation clause. |

Recommendation: **RBI DBIE**, with the Handbook table as a cross-check and press releases as a fallback for the newest week. Reason: official, the only dataset with an explicit reuse grant. Store the auction date and the cut-off yield. Use the auction date as the effective date. Do not interpolate between auctions without labelling it.

Blocker: none on rights. Small task: confirm the DBIE series name.

**Done 2026-10-23** ([as built](../../current/architecture.md#wickstreet-20-risk-free-rate-e2-method-v5)). DBIE lists the report "Auctions of 91-Day Government of India Treasury Bills" (weekly, 1993-01-08 to 2026-10-14), but its report viewer failed in the browser (an invalid certificate on its report host). The Handbook editions 2017–2026 and the weekly press releases supplied 529 auctions from 2016-07-05. RBI's file host answers scripts with a bot challenge, so Wickstreet imports files a person downloads and fetches nothing. A weekly automated fetch from rbi.org.in is an owner decision.

## 4. E3: benchmark TRI daily history, and each scheme's benchmark over time

| Source | Finding |
|---|---|
| NSE Indices (niftyindices.com) | Has the Nifty TRI series. Terms bar systematic or automated collection and storage without a licence (P, 12 §C, 17 §3). niftyindices.com timed out today. I could not re-read it. No fetcher is proposed. |
| BSE Index Services | Same restriction. Terms read in 17 (P): "personal, internal, non-commercial"; no "robots, spiders or other automatic devices". No fetcher is proposed. |
| AMFI scheme vs TRI returns | SEBI orders AMCs to upload daily scheme CAGR with the TRI CAGR for 1, 3, 5, 10 years and since inception, on the AMFI portal (SEBI circular of January 2018, found by search: https://www.sebi.gov.in/sebi_data/attachdocs/jan-2018/1515066187290.pdf; master circular §6.9.1). These are fixed-horizon returns, not a daily TRI series. A download option: U. |
| Index-fund NAV as proxy | NAV of a large Direct index fund tracks the TRI. Gives a labelled proxy series from AMFI NAV, already loaded. Not the index. |
| Benchmark over time | No source. AMFI SSD gives the current benchmark. Change history comes only from stored snapshots or SID addenda (U). |
| Other index providers | Not checked: FTSE Russell, S&P BSE via Asia Index (U). |

Recommendation: no free, rights-clear TRI series exists. Do this in order.
1. Use AMFI scheme-vs-TRI horizon returns for TRI-relative return now. It rides on the E1 AMFI grant.
2. Label an index-fund NAV proxy for beta, alpha and capture. Name it a proxy in the UI.
3. Ask NSE Indices for a personal-licence quote (12 open question 4). Record the grant only if they give one in writing.

Blocker: rights. A written NSE Indices or BSE Index Services licence is the only route to a true daily TRI series. Cost: U.

## 5. E4: monthly portfolio disclosures

| Item | Finding |
|---|---|
| Rule | Portfolios with ISIN within 10 days of month end "in a user-friendly and downloadable spreadsheet format" (master circular §6.1.1, P). Debt schemes fortnightly. |
| Where | Each AMC site, and AMFI hosts copies (circular §6.1.1). The AMFI scheme-wise disclosure page (V) serves quarter-wise investment disclosure per fund. I could not tell if it offers files. |
| Format | XLSX or XLS per AMC, or PDF. About 45 layouts. Columns differ. Debt files carry rating, maturity and YTM only for some AMCs (U). |
| History | AMCs keep a rolling archive, often 12 months or more (U per AMC). Earlier history: only if stored from now. |
| Machine readable | Yes in spreadsheet form. One parser per AMC. |
| Terms | HDFC, PPFAS, Axis, Mirae, Jio BlackRock restrict to personal use. SBI, ICICI Pru, Nippon, Kotak unread (P, 17 §3). New: I did not read any further AMC terms today. |

Recommendation: **AMC monthly XLSX, one adapter per AMC**, starting with the AMCs that hold most of your portfolio (CAS in Slice 6 shows which). Reason: the only source with ISIN, quantity, value, % NAV and rating. Use the AMFI-hosted copy if AMFI grants permission, because it gives one place. Skip AMCs that offer PDF only until the owner asks.

Blocker: per-AMC personal-use grant (P3 in 17). Effort is the largest in the set.

## 6. E5: IDCW payout records

| Item | Finding |
|---|---|
| New rule | A SEBI letter of 2026-05-13 makes AMCs show the last distribution date and either five years of IDCW history or the last five distributions, effective 2026-08-13. Source: HDFC addendum, https://files.hdfcfund.com/s3fs-public/2026-08/1359%20-%20Addendum%20-%20Disclosure%20of%20IDCW%20Track%20Record%20of%20the%20Schemes-w.e.f%20Aug%2013%2C%202026_0.pdf (found by search, V as an AMC notice). I did not find the SEBI letter itself. U. |
| Where | Each AMC's "NAV and IDCW" page and factsheet. HDFC points to a dedicated page. Format per AMC: HTML table or PDF. U. |
| Record-date notices | Per-payout addendum PDFs and exchange filings carry record date and amount per unit (HSBC example found by search). Archive depth varies. |
| AMFI | No IDCW history found. U. |
| Machine readable | No. PDF and HTML per AMC. |

Recommendation: **each AMC's IDCW history page and record-date notices.** Reason: only source, and the new rule makes it uniform in content. Enter records only when a source row exists (owner decision M13). Never infer from NAV drops. Coverage will be partial, five years at most for most AMCs. Say so in the UI.

Blocker: per-AMC personal-use grant. Same AMC list as E4, so one grant covers both.

## 7. E6: ETF exchange prices, volumes, iNAV

| Item | Finding |
|---|---|
| NSE and BSE | The primary source of price, volume and iNAV. Terms restrict automated collection (P, 12, 17). Release blocker already noted in 21. No fetcher is proposed. I did not open their data pages. |
| AMC pages | AMCs publish ETF iNAV intraday on their sites (HDFC ETF pages found by search, https://www.hdfcfund.com/explore/mutual-funds/etf ). Prices and volumes: not there. Terms of use: HDFC personal download only (P). |
| AMFI | Publishes ETF NAV, not exchange price. |
| Broker API | Zerodha Kite Connect historical candles are in doc 12 (P). Paid tier. Owner's own broker key, personal use. Terms for stored history: U. |

Recommendation: **defer E6.** The only lawful route found is the owner's own broker API, paid, and its storage terms are unread. A manual end-of-day download from the exchange by the owner is the owner's act, not Wickstreet's. Do not automate it. Premium and discount analysis (C19) waits.

Blocker: rights. Needs a written exchange licence or a broker-API grant. Lowest priority (21 §5).

## 8. E7: company fundamentals and sector classification for held securities

| Source | Finding |
|---|---|
| Fund portfolio files (E4) | Carry industry per holding. This gives sector exposure with no E7 source. Classification follows AMFI industry labels (U for exact scheme). |
| Quarterly results | Companies file XBRL results on NSE and BSE. Restricted for automation (P, 12). No fetcher proposed. |
| Screener.in | Excel export. Terms: "Personal, non-commercial transitory viewing only"; downloads must be destroyed when the licence ends (P, 12). Not a stored source. |
| yfinance / Yahoo | "intended for personal use only". Reject (P, 12). |
| NSDL ISIN list | CC0 mirror: https://git.captnemo.in/nemo/india-isin-data (found by search; I did not read the licence file). Identifiers only. |
| Paid vendors | Capitaline, CMIE Prowess, Financial Filings: licence and price U. |
| SEBI / MCA | SEBI XBRL and MCA filings: not checked. U. |

Recommendation: **no free source with a clear grant exists.** Use E4 industry labels for sector exposure now. For P/E, P/B and ROE, ask a paid vendor (Capitaline first) for a personal-licence quote. Scope: only securities the owner's funds hold (M15). Until then, C20 and C21 stay blocked. Do not use Screener or Yahoo as a stored source.

Blocker: rights and cost. Owner decision needed on paying for a licence.

## 9. Summary table

| Dataset | Recommended source | Rights status: grant the owner records | Effort | First capabilities completed |
|---|---|---|---|---|
| E1 | AMFI direct (TER, AUM, riskometer, benchmark name, manager, exit load); AMC PDFs for gaps | Written AMFI permission for personal local storage. Not yet held. | M | C14 fund costs, C15 profiles, C4 cost drag, C22 exit loads |
| E2 | RBI DBIE, Handbook as cross-check | RBI reuse with acknowledgement. Terms grant it (P). Record it. | S | C13 Sharpe and Sortino, then C12 |
| E3 | AMFI scheme-vs-TRI horizon returns now; labelled index-fund proxy; NSE Indices licence if quoted | AMFI grant (as E1). True TRI series: written NSE or BSE licence. None held. | M (proxy), L (licensed series) | C12 TRI-relative return; beta, alpha, capture only with the proxy or licence |
| E4 | AMC monthly XLSX, one adapter per AMC | Per-AMC personal-use grant, or AMFI-hosted copy under the AMFI grant. None held. | L | C16 holdings, C17 debt, C25 overlap |
| E5 | AMC IDCW history pages and record-date notices | Per-AMC personal-use grant (same as E4). None held. | M | C8 IDCW total return |
| E6 | Defer. Owner's broker API is the only lawful lead | Written exchange licence or broker-API storage grant. None held. | L | C19 ETF premium and discount |
| E7 | E4 industry labels now; paid vendor quote for P/E, P/B, ROE | Written vendor licence. None held. | L | C16 sector style now; C20 and C21 after licence |

Order of work (matches 21 §5): E2, then E1 and E3 proxy under one AMFI request, then E4 with E5 under one AMC request, then E7, then E6.

## 10. Open questions for the owner

1. Will you ask AMFI for written permission for personal local storage? It unblocks E1, E3 horizon returns and possibly E4.
2. Do you want a quote from NSE Indices or BSE Index Services for a personal TRI licence?
3. Do you accept a labelled index-fund NAV proxy until a licence exists?
4. Will you pay for a fundamentals licence for E7? If not, C20 and C21 stay out of 2.0.
5. Which AMCs hold your funds? That sets the E4 and E5 adapter list.
