# Wickstreet 2.0 — Free Mutual Fund Data Feasibility

> Desk research and limited read-only sampling, 2026-10-23. **This is not legal advice.**
> Scope: the hosted, commercial MF research SaaS in [13](13-wickstreet-2.0-mf-first-release-plan.md) (free tier + ₹199/yr Pro). It rechecks the personal-use findings of [12](12-d0r-data-source-research.md) in a commercial frame and adds new sources.
> No outreach, accounts, purchases, bulk downloads, scraping, ingestion, code changes or commits.

> **Operating modes (owner decision, 2026-10-23, [ADR-023 U13](../../architecture/adr/ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23)).** Wickstreet 2.0 is a local, single-user personal MF research and investment intelligence workstation. Personal mode has the complete feature set: real MF data, real CAS imports, and personalised guidance (fund recommendations, best-fund rankings, suggested allocations, rebalancing, optimisation). This commercial feasibility study applies to the future SaaS phase only, before public deployment; it does not restrict personal-mode development.

## Summary

| Question | Answer |
|---|---|
| **Technical:** can free sources supply the data that comprehensive MF research needs? | **Mostly yes.** AMFI publishes, free, almost everything a Tickertape-class MF product needs: daily NAV since April 2006, scheme master with ISINs, AUM, daily TER, riskometer, fund managers, exit loads, benchmarks, scheme-vs-TRI returns and monthly portfolios. Three free mirrors expose it as APIs. The gaps are a **TRI time series**, **merger/successor mapping**, **IDCW payout history**, and **normalised holdings** (≈45 AMC layouts). |
| **Commercial:** can Wickstreet lawfully retrieve, store, calculate from and display that data to subscribers at zero licence cost? | **Not confirmed.** No source of the core data grants commercial rights that trace back to the publisher. AMFI's terms limit use to "personal and non-commercial use only" and need a written agreement for anything else. Five AMCs read so far say the same. Both index providers explicitly bar derived data and third-party services. Free mirrors either disclaim AMFI rights or grant rights they cannot show they hold. |
| **Decision** | **CONDITIONAL GO.** Coverage is plausible, but material permissions remain unresolved. No live-data commercial launch until **P1** (below) is resolved. A NO-GO on free commercial data is not a NO-GO on Wickstreet. |

**Final answer.** Wickstreet 2.0 cannot *today* deliver Tickertape-class MF research on lawful, zero-licence-fee data. The data exists and is technically promising, pending primary-source validation. The **permission** is missing. One permission unlocks most core MF research capabilities: **written AMFI permission (P1)** for commercial automated retrieval, storage, derived metrics, subscriber display and export. A favourable opinion from qualified counsel on copyright and contract (§3) is a different kind of answer. It is a risk assessment, not a grant, and it is not equivalent to written permission. Benchmark TRI series (P2) and per-AMC holdings rights (P3) block the rest. Everything else is engineering and validation.

**Decision framework**

| Decision | Meaning | Next action |
|---|---|---|
| GO | Confirmed, commercially permissible zero-licence-fee data adequately supports the minimum useful MF product | Authorise full implementation planning |
| **CONDITIONAL GO** ← this report | Coverage is plausible, but material permissions or reliability evidence remain unresolved | Resolve the named dependencies; no commercial launch |
| NO-GO | The minimum product cannot be supported under the zero-licence-fee constraint | Reconsider data strategy, scope or pricing |

**Labels used.**
- Rights: **Permitted** = the terms explicitly allow it. **Restricted** = the terms explicitly bar or limit it. **Unverified** = the terms are silent, unreadable, or the grantor's own title is unshown. Silence is never read as permission (fail-closed, [14 §5](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate)).
- Evidence: **V** = read on the primary page on the stated date. **C** = supported, but depends on an unread term or an interpretation. **U** = secondary or no evidence.
- Quality: **Observed** = measured in this study. **Claim** = the source's own statement. **Not sampled**.

---

## 1. Source comparison (ranked by suitability for a commercial SaaS)

Rank weights: commercial-rights clarity first, then coverage, then reliability.

