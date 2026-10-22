# ADD Amendment A2 — Wickstreet 2.0: Investment Intelligence

> **Status:** Proposed (2026-10-22). The ADD text below takes effect only when the owner approves this amendment. Until then, A1 §4 governs scope.
> **Applies to:** ADD §1, §2, §3, §4, §6, §26, §27 (as amended by A1)
> **Blueprint:** [docs/history/plans/2026-10-22-wickstreet-2/](../history/plans/2026-10-22-wickstreet-2/README.md)

## §1 Executive Summary — add after the A1 paragraphs

**Wickstreet 2.0** adds company fundamentals, mutual funds, ETFs, a unified screener, descriptive scorecards and a private portfolio view to the charting workspace. It stays one self-hosted workstation. Momentum25 stays the momentum engine and keeps its methodology unchanged. Every new number is deterministic, point in time and traceable to a dated source.

## §2 Functional Requirements — add rows

| ID | Requirement | In scope | Notes |
|----|-------------|-----|-------|
| FR-15 | Fundamental screening | ✅ (was deferred) | Through the unified screener (FR-27). The production strategy keeps `FundamentalEngine` disabled. |
| FR-26 | Company research: overview, statements, ratios, peers | ✅ | ADR-016 |
| FR-27 | Unified screener: stocks, funds, ETFs; compound filters; saved screens; presets; historical `as_of` | ✅ | ADR-018 |
| FR-28 | Mutual-fund research: performance, risk, costs, SIP simulation, compare | ✅ | ADR-017 |
| FR-29 | Fund holdings, changes, "held by", overlap, fund → stock journey | ✅ | ADR-017 |
| FR-30 | ETF research: NAV vs price, tracking, liquidity | ✅ | ADR-017, end of day only |
| FR-31 | Portfolio: transactions, imports, valuation, XIRR, look-through, overlap, drift | ✅ | ADR-019 |
| FR-32 | Descriptive scorecards | ✅ after methodology approval | ADR-020 |
| FR-33 | Source-neutral data import contracts | ✅ | ADR-021 |

## §3 Non-Functional Requirements — add

- **Publication-time integrity (NFR-15):** every source fact carries a business date and a publication time. Point-in-time reads filter on publication time and raise `LookAheadError` on any later read.
- **Value states (NFR-16):** a metric is a value, `NM` or `NA`, each with a reason. No missing value becomes zero.
- **Research page responsiveness (NFR-17):** warm P95 targets in blueprint 05 §10; NFR-11 unchanged.
- **Portfolio privacy (NFR-18):** portfolio data never leaves the machine.

## §4 Product Scope — replace the A1 text

**In scope:** everything in A1 §4, plus listed Indian equities' fundamentals, open-ended mutual funds, ETFs, the unified screener, descriptive scorecards and a single-owner portfolio, all on end-of-day data.

**Out of scope:** AI agents; scripting, indicator or formula languages; user-defined executable rules; intraday and real-time data (including iNAV and bid-ask spreads); order placement, execution and broker integration; social features; a hosted multi-user service; composite investment scores without approved calibration; analyst forecasts; any dataset without a recorded supplier decision (ADR-021).

## §6 Deferred Features — change one row

| Deferred capability | Pre-built extension point |
|---|---|
| ~~Fundamentals~~ → **Moves into scope (FR-15, FR-26).** | `FundamentalEngine` slot; `PointInTimeFundamentals` |

## §26 ADR table — add rows

| ADR | Decision | Rationale (rejected alt) |
|---|---|---|
| 016 | Fundamentals stored by publication time; restatements append | Point-in-time correctness (vs vendor ratio tables, overwrite) |
| 017 | Funds, ETFs, holdings disclosures; TRI benchmarks | Honest dates and costs (vs funds as securities, latest holdings for all dates) |
| 018 | Unified screening in the domain over in-memory snapshots | One explainable code path (vs dynamic SQL, browser filters) |
| 019 | Portfolio ledger from transactions; look-through without double counting | One source of truth (vs stored holdings) |
| 020 | Descriptive scorecards, no composite | No unearned claims (vs star ratings) |
| 021 | Source-neutral import contracts; no default fetchers | Licence terms (vs scrapers, unofficial APIs) |

## §27 Roadmap — add milestones

| Milestone | Deliverable | Verification |
|---|---|---|
| **W1 Company intelligence** | Blueprint phase 1 | Metric golden file; restatement and look-ahead tests; Momentum25 outputs unchanged |
| **W2 Unified screener** | Phase 2 | Server/browser parity; determinism golden |
| **W3 Funds and ETFs** | Phase 3 | Metric parity with an independent spreadsheet; RS ratings unchanged |
| **W4 Holdings and overlap** | Phase 4 | Holdings look-ahead tests; signature-journey E2E |
| **W5 Scorecards and portfolio** | Phase 5 | Look-through invariant; privacy tests; scorecard approval gate |
| **W6 Broader research** | Phase 6, per item | Per item |

## Open questions for review

1. Approve A2's scope, or approve it in parts (for example W1–W2 first)?
2. Approve the metric dictionaries (blueprint 03) as methodology, or ask for changes?
3. Supplier decisions per dataset (blueprint 04 §5).
