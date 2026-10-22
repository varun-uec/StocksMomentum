# 03 — Product Specifications: Stocks, Mutual Funds, ETFs

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Every formula here is **financial methodology** and needs owner approval before code (ADR-016, ADR-017). Screens are in [07](07-ux-flows-and-wireframes.md); data sources in [04](04-data-sources.md).

Conventions used on this page:

- **₹ cr** is the display unit for company amounts. Storage is rupees.
- **TTM** is the sum of the latest four quarters visible at `as_of`. If one quarter is missing, TTM is `NA (missing quarter)`. TTM is never built from a 9M + Q mix unless the Q4 filing gives Q4 directly; derived Q4 (FY − 9M) is allowed and flagged `derived`.
- **Basis.** Consolidated when filed for the period, else standalone. The basis used is shown next to every number. A user can force standalone.
- **States.** `NM` = not meaningful (reason shown). `NA` = an input is missing (reason shown). Never zero.
- **Rounding.** Ratios to 1 dp, percentages to 1 dp, amounts to the nearest ₹0.01 cr below ₹100 cr and ₹1 cr above. Rounding happens in display only.

---

## 1. Stocks — Company Intelligence

### 1.1 Company page: sections

One page per company at `/stock/:symbol`, tabbed. The existing score and analysis content moves under the **Momentum25** and **Chart** tabs without change.

| Tab | Content | Default | Data |
|---|---|---|---|
| **Overview** | Identity (name, symbol, ISIN, sector › industry, listing date, former names); price and 52-week range; key metrics strip (Market cap, PE, PB, ROCE, ROE, Debt/Equity, Sales growth 3Y, Profit growth 3Y); Momentum25 status chip; "Strengths / Watch points" (§1.6); "Held by N funds" (Phase 4); data freshness line | Visible | Fundamentals, bars, Momentum25 run |
| **Financials** | Income statement, balance sheet, cash flow; Quarterly / Half-yearly / Annual; Consolidated / Standalone; up to 12 quarters or 10 years; YoY and QoQ change columns; restatement markers; "as filed on" per column | Quarterly, consolidated, 8 periods | `financial_filings`, `financial_facts` |
| **Ratios** | Metric dictionary values over time (§1.4), each as a small multiple with the industry median line | 10 years annual | Metric engine |
| **Peers** | Peer table (§1.5), scatter (any two metrics), outliers, data gaps | Industry level | Snapshot |
| **Chart** | The chart workspace in-page with the symbol loaded; "Open full chart" keeps context | — | Existing |
| **Momentum25** | Today's Assessment panel, rule matrix, history (existing `/stock/:symbol` content) | — | Existing |
| **Research** | Historical screening hits for this stock, Studio evaluations that held it, as-of replay | — | Existing |
| **Filings** (Phase 6) | Result filings, shareholding pattern, announcements links | — | Phase 6 |

### 1.2 Financial statements

- **Rows** come from the canonical taxonomy (`line_items`), in three templates: `general` (Ind AS Schedule III Division II), `bank` (RBI format), `nbfc` (Division III). `insurance` shows the filed statement as reported, with no derived metrics in Phase 1.
- **Collapsed by default:** top-level rows only (Revenue from operations, Other income, Total income, Total expenses, EBITDA *(derived, marked)*, Finance costs, Depreciation, PBT, Tax, PAT, PAT to owners, EPS). Expand shows children.
- **Every cell** links to its filing: period, basis, `published_at`, audit status, source reference. A restated value shows a dot; the tooltip shows the original and restated values and both publication dates.
- **As-of view.** With `as_of` set (from replay or a historical screen), the grid shows only what was public at that time. Restatements published later are hidden, and the banner says "Showing financials as published on or before 12 Mar 2022".
- **Period alignment.** Columns are fiscal periods (India FY Apr–Mar). A company with a non-March year end shows its own periods; peer comparison aligns on TTM, never on fiscal labels.

### 1.3 Shares and market cap

