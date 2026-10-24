# REVIEW-1: independent review of the premium-2026-10-24 milestone

Reviewer: independent, 2026-10-24. Wickstreet at localhost:8000, workspace API mocked in memory. Tickertape public pages, same day.

## Verdict

The fund page overview is clearly better. The dossier answers TER, AUM, benchmark, manager and holdings date on one desktop screen, each with a date (except managers), and the pass is better than Tickertape's page for dated facts. The rest of the app barely changed (Screener, Compare, Studio, Lab, Portfolio are the same layouts with new greens and oranges), the phone fund page does not deliver the dossier on its first screen, and the screener table now clips a column. This is not yet "visually exceptional" or "better than Tickertape" overall.

## Ranked weaknesses

| # | Screen | Evidence | Why it matters to an investor | Fix |
|---|---|---|---|---|
| 1 | Phone fund page (m-fund-light.png, live 390x844) | First screen shows header, score and the top third of the chart. A fixed action bar (719-780px) and tab bar (779-844px) cover 126px of 844. TER and AUM sit at y=1192-1286, managers y=1468, holdings date y=1595. Measured: 0 of 6 facts on screen 1; TER, AUM, benchmark, riskometer after 1 scroll; managers and holdings date after 2 scrolls. | Most users are on a phone. The "first-screen dossier" is a desktop result only. | Put a 2x2 facts strip (TER, AUM, benchmark, holdings date) above the chart on phone. Move the chart below it. Drop the second sticky bar or merge it into the tab bar. |
| 2 | Fund page, Key facts vs chart | Key facts says Benchmark "Nifty 500 TRI, +3.1% a year over it". The chart plots "Large-cap proxy", a median of large-cap funds, for a flexi-cap fund. The "not the scheme benchmark" note is a 12px footnote below the fold on desktop. | The investor reads "benchmark" next to a chart that shows a different line. Two different comparisons on one screen. | Label the chart line "Large-cap fund median (proxy)" in the legend. Add "Chart does not show Nifty 500 TRI" in the Benchmark card until the TRI is licensed. |
| 3 | Screener table (d-screener, live after "Show Return 1Y") | Columns go from 6 to 7. Table scroll width is 1208px in an 838px box. Header reads "Max dra" and its values are hidden behind the star/compare column. No scroll cue. | The metric the investor just asked for works. A different metric silently disappears. A silent number loss is the worst failure in a research tool. | Sticky fund-name column, a visible horizontal scroll shadow, and drop the "3Y NAV" sparkline column when width is short. Or cap visible columns by width. |
| 4 | Screener, desktop and phone (before vs after) | The two desktop screenshots are almost identical except pill and badge colour. Fund names wrap to two lines and truncate ("Flexi Cap Fund Dire..."). Left list truncates "Max drawdown...". Native grey selects for Category and Sort. Phone: "Filters (4)" sits in a tall empty card; "Score category r..." truncates; one fund fills a whole screen. | The owner asked for lively and exceptional. The screener is the main work surface and it looks the same as before. | Single-line fund name with AMC under it, tabular numbers right-aligned, styled selects, compact 2-line phone rows with one metric pair, pinned filter chips on phone. |
| 5 | Screener, "keep only one fund house" | Path: open "Fund" group (1), Filter by Fund house (2), click Find box (3), type 5 letters, tick (4). Typing "parag" returns nothing. Only "ppfas" works. The list holds 112 values with duplicates, for example "360 ONE Asset Management Limited" and "360 ONE Mutual Fund". The Find box is clipped at the right edge; long names are cut. | An investor searches by brand. Duplicate AMC names can hide funds from a one-house filter. | Add brand aliases to the search (Parag Parikh = PPFAS). Merge duplicate AMC names. Show fund count per AMC. Auto-focus the Find box when the checklist opens. Fix the clip. |
| 6 | Screener, range input (scr-range-open) | Placeholders are cut: "No minir", "No maxi". Helper text says "Snapshot values run from -98.9% to 93.6%". That is the whole universe, while the current set is 46 Flexi Cap funds. There is no slider or distribution. | The investor cannot see how many funds a threshold removes before typing. The range text does not describe the set on screen. | Widen the inputs or stack them. Show min and max of the current result set. Add a small histogram or slider. Show "37 left" live. |
| 7 | Fund page, asset bar | Equity 85.4% + Debt 3.9% + Cash 3.9% = 93.2%. The remaining 6.8% is an unlabelled grey stub. Tickertape lists REITs and InvITs at 6.27%. | A bar that does not sum to 100% with no label reads as a defect. | Add an "Other 6.8%" segment, labelled, with its name when known. |
| 8 | Fund page, dates and counts | Managers card says "Start dates as filed", which is no as-of date. It lists 6 managers; Tickertape lists 4. Launch date 13 May 2013 vs Tickertape 24 May 2013. The "Max" chart button starts 17 Oct 2016, 3 years after launch; the reason is in a small footer line. | The brief was "every figure dated". Three differences an investor can see with one other tab open. | Add an AMFI/AMC as-of date to the managers card. Say which date is launch and which is allotment. Rename "Max" to "Since 2016" or add the reason beside the chart. |
| 9 | Fund page, Sharpe and volatility | Wickstreet Sharpe 3Y 0.61, volatility 9.92%. Tickertape Sharpe -1.14, volatility 9.30. The sign differs. The card does not state risk-free rate or window. | A cross-check on a second site looks like an error. | Print the method beside the number: "3Y, risk-free 5.73% (91-day T-bill), daily". |
| 10 | Phone header, all routes | Two icons: "Use dark theme" and "Appearance settings". In dark mode both draw as a sun (m-fund-dark.png). | The user cannot tell which one does what. | Keep one theme toggle. Put the rest under More. |
| 11 | Portfolio (d-portfolio-light.png, m-portfolio-dark.png) | The native grey "Choose File" button is unstyled in both themes. The label row and the Password row are misaligned by about 35px. The disabled Preview button is low contrast. About 400px of empty space below the empty-state box. | It is the page that holds the investor's own money, and it looks the least finished. | Styled drop zone for the CAS file, aligned form grid, a clear disabled state with a reason, and a sample-output preview in the empty space. |
| 12 | Discover (d-discover, m-discover) | Hero right half is an empty tint behind the market card. "Ideas to research" chips are cut ("Shallow-drawdown hyb"). First "Calm equity" idea is a healthcare sector fund with score "-". "Your research" has a block of empty space. Phone: decorative hills sit behind "40,214 plan options" and cut its legibility; search placeholder is cut ("...or an AMF"). | First impression for new users; the first idea shown contradicts the "calm equity" promise. | Remove unscored funds from idea lists. Make chip row wrap or show a fade and arrow. Keep text off the art on phone. |
| 13 | Compare, Studio, Lab | Only colours changed. Compare shows the chart first; no TER, AUM, benchmark or holdings date in the first screen. Chart y-axis starts at Rs 0, so about 40% of the plot is empty. Phone Compare: two stacked buttons, two stacked chips, chart starts after about 1 scroll. | The comparison that matters (cost, size, benchmark) is below the fold. Lines for the two funds overlap for 3 of 10 years. | Add a facts table above the chart. Start the y-axis at the data minimum or use log scale by default. On phone use a horizontal chip row. |
| 14 | Fund chart, market-fall bands | Seven tan bands and one pink band are the strongest marks on the light chart. In dark mode they turn muddy olive-brown (d-fund-dark.png). They are on by default. | Decoration outweighs the data line. The dark bands look dirty rather than premium. | Default off or 8% opacity; use one hue for all bands; legend shows the date range on hover. |
| 15 | Phone and desktop small text | Dates and sub-labels are 11px (contrast 5.9:1 light, 7.4:1 dark, which passes). The date line is the proof for every figure. | The dated fact is the product's promise, and it is the smallest text on the page. | Raise to 12-13px on phone, keep contrast. |

