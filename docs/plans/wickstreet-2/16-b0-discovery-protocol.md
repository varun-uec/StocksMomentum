# Wickstreet 2.0 — B0 Discovery Protocol

> **Status: Accepted planning protocol (2026-10-22).** This document defines a bounded discovery method; it does not itself authorize interviews, recruitment, participant data collection or recording, Tickertape account activity, prototype work, vendor contact, spending, data acquisition, implementation or deployment. The single Tickertape session separately authorized by the owner and completed on 2026-10-22 is recorded in §5.2; it grants no continuing account-access authority. Each other activity requiring external contact or account access needs separate owner approval.
>
> **Authority:** [Accepted B0 planning baseline](15-stage-b0-product-and-value-specification.md), the [Stage B implementation plan](14-stage-b-implementation-plan.md), and [ADD Amendment A3](../../architecture/ADD-amendment-A3.md). This protocol does not change release scope, architecture, the ₹199 price hypothesis, or the separate B0/B1 approval gates.

## 1. Purpose and boundaries

Discover which mutual-fund research tasks self-directed investors struggle with, compare those tasks with publicly visible and—only after approval—hands-on alternatives, and identify a credible first research-workstation proposition at ₹199/year. Explore customer value, lawful data economics and low-cost distribution together. Do not select the final Free/Pro bundle or infer market demand from a small qualitative sample.

A paid research workspace leads the hypotheses, not the approved product. Basic calculators are supporting/free candidates. Define the task and feasible bundle before proposing price tests: ₹199 remains unvalidated, and ₹399–₹499 alternatives require separate test design and approval. Neither a suggested paywall nor an illustrative cash-flow scenario establishes demand or viability. Production tenancy and commercial publication clearance are exposure gates; they do not block an approved synthetic usability test with appropriate participant safeguards.

The long-term objective is useful Tickertape-class MF capability, but evidence from a synthetic prototype has strict limits. It can test task usability and H2's incremental integration value, and provide preliminary evidence that the research tasks are useful for H1. It cannot prove real MF coverage, metric accuracy/currentness, actual capability parity or willingness to pay. Those require separate functional coverage/quality assessment on appropriate rights-cleared data and a price test against the exact commercially feasible feature bundle.

Personalised recommendations, user-specific allocation, suitability and rebalancing instructions remain outside this discovery proposition. Participants describe their own research; Wickstreet does not tell them what to buy.

### 1.1 Owner decision: no-outreach prototype path

> **Superseded in part, 2026-10-23:** [ADR-023](../../architecture/adr/ADR-023-operating-modes.md) replaces the throwaway prototype with the Phase 1 production-evolvable personal application. Saved research uses the tenant-enforced persistence of ADR-023 §2.6 from the first slice, not separate prototype storage. Data follows [ADR-022 §2.11](../../architecture/adr/ADR-022-multilingual-research-agent.md): rights-clean real data, AMFI only within the owner-set personal scope, synthetic fixtures in tests. The no-outreach rule and the completed Tickertape benchmark still apply.

The owner has replaced interview-led discovery as a prerequisite for the initial synthetic prototype. This decision takes precedence over interview/recruitment requirements and Discovery Gate packets elsewhere in this protocol and the B0 baseline for this internal slice only. Interviews, recruitment, surveys and vendor outreach are prohibited under the current scope, not deferred tasks that block prototype development. The accepted six-task Tickertape observations in §5.2 supply the initial functional benchmark; do not repeat completed account research.

Present one concise scope, implementation boundary and acceptance criteria for separate owner approval, then implement that approved slice: discovery/filtering → scheme information and synthetic historical research → consistent fund comparison → metric definitions/provenance → private saved research. Reuse the existing stack/components and design language. Use exclusively fictitious schemes and synthetic observations; no live feed, market-data ingestion or real customer records. Local prototype saves must be isolated from existing stock workspaces and explicitly distinguished from production tenant-safe persistence.

Evaluate internally against the documented Tickertape task coverage, clarity, navigation and reproducibility. Participant-based H2 experiments and statistical demand/price tests are not required for this internal evaluation; developer observations do not validate user usability, actual MF data parity, willingness to pay or conversion. ₹199 remains a hypothesis. Existing interview and matched-condition protocols are retained for a future separately authorized decision, not current prerequisites.