- **Shares outstanding at date D** = the latest `share_count_observations` row with `published_at ≤ D`, multiplied by the split and bonus factors of corporate actions with ex-date after the observation date and on or before D.
- **Market cap (₹ cr)** = traded close at D × shares outstanding at D. Traded close, not adjusted close, because shares are the actual count at D.
- **Size bucket** = the AMFI list in force at D (rank 1–100 Large, 101–250 Mid, 251+ Small) from `classification_assignments`. If no list is imported, the bucket is `NA (AMFI list not imported)`. Wickstreet does not compute its own bucket.

### 1.4 Metric dictionary

All metrics read only filings visible at `as_of`. "Avg" means the mean of the opening and closing balance for the measured period; if the opening balance is not visible, the closing balance is used and the value carries `closing-balance only`.

| ID | Name | Formula | Unit | NM when | Templates |
|---|---|---|---|---|---|
| `mcap` | Market cap | close × shares (§1.3) | ₹ cr | — | all |
| `pe_ttm` | PE | mcap ÷ TTM PAT to owners | × | TTM PAT ≤ 0 | all |
| `pb` | PB | mcap ÷ owners' equity (latest balance sheet) | × | equity ≤ 0 | all |
| `peg` | PEG | `pe_ttm` ÷ (3Y CAGR of annual EPS × 100) | × | PE NM, CAGR ≤ 0, or CAGR NM | general |
| `ev` | Enterprise value | mcap + total borrowings − cash and cash equivalents − other bank balances | ₹ cr | — | general |
| `ebitda_ttm` | EBITDA (operating) | revenue from operations − total expenses + finance costs + depreciation and amortisation (other income excluded) | ₹ cr | — | general |
| `ev_ebitda` | EV/EBITDA | `ev` ÷ `ebitda_ttm` | × | EBITDA ≤ 0 | general |
| `ps_ttm` | Price/Sales | mcap ÷ TTM revenue from operations | × | revenue ≤ 0 | general |
| `div_yield` | Dividend yield | Σ cash dividends per share with ex-date in the last 365 days × shares ÷ mcap | % | — | all (Phase 5, needs dividends) |
| `roe` | ROE | TTM PAT to owners ÷ avg owners' equity × 100 | % | avg equity ≤ 0 | all |
| `roce` | ROCE | TTM EBIT ÷ avg capital employed × 100; EBIT = PBT + finance costs; capital employed = total equity + total borrowings | % | capital employed ≤ 0 | general |
| `roic` | ROIC | TTM EBIT × (1 − t) ÷ avg invested capital × 100; t = TTM tax ÷ TTM PBT clamped to [0, 0.40]; invested capital = total equity + total borrowings − cash and equivalents | % | PBT ≤ 0 or invested capital ≤ 0 | general |
| `roa` | ROA | TTM PAT ÷ avg total assets × 100 | % | — | bank, nbfc (primary), general |
| `op_margin` | Operating (EBITDA) margin | `ebitda_ttm` ÷ TTM revenue from operations × 100 | % | revenue ≤ 0 | general |
| `net_margin` | Net margin | TTM PAT ÷ TTM revenue from operations × 100 | % | revenue ≤ 0 | general |
| `de` | Debt/Equity | total borrowings ÷ total equity | × | equity ≤ 0 | general |
| `int_cover` | Interest coverage | TTM EBIT ÷ TTM finance costs | × | finance costs = 0 (shown as "debt-free") | general |
| `cfo_fy` | Cash from operations | CFO, latest FY | ₹ cr | — | general |
| `fcf_fy` | Free cash flow | CFO − purchase of PP&E and intangibles, latest FY | ₹ cr | — | general |
| `cfo_pat` | Cash conversion | Σ CFO ÷ Σ PAT, last 3 FY | × | Σ PAT ≤ 0 | general |
| `sales_g_q` | Sales growth (quarter YoY) | rev(q) ÷ rev(q − 4) − 1 | % | base ≤ 0 | all |
| `sales_g_ttm` | Sales growth (TTM YoY) | TTM rev ÷ TTM rev 4 quarters earlier − 1 | % | base ≤ 0 | all |
| `sales_cagr_3y`, `_5y` | Sales CAGR | (rev(FY) ÷ rev(FY − n))^(1/n) − 1 | % | either value ≤ 0 | all |
| `profit_g_q`, `profit_g_ttm`, `profit_cagr_3y`, `_5y` | Profit growth | as sales, on PAT to owners | % | base ≤ 0 | all |
| `eps_ttm` | EPS (TTM) | Σ diluted EPS of the TTM quarters, adjusted for later splits and bonuses | ₹ | — | all |
| `nim`, `gnpa`, `nnpa`, `car` | Bank metrics | as filed (bank template disclosures) | % | — | bank (Phase 1 if in source, else Phase 6) |