## Measured task numbers

### B. Fund research (fund 122639)

Desktop 1440x1000, no scroll, no tab change:

| Item | Visible | Date shown |
|---|---|---|
| Expense ratio 0.69% | yes, y=557-635 | AMFI as of 1 Oct 2026 |
| AUM Rs 1,46,988 Cr | yes | AMFI as of 22 Oct 2026 |
| Benchmark Nifty 500 TRI | yes, y=671-770 | AMFI report of 22 Oct 2026 |
| Manager Rajeev Thakkar (6) | yes, y=801-923 | none ("start dates as filed") |
| Holdings date | yes, "30 Sep 2026" at y=878-911 | yes |
| Main chart | yes, y=496-980 | 17 Oct 2016 to 23 Oct 2026 |

Everything fits above y=1000. The proxy footnote and "Show data table" are below the fold.

Phone 390x844: 0 of 6 facts on screen 1. 1 scroll (about 650px) shows the whole chart, TER, AUM, riskometer and benchmark. 2 scrolls show managers and the holdings date. Fixed bars use 126px.

Spot checks against Tickertape (23-24 Oct 2026):

| Number | Wickstreet | Tickertape | Verdict |
|---|---|---|---|
| 1Y return | -6.68% (screener), -6.7% (page) | -6.68% | match |
| TER | 0.69% (1 Oct) | 0.69% (23 Oct) | match |
| AUM | Rs 1,46,988 Cr (22 Oct) | Rs 1,45,070.50 Cr (23 Oct) | 1.3% apart; different as-of dates |
| Top holding HDFC Bank | 7.8% (30 Sep) | 7.75% (23 Oct) | match |
| Equity share | 85.4% | 85.40% | match |
| NAV | Rs 88.9695 (23 Oct) | Rs 88.97 | match |
| Launch date | 13 May 2013 | 24 May 2013 | differ |
| Managers | 6 | 4 listed | differ |
| Sharpe 3Y | 0.61 | -1.14 | differ; method not stated (item 9) |
| Volatility | 9.92% | 9.30 | differ; method not stated |

