# Wickstreet 2.0 (Mutual Funds, ₹199) / 3.0 (Stocks) — Release Plan

> **Current direction and documentation edits approved, 2026-10-22.** Bootstrapped, founder-operated self-service simulations. Implementation, expenditure, real market data ingestion, IA applications, commits, pushes and deployments remain unauthorised. This is the canonical release plan. See the [blueprint](README.md) and [D0-R research](12-d0r-data-source-research.md).

## Context and decision

**Build the useful simulation product, validate demand, and scale spending progressively.** Wickstreet calculates consequences of investment choices made by users; it does not prescribe investments. No IA business is a 2.0 launch dependency. The former advisory proposal and earlier budgets are superseded as current strategy; historical owner decisions remain below.

Binding assumptions:

- Centrally hosted SaaS; Pro ₹199/year including GST. Comprehensive free research remains.
- **Zero incremental hosting during development**, using existing infrastructure and synthetic fixtures. Existing sunk infrastructure cost is not charged again. No production customer data on development systems.
- Zero salaried engineers, dedicated SRE or paid on-call team. Founder owns architecture, maintenance, support, security and operations.
- Supervised interns use legally valid engagements, IP/confidentiality terms and synthetic fixtures. Zero remuneration is conditional on lawful classification, not a blanket exemption for internships or apprenticeships.
- ₹0 recurring MF data licensing is conditional on commercial rights. No production market ingestion or publication of affected datasets before permission and separate authority.
- CAS-first portfolio intake. Groww/Zerodha are optional read-only capabilities, subject to provider permission and separate owner approval. No broker execution, distribution commissions or client-money custody.
- Wickstreet 3.0 retains stocks, Company Intelligence, advanced charting, Momentum25, Strategy Studio and the unified equity roadmap. Existing code, `strategy_id=30`, manifest invariants, Gate 0 G-1 to G-5, sealed hold-out, ADR statuses and audit records are preserved.

## A1. Free and Pro capabilities

| Capability | Free | Pro ₹199/year | Boundary |
|---|---|---|---|
| Discovery, screening, factual comparisons | Comprehensive | — | User-selected criteria; no curated buy list |
| NAV charts, historical returns, risk metrics, TER/costs | Included, rights gated | — | Method, date and coverage shown |
| Holdings and overlap | Included where licensed | — | Factual exposures |
| CAS import, XIRR, allocation and concentration diagnostics | Included | — | Describe the portfolio; no switch instructions |
| Advanced allocation scenarios | — | Included | User selects funds, weights, amounts and assumptions |
| SIP, lumpsum and goal calculators | — | Included | Mathematical outcomes under user-entered assumptions |
| Rebalancing simulations | — | Included | User selects targets, dates, thresholds and cost assumptions |
| Side-by-side comparisons, saved scenarios and reports | — | Included | No suitability ranking or recommended winner |
| Groww/Zerodha portfolio connectivity | — | Optional after approval | Read-only; never a launch dependency |
| Personalised allocation, scheme selection or investment instructions | Excluded | Excluded | Separate future D0-IA capability |

A goal calculator may state the contribution required under the user's return assumption. It must not choose the return, fund or risk allocation. A rebalance simulator may calculate differences from a user-selected target; it must not prescribe that target or tell the user to transact.

**UX safeguards:** no profile-selected defaults, automatic fund replacements, optimisation, “best for you” rankings, “rebalance now” nudges, or historical CAGR prefilled as a future return. Neutral form examples must be visibly hypothetical and require explicit adoption; they must not contain a default investable portfolio. User-selected sorting is labelled with its criterion and period. Factual drift alerts are opt-in and use user-defined thresholds. Reports preserve the same boundary as the UI.

Use “simulate”, “your selected allocation”, “calculated outcome” and “compare”. Avoid “recommended”, “ideal portfolio” and “you should invest”. Disclose assumptions, methods, data dates, missing coverage and historical limitations. Disclaimers support truthful behaviour; they do not change its classification.

## A2. Regulatory classification and gates

**Working classification, not a SEBI approval:** genuine user-controlled calculations need neither IA registration nor advisory onboarding merely because they concern mutual funds. PRO-0 reviews actual workflows for IA **and** RA exposure. A feature that becomes advice is removed/redesigned or enters the separately approved future pathway; registration is not imposed on the whole product by default.

| Workflow | Classification / action |
|---|---|
| Factual data, user-chosen comparisons, XIRR and descriptive portfolio metrics | Analytical candidate; validate content and data rights |
| User-authored historical/assumed-return scenarios | Analytical candidate; no platform-generated investment prescription |
| Profile-selected allocation, named fund/amount recommendation, buy/sell/hold instruction | Potential regulated advice; excluded |
| Curated fund ratings, recommended portfolios or investment opinions | Potential research service even without personalisation; excluded pending separate assessment |
| Account access and billing | Ordinary SaaS obligations; no advisory KYC, suitability review, advisory agreement or advisory retention by default |

