# MF metrics method

The method behind every number in the MF screener and research API ([ADR-017](../architecture/adr/ADR-017-funds-etfs-holdings.md) MF-8, MF-11; [ADR-018](../architecture/adr/ADR-018-unified-screening.md)). Code: `backend/src/wickstreet/analytics/domain/` (`metrics.py`, `classify.py`, `fields.py`). Any change that alters a computed value, a category or a classification bumps `METHOD_VERSION`. A snapshot is stored once per (revision, method version), so two methods never mix.

## Versions

| Version | Date | Change | Status |
|---|---|---|---|
| 1 | 2026-10-23 | The method below, as proposed in the [Slice 2 plan](../plans/wickstreet-2/19-slice-2-mf-analytics.md) | Approved by the owner in the final plan review of 2026-10-23 |
| 2 | 2026-10-23 | The option rule only. The real-data spot check found growth options of unclaimed-dividend plans classed as IDCW ("Unclaimed IDCW Plan - Growth"), AMFI's rename of "Dividend Yield" to "IDCW Yield" inside fund names, "RetireInvest" read as "reinvest", and the misspelling "IDWC". v2 removes those fund and plan phrases before matching, matches `reinvest` as a word, and adds `idwc`. Active plan-options: `idcw` 4,583 → 4,551, `growth` 3,688 → 3,693, `unknown` 327 → 354 | Built and in use; awaits owner review |

| 3 | 2026-10-23 | Slice 3: status, annual returns, drawdown episodes, worst periods, downside risk, category ranks, consistency, the composite score and sibling categories (sections below). v1 and v2 values are unchanged | Superseded by v4 |
| 4 | 2026-10-23 | NAV analytics v4 ([doc 21](../plans/wickstreet-2/21-analytics-expansion-v4.md)): SEBI 2026 categories and fund type; point-in-time peer groups (consistency changes); persistence; deterioration; direct vs regular; rolling percentiles; current drawdown; near-duplicates; the regime proxy; tax rules back to 2018-04-01 (sections below) | Superseded by v5 |
| 5 | 2026-10-23 | E2: the RBI 91-day T-bill yield. Risk-free returns, Sharpe 1Y and 3Y with category ranks, and Sortino against the risk-free return instead of 0% ("Risk-free (v5)" below) | Superseded by v6 |
| 6 | 2026-10-24 | E1, E3, E4: 49 new fields from AMFI's TER, fund performance, scheme summary documents and tracking error, and from AMC portfolio disclosures ("Fund facts (v6)", "Benchmark proxy (v6)", "Holdings (v6)" below). v5 values are unchanged | Superseded by v7 |
| 7 | 2026-10-24 | E5: 6 fields from AMFI's IDCW history ("IDCW (v7)" below). Monthly facts (fund performance, tracking error) are read on the latest business day of each month, not a weekend month-end with few funds reported | Superseded by v8 |
| 8 | 2026-10-24 | Deterministic storage. Every stored float is rounded to 10 significant digits; computation keeps full precision. Beta, R² and alpha against the benchmark proxy use exactly rounded sums (`math.fsum`) instead of NumPy's BLAS-backed `cov` and `corrcoef`. Values move in the 10th significant digit or less | In use (owner decision of 2026-10-24) |

Snapshots of v1 to v6 stay stored; reads use v7.

## Observations

- The series of a plan-option is its current NAV rows at the snapshot revision, in date order.
- A NAV is **valid** when it is a finite number above zero. Null (`N.A.` as filed), zero, negative and `NaN` rows are excluded and counted in `excluded_navs`. Exclusion never fails the stream.
- Rows flagged `nav_jump` (a move beyond 25% of the previous NAV) are kept and counted in `jump_flags`.
- **As-of date D:** the latest NAV date in the store at the revision.
- **End anchor:** the fund's last valid NAV on or before D. The fund is **active** when D minus that date is 7 days or less.

## Anchors

- **Offsets** are calendar months back, with the day clamped to the month end: one month before 31 March is 28 or 29 February. One year is 12 months.
- **Start anchor** for a target date: the last valid NAV on or before it, and no more than 7 days before it. Otherwise the metric is `NA`: `history_too_short` when the series starts after the target, `gap_at_start` when the nearest NAV is more than 7 days early.
- Each trailing return stores the start date it used (`anchors` in `GET /funds/{code}/metrics`).

## Formulas

