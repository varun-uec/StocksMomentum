# ADR-023: One Core, Two Operating Modes (Personal and SaaS)

**Status:** Accepted 2026-10-23 (owner direction). Extends [ADD Amendment A3](../ADD-amendment-A3.md) without changing it. Related: [ADR-022](ADR-022-multilingual-research-agent.md) (agent), [ADR-021](ADR-021-data-supply-policy.md) (data supply), [doc 13](../../plans/wickstreet-2/13-wickstreet-2.0-mf-first-release-plan.md) (release plan), [doc 17](../../plans/wickstreet-2/17-mf-free-data-feasibility.md) (data rights).

## 1. Context

Commercial MF data rights are unresolved (doc 17: CONDITIONAL GO). Waiting for them would block every useful feature. The owner therefore set a two-phase delivery:
- **Phase 1:** a complete, self-hosted, single-user personal MF research application, including the multilingual Research Agent.
- **Phase 2:** the same application, hosted as SaaS, after commercial data rights and regulatory requirements are resolved.

Enabling Phase 2 must change the deployment, data-permission and user-management layers, **not the research engine or the agent**.

## 2. Decision

### 2.0 Governing requirement (applies to every implementation slice)

> Wickstreet 2.0 shall be developed as a production-evolvable, modular application operating initially in single-user personal mode. Commercialisation must require additive capabilities, configuration changes, infrastructure scaling and data-rights clearance, without material rewrites of the MF data foundation, analytics engine, research workstation or multilingual agent.

**Production-evolvable is not production-ready.** The personal version shares the production architecture and business logic. It defers only what multiple users need (§2.7).

**Engineering principle:**

> Wickstreet 2.0 is a clean implementation of a new product on Wickstreet's proven technology foundation. Its core must be suitable for multi-user production without significant rewrites, even though its first deployment is single-user and local.

Do not add production infrastructure early. Do avoid shortcuts that would later force changes to domain models, data ownership or module boundaries.

### 2.1 One core
- MF reference data, Fund Analytics, Simulation, Workspaces and the Research Agent are one codebase.
- Domain and application code contain **no mode conditionals**. Mode differences live only in adapters chosen at the composition root.

### 2.2 Mode selection
- `WICKSTREET_MODE = personal | saas` is read once at startup and selects adapters.
- The application context is the same typed context in both modes (A3 §9). Every read, write, job and agent turn carries a tenant id; in personal mode it is a fixed one.

| Concern | Personal mode (Phase 1) | SaaS mode (Phase 2) |
|---|---|---|
| Users | The owner only | Free and paying subscribers |
| Identity | Local identity adapter: one principal, no login (loopback only) | OIDC adapter (A3 §9) |
| Authorisation | Ownership checks and agent tool permissions enforced | Same, plus subscription entitlements |
| Tenancy | One tenant, one user, **enforced exactly as in SaaS** (§2.6) | Many tenants; tenant derived from the verified session |
| Network exposure | **Binds to loopback only**; refuses any other bind address (A3 §9: the anonymous single-user instance is local only) | TLS and A3 §9 exposure controls |
| Entitlements and billing | All features entitled; no billing adapter | Subscription adapter; Free/Pro entitlements |
| Models | Local Ollama routes only (ADR-022) | Self-hosted or hosted routes under ADR-022 §2.8 |
| Data rights | Personal-mode records (e.g. `amfi_terms_personal_use`) | Commercial permission records only |
| Data acquisition | Same pipeline and daily 11:30 IST job (ADR-022 §2.12), within the personal scope | Same pipeline; licensed or permitted sources |
| Storage | Local PostgreSQL | Shared versioned reference data + tenant-isolated user data |
| Deployment | Docker Compose on the owner's machine | Hosted (A3 Stage B) |

### 2.3 Data rights per mode
- The rights gate evaluates `(source, use, mode)` and fails closed.
- **SaaS mode refuses to start** if any enabled dataset lacks a commercial permission for the uses its features need.
- **Personal mode:** AMFI's "personal and non-commercial use" covers the use, but not storing "any significant portion" of the site. Bulk AMFI acquisition is **gated off**, and AMFI data enters only within an owner-set personal scope (default: none). See ADR-022 §2.11.
- **No unlicensed mirrors as a workaround** (mfnav.in, TigZig, mfapi.in). Personal mode: the owner's exception for TigZig and MFAPI is U11.