SEBI's RA FAQ clarifies that securities coverage is broad, and that the mutual-fund periodic-report exclusion covers specified account/regulatory communications. It is not a blanket exemption for a fund-analysis platform. Sources R1–R3 govern the feature review.

### A2a. October 2026 and educational-data updates

| Primary update | Status and application |
|---|---|
| Certification amendment listed 9 October 2026, notification 7 October | Gazette-publication commencement; electronic Gazette dated 9 October, printed issue 8 October. Changes to “specified persons”, specified NISM programme routes and possible extended certification validity. Already published by review date; no automatic IA certification duty for an unregistered calculator SaaS. Check a specific notified route if future advice is pursued. R4 |
| Intermediaries amendment listed 10 October, notification 8 October | Common Advertisement Code expressly covers specified regulated entities including IAs/RAs. Commences on the 180th day after Gazette publication, not immediately. Printed issue 9 October/electronic publication 10 October: calendar interpretation to confirm before any registered launch; use the earlier April 2027 readiness date conservatively. Not a default 2.0 regulated-entity obligation. R5 |
| RA amendment listed 10 October, notification 8 October | Institutional-client call-recording relaxation; commences 30th day after Gazette publication. Not yet operative on 22 October and not a retail recommendation exemption. R6 |
| 8 May 2026 educational price-data circular | Effective 1 July 2026; 30-day educational sharing/use rules and a specific NISM exception. Map each data flow; Wickstreet cannot claim NISM's exception. R7 |

The educational circular is not commercial redistribution permission. Do not assume every latest NAV display must be delayed, or that all NAV simulations are exempt. PRO-0/D0-MF classify historical simulations, current descriptive valuation and user-entered hypothetical calculations separately. Covered educational feeds use the required lag and agreement; pure assumption calculators can operate without such a feed.

### A2b. Mandatory launch work versus scaling

“Required” below means an owner/product launch gate or an actual applicable obligation; a professional opinion, insurance policy or annual retainer is not universally mandated merely by operating SaaS.

| Stage | Required before that exposure | Deferred until justified |
|---|---|---|
| Development on synthetic fixtures | Existing infrastructure, repo access controls, deterministic methods, input tests | New hosting, paid CI, monitoring subscriptions, SRE, managed DB |
| Publishing affected MF datasets | Written commercial rights covering retrieval, storage, display, history/simulation and export; source/date evidence | Paid feeds, broad AMC coverage, ETFs/TRI; narrow or hold the feature if rights fail |
| Private beta with real CAS | Auth, tenant isolation, secure uploads, TLS, private DB, encryption, consent/deletion flows, backup/restore, scoped independent security review | Enterprise audit packages, 24/7 SOC, multi-region deployment |
| Paid launch | PRO-0 actual-workflow review; lawful account/privacy/subscription/refund/payment handling; payment-provider acceptance; applicable business/tax filings; measured beta capacity | Broad recurring legal retainers, dedicated compliance staffing, advisory agreements/KYC |
| Growth | More capacity/support/security expenditure only when load, data volume, incidents, obligations or founder workload require it | Dedicated SRE or salaried engineers without a separate owner decision |

Retain a **proportionate independent pre-CAS security assessment** as the existing owner gate, with no open critical/high findings. Its scope and price require a quote; the gate does not imply a ₹1.5 lakh enterprise engagement. Repeat assessment after material risk changes and where required, rather than impose the old annual enterprise budget by default.

Ordinary SaaS security/privacy obligations remain applicable. SEBI CSCRF/cloud/regulated outsourcing requirements are assessed for actual entity/activity/contract applicability; they are not automatically imposed while Wickstreet is an unregistered analytics service. Preserve those reviews for a future regulated capability (R11–R12).

## A3. Bootstrapped economics

**Model `SIM-BOOT-2026-10-22-v1`: arithmetic verified; inputs unverified unless sourced.** Estimates are expenditure envelopes, not purchase authority or supplier quotations. No IA-only expenses, deposits, supervisory charges, advisory agreements or ₹40 advisory/client allowance appear. No founder salary, SRE or paid engineering is hidden in the budgets.

### A3a. Unit economics and stage budgets

| Input | Lean launch | Growth stage |
|---|---|---|
| Price | ₹199/year including assumed 18% GST | Same |
| Revenue before refund, excluding GST | ₹168.644068 | Same |
| Refund reserve | 2% of revenue | Same; not a customer refund policy |
| Payment processing | 2% of gross +18% GST on fee = ₹4.6964/invoice | Same; no ITC or promotion assumed |
| New-customer CAC | ₹40 | ₹100 |
| Annual renewal retention | 80% | 70% |
| Free : active paid | 10:1 | 10:1; test 5:1/25:1 |
| Free account cost | ₹2/year | Same assumption, measure actual usage |
| Development hosting | ₹0 incremental | Growth expenditure starts with production exposure |
| Credits / MF data licence | ₹0 credit benefit / conditional ₹0 licence | Same |

