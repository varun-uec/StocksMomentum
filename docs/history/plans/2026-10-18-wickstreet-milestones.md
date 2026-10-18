# Wickstreet Milestones M9–M16

> **Status:** Proposed, under review, 2026-10-18. ADD A1 §27 holds the summary table. This file adds dependencies, exit criteria and what each milestone does *not* include.

## Dependencies

```
M9 ──┐
     ├─► M11 ─► M12 ─► M13 ─► M15 ─► M16
M10 ─┘     └─► M11b ──────────┘
                     ADR-014 accepted ─► M14 ──► M16
```

- M9 and M10 can run in parallel.
- M14 depends only on ADR-014 and M12 (the shell). It does not wait for M13.
- M15 alerts need the indicator specs from M11b and M13.

## M9 — Reference study
- **Scope:**
  - Capability inventory and parity matrix: TradingView, OpenChart and Wickstreet, each row with a priority.
  - Reuse matrix from the code: module, reuse, extend or replace, tests, complexity.
  - Wireframes for the M11 workflow and the screener only.
  - Design record started (ADD §1a), including the prior-exposure entry.
- **Exit:** you review and approve.
- **Not included:** wireframes for Strategy Studio, multi-chart or alerts. Each comes at the start of its own milestone.

## M10 — Stack spike
- **Scope:**
  - The Vite spike on `/chart/:symbol` and the screener (ADR-013 §2, S1–S7).
  - Same-origin `/api/v1`: the API serves the SPA. This also fixes the broken `NEXT_PUBLIC_API_BASE` setting.
  - Every published port bound to loopback (ADR-012).
  - `Host` and `Origin` checks (ADR-012 request table).
  - Lightweight Charts attribution: an About page plus the README.
  - The 16-chart smoke check.
- **Exit:** S1–S7 pass, and ADR-013 goes to Accepted (or option B). Every row of the ADR-012 request table is tested, including `curl` without `Origin`. The existing suite stays green.
- **Not included:** any new user feature.

## M11 — Vertical slice: Find → Analyse → Draw → Restore
- **Scope:** see [the M11 vertical-slice plan](2026-10-18-m11-vertical-slice-plan.md). 1D bars only.
- **Exit (first major review gate):** a working prototype that you use yourself, plus green Playwright E2E tests.
- **Not included:** weekly bars (M11b), more than 4 drawing tools, multi-chart, or toolbars beyond what the workflow needs.

## M11b — Weekly interval
- **Scope:** backend weekly aggregation (ADR-013 §4), 1W indicator series and an interval switch in the chart.
- **Exit:** aggregation golden tests pass (holiday weeks, partial week, corporate-action week).
- **Rule:** M11b merges into M11 only if it does not delay the slice. Otherwise it ships right after.

## M12 — Workspace shell
- **Scope:**
  - Top toolbar, left drawing rail, right panel (watchlist and details) and keyboard shortcuts.
  - The screener inside the shell.
  - Advanced screens reachable from a "More" menu.
  - Light and dark themes.
  - *(Carried from the M11 review.)* Indicator panes follow the price range. Today the RSI, MACD and ADX panes load the whole history, so on a short range they stretch the time axis past the price bars.
- **Exit:** E2E tests across every existing route (NFR-13). Shortcuts are documented. On every range, the panes span the same dates as the price bars.

## M13 — Professional charting
- **Scope:**
  - About 12 drawing tools, with select, move, delete, edit and style.
  - Indicator dialog, context menus, chart types, log and percent scale, compare.
  - Multi-chart layouts up to 4×4, with sync of symbol, interval and crosshair.
- **Exit:**
  - Geometry unit tests pass.
  - **Benchmark report at 1, 4 and 16 charts:** time to open, pan frame rate and memory, using the NFR-11 method (at least 30 runs, environment recorded).
  - The 1-chart case still meets NFR-11. M13 reports the multi-chart numbers and does not redefine NFR-11.

## M14 — Strategy Studio v1
- **Prerequisite:** ADR-014 accepted.
- **Scope, in order:**
  1. Rule parameter schemas.
  2. History tables and the `data_version` manifest. Fix and test the point-in-time gaps: the as-of adjustment, the point-in-time universe and provenance labels.
  3. Re-run a sample of past research and report any differences.
  4. The `StrategyEvaluation` jobs.
  5. The three result classes.
  6. The Studio UI.
- **Exit:**
  - Golden determinism tests pass: the same `config_hash` and `data_version` give the same result.
  - Look-ahead tests pass: a future bar raises `LookAheadError`, and a later split does not change an earlier decision.
  - Provenance tests pass: a period with `reconstructed` inputs carries "Incomplete historical provenance".
  - Family tests pass: a second Out-of-Sample Evaluation in a family is refused.
  - **Hard gate:** the Studio does not ship until all of these pass.

## M15 — Daily alerts
- **Scope:** an alert model that stores an indicator spec, evaluation after each daily sync and an in-app alert list.
- **Exit:**
  - Golden alert tests pass: fixed bars give fixed alerts.
  - A **parity test** passes: for every alert-capable spec, the chart series and the alert input are byte-identical for one `data_version`.

## M16 — Open-source release
- **Scope:**
  - ADR-015 licence.
  - NSE data-use compliance check, recorded in the release checklist (ADR-012).
  - History scan for secrets and data files.
  - README, CONTRIBUTING and `.env.example`.
  - Security-boundary docs (ADR-012).
  - Independent usability review.
  - Name clearance (domain and trademark).
- **Exit:** a fresh clone on a clean machine starts with one command and fetches data.
