# Wickstreet 2.0 — Analytics Completion Specification

> **Status: Accepted by the owner, 2026-10-23** ("Accept Doc 21 as Wickstreet 2.0's comprehensive analytics specification and proceed with implementation"; decisions in §8). The single acceptance baseline for analytics work after Slices 2 and 3. It consolidates the owner's analytics-expansion recommendation, the Analytics Completion Checklist (28 items) and the ten additions of the follow-up review. It maps each item against what is built ([doc 20](20-wickstreet-2.0-complete-mf-scope.md), [mf-metrics](../../current/mf-metrics.md)) and sets NAV analytics v4 as the next backend slice. A new analytics item enters through this doc, with a completion requirement, or not at all. The spec guides building and verification; it does not gate development.

## 1. Objective and completion standard

**Objective.** Comprehensive MF analytics on real Indian MF data that exceed Tickertape's. The engine must answer three questions well: which funds are consistently good, why they are good, and which combination serves a given investor.

**Each item has three states:**

| State | Meaning |
|---|---|
| **Implemented** | Code, unit and golden tests, and an API under `/api/v1/mf`. May run on synthetic data only |
| **Data-ready** | The real dataset it needs is loaded, with a coverage report, and the calculations are validated on it |
| **Complete** | Implemented and data-ready, and it meets every gate G1–G8 (§3) |

A registered field is not a usable dimension. A field counts toward completion only when its coverage on real data is reported (values, `NA` and `NM` by reason). An endpoint alone completes nothing.

