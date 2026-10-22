# 10 — Phased Implementation Roadmap

> Part of the [Wickstreet 2.0 blueprint](README.md). Status: Proposed. Nothing in this roadmap starts until the owner accepts [ADD Amendment A2](../../../architecture/ADD-amendment-A2.md) and the phase's ADRs.

## 0. How every phase runs

- **Two tracks per phase.** *Build* uses synthetic fixtures and can start once the phase's ADRs are accepted. *Real data* waits for the owner's licence decision for each dataset ([04 §5](04-data-sources.md#5-owner-decisions-blocking-real-data-import)). A phase is **usable** when Build is done and real data is imported; it is **complete** only then.
- **Vertical slices.** Each increment is migration + domain + use case + endpoint + UI + tests, one local commit. No layer is built ahead of its use.
- **Gates.** Each phase ends with a review gate: E2E green, screenshots in light and dark at three widths, a report in `docs/history/audits/`, owner sign-off. Regression: the existing backend, Vitest and Playwright suites stay green (NFR-13).
- **Fixtures.** One synthetic company family (general, bank, NBFC template), one AMC with 6 schemes (equity, index, ETF, FoF, debt, hybrid), 3 disclosures each, and a TRI series. Synthetic names only (the `E2ECANDLE` precedent), excluded from production universes.

---

## Phase 1 — Stock Company Intelligence

| Item | Detail |
|---|---|
| User value | One page answers "what is this company, how good is its business, how does it compare" with every number traceable to a filing |
| Dependencies | A2 accepted; ADR-016 accepted; metric formulas ([03 §1.4](03-product-specs.md#14-metric-dictionary)) approved |
| Data | Financials, shares outstanding, industry classification (D-1). **Blocked for real data.** |
| Reuse | `Versioned` + history tables, `data_manifests`, PIT pattern, `import-eod` CLI pattern, `/stock/:symbol` route, Assessment panel |
| Architecture | Tables `companies`, `company_names`, `classification_*`, `financial_filings`, `financial_facts`, `line_items`, `share_count_observations`; `securities.company_id`; `domain/fundamentals/`; `PointInTimeFundamentals`; `METRIC_VERSION` in engine identity; `import-financials`, `import-shares`, `import-classification` |

**Increments**

1. Migration 0026 (identity + classification) + `import-classification` + company header on `/stock/:symbol`.
2. Migration 0027 (filings, facts, line items) + taxonomy seed + `import-financials` with reconciliation (§9 of [05](05-data-model-and-architecture.md)).
3. `PointInTimeFundamentals` + look-ahead tests.
4. Financials tab (grid, basis, period switch, restatement markers, as-of banner).
5. Shares + market cap + `MetricEngine` (all §1.4 metrics) + Overview metric strip + Ratios tab.
6. Peers tab (table, medians, outliers, scatter) + Fundamentals dock tab.
7. Strengths/watch points (owner-approved thresholds) + `/data` fundamentals card + freshness entries.

**Acceptance criteria**

- Every metric on fixtures matches a hand-computed spreadsheet value to the displayed precision (golden file, reviewed by the owner).
- Restated quarter: the latest view shows the restated value; an `as_of` before the restatement shows the original. Proven by test and screenshot.
- A filing published after `as_of` never appears (`LookAheadError` test on every read path).
- Bank-template company shows `NM` for ROCE/EV/EBITDA with the reason; no zero anywhere.
- Momentum25 outputs for every existing run are byte-identical before and after the phase (golden comparison).

**Tests:** domain unit tests per metric (positive, `NM`, `NA` cases); taxonomy completeness; reconciliation; PIT; API contract; Playwright journey "Search → Overview → Financials → Peers → Chart → Momentum25 → back".

**Performance:** overview ≤ 300 ms, financials ≤ 300 ms, peers ≤ 500 ms (warm P95); import of 10 years × 2,500 companies ≤ 10 min.

**Risks:** taxonomy mapping from a vendor format is the largest effort; bank/NBFC templates; corporate rename evidence (R3-B-31 rule: never infer). **Open:** supplier (D-1); thresholds for watch points.

---

## Phase 2 — Unified Stock Screener

| Item | Detail |
|---|---|
| User value | "ROCE > 20% AND profit growth > 15% AND RS > 80 AND Momentum25 qualified", today or on any past date, explained per row |
| Dependencies | Phase 1 Build; ADR-018 accepted |
| Data | Same as Phase 1 |
| Reuse | `ScreenerPanel`, `RangePill`, column sets, `saved_screens`, Studio registry pattern, strategy selector, historical screening |
| Architecture | `domain/screening/` (registry, AST, evaluator); `metric_snapshots`; `GET /screener/fields`, `POST /screener/run`; `SavedScreensV2`; presets in `docs/architecture/screens/` |

**Increments**

1. Field registry + AST validation + evaluator on the latest snapshot (stocks).
2. Server/browser parity for every V1 screen; switch the Momentum25 screener to the server; delete `applyFilters`.
3. Field picker, compound groups, missing-data line, relaxation hint, CSV export.
4. Saved screens V2 + presets.
5. Historical `as_of` screens through PIT ports, with provenance header.
6. Optional: fundamental rules in Strategy Studio via `FundamentalEngine` (research namespace only).

**Acceptance:** determinism golden (byte-identical); parity test green before deletion; historical screen on a fixture date excludes a later filing; the existing screener E2E suite passes unchanged.

**Performance:** warm run ≤ 300 ms; cold snapshot ≤ 5 s; historical new date ≤ 15 s.

**Risks:** semantic drift between client and server Momentum25 filters (mitigated by the parity gate). **Open:** whether fundamental rules enter Studio in this phase.

---

## Phase 3 — Mutual Fund and ETF Intelligence

| Item | Detail |
|---|---|
| User value | Find, understand and compare funds and ETFs by returns, risk, cost and consistency, in plain language |
| Dependencies | A2; ADR-017 accepted; fund formulas ([03 §2.5](03-product-specs.md#25-fund-metric-dictionary)) approved |
| Data | Scheme master, NAV, TER, exit loads, AUM, market-cap list, TRI, risk-free series (D-2, D-3). **Blocked for real data.** |
| Reuse | Chart slot and compare, screener (Phase 2), search dialog, watchlist, `benchmark_index_daily` |
| Architecture | `amcs`, `fund_schemes`, `scheme_benchmarks`, `fund_plans`, `nav_daily`, `fund_expense_ratios`, `fund_exit_loads`, `fund_aum`, `fund_managers`; `securities.instrument_type`; `benchmark_index_daily.kind`; `domain/funds/`; `PointInTimeFunds`; fund and ETF routes |

**Increments**

1. `instrument_type` migration + RS-universe golden test (ratings identical) + ETF tagging.
2. Scheme, plan, NAV tables + `import-schemes`, `import-nav`.
3. Fund metric engine + Performance tab + NAV chart with benchmark/category overlays.
4. Risk tab (plain language) + Costs tab + SIP/lump-sum simulator.
5. Fund screener tab + presets; mixed search (EQ/ETF/MF).
6. ETF page: price vs NAV, tracking, liquidity; ETF screener tab.
7. Compare funds (without holdings sections).

**Acceptance:** returns, rolling returns, drawdown, volatility, capture ratios and tracking error match an independent spreadsheet on fixtures to 1e-6; SIP XIRR matches spreadsheet XIRR; benchmark never silently a price index (test asserts the warning); RS ratings unchanged.

**Performance:** fund page ≤ 500 ms; rolling 3Y on 15 years of daily NAV ≤ 100 ms in the domain; compare ≤ 800 ms.

**Risks:** DB growth (NAV history); IDCW returns need distributions; scheme mergers and code changes. **Open:** AMFI permission; TRI licence; risk-free source.

---

## Phase 4 — Holdings and Overlap Intelligence

| Item | Detail |
|---|---|
| User value | See what a fund really owns, how it changed, which funds hold a stock, and how funds overlap; move fund → stock → chart → Momentum25 → back |
| Dependencies | Phases 1 and 3 Build; ADR-017 |
| Data | Portfolio disclosures (D-4). **Blocked for real data.** |
| Reuse | Company page, chart, Assessment panel, `from` chain, compare view |
| Architecture | `portfolio_disclosures`, `portfolio_holdings`; ISIN resolution job; `GET /funds/{id}/holdings`, `GET /stocks/{symbol}/held-by`; Held-by dock tab |

**Increments:** (1) tables + `import-holdings` (normalized contract + one AMC-layout template parser) + ISIN resolution report; (2) Holdings tab with changes; (3) held-by page and dock tab; (4) context bar and the signature journey; (5) overlap in compare; (6) historical disclosures via `as_of`.

**Acceptance:** a disclosure published after D is invisible at D; before the first disclosure exposure is `NA`; quantity-based change detection survives a split between disclosures; the signature-journey E2E passes with context restored at every step.

**Performance:** holdings tab ≤ 400 ms; held-by ≤ 300 ms; 5-fund overlap ≤ 200 ms domain.

**Risks:** per-AMC layouts; unresolved ISINs (unlisted, foreign, debt). **Open:** holdings supplier.

---

## Phase 5 — Scorecards and Portfolio Intelligence

| Item | Detail |
|---|---|
| User value | One private view of everything owned: value, XIRR, real exposure through funds, overlap, concentration, drift; descriptive scorecards |
| Dependencies | Phases 1–4 Build; ADR-019, ADR-020 accepted; scorecard calibration gate ([09 §5](09-scorecards.md#5-calibration-and-approval-gate)) |
| Data | The user's own transactions (**not blocked**); dividends and distributions for income |
| Reuse | Watchlist (becomes "lists"), corporate actions, traded-price rules, compare |
| Architecture | `portfolios`, `portfolio_transactions`, `import_batches`; `domain/portfolio/`, `domain/scorecards/`; portfolio routes; CAS parser |

**Increments:** (1) manual transactions + FIFO ledger + valuation + XIRR (usable with real data immediately for equities held, since prices exist); (2) CSV import with preview/undo; (3) CAS import; (4) look-through exposure + overlap + concentration; (5) drawdown on time-weighted series + drift/rebalance; (6) stock scorecards; (7) fund scorecards; (8) multiple watchlists including funds and ETFs.

**Acceptance:** look-through invariant property test; XIRR parity; no outbound network call in a network-disabled run; CAS password absent from logs and DB; scorecard sanity cases signed off.

**Performance:** portfolio analysis ≤ 1 s for 500 transactions and 20 funds.

**Risks:** CAS layout changes; privacy expectations. **Open:** scorecard approval; whether scorecards ship at all if the stability check fails.

---

## Phase 6 — Broader Research (subject to access rights)

Shareholding patterns and pledges, corporate announcements and filings list, sector dashboards (sector RS, breadth by sector — closes the empty market-context sector panel), bank-specific metrics, debt-fund credit and duration metrics. Each item needs its own data decision and a short plan before work starts. No commitment in this blueprint.

---

## Summary

| Phase | Build can start after | Real data needs | Gate |
|---|---|---|---|
| 1 Company | A2 + ADR-016 + formula approval | D-1 | Company research review |
| 2 Screener | Phase 1 Build + ADR-018 | D-1 | Parity + determinism |
| 3 Funds/ETFs | A2 + ADR-017 + formula approval | D-2, D-3 | Metric parity + RS unchanged |
| 4 Holdings | Phases 1, 3 Build | D-4 | Signature journey |
| 5 Portfolio/scores | Phases 1–4 Build + ADR-019/020 | none (portfolio core) | Invariant + privacy + calibration |
| 6 Broader | Per item | Per item | Per item |

Phases 1 and 3 can be built in parallel. Phase 5's portfolio core (increments 1–2) can ship before Phase 4 for direct equities, because prices already exist.