Payment rate anchor: R9. Merchant acceptance, subscription extras, refunds and settlement timing require confirmation. GST remains a conservative modelling assumption, not a claim that every pre-threshold business must register. Actual registration, invoicing, credit notes and input credits require entity-specific tax review.

The following annual budgets cover incremental production hosting/backups, email, monitoring, routine risk-based security work, accounting/privacy maintenance, tools and support tooling. They exclude initial launch review work below and founder compensation. **They are not all mandatory costs and are not triggered by account count alone.** Counts index the financial scenario; actual capacity/spend decisions use measured traffic, jobs, storage and obligations. Intermediate model values interpolate linearly; no extrapolation above 50,000.

| Paying users | 1,000 | 5,000 | 10,000 | 13,000 | 25,000 | 50,000 |
|---|---|---|---|---|---|---|
| Lean annual envelope, ₹ lakh | 0.36 | 0.60 | 0.96 | 1.20 | 2.40 | 4.80 |
| Growth annual envelope, ₹ lakh | 1.20 | 1.80 | 3.00 | 3.60 | 6.00 | 10.00 |

Lean starting envelope: ₹14,400 host, ₹3,600 backup/storage, ₹2,400 email, ₹9,600 admin/tools and ₹6,000 routine security work per year = ₹36,000. These are U allowances, not verified AWS or professional quotes. Existing capacity may reduce actual incremental spend; missing legal/entity costs may increase it. The growth envelope permits managed services, deeper reviews and support help when justified, but contains no salaried engineering or SRE. Reconcile supplier line items before authorising each increase.

Steady-state contribution per payer = `199/1.18 × .98 − 4.6964 − 2×free_ratio − (1−retention)×CAC`. This is ₹132.574786 lean / ₹110.574786 growth. Acquisition here replaces annual churn; the monthly growth forecast charges full CAC to every new payer. First-year margins before fixed costs are ₹100.57 lean / ₹40.57 growth; renewals have no new-customer CAC.

Annual steady-state results, ₹ lakh; costs include refunds, payment fees, free users, replacement CAC and the stage envelope. Surplus is before founder pay, income tax and recovery of launch costs.

| Payers | Gross | Ex-GST revenue | Lean costs | Lean surplus | Growth costs | Growth surplus |
|---|---|---|---|---|---|---|
| 1,000 | 1.99 | 1.69 | 0.72 | 0.97 | 1.78 | -0.09 |
| 5,000 | 9.95 | 8.43 | 2.40 | 6.03 | 4.70 | 3.73 |
| 10,000 | 19.90 | 16.86 | 4.57 | 12.30 | 8.81 | 8.06 |
| 13,000 | 25.87 | 21.92 | 5.89 | 16.03 | 11.15 | 10.77 |
| 25,000 | 49.75 | 42.16 | 11.42 | 30.74 | 20.52 | 21.64 |
| 50,000 | 99.50 | 84.32 | 22.83 | 61.49 | 39.03 | 45.29 |

**Model operating break-even:** lean ≈272 payers; growth ≈1,099. These assume the starting envelopes remain sufficient, and do not recover launch investment. **Founder-sustainable**, at ₹24 lakh/year compensation: lean ≈19,499; growth ≈27,492. Neither is proof that one person can support that scale; support/incident time must be measured and capacity costs may change the thresholds.

### A3b. Illustrative cohort cash-flow scenario — 24 months; not a forecast

This is a conditional planning illustration, not a committed forecast, budget, sales target or promise of launch timing. The subscriber path is an unvalidated acquisition scenario; actual demand, CAC, retention, settlement timing, supplier quotes and legal obligations may materially change receipts, costs and funding needs. It is not a basis for committing expenditure. Rebuild the cash flow from observed pilot cohorts and actual costs before a paid launch or funding decision.

M1 November 2026; M7–8 private analytics beta; M9 conditional paid launch July 2027; M24 October 2028. This schedule is an illustration, not implementation authority. If a gate fails, receipts move later and discretionary spend pauses.