Desk-only review of public MF supplier descriptions, licensing terms and indicative economics may continue without contacting anyone, creating accounts or obtaining datasets. Record source/access date, published terms and costs separately from unknown permissions, minimum commitments and quotations; do not assume commercial rights. Full commercial data, regulatory, tenancy and launch gates remain in force before their corresponding exposure. A3, Stage B structure and all Momentum25/Wickstreet 3.0 capabilities remain protected. This decision authorizes the minimal protocol reconciliation and scope proposal; prototype implementation awaits scope approval. No purchase, deployment, commit or push is authorized.

## 2. Evidence streams and approval boundary

| Evidence stream | What it can establish | Conditions / approval status |
|---|---|---|
| **Public desk research** | Publicly stated features, access gates, pricing and terms; a draft list of comparable user tasks; provider documentation and data-rights questions. | May be completed without participant contact by reading public pages and documents. Record URL, access date and whether a claim was independently observed. No scraping, automated extraction, login, circumvention, copying, vendor contact, purchase or expenditure. |
| **Investor interviews** | Recent behavior, recurring problems, workarounds, terminology, discovery channels and task priority. | Requires separate approval for recruitment/outreach, participant consent, any personal-data collection, observation, recording or retention. No interviews have been conducted under this protocol. |
| **Hands-on competitor task benchmark** | Observed task coverage, usability, effort, access limits and comprehension on current alternatives such as Tickertape. | Requires separate approval before account access or other restricted activity. One six-task Tickertape session was completed on 2026-10-22 under separate explicit owner authorization; see §5.2. No further account testing, paid-feature use, credential sharing, screenshot collection or recording is authorized by this protocol. Respect current terms; no scraping, reverse engineering or copying. |
| **Synthetic Wickstreet prototype** | Workflow usability and the incremental value of integration when the same underlying information is available in both conditions. | Requires a separate Prototype Gate decision after Discovery. No live fund facts, NAV, customer records, production persistence, payment, publication or vendor integration. Human testing additionally requires approved recruitment and safeguards. |
| **Actual MF parity and quality benchmark** | Functional coverage, data completeness/freshness and correctness of the proposed live product. | Separate later activity. Requires appropriate data rights, a reference/validation method, and approvals for any account or dataset access. Synthetic data cannot substitute. |
| **Price and channel tests** | Price-visible intent or measured acquisition/conversion for a defined commercially feasible offer and channel. | Separate Commercial Gate design and owner approval. No charge, reservation, advertisement, public post, email campaign or paid acquisition is authorized here. |

Keep desk claims, participant reports, direct observations, synthetic-test results and validated live-data results in separate evidence columns. Do not present a desk claim as an observed result or a synthetic result as a live-product validation.

## 3. Investor segments and initial sample

Recruit only adults in India who make their own mutual-fund research choices. The segment definitions below are discovery hypotheses, not market-size claims. Include people who have not yet invested if they have independently compared schemes. Requests for Wickstreet to choose a suitable fund/allocation are not validation of the self-directed offer; record them as possible segment mismatch. Do not discard an otherwise eligible interview simply because it contains such a negative finding.

| Usage segment | Screening signal (sampling label only) | Recent task contexts to tag |
|---|---|---|
| **Occasional self-directed investors** | One to three substantive MF research episodes in the last 12 months, with a concrete decision in the last six months. | Shortlisted schemes, researched a self-defined SIP/goal, or revisited a choice after a change. Explore whether an occasional task is painful enough to justify a dedicated workspace. |
| **Active self-directed researchers** | At least four substantive MF research episodes in the last 12 months; ask for the actual count and behavior rather than relying on the label. | Repeated screening, same-period comparisons, managing a shortlist, following prior assumptions or investigating multiple schemes. Explore whether repeatability and continuity matter. |
| **Intermediate / unclear frequency** | Frequency is uncertain, recall is unclear, or behavior cannot be classified reliably. Do not use this as a numerical frequency band. | Keep as a separate note; do not force into occasional/active bins or use it to claim segment prevalence. |

