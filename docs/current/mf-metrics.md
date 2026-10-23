# MF metrics method

The method behind every number in the MF screener and research API ([ADR-017](../architecture/adr/ADR-017-funds-etfs-holdings.md) MF-8, MF-11; [ADR-018](../architecture/adr/ADR-018-unified-screening.md)). Code: `backend/src/wickstreet/analytics/domain/` (`metrics.py`, `classify.py`, `fields.py`). Any change that alters a computed value, a category or a classification bumps `METHOD_VERSION`. A snapshot is stored once per (revision, method version), so two methods never mix.

## Versions

| Version | Date | Change | Status |
|---|---|---|---|
| 1 | 2026-10-23 | The method below, as proposed in the [Slice 2 plan](../plans/wickstreet-2/19-slice-2-mf-analytics.md) | Approved by the owner in the final plan review of 2026-10-23 |
| 2 | 2026-10-23 | The option rule only. The real-data spot check found growth options of unclaimed-dividend plans classed as IDCW ("Unclaimed IDCW Plan - Growth"), AMFI's rename of "Dividend Yield" to "IDCW Yield" inside fund names, "RetireInvest" read as "reinvest", and the misspelling "IDWC". v2 removes those fund and plan phrases before matching, matches `reinvest` as a word, and adds `idwc`. Active plan-options: `idcw` 4,583 → 4,551, `growth` 3,688 → 3,693, `unknown` 327 → 354 | Built and in use; awaits owner review |

Snapshot 1 (revision 2769, v1) stays stored; reads use v2.

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

## Known limits

- √252 understates volatility for funds that publish a NAV on every calendar day (liquid, overnight).
- Categories and names are AMFI's of 2026-10-23, because AMFI restates current labels for past dates.
- NAVs before 2023-04-01 come from the TigZig archive at 4 decimals.
- No TRI, TER, AUM or risk-free series, so there is no Sharpe ratio, beta or tracking error (MF-14).
- Series are not spliced across curated links (`plan_option_link`) in this version. A fund whose code changed shows a short history under its new code.
