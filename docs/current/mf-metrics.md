# MF metrics method

The method behind every number in the MF screener and research API ([ADR-017](../architecture/adr/ADR-017-funds-etfs-holdings.md) MF-8, MF-11; [ADR-018](../architecture/adr/ADR-018-unified-screening.md)). Code: `backend/src/wickstreet/analytics/domain/` (`metrics.py`, `classify.py`, `fields.py`). Any change that alters a computed value, a category or a classification bumps `METHOD_VERSION`. A snapshot is stored once per (revision, method version), so two methods never mix.

## Versions

| Version | Date | Change | Status |
|---|---|---|---|
| 1 | 2026-10-23 | The method below, as proposed in the [Slice 2 plan](../plans/wickstreet-2/19-slice-2-mf-analytics.md) | Approved by the owner in the final plan review of 2026-10-23 |
| 2 | 2026-10-23 | The option rule only. The real-data spot check found growth options of unclaimed-dividend plans classed as IDCW ("Unclaimed IDCW Plan - Growth"), AMFI's rename of "Dividend Yield" to "IDCW Yield" inside fund names, "RetireInvest" read as "reinvest", and the misspelling "IDWC". v2 removes those fund and plan phrases before matching, matches `reinvest` as a word, and adds `idwc`. Active plan-options: `idcw` 4,583 → 4,551, `growth` 3,688 → 3,693, `unknown` 327 → 354 | Built and in use; awaits owner review |

| 3 | 2026-10-23 | Slice 3: status, annual returns, drawdown episodes, worst periods, downside risk, category ranks, consistency, the composite score and sibling categories (sections below). v1 and v2 values are unchanged | In use (owner decisions of 2026-10-23, [doc 20](../plans/wickstreet-2/20-wickstreet-2.0-complete-mf-scope.md#3-nav-analytics-to-add-method-v3)) |

Snapshots of v1 and v2 (revision 2769) stay stored; reads use v3.

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

Every other label is **Unclassified**: AMFI's pre-2018 debt terms (Ultra Short to Short Term, Ultra Short Term, Short Term, Dynamic Term, Medium Term, Medium to Long Term, Long Term, Sectoral, Other Debt Scheme, Fixed Term Plan), the broad labels Income, Growth, Balanced, Gilt and Assured Return, and Life Cycle Funds. On 2026-10-23, 1,102 of 8,668 active plan-options are Unclassified, all from these labels.

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
| `sortino_3y` | `cagr_3y` ÷ `downside_dev_3y`. The threshold is 0% until a risk-free series is stored. `NM zero_denominator` when no return was negative |
| `var95_3y` | The 5th-percentile daily return (nearest rank: the ⌈0.05 n⌉-th lowest) |
| `cvar95_3y` | Mean of the daily returns at or below `var95_3y` |
| `ret_risk_3y` | `cagr_3y` ÷ `vol_3y`. Not a Sharpe ratio: there is no risk-free rate |

## Peers, consistency and score (v3)

- **Peer group:** canonical category × plan × option, active funds only. Unclassified and inactive funds have no group (`NA no_peer_group`, `no_recent_nav` or `no_nav`).
- **Ranks** need 5 peers with a value (`NA too_few_peers` otherwise). For each of `ret_1y`, `cagr_3y`, `cagr_5y`, `vol_3y` (lower is better), `mdd_3y`, `sortino_3y`, `ret_risk_3y`, `consistency_3y` and `score`:
  - `_cat_rank` = 1 + the number of peers strictly better;
  - `_cat_pct` = 100 × (peers worse + ½ × other peers equal) ÷ (n − 1), so 100 is best and ties share the average rank;
  - `_cat_quartile` = 1 when the percentile is 75 or more, 2 from 50, 3 from 25, else 4;
  - `_cat_count` = n; `_cat_median` = the median value over the n peers.
- **Consistency:** at each month-end (the fund's last valid NAV of the month), the rolling 3Y return is compared with the median of its group's month-end values, where 5 peers have one. `consistency_3y` = the share of months above the median; it needs 12 months. Only funds active today are in a group, so the medians carry survivorship bias.
- **Score:** the equal-weight mean of the category percentiles of `consistency_3y`, `ret_risk_3y` and `mdd_3y`. Missing when any part is missing. Cost joins the score when TER data is stored. A custom weighting is a screen formula.
- **Sibling categories:** an Unclassified plan-option takes the category of the other plan-options of its scheme (same AMC and scheme name) when they name exactly one canonical category (`category_basis = scheme_sibling`). On 2026-10-23 no active Unclassified fund had such a sibling, so 1,102 remain Unclassified.

## Screen formulas

A screen request may define up to 10 formulas, such as `"0.6 * cagr_5y_cat_pct + 0.4 * mdd_3y_cat_pct"`. A formula uses number fields, numbers, `+ - * /`, unary minus and parentheses; nothing else parses. A missing input makes the result missing with that input's reason; a zero divisor is `NM zero_denominator`, and a non-finite result `NM not_finite`.

## Calculators (`CALCULATOR_VERSION` 1)

- SIP, lump sum, SWP and STP run over the fund's real NAVs. An instalment is scheduled monthly on `day` (clamped to the month end) and trades at the first valid NAV on or after it. An STP transfer trades on the first date both funds have a NAV.
- Stamp duty of 0.005% applies to purchases from 2020-07-01. Redemptions are first in, first out. The final value uses the last valid NAV on or before the end date.
- XIRR solves for a zero net present value on a 365-day year, by bisection over (−99.99%, 10,000%); `null` when no rate there does.
- Exit loads, surcharge and securities transaction tax are not modelled. A simulation reads past NAVs; it is not a forecast.

## Capital-gains tax (`in-2024-07-23`)

For sales from 2024-07-23: equity-oriented funds pay 20% short term (12 months or less) and 12.5% long term on the financial year's net gain above ₹1.25 lakh, with 31 January 2018 grandfathering. Debt funds bought from 2023-04-01 pay the slab rate. Other units held over 24 months pay 12.5%, and otherwise the slab rate. Cess is 4%. A short-term loss is set off against the same year's long-term gain; nothing carries forward. The tax class comes from the category (equity: equity schemes and aggressive hybrid, arbitrage, equity savings; debt: debt schemes and conservative hybrid), or from the request when the category does not decide it. SIP and lump sum are taxed as if every unit were redeemed on the valuation date. Sales before 2024-07-23 are counted as not modelled.

## Known limits

- √252 understates volatility for funds that publish a NAV on every calendar day (liquid, overnight).
- Categories and names are AMFI's of 2026-10-23, because AMFI restates current labels for past dates.
- NAVs before 2023-04-01 come from the TigZig archive at 4 decimals.
- No TRI, TER, AUM or risk-free series, so there is no Sharpe ratio, beta or tracking error (MF-14).
- Series are not spliced across curated links (`plan_option_link`) in this version. A fund whose code changed shows a short history under its new code.
- Consistency and ranks use today's active funds only (survivorship bias).
- No benchmark TRI yet, so there is no beta, alpha, capture ratio or tracking error.