The frequency cutoffs are interview-sampling heuristics, not standard investor categories. Occasional (one to three episodes) and active (four or more episodes) are mutually exclusive for classification; use the intermediate/unclear label only when frequency or recall cannot be established. Tag task context independently of frequency: shortlist builder, goal/SIP researcher and multi-scheme revisitor can each be occasional or active.

An initial qualitative cohort of **8–12 interviews total** is a planning range, aiming for roughly 4–6 occasional and 4–6 active participants where recruitment permits, with task contexts distributed across both. It is for discovery only, not statistical inference, market sizing or price conversion. Stop or request approval to extend if the evidence remains materially divergent; do not quietly enlarge recruitment. Record role/segment using minimal screening data, not detailed holdings.

Across those frequency segments, seek current paid-research users and investors relying entirely on free alternatives; record previous paid use separately. Include satisfied users with little unresolved friction and negative cases, rather than recruiting only people unhappy with current tools. Tag tool/payment history, satisfaction, workaround and discovery channel independently of research frequency. Seek useful variation within the existing cap, not a full factorial sample or another recruitment gate; report missing perspectives and recruitment bias. Free-tool satisfaction or advice-seeking may contradict the proposition and must remain in the evidence ledger.

## 4. Interview session plan

Target 30–40 minutes, subject to the approved consent and privacy plan. Ask participants to recall a concrete recent task before showing any Wickstreet idea. Prefer open prompts and follow the actual sequence they describe. Avoid pitching calculators, implying that a fund was good/bad, or asking the participant to reveal account credentials, CAS files, balances or personally identifying portfolio records.

Suggested prompts:

1. “Think about the last time you compared or researched mutual funds for yourself. When was it, and what prompted you to start?”
2. “What were you trying to decide or understand? What did you do first, next and after that?”
3. “Which schemes or criteria did you choose to examine, and how did you choose them?”
4. “Which sites, apps, people or documents did you use? What information did you look for in each?”
5. “How did you judge the information you found? What was clear or unclear?” If the participant identifies a comparison issue, then ask about periods, plan types, metrics or source differences without implying that inconsistencies occurred.
6. “Where did you spend the most time, get stuck, or remain unsure? What did you do when information was missing or conflicting, and what happened because it remained unresolved?”
7. “What did you decide to do next? What evidence or event would make you revisit that research?”
8. “Did you keep anything from that research? Why or why not?” If yes, ask what they kept, how and whether they later used it; do not assume a saved workspace was needed.
9. “How many times did a similar task come up in the last 12 months? What workaround do you use when you cannot complete it, and what is the consequence in time, confidence or a delayed/abandoned decision?”
10. “How did you first find the tools or sources you mentioned? Which discovery channels do you trust for financial research, and why?”
11. “Have you paid for any research or portfolio tool? What did you pay for and what made it worth—or not worth—the cost?” Ask only after reconstructing behavior; this is context, not a price-conversion measure.
12. “What worked well with your existing tools? Is there anything you would not want to change?”
13. “What have I missed about how you do this?”

Only after the behavior discussion, ask the participant to rank which unresolved task would be most valuable to solve and why. If a participant requests a feature, ask which recent task it would change, how often that task occurs, what the current workaround is and what consequence it avoids. Treat stated feature preferences as hypotheses; prioritize demonstrated behavior, recurrence or severity and a workaround rather than “would you use this?” answers or votes for Tickertape feature names.

## 5. Hands-on competitor task benchmark

The tasks below form a benchmark script, not permission to access competitor accounts. Run them only after owner approval and in accordance with current service terms. Use user-chosen criteria and schemes; never ask a platform to choose a “best” fund. Record when a task or feature is unavailable, hidden behind a plan, or unclear rather than treating it as a failure by Wickstreet.