| # | Source | What it gives | Coverage / depth | Access | Commercial rights | Suitability |
|---|---|---|---|---|---|---|
| 1 | **RBI DBIE** | Risk-free rate inputs (T-bill yields) | Decades (C) | Web/SDMX | **Permitted** with acknowledgement (V) | High, but narrow: one input |
| 2 | **SEBI MF Master Circular 2026** (rules, not data) | Category definitions, TER/IR/TE/TD formulas, riskometer scale, disclosure timelines | — | PDF | Public regulation; cite (C) | High for methodology |
| 3 | **AMFI** (primary publisher) | NAV daily + history, scheme master, ISINs, AAUM and daily AUM, TER, riskometer, SSD (managers, exit load, benchmark, objective), scheme vs TRI returns, IR, portfolios | All schemes; NAV since 2006 (Claim: mirrors) | Text files; 90-day history windows; web pages | **Restricted** to personal, non-commercial use; written agreement needed (V) | **Best data, blocked rights.** The only clean upgrade path is P1. |
| 4 | **TigZig MF API / MFPro** | AMFI NAV + scheme master + SSD + TER + riskometer + AUM, parsed and joined; bulk Parquet/CSV/SQLite | 38,000+ schemes, 37M+ NAVs, since 2006, incl. matured (Claim); 8/8 sampled schemes found (Observed) | No-auth API, 300 req/min; bulk downloads | Own use: "Free to use" (V). CC0 for compilation only; "No rights in the underlying data are claimed here, and none are granted"; "refer to AMFI's own terms" (V, homepage). Underlying data: **Unverified → AMFI Restricted** | Best technical mirror; honest about rights. Useful as a **format and QA reference**, not a licence. |
| 5 | **mfnav.in** | AMFI NAV history, scheme master, AAUM, computed returns | 38,335 schemes, since 2006 (Claim) | No-auth API, 120 req/min | Own terms: "free to use, for any purpose — personal, research, or commercial" (V). Republishes AMFI; claims no AMFI permission (V). Chain of title **Unverified** | Permissive on its face, but cannot grant AMFI's rights. Anonymous operator. |
| 6 | **mfapi.in** | AMFI NAV history, scheme meta | Not stated | No-auth API; "rate limiting" unspecified | No licence; Terms/Privacy links are `#` placeholders; "All rights reserved" (V) | **Unverified** on every right. Reject as a source. |
| 7 | **AMC websites** (≈45) | Portfolios (monthly, debt fortnightly), factsheets, SID/KIM, IDCW history, TE/TD | Per AMC | Spreadsheets/PDFs; each layout differs | HDFC, PPFAS, Axis, Mirae, Jio BlackRock: **Restricted** to personal/non-commercial use without written permission (V). SBI, ICICI Pru, Nippon, Kotak: **Unverified** (pages unread) | Needed only for holdings and IDCW. High engineering cost. |
| 8 | **Open-source mirrors** (captn3m0/historical-mf-data, Kaggle sets) | AMFI NAV archives | Full history (Claim) | Git releases | Code/compilation under MIT (V/U). An open licence on a republished dataset cannot grant AMFI's rights | Format reference only |
| 9 | **NSE Indices / BSE Index Services** | TRI series, constituents | Full | Web; licence | **Restricted** (V): see §3 | Not free. Licence fee unknown. |
| 10 | **data.gov.in, India Data Portal** | No scheme-level MF dataset found; IDP mirrors AMFI monthly reports (U) | — | — | data.gov.in and IDP returned HTTP 403; **Unverified**. GODL-India permits commercial reuse with attribution (C, secondary text) but no MF dataset under it was found | No contribution |
| 11 | **SEBI data-sharing policy** | Raw SEBI data | ≥2 years old | Request + NDA | For "educational, research institutions, and regulators"; confidentiality; data must be expunged (V) | Not usable for SaaS |

Not needed: NSDL ISIN master and OpenFIGI (AMFI already supplies ISINs). Account Aggregator: closed to an unregulated FIU and irrelevant to research data ([12 §B5](12-d0r-data-source-research.md)).

---

## 2. Feature-to-data coverage matrix

**S** = supplied by a source. **D** = derived deterministically by Wickstreet from the listed inputs. "Free" = a free source supplies or enables it. "Free + rights" = a free source with **confirmed** commercial rights.

