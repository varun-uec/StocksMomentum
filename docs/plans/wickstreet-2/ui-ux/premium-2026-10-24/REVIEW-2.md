# REVIEW-2: second independent review of the premium-2026-10-24 milestone

Reviewer: independent, 2026-10-24. Live app at localhost:8000, workspace API mocked in memory (GET returns [], other methods return {}). No uploads, no deletes. Live captures (9 routes, 2 themes, 2 viewports) are in the scratchpad `r2/` folder. I did not re-run Tickertape this round; I did not re-check its numbers.

## Verdict

The fund page and Compare now answer the investor's first questions on desktop, and the phone fund page now shows all six key-fact values on screen 1. The rest is still not "visually exceptional": the screener is almost unchanged, the Compare answers fall below the first phone screen, the default Compare pair cannot show shared holdings, and the new phone facts strip hides its values from screen readers.

## A. REVIEW-1 ranks the ledger marks fixed

| Rank | Verdict | Evidence |
|---|---|---|
| 1 Phone fund facts | Partly | Live 390x844: TER, AUM, Risk, Benchmark, Manager, Portfolio date all sit at y=369-411 on screen 1 (was 0 of 6). Only one fixed bar remains (tab bar, 65 px). But the strip has no as-of dates; the first dated line is at y=1252 and the last (managers, holdings) at y=1653-1670, so dates need 2 scrolls. The chart shows about 77 px of plot above the tab bar, a sliver. The strip link has `aria-label="Key facts; go to their dates and sources"`, so a screen reader never hears the six values (axe `label-content-name-mismatch`). |
| 2 Proxy vs benchmark | Partly | Desktop legend reads "Large-cap proxy, not the benchmark" and the Benchmark card says the dashed line is a proxy. Phone legend reads only "Large-cap proxy"; the "not the benchmark" words are missing there. |
| 3 Screener clipped column | Partly | "More columns to the right" and a working Scroll button exist; Scroll reveals Consistency and Score category rank. Fund column is sticky. At 1440 the table is 1093 px in 838 px: the last header still reads "Co" and, after Show Return 1Y, "Max drawdc" (header clipped mid-word). The 3Y NAV sparkline slides under the sticky fund avatar when scrolled. |
| 6 Range inputs (part) | Partly | Placeholders now "Any". Text reads "The 46 funds shown run from −11.5% to 3.37%. All 7,887 plan options with a value run from −98.9% to 93.6%." After typing −10 it reads "The 37 funds shown run from −9.38%..." and the range is now the result, not what the threshold removes. No slider, no histogram, no "37 left" before typing. The filter bar also adds "32,327 exclusions because a value is missing", which is unexplained noise for a 46-fund view. |
| 7 Asset bar | Fixed | "Equity 85.4, Debt 3.9, Cash 3.9, Other 6.9" labelled (sums to 100.1 by rounding). |
| 8 Dates and counts | Partly | Overview managers card says "Scheme document of 24 Oct 2026" (that is today's date, which looks like a retrieval date, not a filing date). The Facts & costs managers card still says only "Start dates as filed", no date. Facts tab shows "7 managers in the SSD" while the same page lists 6. "Max" is now "All". Facts tab shows "Allotment date 24-May-2013" only; I found no "launch (NFO)" line. |
| 9 Sharpe method | Partly | Risk tab: "Sharpe 3Y 0.61 · rank 5 of 36 in category · risk-free 6.25%". Discover shows "Risk-free rate (91-day T-bill) 5.73%". Two risk-free numbers, no window or source beside the Sharpe. |
| 10 Phone theme icons | Fixed | Appearance icon is a palette; the theme toggle is a moon (light) or sun (dark). |
| 12 Discover ideas | Partly | Ideas now show scores and chips wrap. But "Calm equity" leads with Aditya Birla International Equity and healthcare sector funds (Sectoral/Thematic, Sharpe 1.20-1.32). Phone search placeholder still cut ("...or an AMF"), and the hero hills still sit behind the "40,214 plan options" line. |
| 14 Fall bands | Fixed | Bands are one faint neutral hue; dark mode no longer olive. Still on by default; on light they are still the most visible mark after the line. |
| 15 11px sources | Fixed | Date lines measure 12 px. One 10 px label remains ("/100" in the score ring). |
| 4, 5, 13 (open in ledger) | Not fixed | 4: screener looks the same (see weakness 3). 5: confirmed below. 13: y-axis still starts at ₹0 on fund and Compare charts. |
| 11 Portfolio (partly in M2) | Partly | Page now has "What you will see", a three-step CAS guide and two live tools; the CAS drop zone is styled. The Password label still sits about 30 px above the CAS label on desktop; Preview is disabled with no reason beside it; about 240 px of blank space below the cards. |

Rank 5 check: Fund house checklist still lists "360 ONE Asset Management Limited" and "360 ONE Mutual Fund" as separate values (112 values, duplicates for ABSL, Axis, HDFC, Bandhan and others). "parag" returns nothing; "ppfas" finds "PPFAS Asset Management Pvt. Ltd.". The Find box is clipped at the right edge. No per-AMC fund counts. The Find box is not focused when the list opens.

## Measured numbers

Fund page (fund 122639):

| Item | Desktop 1440x1000 | Phone 390x844 |
|---|---|---|
| Facts visible on screen 1 | 6 of 6, each with its date (dates at y=626-918) | 6 of 6 values, 0 of 6 dates |
| Scrolls to see all six dated facts | 0 | 2 (about 700 px each); 1 scroll gives TER, AUM, risk, benchmark dates |
| Chart on screen 1 | full, y=496+ | about 77 px of plot |
| Fixed bars | none | 65 px tab bar only |
| Page horizontal overflow, all 9 routes | none | none |

Screener, "show 1Y return, keep funds above −10%": 2 clicks (Show Return 1Y checkbox, Minimum box) + 3 keys; 46 to 37 funds; Return 1Y becomes the first data column; the request is `ret_1y between [-0.1, null]`. Keyboard only: 29 Tab presses to the Show checkbox, Space, 2 Tab to Minimum, 3 keys. The Return 1Y chip reads "Return 1Y ≥ -10%".

Screener, "keep one fund house": group path is 4 clicks + 5 keys (Fund group, Filter by Fund house, Find box, type "ppfas", tick). Search path is 4 clicks + about 14 keys. "parag" fails.

Compare PPFAS (122639) + HDFC (118955):
- Desktop: all three answers on screen 1 from the "At a glance" strip. Cheaper: PPFAS, 0.69% vs 0.75%. Fell less: PPFAS, −11.0% vs −13.3%. Higher 3Y return: HDFC, +14.4% vs +12.3%. Shared holdings: "No stored portfolio for HDFC Flexi Cap, so overlap cannot be read." So the default pair cannot answer the holdings question.
- Same page with 150346, 149763 or 148990 instead of HDFC: overlap 22.6%, 13.8%, 24.3% with security counts and a 30 Sep 2026 date.
- Phone: "Higher 3Y return" at y=598 is the only answer in full on screen 1. "Shallower fall" starts at y=749 (cut by the tab bar), "Lower cost" at y=900, the overlap card at y=1202 or lower. Cheaper and fell-less need 1 scroll; the holdings answer needs 2. The 5 cards stack one per screen.

## Visual problems seen in the captures (all 9 routes)

- Screener, desktop light and dark: fund names wrap to 2-3 lines with a code line under; header clipped ("Co"); "High to low" is an orphan label between selects; native grey selects for Category and Sort.
- Screener, phone: 4 header blocks (title, count, chips, Filters, two selects, Columns) take about 440 px before the first fund; one fund per screen; "Score category r..." truncated.
- Workspace, desktop: empty watchlist leaves about 450 px blank; the "+" button is washed out; "Nothing here yet." is plain text.
- Workspace, phone: all three starter fund names truncate ("Parag Parikh Fle...", "HDFC Flexi Cap ...", "Kotak Flexi Cap ...").
- Ask, both viewports: "PLANNED · SLICE 5", "Needs: A1, the agent runtime ... (ADR-022)" are internal build terms shown to investors; the page sits in the main nav with a "Planned" badge.
- Discover, phone: hills art runs behind the stat line; placeholder cut. Desktop: the "Market today" mini chart is red and falling while its headline says "recovery ... +4.2%".
- Studio: one plain line chart under a long tab row; no stated takeaway. Phone tab row is cut after "Peer rankings" with no cue.
- Portfolio: see rank 11 above.
- Fund, phone: action row clips mid-word under "Back" when scrolled ("pare"); "How it ranks" wraps to a second line beside the ring.
- Dark theme: no broken contrast found by axe; the fund and Compare pages look good in dark.

## Ranked remaining weaknesses

| Rank | Screen | Evidence | Why it matters to an investor | Fix |
|---|---|---|---|---|
| 1 | Compare, default PPFAS + HDFC | Overlap card says "No stored portfolio for HDFC Flexi Cap". This pair is the workspace starter set. Other pairs work (13.8-24.3%). | "Do they share holdings?" is one of the three questions Compare exists for. It fails on the most-clicked pair. | Load HDFC holdings (owner file needed; AMC is bot-blocked). Until then say "HDFC has not published a stored portfolio; showing category overlap" and hide the empty card. |
| 2 | Compare, phone | One answer visible on screen 1; cheaper at y=900, overlap at y=1202+; 5 cards stack. | Most users are on a phone. The page's main promise is below the fold. | One 2-column table (metric, fund A, fund B, winner mark) above the chart; 4 rows fit on screen 1. |
| 3 | Screener, desktop and phone | Same layout as before. Table 1093 px in 838 px; clipped headers; 2-3 line names; native selects; one fund per phone screen. | The screener is the work surface. REVIEW-1 rank 4 is unchanged, and the owner asked for lively and exceptional. | Single-line name with AMC under it; drop the 3Y NAV sparkline when width is under 1100; styled selects; 2-line phone rows with two metrics. |
| 4 | Screener, fund-house filter | 112 values with duplicates; "parag" returns nothing; Find box clipped; no counts; not auto-focused. | An investor searches by brand. Duplicates can hide funds from a one-house filter. | Merge AMC names to one canonical house; add alias "Parag Parikh = PPFAS"; show fund count per house; autofocus Find; fix the clip. |
| 5 | Fund, phone, key-facts strip | `aria-label="Key facts; go to their dates and sources"` replaces the visible values. axe: `label-content-name-mismatch` (serious). Strip shows no dates. | Screen-reader users hear no TER or AUM. Sighted users see undated numbers, against the "every figure dated" rule. | Remove the aria-label or start it with the visible text ("TER 0.69%, AUM ..."). Add "AMFI, 1-22 Oct 2026" under the strip. |
| 6 | Screener, range control | Text describes the shown set; after typing it just echoes the typed edge (−9.38%). No distribution, no "N left" before typing. Extra "32,327 exclusions" line. | The investor still cannot see what a threshold removes before choosing it. | Show a small histogram of the 46-fund set with the threshold marker and "37 of 46 kept" live. Hide or explain the exclusions line. |
| 7 | Fund, managers and Sharpe | Overview says "6 managers", Facts says "7 managers in the SSD" and lists 6. Managers date "24 Oct 2026" equals today. Sharpe shows risk-free 6.25%, Discover shows 5.73%. | Cross-checks on a second site look like errors. The brief was "every figure dated". | Reconcile the count and say why (7 filed, 6 listed). Show the real filing date. Print "3Y, risk-free 6.25% (source, window)" and use one risk-free value name across pages. |
| 8 | Ask (and nav) | "PLANNED · SLICE 5", "A1", "ADR-022" on the page; a "Planned" item in main nav. | Build jargon in front of investors reads as unfinished. | Remove internal codes; move the page out of primary nav until it works, or title it "Ask (coming soon)" with plain copy. |
| 9 | Workspace | 450 px blank on desktop; phone starter names truncate; "+" button washed out; empty state is a text line. | First impression of the personal area is empty and cramped. | Let names wrap on phone; fill the empty area with the three starter funds as full-width cards; give "+" a clear enabled state. |
| 10 | Discover | "Calm equity" leads with sector healthcare funds; red falling sparkline under a "recovery +4.2%" headline; phone hills behind text; placeholder cut. | The first idea contradicts its label, and the market card contradicts itself. | Restrict "Calm equity" to diversified categories; colour the line by the headline sign or label the window; remove art under text; shorten the placeholder to "Search a fund or AMFI code". |
| 11 | Fund and Compare charts | y-axis starts at ₹0; the first two years are a flat strip; bands on by default. | The line differences that matter (last 5 years) use the top half of the plot. | Start the axis at the data minimum or default to log scale; default the bands off, on by a toggle. |
| 12 | Fund, phone | Chart gets about 77 px above the tab bar; action row clips mid-word under Back ("pare"); "How it ranks" wraps beside the ring; legend loses "not the benchmark". | The chart is the product's hero and shows as a sliver. | Collapse the facts strip to two rows or put the chart above the tabs; add a fade on the action row; restore the full proxy label on phone. |

## D. Accessibility smoke

Keyboard:
- Phone Fund actions: Tab 7 reaches the group (tabindex 0, role group, label "Fund actions; scroll sideways for more actions"). Tabs 8-11 reach Add to watchlist, Compare, Test an investment, Notes; the row scrolls so each is fully visible. Focus ring on every stop: 3px solid rgb(4,120,87) light. The ring on Notes is slightly clipped at the right edge.
- Screener range: 29 Tab presses to the Show Return 1Y checkbox (no skip link to the filter rail; only "Skip to content"). After Space, Tab 1 is "Filter by Return 1Y", Tab 2 is "Minimum Return 1Y", Tab 3 is "Maximum Return 1Y". Same 3px ring. Typing −10 works from the keyboard.

axe-core (wcag2a, wcag2aa, wcag21a, wcag21aa), logged out, workspace mocked:

| Route | Desktop 1440 light | Desktop dark | Phone 390 light | Phone dark |
|---|---|---|---|---|
| /mf/funds/122639 | 0 | 0 | 1 serious: label-content-name-mismatch (the key-facts strip link) | 1 (same) |
| /mf/screen | 0 | 0 | 0 | 0 |
| /mf/compare?code=122639&code=118955 | 0 | 0 | 0 | 0 |
| /mf/portfolio | 0 | 0 | 0 | 0 |
| /mf/workspace | 0 | 0 | 0 | 0 |

"Incomplete" (not failures): colour contrast on text over gradients (hero, headings) could not be computed; `aria-label` on a plain span for the score ("Score 98 of 100", aria-prohibited-attr); a table header with no data cells in Compare. Contrast on gradient heroes needs a manual check.

## Not done

- No screen-reader run, no 200% zoom, no reduced-motion check.
- Tickertape pages were not re-opened. Comparisons rely on REVIEW-1.
- Studio and Lab were checked by eye only; no task was timed there.