**Tracker** (updated 2026-10-23, after v4; [as built](../../current/architecture.md#wickstreet-20-nav-analytics-v4)). Slices 2 and 3 delivered the base: 120 fields, the screener, trailing and rolling returns, annual returns, drawdown episodes, downside risk, ranks, consistency, the score, compare and the calculators. v4 adds 31 fields (151 in all), per-field coverage and 12 endpoints.

| Item | Implemented | Data-ready | Open |
|---|---|---|---|
| C1 Historical peer rankings | Yes | Yes | Survivorship reduced, not removed (§5) |
| C2 Rolling performance | Yes | Yes | — |
| C3 Advanced SIP | Yes | Yes | — |
| C4 Direct vs regular | NAV part | NAV: yes; TER: no | Cost drag needs E1 |
| C5 Drawdown | Yes | Yes | — |
| C6 Risk-return efficiency | Yes | Yes | — |
| C7 Correlation | Yes | Yes | — |
| C8 IDCW total return | No | No (E5) | E5 |
| C9 Classification | Partly | Yes | SEBI 2026 categories (Unclassified 1,102 → 111) and fund type done; categories as filed at past dates have no source |
| C10 Selection backtesting | Yes | Yes | — |
| C11 Investor-level attribution | No | No | Slice 6, E1 |
| C12 Benchmark analytics | No | Risk-free: yes; TRI: no | E3 |
| C13 Risk-free metrics | Yes | Yes (E2, RBI, 2016-07 to 2026-10) | Rates must be imported as RBI publishes them; stale after 35 days |
| C14–C21 | No | No | E1, E3–E7 ([doc 22](22-e1-e7-source-research.md)) |
| C22 Tax-aware analysis | Partly | Yes | Rules back to 2018-04-01 done; exit loads (E1), switching costs and post-tax comparison across funds not built |
| C23 Market regimes | Proxy | Yes | Index regimes need E3 |
| C24 Deterioration detection | Yes | Yes | — |
| C25–C28, C30 | No | — | Slice 6 |
| C29 Explainable rankings | Yes | Yes | — |

Gates for the v4 items: G1, G4, G6 and G8 met. G2: month-end ranks match an independent pandas rebuild from SQL rows, and the §5 limits are stated. G3: per-field coverage and `as_of` on every response; no separate calculation timestamp. G5: independent real-data checks cover C1, C3, C4, C5, C7, C10, C13 and C23. G7: measured against the Slice 3 baseline ([as built](../../current/architecture.md#wickstreet-20-nav-analytics-v4)); the event-loop stall grew from 75 ms to about 170 ms.

## 2. Capabilities

Columns: **Data** = what the item needs; **Ready** = whether that data is loaded today; **Built** = what Slice 3 already has; **Delivered in** = the slice that completes it. Datasets E1–E7 are in §4.

### P0 — Core NAV analytics and fund selection (0/11)

| # | Capability | Completion requirement | Data | Ready | Built | Delivered in |
|---|---|---|---|---|---|---|
| C1 | Historical peer rankings | Month-end ranks with point-in-time peer groups; quartiles; quartile transitions; persistence; survivorship correction within §5 limits (M1–M3) | NAV | Yes | Today's ranks only | v4 |
| C2 | Rolling performance | Rolling 1Y/3Y/5Y distributions with p10–p90 (M5); positive-return share; consistency across holding periods side by side | NAV | Yes | Partial: count, mean, median, min, max, `positive_share`; rolling series | v4 |
| C3 | Advanced SIP | Rolling SIP XIRR for every start month at fixed tenors; best and worst start; SIP drawdown; step-up variants (M9) | NAV | Yes | Partial: SIP with step-up, XIRR | v4 |
| C4 | Direct vs regular | Matched-plan return gap; long-term wealth difference (M4); exact cost drag | NAV; E1 for cost drag | Partly | — | v4; cost drag with E1 |
| C5 | Drawdown | `dd_now`, `dd_now_days` (M6); underwater series; recovery-time spread; longest time under water; unrecovered losses | NAV | Yes | Partial: deepest-fall episodes, worst 1M/3M/1Y | v4 |
| C6 | Risk-return efficiency | Downside-adjusted comparisons; peer-group frontier and its non-dominated set; category-relative risk scores | NAV | Yes | Partial: `ret_risk_3y`, `sortino_3y`, risk percentiles | v4 |
| C7 | Correlation | Full matrix in compare; average pairwise correlation of a chosen set; near-duplicates in the peer group (M7) | NAV | Yes | Partial: pairwise correlation in compare | v4 |
| C8 | IDCW total return | Returns with payouts reinvested; cash-payout history; growth-vs-IDCW comparison of the same scheme (M13) | E5 | No | — (IDCW plans show NAV return excluding payouts) | E5 |
| C9 | Classification | Fewer Unclassified funds; fund-type distinctions (index, ETF, FoF, closed-ended, interval); categories as filed at each date for past peer groups | NAV, AMFI master; as-filed categories (stored TigZig rows) | Partly | Partial: sibling categories; 1,102 active funds Unclassified | v4 |
| C10 | Selection backtesting | A strategy (a screen or the score) applied at each past month-end to the funds and data available then; returns against the category median; walk-forward with hold-out (M14) | NAV; C1 | Yes | — | v4 (after C1) |
| C11 | Investor-level attribution | Realised XIRR split into market return, contribution timing, fees and taxes (M17) | CAS; E1 for fees | No | — | Slice 6; fees with E1 |

### P1 — Benchmark, fund and holdings intelligence (0/11)

| # | Capability | Completion requirement | Data | Ready | Built | Delivered in |
|---|---|---|---|---|---|---|
| C12 | Benchmark analytics | TRI-relative return; alpha, beta, tracking error, information ratio; upside and downside capture | E2, E3 | No | — | E3 |
| C13 | Risk-free metrics | Sharpe and risk-free Sortino against a dated 91-day T-bill series | E2 | No | — | E2 |
| C14 | Fund costs | TER history; exit loads; expense drag; cost-aware comparisons and score | E1 | No | — | E1 |
| C15 | Fund profiles | AUM, manager tenure, scheme history, riskometer, fund characteristics | E1 (manager history has no candidate source) | No | Attributes from AMFI's master | E1 |
| C16 | Holdings intelligence | Overlap, top holdings, sector and market-cap exposure, concentration, style drift | E4; E7 for style | No | — | E4 |
| C17 | Debt intelligence | Duration, YTM, credit quality, issuer exposure, rate sensitivity where AMC files carry the fields | E4 | No | — | E4 |
| C18 | Debt liquidity and credit risk | Rating changes over time; duration changes; concentration; liquidity exposure from redemptions | E4 history | No | — | E4 |
| C19 | ETF and index-fund analysis | Tracking difference and error against the index; replication quality; liquidity and premium/discount for ETFs | E3; E6 for ETF trading | No | — | E3; ETF trading with E6 |
| C20 | Equity portfolio valuation | Weighted P/E, P/B, ROE, earnings growth; valuation trend; sector exposure (M15) | E4, E7 | No | — | E7 |
| C21 | Performance attribution | Returns explained by asset allocation, sector exposure, security selection and benchmark-relative contribution | E3, E4, E7 | No | — | E7 |
| C22 | Tax-aware analysis | Lot-level gains; STCG/LTCG by rule set on each sale date (M18); exit loads; switching costs; post-tax comparisons | NAV; E1 for exit loads | Partly | Partial: FIFO lots, tax under `in-2024-07-23` | v4; exit loads with E1 |

### P2 — Differentiating investment intelligence (0/8)

| # | Capability | Completion requirement | Data | Ready | Built | Delivered in |
|---|---|---|---|---|---|---|
| C23 | Market regimes | Fund behaviour in corrections, crashes, recoveries and other regimes (M8) | Labelled category-median proxy; E3 later | Proxy: yes | — | v4 (proxy); E3 adds index regimes |
| C24 | Deterioration detection | 12-month change in rank, rolling return, drawdown, volatility and consistency (M10) | NAV; C1 | Yes | — | v4 |
| C25 | Portfolio X-Ray | Real CAS import; transaction-aware XIRR; allocation; overlapping holdings; concentration | CAS; E4 for overlap | No | — | Slice 6; overlap with E4 |
| C26 | Portfolio optimisation | Personalised fund selection; model allocations; diversification; rebalancing scenarios | NAV; CAS; E4 improves it | Partly | — | Slice 6 |
| C27 | Stress testing | Historical crisis scenarios applied to the portfolio; sensitivity | CAS; C23 windows | No | — | Slice 6 |
| C28 | Goal-based analytics | Targets, contribution scenarios, horizons, probability of reaching a goal (M11) | NAV | Yes | — | Slice 6 |
| C29 | Explainable rankings | Each score part with its percentile, weight, peer count, missing reason and data-quality notes; penalties (M12) | NAV | Yes | Partial: score parts are stored fields | v4 |
| C30 | Advanced construction | Scenario simulation (M11), contribution optimisation, efficient allocations, sensitivity analysis | NAV; CAS | Partly | — | Slice 6 |

## 3. Quality gates (0/8)

Every capability meets all eight before it is Complete.

| # | Gate | Today | v4 adds |
|---|---|---|---|
| G1 | Real data | Real 22.27M-row store; opt-in real-data tests; synthetic data only in automated tests and benchmarks | Real-data tests for each new field and view |
| G2 | Historical correctness | No rank history yet; survivorship bias and restated categories documented | Tests that a value at date t reads only data on or before t and only funds alive at t. Each historical view states the §5 limits that apply |
| G3 | Methodology, provenance, coverage | `METHOD_VERSION`, mf-metrics.md, NA/NM reasons, anchors, snapshot revision | Per-field coverage in `/screener/fields` (values, NA and NM by reason); calculation date and data freshness in each response; source per period |
| G4 | Integration | `/api/v1/mf` routes used by the screener | Every item through the shared API; Slice 4 UI and Slice 5 agent call the same services, never their own formulas |
| G5 | Independent validation | Unit, golden and real-data tests; suite 1,353 | Golden tests per formula; an independent recompute (separate code path) of sampled real funds; boundaries (5 peers, gaps, ties, first window) |
| G6 | Determinism | Byte-identical real recompute test | The same test over every v4 field and view; no random draws (M11) |
| G7 | Performance | Baseline (Slice 3, real store): compute 102 s / 404 MB; presets ~18 ms; event-loop stall ≤ 75 ms | v4 benchmarked on the complete real dataset and reported against the baseline: compute, memory, screen, each new view, a backtest run |
| G8 | Delivery | Coverage report, docs, local commits | This doc's tracker updated: each item's Implemented and Data-ready state |

## 4. Datasets

Each follows the Slice 1 pattern: an import contract, raw files kept, append-only revisions, reconciliation, and a rights-register grant (fails closed). E1–E4 are from doc 20 §4; E5–E7 are new.

| # | Dataset | Unlocks | Candidate source |
|---|---|---|---|
| E1 | TER, AUM, exit load, minimums, managers, riskometer, benchmark name | C4 cost drag, C11 fees, C14, C15, C22 exit loads | AMFI TER and AUM disclosures; AMC factsheets and scheme documents |
| E2 | Risk-free series (91-day T-bill) | C12, C13 | RBI |
| E3 | Benchmark TRI history; each scheme's benchmark over time | C12, C19, C21, C23 | NSE Indices, BSE indices (terms restrict automated collection) |
| E4 | Monthly portfolio disclosures, equity and debt | C16–C18, C20, C21, C25 overlap | Each AMC's monthly files |
| E5 | IDCW payout history (amount per unit, record date) | C8 | AMC IDCW histories; AMFI to check |
| E6 | ETF exchange prices, volumes, iNAV | C19 ETF trading | NSE, BSE (terms restricted; a known release blocker) |
| E7 | Company fundamentals and sector classification for securities held | C16 style, C20, C21 | Not yet identified. Doc 20 puts equity fundamentals in 3.0 (M15) |

## 5. Data limits on history

These cap how much survivorship bias C1, C10 and C24 remove. Each historical view states them.

- **Restated categories.** AMFI writes today's category for past dates. A fund that changed category in 2018 ranks in its new category for 2018. C9's as-filed categories reduce this.
- **Dead funds.** Many closed funds carry pre-2018 labels, so they are Unclassified and drop out of every group.
- **No splice.** A fund whose code changed shows a short history under its new code (`plan_option_link` not spliced).
- **As-filed names.** TigZig has per-row names and categories; they are not stored.
- **Usable period per lookback.** NAVs start 2016-10-16 and end 2026-10-22. The usable signal period depends on the lookback, and evaluation needs the forward horizon after it:

  | Lookback | First signal | Last signal with a 12-month forward return |
  |---|---|---|
  | 1Y (M2) | 2018-06-30 | 2025-09-30 |
  | 3Y (M2) | 2019-10-31 | 2025-09-30 |

  These periods span the 2018 mid- and small-cap fall, the 2020 crash and recovery, the 2022 rate-rise fall and the 2024–25 correction. Each backtest result states its exact signal period, horizon and the market windows it spans (dated from the C23 proxy), not a blanket claim either way.

## 6. Method decisions (default in bold)

Each point changes computed values, so v4 bumps `METHOD_VERSION` to 4.

| # | Decision | Default |
|---|---|---|
| M1 | Peer group at a past month-end | **Canonical category × plan × option, funds with a valid NAV within 7 days of that date** (alive then, not only alive now) |
| M2 | Rank history: metrics, dates, start | **Trailing 1Y return and 3Y CAGR at each month-end. 1Y ranks from 2018-06-30 (after SEBI's recategorisation); 3Y ranks from 2019-10-31.** 5 peers minimum, as today |
| M3 | Persistence; consistency | **`q1_share_3y`, `quartile_now`, `quartile_1y_ago`, `quartile_change_1y`; per-category 12-month quartile transition matrix. `consistency_3y` switches to point-in-time medians**, which changes existing values and the score |
| M4 | Direct–regular pair and gap | **Same AMC, scheme name and option; one active direct and one active regular plan. Gap = direct 3Y CAGR − regular 3Y CAGR; wealth difference on ₹10 lakh over 10 years. Labelled "observed NAV gap, not TER"** until E1 |
| M5 | Rolling percentiles | **p10, p25, p75, p90 by nearest rank, as for VaR** |
| M6 | Current drawdown | **`dd_now` = end NAV ÷ running peak − 1; `dd_now_days` = days since that peak** |
| M7 | Near-duplicate | **Same peer group, daily-return correlation ≥ 0.95 over 3Y common dates (≥ 500 days); `near_duplicates` count and a list view** |
| M8 | Regimes | **Owner decision: explicitly labelled proxies are allowed.** v4 dates regimes from a category-median index, labelled as a proxy built from fund NAVs, never as an official index. E3 adds index regimes |
| M9 | Rolling SIP | **₹10,000 monthly on day 1; tenors 3Y and 5Y; every start month with a full tenor; step-up 0%, 5%, 10% a year;** SIP calculator rules |
| M10 | Deterioration signals | **12-month change in the category percentile of `ret_1y`, `vol_3y`, `mdd_3y`, `consistency_3y`, plus `quartile_change_1y`. No combined flag**; a screen combines them |
| M11 | Simulation (C28, C30) | **Owner decision: both.** Deterministic historical scenarios over every stored window, and Monte Carlo with a seed that is part of the request and the response. Same inputs and seed give the same result |
| M12 | Score penalties | **None.** A penalty (for example, for short history) is an owner method change |
| M13 | IDCW payouts | **Owner decision: actual sourced distribution records (E5) only. Never infer payouts from NAV jumps** |
| M14 | Backtest protocol | **Strategies are screens over point-in-time fields; monthly rebalance; equal weight; NAV returns (net of TER); no tax; compared with the category median; walk-forward with a hold-out from 2024-01; every result carries the §5 limits** |
| M15 | Equity fundamentals scope | **Owner decision: fund-level weighted P/E, P/B, ROE and valuations (C20) are 2.0; individual-stock research stays 3.0.** E7 is loaded only for securities funds hold |
| M16 | Code splice | **Splice `plan_option_link` in v4**, before rank history |
| M17 | Investor attribution | **Market = time-weighted return of the holdings; timing = XIRR − time-weighted return; fees = TER drag (E1) plus the direct–regular gap; taxes = pre-tax XIRR − post-tax XIRR** |
| M18 | Tax rule history | **Add rule sets back to 2018-04-01** (LTCG on equity from 2018-04-01; debt change from 2023-04-01), so post-tax comparisons cover the stored history |

## 7. Order

1. **v4** (NAV only; built 2026-10-23), in this order: splice (M16; not built, `plan_option_link` has no rows) and classification (C9) → historical ranks and point-in-time consistency (C1) → direct vs regular (C4) → rolling, drawdown, SIP, frontier, correlation (C2, C3, C5–C7) → tax rule history (C22 part) → deterioration and explanation (C24, C29) → backtesting (C10). It completes C1–C3, C5–C7, C9, C10, C23 (proxy), C24 and C29.
2. **Slice 4 UI: paused** by the owner ("Do not build UI yet"). When it starts, it reads the same `/api/v1/mf` API; v4 added endpoints and new keys, and removed or renamed none.
3. **In parallel, data enrichment E1–E7** (D5): research, select and integrate sources as independent workstreams. They never delay NAV analytics or the UI. Each dataset still needs its rights-register grant before ingestion. Priority within the workstream: E2 (cheap; C13), E3 and E4 (largest research gains), E1, E5, E7, E6.
4. **Slice 6** (portfolio, attribution, optimisation, stress, goals) and Slice 5 (agent) follow.

## 8. Owner decisions (2026-10-23)

| # | Decision |
|---|---|
| D1 | v4 scope approved |
| D2 | Slice 4 UI starts now with Codex; v4 analytics in parallel. **Superseded the same day:** "Do not build UI yet." UI work is paused |
| D3 | M1–M18 defaults kept, with the owner's decisions on M8, M11, M13 and M15 (§6). Remaining definitions stay consistent with the existing method |
| D4 | G7: measured Slice 3 performance is the baseline; v4 is benchmarked on the complete real dataset |
| D5 | E1–E7: research, select and integrate real-data sources independently; never block NAV analytics or UI work |
