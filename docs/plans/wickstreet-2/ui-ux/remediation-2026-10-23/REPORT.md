# Wickstreet 2.0 MF workstation: audit remediation

**Date:** 23 October 2026 · **Baseline:** [audit of 23 Oct 2026](../audit-2026-10-23/REPORT.md) (unchanged) · **Data:** snapshot 2801, NAV as of 22 Oct 2026, method v5
**Branch:** `wickstreet/m10-m11`, local only. Nothing is pushed.
**Evidence:** `screens/` (21 screenshots after the fix). The audit's `screens/` folder holds the "before" set.

The audit scored the build 6.9 / 10. This report does not score it again. The score needs an independent assessment.

---

## 1. Defects

### P1 (all six resolved)

| ID | Defect | Fix | Regression check |
|---|---|---|---|
| F-01 | Regimes bands drew as one block | Charts plot dates as time (`axis.ts`), so a band resolves at any date, not only at a date the thinned data keeps | E2E counts one band per API window (12) |
| F-02 | Axis labels were rounded copies of non-round gridlines | Round 1-2-5 gridlines and a label that shows the decimals the value needs (`niceTicks`, `pctTick`) on every value axis | Unit tests; E2E reads every risk-return label as a whole or half percent |
| F-03 | Row actions hidden in a sideways scroller | The action column is sticky on the right | E2E at 1280, 1440 and 1920 px |
| F-04 | Search hid the flagship fund | Backend: every term must match the name or AMC with spaces and punctuation removed; two synonyms (`bluechip` → large cap, `elss` ↔ tax saver). Order: exact code or ISIN, whole-query phrase, active Direct Growth, longest NAV history, name | Unit tests; real-data test of 10 queries in the top 3; E2E |
| F-05 | "Match any" ORed the universe | Status, plan and option stay ANDed: `ALL(gates, ANY(rest))`. Dashed chips and a note show it | Unit test; E2E count ≤ gates-only count |
| F-06 | Default sort ranked a category percentile across categories | The default screen is Flexi Cap by score. A category switch sits next to the sort. A note and a "Sort by CAGR 3Y" button appear when the score sort spans categories | Unit test; E2E |

**F-06, one criterion justified.** The audit also asked that the top 10 of the default view hold no fund below its category median 3Y CAGR. Rows 9 and 10 of Flexi Cap by score fall below it (25.7th and 45.7th percentile). The score is an equal mean of three parts (consistency, return per volatility, drawdown), so this is the method at work. Changing it changes the investment methodology, which needs the owner's approval. The page now says what the score ranks.

### P2

| ID | State | What changed |
|---|---|---|
| F-07 | Resolved | "Worst 1-month window" says it is any 1-month span. The Risk tab's 1-year tile now shows `rolling_1y_min`, the same figure as the rolling 1Y charts. E2E compares the two tabs |
| F-08 | Resolved | Each count names what it counts: "median 3Y CAGR of 36 funds with 3 years of NAVs", "Rank 1 of 31 scored Flexi Cap funds", and a line that explains why the scored count is smaller |
| F-09 | Resolved | The drawer runs a one-row screen with the formula first. A bad one stays in the drawer with the parser's message; the URL and results keep their last good state. E2E |
| F-10 | Resolved | A failed save reads "Could not save. Your draft is kept". A conflict offers "Copy my text" before "Load the latest version (replaces your text)" |
| F-11 | Resolved | Every blank trailing-return cell shows a dash with its reason on hover and for screen readers |
| F-12 | Resolved | Per-kind defaults: SWP ₹10 lakh with ₹6,000 a month lasts the full 5 years on 122639 (60 withdrawals, value ₹12.5 lakh). E2E |
| F-13 | Resolved | The Appearance panel says "Your choice is kept in this browser". The literal `border-black/10` is gone |
| F-14 | Resolved | The tray is one 48 px line. On phones it hides the fund list and the page gains bottom padding, so it covers nothing. On a fund page the phone action bar replaces it |
| F-15 | Resolved | Time ticks fall on month or year starts and never before the series starts |
| F-16 | Resolved | Backend labels use words ("Sharpe 3Y category rank", not "SHARPE 3Y …"). The formula picker groups fields and hides ids. A backend test bars code-style labels. `registry_version` changes, as designed |
| F-17 | Resolved | Card grids align to the top, so short cards no longer stretch |
| F-18 | Resolved | A sentence states both periods and the verdict, for example "The signal worked in-sample and did not hold up on the hold-out" |
| F-19 | Resolved | The backtest chart is growth of 100 from compounded monthly returns. Its end equals the API's `strategy_growth` (checked: 0.21364 on the hold-out). The caption names the shaded band |

## 2. Improvements delivered