Bank and insurance revenue lines differ: for `bank`, "revenue" in growth metrics means total interest earned + other income, and the label says so.

### 1.5 Peer intelligence

- **Peer set.** Companies in the same industry (classification level 3 of the imported scheme) at `as_of`, with a visible filing in the last 6 months. If fewer than 5, widen to the sector, and say so.
- **Table.** Name, mcap, PE, PB, EV/EBITDA, ROCE, ROE, op margin, sales and profit CAGR 3Y, D/E, RS rating, Momentum25 status. Default sort: mcap desc, tie-break `security_id`.
- **Per metric:** peer median, the company's percentile within the peer set (average rank for ties), and an **outlier** marker for values outside [Q1 − 3·IQR, Q3 + 3·IQR] of the peer set.
- **Gaps.** A peer with `NA` shows the reason. The footer counts peers excluded from each median.
- **Scatter.** Any two metrics, log scale option, the company highlighted, median cross-hairs. Clicking a dot opens that company with `from` set to this peer view.

### 1.6 Strengths and watch points

Plain-language facts, generated by fixed rules. They describe; they do not recommend. Thresholds are editorial and listed in one config file, owner-approved before release.

| Rule | Text (example) |
|---|---|
| `roce ≥ 20` for each of 3 FY | "ROCE above 20% in each of the last 3 years" |
| `de ≤ 0.1` | "Almost no debt (Debt/Equity 0.04)" |
| `cfo_pat < 0.5` over 3 FY with Σ PAT > 0 | "Cash from operations is less than half of reported profit over 3 years" |
| `int_cover < 1.5` | "Operating profit covers interest less than 1.5 times" |
| balance-sheet identity flag | "The latest filing does not balance; balance-sheet metrics are hidden" |
| restated in last 8 quarters | "Results for Q2 FY25 were restated on 14 Feb 2025" |

---

## 2. Mutual Funds — Fund Intelligence

### 2.1 Units of analysis

- **Scheme**: the fund (one portfolio, one manager team, one category).
- **Plan-option**: Direct/Regular × Growth/IDCW. Each has its own NAV and TER.
- **Default view** is Direct Growth. Regular is one click away, with the cost difference shown. Returns are always computed on Growth NAVs. IDCW plan returns need distributions (`fund_distributions`); until imported they show `NA (needs distributions)`.

### 2.2 Fund discovery and screening

Covered by the unified screener ([06](06-unified-screener.md)). Fund presets:

| Preset | Filter |
|---|---|
| Consistent large-cap funds | category = Large Cap, plan = Direct Growth, rolling 3Y return beat benchmark in ≥ 70% of windows, age ≥ 5Y |
| Low-cost index funds | is index fund, TER ≤ 0.25%, tracking error 1Y ≤ 0.2% |
| Shallow drawdown hybrids | asset class = hybrid, max drawdown 5Y ≥ −15% |
| Liquid with lowest cost | category = Liquid, TER ≤ category median |

### 2.3 Fund page: sections (`/fund/:planId`)

