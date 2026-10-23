# Wickstreet 2.0 — Multilingual Research Agent (Core Product)

> **Owner decisions, 2026-10-23:** (1) **the AI agent is part of the core product** (AG-1, §8). (2) **Build something truly meaningful and differentiated first; address cost later** (AG-4). Cost does not gate design choices in Discovery or prototyping. It is no longer an optional hypothesis. This amends the B0 product proposition in [15 §2–§4](15-stage-b0-product-and-value-specification.md). It does not change the data-rights verdict in [17](17-mf-free-data-feasibility.md): **CONDITIONAL GO stays.** It authorises no implementation, model-provider account, data ingestion, outreach or expenditure.
> **Superseded for Wickstreet 2.0 by this decision:** the "AI agents" out-of-scope entries in proposed ADD amendments [A1](../../architecture/ADD-amendment-A1.md) and [A2](../../architecture/ADD-amendment-A2.md), and the owner's 2026-10-18 direction to avoid AI agents.
> **Architecture accepted 2026-10-23 (AG-2):** [ADR-022](../../architecture/adr/ADR-022-multilingual-research-agent.md) (agent) and [ADR-023](../../architecture/adr/ADR-023-operating-modes.md) (operating modes) cover model egress and non-deterministic output. Where this document and those ADRs differ, the ADRs govern.

## 1. Positioning and what remains to test

**From:** "A cheaper Tickertape for mutual funds."
**To:** "Understand and research mutual funds in your own language." The agent performs research tasks; it is not a chatbot that answers finance questions. It is the primary research interaction, and the conventional workstation stays.

**Decided:** the agent is core. **Still to test in B0 Discovery ([16](16-b0-discovery-protocol.md)), as hypotheses H-AG1 to H-AG3:**
- **H-AG1 (value):** users complete MF research tasks better with the agent operating Wickstreet's deterministic tools than with the workstation alone.
- **H-AG2 (language):** English, Hindi and Hinglish quality is good enough for release; each regional language passes the same bar before it ships.
- **H-AG3 (cost): deferred by the owner.** Record cost per task during prototyping so the later decision has data. It is not a gate now.

These test **how** the agent ships, not **whether**. The main test is H-AG1 against the signature capabilities in §2.1. AI alone is not the differentiator: competitors already ship AI features (§2). The value must come from **completed research tasks**, not from speaking Hindi.

## 2. Competitive check (2026-10-23)

