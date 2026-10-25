# QA review: 25 Oct remediation

Independent acceptance on the served app, 25 Oct 2026.

- App: http://localhost:8000/mf, branch `wickstreet/m10-m11` at 8ae1a2c, snapshot 6000, method v8, NAVs to 23 Oct 2026.
- Browser: Playwright Chromium. Workspace records mocked to `[]`. Phones use `isMobile` at height 844.
- Database: read-only session (`default_transaction_read_only=on`) on `localhost:55432`. Port 5432 is not open; `.env` maps Postgres to 55432.
- Screens and scripts: `/private/tmp/claude-501/-Users-varunagarwal-Downloads-Applications-StocksMomentum/ace4e294-de48-4b61-820d-a404492ff5d6/scratchpad/qa/`. File names below are relative to that folder.

## Results

| # | Criterion | Result | Evidence |
|---|---|---|---|
| A1 | Screener columns at 1280 and 1440; row actions; keyboard scroll | **FAIL** | Default 6 columns fit at both widths (scroll width = client width: 702 at 1280, 862 at 1440). The A2 task breaks it at 1280: with Return 1Y shown, "Score category rank" is 26 of 79 px visible. The header reads "cat" and the values are half faded (`a1-1280-ret1y.png`). After one "Scroll" click, TER shows 12 of 57 px and Consistency 3Y 16 of 99 px (`a1-1280-scrollbtn-0.png`). At 1440 with Return 1Y, TER, AUM and Volatility 3Y shown, Sharpe 3Y shows 13 of 69 px (`a1-1440-wide.png`). When scrolled, columns are cut where they pass under the sticky fund column (": Oct 2026", `a1-1440-wide-scrolled.png`). Actions pass: 46 of 46 rows have enabled Watch and Compare buttons at both widths. Keyboard passes: the region (`role=region`, `tabindex=0`, "Screen results") scrolls 0 → 200 px on 5 × ArrowRight. |
| A2 | Return 1Y show, −10 minimum, recompute, phone sheet | **PASS** | Ticking "Show Return 1Y" adds the column. The count stays 46. Typing −10 opens no dialog (0 `dialog` elements). One request is sent with `{"field":"ret_1y","op":"between","value":[-0.1,null]}`. The page and API both give 37. Raw-NAV recompute (NAV on 23 Oct 2026 ÷ last NAV on or before 23 Oct 2025 − 1) for the 46 funds: 42 have a start NAV, 37 are ≥ −10%. The set equals the API set exactly. Max difference to API `ret_1y` is 2.9e−11. The 4 without a value first traded on 30 Dec 2025, 4 Mar 2026, 13 Aug 2026 and 10 Sep 2026. Phone 390×844: the sheet opens as a native `<dialog>` with "Show 46 funds". After −10 it reads "Show 37 funds". Tapping it shows 37 cards (`a2m-3-min.png`, `a2m-4-results.png`). |
| A3 | Enum, boolean, date inline | **PASS** (desktop only) | Fund house: inline searchable checklist. Ticking "HDFC Asset Management Company Limited" sends `amc in [...]` and the count goes 46 → 1. Active: inline Any/Yes/No radio. "No" sends `active = false` (0 funds), "Yes" sends `active = true` (46 funds). First valid NAV: inline From/To date inputs. From 2020-01-01 sends `since_start between ["2020-01-01",null]` and gives 23. The DB gives 23 of 46 with first NAV on or after 1 Jan 2020. No operator step and no dialog for any of them. I did not test these three on the phone sheet. |
| A4 | Missing-value note scoped to this screen | **PASS** | The note reads "4 funds meet every other condition but have no Return 1Y value, so they are left out." The API `excluded_missing` for `ret_1y` is 4 (`history_too_short`). The DB check agrees (4 funds launched after 23 Oct 2025). |
| B1 | Phones 320/375/390/430 × 8 routes | **FAIL** | Pass parts: no horizontal page overflow on any of 32 views (document overflow 0). No floating compare tray; the only fixed or sticky elements are the header and the bottom nav. The bottom nav hides on scroll down (top 779 → 844) and returns on scroll up (844 → 779) on all 32 views. The page end is not covered (last content ends at 758 px or above; nav top is 779). Fail parts: on `?tab=risk` and `?tab=holdings` the fund name column is 5 px wide at 320, 60 at 375, 75 at 390 and 115 at 430, for a 263 px name. At 320 the name shows as "]" (`b1/320-holdings.png`). Numbers are clipped at 320 on /mf/simulate and /mf/funds/122639 (defects 2 and 6). |
| C1 | Phone key facts show source and date | **PASS** | At 390: TER "AMFI 1 Oct" = `ter_as_of` 2026-10-01. AUM "AMFI 22 Oct" = `aum_as_of` 2026-10-22. Risk "AMFI 22 Oct" = `riskometer_as_of` 2026-10-22. Benchmark "AMFI 22 Oct" = `perf_as_of` 2026-10-22. Manager "Scheme doc 24 Oct" = `document.managers.as_of` 2026-10-24. Portfolio "30 Sep 2026 · AMC filing" = `holdings_as_of` 2026-09-30 (`c1-390.png`). At 320 these values truncate (defect 2). |
| D1 | Calm equity rule and order | **PASS** on rule, **FAIL** on wording | Stated rule: "Diversified equity funds, no sector or theme funds, in the calmer half of their category by 3Y volatility, with a 3Y return at or above the category median. Calmest first." I checked all 57 funds (API, page order matches for the first 22). 0 Sectoral/Thematic. Every fund has `vol_3y_cat_pct` ≥ 50 and `vol_3y` ≤ its category median, so 100 means calmest. Every fund has `cagr_3y_cat_pct` ≥ 50 and `cagr_3y` ≥ its category median. Sorted by `vol_3y` ascending, 9.92% → 16.9%. Wording problems for a beginner: the chip reads "Volatility 3Y category percentile ≥ 50", which looks like "more volatile than half". The list holds 5 small-cap and 4 mid-cap funds (3Y volatility 14.9–16.9%), so "calm" is relative to the category only. The Category select shows "All categories" while 11 categories are filtered (`d1-1440.png`). |
| D2 | Compare peers from PPFAS | **PASS** | One click on "Compare peers" opens `/mf/compare?code=122639&code=118955&code=120166` at 1440 and 390. Identities: 118955 "HDFC Flexi Cap Fund - Growth Option - Direct Plan" and 120166 "Kotak Flexi Cap Fund - Growth - Direct". Both have plan `direct`, option `growth`, and they are the two largest Flexi Cap direct growth peers by AUM. They are chosen by a query, not hard-coded. Page = API: TER 0.69 / 0.75 / 0.67%; AUM ₹1,46,988 / ₹1,07,566 / ₹52,650 Cr; 1Y −6.68 / −6.76 / −8.97%; 3Y CAGR 12.3 / 14.4 / 10.3%; max drawdown 3Y −11.0 / −13.3 / −16.3%; benchmark Nifty 500 TRI for all three. Overlap: the API gives `not_filed` for all 3 pairs. The page says "No stored portfolio for HDFC Flexi Cap, Kotak Flexi Cap, so overlap cannot be read." It also says "Wickstreet stores the monthly portfolio only where it can read the fund house's file." This is true: only PPFAS has `holdings_as_of` (30 Sep 2026). |
| V1 | Visual pass, 5 routes × 1440/390 × light/dark | **FAIL** | 60 captures in `v1/`. Desktop light and dark are coherent and legible. The phone fund tab header is broken (defect 1). Phone compare cards lose fund names (defect 5). See defects 7, 12 and 13 for smaller issues. |
| R1 | Regressions: Advanced, formula, Save | **PASS** | Advanced → search "CAGR 3Y" → "Add condition" panel → at least 12 sends `cagr_3y >= 0.12`. Count 46 → 16, the API also gives 16. Formula `edge_3y = cagr_3y - cagr_3y_cat_median` adds a column. PPFAS shows 0.01 against API 0.01479 (correct, but see defect 14). "Save screen" opens the "Save this screen" sheet with Name and Save. |