### 2.4 Built for full scale, gated by rights
- Schema, import contracts, ingestion, validation and the daily job are designed for the full MF universe: ~38,000 schemes × ~20 years of daily NAVs.
- They are verified at that scale on **synthetic** data and on any appropriately permitted records.
- Turning on bulk acquisition later is a rights-register change, not a code change.

### 2.5 Phase 1 priorities
1. **Modular MF data foundation:** provider adapters, MF-owned versioned reference data (§2.8; never registered in Momentum25's `ALL_VERSIONED`), historical NAV storage, validation, and the daily 11:30 IST refresh.
2. **Research workstation:** discovery, screening, scheme details, historical analysis, comparison and saved research.
3. **Research Agent:** Pydantic AI with local Ollama, deterministic tools, English/Hindi/Hinglish (ADR-022).
4. **Deterministic, versioned, independently testable calculations.** Metric definitions need owner approval before they ship.
5. **Full-universe design** without assuming bulk AMFI acquisition is authorised (§2.4).
6. **Simple local operation:** no production authentication, billing, multitenancy or hosting in personal mode.
7. **Stable seams** for identity, tenancy, model providers, data permissions and billing (§2.2).
8. **Momentum25 and existing Wickstreet capabilities preserved** (A3 §3.2).

### 2.6 Tenant ownership is enforced, not just stored
- Every user-owned record (saved research, conversations, preferences, later portfolios) has non-null `tenant_id` and owner columns. A `tenant_id` field that nothing checks does not count.
- Repositories always filter by the context's tenant and owner. There is no unscoped query path for user-owned data.
- PostgreSQL Row-Level Security policies, created by migrations, enforce the same rule in the database in **both** modes. The application role is not the table owner and has no `BYPASSRLS` (A3 §9).
- Shared reference data (schemes, NAVs, analytics results) is not tenant-owned and stays shared.

### 2.7 Production-grade from day one vs added at commercialisation

| Component | Personal mode (Phase 1) | Added for SaaS (Phase 2) |
|---|---|---|
| MF data models and persistence | Production-grade | Reused unchanged |
| Data acquisition and validation | Production-grade | Source adapter switched to rights-cleared supply if needed |
| Calculations and analytics | Production-grade, versioned, deterministic | Reused unchanged |
| Research workstation | Production-grade | Reused UI and workflows |
| Research Agent | Production-grade interfaces (ADR-022) | Model capacity and routing |
| Saved research | Tenant-aware and enforced (§2.6) | More tenants |
| Authentication | Local identity adapter | Production identity provider |
| Authorisation | Ownership + tool permissions | Subscription entitlements |
| Database migrations | Alembic, versioned from day one | Same process |
| Observability | Structured logs and metrics locally | Production monitoring and alerting |
| Deployment | Docker Compose locally | Hosted infrastructure, deployment automation |
| Billing | Not built | Subscription module |

**Still required before commercial launch (additive work and hardening, not a rebuild):**
- production authentication, tenant-isolation security verification;
- billing and entitlements;
- rights-cleared financial data and AI processing;
- capacity testing and inference cost controls;
- backups, disaster recovery, monitoring and incident handling;
- regulatory and privacy review;
- deployment automation and production operations.

### 2.8 Application boundary inside the repository (owner direction, 2026-10-23)

Wickstreet 2.0 is a **new, cleanly separated application in this repository**. It reuses the stack and proven components and stays isolated from Momentum25. It is still a modular monolith, not microservices.

| Area | Decision |
|---|---|
| Backend package | New top-level package `backend/src/wickstreet/`, with one subpackage per A3 bounded context (MF reference data, analytics, simulation, workspaces, research agent, data rights, identity). Each is layered domain / application / infrastructure / interface, like `momentum25` |
| Independence | `wickstreet` never imports `momentum25`, and `momentum25` never imports `wickstreet`, enforced by import-linter. Contexts call each other only through their `application` interfaces (A3 §5.1). Shared code is not reached into Momentum25; if a utility is truly needed by both, extracting it is a separate, regression-tested change |
| API and composition | Own composition root, router registration, dependencies and middleware (tenant context, local identity). Served same-origin under `/api/v1/mf/...` (A3 §8). MF routes never pass through Momentum25's global `api_router` or its non-tenant-scoped watchlist and user-document paths (doc 14 §2). Whether the MF app is mounted in the existing process or run as a second process of this repo is a Slice 1 choice, within this constraint |
| Persistence | Same PostgreSQL server. MF tables live in a dedicated PostgreSQL schema owned by `wickstreet`, with their **own Alembic environment and version table** (A3 §7.1: one owning module per table). Momentum25's schema and migrations are untouched. Versioning is MF-owned; MF tables are never added to Momentum25's `ALL_VERSIONED`, so Momentum25's `data_version` cannot move |
| Frontend | The existing `web/` app and stack (React, TypeScript, Vite), Lightweight Charts and the paper-and-ink design system, reused. A new MF route tree and research-first layout, with an API client generated from the MF OpenAPI schema |
| Build new | MF domain and data engine; analytics and calculations; workspaces (tenant-safe from day one); Research Agent; MF layout |
| Reuse | Python/FastAPI/PostgreSQL/SQLAlchemy/Alembic, frontend stack, charts and design system, test and CI tooling (pytest, mypy, ruff, lint-imports, Vitest, Playwright, `scripts/test-infra.sh`) |
| Preserve unchanged | Momentum25 engines, APIs, persistence and regression suites (A3 §3.2). Stock capabilities come back in Wickstreet 3.0 through explicit application interfaces |

## 3. Consequences
- Useful work proceeds now. Phase 2 adds adapters and deployment, not a rewrite.
- One tenant-aware code path in both modes means SaaS isolation is exercised from day one, not bolted on later.
- With the default AMFI scope of none, personal mode shows synthetic fund data plus rights-clean real data until the owner sets a scope or a legal basis exists. The app labels synthetic data as synthetic.

## 4. Acceptance criteria

| # | Criterion |
|---|---|
| OM-1 | No mode conditionals in domain or application packages (import-linter contract + test) |
| OM-2 | Personal mode refuses to bind to a non-loopback address |
| OM-3 | SaaS mode fails startup when an enabled dataset lacks a commercial permission |
| OM-4 | AMFI bulk acquisition cannot run while its gate is closed; AMFI retrieval outside `amfi.personal_scope` is refused |
| OM-5 | Full-universe synthetic load (~38,000 schemes × ~20 years) ingests, validates and serves within a performance budget measured and recorded on first run |
| OM-6 | Momentum25 and existing Wickstreet regression suites pass |
| OM-7 | Switching a test deployment from personal to SaaS mode changes only configuration and adapters; core test suites pass unchanged in both modes |
| OM-8 | **Cross-tenant denial:** with two or more synthetic tenants, no tenant can read, list, change or export another tenant's user-owned records, through the API, the agent tools or a direct query under the application role (RLS) |
| OM-9 | **Replaceable infrastructure:** tests swap the AMFI adapter, the model route and the identity adapter for test doubles by configuration; research and agent tests pass unchanged |
| OM-10 | **No single-user assumptions:** a schema test fails if any user-owned table lacks non-null tenant and owner columns or an RLS policy |
| OM-11 | **Application boundary:** import-linter forbids `wickstreet ↔ momentum25` imports in both directions, and enforces layering inside every `wickstreet` context |
| OM-12 | MF routes are registered only by the `wickstreet` composition root; MF migrations run in their own Alembic environment; Momentum25's migration history and `data_version` are unchanged by MF work |

**The four non-negotiable conditions, and how they are proven:**
1. *One codebase:* OM-1, OM-7.
2. *No single-user assumptions in domain logic:* OM-8, OM-10.
3. *Replaceable infrastructure* (AMFI adapter, Ollama, local identity and local storage stay out of the research and agent domain): OM-1, OM-9.
4. *Executable proof:* OM-6, OM-8, OM-9 run in CI.

## 5. Alternatives considered
- **A separate personal app:** rejected. Two implementations would drift.
- **SaaS-first:** rejected. It blocks useful work on unresolved rights.
- **Personal mode without tenant context:** rejected. It would make Phase 2 a rewrite of every query.

## 6. Open owner decision
- **AMFI personal scope** (`amfi.personal_scope`): which AMFI records the personal app may fetch and keep under "personal and non-commercial use" without storing "a significant portion". The default is none. Any scope is the owner's legal judgement, not an engineering default.

## 7. Architecture review update (2026-10-23)

An independent review checked this ADR against the code. The decisions in §2 stand. Items U1–U13 close gaps that would otherwise force rework. Where an item and the text above differ, the item governs.

| # | Item |
|---|---|
| U1 | **One process, two apps.** `wickstreet` builds a standalone FastAPI app with its own lifespan, middleware and OpenAPI schema. In personal mode, one host module outside both packages, the only module that imports both, mounts it at `/api/v1/mf` before Momentum25's unchanged app at `/`. Momentum25 keeps its routes, scheduler and SPA serving. The host must enter both apps' lifespans itself: FastAPI and Starlette do not run the lifespan of a mounted app, so Momentum25's database, Redis and scheduler startup would stop silently (A3 §3.2). OM-6 runs against the host. This settles the §2.8 "same process or second process" choice. In SaaS mode the MF app can run alone |
| U2 | **Shared platform code is extracted, not copied.** The transport guards (Host/Origin, body size, security headers, request context), the logging setup and the async database engine and session factory are generic and security-relevant. Do not copy them into `wickstreet`. When MF first needs one, move it into a small package, `platform_common`, that imports neither application and holds no domain policy (A3 §5.1). Momentum25 then imports it from there with no behaviour change, proven by its suites. This is the "separate, regression-tested change" of §2.8. import-linter forbids `platform_common` from importing `momentum25` or `wickstreet` |
| U3 | **Database roles make RLS real.** The Compose database user is the image's superuser. Superusers and table owners bypass RLS, so §2.6 would be inert in personal mode. The MF schema uses two roles in both modes. `wickstreet_owner` owns the schema and runs only the MF Alembic environment. `wickstreet_app` is the runtime login: NOSUPERUSER, NOBYPASSRLS, DML grants on the MF schema only, no grants on Momentum25 tables. The unit of work sets the tenant with `set_config('wickstreet.tenant_id', …, true)` at the start of each transaction. Policies compare against `current_setting('wickstreet.tenant_id', true)`, so a missing setting matches no row. OM-8 and OM-10 run as `wickstreet_app`. MF migrations run as their own step, not at API startup (A3 §7.3). Momentum25's role and startup migration stay unchanged |
| U4 | **History depth and scale (owner decision, 2026-10-23: the last 10 years).** This replaces "~38,000 schemes × ~20 years" in §2.4 and OM-5. Stored NAV history starts 10 years before the backfill runs, plus a short margin so a 10-year trailing return has its start NAV. Later history accumulates and is never trimmed, because trimming would break replay (ADR-022 §2.7) and the append-only rule (ADR-017 MF-5). Estimate: about 8,300 active plan-options publish about 2 million NAVs a year, so 10 years is roughly 20 million rows. The full AMFI history since April 2006 is about 37 million rows ([17 §1](../../plans/wickstreet-2/17-mf-free-data-feasibility.md#1-source-comparison-ranked-by-suitability-for-a-commercial-saas), a mirror's claim). OM-5's synthetic universe covers the 10-year window with at least 25 million NAV rows and doc 17's quirks. It is generated deterministically at test time and never committed. Schemes older than the window have no inception NAV in store, so their since-inception metrics need a labelled rule, decided with the metric formulas. The depth is a design target only: bulk acquisition stays gated (§2.3) |
| U5 | **Entitlements context.** Add `entitlements` to the §2.8 context list, because ADR-022 §2.1 calls it. Personal mode uses a grant-all adapter. SaaS mode adds the subscription adapter |
| U6 | **Identifiers.** Tenant and user ids in the `wickstreet` context are UUIDs. Personal mode creates its fixed tenant and user at bootstrap. Momentum25's `CurrentUser.tenant_id: int \| None` is not reused |
| U7 | **Phase and stage.** Phase 1 personal mode is an A3 Stage A deployment on the owner's machine. Phase 2 starts at A3 Stage B with every Stage B gate unchanged ([A3 §17](../ADD-amendment-A3.md#17-later-accepted-extensions-2026-10-23)) |
| U8 | **Loopback in a container.** Under Docker Compose the app must bind `0.0.0.0` inside its container, so OM-2 cannot be a bind-address check there. In personal mode, loopback-only means: outside a container the app refuses a non-loopback bind; under Compose the published port binds `127.0.0.1` and personal mode rejects any other `APP_BIND`; the Host/Origin guard (U2) stays on. OM-2's test covers all three |
| U9 | **Product target (owner decision, 2026-10-23).** Phase 1 serves real MF data: the complete universe, 10 years of NAV history (U4), refreshed daily at 11:30 IST (ADR-022 §2.12), stored locally. This is the target requirement, not a record of acquisition rights. AMFI's terms permit personal, non-commercial use of the site but bar electronic storage of "any significant portion" of it, so personal use alone does not establish permission for a full-universe, 10-year database. AMFI's 90-day limit per history download is a technical limit, not a licence. Bulk acquisition therefore stays gated (§2.3, ADR-022 §2.11) until a verified permission or a licensed supplier is recorded. Slice 1 builds and tests the complete pipeline on synthetic data, so a recorded permission turns real acquisition on by configuration, not code |
| U10 | **Owner authorisation of bulk acquisition (2026-10-23).** The owner explicitly authorised bulk download of AMFI NAV history and the AMFI scheme master, for personal mode, direct from AMFI. This is the owner's authorisation and acceptance of risk under AMFI's terms, not a permission from AMFI. It opens the U9 gate for personal mode only. The rights register stores it as `rights_grant` rows with that basis, and every ingestion run records the grants it ran under (ADR-017 MF-9). SaaS mode still needs a commercial permission or a licensed supplier. **Observed the same day:** AMFI's history endpoint serves dates from 2023-04-03 only; earlier dates redirect to the download page, with or without a fund-house filter. AMFI direct therefore yields about 3.5 years, not U4's 10. The 2016-10 to 2023-03 range needs a separate source decision |
| U11 | **Owner direction on archive sources (2026-10-23).** The owner directed Wickstreet to fill the dates AMFI no longer serves from TigZig's AMFI NAV archive, and to cross-check the store against MFAPI. For personal mode and these two uses only, this replaces the §2.3 bar on mirrors. It is the owner's decision and acceptance of risk, not a permission from AMFI, TigZig or MFAPI. The rights register stores it as `rights_grant` rows for `tigzig` and `mfapi`. TigZig states that its source is AMFI, gives no warranty, and asks for credit to Amar Harolikar and the source URL. MFAPI publishes no terms. **Precedence:** AMFI direct is the source of record from the first date it serves. Before that date the archive is the record. From that date on, the archive only fills a code and date that AMFI lacks; a different value counts as a conflict on the run and never replaces AMFI's value. MFAPI writes nothing to the store. TigZig keeps NAVs to 4 decimals, so a difference of 0.0001 or less is rounding, not a conflict. **Observed:** the backfill's search found AMFI's first served date to be 2023-04-01, two days before U10's observation. SaaS mode still needs a commercial permission or a licensed supplier for every source |
| U12 | **MF metrics method (owner approval, 2026-10-23).** The owner approved methodology v1 for MF metrics in the final Slice 2 plan review: NAV-only returns, CAGR on calendar days, rolling 1Y/3Y/5Y returns, volatility as daily-return deviation × √252, maximum drawdown, rounding for display only, exclusion of zero and missing NAVs with `NA`/`NM` states, flagged jumps kept, history labelled from the first stored valid NAV, AMFI's categories with only unambiguous variants mapped, and NAV returns marked as not total returns for non-growth options. Any change that alters a computed result bumps the method version. Version 2 changes only the option rule, after the real-data spot check; it is in use and awaits the owner's review. Spec: [mf-metrics.md](../../current/mf-metrics.md) |
| U13 | **Personal mode is the complete product (owner decisions, 2026-10-23).** Wickstreet 2.0 is a local, single-user personal MF research and investment intelligence workstation; SaaS is a later phase. (a) Personal mode supports the complete feature set, including AI-driven fund recommendations, best-fund rankings, composite scores, suggested allocations, rebalancing, portfolio optimisation and actionable investment insights for the owner. This is the owner's own tool, not a publicly offered advisory service. (b) The owner's real CAS statements are imported, parsed and analysed locally. CAS files, passwords and derived portfolio records stay on the owner's machine, in tenant-owned tables under RLS, and never enter the repository, logs, test fixtures or telemetry; raw CAS files are never sent to a model provider. (c) Product workflows use actual MF data. Synthetic data is only for automated tests and benchmarks. (d) Everything for mutual funds belongs in 2.0, including Tickertape MF parity and beyond ([doc 20](../../plans/wickstreet-2/20-wickstreet-2.0-complete-mf-scope.md)). (e) SaaS licensing, regulatory and commercial requirements (A3 §3.1, §3.3, §4 Stages B–C, §9.1; doc 13 A1–A2; docs 14–17; the agent's advice-refusal policy in ADR-022 §2.9 and AC-4) apply before public deployment in SaaS mode. They do not block personal-mode development. Ordinary privacy, security and correctness requirements apply in both modes. Where an earlier text restricts a feature without naming a mode, it applies to SaaS mode. In code, the SaaS restrictions are mode adapters chosen in the composition root (OM-1), not missing features |
| U14 | **Owner direction on further AMFI and AMC datasets (2026-10-24).** The owner directed Wickstreet to complete fund facts, benchmark, holdings and IDCW data (doc 21 E1, E3–E5) from "actual Indian mutual fund data", reusing the existing ingestion, provenance and revisioning. Under that direction, Wickstreet reads these AMFI datasets under the U10 `amfi` grants: the scheme list and scheme summary documents (SSD), monthly TER, fund performance, tracking error, IDCW history and the half-yearly market-cap lists. U10's text names only NAV history and the scheme master, so this row records the wider use; it is the owner's decision and acceptance of risk, not a permission from AMFI. Grants 17–26 record the same direction for the PPFAS and DSP portfolio disclosures, and grants 27–41 and 47–51 for Nippon India, SBI, ICICI Prudential and UTI (added 2026-10-24); each basis quotes what the AMC's site terms say. Grants 42–46 (Baroda BNP Paribas) record the owner's authorisation and risk acceptance of 2026-10-24: that AMC's terms bar copying without written consent, and the basis quotes them. Grants 52–86 record the owner's direction for Tata, Motilal Oswal, Groww, Samco, WhiteOak, PGIM India and Trust. On 2026-10-24 the owner accepted the same data-use risk as for Baroda BNP Paribas for 16 AMCs whose terms bar copying or storage without consent (Axis, Bandhan, Mirae Asset, Invesco, Sundaram, Bank of India, Canara Robeco, LIC, Shriram, Union, Bajaj Finserv, Quantum, Mahindra Manulife, JM, 360 ONE and ITI), for a local, non-commercial workstation. Grants 87–106 and 112–116 record that acceptance for the five of them Wickstreet reads (Mirae Asset, Invesco, Sundaram, LIC and Quantum). Grants 107–111 record the owner's direction for quant under its personal-use terms. The owner's risk acceptance is not a permission from any AMC. It never covers working around an access control, so the other 11 are not fetched: Axis (a token, and robots.txt disallows `/cms/`), Bandhan, Mahindra Manulife, ITI and JM (encrypted listing APIs), Canara Robeco (robots.txt disallows `/wp-content/uploads/`), Union (the site answers errors), and Bank of India, Bajaj Finserv, 360 ONE and Shriram (no listing found). No grant covers an AMC whose site blocks automated clients (Kotak, HDFC, Edelweiss, Wealth Company) or whose terms bar robots (ABSL, HSBC, Franklin Templeton, Jio BlackRock). Manual import works only for the 20 AMCs with an adapter; the 21 others need an owner `storage` grant and a source entry first. [mf-data-architecture](../../current/mf-data-architecture.md) records each source's terms, grants, provenance and procedure. Every run records the grants it ran under. **Not used:** NSE and BSE index TRI and ETF trade data (their terms bar automated retrieval); the benchmark statistics use a labelled index-fund proxy instead. SaaS mode still needs a commercial permission or a licensed supplier for every source. **Confirmed by the owner (2026-10-24):** this row matches the owner's intent, which is to use real AMFI datasets for the complete local, personal-use MF workstation, including TER, AUM, fund profiles and performance reports. It records the owner's authorisation. It does not claim a permission from AMFI |
| U15 | **Owner decision for manual AMC portfolio imports (2026-10-24).** This decision supersedes only the final sentence of U14, which predates the manual source registrations. The owner authorised Wickstreet to register all 21 previously unregistered AMC source names and to store files the owner downloads manually for local personal use. This authorises storage only. It does not grant automated retrieval, display, derived metrics, export or AI processing, and it is not permission from any AMC. No technical access restriction may be bypassed. `MANUAL` registers Kotak, HDFC, Edelweiss, ABSL, Wealth Company, HSBC, Franklin Templeton, Jio BlackRock, Axis, Bandhan, Mahindra Manulife, ITI, JM Financial, Canara Robeco, Union, Bank of India, Bajaj Finserv, 360 ONE, Shriram, Navi and Zerodha. The code routes these sources to `mf import-portfolios` only; scheduled fetching still uses the 20 existing adapters. Personal-mode `storage` rows 117–137 record this owner decision by source with a basis that says it is not AMC permission. The shared parser accepts XLS/XLSX/CSV and ZIPs of these formats, but no genuine files for the 21 AMCs have been independently parsed yet. Their layouts remain unverified, and none is classified as operational until a real disclosure is imported and independently checked. The [manual-import procedure](../../operations/mf-source-runbooks.md#manual-portfolio-import) and [current source register](../../current/mf-data-architecture.md#manual-portfolio-imports) show the supported route and its limits. This decision changes no automated acquisition rights and grants no commercial or SaaS rights |