| Competitor | AI capability | Evidence | Conf. |
|---|---|---|---|
| Tickertape | An "AI Assistant" that "may access your personal and financial data on the Platform, including your holdings"; "the underlying AI model is licensed from a third-party provider and may train its model on your data or queries"; it "may use web search". Users can also connect third-party AI applications (§6.1) | [Terms §6.1–6.2](https://www.tickertape.in/meta/terms) | V |
| Groww | Official MCP connector for AI assistants; "The current version supports stocks and F&O"; "Mutual funds … will be added" (article dated 2025-08-04) | [Groww MCP](https://groww.in/updates/groww-mcp) | V (as of that date) |
| Groww "MF Prime" AI guidance | Not found | — | U |

**Where Wickstreet could differ:**

| Dimension | Wickstreet aim | Status |
|---|---|---|
| Language | English, Hindi and Hinglish first, measured before adding regional languages | Hypothesis |
| Agentic operation | The agent sets filters, sorts, opens charts and comparisons, and saves research in the workstation | Hypothesis |
| Provenance | Every number traces to a dataset, date, revision and calculation | Design rule (§4) |
| Price | Useful agent help inside ₹199/yr | Deferred (§6) |

### 2.1 Signature capabilities: what "meaningful and differentiated" must mean

Speaking Hindi and calling tools are table stakes once competitors add them. A Wickstreet capability counts as differentiated only if it passes all three tests:
1. It completes a task that matters to an ordinary investor.
2. It rests on data or rules that Wickstreet can show and cite.
3. A desk check finds no competitor doing it well.

The candidates below are **hypotheses**. Each needs the competitor check in [01](01-competitive-parity.md) refreshed hands-on and B0 interview evidence ([16](16-b0-discovery-protocol.md)).

| # | Signature capability | Example | Why it matters | Why it may be different | Data |
|---|---|---|---|---|---|
| SC-1 | **"What changed in my fund?"** A monthly change brief in the user's language: portfolio moves, riskometer change, TER change, manager change, benchmark change, merger notices | "इस महीने मेरे fund में क्या बदला?" | SEBI forces this disclosure every month (17 §3), but few investors read spreadsheets and Scheme Summary Documents. The facts exist; understanding does not | Competitors show current values. A dated, cited change explanation across disclosures is not a feature found in the desk review (U) | P1 (+ stored history) |
| SC-2 | **Disclosure explained in rupees** | "Expense ratio 1.2% का मेरे ₹5,000 SIP पर 10 साल में कितना खर्च?" | Turns percentages into the user's own money; a deterministic calculation | Personal rupee framing in Hindi/Hinglish, with every input shown (U) | P1 for real TER; user's amounts otherwise |
| SC-3 | **Show, don't tell:** the agent builds the screen | "Compare these three over 5 years" opens a comparison the user can edit | The user sees and controls the research, not just a chat answer | Tickertape's assistant answers in chat (terms §6.2); operating the workstation is the gap (C) | Screen data |
| SC-4 | **Every number cited** | Tap any figure to see source, as-of date, revision and method | Trust; corrections are visible | Most AI assistants do not cite at the figure level (U) | Provenance (§4) |
| SC-5 | **Research memory** | "Save this; what changed since my last review?" | Research becomes a continuing record, not a one-off answer | Saved, replayable research with change diffs (U; Tickertape saved screens need checking per 15 §4) | Workspace + P1 |
| SC-6 | **A factual decision frame instead of a pick** | "कौन सा fund अच्छा है?" gets the user's own criteria laid side by side, with no winner | Keeps users inside the advice boundary while still helping them decide | Competitors either avoid the question or edge toward ranking (U) | P1 |

**Recommended lead:** SC-1 with SC-3 and SC-4. Together they turn mandated but unread disclosures into understanding, in the user's language, with proof. That is meaningful even to a first-time investor, and it makes Wickstreet more than "AI plus Hindi". SC-1 needs P1 plus the right to keep monthly history.

## 3. Capability scope

| Request type | Example | Tool used | Data needed | Regulatory class |
|---|---|---|---|---|
| Discover | "Large-cap direct growth funds with low expense ratios" | Screener | P1 | Factual filter (user's criteria) |
| Compare | "इन दोनों म्यूचुअल फंड्स में क्या अंतर है?" | Comparison | P1 | Factual comparison; **no winner** |
| Explain a concept | "What is rolling return?" | Glossary (versioned, pre-translated) | None | Education |
| Analyse history | "Compare their 5-year drawdowns and volatility" | Metrics engine | P1 | Factual, dated, method shown |
| Operate the workstation | "Filter by AUM and sort by expense ratio" | UI action API | None beyond the screen's data | — |
| Preserve research | "Save this and tell me what changed since my last review" | Workspace + diff | P1 + storage | Factual diff |
| Hinglish | "इन funds का 5-year return compare करो" | As above | As above | As above |

**Out of scope (unchanged from [13 A1](13-wickstreet-2.0-mf-first-release-plan.md)):** "which fund should I buy", rankings presented as advice, allocation instructions, suitability, and any personalised scheme selection. The agent answers these with the factual comparison and a plain statement that it does not recommend. A multilingual interface does not change IA/RA obligations ([13 A2](13-wickstreet-2.0-mf-first-release-plan.md), [SEBI RA FAQ, July 2025](https://www.sebi.gov.in/sebi_data/attachdocs/jul-2025/1753268710217.pdf)). Conversational comparison is harder to keep factual than a table. It needs its own feature-level IA/RA review before launch.

**Free hypothesis that does not depend on P1:** the concept glossary, workstation operation, and SIP/lumpsum/goal calculators on user-entered assumptions. These can be prototyped and tested on synthetic fixtures today ([14 §5](14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate)). That tests language and tool-use quality without real fund data.

## 4. Design rules (principles only; the ADR decides the design)

1. **The model interprets; Wickstreet computes.** The language model chooses tools and parameters and asks clarifying questions. Every number, fact and ranking-by-user-criterion comes from a deterministic Wickstreet tool. The model never computes or recalls a financial figure.
2. **Hybrid explanations (owner decision, 2026-10-23).** Deterministic tools produce calculations, facts and structured conclusions. Reviewed, pre-translated templates hold the authoritative interpretation of sensitive results. The model may explain those results naturally in the user's language. A validator blocks unsupported numbers, claims and advice; on failure, the verified template answer is shown. Structured results are deterministic; conversational wording may vary. Saved research stores tool calls, results and the exact text shown. Details: [ADR-022 §2.7–§2.8](../../architecture/adr/ADR-022-multilingual-research-agent.md).
3. **Provenance on every claim.** Each figure shows source, as-of date, data revision and method version. An output validator blocks any number that did not come from a tool result.
4. **Tool allowlist.** The agent can only call read-only research tools and UI actions. No order, payment, account or admin tools. No web search.
5. **Provider independence.** Pydantic AI's model layer plus a versioned routing table, with no Wickstreet model-provider port ([ADR-022 §2.2, C4](../../architecture/adr/ADR-022-multilingual-research-agent.md)). Language detection becomes a port only when a second implementation is adopted (ADR-022 V1).
6. **Advice boundary in code.** A classifier and response policy handle recommendation-seeking requests in every supported language. The policy is tested with adversarial Hindi and Hinglish prompts.

## 5. Constraints

| Constraint | Effect | Evidence |
|---|---|---|
| **Data rights (extends P1)** | The P1 permission request must also cover AI processing, and transmitting licensed data to an external model provider. Without that, licensed fields must not enter prompts. Suppliers treat AI use as a separate right: Tickertape's terms bar using S&P data "for the purpose of training, developing, or implementing any artificial intelligence" (§7.3) | [17 §10](17-mf-free-data-feasibility.md); Tickertape terms (V) |
| **Privacy** | User queries and saved research are personal data and may reveal holdings. The provider contract must bar training on Wickstreet data and set retention limits. DPDP Act obligations need review before launch | Tickertape's own disclosures show the risk (V); legal review (U) |
| **Regulation** | §3 boundary; feature-level IA/RA review of conversational comparison | 13 A2 |
| **Determinism** | §4 rule 2 | Repo CLAUDE.md |
| **Language quality** | Hindi financial terms and Hinglish must be evaluated on a fixed test set before release; regional languages only after measured quality | — |
| **Language infrastructure** | BHASHINI is worth evaluating. Its production-use terms and pricing are unverified; a secondary source says its APIs are for proof of concept and production needs a paid plan | [secondary](https://ecorpit.com/ecorpit-indic-language-app-localization-service-india-2026/) (U) |
| **Architecture** | New external egress to a model provider; new non-deterministic component. Needs an A3 amendment or ADR | A3 (silent), A1/A2 (out of scope) |

## 6. Economics (deferred by the owner, 2026-10-23)

This section does not gate Discovery or prototyping. It is kept so that the later cost decision starts from the right frame. One thing continues now: log model calls and tokens per task in prototypes.

[13 A3a](13-wickstreet-2.0-mf-first-release-plan.md) assumes ₹2/yr per free account and contains **no inference cost**. Net receipts are ₹168.64 per payer-year, and steady-state contribution is ₹132.57 (lean) before data licences and fixed costs. Free users are modelled at 10 per payer.

Let `s` = the share of net receipts allotted to all AI usage, `A = s × 168.64` per payer-year, and `f` = free users per payer. Then `A = paid_budget + f × free_budget`.

Illustration only, not a forecast or a model-price claim: at `s` = 25% and `f` = 10, A ≈ ₹42. If a payer gets ₹32 of agent use per year, each free user gets ₹1 per year.

**Consequences:**
- The free-tier agent must be almost free to run: the cached glossary, templated answers, and deterministic UI actions. Model calls need strict quotas.
- Pro needs per-user usage limits, response caching and routing to a small model by default.
- Per-active-user inference cost is a B0 measurement, priced against real provider quotes. It is not an assumption to adopt.
- The agent is core, so a cost misfit does not remove it. If measured cost does not fit, change the quotas, the model routing, the free/Pro split or the price. The ₹199 price is itself unvalidated ([15 §4](15-stage-b0-product-and-value-specification.md)).

## 7. Sequence

1. **Data foundation:** resolve P1, or choose another lawful route ([17](17-mf-free-data-feasibility.md)). Live-data agent features wait for this.
2. **Deterministic tools and APIs** (Stage B): screener, comparison, metrics, glossary, workspace. The agent depends on these; it does not replace them.
3. **Agent as the primary research interaction**, keeping the conventional workstation.
4. **Evaluate** on fixtures first, then on licensed data. Measures:
   - task completion in English, Hindi and Hinglish vs the workstation alone;
   - tool-call accuracy;
   - **0 numbers without provenance**;
   - correct handling of advice-seeking requests;
   - for each signature capability (§2.1): would users miss it, and do they understand their fund better afterwards;
   - per-task inference cost, recorded only (not a gate; §6).
5. **Expand** to Marathi, Bengali, Tamil, Telugu, Kannada, Gujarati, Malayalam and Punjabi, then voice, one at a time, each gated on measured quality and cost.

Steps 2 and 4 on synthetic fixtures do not depend on P1. ADR-022 now authorises them in Phase 1 personal mode.

**Consequence of "core" plus CONDITIONAL GO.** Until P1 is resolved, the agent can only explain concepts, operate the workstation and run calculators on user-entered assumptions. Discovery, comparison, history and saved fund research all need licensed data. A core agent does not reduce the P1 dependency; it widens it, because the request must also cover AI processing (§5).

## 8. Owner decisions

| # | Decision | Default I would take |
|---|---|---|
| AG-1 | Is the agent core or a hypothesis? | **Decided 2026-10-23: core product.** Supersedes the 2026-10-18 "avoid AI agents" direction and the A1/A2 out-of-scope entries for 2.0 |
| AG-2 | Architecture for the agent | **Accepted 2026-10-23:** [ADR-022](../../architecture/adr/ADR-022-multilingual-research-agent.md) with corrections C1–C6. Pydantic AI; local Ollama for development; production model deferred. Phase 1 personal mode ([ADR-023](../../architecture/adr/ADR-023-operating-modes.md)): local Ollama, rights-clean real data, AMFI only within an owner-set personal scope; bulk AMFI acquisition gated. Tests use synthetic fixtures (owner direction 2026-10-23) |
| AG-3 | Explanation policy | **Decided 2026-10-23: hybrid.** Templates are authoritative; the model explains; the validator falls back to templates |
| AG-4 | AI budget share `s` and free-tier quota | **Deferred by the owner, 2026-10-23:** differentiation first, cost later |
| AG-8 | Lead signature capability (§2.1) | SC-1 "What changed in my fund?" with SC-3 and SC-4 |
| AG-5 | Add AI processing and model-provider transmission to the P1 permission scope | Yes; the owner sends any request |
| AG-6 | Language providers to evaluate (BHASHINI, commercial LLMs, open models) | Desk evaluation of terms first; no accounts without approval |
| AG-7 | IA/RA review of conversational comparison and the advice-refusal policy | Required before any public agent |

## Sources (accessed 2026-10-23)

- Tickertape terms of use, §1.2, §2.9, §6.1, §6.2, §7.3: <https://www.tickertape.in/meta/terms>
- Groww MCP product update, 2025-08-04: <https://groww.in/updates/groww-mcp>
- BHASHINI production terms (secondary, U): <https://ecorpit.com/ecorpit-indic-language-app-localization-service-india-2026/>; monetisation report (2024): <https://www.cdomagazine.tech/aiml/indian-govt-ai-translation-platform-bhashini-gears-up-for-monetization>
- SEBI RA FAQ, July 2025: <https://www.sebi.gov.in/sebi_data/attachdocs/jul-2025/1753268710217.pdf>
- Internal: [13](13-wickstreet-2.0-mf-first-release-plan.md), [14](14-stage-b-implementation-plan.md), [15](15-stage-b0-product-and-value-specification.md), [16](16-b0-discovery-protocol.md), [17](17-mf-free-data-feasibility.md), [ADD A1](../../architecture/ADD-amendment-A1.md), [A2](../../architecture/ADD-amendment-A2.md), [A3](../../architecture/ADD-amendment-A3.md)
