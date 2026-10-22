# Wickstreet 2.0 Blueprint — Investment Intelligence

> **Status:** Proposed (2026-10-22). Design and planning only. No code, migration, data import or deployment was done. Branch `wickstreet/m10-m11`, base `c03a890`.
> **Governs:** nothing until the owner accepts [ADD Amendment A2](../../architecture/ADD-amendment-A2.md) and [ADR-016](../../architecture/adr/ADR-016-fundamentals-point-in-time.md) to [ADR-021](../../architecture/adr/ADR-021-data-supply-policy.md).

## The product in one paragraph

Wickstreet 2.0 adds company research, mutual funds, ETFs, a unified screener, descriptive scorecards and a private portfolio view to the existing chart workstation. It stays one local app. Every number shows its formula, its inputs and the date they became public. A user can move from a fund to a stock it holds, to its chart, to its Momentum25 assessment and back, without losing their place. Momentum25 does not change.

## The binding constraint

**Data rights, not code.** NSE's terms forbid automated collection and simulation use. AMFI's terms allow only personal, non-commercial use and forbid storing "any significant portion" of its site. BSE and NSE Indices terms could not be read. So every dataset enters through a source-neutral import contract, and the owner chooses a lawful supplier per dataset. All six phases can be **built** on synthetic fixtures. Real company, fund and index data waits for the owner's supplier decisions ([04 §5](04-data-sources.md#5-owner-decisions-blocking-real-data-import)). The user's own portfolio is not blocked.

## Deliverables

| # | Deliverable | Document |
|---|---|---|
| 1 | Competitive capability and parity matrix | [01-competitive-parity.md](01-competitive-parity.md) |
| 2 | Reuse and gap assessment | [02-reuse-and-gaps.md](02-reuse-and-gaps.md) |
| 3 | Stock, mutual-fund and ETF product specifications, metric dictionaries | [03-product-specs.md](03-product-specs.md) |
| 4 | Authorised data-source feasibility report | [04-data-sources.md](04-data-sources.md) |
| 5 | Canonical data model and architecture | [05-data-model-and-architecture.md](05-data-model-and-architecture.md) |
| 6 | Unified screening specification | [06-unified-screener.md](06-unified-screener.md) |
| 7 | Research screen designs, UX flows, wireframes | [07-ux-flows-and-wireframes.md](07-ux-flows-and-wireframes.md) |
| 8 | Holdings, overlap, look-through and portfolio | [08-holdings-overlap-portfolio.md](08-holdings-overlap-portfolio.md) |
| 9 | Portfolio Intelligence specification | [08 §4–§6](08-holdings-overlap-portfolio.md#4-portfolio-intelligence) |
| 10 | Scorecard methodology proposals | [09-scorecards.md](09-scorecards.md) |
| 11 | UX flows and wireframes | [07](07-ux-flows-and-wireframes.md) |
| 12 | Phased roadmap with acceptance gates | [10-roadmap.md](10-roadmap.md) |
| 13 | Proposed ADRs and methodology decisions | [ADD A2](../../architecture/ADD-amendment-A2.md), [ADR-016](../../architecture/adr/ADR-016-fundamentals-point-in-time.md), [017](../../architecture/adr/ADR-017-funds-etfs-holdings.md), [018](../../architecture/adr/ADR-018-unified-screening.md), [019](../../architecture/adr/ADR-019-portfolio-look-through.md), [020](../../architecture/adr/ADR-020-descriptive-scorecards.md), [021](../../architecture/adr/ADR-021-data-supply-policy.md) |
| — | **Wickstreet 2.0 — staged implementation plan (approved for Stage A)** | [11-wickstreet-2.0.md](11-wickstreet-2.0.md) |
| — | D0-R data-source research and feasibility (for owner review) | [12-d0r-data-source-research.md](12-d0r-data-source-research.md) |

## Key decisions taken (routine, reversible)

| Decision | Why |
|---|---|
| No new services; same FastAPI/PostgreSQL/Redis process | ADR-002/004/007; local-first |
| Filings and disclosures stored by publication time; restatements append | Point-in-time integrity (NFR-15) |
| Screening runs in the domain over in-memory snapshots | Universes are small; one explainable code path |
| Three value states: value, `NM`, `NA` | No silent zeros (NFR-16) |
| Portfolio holdings derived from transactions | One source of truth |
| XIRR by bisection | Deterministic |
| No composite score; scorecards are descriptive | No unearned claims |
| No new single-letter shortcuts | A typed letter opens symbol search ([keyboard shortcuts](../../current/reference/keyboard-shortcuts.md)) |

## Owner decisions

| # | Decision | Default taken | Blocks |
|---|---|---|---|
| O-1 | Accept ADD A2 scope (whole or by phase) | Nothing starts until accepted | All phases |
| O-2 | Approve metric dictionaries (03 §1.4, §2.5) as methodology | Treated as Proposed | Phase 1 and 3 code |
| O-3 | Company financials supplier (vendor or exchange permission) | Build contracts on fixtures | Phase 1–2 real data |
| O-4 | Send the AMFI permission request (04 §6) | Not sent: sending leaves this machine | Phase 3 real data |
| O-5 | Index TRI licence | Price index with "excludes dividends" warning | Fund/ETF benchmark accuracy |
| O-6 | Holdings supplier | Normalized contract + one AMC template parser | Phase 4 real data |
| O-7 | Watch-point thresholds and scorecard metric lists | Proposed lists | Phase 1 (flags), Phase 5 |
| O-8 | Hands-on competitor walkthrough to close UNVERIFIED rows | Desk research only | Nothing; improves 01 |

## What was not done

- No code, migration, database change, data download, deployment or push.
- No hands-on use of competitor products (desk research only; UNVERIFIED rows marked).
- The sealed hold-out was not read. Completed audit rounds were not reopened. Momentum25 methodology was not changed.
- BSE, NSE Indices and RBI terms could not be read (HTTP 403 or timeout).