All arithmetic is IEEE double precision with no intermediate rounding. Sums use `math.fsum`. Values are stored and returned at full precision; round them only for display. Returns are fractions: 0.12 means 12%.

| Field | Formula |
|---|---|
| `ret_1m`, `ret_3m`, `ret_6m`, `ret_1y` | end / start − 1, anchored at D |
| `cagr_3y`, `cagr_5y`, `cagr_10y` | (end / start)^(365.25 / days) − 1; days = calendar days between the two anchors |
| `since_start` | Date of the first valid NAV stored. A zero or null opening row is skipped. Labelled "since <date>, first stored valid NAV, not inception" |
| `ret_since` | end / first valid NAV − 1 |
| `cagr_since` | Annualised as above; needs 365 days |
| `rolling_1y_*`, `rolling_3y_*`, `rolling_5y_*` | One annualised return at every valid date that has a valid start anchor, over the whole stored history up to the end anchor. Summary: `count`, `mean`, `median` (mean of the two middle values for an even count), `min`, `max`, `positive_share` (share above zero) |
| `vol_1y`, `vol_3y` | Sample standard deviation (n − 1) of simple returns between consecutive valid NAVs in [start, end], × √252. Needs 2 returns |
| `mdd_1y`, `mdd_3y`, `mdd_since` | min(NAV / running peak − 1) over the window; always between −1 and 0 |

## States

A missing value is never 0. It is `NA` (not available) or `NM` (not meaningful), with a reason:

| State | Reason | When |
|---|---|---|
| NA | `no_nav` | The plan-option has no valid NAV. It stays in search and screens; every metric reports this |
| NA | `no_recent_nav` | The fund is not active; trailing returns, volatility and 1Y/3Y drawdown only |
| NA | `history_too_short` | The series starts after the target date, or has too few points |
| NA | `gap_at_start` | The nearest NAV before the target is more than 7 days early |
| NM | `gap_in_window` | Two consecutive valid NAVs inside a volatility or drawdown window are more than 7 days apart |
| NA | `no_pair` | v4: the fund has no single direct–regular counterpart |
| NA | `no_risk_free` | v5: no risk-free rate covers the window, or it is more than 35 days old |
| NA | `no_scheme_join` | v6: no AMFI scheme joins the plan-option (the SSD lists none of its ISINs) |
| NA | `not_filed` | v6: AMFI or the AMC filed no value for the scheme |
| NM | `growth_option_only` | v6: AMFI reports fund-versus-benchmark figures for growth options only |
| NA | `no_benchmark` | v6: no benchmark filed |
| NA | `no_benchmark_proxy` | v6: no active index fund or ETF tracks the filed benchmark |
| NA | `no_year_ago_value` | v6: no value within 45 days of a year before |
| NM | `no_equity` | v6: the portfolio holds no equity, so sector and market-cap shares do not apply |
| NM | `not_idcw_option` | v7: the IDCW fields apply to IDCW options only |

In a screen, every comparison on an `NA` or `NM` value is false, including `!=` and `not_in`. `is_missing` is true exactly on them and `is_available` exactly on a value.

## Plan and option

- **Option text:** AMFI's option column in the NAV file when present. Otherwise the NAV name with the scheme name removed from its start, or the whole NAV name when it does not start with the scheme name.
- **Fund and plan phrases** are removed first: "Dividend Yield", "IDCW Yield", "Dividend Opportunities", "Growth Fund", "Growth Opportunities", "Growth &"/"Growth and", "Income Fund", and "Unclaimed … Dividend/IDCW/Div" (v2).
- **Order:** IDCW words (`idcw`, `idwc`, `dividend`, `div`, `payout`, `reinvest…`, `income distribution`) → `idcw`; `bonus` → `bonus`; `growth` or `cumulative` → `growth`; anything else → `unknown`. Most `unknown` options are ETFs, whose names carry no option.
- **Return basis:** `nav` for growth options. Every other option is `nav_excluding_payouts`, and each response row carries "NAV return; excludes payouts; not a total return."
- **Plan:** `direct` when the plan column or the NAV name has the word "direct", else `regular`.

## Categories

The canonical categories are AMFI's SEBI labels, as AMFI writes them (including "Other Scheme - Other  ETFs" with two spaces and "Children s Fund"). The source label is kept as `source_category`; `asset_class` comes from the canonical prefix.

A variant label maps only when it names exactly one canonical category:

| Variant | Maps to |
|---|---|
| "Equity Schemes - X" for Large Cap, Large & Mid Cap, Mid Cap, Small Cap, Multi Cap, Flexi Cap, Focused, Value, Contra, Dividend Yield | "Equity Scheme - X" |
| "Equity Schemes - ELSS- Tax Saver Fund", "ELSS" | Equity Scheme - ELSS |
| "Equity Schemes - Sectoral Fund", "Equity Schemes - Thematic Fund" | Equity Scheme - Sectoral/ Thematic |
| "Income/Debt Oriented Schemes - X" for Overnight, Liquid, Money Market, Corporate Bond, Credit Risk, Gilt | "Debt Scheme - X" |
| "… - Banking and PSU Debt Fund" | Debt Scheme - Banking and PSU Fund |
| "… - 10-year Constant Maturity Gilt Fund" | Debt Scheme - Gilt Fund with 10 year constant duration |
| "… - Floating Interest Rates Fund", "Floating Rate" | Debt Scheme - Floater Fund |
| "Liquid", "Money Market" | Debt Scheme - Liquid Fund, Money Market Fund |
| "Hybrid Schemes - X" for Aggressive, Conservative, Balanced Hybrid, Arbitrage | "Hybrid Scheme - X" |
| "Hybrid Schemes - Multi Asset Allocation Fund", "- Equity Savings Fund", "- Balanced Advantage Fund/ Dynamic Asset Allocation" | Hybrid Scheme - Multi Asset Allocation, Equity Savings, Dynamic Asset Allocation or Balanced Advantage |
| "Solution Oriented Schemes ** - Retirement Fund"; "Children s Fund - Childrens' Fund" and the mis-encoded "Childrenâ€™s Fund" | Solution Oriented Scheme - Retirement Fund, Children s Fund |
| "Index Funds - Equity/Debt/Hybrid Fund(s)" | Other Scheme - Index Funds |
| "Fund of Funds Scheme (Domestic) - …", "Fund of Funds - Domestic" | Other Scheme - FoF Domestic |
| "Overseas Fund of Funds - …", "Fund of Funds - Overseas" | Other Scheme - FoF Overseas |
| "Exchange Traded Funds (ETFs) - Gold ETF", "GOLD ETFs" | Other Scheme - Gold ETF |
| "Exchange Traded Funds (ETFs) - Equity/Debt/Other/Silver/Hybrid ETF, ETFs investing overseas", "Other ETFs" | Other Scheme - Other  ETFs |

**SEBI 2026 categories (v4).** SEBI revised the categorisation on 26 February 2026 and gave schemes six months to comply. AMFI now writes a second label family beside the 2017 one. A 2026 label with the same name as a 2017 category maps to it (the table above). These 2026 labels name no 2017 category, so each is its own canonical category and peer group, as AMFI writes it: "Income/Debt Oriented Schemes - " + Ultra Short Term Fund, Ultra Short to Short Term Fund, Short Term Fund, Medium Term Fund, Medium to Long Term Fund, Long Term Fund, Dynamic Term Fund and Sectoral Fund (asset class Debt); and "Life Cycle Funds - Life Cycle Fund with Maturity of N Years" for N = 5 to 30 in steps of 5 (asset class Life Cycle). Mapping "Short Term" to "Short Duration" would be a guess, so v4 does not. Up to v3 these labels were read as pre-2018 terms and left Unclassified; that was wrong.

Every other label is **Unclassified**: the broad labels Income, Growth, Balanced, Gilt and Assured Return, and "Other Debt Scheme" and "Fixed Term Plan". On 2026-10-23 (v4), 111 of 8,668 active plan-options are Unclassified (v3: 1,102); 102 of them are closed-ended "Income" plans, mostly fixed maturity plans.

**Fund type (v4).** `fund_type` is `index`, `etf` or `fof` from the category (Index Funds; Gold ETF and Other ETFs; FoF Domestic and Overseas). Otherwise it comes from AMFI's scheme type: `close_ended` ("Close Ended…"), `interval` ("…Interval…"), else `open_ended`.

## Status (v3)

`status` is `active` (last valid NAV within 7 days of D), `historical` (valid NAVs, but older) or `no_nav`. Screens, ranks and views keep the three apart.

## Annual returns (v3)