| Task | Participant instruction | Evidence to capture if approved |
|---|---|---|
| **Find a candidate set** | “Using criteria you would choose yourself, find schemes in the category or categories you want to examine. Explain the criteria you applied.” | Supported filters, filter discoverability, results, steps, time, confusion and any prebuilt ranking or recommendation-like language encountered. |
| **Inspect a scheme** | “For a scheme you selected, find the facts and historical measures you would normally check before comparing it.” | Fields/metrics shown, period choices, source/date/method visibility, free/paid access and participant comprehension. |
| **Compare like with like** | “Compare two schemes you selected over the same periods and explain what you learned.” | Whether periods, plan/option and metric definitions align; navigation effort; missing caveats; ability to explain observed differences. |
| **Refine a screen** | “Change one criterion you chose and see how the result set changes.” | Customization steps, result changes, clarity of applied filters, and whether the participant mistakes a screen or ordering for a recommendation. |
| **Save and revisit** | “Save or otherwise preserve this screen/comparison, then return to it and explain what you would need to reproduce it later.” | Whether saving, notes and revisiting are supported in the accessed plan; retained assumptions, filters, periods, dates and method context. The reported screener-note option remains unverified until directly observed. |
| **Check provenance and access** | “Find how you would determine when the data was updated, what a measure means, or why a feature is unavailable.” | Ability to locate dates, definitions, limitations and access terms without coaching. |

### 5.1 Public desk review completed without account access

Read-only public-page review on **2026-10-22** found the following; it is not a hands-on usability or data-quality audit:

- Tickertape's current MF screener page advertises 60+ unique filters, custom-filter creation, popular/prebuilt screens, and marks some screens as Pro. Its public MF landing page also presents category entry points, curated collections, a popular-funds list and curated MF screens. These establish broad public claims about discovery and screening, not how well users complete tasks or what is available after login.
- Current public equity-category pages show category counts/AUM, 5-year CAGR listings and scheme snippets with AUM, base expense ratio, performance, a SEBI risk label/standard-deviation comparison and composition. Coverage and availability may differ by category, scheme, plan or access state; source freshness, corrections and calculation accuracy were not verified.
- Tickertape's published screener guide is dated 2022. It describes prebuilt/custom screens, saving a screen, CSV export, fund analysis and a watchlist. Treat these as leads for the hands-on benchmark, not verified present-day behavior. Its current public pages do not confirm the owner-observed screener-note option; note support remains unknown.
- The public annual Pro page lists ₹2,999/year and bundles MF research with stocks, ETFs, portfolio features and exports. This is not a like-for-like MF-only price. The approved hands-on session is recorded in §5.2; it showed an account-specific renewal promotion, while exact MF-specific Pro entitlements remain unverified.

The public evidence shows Tickertape already advertises substantial discovery, screening, scheme information, curated screens and some saved/export workflows. It does **not** establish a verified user problem or competitor gap. A candidate Wickstreet opportunity is an MF-first, method-consistent path from discovery through comparison and repeatable user-selected analysis at a lower price; whether users value that workflow or the price is untested. The separately recorded direct observations in §5.2 identify interface friction, but do not establish that investors experience or value those issues. Tickertape remains the principal MF benchmark; the saved-screen note claim is unverified.

### 5.2 Owner-authorized Tickertape hands-on benchmark — completed 2026-10-22

**Status:** Six scripted tasks completed in one existing signed-in account using normal UI interaction. The owner authorized the session separately from acceptance of this protocol. The benchmark is closed; no further Tickertape account activity is authorized here. Findings are direct observations by one researcher, not participant usability results or evidence of market demand.

