# Wickstreet 2.0 MF workstation: independent UI/UX and product audit

**Date:** 23 October 2026 · **App:** `http://localhost:8000/mf` · **Data:** snapshot 2801, NAV as of 22 Oct 2026, method v5
**Code audited:** `6b55da2` (workspace backend), `2fcdaa0` (MF UI), branch `wickstreet/m10-m11`
**Status:** local only. No application code was changed. Nothing was committed or pushed.
**Evidence:** `screens/` (82 screenshots), `refs/` (the owner's two visual references).

---

## How to read this report

Each claim carries one of three labels.

- **Verified.** I reproduced it in the running app, through the API, or in the source. A reproduction is given.
- **Reported.** The implementation notes say it. I did not re-run it.
- **Judgment.** A design opinion. It has no pass or fail.

I did not re-run the 172 unit tests, the 21 MF browser tests, the 236 Momentum25 tests or the 1,407 backend tests. I did not re-run the axe sweep. I spent the time on new evidence instead.

---

## 1. Executive verdict

**Wickstreet does not yet achieve the original vision. It is a strong analytical product in a good-looking shell. It is not yet a category-leading product.**

What is true today:

1. **The numbers are right.** Every figure I cross-checked matched an independent source. That includes a SIP and XIRR I rebuilt from raw NAVs, and Tickertape's public returns for the same fund. This is the hardest thing to get right and it is done.
2. **The analytical depth is beyond Tickertape.** Rolling returns, deepest falls, time to recover, capture in market falls, rank history, a hold-out backtest and rolling-SIP start months have no Tickertape equivalent. The honesty rules (missing values with a reason, proxy labels, in-sample next to out-of-sample) are a real differentiator.
3. **The look is clean and calm, but it is not yet "premium and distinctive" at the owner's reference level.** The paper-and-ink identity is present. The richness of the references is not: no sparklines, no fund or AMC marks, no illustrated collections, no category band on charts, no efficient-frontier line.
4. **The signature screens do not start with a story.** The Analytics studio and the Investment lab open empty. A first-time visitor sees a form, not a chart.
5. **Six defects reduce trust or discovery** (section 5, P1). The worst two are visible in seconds: the Market regimes chart is unreadable, and the fund search hides the most famous fund.
6. **The theme architecture is excellent.** It is the best-engineered part of the build.

**Verdict on the stated ambition ("surpass Tickertape by a substantial margin"):** *not established.* Wickstreet is ahead on analytics and honesty. It is behind on data breadth (holdings, expense ratio, AUM, manager, benchmark), which the plan already marks as dependent on licensed data. On visual richness it is at parity with Tickertape at best, and below the owner's references.

**Weighted score: 6.9 / 10** (section 2).

**What separates this build from category-leading** (detail in section 8):

1. A story on first screen of every tool: pre-filled Studio, Lab and Compare, and a plain-language verdict on every fund.
2. Charts that invite touch: zoom, linked crosshairs, event marks, a category band, a correct axis.
3. A search and a screener that never mislead a beginner.
4. A shared research context (fund set, period, snapshot) that travels between screens.
5. The data the plan already names (E1, E3, E4) so the fund page reaches parity on facts.

---

## 2. Weighted scorecard

Scores are judgments, anchored to the evidence in sections 3 to 6. 10 is "category-leading". 5 is "competent".

| Area | Weight | Score | Weighted | Why |
|---|---|---|---|---|
| Visual design | 25% | 7.0 | 1.75 | Coherent type, spacing and colour; calm paper-and-ink identity; dark mode is good. Short of the references: no sparklines, logos, illustrated cards or rich hero. |
| UX and navigation | 20% | 6.5 | 1.30 | Honest, deep-linked, state restores on Back. Empty first screens, weak search, "Match any" trap, mixed-category default sort, hidden row actions. |
| Financial visualisations | 20% | 6.0 | 1.20 | Good tooltips, histograms, heat table, underwater chart. Broken regimes chart, mislabelled value axes, no zoom or annotations. |
| Functionality | 15% | 8.0 | 1.20 | Figures verified. Persistence and concurrency are robust. Defects are about labels and edge states, not numbers. |
| Mobile | 10% | 7.0 | 0.70 | Designed for phones (bottom bar, filter sheet, card results). Fund page spends the first screen on chrome. A tray covers content. |
| Engineering quality | 10% | 8.0 | 0.80 | One-file theme system with no literal colours elsewhere, keyboard charts, data tables, zero console errors. Some chart-kit defects. |
| **Total** | 100% | | **6.95** | |

---

## 3. Screen-by-screen findings

Paths are under `screens/`. "Owner ref A" is `refs/owner-ref-a-app-screens.png`. "Owner ref B" is `refs/owner-ref-b-visual-proposal.png`.

### 3.1 Discover (`d01-discover-desktop-full.png`, `m-discover-viewport.png`)

**Good.** Serif hero with a layered forest illustration. Six preset chips. Four registry facts. Eight category cards with a tint, the median 3Y CAGR and the top-scored fund. A proxy-labelled market chart and an RBI risk-free chart, each with a data table. The page footer names the snapshot. No console errors.

**Gaps.**

- *Judgment.* The page informs but does not invite. The category cards show a number and a name. The reference shows a 3Y sparkline in each card. Nothing on the page moves.
- *Verified.* "Ideas to research" opens on "Category leaders". The first rows are debt funds (ITI Banking and PSU, UTI Banking and PSU). A young investor who asks "where do I start?" gets bank-and-PSU debt funds first.
- *Verified.* The desktop hero has no search box. The phone hero has one. Both owner references put search in the hero.
- *Verified.* Time axes on the two market charts carry irregular labels ("Jan 22, Dec 22, Nov 23, Oct 24"). See F-15.
- *Verified.* "Flexi Cap 36 funds ranked" on a card, 46 funds in the screener after the click, and "Rank 1 of 31" on the fund page. The three counts are never reconciled. See F-08.
- The "Your watchlist" card is empty text. Owner ref B shows a "Your research" panel with counts and recent views.

### 3.2 Screener (`screen-desktop-light.png`, `screen-preset-consistent-desktop.png`, `m-screen-viewport.png`, `m-screen-filter-sheet.png`)

**Good.**

- Seven presets, each with one plain sentence ("Large-cap funds whose rolling 3Y return beat the category median in 70% of months").
- A 160-field browser, typed conditions, sort, columns, cursor paging.
- Exclusions disclosed: "34,755 exclusions because a value is missing. A missing value never matches."
- Formulas work. I added `cagr_3y / vol_3y` and the first row showed 1.23, the same number as "Return per volatility" on the fund page.
- The view lives in the URL, so a link restores the screen. Back from a fund returned to the same 7-row result (verified).
- CSV export carries a provenance header (snapshot, method, sources, filter, sort) and a reason code per missing cell: `NA:history_too_short`. The file name includes the revision (`...-r2801.csv`).
- The phone filter sheet is well made: current filters on top, field search, Cancel and "Apply filters" in a fixed footer.

**Defects.** See F-03, F-05, F-06, F-09, F-16.

- **F-03.** At 1440 px the default result view hides the watchlist and compare buttons. They sit at x = 1383 and 1425, inside a horizontal scroller (scrollWidth 906 against clientWidth 823). The compare button is cut by the viewport edge. A four-column view shows both buttons.
- **F-05.** "Match any" also ORs the starting universe (Active, Direct, Growth). The result grows from 1,825 to **27,052** funds, including Regular and IDCW plans.
- **F-06.** The default sort is Score, high to low, across all categories. The score is a category percentile. Row 2 is *SBI Medium to Long Term Fund* (score 97, CAGR 6.53%, Sharpe 0.15), above equity funds with far higher return. Debt and sectoral funds fill the top of the list.

*Judgment.* Compared with the references, the table lacks the "Chart (3Y)" sparkline column and the Preset / Custom / My screens tabs. Fund names are cut at about 200 px while the column has room. The 140-option formula field list shows internal ids.

### 3.3 Fund intelligence (`fund-*-desktop-light.png`, `m-fund-*.png`)

This is the strongest screen. It is the closest to Owner ref A, panel 2.

**Overview.** Three plain-language evidence cards (growth, downside today, last year). A score card with three equal parts and peer counts. Six key metrics, each against the category median. A "Growth of ₹10,000" chart. A rolling 3Y distribution. Fund essentials with Planned markers for expense ratio, AUM and benchmark.

**Performance.** A trailing-returns table, calendar and financial-year bars with hatched part years, rolling 1Y and 3Y, a monthly heat table.

**Risk.** Eight risk tiles, an underwater chart with the current fall and the longest time under a peak, the five deepest falls, time to recover, and capture in twelve market windows.

**Peers and rankings.** Percentile history, rank on nine measures, direct against regular (the 10-year wealth gap is stated), near-duplicates.

**Holdings.** Four Planned cards with their dependency named.

**Data and profile.** Source mix by date range (Tigzig to 31 Mar 2023, AMFI after), gap and jump counts, caveats.

**Verified correct.**

- 1Y −5.69%, 3Y 12.20%, 5Y 10.58% and NAV ₹89.41 (−0.60%) match Tickertape's public page for the same fund.
- Score 97.78 = mean(93.3, 100, 100), as the API states.
- Charts: hover shows a crosshair and a tooltip for both series. Keyboard arrows move the tooltip (verified). Every chart has a data table.

**Gaps.**

- **F-07.** Risk shows "Worst month −30.9%". The Performance heat table shows the worst *calendar* month, Mar 2020, at −19.6%. The API field `worst_1m` is a rolling one-month window, not a calendar month. Risk also shows "Worst year (rolling) −21.5%" while the rolling 1Y chart says −21.3%. Two near-equal numbers with near-equal labels and different definitions.
- **F-11.** In the trailing-returns table the category median and percentile are blank for 1M, 3M, 6M, YTD, 10Y and since-first. No reason is shown. Doc 08 says a missing value shows its reason.
- **F-17.** Grid rows stretch short cards. The score card leaves about 180 px of empty space under the key metrics. The near-duplicates card and the rank-history card are mostly empty.
- *Judgment.* The growth chart starts its value axis at ₹0, so the first four years look flat. It compares with a *large-cap* proxy while the fund is flexi-cap. The reference compares with the category and the benchmark. There is no zoom, no brush, no mark for March 2020, and no category band.
- *Judgment.* The Risk tab's "Through market falls and recoveries" is a 12-row table. It is accurate, but a chart would tell the story at a glance.

### 3.4 Analytics studio (`studio-*-desktop.png`, `studio-backtest-result.png`)

**Good.** Seven modes with clean tabs. The rolling chart overlays three funds and a statistics table. The hold-out backtest keeps in-sample (Oct 2019 to Dec 2023: top-5 23.5% a year against a 18.7% median) and out-of-sample (Jan 2024 to Aug 2026: 7.5% against 8.4%) in separate cards, with a "Limits of this test" list. It is honest.

**Defects.**

- **F-01 (P1).** The *Market regimes* chart is broken. The twelve alternating crash, correction and recovery windows render as one dark olive block from 2017 to Jan 2025, then two pale bands. The legend promises red, brown and green. The same defect shows in every theme (`studio-regimes-desktop.png`, `theme-monsoon-dark-regimes.png`, `m-studio-regimes.png`).
- **F-02 (P1).** The *Risk-return* map mislabels its axes (section 5).
- **F-18 (P2).** The backtest verdict is not written. Out-of-sample, the top-5 *under-performed* the median (7.5% against 8.4%). The page shows both numbers and says nothing. A beginner will not draw the conclusion.
- **F-19 (P2).** The backtest chart plots monthly returns as a smoothed line. The two lines lie on top of each other. A cumulative-growth chart would show the story. The caption says "dashed band"; the band is not dashed.
- The studio opens empty (see 4.1 and U-01).
- *Judgment.* The risk-return map has no frontier line, no hover label on a dot in the screenshot, and no fund names near the dots.

### 3.5 Comparison (`compare-3funds-desktop.png`, `compare-3funds-mobile.png`)

**Good.** Up to five funds. A common start date with an explicit banner. Rebased growth. Aligned metrics in five groups with a mark on the strongest value in each row. A correlation matrix with day counts, labelled "does not measure shared holdings". Average pairwise correlation 0.76. I checked the 3Y percentile (62.9) against the fund page (63): consistent.

**Gaps.** *Judgment.* There is one chart. The brief asks for synchronised periods and visual trade-offs. There is no 1Y / 3Y / 5Y selector, no drawdown overlay, no rolling-return overlay and no risk-return picture for the chosen funds.

### 3.6 Investment lab (`simulate-sip-result.png`)

**Good.** SIP, lump sum, SWP and STP on real NAVs. Summary tiles. A "how the money moved" chart. Tax by financial year with cautions. A "Did the start month matter?" histogram across 84 start months (median XIRR 20.9%, worst −6.7%, best 41.4%). Lakh formatting in the axes.

**Independent check (verified).** I rebuilt a SIP of ₹10,000 on day 1 of each month, 1 Oct 2021 to 23 Oct 2026, from the raw NAV series. My result: 61 instalments, value ₹7,98,318, XIRR 10.62%. The app: ₹7,98,278, XIRR 10.62%. The ₹40 gap (0.005%) matches stamp duty, which the app models and I did not.

**Defects.**

- **F-12 (P2).** The SWP form opens with an initial investment of ₹10,000 and a ₹5,000 monthly withdrawal. The default scenario ends after three withdrawals with a value of ₹0 and an XIRR of 23.82%.
- *Judgment.* Inputs are plain number boxes. The references use sliders with a live projection. The lab opens empty (see 4.1).

### 3.7 Workspace (`workspace-*.png`)

Tested through the API and the UI with isolated records named `ZZ-AUDIT-*`. All test records were archived afterwards. They remain in the database as archived rows, because the API has no delete.

| Test | Result |
|---|---|
| PUT without `If-Match` | 428 |
| PUT with the current version | 200, version +1 |
| PUT with a stale version | 412, "The record is at version 2" |
| PUT with a garbage `If-Match` | 412 |
| Six parallel PUTs with the same version | one 200, five 412, final version 2 |
| 3 MB body | 422 |
| Unknown kind, empty name | 422 with a clear detail |
| UI: network failure on save | draft kept, Save stays enabled |
| UI: another window saved first | warning, draft kept, "Load the latest version" works, next save gives version 3 |

**Defects.**

- **F-10 (P2).** A failed save shows "Could not load this view. Failed to fetch." The words say *load*, not *save*.
- **F-10b (P2).** "Load the latest version" replaces the draft with no copy and no diff. The warning says "Your text is still here", and one click removes it.
- The 412 body names the current version only. The client must fetch the record again. That works, but it is one call more than the module comment ("so the client can merge") suggests.

I did not star a fund in the live store. That would change the owner's real "My watchlist". The write path is covered by the API checks above.

### 3.8 Portfolio, AI research and Alerts

*Judgment.* Presented well. Each page says what it will do, what it needs, and gives "works now" shortcuts. The Hindi and Hinglish examples on the AI page are a nice touch. Planned items carry no active control. I count none of this as a defect. Opportunity: a locked preview of the portfolio donut (as in Owner ref B) would make the page feel like a promise, not a text block.

### 3.9 Mobile (`m-*.png`)

**Good.** Bottom bar with a More sheet, a filter sheet, card results, no sideways page scroll at 390 px (verified on 14 route captures: scrollWidth 390).

**Gaps.**

- The fund page spends the first screen on Back, four action buttons, the title, the price and the tabs. The score is below the fold. Owner ref A (panel 3) puts the score and a fixed "Add to watchlist / Compare" bar on the first screen.
- **F-14.** The compare tray floats above the bottom bar on every route and covers about 60 px of content.
- Many tap targets are 32 to 36 px high (about 147 on the phone screener). They pass WCAG 2.2 AA (24 px) but fall short of 44 px.
- The phone screener puts a title, a count, Save, Export and the presets above the first result. The first row starts at about y = 630.

---

## 4. Cross-cutting findings

### 4.1 First-visit story

The Studio, the Lab and Compare open empty and wait for a fund (`studio-desktop-light.png`, `simulate-desktop-light.png`). The strongest charts in the product are invisible until the visitor does work. The references show every tool already filled with Parag Parikh. *Judgment, high confidence:* this is the biggest single reason the build feels like a toolkit and not a product.

### 4.2 Context across screens

*Verified.* The URL carries fund codes and views, so Back and shared links work. There is no shared "current fund" or "current period". A fund opened in the Screener must be re-chosen in the Studio unless the user follows a link. *Reported:* only the CSV export pins its snapshot. All pages I opened showed snapshot 2801, so I could not test a mixed-revision case. I could not force a new revision without writing to the data store.

### 4.3 Explanation

*Good.* Info icons on metrics, a score drawer, "how this is calculated" text, a per-chart data table, and a footer with the snapshot on every page.

*Gap.* The page explains *what* a metric is more than *what it means for you*. For a beginner, "Sortino 0.84, rank 3 of 36" needs one line: "Gains came with few bad days." The three evidence cards at the top of the fund page do this well. The rest of the page does not.

### 4.4 Search

**F-04 (P1).** Verified in the top bar search:

| Query | Result |
|---|---|
| `parag` | 8 rows, alphabetical: Arbitrage, Conservative Hybrid, Dynamic Asset... The flexi-cap fund is not among them |
| `parag parikh flexi` | 4 rows: Direct Growth, Direct IDCW, Regular Growth, Regular IDCW |
| `ppfas` | 0 rows |
| `sbi smallcap` | 0 rows (the fund is "SBI Small Cap Fund") |
| `122639`, `INF879O01027` | correct single row |

Search is a substring match, alphabetical, capped at 8, and it lists IDCW and Regular plans beside Direct Growth. It has no fuzzy match and no AMC aliases.

### 4.5 Performance (local, uncompressed)

Fund tabs load in about 0.6 s. The Peers tab takes 2.0 s. Studio modes take about 2.1 s. `/mf` loads 1.1 MB of JavaScript (the shared main bundle is 0.73 MB of it). A fund page makes 35 requests. Zero console errors and zero 4xx or 5xx responses on every route I tested.

### 4.6 Accessibility beyond axe (verified)

Skip link is the first Tab stop, and it shows a 3 px focus outline. `/` focuses the search. Charts are focusable (`role=application`, `tabindex=0`) and arrow keys move the tooltip. Every chart has an `aria-label` and a data table. A `prefers-reduced-motion` rule exists. There are 206 text nodes under 12 px (axis ticks and captions). There are two navigation landmarks with the same name ("Mutual fund research"); one is the phone bar. I did not test with a screen reader.

### 4.7 Theme architecture

**Verified.**

- No hex, `rgb()` or `hsl()` value exists under `web/src/features/mf` outside `theme/themes.ts` (and its test). One literal remains: `border-black/10` on the swatch dots in `MfShell.tsx:130`.
- No Tailwind default-palette colour class is used in MF components.
- The Appearance panel builds its list from `Object.keys(THEMES)` (`MfShell.tsx:125`). The palette choice is stored in `localStorage` (`mf-palette`).
- I switched all four combinations (Paper & ink and Monsoon, each light and dark) and captured Discover, Fund performance, Regimes and Compare (`theme-*.png`). Charts, the hero illustration, tints and focus colours all follow. Dark mode keeps contrast and heat-cell legibility.
- I did not add a third theme. Adding one is an entry in `THEMES` by code review, and the theme-completeness test enforces every role.

**Gap (F-13).** The Appearance panel prints developer text to end users: "Themes live in one file, src/features/mf/theme/themes.ts."

### 4.8 Momentum25 isolation

`/` loads with zero console errors. The MF shell does not mount on Momentum25 routes. I did not re-run the 236-test regression.

---

## 5. Functional defect register

Severity. **P0:** a wrong financial number or lost data. **P1:** a broken or misleading signature feature, or a discovery failure. **P2:** a label, edge state or polish defect. **No P0 was found.**

### P1

| ID | Defect | Reproduce | Code |
|---|---|---|---|
| F-01 | Market regimes bands are unreadable: twelve windows draw as one block | Open `/mf/studio?mode=regimes&code=122639`. The legend shows crash, correction and recovery in three colours. The plot shows one olive block, then two pale bands | `routes/studio.tsx:316,328`; `components/charts.tsx:200`. *Likely cause, not confirmed:* each band's `x1` and `x2` is an exact date string on a category axis, and the series is thinned twice (800, then 700 points). A window edge missing from the thinned data does not resolve |
| F-02 | Value-axis labels are rounded copies of non-round tick positions | Open `/mf/studio?mode=frontier&code=122639`. Gridlines labelled 11%, 14%, 17% sit at 11.4%, 14.4%, 17.4% (computed from circle positions against API `vol_3y` 9.92% to 17.70%). Labels may be off by up to 0.5 percentage point. Parag Parikh plots at 9.5% for a true 9.92%. The Y axis shows the same pattern. Histogram axes read −19%, 11%, 41%, 71%, 98% (rolling 1Y) and 2%, 11%, 20%, 29%, 37% (rolling 3Y) | `components/charts.tsx:310` (`PAD` domain functions give a non-round domain), `:240` (`dataMin`/`dataMax`), `:340-341` |
| F-03 | Watchlist and compare buttons are off-screen in the default results at 1440 px | Open `/mf/screen`. The first row's buttons are at x = 1383 and 1425 inside a scroller of 823 px against 906 px of content | `components/screener/ResultsTable.tsx` |
| F-04 | Fund search hides the flagship fund and finds nothing for common spellings | Table in 4.4 | `components/FundSearch.tsx`; API `GET /funds?q=` |
| F-05 | "Match any" ORs the starting universe | Open `/mf/screen`. Click "Match any". Count goes 1,825 to 27,052 | `view-spec.ts` (`UNIVERSE`, `filterOf`); `components/screener/ConditionEditor.tsx` |
| F-06 | Default sort ranks a category-relative score across all categories | Open `/mf/screen`. Row 2 is a medium-to-long debt fund with Sharpe 0.15 | `view-spec.ts` (`defaultView`: sort by `score`) |

### P2

| ID | Defect | Reproduce or evidence |
|---|---|---|
| F-07 | "Worst month" and "Worst year (rolling)" labels do not match the numbers beside them | Fund 122639 Risk tab: −30.9% against −19.6% (Mar 2020 calendar month). −21.5% against −21.3% (rolling 1Y chart). API: `worst_1m` −0.3093, `worst_1y` −0.2145, `rolling_1y_min` −0.2131 |
| F-08 | Three peer counts for one category, never reconciled | Flexi Cap Direct Growth: 36 ("funds ranked", Discover), 46 (screener), 31 (score rank). API `score_cat_count` 31, `cagr_3y_cat_count` 36 |
| F-09 | A bad formula enters the URL and the columns, replaces the whole result with "The request was not accepted. formulas.bad_formula: the expression does not parse", and offers only "Try again" | In the Formula drawer enter `cagr_3y / (` and add it |
| F-10 | A failed save reads "Could not load this view"; "Load the latest version" drops the draft with no copy | `/mf/workspace?tab=notes`, block PUT, then edit and save |
| F-11 | Blank category median and percentile cells with no reason | Fund Performance tab, trailing returns |
| F-12 | SWP defaults exhaust the corpus in three months | `/mf/simulate?kind=swp&code=122639` and run |
| F-13 | Developer text shown in the Appearance panel | Sidebar, Appearance |
| F-14 | The compare tray floats on every route and covers content on phones | Visit `/mf/compare?code=...`, then any route |
| F-15 | Time-axis labels are irregular and the first label does not match the series start | Growth chart: first tick "Nov 16" for a series that starts 17 Oct 2016 |
| F-16 | Formula field picker is a flat 140-item list with ids and capital-letter codes ("RET RISK 3Y category rank (ret_risk_3y_cat_rank)") | Formula drawer |
| F-17 | Stretched grid cards leave empty space | Fund Overview and Peers tabs |
| F-18 | The backtest shows an out-of-sample loss to the median but never says so | Studio, Selection backtest, run with defaults |
| F-19 | Backtest chart smooths monthly returns and its caption mentions a dashed band that is solid | Same |

---

## 6. Usability and visual improvement register

These are judgments, not defects. Ranked by effect on the original ambition.

| ID | Improvement | Why it matters |
|---|---|---|
| U-01 | Fill the Studio, Lab and Compare on first visit. Use the last fund the visitor opened, or a named example fund | Largest effect on "beautiful and insight-first" |
| U-02 | Add one plain-language verdict line to every fund, built from fields the API already returns: "In the March 2020 fall it lost 31% against 35.5% for the market proxy, and recovered in 105 days" | Makes the product legible to a first-time investor. Tickertape locks its score behind Pro |
| U-03 | Give charts brush-zoom, a linked crosshair across charts on one page, marks for regime windows, a log toggle, and a category band behind the fund line | The gap between "functional" and "TradingView-like" |
| U-04 | Start the growth chart at the first value, not ₹0, and compare with the fund's own category median as well as the proxy | Matches the reference and fixes a flat first half |
| U-05 | Add sparklines to category cards, screener rows and "Ideas to research". The `Sparkline` component exists (`charts.tsx:418`) | The references use them everywhere |
| U-06 | Show fund house marks or monograms in lists | Owner ref A and B both show them |
| U-07 | Put search in the desktop hero | Matches both references |
| U-08 | A shared research bar: fund set, period, snapshot. It travels between Screener, Fund, Studio, Compare and Lab | Delivers the "context preserved" goal |
| U-09 | Sliders with a live preview in the Lab | Owner ref B (SIP calculator) |
| U-10 | A cumulative-growth view for the backtest, plus a sentence for the verdict | Turns a table into a story |
| U-11 | Make the nested filter group visible: expand "Any of 2 conditions" into its rows, and let the user edit it | Known gap in doc 08; I confirmed a nested group runs correctly (280 funds) but shows as an opaque chip |
| U-12 | Frontier line and fund names on the risk-return map | Makes the chart readable without the side table |
| U-13 | On the phone fund page, show the score and a fixed Add / Compare bar on the first screen | Owner ref A, panel 3 |
| U-14 | "Why shown" on each Discover idea: one line naming the rule | Honest personalisation without a quiz |
| U-15 | A locked preview of Portfolio (donut, overlap) | Turns a Planned page into a promise |
| U-16 | Raise phone tap targets to 44 px on chips and row actions | Thumb use |

---

## 7. Competitive assessment against Tickertape

**Method.** I fetched Tickertape's public page for Parag Parikh Flexi Cap Direct Growth and its public screener and help pages. I did not use a logged-in account. Pro content was not visible. Claims about Tickertape rest on the public page and may miss gated features. Sources: [Tickertape MF screener](https://www.tickertape.in/screener/mutual-fund), [fund page](https://www.tickertape.in/mutualfunds/parag-parikh-flexi-cap-fund-direct-plan-growth-M_PARO), [screener guide](https://www.tickertape.in/blog/how-to-use-tickertape-mutual-fund-screener/).

**Cross-check.** The two products agree on 1Y (−5.69%), 3Y (12.20%), 5Y (10.58%) and NAV (₹89.41, −0.60%). They differ on risk. Tickertape shows a standard deviation of 9.30 and a Sharpe of −1.08. Wickstreet shows a volatility of 9.92% and a Sharpe of 0.60. The difference is method (risk-free rate, annualisation). Wickstreet states its method (RBI 91-day T-bill, 3Y average 6.26%). Tickertape's page did not.

| Area | Verdict | Evidence |
|---|---|---|
| Screener depth | **Wickstreet superior** | 160 fields, formulas, any/all, saved views, exclusion counts, CSV with provenance. Tickertape lists 50+ filters, some Pro-only |
| Risk analytics | **Wickstreet superior** | Underwater chart, deepest falls, time to recover, capture in 12 windows, rolling 1Y/3Y/5Y. Tickertape shows summary ratios |
| Honesty and provenance | **Wickstreet superior** | Missing reasons, proxy labels, source mix by date, snapshot on every page |
| Simulation | **Wickstreet superior** | SIP, SWP, STP, lump sum, XIRR, tax by financial year, start-month histogram. Tickertape's page has a SIP chart mode and no calculator |
| Backtest | **Wickstreet superior** | Hold-out split shown. No Tickertape equivalent on the public page |
| Score | **Parity, with an edge** | Both have a score. Tickertape locks the full score behind Pro. Wickstreet shows its three parts and peer counts. The Wickstreet score is a category percentile |
| Compare | **Parity** | Wickstreet compares up to five funds with correlation. Tickertape compares peers and any instrument on a chart |
| Visual polish and chart interaction | **Parity at best** | Both are clean. Wickstreet's regimes chart is broken. Neither offers rich zoom in my capture |
| Search | **Tickertape better (not tested on its side)** | Wickstreet's search fails on common spellings (F-04). Tickertape's was not tested |
| Holdings, sector, asset allocation | **Tickertape better** | Wickstreet shows Planned (needs E4) |
| Expense ratio, AUM, exit load, minimum investment, benchmark | **Tickertape better** | Wickstreet shows Planned (needs E1, E3) |
| Manager, AMC profile, opinions | **Tickertape better** | Not in Wickstreet scope yet |
| Portfolio import | **Not comparable yet** | Wickstreet: Planned (Slice 6) |

**Decisive-advantage candidates** (each uses data Wickstreet already has):

1. **The verdict line (U-02).** A free, plain-language reading of the evidence on every fund.
2. **"What would have happened?" on first screen.** A pre-filled SIP, with the start-month histogram as the hero.
3. **Regime story.** One interactive chart of falls and recoveries with the fund's capture shown on hover (fix F-01 first).
4. **Honest backtest verdict (F-18).** "This signal worked in-sample and did not out-of-sample." No competitor says this.
5. **Context that travels (U-08).**

---

## 8. Prioritised remediation roadmap

Each item has an acceptance test that a person can run.

### Wave 1: fix trust and discovery (about one week of work)

| # | Work | Acceptance criteria |
|---|---|---|
| 1 | Fix the regimes chart (F-01). Draw bands on a numeric time axis | Twelve distinct bands visible for fund 122639. Colours match the legend. Band edges fall within one trading day of the API window dates. A Playwright test counts twelve band elements |
| 2 | Fix chart axes (F-02). Use round ticks, or label the real tick value | For the risk-return map: every gridline label equals its true value to the shown precision. A unit test maps a known point (vol 9.92%, CAGR 12.18%) to the labelled grid within 0.05 percentage point. Histogram ticks are round numbers |
| 3 | Show row actions without sideways scroll (F-03) | At 1440 px with the default columns, watchlist and compare are fully visible without scrolling. Test at 1280, 1440, 1920 px |
| 4 | Rebuild fund search (F-04) | `parag` lists Parag Parikh Flexi Cap Direct Growth first. `ppfas` and `sbi smallcap` return the right funds. Direct Growth plans rank above IDCW and Regular. Ten queries from a fixed list return the expected fund in the top 3 |
| 5 | Protect the "Match any" universe (F-05) | Switching to Match any keeps Active, Direct and Growth as fixed gates. The count never exceeds the ALL count of the gates alone. A test covers it |
| 6 | Make the default screen category-aware (F-06) | The default view either sorts within one chosen category or sorts by an absolute measure. The top 10 of the default view contain no fund with 3Y CAGR below its category median |

### Wave 2: correct labels and edge states (about three days)

| # | Work | Acceptance criteria |
|---|---|---|
| 7 | Rename or redefine rolling-window measures (F-07) | "Worst month" says "Worst 1-month window". The Performance and Risk tabs use one definition for worst year. A test compares the two tabs for fund 122639 |
| 8 | Reconcile peer counts (F-08) | Each count has a visible label that says what it counts. The tile, the screener and the score show the same number or a one-line reason |
| 9 | Validate formulas before they enter the view (F-09) | A bad expression shows an inline message in the drawer, is not added to the URL, and the result keeps its last good state |
| 10 | Fix save and conflict copy (F-10) | Failed save says "Could not save". Conflict offers "Copy my text" before "Load the latest version" |
| 11 | Show a reason in blank cells (F-11) | No blank metric cell on the fund page. Each shows a reason or a dash with a tooltip |
| 12 | Sensible lab defaults (F-12) | SWP defaults produce a result that lasts at least 5 years on 122639 |
| 13 | Remove developer text (F-13), tidy the tray (F-14), round time ticks (F-15), friendly field names (F-16) | Text search finds no source path in the UI. Tray is one line and does not cover content. Time ticks fall on month or year starts |

### Wave 3: make it category-leading (about three to four weeks)

| # | Work | Acceptance criteria |
|---|---|---|
| 14 | Pre-filled Studio, Lab and Compare (U-01) | Opening each with no fund shows a chart within 2 s. A Playwright test asserts a chart on first paint |
| 15 | Fund verdict line (U-02) | Every fund page shows one sentence with three numbers, each linked to its chart. A test checks each number against the API |
| 16 | Chart interaction layer (U-03, U-04, U-12) | Brush-zoom, a linked crosshair and regime marks on the performance and risk charts. Growth chart starts at the first value and shows the category median |
| 17 | Shared research bar (U-08) | A fund chosen in one tool is the default in all tools. Period and snapshot shown. A journey test: Screener, Fund, Studio, Compare with no re-selection |
| 18 | Sparklines, logos, hero search (U-05, U-06, U-07) | Category cards, screener rows and ideas show a 3Y sparkline. Visual diff against owner ref A panel 1 reviewed by the owner |
| 19 | Backtest verdict and growth view (F-18, U-10) | A sentence states in-sample and out-of-sample results in plain words. A cumulative chart replaces the smoothed monthly line |
| 20 | Phone fund page and targets (U-13, U-16) | Score and a fixed action bar visible at 390 x 844 without scrolling. Chips and row actions at least 44 px |
| 21 | Nested group editor (U-11) | A saved nested group can be opened, edited and re-run in the UI |

### Wave 4: data (already in the plan)

E1 (expense ratio, AUM, exit load), E3 (licensed TRI benchmark) and E4 (holdings) move the fund page from "best analytics" to "complete". They need the rights decisions in doc 22. This wave is outside the UI team's control.

---

## 9. What I did not verify

- Authenticated Tickertape, and any Pro content.
- A real phone, a screen reader, or a usability test with young investors.
- A mixed-revision case. All pages showed snapshot 2801.
- A third theme added in code. I verified the mechanism by reading it and by switching the two shipped themes.
- The fund and screener star flows against the live workspace store. I avoided changing the owner's real watchlist.
- A slow network, and the 1,825-row paging limit.
- The regimes root cause. The reading in F-01 is a hypothesis from the source and the rendering.

## 10. Evidence index

| Topic | Files in `screens/` |
|---|---|
| Discover | `d01-discover-desktop-light.png`, `d01-discover-desktop-full.png`, `m-discover-viewport.png`, `search-parag.png` |
| Screener | `screen-desktop-light.png`, `screen-preset-consistent-desktop.png`, `screen-formula-open.png`, `screen-formula-bad-viewport.png`, `screen-formula-good.png`, `screen-match-any-trap.png`, `screen-nested-group.png`, `journey-category-to-screen.png`, `m-screen-viewport.png`, `m-screen-filter-sheet.png` |
| Fund | `fund-{overview,performance,risk,peers,holdings,profile}-{desktop,mobile}-light.png`, `fund-performance-hover-growth.png`, `m-fund-viewport.png`, `m-fund-performance-chart.png` |
| Studio | `studio-{rolling,drawdown,ranks,frontier,transitions,regimes,backtest}-desktop.png`, `studio-backtest-result.png`, `studio-frontier-single.png`, `m-studio-regimes.png` |
| Compare, Lab | `compare-3funds-{desktop,mobile}.png`, `simulate-{desktop,sip-result,swp-result}.png` |
| Workspace | `workspace-desktop-light.png`, `workspace-notes-before.png`, `workspace-save-failed.png`, `workspace-conflict.png` |
| Themes | `appearance-panel.png`, `theme-{paper,monsoon}-{light,dark}-{discover,fund,regimes,compare}.png` |
| References | `refs/owner-ref-a-app-screens.png`, `refs/owner-ref-b-visual-proposal.png` |