| ID | Delivered |
|---|---|
| U-01 | Studio, Compare and Lab open on a chart. They start from the funds this visitor opened last (kept in this browser), else three named example flexi caps, and say so. The backtest runs on open |
| U-02 | A verdict line on every fund: its loss in the deepest proxy fall it lived through, the proxy's fall, and when it regained its peak. It links to the Risk tab. E2E checks each number against the API |
| U-03 | Zoom brush on the fund growth chart, the Studio rolling and drawdown charts and the Compare chart. Proxy-fall bands on the growth chart. A log-scale toggle. *Not done:* a crosshair linked across charts |
| U-04 | The value axis starts near the first value. The log scale removes the flat first half. *Not done:* a category-median line, because no category NAV series exists in the API |
| U-05 | Real 3Y sparklines (month-end NAVs from the new `GET /funds/sparklines`, up to 50 funds a call) in category cards, screener rows and ideas |
| U-06 | Fund-house monograms with a stable theme tint. They are markers, not logos |
| U-07 | Search in the desktop hero |
| U-08 | Partly. The recent-fund set travels to Studio, Compare and Lab. *Not done:* a shared period and a pinned snapshot across screens |
| U-09 | Sliders beside the rupee boxes, quick 1/3/5/10-year starts, and results that update 400 ms after each change |
| U-10 | See F-18 and F-19 |
| U-12 | The frontier is a line. Selected funds carry their names on the map |
| U-13 | On a 390 × 844 phone, the score ring, verdict and a fixed watch / compare / test bar are on the first screen. E2E |
| U-14 | Each idea says "Why these funds" from the preset's rule. Equity collections come first |
| U-16 | Small buttons and chips are 44 px tall on phones. E2E |
| Other | Fund header with score ring and three key numbers. A labelled risk-return map of the compared funds and a 1Y/3Y/5Y window on Compare. Fund-against-proxy bars per market window on the Risk tab and in the Studio. A "Your research" panel that lists recent funds or examples |

**Not done:** U-11 (nested group editor) and U-15 (locked portfolio preview). Section 5 lists them.

## 3. Screens

| Screen | Before (audit `screens/`) | After (`screens/`) |
|---|---|---|
| Discover | `d01-discover-desktop-full.png` | `discover-desktop.png`, `m-discover.png`, `dark-discover-desktop.png` |
| Screener | `screen-desktop-light.png`, `screen-match-any-trap.png` | `screen-desktop.png`, `m-screen.png` |
| Fund overview | `fund-overview-desktop-light.png`, `m-fund-viewport.png` | `fund-overview-desktop.png`, `m-fund.png`, `dark-fund-desktop.png` |
| Fund performance, risk | `fund-performance-desktop-light.png`, `fund-risk-desktop-light.png` | `fund-performance-desktop.png`, `fund-risk-desktop.png` |
| Studio | `studio-desktop-light.png`, `studio-regimes-desktop.png`, `studio-frontier-single.png`, `studio-backtest-result.png` | `studio-rolling-desktop.png`, `studio-regimes-desktop.png`, `m-studio-regimes.png`, `studio-frontier-desktop.png`, `studio-backtest-desktop.png`, `dark-regimes-desktop.png` |
| Compare | `compare-3funds-desktop.png` | `compare-desktop.png`, `m-compare.png` |
| Lab | `simulate-desktop-light.png`, `simulate-swp-result.png` | `simulate-desktop.png`, `simulate-swp-desktop.png`, `m-simulate.png` |

Every capture showed zero console errors. Every phone capture has a 390 px scroll width.

## 4. Verification

| Suite | Result |
|---|---|
| Web unit tests (Vitest) | 193 passed, 29 files (172 before) |
| Web lint (ESLint, zero warnings) and `tsc` | Clean |
| MF browser suite (Playwright, live snapshot, workspace mocked) | 37 passed: 21 earlier journeys and axe checks, 1 new lab test, 15 new regression tests |
| axe, light and dark, every MF route | No violation |
| Backend suite | 1,414 passed, 13 skipped (opt-in real-data tests) |
| Real-data checks (read-only) | 12 passed, including the new search test. The 300 s recompute test was not run |
| Momentum25 browser regression (Playwright) | 236 passed, 8 skipped |

The API container was rebuilt so the live app serves the new search, labels and sparkline route.

## 5. Remaining limitations

- **Not scored.** The 9 / 10 target needs an independent assessment against the owner's references.
- **Data gaps stay** (audit wave 4): expense ratio, AUM, exit load, benchmark TRI, holdings and manager need E1, E3 and E4 with rights grants.
- **U-04 category line:** no category NAV series exists. Adding one is a backend method change.
- **U-08:** no shared period or pinned snapshot across screens. Only the CSV export pins its revision.
- **U-11:** nested filter groups still show as one chip and cannot be edited.
- **U-15:** the Portfolio page has no locked preview.
- **Search:** no typo tolerance, and the synonym list has two entries. Former scheme names are not stored, so "axis bluechip" works through the `bluechip` synonym, not through history.
- **Bundle size:** `/mf` still loads about 1.1 MB of JavaScript.
- **Not tested:** a real phone, a screen reader, a usability study.
