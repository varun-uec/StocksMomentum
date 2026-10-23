# 01 · Product strategy and information architecture

## Product idea

Wickstreet is a research notebook that turns evidence into a decision the investor can revisit. Its primary loop is **ask or discover → narrow → understand → compare → test → record → review**. The product must explain a tradeoff before suggesting a next step. It should feel spacious and calm, with the depth of a workstation revealed where a question needs it.

The complete personal product includes recommendations, allocations, CAS analysis and multilingual research, as accepted in [doc 20](../20-wickstreet-2.0-complete-mf-scope.md) and ADR-023 U13. These capabilities remain in 2.0. Their future UI designs are included now; their services are tracked as dependencies. SaaS, pricing and stock fundamentals are separate releases.

## Working personas

These are design hypotheses for recruiting, not observed user research.

| Persona | Context and job | What gets in the way | Successful outcome |
|---|---|---|---|
| Asha, 23, first salaried investor | Starts a monthly SIP; understands how a fund could behave over five years | Acronyms, rankings without reasons, fear of losing savings | Explains CAGR versus total return, identifies a historical loss and saves a reasoned shortlist |
| Kabir, 29, self-directed researcher | Chooses between shortlisted flexi-cap funds; comfortable with spreadsheets | Switching tools, cherry-picked returns, repeated filter entry | Builds a repeatable screen, compares consistency and downside, saves a dated brief |
| Meera, 34, portfolio caretaker | Reviews several funds across folios and rebalances toward goals | Duplicate exposures, tax uncertainty, opaque CAS import | Reconciles transactions, sees unknown exposure and evaluates an allocation without placing an order |
| Dev, 31, experienced analyst | Tests selection rules, peer persistence and regime sensitivity | Simplified dashboards that hide samples, windows or method | Audits each formula and peer group; reproduces the result from its revision |

Age is a targeting assumption, not a proxy for investment knowledge. Density and explanation preferences are independent of risk tolerance. No compulsory quiz or tutorial precedes research.

## Primary journeys

| ID | Task | Main path | Completion evidence |
|---|---|---|---|
| J1 | Find consistent equity funds | Discover collection → Screen → explain condition → fund | User names the criterion, shortlist and a limitation |
| J2 | Understand a fund's downside | Search → fund Risk → underwater → recovery episode | User states worst fall, dates and whether recovered |
| J3 | Compare genuine alternatives | Add 2–5 plans → Compare → correlation → simulation | Common period understood; NAV correlation not mistaken for holdings overlap |
| J4 | Test an investment habit | Simulate → historical SIP → vary start and step-up → save | Amounts, dates, tax class, stamp duty and omissions visible |
| J5 | Audit a screening strategy | Screen → Studio → historical ranks → top-N backtest | In-sample and hold-out separate; category-history limitations understood |
| J6 | Review owned investments | Portfolio → import CAS → preview → reconcile → commit → exposures | Exact import coverage and unexplained balances visible before commit |
| J7 | Research in my language | Contextual ask → proposed tools → evidence answer → open editable view | Hindi/Hinglish answer has cited numbers and completes a UI task |
| J8 | Resume a decision | Workspace brief → restore screen/revision → compare changes → annotate | Original and latest evidence remain distinguishable |

## Navigation and routes

**Desktop ≥1280:** a 208 px left rail, 72 px top utility bar, fluid content up to 1440 px, optional 360 px research agent/evidence rail. Only one right rail at once. The agent opens a wider reading mode when needed. A compare tray appears only after selection.

**Tablet 768–1279:** collapsed 72 px rail, responsive two-column content; right panel overlays with a focus trap and preserves page width. At 1024 px the screener filter rail becomes an explicit drawer. Landscape comparisons may use a focusable horizontal table.

**Mobile 320–767:** top search/ask bar, four fixed bottom destinations—Discover, Screen, Portfolio (after available; Workspace before), More. More opens Studio, Compare, Simulate, Workspace and Momentum25. Compare tray sits above the bottom bar only when selected; collapse it to a count badge. Safe-area padding reserves both. Fund page has a compact sticky identity and horizontal section navigation. Touch actions are at least 44 × 44 px. No hover-only feature.