| Capability | Required fields | How obtained | Free | Free + rights |
|---|---|---|---|---|
| **Scheme master, category, AMC, plans, identifiers** | AMFI code, ISIN growth/payout, ISIN reinvest, name, AMC, open/close/interval, SEBI category, plan, option, launch/allotment date | S: AMFI NAV file header + SSD. D: plan/option parsed from name | ✅ Supported. Plan/option needs a parser: mfnav labels an ETF "Direct" (Observed) | ❌ (P1) |
| **Historical NAV and performance** | Date, NAV per plan, corrections | S: AMFI. D: point returns, CAGR, calendar-year returns | ✅ Supported since 2006. Unit splits/face-value changes are not adjusted (Claim, TigZig) | ❌ (P1) |
| **AUM and expense ratios** | Scheme AAUM (quarterly), fund daily AUM, TER and base TER per plan, TER date | S: AMFI (AAUM, daily performance, TER) | ✅ Supported. TER before and after April 2026 is not comparable: the definition changed (Claim, TigZig; circular §11.2.4 V) | ❌ (P1) |
| **Risk metrics and riskometer** | Riskometer level (scheme + benchmark), PRC for debt; volatility, drawdown, Sharpe, Sortino | S: AMFI riskometer (monthly), SSD. D: volatility/drawdown from NAV; Sharpe/Sortino from NAV + RBI rate | ✅ Supported. Riskometer history only from the first snapshot stored | ❌ for riskometer and NAV (P1); RBI input ✅ |
| **Fund manager details** | Names, start dates, history | S: AMFI SSD (current, as filed) | ⚠️ Partial: current only. Tenure history needs stored snapshots or SID addenda | ❌ (P1) |
| **Holdings and portfolio composition** | Portfolio date, ISIN, instrument, quantity, value, % NAV, industry, rating | S: AMC spreadsheets (Format 4C, within 10 days; debt fortnightly), also hosted on AMFI (circular §6.1.1 V) | ⚠️ Partial: data free but ≈45 layouts; not in any free mirror | ❌ (P1 for AMFI-hosted copies, or P3 per AMC) |
| **Benchmark information and comparisons** | Benchmark name (tier 1/2); TRI series; scheme vs benchmark returns | S: benchmark names (SSD); scheme and TRI CAGR for 1/3/5/10y/SI, updated daily (AMFI, circular §6.9.1 V); IR daily (§6.10). D: beta, alpha, TE, capture ratios need a **TRI series** | ⚠️ Partial: fixed-horizon comparisons only. No free TRI series | ❌ (P1 for AMFI figures; P2 for series) |
| **Advanced screening and analytical ratios** | All of the above per scheme; category medians, ranks | D from NAV, AUM, TER, riskometer, category | ✅ Supported, except TRI-based ratios | ❌ (P1) |
| **Historical SIP and rolling returns** | Daily NAV; IDCW for non-growth options | D: SIP XIRR, rolling CAGR distributions from NAV | ✅ Supported for Growth options. IDCW options need payout history (AMC sites) | ❌ (P1) |
| **Scheme changes, mergers, discontinued funds** | Active flag, last NAV date, successor scheme, change dates (name, category, benchmark, fundamental attributes) | S: last NAV date (AMFI). D: inactive flag. **Successor mapping: no free structured source** (Observed: none of 3 mirrors links the merged L&T Large Cap to an HSBC successor) | ⚠️ Partial: discontinued yes, mergers no | ❌ (P1) |

**Supplied vs derived.** Every analytical ratio in a Tickertape-class product (returns, CAGR, rolling, SIP XIRR, volatility, drawdown, Sharpe, Sortino, category ranks and medians) derives deterministically from NAV + risk-free rate. Beta, alpha, tracking error, capture ratios and Wickstreet's own IR derive from NAV + TRI series. So **NAV rights (P1) and a TRI series (P2) are the only two inputs that gate the analytics layer.** Metric formulas remain methodology and need owner approval ([12 §H](12-d0r-data-source-research.md)).

---

## 3. Rights assessment

Columns follow [14 §5](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate). All read 2026-10-23 unless noted.