- A year's end anchor is the start anchor of its last day (31 December, or 31 March for the April–March financial year).
- `ret_cy_last` and `ret_fy_last`: the last complete year ending on or before D. `ret_ytd`: end NAV ÷ last year's end anchor − 1, active funds only.
- `cy_best`, `cy_worst`, `cy_positive_share`, `cy_count`: over every complete calendar year stored.
- `GET /funds/{code}/annual` also lists the partial first and last years, labelled `partial`, and month-end to month-end returns.

## Drawdown episodes and worst periods (v3)

- `dd_3y_*` and `dd_since_*`: for the deepest fall in the window, the peak, trough and recovery dates (first NAV back at the peak), the fall length and the recovery time in calendar days. `NA not_recovered` when the NAV has not regained the peak; `NA no_drawdown` when it never fell. A gap over 7 days is `NM gap_in_window`, as for `mdd`.
- `worst_1m`, `worst_3m`, `worst_1y`: the lowest end ÷ start − 1 over every window of that length in the stored history (start anchors as for rolling returns).
- `GET /funds/{code}/drawdowns` lists the deepest falls of the whole history, recovered or not.

## Downside risk (v3)

Over the 3Y window of `vol_3y` (same anchors, same gap rule):

| Field | Formula |
|---|---|
| `downside_dev_3y` | √(mean of min(r, 0)²) × √252, over daily returns r |
| `sortino_3y` | v5: (`cagr_3y` − `rf_3y`) ÷ the downside deviation below the risk-free return of each interval (see "Risk-free (v5)"). v3–v4: `cagr_3y` ÷ `downside_dev_3y` |
| `var95_3y` | The 5th-percentile daily return (nearest rank: the ⌈0.05 n⌉-th lowest) |
| `cvar95_3y` | Mean of the daily returns at or below `var95_3y` |
| `ret_risk_3y` | `cagr_3y` ÷ `vol_3y`, with no risk-free rate. It stays a score part; `sharpe_3y` is the risk-free version |

## Peers, consistency and score (v3)

- **Peer group:** canonical category × plan × option. Today's ranks use active funds only. Unclassified and inactive funds get no peer fields (`NA no_peer_group`, `no_recent_nav` or `no_nav`). From v4, past month-ends use every fund of the key alive then (see "Point-in-time peers").
- **Ranks** need 5 peers with a value (`NA too_few_peers` otherwise). For each of `ret_1y`, `cagr_3y`, `cagr_5y`, `vol_3y` (lower is better), `mdd_3y`, `sortino_3y`, `ret_risk_3y`, `consistency_3y` and `score`:
  - `_cat_rank` = 1 + the number of peers strictly better;
  - `_cat_pct` = 100 × (peers worse + ½ × other peers equal) ÷ (n − 1), so 100 is best and ties share the average rank;
  - `_cat_quartile` = 1 when the percentile is 75 or more, 2 from 50, 3 from 25, else 4;
  - `_cat_count` = n; `_cat_median` = the median value over the n peers.