- M1–6 development hosting/running cost: **₹0 incremental** using existing resources. No automatic monthly legal/security/operations spend.
- M6 launch-preparation allowance: ₹25,000 targeted workflow/data/privacy/terms review + ₹25,000 scoped independent security review = ₹50,000. **U, not quotes or a legal minimum**. Pay only when those reviews become necessary for the intended exposure. No incorporation/trademark spend is assumed; if existing arrangements are insufficient, add the actual required cost before launch.
- M7–8: ₹1,800/month production-beta envelope, triggered by real users, plus free-account cost. M9 onward: stage annual envelope at active paid count /12, using the 1,000-user minimum until actual costs justify less.
- No separate annual VAPT or ₹3 lakh initial opinion is charged. Material-change assessment/legal costs must fit the selected envelope or be added transparently.
- Full new paid cohorts M9–12: 200, 300, 400, 500; M13–24: 600, 650, 700, 750, 800, 850, 900, 950, 1,000, 1,050, 1,100, 1,150. This remains an **unvalidated demand path**, not a forecast justified by pricing alone.
- Renewals occur exactly 12 months later: `R[m]=retention×N[m−12]`; first renewals M21. Active = sum of new and renewed contracts issued in the latest 12 months. Failed renewals are already in retention; no duplicate churn charge.
- Free accounts M7 onward = `max(2,000,10×active)`; earlier zero. Refunds are reserved in collection month; expected service capacity is retained through expiry conservatively.

Reproduction equations, unrounded rupees: `gross=199×(N+R)`; `refund=.02×gross`; `GST=(gross−refund)×18/118`; `net_receipts=(gross−refund)/1.18`; `PG=4.6964×(N+R)`; `cash_delta=net_receipts−PG−CAC×N−2×free/12−stage_running_cost−launch_review_cost`. Cumulative cash starts at zero; no deposits, financing, salary or credit inflows. Assume collection/settlement in month of sale and immediate GST reserve; actual settlement lag must be added if material.

Monthly cash movements and cumulative positions, ₹ lakh (negative cumulative values are required funding, not permitted overdrafts). Both cases use the full cohort path; operating budgets and CAC/retention differ as above.

| Month | Lean cash Δ | Lean cumulative | Growth cash Δ | Growth cumulative |
|---|---|---|---|---|
| 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| 3 | 0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 0.000 | 0.000 | 0.000 | 0.000 |
| 5 | 0.000 | 0.000 | 0.000 | 0.000 |
| 6 | -0.500 | -0.500 | -0.500 | -0.500 |
| 7 | -0.021 | -0.521 | -0.021 | -0.521 |
| 8 | -0.021 | -0.543 | -0.021 | -0.543 |
| 9 | 0.208 | -0.335 | 0.018 | -0.525 |
| 10 | 0.323 | -0.011 | 0.073 | -0.451 |
| 11 | 0.437 | 0.426 | 0.127 | -0.324 |
| 12 | 0.548 | 0.973 | 0.175 | -0.150 |
| 13 | 0.655 | 1.628 | 0.218 | 0.068 |
| 14 | 0.701 | 2.330 | 0.229 | 0.297 |
| 15 | 0.746 | 3.076 | 0.239 | 0.536 |
| 16 | 0.790 | 3.867 | 0.247 | 0.783 |
| 17 | 0.833 | 4.700 | 0.254 | 1.037 |
| 18 | 0.875 | 5.575 | 0.254 | 1.291 |
| 19 | 0.914 | 6.489 | 0.251 | 1.543 |
| 20 | 0.953 | 7.442 | 0.247 | 1.789 |
| 21 | 1.249 | 8.691 | 0.467 | 2.257 |
| 22 | 1.415 | 10.106 | 0.575 | 2.832 |
| 23 | 1.580 | 11.686 | 0.683 | 3.515 |
| 24 | 1.744 | 13.431 | 0.793 | 4.308 |

| Funding result | Lean | Growth |
|---|---|---|
| Peak cumulative deficit | ₹54,267 (M8) | ₹54,267 (M8) |
| Opening funding +20% headroom | **₹65,120** | **₹65,120** |
| M24 cumulative cash | +₹13.431 lakh | +₹4.308 lakh |

These low funding outputs depend heavily on the assumed conversions, CAC and review quotes. They are **not a guarantee that ₹65,120 funds a viable business**. The growing customer base must finance its service obligations; annual advance receipts are not immediately earned profit. Earn revenue over 12 service months and track the deferred balance. Founder living costs are excluded.

Downside checks using the lean operating envelope: half-sized cohorts, CAC ₹100/70% retention → M24 +₹2.57 lakh; half-sized cohorts, CAC ₹150/60% retention → M24 −₹0.52 lakh and peak funding with 20% headroom ≈₹1.07 lakh. Zero paid conversions while keeping 2,000 free beta users online through M24 → cumulative −₹1.08 lakh, funding/headroom ≈₹1.29 lakh. In practice, stop expansion/reassess before paying indefinitely for an offer without demand.

Sensitivity: at 70% retention, contribution for free:paid 5/10/25 is ₹138.57/128.57/98.57 with CAC ₹40, ₹120.57/110.57/80.57 with CAC ₹100, and ₹75.57/65.57/35.57 with CAC ₹250. At CAC ₹250, 50% retention and 25:1, contribution becomes **−₹14.43**: no scale fixes negative contribution. Free-user retention/traffic can exceed the ratio proxy; update the measured account and active-user model rather than assume old free users disappear.

### A3c. Spend triggers

