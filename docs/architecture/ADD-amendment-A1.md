# ADD Amendment A1 — Wickstreet Charting Workspace and Open-Source Release

> **Status:** Proposed (revision 3, under review). The ADD text below takes effect only when this amendment is approved.
> **Date:** 2026-10-18 (revision 1: 2026-10-17)
> **Applies to:** ADD §0, §1, §2, §3, §4, §6, §26, §27

Each block names the ADD section, then the exact text to add or replace.

---

## §0 Header — replace the status line

> **Status:** Approved blueprint (Phase 2), amended by A1 (2026-10-18): the Wickstreet charting workspace and open-source release. Implementation follows the roadmap in §27.

## §1 Executive Summary — add after the first paragraph

**Wickstreet** is the product. It is an open-source, self-hosted market workspace for NSE daily data. The chart comes first. A user who knows TradingView must feel at home on the first visit.

**Momentum25** is Wickstreet's analysis engine and its built-in screener strategy. Every existing Momentum25 capability keeps working. Advanced screens (validation, experiment, backtest, analytics, historical, Elliott wave and others) stay reachable even when the default navigation hides them.

The project is released on GitHub. Each user runs a private copy. Each copy fetches its own daily data. The project hosts no data and runs no shared service (ADR-012).

The name "Wickstreet" is provisional until domain and trademark clearance is complete (M16).

## §1a Reference Rule (new section)

Wickstreet is an independent implementation. TradingView and OpenChart are references for usability and capability, not sources of code.

- We study observable behaviour, public documentation and screenshots.
- We never read, copy or adapt TradingView or OpenChart frontend source, assets, icons or branding.
- M9 starts an **independent design record**. Each entry names the Wickstreet decision, the reference that prompted it and our own rationale.
- The record states prior exposure honestly. On 2026-10-18 the team read OpenChart's public README and LICENSE text, but no frontend source. Any later exposure gets logged with its date and scope.
- This rule lowers legal risk. It does not remove it.

## §2 Functional Requirements — add rows

| ID | Requirement | In scope | Notes |
|----|-------------|-----|-------|
| FR-17 | Charting workspace with a terminal-style layout | ✅ | Top toolbar, left drawing rail, right panel, keyboard shortcuts. Own name and visual identity (ADR-012). |
| FR-18 | Chart types and intervals | ✅ | Candle, bar, line, area, Heikin-Ashi. Intervals 1D and 1W (ADR-013 §Data). Log and percent scale. Compare symbols. |
| FR-19 | Indicators on the chart | ✅ | Overlays and sub-panes. See NFR-1a for which values are authoritative. |
| FR-20 | Drawing tools | ✅ | About 12 tools. Select, move, delete. Drawings belong to the symbol (ADR-013 §Workspace). |
| FR-21 | Screener screen | ✅ | The existing Top-25, rule breakdown and history, inside the workspace shell. |
| FR-22 | End-of-day alerts | ✅ | Price and indicator conditions, checked after each daily sync, shown in the app. |
| FR-23 | Persistent workspace on the server | ✅ | Layout, charts and drawings survive a reload and a browser change (ADR-013 §Workspace). |
| FR-24 | Multi-chart layouts | ✅ | Up to 4×4. Optional sync of symbol, interval and crosshair. |
| FR-25 | Strategy Studio | ✅ | Configure registered rules, gates, thresholds and weights. Gated by ADR-014. |

## §3 Non-Functional Requirements — add

- **Indicator authority (NFR-1a):** an indicator is identified by `(indicator_id, params, interval, data_version)`. If an indicator can drive an alert, only the backend computes it, and the chart draws the backend values. The browser may compute other studies to draw them. A browser-computed value never feeds a score, a gate, a rank or an alert. This keeps NFR-1 intact.
- **Interval semantics (NFR-1b):** the backend domain owns bar aggregation. ADR-013 §Data defines it.
- **Chart responsiveness (NFR-11):** one chart opens a symbol with 10 years of locally stored daily bars:
  - **Warm open: P95 ≤ 1 s.** The API and database are running, and the app's assets are in the browser cache. The symbol's data is not in the browser's query cache.
  - **Cold open: P95 ≤ 3 s (provisional).** First open after an API container restart, with the browser cache cleared.
  - **"Open"** runs from navigation start to the first paint of the last candle, measured with a browser performance mark.
  - **Method:** at least 30 runs per case, across at least 10 symbols. Each report records the hardware, OS, browser version, dataset date and git commit.
  - M13 benchmarks 1, 4 and 16 charts and reports the results. It does not redefine this target.