- **Consistency:** at each complete month-end the fund was alive (below), its 3Y CAGR is compared with the median of the 3Y CAGRs of the group members alive that month-end, where 5 have one. `consistency_3y` = the share of months above the median; it needs 12 months. From v4 the medians include funds that later stopped publishing (v3 used today's active funds only).
- **Score:** the equal-weight mean of the category percentiles of `consistency_3y`, `ret_risk_3y` and `mdd_3y`. Missing when any part is missing. Cost joins the score when TER data is stored. A custom weighting is a screen formula.
- **Sibling categories:** an Unclassified plan-option takes the category of the other plan-options of its scheme (same AMC and scheme name) when they name exactly one canonical category (`category_basis = scheme_sibling`). On 2026-10-23 no active Unclassified fund had such a sibling, so 1,102 remain Unclassified.

## Risk-free (v5)

- **Series:** the implicit yield at the cut-off price of RBI's 91-day Treasury Bill auctions (% a year, actual/365), from the Handbook of Statistics on the Indian Economy (one edition a year) and the weekly "Treasury Bills: Full Auction Result" press releases. Stored in `rate_point`, revisioned like NAVs, so a snapshot reads the rates of its revision. A week with no accepted bids has no rate. Every response that uses it lists source `rbi`; `GET /risk-free` carries RBI's acknowledgement, which its terms require.
- **Deposit:** each auction's yield is in force from its date to the next auction, and accrues yield ÷ 365 on each calendar day. The growth from day a to day b is ∏ (1 + yᵈ ÷ 36,500) over the days d in [a, b).
- `rf_1y`, `rf_3y`: that growth over the fund's own 1Y or 3Y window (the start anchor of `ret_1y` or `cagr_3y` to the end anchor), annualised on 365.25-day years like a CAGR.
- `sharpe_1y` = (`ret_1y` − `rf_1y`) ÷ `vol_1y`; `sharpe_3y` = (`cagr_3y` − `rf_3y`) ÷ `vol_3y`. `sharpe_3y` has category ranks like the other ranked fields.
- `sortino_3y` = (`cagr_3y` − `rf_3y`) ÷ √(mean of min(rₖ − gₖ, 0)²) × √252, where gₖ is the deposit's growth over the k-th return interval.
- `NA no_risk_free` when no auction precedes the window start, or the last auction before the window end is more than 35 days old. Without new imports, values go stale 35 days after the last stored auction.

## Fund facts (v6)

Sources: AMFI's monthly "TER of MF schemes" file, the fund performance report (one call per sub-category and date, 2019 onward), the scheme summary document (SSD) of each scheme, and the scheme list. Each fact is stored once per (scheme, name, plan, date) in `scheme_fact`, revisioned like NAVs. TER is stored as change points.

- **Join:** a plan-option joins a scheme through the ISINs its SSD lists, or through the AMFI codes it lists (by that plan-option's ISINs). A plan-option with neither joins by its master scheme name when exactly one listed scheme has that name (case, spaces and punctuation ignored). When the two disagree, one AMC filing is wrong; the code wins only when the plan-option's AMFI name contains the code's scheme name and not the other's. AMFI serves SSDs in two layouts (`SchemeSummary` elements, or label–value records); both give the same fields. TER rows join by SEBI scheme code, else by name. Performance rows join by name, else by NAV pair: the report's regular and direct NAVs on that date, to the paisa, must point to one scheme and differ from each other.
- `ter`, `ter_base`: the plan's total and base TER, % a year of daily net assets, as filed. `ter_change_1y` = today's TER − the TER in force a year before (percentage points as a fraction). SEBI changed what the total TER includes from 1 April 2026, so values on either side are not like for like; the profile says so.
- `ter_cat_pct`, `ter_cat_median`: the percentile and median of `ter` in the plan-option's peer group (category, plan, option), cheapest = 100. Under 5 priced peers: `NA too_few_peers`.
- `aum_cr`: the scheme's AUM in ₹ crore from the latest fund performance report. `aum_change_1y` = AUM ÷ the AUM a year before − 1.
- `riskometer`, `riskometer_level` (1 Low … 6 Very High), `benchmark`: from fund performance, else the SSD.
- `manager_count`, `manager_tenure_y` (years since the earliest start date filed), `inception` (allotment date), `min_lumpsum`, `min_sip`: parsed from SSD text. A start filed as "since inception" uses the allotment date.
- `bench_ret_1y` … `bench_ret_10y`: the benchmark's return as AMFI reports it. `excess_h` = the fund's AMFI-reported return − `bench_ret_h`, growth options only. `ir_1y` … `ir_5y` and `tracking_error`: as filed by AMFI (tracking error for index funds and ETFs only).

## Benchmark proxy (v6)

NSE and BSE terms bar automated retrieval of index TRI, so Wickstreet uses a proxy and labels it. For each benchmark (filed names normalised: case, spaces, "TRI", "Total Return Index", "S&P"), the proxy is the active direct growth index fund or ETF with that benchmark and the lowest tracking error AMFI lists; ties go to the lower plan-option id. `bench_proxy_gap_3y` is the proxy's 3Y return minus its benchmark's 3Y return, both from the proxy's latest AMFI fund performance report: the tracking difference the proxy adds.

Over the common daily NAV dates of the last 3 years (more than 500 steps, each 7 days or shorter), with daily returns rₜ (fund) and pₜ (proxy):

- `beta_3y` = cov(r, p) ÷ var(p). `r2_3y` = corr(r, p)².
- `alpha_3y` = CAGR − rf − β (proxy CAGR − rf), rf the risk-free return over the same window (v5).
- `te_3y` = std(r − p) × √252. `ir_3y_proxy` = (CAGR − proxy CAGR) ÷ `te_3y`.
- `up_capture_3y`, `down_capture_3y`: the geometric mean monthly return of the fund ÷ that of the proxy, over months when the proxy rose (fell). At least 6 such months.
- A zero-variance series gives `NM zero_denominator`, never NaN.

## Holdings (v6)

Sources: AMC monthly portfolio disclosures (PPFAS and DSP fetched; any AMC's file can be imported with `mf import-portfolios`) and AMFI's half-yearly market-cap lists. Each line keeps the AMC's name, ISIN, industry, section, quantity, value and % of net assets. The parser stops at the grand total and skips subtotals. A line is a derivative when its industry says futures or options, or its name ends in a contract month ("Axis Bank Limited Oct26"), whatever section it is under. A portfolio reconciles when its lines add to 100% ± 2% with or without its derivative lines: AMCs file a hedge's short futures as notional lines outside the 100%, but count long futures and options inside it. A portfolio that does not reconcile is kept and flagged.

- `holdings_as_of`, `holdings_count`, `top10_weight` (all lines), `equity_share`, `debt_share`, `cash_share`: from the latest portfolio, as % of net assets.
- `effective_holdings` = 1 ÷ Σ w², `large_cap_share`, `mid_cap_share`, `small_cap_share`, `foreign_share`: over the equity part, rescaled to 100%. A stock's cap class is AMFI's list in force on the portfolio date; an ISIN not starting "IN" is foreign. A fund without equity gets `NM no_equity`.
- The holdings view adds sectors (the AMC's industry labels), debt by the AMC's rating labels, and the change since the month before.
- Overlap of two portfolios = Σ min(wₐ, w_b) over shared ISINs, excluding cash and derivatives. `same_month` says whether both are of one month.

## IDCW (v7)

Source: AMFI's IDCW history per scheme (record date, ₹ per unit, per plan-option code).

- `idcw_last`, `idcw_count_1y`, `idcw_1y` (₹ per unit with a record date in the last 365 days), `idcw_yield_1y` = `idcw_1y` ÷ latest NAV.
- `ret_1y_with_idcw`, `cagr_3y_with_idcw`: NAV growth from the start anchor of `ret_1y` (or `cagr_3y`) to the last NAV, with each payout in the window reinvested at the NAV of its record date: growth = (NAV_end ÷ NAV_start) × ∏ (1 + payout ÷ NAV on the record date). The 3Y figure is annualised over the same days as `cagr_3y`. Both need the fund's 3Y daily window, so an IDCW option under 3 years old gets `NA history_too_short`.

## Point-in-time peers (v4)

- **Alive at a month-end:** the fund's last valid NAV of the month is within 7 days of the month's last day. Only complete months count: the month's last day is on or before D.
- **Month-end values:** the NAV, the trailing 1Y return and the trailing 3Y CAGR at that NAV, with the start-anchor rules above.
- **Members:** every plan-option of the group key with a valid NAV, active or not. A month ranks when 5 members alive then have a value. Rank, percentile and quartile use the formulas of today's ranks. Funds whose labels map to no category are in no group.
- **Persistence:** over the last 36 complete month-ends, `q1_share_3y` = the share of ranked month-ends with the 1Y return in quartile 1, and `pct_mean_3y` = the mean 1Y percentile. Both need 12 ranked month-ends.
- **Rank history** (`GET /funds/{code}/rank-history`) lists the 1Y and 3Y rank, peer count, percentile and quartile at each month-end. **Transitions** (`GET /peers/transitions`) count (1Y quartile at a month-end, 1Y quartile 12 month-ends later) over the group's history.

## Deterioration (v4)

One year before D (T = D − 12 months), a fund is alive when it has a start anchor at T. For funds alive then: `ret_1y` (anchors T and T − 12 months), `vol_3y` and `mdd_3y` (window T − 36 months to T).

| Field | Formula |
|---|---|
| `ret_1y_cat_pct_1y_ago`, `vol_3y_cat_pct_1y_ago`, `mdd_3y_cat_pct_1y_ago` | Category percentile at T among the group members alive at T (5 needed) |
| `ret_1y_cat_quartile_1y_ago` | Quartile of that 1Y percentile |
| `ret_1y_pct_chg_1y`, `vol_3y_pct_chg_1y`, `mdd_3y_pct_chg_1y` | Percentile now − percentile at T. 100 is always best, so a fall is negative |
| `quartile_change_1y` | Quartile at T − quartile now; −3 to 3, negative = moved down |
| `consistency_3y_chg_1y` | `consistency_3y` − the same share over month-ends up to 12 months before the last complete month |

No field combines them; a screen does.

## Direct vs regular (v4)

- **Pair:** among active funds, same AMC, scheme name and option, with exactly one direct and one regular plan-option. Otherwise `NA no_pair` (most IDCW options have several plan-options per side).
- `dr_gap_1y` = direct `ret_1y` − regular `ret_1y`; `dr_gap_3y` = direct `cagr_3y` − regular `cagr_3y`. Both plans carry the same values.
- `dr_wealth_10y` = ₹10,00,000 × ((1 + direct `cagr_3y`)^10 − (1 + regular `cagr_3y`)^10).
- Labelled "observed NAV gap, not TER" until TER data (E1) is stored. On 2026-10-23, 5,794 plan-options have a pair; the median equity gap is +1.29% a year.

## Rolling percentiles and drawdown (v4)

- `rolling_1y/3y/5y_p10`, `_p25`, `_p75`, `_p90`: the ⌈q × n⌉-th lowest rolling return (nearest rank, as for VaR).
- `dd_now` = end NAV ÷ the highest valid NAV so far − 1; `dd_now_days` = days since the last NAV at that peak. Active funds only (`NA no_recent_nav`).
- `underwater_max_days`: the longest stretch from a peak to the first NAV back at it, or to the last NAV when not recovered, over the stored history.
- `GET /funds/{code}/underwater`: the fall from the running peak at every valid NAV, and the recovery-time spread (count, min, median, 90th percentile and max days, nearest rank) of the recovered falls of at least 5%, 10% and 20%, with the count not recovered.

## Near-duplicates (v4)

Within the peer group, two active funds are near-duplicates when their daily returns over the 3Y window correlate at 0.95 or more, over at least 500 returns. Returns are those between consecutive dates both funds have a NAV, from each fund's 3Y start anchor: the compare definition. A fast screen on each fund's own returns at 0.85 picks the candidate pairs; each candidate is then computed exactly. `near_duplicates` counts them (`NA history_too_short` without a 3Y window); `GET /funds/{code}/near-duplicates` lists the top 10. On 2026-10-23, 3,075 active funds have at least one. `GET /compare` adds `average_correlation`, the mean of its pairwise correlations.

## Regime proxy (v4)

- **Proxy:** the median daily return of the "Equity Scheme - Large Cap Fund" direct growth plan-options with a valid NAV that day and the day before (gap of 7 days or less), on days with 5 such funds, chained into a level from 100. Funds that later stopped count while alive. It is labelled everywhere as a proxy built from fund NAVs, not an official index (owner decision M8).
- **Regimes:** a fall from a running peak of 10% or more is a `correction`, of 20% or more a `crash`, from the peak to the trough. Its `recovery` runs from the trough to the first level back at the peak, `ongoing` when it has not.
- `GET /regimes` lists the windows and the daily levels. `GET /funds/{code}/regimes` gives the fund's return over each window (start anchors at both ends), the difference from the proxy, and capture = fund return ÷ proxy return.
- On 2026-10-23 the proxy shows six falls: 2016-10 to 2016-12 (−11.0%), 2018-08 to 2018-10 (−14.4%), 2020-02 to 2020-03 (−35.5%, crash), 2021-10 to 2022-06 (−18.0%), 2024-09 to 2025-02 (−16.1%) and 2026-01 to 2026-03 (−14.2%).

## Backtests (v4)

`POST /backtests` with a peer group, a `signal` (`ret_1y` or `cagr_3y`) and `top` (1 to 50):

- At each complete month-end, rank the group's funds alive then on the signal (ties by AMFI code), hold the top `top` with equal weights to the next month-end. A pick with no NAV at the next month-end is dropped that month. A month counts when 5 funds have a signal and 5 have both month-end NAVs.
- **Benchmark:** the median next-month return of every fund alive at both month-ends.
- Returns are NAV returns, net of TER, before tax. Months with a signal before 2024-01 are in-sample, the rest the hold-out. The strategy fits nothing, so the split only reports the two periods apart.
- Each result states its first and last signal month per period, the regime windows its months span, and the limits: current categories applied to past dates, unmapped closed funds outside every group, no splice across code changes.
- Usable signal periods: 1Y from the first month-end with a 1Y window (about 2017-10), 3Y from about 2019-10, to the month before the last complete month.

## Rolling SIP, frontier, score and confidence views (v4)

- `GET /funds/{code}/rolling-sip?tenor=3y|5y&amount=&day=&step_up=`: the SIP calculator run for each start month (the 1st, from the first month that starts on or after the first valid NAV) whose tenor ends on or before D. Each start reports XIRR and the SIP drawdown, the lowest value ÷ invested − 1 on the instalment dates. The summary gives the best, worst and median XIRR, the share above zero and the worst SIP drawdown. Defaults: ₹10,000 on day 1, step-up 0 (M9).
- `GET /peers/frontier`: the group's active funds on `vol_3y` and `cagr_3y`; `frontier` marks the funds no other fund beats on both, with risk no higher and return no lower (ties keep the first code).
- `GET /funds/{code}/score`: each score part with its value, category percentile, peer count, weight (⅓) and missing reason; penalties (none, M12); data-quality notes.
- `GET /funds/{code}/confidence`: status, first and last NAV, valid NAV count, gaps over 7 days, excluded and flagged rows, category and its basis, the rows and dates of each source, and fixed notes on the limits.
- `GET /screener/fields` adds each field's `coverage`: rows with a value and rows missing by reason.

## Screen formulas

A screen request may define up to 10 formulas, such as `"0.6 * cagr_5y_cat_pct + 0.4 * mdd_3y_cat_pct"`. A formula uses number fields, numbers, `+ - * /`, unary minus and parentheses; nothing else parses. A missing input makes the result missing with that input's reason; a zero divisor is `NM zero_denominator`, and a non-finite result `NM not_finite`.

## Calculators (`CALCULATOR_VERSION` 1)

- SIP, lump sum, SWP and STP run over the fund's real NAVs. An instalment is scheduled monthly on `day` (clamped to the month end) and trades at the first valid NAV on or after it. An STP transfer trades on the first date both funds have a NAV.
- Stamp duty of 0.005% applies to purchases from 2020-07-01. Redemptions are first in, first out. The final value uses the last valid NAV on or before the end date.
- XIRR solves for a zero net present value on a 365-day year, by bisection over (−99.99%, 10,000%); `null` when no rate there does.
- Exit loads, surcharge and securities transaction tax are not modelled. A simulation reads past NAVs; it is not a forecast.

## Capital-gains tax (`in-2018-04-01`, v4)

Each sale follows the rules in force on its sale date:

| Sale date | Equity-oriented | Debt bought from 2023-04-01 | Other debt and `other` |
|---|---|---|---|
| From 2024-07-23 | 12.5% over 12 months, else 20% | Slab rate | 12.5% over 24 months, no indexation; else slab |
| 2018-04-01 to 2024-07-22 | 10% over 12 months, else 15% | Slab rate | 20% on the indexed gain over 36 months; else slab |

Holding periods are 365, 730 and 1,095 days. Indexed cost = cost × CII of the sale year ÷ CII of the purchase year (CBDT index, FY2013-14 to FY2024-25). Equity uses 31 January 2018 grandfathering. The financial year's net long-term equity gain above ₹1 lakh (₹1.25 lakh from FY2024-25) is taxed; the exemption goes against the highest rate first. Within a year, a long-term loss offsets only long-term gains; short-term and slab losses offset any gain; each goes against the highest rate first. Nothing carries forward. Cess is 4%. Sales before 2018-04-01 are counted as not modelled. The tax class comes from the category (equity: equity schemes and aggressive hybrid, arbitrage, equity savings; debt: debt schemes and conservative hybrid), or from the request when the category does not decide it. SIP and lump sum are taxed as if every unit were redeemed on the valuation date. Sales before 2018-04-01 are counted as not modelled.

## Known limits

- √252 understates volatility for funds that publish a NAV on every calendar day (liquid, overnight).
- Categories and names are AMFI's of 2026-10-23, because AMFI restates current labels for past dates.
- NAVs before 2023-04-01 come from the TigZig archive at 4 decimals.
- No index TRI. Beta, alpha, tracking error and capture use a labelled index-fund proxy (v6), which carries the proxy's own costs and tracking difference.
- Holdings come from two AMCs' sites and any imported files; most funds have none.
- Series are not spliced across curated links (`plan_option_link`) in this version. A fund whose code changed shows a short history under its new code.
- Today's ranks use today's active funds. Past month-ends include funds that stopped, but only where their label maps to a category; many closed funds carry broad labels and stay outside every group, so survivorship bias is reduced, not removed.
- No series of categories as filed: AMFI restates current labels for past dates, and the TigZig archive carries no category.