| Trigger | Response before spending |
|---|---|
| Development only | Reuse infrastructure; no incremental hosting commitment |
| First external users | Verify safe production isolation; deploy the smallest adequate host if existing resources are unsuitable |
| Queue delay, latency, sustained CPU/memory or storage pressure | Profile/cache/rate-limit first; resize or separate workers/DB based on measurements |
| More CAS/history/log volume | Measure storage and restore time; adjust retention and backup capacity lawfully |
| Restore or availability objective fails | Repair recovery/hosting design; spend on redundancy when justified |
| Material security change or finding | Scoped independent reassessment; remediate before increasing exposure |
| Founder support/incident workload exceeds agreed capacity | Restrict intake, improve self-service or separately approve assistance; no hidden SRE budget |
| New legal duty or supplier tariff | Record applicability/quote and update the model; do not fund it by silently assuming free labour |

AWS credits reduce actual bills only after award; no assumed award, stacking, validity or application is required for viability. Budgets/alerts use pre-credit consumption. Avoid Kubernetes, NAT gateways, multi-region infrastructure, always-on load balancers and managed-service expansion until a measured need justifies them.

## A4. Architecture, rights and delivery

**Simulation engine proposal:** pure deterministic domain calculations over explicit user inputs; application orchestration; source-neutral data and persistence adapters; thin API/UI. Reuse existing FastAPI/PostgreSQL, Compose, ledger, point-in-time and immutable snapshot investments. No new microservice is required at launch.

Each run records user-selected funds/weights/amounts/timing, assumptions and cost/rebalance rules; the selected data revision and lawful cutoff; engine/method versions; rounding conventions; coverage; input/output hashes. Same inputs and versions reproduce the same result. Persist scenario evidence for user reproducibility under an appropriate SaaS retention/deletion policy, not an invented advisory five-year obligation. No suitability engine, recommendation model or LLM investment instructions.

Tests planned for later authorised work: cash/unit conservation; SIP timing and rounding; rebalance transaction/cost assumptions; missing/stale NAV and coverage; deterministic replay and point-in-time visibility; tenant isolation and output wording. Methodology requires owner approval before code.

**D0-MF:** per dataset, establish commercial retrieval, storage, display, simulation/history, derived report and export permissions in writing before publication/ingestion. R8 does not establish those rights by public availability. Retain source/date/permission evidence and fail closed per use; no aggregator workaround. User-entered hypothetical calculators can proceed on fixtures without a market feed. Historical simulations and the full research product wait for rights; narrow or hold affected capabilities if permission fails.

**CAS baseline:** password in memory only, secure parser sandbox/limits, preview/undo, discard raw PDF after the defined processing step, encrypt retained records, tenant controls, consent/deletion and backups. Never put real CAS into development fixtures or logs.

**Provider boundary:** official Kite documentation identifies read-only MF holdings and says MF order placement cannot be done through those APIs (R10). Groww public equity holdings APIs do not establish an MF connector. No claimed Groww MF sync until written approval. No broker credentials scraping, execution or commission-funded business model.

**Rules for every increment:**
- **Founder-only work:** architecture and ADRs; authentication, sessions and tenancy; billing and webhooks; the rights gate; production migrations and deploys; secrets; incident response; CAS-upload security; final merge.
- **Intern-suitable work:** importers and parsers on synthetic fixtures; metric functions against an approved dictionary; UI pages inside `WorkstationShell`; tests (unit, PIT harness, Playwright); documentation.
- **Access:** interns never get production access, secrets or real personal data. Synthetic fixtures only, as every E2E test does today. Protected main branch, founder review and merge, CI green before review.
- **Intern agreements:** an internship agreement with IP assignment and confidentiality before any access. **Zero remuneration cannot be assumed lawful for every engagement called an internship.** Formal apprenticeships under India's apprenticeship framework carry stipend requirements. Each other arrangement needs its own classification (legal opinion item).
- **Interns are uncertain capacity (P1).** The plan must stay viable when an intern leaves mid-package:
  - no critical-path item depends on intern delivery;
  - every package ships with its spec, tests and a short handover note in the repo;
  - code is reviewed for maintainability by someone other than its author;
  - an unfinished package is parked on a branch, never half-merged.
- **Security and production stay founder-owned (P0)**, with independent professional assessment where needed. Interns never touch auth, tenancy, billing, secrets, production data or the rights gate.
- **Package size:** one vertical slice per package, 1–2 weeks, with a written spec, fixtures and acceptance tests up front, a reviewable change (no commit without separate authority), and the existing verification steps (`pytest`, `mypy`, `ruff`, `lint-imports`, migrations on a fresh DB, Vitest, Playwright).


