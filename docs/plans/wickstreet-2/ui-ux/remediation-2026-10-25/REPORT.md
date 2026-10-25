# Remediation of the 25 October live assessment

**Date:** 25 October 2026 · **Branch:** `wickstreet/m10-m11` (local, not pushed) · **Data:** snapshot 6000, method v8, NAVs to 23 Oct 2026.

This report covers the P0 defects in [LIVE_ASSESSMENT_2026-10-25](../tickertape-competitive-benchmark/LIVE_ASSESSMENT_2026-10-25.md), the backlog items done after them, and what is still open. The engineer who made a fix did not accept it alone. An independent reviewer checked the served app; see [QA-REVIEW.md](QA-REVIEW.md).

## P0 fixes

| Item | Defect as found | Fix | Evidence |
|---|---|---|---|
| A. Screener columns | At 1440 px the sticky Actions column (104 px) covered Consistency and Score category rank. The table needed 1,033 px in an 838 px scroller. | Watch and Compare sit in the fund cell. Headers wrap to two lines. A fade marks columns still off-screen. The filter rail is 256 px below 2xl. | Six default columns fit with no clipped header at 1280, 1366, 1440 and 1536 px (probe and E2E). |
| A. Threshold | Not proven end to end. | Already one action: ticking Return 1Y opens its range. The phone sheet now ends with "Show N funds". The missing-value note counts funds in this screen only. | Return 1Y ≥ −10% sends `ret_1y between [-0.1, null]`. 46 funds become 37, on desktop and phone. A recompute from raw NAVs gives the same 37 funds. 4 young funds have no 1Y value; the note now says 4, not 32,327. |
| A. Other kinds | Not verified. | — | Fund house = PPFAS → 1 fund. Active = Yes → 46. First valid NAV from 2020-01-01 → 23; an independent DB count gives 23. No operator or date step. |
| B. Phone overlays | The compare tray floated over Discover's market card. The bottom bar covered charts. | Phones have no tray: the Compare tab shows the count. The bottom bar slides away while the reader scrolls down. | 320, 375, 390 and 430 px on 8 routes: no page overflow, no off-edge text, nothing under a fixed bar after a scroll. |
| C. Phone provenance | The six phone facts had no source or date. | Each fact shows a source and date, for example "AMFI 22 Oct". The phone score line became one rank link to keep the 80 px plot budget. | E2E: facts show AMFI, Scheme doc and AMC filing; the plot budget test passes. |
| D1. Calm equity | 25 of 82 funds were sectoral or thematic (16 of the top 20). | The 11 diversified SEBI equity categories, calmer half by 3Y volatility, 3Y return at or above the category median, calmest first. | 57 funds, none sectoral, no rule violation. |
| D2. Compare peers | Compare showed PPFAS with Axis ELSS; no peer route. | "Compare peers" on every fund opens its two largest same-category peers by AUM. Compare offers the next-largest peers as chips and marks the ones with a stored portfolio. | PPFAS → HDFC Flexi Cap + Kotak Flexi Cap in one click, with returns, risk, TER, AUM and benchmark. Overlap says plainly that HDFC and Kotak have no stored portfolio. |

## Done after the P0 list

- **Category lens (rank 9).** Discover's category cards highlight the top-scored, largest or lowest-cost fund, and open the category sorted the same way.
- **Peers tab (rank 2).** It opens with the fund and its four largest peers: 1Y, 3Y CAGR, worst 3Y fall, TER and AUM, with "Compare these 5".
- **Data integrity.** 254 schemes showed a direct TER of 0.00%. Three causes, all fixed with tests:
  - AMFI files 0 for a plan an ETF does not offer. The parser now skips a plan whose Total TER is 0.
  - AMFI serves UTI Large Cap's SSD under two scheme ids (264 and 807). The higher id won the ISIN join and the SEBI-code join, so UTI Large Cap Direct showed another scheme's TER: 0, not the filed 1.19%. Contested ISINs now go to the scheme the plan's NAV name names. A SEBI code two schemes share joins by name. 12 codes are shared by 24 schemes.
  - A reparse superseded only changed values, so a fact the fixed parser no longer gives stayed current. A reparse now retracts what its own run wrote and the new parse drops. Other runs are untouched; superseded rows stay for audit.
- **Data correction run (real data, 25 Oct).** The kept 24 Oct SSD file was republished; TER months 2019–2026, performance days 2019–2026 and tracking-error days 2024–2026 were reparsed from kept files. Nothing was fetched. 31,954 TER rows were retracted (23,394 + 8,560); performance moved 2,815. New snapshot: revision 6236, method v8 unchanged, 148 s, 667 MB peak.

  | Check against AMFI's raw file | Before | After |
  |---|---|---|
  | UTI Large Cap Direct (120656) TER | 0.00% | 1.19% (filed 1.19%) |
  | UTI Large Cap Direct AUM | ₹11,433 Cr, from the wrong scheme's row | ₹11,433 Cr, its own row (scheme 264) |
  | Kotak MNC Fund Direct TER | 0.56% (the Tourism Index fund's) | 0.90% (filed 0.9014%) |
  | Kotak Nifty India Tourism Index Direct TER | 0.33% | 0.56% (filed 0.5615%) |
  | Active plan options with a 0 TER | 81 | 0 |
  | Nippon India Nifty Auto Index benchmark | Nifty 500 Low Volatility 50 TRI | Nifty Auto TRI |
  | LIC MF Large Cap benchmark | NIFTY 500 Multicap 50:25:25 | Nifty 100 TRI |
  | WhiteOak Capital Quality Equity benchmark, riskometer | Nifty Equity Savings TRI, Moderately High | BSE Quality TRI, Very High |
- **SIP check.** ₹10,000 a month into PPFAS Flexi Cap from Oct 2021, valued on 23 Oct 2026: 61 instalments, ₹6,10,000 invested, ₹7,94,356, XIRR 10.41%. An independent script from raw NAVs gives the same figures.
- **Clarity.** "Compare peers" and "Add to compare" no longer look alike. Discover names the proxy's 12-month change beside its line.

## Screens

[screens/after](screens/after) holds 12 routes in light and dark, desktop (1440 × 1000) and phone (390 × 844). [scripts/capture.cjs](scripts/capture.cjs) recreates them.

## Open

| Item | Why open | Next step |
|---|---|---|
| PPFAS / HDFC / Kotak holdings overlap | HDFC and Kotak block automated portfolio download. | Owner imports their monthly files with `wickstreet mf import-portfolios`. |
| Whole-portfolio X-ray from a real CAS | No genuine CAS file is available. Synthetic tests do not count. | Owner supplies an authorised CAS. |
| Tickertape matched test | Runs once QA accepts the fixes. | See the comparative section when it lands. |
