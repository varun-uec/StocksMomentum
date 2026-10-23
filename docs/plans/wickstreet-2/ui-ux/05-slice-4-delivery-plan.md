# 05 · Delivery plan and release gates

This is an implementation-ready sequence within the accepted architecture. Estimates are intentionally omitted until an implementer sizes the tasks; each milestone has a testable exit. Slice 4 owns the MF workstation and personal research persistence. Slice 5 and 6 own agent and portfolio engines. E1–E7 can attach additively; they are not silently removed from 2.0.

## Architecture and file placement

Propose `web/src/features/mf/{api,components,routes,state,charts}` with lazy route modules. Keep MF business logic in `wickstreet`, typed HTTP transport in the frontend and generic visual primitives reusable. Reuse React Query, React Router, Recharts, Inter and existing focus/dialog patterns. Lightweight Charts remains for Momentum25; decide a shared chart adapter only after a measured need. No new UI framework is necessary.

MF gets a separate shell selected by route without mounting the stock symbol search/right dock or making stock queries. Add one product-switch entry to the existing shell. Keep existing URLs and state namespaces stable. Generate MF types from the standalone OpenAPI via a separate command, retaining Momentum25's generated types. Current API `dict[str, Any]` responses may need explicit DTO schemas before full response codegen; until then checked transport interfaces and contract fixtures are required. Do not claim codegen alone solves dynamic response typing.

Persistence follows `wickstreet` tenant context and RLS, with repository ports and interface DTOs. Reuse frontend `DocumentStore`/merge mechanics as a pattern; MF routes do not write through Momentum25's document tables or reuse its numeric tenant id. Store versioned JSON documents initially where accepted; relational events/rule evaluation stay in their own application services. No speculative new service deployment.

## M0 · Contract baseline and research safety

**Depends:** existing personal host and live v5 data. **Deliver:** reproducible API smoke matrix, schema/response types, registry unit/state adapter, reusable revision context, method/source drawer. Pin all queries; validate codes/routes/view-state schema. Record p50/p95 transport timings using a repeatable run, not this plan's single samples. Capture baseline Momentum25 route/screenshots.

**Acceptance:** all current endpoint shapes covered, including `/confidence.sources`, no-snapshot and invalid-cursor; number fraction/percentile/ratio/date handling verified. Unknown field types fail visibly. A refreshed registry never mixes metrics from a prior revision under the new date. **Tests:** unit transport/state formatting; pinned contract integration; current backend MF suites; no application data mutation by smoke tests.

## M1 · Design system and MF shell

**Depends:** M0. **Tasks:** scoped tokens/type scale, buttons/fields/disclosures/drawers/table/empty/error/save primitives; desktop/tablet/mobile shell; six destinations and product switch; skip link, focus routing, reduced-motion, dark theme. Add `/mf` without redirecting `/`.

**API:** registry envelope status only; no eager analytics fan-out. **Acceptance:** 320–1440 px and 200% zoom; keyboard/trap/return focus work; one `main`; stock shell unaffected. **Tests:** axe light/dark, visual snapshots at 390/768/1024/1440; existing Momentum25 shell/search/chart tests.

## M2 · Navigation, search and context

**Depends:** M1. **Tasks:** typed route schema; global name/code/ISIN combobox; exact plan/option/status result; query cancellation, recent-public-view cache; URL/back/scroll/focus restoration; compare selection tray; original/latest revision choice. Validated local return path.

**API:** `/funds`, `/funds/{code}`, `/screener/fields`, `/me`. **Acceptance:** Enter opens the selected result; direct/regular and growth/IDCW never conflated; unknown code and no-NAV handled; adding sixth comparison explained. No sensitive inputs in URL. **Tests:** search races, keyboard, Back loop, invalid URL and unsafe return target, screen→fund→Back context.

## M3 · Discovery and visual screening

**Depends:** M2. **Tasks:** six current collections/category explorer; schema-driven field browser, ALL/ANY clauses, type-aware inputs, raw/display unit conversions, formulas/autocomplete; saved local draft; sortable table/mobile cards, columns; result explanations/missing states/relaxations; pinned all-results CSV export with cancellation. Save UI integrates W1 in M6; until then draft is labelled session-only and no fake Saved state.

**API:** fields, presets, screener/run. **Acceptance:** all registry fields available, valid formulas round-trip, missing excludes correctly, stable cursor resets after edits; empty ANY has no fabricated relaxation; exported row count equals matched at pinned revision. **Tests:** formula/units/URL unit tests, backend-screen integration, full J1 E2E, large page/export cancellation, accessible field/dialog navigation, no long main-thread block on table rerender.

## M4 · Fund intelligence and analytical studio

**Depends:** M3. **Tasks:** all six fund tabs and sections; current reference summary with balanced evidence templates; NAV/rebased chart, rolling quantiles, annual/FY/monthly, underwater/recovery, rank history, score drawer, direct/regular, confidence, near-duplicates; Studio frontier/transitions/regimes/backtest; dataset dependency panels. Link compatible date charts, with accessible data table for every chart. Save view in URL before W1 integration.

**API:** every fund view, peers, regimes, risk-free, backtests. **Acceptance:** numerics/windows/anchors/method agree; “not recovered” preserved; rate missing stays missing; source acknowledgement shown; backtest in-sample/hold-out separate; no official benchmark label on proxy. **Tests:** real API E2E J2/J5 plus synthetic edge fixtures, numeric view assertions, visual chart states/tooltips, keyboard chart selection, stale/partial/error snapshots. No financial formula duplicated in UI.