- **Open-source hygiene (NFR-12):** the repository holds no secrets, no market data and no database dumps. A new user starts the app with `docker compose up` and one `.env` file.
- **No regression (NFR-13):** every existing Momentum25 endpoint, CLI command and screen keeps working through every Wickstreet milestone.
- **Local by default (NFR-14):** a fresh install listens on loopback only. Wider access needs an explicit setting (ADR-012).

## §4 Product Scope — replace

**In scope:** NSE equities; daily EOD; the Momentum25 strategy with full explainability; historical snapshots; backtesting; the charting workspace (FR-17 to FR-20, FR-23, FR-24); the screener screen (FR-21); end-of-day alerts (FR-22); Strategy Studio (FR-25); local self-hosted deployment; open-source release.

**Out of scope:** AI agents; scripting or indicator languages; user-defined executable rules; intraday and real-time data; order placement, execution and broker integration; social features; a hosted multi-user service; BSE and non-equity assets in the workspace; the TradingView Advanced Charting Library (ADR-011).

## §4a Identifiers (new)

The Python package, CLI commands, database names and API paths stay `momentum25`. Only user-facing text, the web app title and the repository README use "Wickstreet". We do not rename internal identifiers.

## §6 Deferred Features — change one row

| Deferred capability | Pre-built extension point |
|---|---|
| ~~Alerts / webhooks~~ → **Alerts move into scope (FR-22).** Delivery outside the app (email, Telegram, webhook) stays deferred. | The `RunCompleted` event plus the `EventPublisher` notifier |

## §26 ADR table — add rows

| ADR | Decision | Rationale (rejected alt) |
|---|---|---|
| 011 | Chart engine: keep `lightweight-charts` | Apache-2.0, already in use (vs Advanced Charting Library: proprietary; vs KLineChart: a rewrite) |
| 012 | Open-source, self-hosted, local by default | Each user fetches their own data, so there is no redistribution (vs a hosted service: needs a data license and auth) |
| 013 | Web stack and chart data semantics *(Accepted 2026-10-18, after the M10 spike)* | A same-origin SPA plus backend-owned bars and indicators (vs keeping Next.js with a build-time API URL) |
| 014 | Strategy Studio: configured rules, hypothesis-and-lineage families, one 36-month hold-out evaluation per family, a reproducible `data_version` *(Proposed)* | The real engine evaluates user strategies point in time (vs reusing the walk-forward backtest, which is a different method) |
| 015 | Licence *(placeholder, decided separately)* | Apache-2.0 vs AGPL-3.0 |

## §27 Roadmap — add milestones

| Milestone | Deliverable | Verification |
|---|---|---|
| **M9 Reference study** | Capability inventory and parity matrix (full); reuse matrix from the code; wireframes for the M11 workflow and the screener only; design record started | User review |
| **M10 Stack spike** | Vite spike and ADR-013 decision; same-origin API; loopback binding; `Host` and `Origin` checks; Lightweight Charts attribution; 16-chart smoke check | Spike criteria in ADR-013; every row of the ADR-012 request table tested |
| **M11 Vertical slice** | Find → Analyse → Draw → Restore on 1D bars, with server-side workspace persistence | **First major review gate:** a working prototype plus E2E tests |
| **M11b Weekly interval** | Backend 1W bars and 1W indicator series | Aggregation golden tests. Runs inside M11 only if it does not delay the slice. |
| **M12 Workspace shell** | Toolbars, panels, watchlist panel, shortcuts, screener in the shell, advanced screens reachable | E2E; no regression (NFR-13) |
| **M13 Professional charting** | About 12 drawing tools, indicator dialog, context menus, multi-chart sync, 1/4/16-chart benchmark | Geometry tests; benchmark report; NFR-11 still met |
| **M14 Strategy Studio** | Rule parameter schemas, history tables and the `data_version` manifest, provenance labels, the evaluation path, the UI (ADR-014) | **Hard gate:** golden determinism, look-ahead and provenance tests |
| **M15 Alerts** | Alert model on authoritative indicator specs, checked after daily sync | Golden alert tests; chart and alert parity test |
| **M16 Release** | ADR-015 licence, NSE data-use compliance check (ADR-012), history scan, docs, independent usability review, name clearance | A fresh clone on a clean machine starts and fetches data |

---

## Open questions for review

1. **ADR-010 and SaaS.** The licence choice (ADR-015) decides whether a later SaaS needs protection. This does not block M10 to M15.