| Evidence ID / task | Observed result | Interpretation and limits |
|---|---|---|
| **TT-01 — Find a candidate set** | The MF screener exposed category and plan selection and a filter panel grouped around scheme information, returns, risk, portfolio composition and ratios. After user-selected Equity/partial Hybrid category and Growth plan filters, the screen showed 907 results and a last-updated time. The results table exposed scheme name, sub-category, plan, AUM and a three-year CAGR column. | Broad, configurable discovery is established as observed functionality. This is not a complete filter-coverage count or data-quality check. The Add Filter panel said “over 50”; related pricing copy said “60+,” while an All Screens page referred to “200+ filters across 13 categories.” These counts have different scopes and do not establish MF-specific parity. A stock-oriented “screen stocks faster” tutorial tip appeared in the MF workflow. |
| **TT-02 — Inspect a scheme** | A quick preview exposed chart and summary metrics, with a route to a detailed page. The detail experience included period choices, metric definitions/help, scheme information, peer and portfolio sections, AMC and manager information, and other research sections. A scorecard surfaced performance, risk, cost, composition and red-flag concepts, with a Pro label and peer/rating-style presentation. | Tickertape connects factual scheme detail with analytical summaries. The scorecard and ranking language are recommendation-adjacent product patterns for Wickstreet and need feature-specific regulatory review before any analogous output. No particular scheme values are reproduced here. An account-specific holdings panel appeared on the page; it was excluded from the benchmark and not inspected or used. |
| **TT-03 — Compare like with like** | The peer view exposed multiple peer schemes and switchable metric groupings, including returns, scheme attributes and ratios. Changing the grouping changed the comparison fields. A separate price-comparison chart offered mutual funds and other asset types with a selectable date range. | Multi-metric comparison exists within the research journey. The task was not timed; consistency of every period, plan/option, formula or benchmark was not audited. No numerical outputs are transcribed. |
| **TT-04 — Refine a screen** | Category and plan selections could be changed, with the resulting set updating. The filter panel provided category groupings and searchable choices. | Filter refinement was operational in the observed session. The task was not tested with participants, and no completion-time, comprehension or error-rate claim is made. |
| **TT-05 — Save and revisit** | A new screen was saved with a temporary Wickstreet benchmark title and description, then its saved-list entry and saved-screen route/state were verified. The generated title/description needed correction. The save dialog initially showed visibility to fellow investors enabled; it was switched off before saving. | Save/reopen behavior is observed, so saving alone is not a Wickstreet differentiator. Wickstreet should use accurate summaries and private-by-default saved research. The test-only screen remains in the owner's account as a private artifact; this document records its existence but does not authorize further account changes or deletion. |
| **TT-06 — Check provenance and access** | The screener displayed an update time; the detail experience showed dated NAV context, metric help/definitions and methodology/help links. Pro labels appeared on some analytical features and filters. The pricing page listed a broader Pro feature set, including custom filters/universes, advanced screens, scorecard/red-flag and manager-analysis categories, Pro alerts and mutual-fund screener exports. | Some freshness cues, explanations and access markers are visible, but a data-provider/provenance trail, licence terms for Wickstreet's use, calculation correctness and freshness guarantees were not established. Exact MF-specific entitlements and paywall behavior remain **unverified** except for labels explicitly observed; no paid barrier was tested, no export was performed, and no subscription was purchased. |

#### Cross-cutting observations and evidence limits

- A saved-screen title/description was auto-generated and required correction. The initial public-visibility setting was on and was switched off before saving. These are interface observations, not evidence that users have encountered or are harmed by them.
- The signed-in renewal page showed an account-specific annual offer of ₹2,399.20 with a 20% promotion applied (about ₹200/month). This is not a verified universal or public list price, does not establish tax treatment, and is not a like-for-like comparison with Wickstreet's MF-only ₹199/year hypothesis. Tickertape's public annual pricing page separately advertised ₹2,999/year for a broader multi-asset membership.
- The six tasks were completed through one user's account and were not independently timed, repeated, or compared under balanced conditions. Transient screenshots were used only to inspect visible interface states; no screenshots were retained in the evidence record. No interviews, participant observation, alternative-provider test, paid-feature test, price experiment, live-data accuracy test or commercial data-rights review was performed. H1 (value at ₹199) and H2 (incremental workflow value) remain unvalidated.
- The site terms restrict copying, exploitation, reverse engineering and resale. The benchmark used ordinary UI observation and records only high-level functional and usability notes; it did not scrape, export, copy market data, reproduce proprietary screens or infer data rights.