**Usability goal (owner, 2026-10-22): the free tier offers better usability than Tickertape.** This is a target to prove, not a claim to publish.
- **Benchmark (UX-1, before beta and again before launch):** the same fund tasks on Wickstreet free and on Tickertape's free tier. Tasks: find a fund, read its returns and risk, compare 2–3 funds, see its costs. Measure interactions to answer, time to answer, task success, and interruptions (paywalls, ads, sign-up walls).
- **Pass bar:** fewer interactions and higher task success on every task. The existing I-5 rule (any capability within 2 interactions from where the user is) holds. Keyboard and screen-reader checks pass. Light and dark themes are checked at 1440, 1024 and 390 px.
- Results go in `docs/audits/`.


### A4a. Sequence and launch gates

All stages below describe future work and need separate implementation/expenditure authority.

| Stage | Deliverable | Gate |
|---|---|---|
| D0-MF / PRO-0 | Rights map; screen/default/report/notification classification against IA/RA and educational-data rules | Founder review and targeted professional clarification where needed; remove unclear prescribing features |
| SIM-0 / S0-A | Calculation dictionary; hosted/auth/tenancy/billing/rights/privacy/simulation ADR proposals | Owner accepts methodology and architecture; ADR-010/012 and proposed ADR-019/021 changes remain proposals |
| W0 / MF2-0 | Synthetic fixtures, identity isolation, rights harness, portfolio accounting spec | Existing invariants and acceptance tests preserved |
| B1–B4 | CAS → accounting/XIRR → compare owned funds → descriptive risk/overlap | Accuracy, provenance and upload security verified |
| SR-0 / SR-1 / H0 | Threat model, scoped independent review, production hardening, encrypted off-host backup and restore drill | No open critical/high findings before live CAS; no production data on development infrastructure |
| LT / free beta | Founder-operated capacity test and portfolio-first beta | Expected beta peak passes NFR targets; users can complete portfolio tasks |
| DV / MF1 | Validate ₹199 simulation demand; complete comprehensive discovery | Intent, task success, actual paid conversion and fully loaded CAC measured; no advice pre-order |
| SIM-1 | User-controlled allocation, SIP/lumpsum/goal scenarios | Determinism, arithmetic parity and PRO-0 wording/default checks |
| SIM-2 | Rebalance simulation, comparison, reports, saved scenarios | User-selected rules, explainability and output boundary preserved |
| Paid pilot / launch | Useful end-to-end Pro product | Rights, PRO-0, security, payments/privacy and observed capacity pass; owner go/no-go |
| Optional connectors | Provider-approved read-only Groww/Zerodha | Separate approval and cost assessment; no launch dependency |
| Growth | Capacity/support/security expansion | Measured spend triggers, reviewed unit economics and separate spending authority |
| Future D0-IA | Personalised advice, if later desired | Separate product/legal/business-case/registration decision; not part of 2.0 launch |
| 3.0 | Stock/Company Intelligence/charting/Strategy Studio/Momentum25 roadmap | Existing investments retained; separate equity rights and scope authority |

**Demand gate:** a useful fixture-based prototype and direct user research come before substantial spending. Historical waitlist ≥2,000/20% stated intent, CAS activation ≥40% and paid conversion ≥5% remain comparison hypotheses, not prerequisites for learning with a small pilot. Validate the simulation offer itself: a payer can save/compare scenarios and explain the benefit over free diagnostics. Measure CAC including unsuccessful acquisition attempts and founder acquisition time separately. Renewal is measured only when cohorts reach 12 months; 80%/70% are assumptions until then. Test 5:1, 10:1 and 25:1 free:paid exposure.

## A5. Current owner decision register

| ID | Current decision / status | Still required |
|---|---|---|
| OD-1/2 | MF 2.0 / stocks 3.0 split retained; W0 investment retained; W1 belongs to 3.0 | No rewrite of historical Gate 0 or implemented code |
| OD-3 | Rights/provider correspondence remains unsent | Owner controls actual sending/permissions; existing commercial rights still unresolved |
| OD-4 | Targeted legal clarification of real workflows/data/terms, not automatic enterprise retainer | Applicability, scope and quotes before expenditure |
| OD-5/8 | Validate simulations using a small useful prototype; scale acquisition on observed economics | Pilot metrics, CAC ceiling, renewal evidence |
| OD-6/15 | Comprehensive free research; ₹199 Pro self-service simulations | PRO-0 behaviour review and demand evidence |
| OD-7 | Architecture scope proposed in this plan | Accept ADR/methodology changes before code |
| OD-9 | Portfolio-first; scoped independent security check before live CAS | Assessment quote and findings closure |
| OD-10 | Replace old funding claims with stage/cohort model; development hosting ₹0 incremental | Validate review costs, actual production costs and own living runway; no spend authority |
| OD-11/12 | Founder-managed hosting; credits optional; spending follows measured demand | Appropriate production setup, bill alerts and restore evidence |
| OD-13 | Personalised advice deferred; founder-led non-individual IA only a future working hypothesis, subject to D0-IA | No eligibility/registration commitment; later compare partnership on actual costs |
| OD-14 | CAS-first, optional approved read-only connectors; no execution or commissions | Provider permissions and separate integration approval |
| OD-16 | Simulation calculation/version/input contract proposed | Owner approves exact timing, rounding and rebalance rules |
| OD-17 | Founder support/incident limits must be explicit before scaling | Measured workload, intake cap and fallback access/runbooks |
| OD-18 | Quotations remain pending; owner requested drafts to send from StackVerity | No requests sent or supplier selected; replace allowances with applicable SaaS quotes, not IA procurement |