## Defects, ranked

1. **High. Phone fund tab header collapses.** `/mf/funds/122639?tab=risk` and `?tab=holdings`, 320–430 px, both themes.
   - Repro: open the route on a phone.
   - Expected: the fund name is readable, as on the Overview tab.
   - Actual: the `h1` is 5 px wide at 320, 60 px at 375, 75 px at 390 and 115 px at 430. At 320 the name shows as "]". "Flexi Cap · Direct · Growth" stacks one word per line, and the score badge overlaps it.
   - Screens: `b1/320-holdings.png`, `v1/m-risk-dark-0.png`.
2. **High. Numbers clipped at 320 px.**
   - `/mf/simulate?code=122639`: the hero tiles show "₹6,10,0…", "₹7,94,3…" and "₹1,84,3…" (`b1/320-simulate.png`).
   - `/mf/funds/122639`: the key-fact strip shows "₹1,46,98…", "Nifty 500 …", "30 Sep 2…" and "Scheme doc …" (`b1/320-fund.png`).
   - Expected: full values; wrap or shrink the text.
3. **Medium. Screener columns cut at 1280 and 1440 once a metric is added.** `/mf/screen`, light.
   - Repro at 1280: tick "Show Return 1Y". Repro at 1440: also tick TER, AUM and Volatility 3Y.
   - Expected: no half-visible header or value.
   - Actual: the edge column is partly visible under a fade ("cat", 26 of 79 px; Sharpe 3Y 13 of 69 px). The "Scroll" button and arrow keys stop at pixel offsets, not column edges. Cells are cut where they pass under the sticky fund column.
   - Screens: `a1-1280-ret1y.png`, `a1-1280-scrollbtn-0.png`, `a1-1440-wide-scrolled.png`.