No figure on the page is missing its date except managers. Tickertape's own page shows the same fund with Cost "High" while its category TER is 1.64% and the fund's is 0.69%; Wickstreet's "cheaper than 95% of peers" is the more consistent statement.

### C. Screener

Wickstreet, "show 1Y return, keep funds above -10%":
- Click "Show Return 1Y": 1 click. The range opens inline, no dialog. Focus stays on the checkbox, not the input.
- Click the Minimum box and type "-10": 1 click + 3 keys.
- Total: 2 clicks + 3 keys. Result 46 -> 37 funds. Request: `ret_1y between [-0.1, null]`. Column visible; result updates within the debounce.
- Keyboard only: 29 Tab presses to the first checkbox (sidebar and header first), Space, 2 Tab to the Minimum box, 3 keys.
- Note: clicking "Filter" after "Show" closes the range that Show just opened. A user who clicks both ends up with nothing open.

Wickstreet, "keep only one fund house": 4 clicks + 5 keys (Fund group, Filter by Fund house, Find box, type "ppfas", tick). Result 1 fund (inside the Flexi Cap default). The word "parag" finds nothing.

Tickertape public screener (desktop, logged out, this session):
- Dismiss tour (1), Add Filter (2), Absolute Returns - 1Y (3), Done (4): a sign-up modal appeared. Escape closed it.
- Typing -10 into the low box worked (slider and box updated: "-10.00 to 91.00").
- The results table then turned blurred with "Sign up to apply all our free filters and view unlimited results". Count stayed 1,849.
- So the 1Y threshold task could not be completed logged out today: 4 clicks + 1 click in the box + 3 keys + Escape, then a gate. This differs from the 24 Oct LIVE_ASSESSMENT note that it worked ungated. Gate behaviour may vary by session.
- "AMC" exists under Scheme Info. I did not run it: Add Filter, Scheme Info, AMC, Done is already 4 clicks before choosing a name, so at least 5-6 clicks. Not measured.
- Forced steps: a tour dialog and a promo overlay on first load, a filter picker dialog, a Done button, a login gate.

### D. Accessibility smoke

- Key facts: 43 Tab presses from page load to the first card (or fewer after the "Skip to content" link, which exists). The 5 cards are real links, each reachable with one Tab. Focus ring: 3px solid, rgb(4,120,87) light and rgb(110,231,183) dark; clearly visible in the screenshot. Chart handles show a ring too.
- Screener range inputs: reachable by keyboard; ring is the same 3px outline plus a border colour change. Typed "-10" gave 37 funds. Inputs have aria-labels ("Minimum Return 1Y").
- Contrast of the 11px date text: 5.93:1 light, 7.39:1 dark.
- Not tested: screen reader output, reduced-motion, 200% zoom.

### Not done
- No writes, imports or uploads. Tickertape pages were not logged in.
- Phone Tickertape was not tested.
- Before/after screenshots for Studio and Lab were compared by eye for the dark and light palette only.