| Source | Automated retrieval | Storage / cache / backups | Derived metrics | Subscriber display | Export / reports | Key wording (verbatim) | Conf. |
|---|---|---|---|---|---|---|---|
| **AMFI** ([terms](https://www.amfiindia.com/terms-of-use)) | Unverified (no clause) | **Restricted** | **Restricted** | **Restricted** | **Restricted** | "for your personal and non-commercial use only"; "You shall not store electronically any significant portion of any part of the Site"; "or create derivative works based on anything available through the Site, in whole or in part"; "participate in the sale or transfer of"; "No other use of the Site is authorised unless you and we have agreed otherwise in writing." No licensing contact. NAV history page: "a maximum period of 90 days at a time" ([nav-download](https://www.amfiindia.com/net-asset-value/nav-download)) | V |
| **TigZig** ([catalog](https://api.tigzig.com/mf/v1/), [terms](https://www.tigzig.com/terms)) | Permitted for its API ("Free to use") | Compilation: Permitted (CC0, homepage). Underlying: **Unverified** | Same | Same | Same | "No rights in the underlying data are claimed here, and none are granted"; "For MF NAV the publisher is AMFI - refer to AMFI's own terms and conditions" (homepage, V). Its /terms page (Aug 2026) has no licence section: the statements are **inconsistent** across pages | V |
| **mfnav.in** ([terms](https://mfnav.in/terms)) | Permitted (120 req/min) | Permitted by mfnav | Permitted by mfnav | Permitted by mfnav | Redistribution: no clause | "free to use, for any purpose — personal, research, or commercial, with no login or attribution required"; "republishes daily NAV … as published by AMFI". About page: no AMFI permission claimed; operator unnamed. **Chain of title Unverified**: mfnav cannot grant rights it does not hold | V |
| **mfapi.in** | Unverified | Unverified | Unverified | Unverified | Unverified | Terms links are `#`; "© 2025 MFapi.in. All rights reserved." | V |
| **AMCs** | Jio BlackRock: **Restricted** (no automated retrieval). Others: Unverified | **Restricted** (HDFC, PPFAS: personal download only; Axis, Mirae: no "significant portion") | **Restricted** (HDFC, PPFAS: no modify/reuse) | **Restricted** | **Restricted** | HDFC/PPFAS: "may download materials, data etc displayed on the Site for non-commercial and/or personal use only" … not "for public or commercial purposes" without "written permission". Axis/Mirae: "personal, non-commercial use, unless user and AMC have agreed otherwise in writing". SBI, ICICI Pru, Nippon, Kotak: **Unverified** (404 or empty) | V (5), U (4) |
| **BSE Index Services** ([terms](https://www.bseindices.com/terms-of-use), read today; was U in 12) | **Restricted** | **Restricted** | **Restricted** | **Restricted** | **Restricted** | "limited right … for your own personal, internal, non-commercial purposes"; no "robots, spiders or other automatic devices"; prohibited "(ii) creating derivative works from the Content; and (iii) using the Content in the provision of any services to third parties"; may not "create … historical databases" or "any derived data … except with BISPL express written consent" | V |
| **NSE Indices** | **Restricted** | **Restricted** | **Restricted** | **Restricted** | **Restricted** | "personal, non-commercial use only"; "may not conduct any systematic or automated data collection"; index data "require[s] a license" ([12 §C](12-d0r-data-source-research.md), read 2026-10-22; HTTP 403 to plain fetch, not re-read) | V (2026-10-22) |
| **RBI DBIE** ([disclaimer](https://data.rbi.org.in/DBIE/#/dbie/disclaimer)) | Unverified (no clause) | Permitted | Permitted | Permitted | Permitted | "Reproduction is permitted provided an acknowledgement of the primary source is made." | V |
| **SEBI circulars** | n/a | Permitted (C) | Permitted (C) | Permitted (C) | Cite | Public regulation; the formulas are rules, not data | C |
| **data.gov.in / GODL** | — | — | — | — | — | Portal returned HTTP 403. GODL permits commercial use with attribution (secondary copy). No MF dataset found | U |

### Does SEBI's mandate to publish grant reuse rights?

**No, not by itself.** The [Master Circular of 2026-03-20](https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html) (HO/24/13/11(1)2026-IMD-POD-1/I/7602/2026, in force 2026-04-01) orders AMCs and AMFI to **publish**:
- portfolios with ISIN within 10 days, "in a user-friendly and downloadable spreadsheet format" (§6.1.1);
- daily TER "in a downloadable spreadsheet and a machine readable format" (§11.2.2, §11.2.4);
- daily scheme vs TRI returns for 1/3/5/10y/SI, "filtered … and sorted" (§6.9.1);
- daily IR "in a comparable, downloadable (spreadsheet) and machine readable format" (§6.10);
- monthly riskometer with the portfolio disclosure (§6.16, product labelling, item (j));
- NAVs "on the website of AMFI" (§9.3.2);
- annual reports linked at AMFI "so that the investors and analyst(s) can access" them (§6.4.2).

None of these clauses licenses third-party reuse, storage or redistribution, and the circular has no data-reuse clause (searched: "third party", "redistribut", "copyright", "public domain"). One clause matters by analogy. **Execution-Only Platforms** must "Display in a user-friendly manner, the factual information pertaining to Mutual Funds as available on public domain including past performance" and "Provide an interactive tool for the investors to screen or filter various schemes", with "no auto display of recommendation or ranking" (§19.10.4). This shows that SEBI expects public MF facts to be displayed and screened by platforms. But EOPs are AMFI- or SEBI-registered transaction platforms. The clause regulates them. It licenses nothing to Wickstreet. (V for the text; C for the interpretation.)

The 8 May 2026 educational price-data circular (HO/47/17/12(11)2025-MRD-POD3/I/11107/2026) covers "market price data" shared by MIIs and market intermediaries, with a 30-day lag and a legal agreement. Whether it covers AMFI NAVs is not established. It grants no reuse rights in any case. (V text; C scope.)

### Is there a lawful zero-fee route that does not need AMFI's consent?

Possibly. It is unproven. These are questions for qualified counsel. An opinion would assess risk; it would not grant rights the way written permission does. Three questions need answers:
1. **Copyright in facts.** In *Eastern Book Company v. D.B. Modak*, (2008) 1 SCC 1, the Supreme Court held that a compilation needs a minimum of creativity, and that purely functional compilations are not protected. Daily NAVs, TERs and AUMs are facts that SEBI compels AMCs to publish. A rule-mandated, unselective list may not attract copyright (C). India appears to have no separate database right like the EU's (U: not confirmed against a primary source in this study).
2. **Contract.** AMFI's terms may still bind anyone who uses the site, whatever the copyright position. Whether these browse-wrap terms bind an automated retriever, and whether retrieving through a third-party mirror avoids them, is a legal question. A mirror does not clean the data: its operator's own compliance with AMFI's terms is unknown.
3. **Regulatory exposure.** Republishing scheme data commercially, even factual data, must also respect SEBI's advertisement and IA/RA boundaries ([13 A2](13-wickstreet-2.0-mf-first-release-plan.md)).

Under the fail-closed policy, an unresolved route blocks commercial use. It does **not** prove that no lawful route exists.

---

## 4. Data quality and freshness findings

**Method (strict posture).** Programmatic reads only on mfnav.in and TigZig, whose terms explicitly allow API use. mfapi.in was hand-viewed for 2 records. AMFI: download pages hand-viewed; no AMFI data fetched. Results stayed in memory; nothing was stored except this summary. Sample: 8 schemes.

| Scheme (AMFI code) | Type | TigZig rows (range) | mfnav rows | NAV mismatches on common dates |
|---|---|---|---|---|
| ICICI Pru Large Cap Direct Growth (120586) | Large cap | 3,398 (2013-01-02 → 2026-10-22) | 3,395 | 0 |
| Mirae Asset ELSS Tax Saver Direct Growth (135781) | ELSS | 2,667 (2015-12-29 → 2026-10-22) | 2,664 | 0 |
| UTI Nifty 50 Index Direct Growth (120716) | Index fund | 3,398 (2013-01-02 → 2026-10-22) | 3,395 | 0 |
| Nippon India ETF Nifty 50 BeES (140084) | ETF | 2,460 (2016-11-07 → 2026-10-22) | 2,457 | 0 |
| HDFC Liquid Direct Growth (119091) | Liquid (calendar-day NAV) | 4,609 (2012-12-31 → 2026-10-22) | 4,606 | 0 |
| ABSL Credit Risk Segregated Portfolio 1 Direct Growth (147802) | Segregated portfolio | 694 (2019-11-25 → 2022-09-30) | 691 | 0 |
| L&T India Large Cap Direct Growth (119308) | Merged (last NAV 2022-11-25) | 2,436 (2013-01-02 → 2022-11-25) | 2,433 | 0 |
| ICICI Pru FMP Corp Bond Series B 1100D Direct (130803) | Matured FMP | 722 (2014-08-14 → 2017-08-16) | 721 | 0 |

**Observed**
- **Agreement.** 20,362 common date–NAV pairs across the two mirrors; 0 differ by more than 0.0001. Both copy AMFI, so this tests pipeline fidelity, not independent truth.
- **Missing days in mfnav.in.** It lacks 2019-12-23 and 2019-12-24 for every live scheme, and returns `nav: null` for 2020-04-24 in 7 of 8 schemes. TigZig has all three days. mfnav also lacks the FMP's final NAV (2017-08-16).
- **Missing day in mfapi.in.** The merged L&T scheme's latest NAV is 2022-11-24 (45.6494, which matches TigZig). TigZig and mfnav have one more day, 2022-11-25 (45.671). mfapi.in also returns `isin_growth: null` for this scheme; TigZig and mfnav have INF917K01FQ0.
- **Derived-return conventions differ.** mfnav's own 1y return differs from a plain end/start recomputation for all 4 equity schemes. Example, ICICI Large Cap as of 2026-10-22: −10.340% vs −10.392%. The cause is the choice of start date when the anniversary is a holiday. Liquid fund (calendar NAV): identical (+6.4241%). **Wickstreet must compute every metric itself under one documented convention.**
- **Classification parsing.** mfnav labels the ETF `plan=Direct`; mfapi.in shows AMFI's name as "… BeES - Direct Plan". Plan/option must come from a tested parser with exceptions for ETFs.
- **History breaks at scheme-code changes.** The Nifty BeES ETF (launched 2001) has history only from 2016-11-07 under code 140084. Direct plans start in January 2013, as expected.
- **Gaps.** Gaps longer than 5 calendar days: 2014-10-01 → 10-07 (a run of holidays) in 4 of 8 schemes; the FMP also has 2015-03-31 → 04-06.
- **Successors.** None of the three mirrors links a merged scheme to its successor.
- **Freshness.** All three had the 2026-10-22 NAV on the morning of 2026-10-23. TigZig catalog `generated_at` 2026-10-22T18:40Z.

**Published claims (not verified here)**
- AMFI NAV deadlines: 11 PM on T for most schemes; 10 AM on T+1 for FoFs and overseas funds (circular §9.3.4, V as rule).
- mfapi.in: "Updated 6x daily", "99.9% uptime". mfnav.in: daily 03:00 sync, random past-date re-check against AMFI. TigZig: NAV 3×/day, details 4×/day.
- TigZig data caveats: no split adjustment; 0.00 and negative NAVs kept as filed; about 50 stale schemes; about 800 ISINs map to two codes; weekly NAVs for early close-ended schemes; holiday-dated NAVs for liquid funds; SEBI's February 2026 recategorisation mixes old and new category names; segregated portfolios stop around 2026-03-09.

**Not sampled**
- AMFI directly (terms); holdings files (AMC terms); TRI series (index terms); SSD, TER, riskometer and AUM values (seen only as schema fields in TigZig's data dictionary).

---

## 5. Gaps and free mitigations

| # | Gap | Blocks | Free mitigation | Residual |
|---|---|---|---|---|
| **P1** | **No commercial right to AMFI data** (NAV, master, AUM, TER, SSD, riskometer, returns, portfolios) | Most core MF research capabilities | (a) Written AMFI permission (no fee assumed; none quoted). (b) Weaker: counsel's opinion on facts/contract (§3), a risk assessment, not a grant. (c) Mirrors **do not** mitigate | Owner decision; outward-facing; not authorised here |
| **P2** | No free TRI series | Beta, alpha, TE, capture ratios, benchmark charts | (a) Use AMFI's daily scheme vs TRI CAGR at fixed horizons (under P1). (b) Use a large index fund's Direct-plan NAV as a labelled **proxy**, under P1. (c) Show price index with "excludes dividends" (still needs P2) | An index fund's NAV is **not** an interchangeable TRI substitute. Its expenses, tracking difference, and scheme-specific history (start date, code changes, mergers) bias beta, alpha, TE and capture ratios. Any proxy-based metric must be labelled as such. True TRI needs a licence |
| **P3** | Holdings rights per AMC | Holdings, overlap, sector/rating exposure | Use AMFI-hosted copies under P1 (§6.1.1), so one permission covers all AMCs | ≈45 layouts to parse; ratings/industry labels differ by AMC |
| G4 | Merger/successor mapping | Continuous track records, migration of saved lists | Curate by hand from AMC notices (a small, versioned reference table) | Manual effort; rights to AMC notices are factual citations (C) |
| G5 | IDCW payout history | IDCW-option returns, SIP on IDCW | Restrict analytics to Growth options; show IDCW NAV only | Feature narrowed |
| G6 | Manager, TER and riskometer history | Tenure analytics, TER trend | Accumulate snapshots from the first permitted ingestion | History starts at ingestion; needs storage rights (P1) |
| G7 | Split/face-value changes | Correct returns across events | Detect NAV jumps and keep a curated adjustment table | Manual review |
| G8 | Retrieval limits | Bulk backfill | AMFI history: 90-day windows; backfill as a one-off batch, only once P1 allows it | Engineering time |

---

## 6. Recommended source strategy

| Dataset | Primary | Fallback | Condition |
|---|---|---|---|
| NAV daily + history, scheme master, AUM, TER, SSD, riskometer, scheme vs TRI returns, portfolios | **AMFI, direct**, under written permission (P1) | AMC sites under per-AMC permission (P3) | Fail-closed until P1. Do **not** use a mirror as the system of record: none can show chain of title, and one republishes with no named operator |
| QA cross-check | TigZig, then mfnav.in, as **read-only reconciliation** (not stored, not displayed) | — | Only within their API terms, and only after P1 makes the primary data lawful. Their data dictionary and exception list are useful format references |
| Benchmark series | Index-fund NAV proxy (labelled) + AMFI fixed-horizon TRI returns | NSE Indices / BISPL licence (P2, fee unknown) | Proxy needs P1 |
| Risk-free rate | **RBI DBIE**, with acknowledgement | Leave Sharpe `NA` | Confirm the series exists on DBIE (C) |
| Methodology rules | SEBI Master Circular 2026 | — | Cite clause numbers |
| Mergers, splits | Curated reference tables | — | Owner-maintained |

---

## 7. Feasible product scope under **confirmed** zero-fee permissions (today)

| Capability | Status today | Basis |
|---|---|---|
| SIP, lumpsum and goal calculators on user-entered assumptions | ✅ | No market data ([15 §6](15-stage-b0-product-and-value-specification.md#6-data-rights-and-199-cost-envelope)) |
| SEBI rule explainers (categories, riskometer scale, TER/IR formulas) | ✅ | Public regulation |
| Risk-free rate series with acknowledgement | ✅ (C: dataset to confirm) | RBI DBIE |
| User's own CAS holdings and XIRR (Stage C) | ✅ data rights; Stage C security gate applies | User's own records |
| Scheme discovery, NAV charts, returns, risk, TER, screening, comparisons, SIP replay, holdings, overlap | ❌ | P1 (and P2/P3 for parts) |

**This confirmed scope is not Tickertape-class MF research.** It supports only the assumption-only prototype that [14 §5](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate) already allows.

**Scope if P1 is granted at zero fee:** everything in §2 marked ✅ or ⚠️ under "Free", except true TRI-based ratios (P2). That covers scheme discovery and master, NAV charts, all NAV-derived returns and risk metrics, rolling returns, SIP replay (Growth options), AUM, TER, riskometer, current managers, exit loads, benchmark names, fixed-horizon scheme vs TRI returns, holdings and overlap (from AMFI-hosted portfolios), and discontinued-scheme handling. That is a credible Tickertape-class MF core.

---

## 8. Architecture fit (conditional on verified rights)

> **Superseded in part, 2026-10-23:** the refresh runs once daily at 11:30 IST ([ADR-022 §2.12](../../architecture/adr/ADR-022-multilingual-research-agent.md)), not at the example times below. MF tables live in the `wickstreet` schema with MF-owned versioning, not in Momentum25's `REFERENCE_VERSIONED` ([ADR-023 §2.8](../../architecture/adr/ADR-023-operating-modes.md); [ADR-017 MF-5 to MF-8](../../architecture/adr/ADR-017-funds-etfs-holdings.md#wickstreet-20-realignment-accepted-2026-10-23)).

The accepted FastAPI/Python + PostgreSQL design fits without new services. Daily volume is small: about 8,300 active plans × 1 NAV/day. Each stage below runs **only for datasets whose permission record covers that use** ([14 §5](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate)). A technically feasible pipeline is not a permitted one.

| Stage | Design | Gate |
|---|---|---|
| Acquire | One scheduled batch job after the NAV deadline (e.g. 23:30 and 10:30 IST), fetching publisher files. No per-user API calls | Automated-retrieval right |
| Snapshot | Store each raw file unchanged with source URL, fetch time and SHA-256 | Storage + backup rights |
| Normalise | Parse into versioned reference tables in `REFERENCE_VERSIONED` (never `ALL_VERSIONED`, so Momentum25 `data_version` is unaffected). Corrections append new revisions | Storage right |
| Validate | Reject or quarantine: null/zero/negative NAV, duplicate ISIN→code, day-over-day jumps above a threshold, missing expected schemes, future-dated rows. Reconcile a sample against a mirror (read-only) | — |
| Derive | Deterministic metrics with one documented convention; record method version and input revision | Derived-metrics right; owner-approved formulas |
| Serve | Read-only API from the shared cache; every value carries source, date and revision | Subscriber-display right; free vs paid both covered |
| Export | Reports and CSV only for fields whose permission covers export | Export right |
| Retire | Delete or stop serving data when a permission ends | Termination/deletion terms |

---

## 9. Economic feasibility

Reuse of [13 A3a](13-wickstreet-2.0-mf-first-release-plan.md) and [15 §6](15-stage-b0-product-and-value-specification.md#6-data-rights-and-199-cost-envelope); no new model.

| Cost line | Status | Evidence |
|---|---|---|
| **Supplier licence fee, AMFI data** | ₹0 **only if** P1 is granted free. No quote or price exists; unknown ≠ zero | This report §3 |
| Supplier licence fee, TRI series | **Not zero** if bought; fee unknown. A labelled proxy defers it but does not replace TRI | §5 P2 |
| Infrastructure | Lean envelope ₹0.36 lakh/yr at 1,000 payers to ₹4.80 lakh at 50,000 | 13 A3a (U allowances) |
| Data engineering | One-off: NAV/master/TER/SSD parsers, 90-day-window backfill, ≈45 AMC portfolio layouts (or one AMFI-hosted format), curated merger/split tables. Ongoing: format drift and validation triage. Founder/intern time; unpriced | §5, §8 |
| Legal | Opinion on facts vs contract (§3), drafting the permission request, terms of service. Unquoted | — |
| Support and regulatory | Data-error handling; advertisement-code and IA/RA boundary review | 13 A2 |
| Net receipts per payer | ₹168.64 ex-GST; steady-state contribution ₹132.57 lean / ₹110.57 growth before data licences; operating break-even ≈272 payers lean | 13 A3a |

**Assessment.** If P1 is granted at no fee, zero-fee rights would remove a major cost uncertainty. They would not make the ₹199 product viable on their own. Engineering, support, acquisition, legal and operating costs remain, and 13 A3a's viability is itself unproven. Among data costs, the binding constraint is **rights, not supplier fees.** The remaining supplier-fee risk is a TRI licence. A labelled proxy can defer that cost, with weaker benchmark-relative metrics.

---

## 10. Dependencies to resolve (for CONDITIONAL GO → GO)

| # | Dependency | Owner action | Unblocks |
|---|---|---|---|
| **P1** | Written AMFI permission for commercial automated retrieval, storage, backups, derived metrics, free and paid subscriber display, reports and export, covering NAV, scheme master, AUM, TER, SSD, riskometer, performance and AMFI-hosted portfolios. **Weaker alternative:** an opinion from qualified counsel on whether these factual, SEBI-mandated disclosures may be used commercially without AMFI's licence, and on which retrieval route is lawful. That opinion assesses risk; it is not equivalent to written permission | Owner only: any request or legal engagement is outward-facing and is not authorised by this research | Most core MF research capabilities |
| P2 | TRI series licence quote (NSE Indices, BISPL), **or** owner acceptance of a labelled index-fund proxy with its known bias (§5) | Owner decision | Beta, alpha, TE, capture ratios |
| P3 | Covered by P1 if AMFI-hosted portfolios are included; otherwise per-AMC permission | — | Holdings, overlap |
| R1 | Reliability evidence on AMFI direct (latency vs deadline, correction frequency) over ≥20 trading days | Only after P1 | Freshness SLA |
| R2 | Confirm unread AMC terms (SBI, ICICI Pru, Nippon, Kotak) and the RBI T-bill series | Desk check | Fallback paths |

Until P1 is resolved: no ingestion of live MF data and no commercial launch. Fixture-based development and the assumption-only prototype stay as authorised in [14](14-stage-b-implementation-plan.md).

---

## Sources (accessed 2026-10-23 unless noted)

Primary
- AMFI terms of use: <https://www.amfiindia.com/terms-of-use>; NAV download (90-day note): <https://www.amfiindia.com/net-asset-value/nav-download>; scheme-wise disclosure page: <https://www.amfiindia.com/otherdata/scheme-wise-disclosure>
- SEBI Master Circular for Mutual Funds, 2026-03-20: <https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html> (PDF <https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf>), §§6.1, 6.4, 6.8, 6.9, 6.10, 6.16, 9.3, 11.2, 19.10.4
- SEBI educational price-data circular, 2026-05-08: <https://www.sebi.gov.in/sebi_data/attachdocs/may-2026/1778242522289.pdf>
- SEBI Guidelines for Seeking Data, v2, 2019-10-17: <https://www.sebi.gov.in/pdf/guidelines-of-data-sharing-final.pdf>
- TigZig: catalog <https://api.tigzig.com/mf/v1/>, API terms <https://api.tigzig.com/mf/v1/terms>, site terms <https://www.tigzig.com/terms>, data dictionary <https://mfpro.tigzig.com/md/data-dictionary.md>, homepage <https://www.tigzig.com/>, API guide <https://www.tigzig.com/apis/mf-nav>
- mfnav.in: <https://mfnav.in/terms>, <https://mfnav.in/about>, <https://mfnav.in/api-docs>
- mfapi.in: <https://www.mfapi.in/>, <https://www.mfapi.in/docs/>
- AMC terms: HDFC <https://www.hdfcfund.com/disclaimer>; PPFAS <https://amc.ppfas.com/other-links/disclaimer.php>; Axis <https://www.axismf.com/term-of-use>; Mirae <https://www.miraeassetmf.co.in/terms-of-use>; Jio BlackRock <https://www.jioblackrockamc.com/terms-and-conditions>
- BSE Index Services terms: <https://www.bseindices.com/terms-of-use>
- RBI DBIE disclaimer: <https://data.rbi.org.in/DBIE/#/dbie/disclaimer>
- captn3m0/historical-mf-data: <https://github.com/captn3m0/historical-mf-data>
- Prior study: [12-d0r-data-source-research.md](12-d0r-data-source-research.md) (NSE Indices terms, read 2026-10-22)

Secondary (C/U rows only)
- *Eastern Book Company v. D.B. Modak*, (2008) 1 SCC 1, summary: <https://lawtimesjournal.in/eastern-book-company-and-ors-vs-d-b-modak-and-ors/>
- GODL-India text (mirror): <https://wiki.openstreetmap.org/wiki/Open_Geospatial_Data_from_Government_of_India>
- BullWiser data sources (commercial site relying on "publicly available" AMFI files, no licence claimed): <https://bullwiser.com/data-sources>
- Kaggle MF dataset (MIT compilation): <https://www.kaggle.com/datasets/tharunreddy2911/mutual-fund-data>

Inaccessible (Unverified): data.gov.in search and GODL page (HTTP 403); India Data Portal (HTTP 403); SBI, ICICI Pru, Nippon, Kotak terms (404/empty); NSE Indices (HTTP 403 to plain fetch; not bypassed).