**Evidence references (accessed 2026-10-22):** [Tickertape MF screener](https://www.tickertape.in/screener/mutual-fund), [Tickertape mutual-fund pages](https://www.tickertape.in/mutualfunds), [Tickertape pricing](https://www.tickertape.in/pricing), and [Tickertape terms](https://www.tickertape.in/meta/terms). The detailed scheme page was inspected through normal navigation from the screener; specific scheme values and its account-specific holdings content are intentionally not recorded.

Where practical, compare the same participant task across Tickertape and another accessible alternative, with order balanced. For eventual synthetic Wickstreet testing, use matched tasks but do **not** compare synthetic numerical outputs against live competitor values. The prototype comparison isolates usability; actual parity requires the separate rights-cleared coverage/quality benchmark in §7.

## 6. Measures and interpretation

Predefine task-level success criteria before observing participants. For each session or task, record only what is necessary:

- task completed, partially completed or not completed, with the reason;
- elapsed time, meaningful steps, errors, backtracking and help needed;
- whether the participant can explain the metric, period, assumptions and caveats in their own words;
- whether they can reproduce the chosen filters, schemes and periods later;
- uncertainty, trust and perceived effort, with the question wording kept consistent; and
- whether they interpret filtering/order as Wickstreet choosing or recommending an investment.

For synthetic H1/H2 work, give the basic and integrated conditions the same scheme set, fields, metrics, periods, assumptions, factual values and calculation results. The integrated condition may combine navigation, saved context and user-directed scenario steps, but must not gain additional facts or higher-quality data. Pre-register a primary outcome and a minimum meaningful difference based on the task before sessions; counterbalance condition/task order where practical. The basic condition provides preliminary evidence about whether the task is useful; the incremental change estimates H2's workflow effect. Neither establishes actual H1 parity, current data quality, or willingness to pay.

Use a credible, competently implemented conventional baseline informed by observed Tickertape tasks and accessible free alternatives. Do not manufacture an advantage through a deliberately fragmented, slow or weakened basic condition, and do not copy proprietary designs/content. H2 concerns clearer comprehension, less unnecessary effort or better reproducibility; connecting activities alone is not differentiation. Record familiarity, task order and negative/no-improvement results. Apply the same success criteria to satisfied users; do not reinterpret their lack of a problem as a failed interview.

### Actual parity benchmark, separately

When rights and a suitable validation source are later approved, assess a selected useful task set—not a matching filter count—across:

- functional coverage: whether users can complete each defined research task;
- universe/period/metric coverage and known missing cases;
- accuracy against an independent, appropriate reference for sampled scheme facts and calculations;
- freshness, correction handling, provenance and method consistency; and
- reproducibility of the same user-selected query and comparison.

Tickertape's observed outputs may inform a workflow benchmark only where access and terms permit. They are not automatically the ground-truth data source. Keep the benchmark scope and source rights documented. A full ₹199 proposition is tested later against the exact bundle Wickstreet can lawfully and economically deliver, not a hypothetical maximum feature set.

## 7. Preliminary data affordability and unit economics

**No-outreach desk check (2026-10-22):** [AMFI's published terms](https://www.amfiindia.com/terms-of-use) restrict ordinary use to personal/non-commercial purposes and do not establish Wickstreet's SaaS permission. [Accord](https://www.accordfintech.com/static/data-feed-solutions.aspx) publicly describes MF data feeds through FTP/API, but no applicable public tariff or Wickstreet-specific commercial-use grant was established. [CMOTS](https://www.cmots.com/services/market-data-provider)' indexed supplier description mentions 12-month subscriptions; its full page required JavaScript during this check. Current pricing, minimum commitments, coverage, derived-use rights, shared caching and free/paid user display terms remain unverified. Supplier availability is not permission. Use only labelled cost sensitivities until verifiable terms exist; no contact, account creation or dataset retrieval occurred, and these unknowns do not block the synthetic prototype.

Use the [B0 affordability assumption](15-stage-b0-product-and-value-specification.md#6-data-rights-and-199-cost-envelope) only as an initial screen. At ₹199/year including an illustrative 18% GST, the tax-exclusive amount is **₹168.64 per paying subscriber/year** before any operating cost. This rate/treatment is not confirmed for Wickstreet; professional tax classification is required.

For a sensitivity check, allocate 0%, 10%, 20% and 30% of ₹168.64 to data. These are arithmetic scenarios, not approved budget targets or supplier quotes:

| Illustrative data allocation | Annual data-cost screening amount per paid subscriber | Interpretation |
|---:|---:|---|
| 0% | ₹0.00 | No licensed-data allowance; only if the product's lawful data model actually has no incremental data cost. |
| 10% | ₹16.86 | Low allowance scenario, before all other costs. |
| 20% | ₹33.73 | Middle sensitivity scenario, before all other costs. |
| 30% | ₹50.59 | Upper sensitivity scenario, before all other costs; leaves ₹118.05 for every other cost and contribution. |

Actual data headroom is lower and can be zero or negative. Model a fixed licence allocation and variable data use separately:

```text
annual data cost per paid subscriber
  = fixed annual licence / retained annual paid subscribers
  + paid-user variable data cost
  + (active free users / paid subscribers × variable data cost per free user)
```

Show the fixed-fee dilution explicitly. For any quoted annual minimum `F`, display `F/100`, `F/500`, `F/1,000` and `F/5,000` per retained paid subscriber/year before variable usage charges; these are subscriber-count sensitivities, not forecasts. Separately show supplier charges triggered by API calls, displayed users, data volume, history depth or refresh frequency. Include free-active-users-per-payer ratios so free-tier traffic is not treated as costless.

Then calculate the remaining contribution from ₹168.64 after payment processing, customer support/service, acquisition and renewal effort, infrastructure, free-tier traffic/data allocation, business costs and a chosen operating reserve. Run low/base/high assumptions for active free users per payer, request volume, conversion, retention and supplier pricing. Count founder time in acquisition/support analysis even if it is not a cash salary. A supplier quote that exceeds a screening band is a prompt to revisit coverage, caching/usage permissions, price or the model—not automatic rejection or approval. No data request, licence commitment or spending follows from this calculation.

Separate first-year full acquisition from renewal servicing/renewal effort and mature replacement-CAC economics; retention remains an assumption until cohorts renew. Distinguish cash contribution from founder-sustainable economics and advance receipts from earned revenue. Keep fixed minimums and free-user load visible at small paying cohorts. After defining a feasible task/bundle, any separately approved alternative-price test must assess both conversion and net contribution for equivalent offers; a higher price is not assumed to improve the business. Conditional 24-month paths describe consequences of inputs, not the probability that those inputs will occur.

## 8. Distribution hypotheses

The ₹199 price makes repeatable low-cost discovery important. These are hypotheses to investigate, not approved channel experiments:

| Channel hypothesis | Why it may fit the product | Evidence to seek during discovery | Later test boundary |
|---|---|---|---|
| **Search-led original research pages** | Investors may search for specific MF comparison, metric and calculator tasks. | How participants find current tools; search terms and task wording they recall; whether a genuinely useful public guide could meet that need. | Content publication requires rights and regulatory review for any fund-specific facts; SEO results take time and are not guaranteed. |
| **Shareable, reproducible research outputs** | Users may share a comparison or explanation with a peer/adviser while keeping their own choices and assumptions visible. | Whether sharing/revisiting is part of a recurring task and what context must travel with it. | Requires privacy, data rights and suitable sharing controls; no shareable customer report is authorized. |
| **Permissioned investor education/community partnerships** | Trusted educators or communities may reach self-directed investors at lower cost than broad paid media. | Which communities participants already use and what makes financial content credible. | Contact, posting, partnership or endorsement requires separate approval and careful regulatory/brand review. |
| **Referral and word of mouth** | A focused research workflow may be useful when one investor helps another understand a comparison. | Whether participants already share tools/research and what makes them comfortable doing so. | No referral campaign or incentive is approved; test after product and disclosure review. |
| **Paid acquisition** | Could quantify channel economics at scale, but may be hard to support at ₹199/year. | No paid test during discovery; later compare fully loaded CAC with retained contribution. | Requires a separate spending cap and campaign approval. |

Do not assign zero CAC to organic channels: include founder time and content production. A channel's eventual CAC is attributable cash spending plus measured channel labor divided by new paying subscribers attributable to it. Interviews and no-charge intent actions are not CAC or conversion evidence. Avoid publishing, contacting groups or recruiting through a channel until separately authorized.

## 9. Sequence and outputs

1. **Desk-only preparation:** read public claims, terms and provider documentation without participant contact; prepare the public-claims/task matrix, interview script, competitor task sheet, affordability worksheet and channel hypotheses. Separate published claims from what is unverified. No contact, accounts, scraping, purchase or data acquisition.
2. **Discovery execution request:** present the protocol, participant privacy/consent plan, recruitment source, interview cap, benchmark-account scope and no-spend boundary for separate owner approval. Do not contact participants or create/access competitor accounts before that approval.
3. **Discovery output:** summarize observed recent tasks, recurring friction, paid/free-tool and frequency differences, satisfied users, negative cases, alternatives and channel discovery; rank task opportunities; revise the capability-to-task matrix; fill the preliminary affordability model with explicit assumptions/unknowns; recommend prototype, revise or stop. Preserve evidence against the workspace and ₹199 hypotheses. Do not make statistical conversion or actual data-parity claims.
4. **Later separate Prototype Gate:** if approved, run the matched synthetic conditions specified in §§6–7. Prototype findings are usability evidence only.
5. **Later parity and Commercial Readiness:** after rights-cleared data and appropriate approvals, complete the functional coverage/quality benchmark and price test for the exact feasible bundle. Do not treat these as prerequisites for planning or fixture-only B1 consideration; do require them before live/paid exposure as defined by the B0 baseline.

The Discovery Gate packet must state one prioritized investor task in the form “segment + recent trigger + job to complete + current workaround + unresolved outcome.” It must summarize evidence of recurrence **or** severity: either a repeated pattern across independent interviews, or a well-described high-consequence unresolved task. This is qualitative evidence, not an estimate of prevalence.

It must also show either (a) a competitor task gap/friction supported by authorized task observation, or (b) a viable parity opportunity: a useful task already served by Tickertape that Wickstreet could plausibly deliver in a cohesive MF-first workflow and test at the lower target price. Public desk claims alone can identify the task and hypothesis, but cannot establish a usability gap. Include a narrow synthetic brief that names one primary task, the same underlying information in both conditions, the workflow difference to test, the primary outcome, and the meaningful-improvement criterion. Do not require commercial proof, live-data rights or a finalized Pro bundle to justify this small prototype request.

A positive discovery result may support a request for Prototype Gate approval. It does not authorize interviews, competitor account activity, prototype construction, B1, vendor contact, data procurement, spending or launch.

## 10. Owner decisions

| Decision | Status |
|---|---|
| Accept this protocol as the planning method | Accepted (2026-10-22); no execution authority |
| Authorize 8–12 qualitative interviews and recruitment | Prohibited under current no-outreach scope; not a prototype prerequisite |
| Authorize hands-on Tickertape/alternative account tasks | Six-task Tickertape session completed 2026-10-22 under separate explicit owner authorization; benchmark closed. No alternative-provider or further account testing authorized. |
| Authorize a synthetic prototype | Scope/criteria proposal is the next approval gate under §1.1; implementation awaits separate approval; interviews, surveys and vendor contact are not prerequisites |
| Authorize fixture-only B1 engineering | Not authorized; separate decision after prototype evidence |
| Approve data acquisition, channel experiments, spending or price testing | Not authorized; separate approvals |

## 11. Sources and limits

Public pages accessed on 2026-10-22 support the desk notes in §5.1: [Tickertape MF screener](https://tickertape.in/screener/mutual-fund), [MF landing page](https://tickertape.in/mutualfunds), [equity-category page](https://tickertape.in/mutualfunds/equity), and [pricing](https://tickertape.in/pricing). Tickertape advertises 60+ screening filters and public category/scheme research content; its annual Pro page lists ₹2,999 and broader multi-asset functionality. The [screener guide](https://tickertape.in/blog/how-to-use-tickertape-mutual-fund-screener/) was last updated in 2022 and describes saving custom screens, exporting and watchlists; it is historical evidence only until current access is verified. Public pages and the one hands-on session do not establish all account entitlements, data accuracy/freshness, or Wickstreet's rights to use data. See §5.2 for direct observations and the [terms](https://tickertape.in/meta/terms); do not infer a licence or data right from public availability.

The illustrative GST sensitivity is not a determination of Wickstreet's tax treatment. CBIC's [sectoral FAQ](https://cbic-gst.gov.in/hindi/sectoral-faq.html) lists an 18% rate for IT services, but product classification and input tax treatment require qualified review.