## M5 · Comparison and historical simulation

**Depends:** M4. **Tasks:** 2–5 exact plan identities, metric groups and difference view; rebased common-start plot, correlation/sample detail; historical SIP/lumpsum/SWP/STP forms with schedule/step-up/tax; outcomes/cash flows/rolling SIP; dirty-result label, export, scenario drafts. Future forward scenarios shown only as a named dependency until S1 exists.

**API:** compare, calculators, rolling-sip; metrics for help. **Acceptance:** J3/J4 complete, different trailing/compare periods named; no holdings overlap inference; tax unknown not treated as zero, exit-load omission clear; empty lumpsum timeline handled; no target/source duplication STP. **Tests:** contract fixtures for tax unmodelled, SWP exhaustion, short history, different fund start dates; live summary equality; responsive table/card and keyboard forms.

## M6 · Durable personal workspace, briefs and alerts

**Depends:** M3–M5, W1–W3 built in this milestone. **Backend tasks:** tenant-scoped schema/repository/application CRUD; versioned view specs; optimistic concurrency; archive/restore; rule evaluator after snapshot publish, deduped events and cadence/last evaluated; snapshot evidence diff; scoped exports. Add migration/RLS/rollback tests before hooking the UI.

**Frontend tasks:** named watchlists/screens/notes/briefs/scenarios; autosave and conflict resolution; initial draft import preview; alert editor, pending/active/paused/error states and event evidence; original/latest replay. “Decide” is the structured brief action shared everywhere. No silent destructive reconciliation of browser drafts.

**Acceptance:** data persists across browser/app restart; two-window conflict never overwrites unseen edits; alert event exactly once per rule/revision; no “Active” before registration/evaluation; tenant isolation holds using runtime role. **Tests:** unit merges/schema migrations, backend transaction/RLS/API, restart/conflict/dedupe E2E, storage/network failure recovery. Required CI uses generated synthetic data, no real CAS or owned holdings.

## M7 · Complete-vision integration seams

**Depends:** M6. **Slice 4 deliver:** capability manifest adapter from actual service availability/configuration (proposed, not an existing endpoint); shared context/action schema; dependency panels; slots for dated profile/holdings/cost/benchmark data; proposed portfolio and agent contract fixtures confined to tests. No runnable fake AI or upload flow in delivered product.

**Slice 5 deliver later:** A1/A2, ADR-022 runtime, local Ollama and rights-checked tools, authoritative templates/validator, English/Hindi/Hinglish, research-memory replay and recommendation evidence. **Slice 6:** P1/P2 local CAS preview/commit/undo, reconciliation, portfolio XIRR/look-through/drift/allocations with approved methods. **Enrichment:** E1–E7 dated adapters and field coverage. These remain part of the complete Wickstreet 2.0 plan.

**Acceptance for seams:** known capability state maps to visible explanatory UI; conventional tools work with agent absent; raw CAS cannot be attached to model context; a future field can join existing registry/table/help without a parallel hardcoded metric system. **Later acceptance:** J6/J7 and screen-specific criteria in 03. **Tests:** unavailable service contracts, context action validation, tenant isolation; later adversarial language, numeric citations, parser privacy and portfolio invariants.

## M8 · Release refinement and comparative validation

**Depends:** each delivered feature's service and its gate, not a promise that unavailable features are complete. **Tasks:** measure full journeys, accessibility/manual screen reader, loading/stale/partial/error polish, multi-theme/multi-viewport visual QA, keyboard and touch, browser restart, slow network, performance profiles and competitive study. Close all critical/high issues; recheck just affected journeys after fixes.

**Performance targets (proposals to verify):** warm route content ≤1 s locally; remote-shaped p75 LCP ≤2.5 s, INP ≤200 ms, CLS ≤0.1; immediate local input response ≤100 ms; first 50 screen rows ≤500 ms warm; heavy Studio view ≤1.5 s warm with cancelled obsolete requests. p95 measured over ≥30 runs with environment/network profile recorded. Initial MF route adds ≤200 KB gzip JS beyond shared shell; chart chunks load on demand. These are targets, not observed results. Backtest/correlation budgets must account for current per-group backend cache.

**Acceptance:** equivalent-journey study meets [06](06-competitive-and-validation.md) targets; beginners explain downside/annualisation without tutorial; advanced users reproduce screen and inspect peers without dead ends; zero critical/serious axe findings and no critical keyboard/screen-reader blocker. Preserve Momentum25 golden behaviours/route tests. **Evidence:** command logs, endpoint assertions, redacted timing aggregates, viewport captures and consented anonymous study summary. Product screenshots cannot expose owned financial records.

## Implementation checks and definition of done

Run `npm run lint`, `npm test`, `npm run build`, targeted Playwright suites, MF backend unit/integration and architecture checks when changed. When endpoints change, regenerate/review both schemas and run tenant/runtime-role tests. E2E uses a safe `_e2e` database and generated fixtures as the existing harness requires; never seed or migrate the real personal store for tests. A separate opt-in, read-only live-data smoke asserts shown values against the same revision. No UI test writes to the owner's portfolio or research database.

Each milestone records scope, touched contracts, checks, screenshots and remaining dependencies. A visible enabled action is done only when its effect, persistence, failure and return navigation work. Warnings/limitations are adjacent to the relevant evidence; there is no hidden universal disclaimer that substitutes for accurate UI. Complete 2.0 requires the later agent, portfolio and enrichment gates as well as Slice 4.