| Route proposal | Meaning and parameters | Entry / return contract |
|---|---|---|
| `/mf` | Discover, goal/horizon preferences from workspace | App switcher; never takes over Momentum25 `/` |
| `/mf/screen` | `preset`, `screen`, `rev`; filters/columns/formulas encoded as versioned `view` for an unsaved public research view | Return restores filters, cursor, scroll and focus row |
| `/mf/funds/:amfiCode` | `tab=overview|performance|risk|peers|holdings|profile`, `window`, `rev`, `disclosure` when available | Stable plan-option identity; show plan and option on every title |
| `/mf/studio` | `mode=rolling|ranks|regimes|frontier|backtest`, `codes`, `window`, `rev`, `view` | Open from fund, screen or comparison with selections intact |
| `/mf/compare` | `codes` 2–5 distinct AMFI codes, `start`, `metricSet`, `rev` | Order persists; replace a fund without clearing the others |
| `/mf/simulate` | `kind`, `code`, `target`, `rev` | Financial amounts and personal scenarios are saved by opaque workspace id, not URL |
| `/mf/portfolio` | Private portfolio summary; tab and local opaque id only | CAS import and transaction detail never appear in URLs |
| `/mf/workspace` | `tab=watchlists|screens|briefs|notes|alerts`, opaque record id | Saved, saving, unsaved, error and conflict states |
| `/mf/research/:briefId` | Dated decision brief | Contains objectives, sources, alternatives, scenarios, thesis, doubts and review date |
| `/mf/ask` | Full agent workspace; `context` points to non-sensitive public research only | Mobile full screen; transcript retrieved by tenant-scoped opaque id |
| Existing `/`, `/chart`, `/stock/*`, `/studio`, `/watchlist`, etc. | Momentum25 routes unchanged | Product switch labelled “Momentum25 · Stocks”; no MF filters in stock state |

Routes are a proposed Slice 4 decision, not existing API endpoints. Route naming differs from historical doc 06's unified root because the accepted MF-first scope now requires a full product without changing the established stock workstation. Keep reusable primitives; do not merge MF and stock domain state. Add future holdings → stock → chart → Momentum25 navigation with a validated local return path and disclosure context (E4); do not pretend stock fundamentals ship in 2.0.

## Research context and deep links

A `ResearchContext` carries selected AMFI codes, `data_revision`, method version, window, category/plan/option, view specification, source route and focused row. It is shared between view and agent tools. It holds no financial calculations. The client resolves the initial registry envelope, pins dependent calls to its revision, and displays new-revision availability instead of silently mixing snapshots. Opening a saved record can replay its original snapshot or explicitly refresh a copy.

Use browser history for meaningful changes (tab, fund, preset, simulation result); use replacement for live filter editing and chart scrubbing. Bound URL schema/version/length, validate ids and permit only same-origin return paths. Invalid public view links offer “Open default screen” without losing the malformed input for inspection. Sensitive saved work is never exported through a share link.

## Progressive disclosure

Level 1 answers “What should I understand?” with three evidence statements, a primary chart and a sensible next action. Level 2 opens tables, windows, peer counts and distribution details. Level 3 opens method, exact dates, source/revision, missing states and downloadable evidence. An optional **Compact** density preference affects geometry; it does not change the numbers or hide uncertainty. Per-view disclosure survives return navigation.

A recommendation must expose criteria, constraints, data coverage, alternatives and reasons against the pick. “Highest score” is a category-relative historical ranking, not a suitability finding. The current score has three equal parts; neither risk-free Sharpe nor TER silently replaces a part. Only an approved future method version may change it.

## Personalisation without an opaque feed

Allow optional goal, horizon and comfort-with-loss preferences. Explain how each changes collection ordering and scenario defaults. Initial Slice 4 uses explicit user selection and read-only presets; it does not infer suitability. Future recommendation services may use approved profile fields with a clear “Why shown” explanation. Users can reset preferences, inspect the active criteria and research every fund without personalisation.

An editable decision brief closes the loop: objective → shortlist → evidence for/against → investment scenario → chosen research conclusion → review condition. Saving a conclusion never initiates a financial transaction. Alerts describe evidence changes; a scheduler and event store are required before calling them active.