Remaining blockers: commercial dataset permissions; actual-flow IA/RA classification of any ambiguous ratings/defaults; educational-cutoff treatment; payment merchant approval; lawful privacy/business arrangements; independent pre-CAS security scope/quote; demand and founder-capacity evidence. None requires buying growth infrastructure before development.

## A6. Sources and evidence status

V = primary publication verified during review; I = product-specific interpretation, requires actual workflow assessment; U = unverified planning assumption/quote. Legal sources describe rules, not a SEBI approval of Wickstreet. Recheck amendments at release.

- **R1 (V):** [IA Regulations, December 2024 consolidation](https://www.sebi.gov.in/sebi_data/attachdocs/dec-2024/1735037757673.pdf), definitions and risk/suitability boundary. Read with later amendments.
- **R2 (V):** [February 2026 IA Master Circular](https://www.sebi.gov.in/sebi_data/attachdocs/feb-2026/1770375291405.pdf). Experience removed December 2024; graduate/certification route broadened November 2025. Future IA analysis must not assume obsolete experience barriers. Deposits ₹1/2/5/10 lakh by prescribed client bands are future-only; liquid/overnight MF options exist. No deposit is a 2.0 simulation expense.
- **R3 (V):** [SEBI RA FAQ, July 2025](https://www.sebi.gov.in/sebi_data/attachdocs/jul-2025/1753268710217.pdf), questions 4–8; [February 2026 RA Master Circular](https://www.sebi.gov.in/sebi_data/attachdocs/feb-2026/1770375507051.pdf). No blanket exclusion for all fund analytics.
- **R4 (V):** [SEBI certification amendment listing, 9 October 2026](https://www.sebi.gov.in/legal/regulations/oct-2026/securities-and-exchange-board-of-india-certification-of-associated-persons-in-the-securities-markets-amendment-regulations-2026_105146.html); [original Gazette reproduced by NSE](https://nsearchives.nseindia.com/content/circulars/COMP76971.pdf), SEBI/LAD-DOP/2026/319. SEBI direct PDF did not load; original Gazette annexure was read.
- **R5 (V):** [Intermediaries Second Amendment, October 2026](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1791796362093.pdf), SEBI/LAD-NRO/GN/2026/323, commencement clause 2 and Common Advertisement Code.
- **R6 (V):** [RA amendment, October 2026](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1791796596784.pdf), SEBI/LAD-NRO/GN/2026/321, commencement clause 2 and institutional-client recording change.
- **R7 (V):** [Educational price-data circular, 8 May 2026](https://www.sebi.gov.in/sebi_data/attachdocs/may-2026/1778242522289.pdf), paragraphs 6–7. Effective 1 July 2026.
- **R8:** [AMFI terms of use](https://www.amfiindia.com/terms-of-use), personal/non-commercial restriction; commercial permission remains unresolved. Also retain [12's evidence and permission questions](12-d0r-data-source-research.md).
- **R9 (V):** [Razorpay published pricing](https://razorpay.com/pricing/), standard 2% +GST; merchant/product acceptance and actual invoice are unverified. No discount or ITC assumed.
- **R10 (V):** [Kite MF documentation](https://kite.trade/docs/connect/v3/mutual-funds/); [Groww portfolio documentation](https://groww.in/trade-api/docs/python-sdk/portfolio). Public documentation is not multi-user commercial permission.
- **R11 (V):** [SEBI CSCRF](https://www.sebi.gov.in/sebi_data/attachdocs/aug-2024/1724326790365.pdf) and [June 2025 CSCRF/cloud FAQs](https://www.sebi.gov.in/sebi_data/faqfiles/jun-2025/1749647139924.pdf). Category-specific applicability and later clarifications must be assessed if becoming a regulated entity.
- **R12:** [SEBI cloud framework](https://www.sebi.gov.in/legal/circulars/mar-2023/framework-for-adoption-of-cloud-services-by-sebi-regulated-entities-res-_68740.html), IA Master Circular §13 outsourcing/Annexure H, and [24 August 2026 FIRE portal update](https://www.sebi.gov.in/legal/circulars/aug-2026/alignment-of-sebi-s-cyber-incident-reporting-portal-with-fire-format_103915.html). Future regulatory review includes incident reporting, provider/subcontractor controls, regulator access, retention/exit and continuing IA responsibility. Generic outsourcing rules must be reconciled with specific permitted compliance-professional arrangements.

## A7. Historical decisions — superseded as current direction

The sequence on 2026-10-22 was: MF/stock release split; personalised-advice exploration; analytics-only direction; founder-led IA reassessment; return to user-controlled simulations; bootstrapped spending correction; approval of repository documentation edits. No intermediate proposal authorised code, data ingestion or an IA application. Earlier ₹9–11/₹19–21/₹32 lakh and later enterprise-style simulation funding estimates are retired as current budgets. Prior cost assumptions are not validated quotations.

Earlier owner-register text is preserved verbatim below as history; current A5 controls the planning direction. Historical “adopt”/“approve” text does not grant new expenditure or implementation authority.

<details>
<summary>Earlier A5 owner register (historical)</summary>

### A5. Owner decisions (each with my default)
- **OD-1** Adopt the split. *Adopt.*
- **OD-2** Re-scope Stage A: W0 kept, W1 moved to 3.0. G-1 to G-5 kept as history. *Adopt.*
- **OD-3** Send the AMFI and Zerodha letters (I draft, you send). *Approve.*
- **OD-4** Commission the legal opinion. It now also covers **SEBI IA scope**: which Pro features are advice, own registration vs partnership, principal-officer eligibility, KYC and agreement duties, and the provider hand-off. It covers the circular, site terms, automated retrieval, paid re-hosting, SEBI RA/IA, DPDP, subscription law and internship terms. *Commission before real data.*
- **OD-5** Run demand validation (DV) before S0-B. *Run.*
- **OD-6 (replaced per owner, 2026-10-22): free/paid boundary.**
  - **Free** offers comprehensive MF research, comparison, overlap, CAS import and descriptive portfolio diagnostics.
  - **Pro ₹199** offers interactive allocation simulations, scenario comparisons, goal-planning calculators, educational model portfolios, detailed reports, and Zerodha/Groww sync once approved. **Users choose; Wickstreet does not instruct.**
  - Personalised recommendations are excluded from the launch and gated by D0-IA.
  - Plan on 10 free users per payer and test 5:1 and 25:1. Free-user cost stays low through cached shared pages and rate limits.

  *Adopted.*
- **OD-13** Later Pro Advice: own IA registration or RIA partnership. *Deferred; default RIA partnership unless the founder qualifies as principal officer. Revisit only if the product promise becomes "Wickstreet tells you where to invest".*
- **OD-14** If advice is ever offered: advice-only, direct plans, no commissions; execution as a link-out. *Adopt as a standing rule.*
- **OD-15** Pro launch scope = decision support with the A1 safeguards, signed off in PRO-0. *Adopted.*
- **OD-7** Accept the S0-A ADR list. *Accept.*
- **OD-8** Thresholds, kept apart:
  - **pre-launch (DV):** waitlist ≥ 2,000; stated intent-to-pay ≥ 20%; observed CAC ≤ ₹100;
  - **beta:** ≥ 40% of beta users import a CAS; ≥ 5% convert at ₹199;
  - **post-launch:** renewal ≥ 70% at month 12.

  *Accept as planning values; revise after DV.*
- **OD-9** First beta is portfolio-first (B1–B4); discovery (MF1) follows. *Adopt.*
- **OD-10** Founder capital ≈ ₹9–11 lakh for the free product and an analytics-only Pro. Add the IA bank deposit (up to ₹10 lakh, refundable) if Wickstreet registers as an IA itself. CAC > ₹250 is a stop signal. *Accept.*
- **OD-11** Founder-managed AWS as the default, with the Indian VPS as the fallback after credits:
  - one EC2 instance in ap-south-1, Docker Compose, PostgreSQL;
  - S3 backups, Cloudflare in front;
  - a Paid plan with credits applied; AWS Budgets on pre-credit usage;
  - scale on measured triggers; no home machine as the production host.

  *Adopt.*
- **OD-12** Apply for AWS Activate Founders ($1,000) shortly before beta. Plans and prices use the sustainable (full-bill) case; credits are upside. *Adopt.*


</details>

## Part B — Documentation changes and verification

Approved edits are limited to this canonical file, [README](README.md), [10 roadmap](10-roadmap.md) and [11 staged plan](11-wickstreet-2.0.md). Supporting documents receive scope/status banners; their historical decisions and detailed designs remain intact. No duplicate release-plan file or memory edit is required. ADR bodies, blueprint 01–09, code, strategies, audit/history files, staged research and index state are preserved.

Verification for this amendment: validate relative file/anchor links; recompute annual tables, all 24 monthly cash movements, renewal timing, cumulative balances, break-even interpolation and downside cases from the stated inputs; compare staged diff before/after; hash-check unrelated files. No application test suite is required for documentation-only edits. Financial arithmetic verification does not validate demand, data permissions, vendor prices or legal conclusions.