| Tab | Content |
|---|---|
| **Overview** | Name, AMC, category, plan/option switcher, benchmark, riskometer level (as disclosed), NAV and date, AUM and date, TER (Direct and Regular side by side), exit load in words ("1% if sold within 12 months"), minimum SIP/lump sum, managers and tenure, launch date, objective; summary strip: 1Y/3Y/5Y return vs category median and benchmark |
| **Performance** | NAV chart (growth of ₹10,000) with benchmark TRI and category median overlays; trailing returns table; calendar-year returns; rolling returns (distribution chart + "beat benchmark in X% of 3-year periods") |
| **Risk** | Volatility, max drawdown with dates and recovery time, Sharpe, Sortino, beta, upside/downside capture, all with plain-language labels and category percentile |
| **Holdings** | Latest disclosure (date and age), top holdings, sector, market-cap split, asset mix, concentration (top-10 weight, effective number of holdings), change since previous disclosure (added, exited, increased, reduced). A date picker switches to any stored disclosure. |
| **Costs** | TER history, Direct vs Regular gap, exit load history |
| **SIP & lump sum** | Simulator (§2.6) |
| **Compare** | Opens the compare view with this fund pinned |

### 2.4 Plain language

Each risk metric shows a plain name first and the technical name second, with a one-line "what this means":

| Plain name | Technical | One line |
|---|---|---|
| Ups and downs | Annualised volatility | "How much the NAV usually moves in a year" |
| Worst fall | Maximum drawdown | "The biggest drop from a peak, and how long it took to recover" |
| Return per unit of risk | Sharpe ratio | "Extra return over a risk-free rate for each unit of ups and downs" |
| Return per unit of bad risk | Sortino ratio | "Like Sharpe, counting only the falls" |
| Market sensitivity | Beta | "1.0 moves with the benchmark; above 1 moves more" |
| Up-market / down-market capture | Capture ratios | "Of each 1% the benchmark gained (lost) in a month, how much the fund gained (lost)" |
| How often it beat its benchmark | Rolling outperformance | "Share of all 3-year periods in which the fund beat its benchmark" |

### 2.5 Fund metric dictionary

NAV series are Growth-option NAVs. "Start NAV" for a window is the NAV on the start date or the latest NAV before it. Windows end at `as_of`.

| ID | Formula | Notes |
|---|---|---|
| `ret_abs_{1m,3m,6m,1y}` | NAV_end ÷ NAV_start − 1 | Not annualised for windows ≤ 1Y |
| `ret_cagr_{3y,5y,7y,10y,si}` | (NAV_end ÷ NAV_start)^(365 ÷ days) − 1 | `si` = since the first stored NAV; labelled "since 2006-04-03 (first NAV stored)" when that differs from launch |
| `ret_cy_{yyyy}` | Calendar-year return | |
| `roll_{1y,3y,5y}_{min,median,max}` | CAGR for every window ending on each NAV date in the lookback (default 10Y, or since inception) | Needs ≥ 1 full window; else `NA` |
| `roll_3y_beat_bm_pct` | Share of rolling 3Y windows where fund CAGR > benchmark TRI CAGR for the same dates | `NA` without TRI |
| `roll_3y_beat_cat_pct` | Share of rolling 3Y windows above the category median | Category median from the same dates, same plan type |
| `vol_3y` | Sample standard deviation of daily simple returns × √252 | 252 is fixed; stated on screen |
| `mdd_{3y,5y,si}` | min over t of (NAV_t ÷ max_{s≤t} NAV_s − 1) | Plus peak date, trough date, recovery date or "not recovered" |
| `sharpe_3y` | (CAGR_3y − rf) ÷ `vol_3y` | rf = mean 91-day T-bill yield over the window. `NA (risk-free series not imported)` until it is |
| `sortino_3y` | (CAGR_3y − rf) ÷ downside deviation (daily returns below rf_daily, × √252) | Same rf rule |
| `beta_3y` | cov(fund, benchmark daily returns) ÷ var(benchmark) | Benchmark TRI; `NA` without TRI |
| `alpha_3y` | Jensen's alpha, annualised | Shown under "Advanced" only |
| `capture_up_3y`, `capture_down_3y` | Mean fund monthly return ÷ mean benchmark monthly return, over months where the benchmark rose (fell) | |
| `te_1y` | Sample SD of daily (fund − index TRI) returns × √252 | Index funds and ETFs |
| `td_1y` | Fund 1Y return − index TRI 1Y return | Index funds and ETFs |
| `ter` | Latest TER for the plan | % per year |
| `ter_gap` | Regular TER − Direct TER | |
| `aum` | Latest month-end AUM, scheme level | ₹ cr |
| `top10_wt`, `eff_holdings` | Σ top-10 equity weights; 1 ÷ Σ wᵢ² over equity holdings (weights rescaled to the equity sleeve) | From the visible disclosure |
| `cat_rank_{1y,3y,5y}` | Rank of the plan's return in its SEBI category among plans of the same type (Direct or Regular) | Shown as "4 of 31" |
| `age_years` | (as_of − launch) ÷ 365.25 | |