4. **Medium. The Fund house filter overflows its card and pushes columns off at 1440.**
   - Repro: Basic → Fund → Filter by Fund house → type HDFC → tick a value.
   - Actual: the value list and search box run past the left card's edge ("HDFC Asset Management C…"). Filtering also adds a wide "Fund house" text column, so Consistency 3Y is cut at the right edge.
   - Screen: `a3-enum.png`.
5. **Medium. Phone compare cards drop fund names.** `/mf/compare?...`, 320–430.
   - Actual: each card reads "0.69% vs 0.75% vs 0.67%". The reader must map values to funds by chip order. The winner's name truncates ("Parag Parik…", "HDFC Flexi…").
   - Expected: label each value, as on desktop.
   - Screens: `d2-390.png`, `b1/320-compare.png`.
6. **Medium. "Compare peers" is half hidden at 320.** `/mf/funds/122639`.
   - Actual: the action row scrolls sideways (scroll width 725, client width 229), and the button shows as "Compa".
   - Screen: `b1/320-fund.png`.
7. **Medium. Calm equity wording misleads a beginner.** `/mf/screen?preset=calm_equity`.
   - The chip "Volatility 3Y category percentile ≥ 50" reads as "more volatile". It should say, for example, "Volatility 3Y in calmer half of category".
   - "Calm" includes small-cap funds with 3Y volatility up to 16.9%. The purpose line says the rule is category-relative, but the name does not.
   - The Category select shows "All categories" while 11 categories are filtered.
8. **Low–medium. Duplicate AMC names in Fund house.** Examples: "HDFC Asset Management Company Limited" and "HDFC Mutual Fund", plus the same split for Kotak, Aditya Birla and 360 ONE. Picking one name can miss funds. The list shows all 112 values, not only those in the screen. This is a known data item.
9. **Low. The column cap blocks a fifth metric.** Ticking Return 1Y, TER, AUM and Volatility 3Y fills all 12 columns, because TER and AUM each add a date column. The panel then says "All 12 result columns are in use." New columns go before Score, in reverse click order.
10. **Low. The table header does not stay in view.** The header is sticky only inside the scroll container (thead top −993 px after a page scroll), so column names disappear on a 46-row list.
11. **Low. Fund names truncate at 1440** in the fixed 170 px fund column ("Parag Parikh Flexi Cap ...", "ICICI Prudential Flexi C..."), even when there is spare width.
12. **Low. The compare table colours the best negative value green** ("−6.68% ✓" in green next to red "−6.76%"). The best-value mark overrides the sign colour. Screen: `v1/d-compare-dark-2.png`.
13. **Low. Phone Discover polish.**
    - The stats line wraps with a leading "·".
    - The hero's decorative peaks run behind the stats text.
    - The search placeholder is cut ("or an AMF").
    - At 375, idea rows truncate the Sharpe value ("Sharpe 0.8…").
    - Screens: `v1/m-discover-dark-0.png`, `v1/m-discover-light-0.png`.
14. **Low. Formula values show 2 decimals with no unit.** 0.01479 shows as "0.01".
15. **Low. Copy consistency.**
    - The count reads "1 funds".
    - The chip uses a hyphen ("≥ -10%") where the table uses "−".
    - The date chip uses ISO format ("≥ 2020-01-01").
    - Phone facts drop the year ("AMFI 1 Oct") but keep it for the portfolio date.
    - The phone shows "Scheme doc 24 Oct", which reads like a filing date. Desktop says "read 24 Oct 2026".
16. **Low. The same fall appears as two numbers.** The Risk tab says "Deepest −31.2% on 24 Mar 2020": own peak 13 Feb to trough 24 Mar, DB −31.20%. Overview says "lost 31.0% (12 Feb 2020 to 23 Mar 2020)": the proxy window, DB −30.96%. Both are right, but the page does not say why they differ.

## Not tested

- Enum, boolean and date refinement inside the phone filter sheet (A3 covered desktop only).
- Touch swipe on the results region (A1 covered keyboard only).
- Count latency against a ≤ 1 s budget. I waited 1.0–1.5 s and did not time it.
- Saving a screen. The workspace store is mocked, so only the sheet was checked.