**Benchmark rule.** Fund and ETF comparisons use the TRI of the scheme's tier-1 benchmark in force on each date. A price index is never used silently. If only a price index is available, the comparison is shown as "vs price index (excludes dividends)" with a warning.

### 2.6 SIP and lump-sum simulation

- **Inputs:** plan, amount, frequency (monthly; weekly later), day of month, start and end dates, optional step-up %.
- **Rules:** an instalment buys at the NAV of the first NAV date on or after the scheduled day. Units = amount × (1 − stamp duty) ÷ NAV, with stamp duty 0.005% for purchases from 2020-07-01 *(to verify against the Indian Stamp Act notification before release)*. Exit load and tax are excluded and the screen says so.
- **Outputs:** invested amount, current value, absolute gain, XIRR (§4 of [08](08-holdings-overlap-portfolio.md)), a value-over-time chart against the same cash flows into the benchmark TRI (if imported).
- A simulation is deterministic: same plan, inputs and `data_version` give the same output.

### 2.7 Compare (`/compare/funds?plans=…`)

Up to 5 plans. Sections, each with a one-line summary sentence above the table ("Fund B cost 0.6% a year less and fell less in 2020"):

1. Snapshot: category, AUM, TER, age, manager tenure.
2. Returns: trailing, calendar-year, rolling 3Y distribution (box plot).
3. Risk: plain-language table, category percentiles.
4. Costs: TER and exit load.
5. Holdings: sector and market-cap split side by side; overlap matrix (§3 of [08](08-holdings-overlap-portfolio.md)); common holdings list with each fund's weight.

Comparisons warn when plans differ in plan type (Direct vs Regular) or when disclosure dates differ by more than 31 days.

---

## 3. ETFs

An ETF is a **listed security** (`instrument_type = 'ETF'`) linked to a fund plan. It has both exchange bars and a NAV. It is not interchangeable with an equity or with an unlisted fund plan.

| Section | Content | Availability |
|---|---|---|
| Overview | Underlying index, AMC, TER, AUM, creation unit (if disclosed), listing date | Scheme master |
| Price vs NAV | Close and NAV per day; premium/discount = close ÷ NAV − 1 | End of day only. Intraday iNAV is out of scope (EOD product). |
| Tracking | Tracking difference (1Y, 3Y) and tracking error (1Y) vs index TRI (§2.5) | Needs TRI; else `NA` |
| Liquidity | 20-day median traded value, median daily volume, days with no trade in last 60 sessions | From bhavcopy bars |
| Bid-ask spread | Not available from EOD files | Shown as "not available on end-of-day data" |
| Holdings and exposure | As for funds (disclosure-based) | Phase 4 |
| Chart | Full chart workspace; indicators work as for any listed security | Existing |
| Compare | ETF vs ETF on the same index (cost, tracking, liquidity); ETF vs index fund (cost, tracking) | Phase 3/4 |

**Exclusions.** ETFs never enter the Momentum25 universe or RS ratings. The stock screener excludes them; the ETF screener tab lists them. A user who opens an ETF chart sees the Momentum25 panel replaced by the ETF panel.
