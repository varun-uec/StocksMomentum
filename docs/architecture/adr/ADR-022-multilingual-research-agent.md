# ADR-022: Multilingual Research Agent

**Status:** Accepted 2026-10-23, with corrections C1–C6 (§7) applied. Extends [ADD Amendment A3](../ADD-amendment-A3.md) (Accepted) without changing it. Product basis: [doc 18](../../plans/wickstreet-2/18-multilingual-research-agent.md). Data-rights basis: [doc 17](../../plans/wickstreet-2/17-mf-free-data-feasibility.md) (CONDITIONAL GO).
**Authorises:** implementation of the agent in the Phase 1 **personal mode** ([ADR-023](ADR-023-operating-modes.md)): one local user, local Ollama, rights-clean real data, user-entered calculations, and AMFI records only within the permitted personal scope (§2.11). Tests and CI use synthetic fixtures.
**Does not authorise:** bulk AMFI acquisition; external AI processing of licensed data; a production model choice; hosted AI infrastructure; SaaS deployment; commits or pushes without separate instruction.

## 1. Context

The owner made a multilingual research agent part of the core Wickstreet 2.0 product (doc 18, AG-1). A3 does not cover an agent. An agent adds two things A3 has no rules for:
1. **outbound calls to a model provider**, which carry user text and possibly licensed data;
2. **non-deterministic output**.

The repo requires deterministic, explainable results. Doc 17 requires every data use to pass a fail-closed rights gate. The agent is a **restricted financial research agent**, not a general-purpose autonomous agent.

## 2. Decision

### 2.1 Role and placement
- The agent is the primary research interface for Wickstreet 2.0. The conventional workstation stays and is fully usable without the agent.
- The agent is a new bounded context, **Research Agent**, inside the modular monolith (A3 §1, §5). No new service, queue or broker.
- It calls other modules **only through their public application interfaces** (A3 §5.1): Fund Analytics, Simulation and scenarios, MF reference data (read), User research and workspaces, Data rights and provenance, Subscription and entitlements. It never imports another module's persistence.
- It has no access to Portfolio/CAS in Stage B. Portfolio tools need a separate decision in Stage C.
- Dependency rule addition (A3 §6.4): `Research Agent → {Analytics, Scenarios, MF data (read), Workspaces, Rights, Entitlements}`. Nothing depends on Research Agent.

### 2.2 Framework and models
- **Agent framework: Pydantic AI** (MIT). It has built-in Ollama, vLLM and LiteLLM providers, any OpenAI-compatible endpoint, `FallbackModel`, Pydantic-typed tools, and deferred tools for approval.
- **Fallback framework: OpenAI Agents SDK** (MIT). It supports non-OpenAI Chat Completions endpoints. If adopted, disable its default trace upload to OpenAI.
- The framework sits behind one thin `AgentRuntime` port, so a fallback costs one adapter.
- **No second model abstraction (C4).** Pydantic AI's model classes are the provider layer. Wickstreet adds only:
  - a versioned **routing table**;
  - the **outbound policy** (§2.8);
  - **configuration**;
  - **usage normalisation** (§2.10).
- **Development inference:** a local open-weight model through **Ollama**.
- **Production model:** deferred until quality, cost and licence evaluation. Each candidate model's licence must permit commercial SaaS use before it enters routing.
- **Not now:** multi-agent orchestration, external MCP tools, code execution, web browsing, hosted AI infrastructure.

### 2.3 Interfaces

```python
class AgentRuntime(Protocol):            # wraps a Pydantic AI Agent; one adapter
    def run_turn(self, ctx: TurnContext, history: Sequence[Turn], user_text: str) -> AgentTurnResult: ...

@dataclass(frozen=True)
class ModelRoute:                        # configuration, not an abstraction over providers
    task: Literal["intent", "tool_selection", "explanation"]
    lang: LanguageTag
    model: str                           # Pydantic AI model string, e.g. "ollama:<name>"
    location: Literal["internal", "external"]   # internal = runs on Wickstreet infrastructure
    fallbacks: tuple[str, ...]
    licence_ref: str                     # recorded commercial-use licence check

class LanguageService(Protocol):         # detection/transliteration/templates; replaceable
    def detect(self, text: str) -> LanguageTag: ...           # en, hi, hi-Latn (Hinglish), ...
    def render_template(self, template_id: str, version: int, lang: LanguageTag, values: Mapping[str, Value]) -> str: ...

class ToolRegistry(Protocol):            # the only way the model reaches Wickstreet
    def specs_for(self, ctx: TurnContext) -> Sequence[ToolSpec]: ...    # filtered by entitlement + rights
    def invoke(self, ctx: TurnContext, name: str, raw_args: JsonValue) -> ToolResult: ...

class OutboundPolicy(Protocol):          # §2.8; fails closed
    def check(self, ctx: TurnContext, route: ModelRoute, payload: OutboundPayload) -> PolicyDecision: ...

class ResponseValidator(Protocol):       # §2.6; a safety boundary, not a correctness proof
    def validate(self, draft: str, results: Sequence[ToolResult], lang: LanguageTag) -> ValidationOutcome: ...
```

- `TurnContext` carries tenant, user, entitlements, language and data revision. The server derives tenant from the session (A3 §9).
- `ToolResult` carries structured values plus provenance (`source`, `as_of`, `data_revision`, `method_version`) and the authoritative `template_id`/`version` for its interpretation.
- `OutboundPayload` is the **complete** request: system prompt, history, tool definitions, tool results and user text (§2.8).

### 2.4 Languages
- **Initial:** English (`en`), Hindi (`hi`) and Hinglish (`hi-Latn`, code-mixed). The agent replies in the user's language unless the user asks otherwise.
- **Templates:** every authoritative template exists in all supported languages, reviewed by a fluent reviewer for financial terms.
- **Adding a language** (Marathi, Bengali, Tamil, Telugu, Kannada, Gujarati, Malayalam, Punjabi): add templates and evaluation sets, then pass AC-4 and AC-7 for that language. Configuration only.
- **BHASHINI or other Indic services** plug in behind `LanguageService` only after their terms are read (doc 18 §5).

### 2.5 Tool boundary

Only registered tools exist. Each has a strict schema (`additionalProperties: false`), an owning module, an entitlement check and a rights check. Arguments are validated before invocation; invalid input returns a structured error to the model.

| Tool | Owner | Effect | Data rights needed | Stage |
|---|---|---|---|---|
| `glossary.explain(term, lang)` | Research Agent (template store) | Read | None | Now |
| `calc.sip / calc.lumpsum / calc.goal(inputs)` | Simulation | Read (pure) | None (user inputs) | Now |
| `calc.cost_in_rupees(ter, amount, years)` | Simulation | Read (pure) | None with user TER; P1 for real TER | Now (user inputs) |
| `funds.search(filters)` | Analytics | Read | P1 (`display`) | After P1; fixtures now |
| `funds.compare(ids, metrics, period)` | Analytics | Read | P1 | After P1; fixtures now |
| `funds.metrics(id, metrics, period)` | Analytics | Read | P1 | After P1; fixtures now |
| `funds.changes(id, from, to)` (SC-1) | Analytics | Read | P1 + history retention | After P1; fixtures now |
| `ui.apply(command)` | Research Agent | Returns a UI command (filter, sort, open chart/compare) that the client executes in view of the user | Inherits the screen's data | Now |
| `research.save(snapshot)` | Workspaces | **Write; server-verified confirmation (below)** | Storage right for included data | Now (fixtures) |
| `research.diff(saved_id)` (SC-5) | Workspaces + Analytics | Read | P1 for live data | After P1; fixtures now |

**Server-verified confirmation (C3).** `research.save` is a Pydantic AI deferred tool (`requires_approval=True`). Client approval alone is not authorisation:
1. When the model calls the tool, the server stores a **proposed action**: id, tenant, user, the canonical action payload with its SHA-256 hash, and an expiry. The client shows the user exactly that payload.
2. The confirmation request carries the action id. The server checks that tenant and user match the session, the hash matches the stored payload, the action has not expired and has not been used, and the user is entitled.
3. Only then does the server execute **the stored payload**, never one resubmitted by the client or regenerated by the model. Each action id works once.

**Forbidden:**
- tools that place orders, move money, change accounts, read other tenants, browse the web, run code or reach Portfolio/CAS;
- any tool that returns a recommendation, ranking-as-advice or allocation.

### 2.6 Financial calculations and explanations

**Calculations.**
- Every number, date, fact and user-criterion sort shown to a user comes from a deterministic Wickstreet tool.
- The model never computes, estimates, rounds or recalls a financial figure.
- Methods are owner-approved methodology and carry `method_version`.

**Explanations (hybrid).**
1. Tools return structured results **and** the id/version of the reviewed template that holds the authoritative interpretation of sensitive results: returns, risk, costs, riskometer, changes, and anything that could read as advice.
2. The model may explain those results conversationally in the user's language, grounded only in this turn's tool results and templates.
3. `ResponseValidator` checks the draft before display:
   - every numeric token (any script, including Devanagari numerals and lakh/crore forms) matches a tool value after unit normalisation;
   - every named scheme, date and metric appears in a tool result;
   - no recommendation, suitability, allocation or future-return language (classifier + lexicon, per language);
   - it does not contradict the template's interpretation;
   - provenance is attached for every figure.
4. **On any failure:** discard the draft and show the verified template rendering in the user's language. Log the failure class without user text.

**The validator is a safety boundary, not a correctness guarantee (C1).** Token matching and classifiers cannot detect every misleading inference: a correct number with a wrong implication, a selective emphasis, or an implied comparison. Correctness rests on:
- deterministic tools;
- reviewed templates as the authoritative interpretation;
- evaluation suites (§4);
- production monitoring of validator outcomes and user reports, with an incident path that can switch any route to template-only answers by configuration.

Templates alone are always a complete, correct answer.

### 2.7 Determinism
- **Guaranteed:** identical tool inputs, data revision and method version produce byte-identical structured results and identical template renderings.
- **Not guaranteed:** conversational wording. The owner accepted this exception to the repo determinism rule for the agent's prose only.
- **Reproducibility:** a saved turn stores tool calls, arguments, results, provenance, template ids/versions, model string, routing-table version and the exact text shown. Replay shows what the user saw. It never re-generates prose.

### 2.8 Privacy and outbound data (C2)
- **Scope.** `OutboundPolicy` checks the **complete outbound payload** before every model call:
  - system prompt and tool definitions;
  - the full conversation history;
  - every tool result;
  - the current user text.
  
  The same rules apply to **telemetry**: traces, spans, logs and metrics exports. Pydantic AI instrumentation is off by default. Any exporter sends only to Wickstreet-controlled infrastructure. Logfire or another SaaS backend needs a separate privacy review.
- **Redaction** runs over the whole payload, not only the latest message: PAN, phone, email, folio, account and similar identifiers, in every language and script.
- **Payload classes:**
  - user text and history: allowed after redaction;
  - public glossary and templates: allowed;
  - tool results built on licensed data: **only if the rights gate grants `ai_processing_external` (or `ai_processing_internal` for `internal` routes) for every source present anywhere in the payload, including history**;
  - other tenants' data: never.
- **Fail closed:** if a check cannot classify content, the call does not go out.
- **External provider terms** must (a) bar training on Wickstreet data, (b) state the retention period and support deletion, and (c) name the processing location. Without these, a provider cannot enter routing.
- **Conversation storage** is tenant-scoped, with user deletion and export, under A3 §9 backup and encryption rules. No conversation content in application logs. DPDP obligations need review before any real user data.
- **Prompt injection:** scheme documents and AMC-filed text are untrusted data. Tool results are passed as data, never as instructions. The only write tool needs server-verified confirmation (§2.5).

### 2.9 Compliance boundary
- No investment recommendations, scheme selection, allocations, suitability judgments or rebalancing instructions. These need separate approval (A3 §3.3).
- Recommendation-seeking requests in any language get a template-backed factual decision frame: the user's own criteria side by side (doc 18 SC-6), plus a plain statement that Wickstreet does not recommend.
- The agent never presents historical returns as expected returns.
- A versioned audit record keeps each turn's tool calls and validator outcomes, without user text.

### 2.10 Cost controls (mechanisms now; thresholds deferred per AG-4)
- Every model call records model string, route, tokens in/out (normalised across providers), latency, tenant, feature and outcome.
- **Quotas** per plan and per tenant, as configuration. Unlimited in development; the owner sets them before launch.
- **Caching:** deterministic tool results by `(args, data_revision, method_version)`; glossary and template renderings by `(id, version, lang)`. No cross-tenant caching of model output.
- **Routing:** cheapest adequate model per task type and language (§2.2).

### 2.11 Data permissions
- Until the rights gate records the needed uses for a source, live MF data is neither ingested nor displayed (doc 17), and no licensed data reaches any model.
- The Data rights module gains two permitted-use values: **`ai_processing_internal`** and **`ai_processing_external`**. The P1 request must name both.
- **Real data used now (owner decision, 2026-10-23: build on real data, rights-clean only):**

  | Data | Source | Rights basis | How it enters |
  |---|---|---|---|
  | Risk-free rate (T-bill yields) | RBI DBIE | "Reproduction is permitted provided an acknowledgement of the primary source is made" (doc 17 §3). Automated retrieval: no clause, so not assumed | Owner-downloaded file through an import contract (ADR-021); acknowledgement shown wherever used. The series' availability on DBIE is still to confirm |
  | SEBI scheme categories, riskometer scale, TER/IR formulas, disclosure rules | SEBI MF Master Circular 2026-03-20 | Public regulation, cited by clause | Hand-encoded reference data and glossary templates, with clause citations |
  | Amounts, horizons, TER and return assumptions the user enters | The user | The user's own input | Calculator tools |

- **AMFI fund data in Phase 1 personal mode (owner direction, 2026-10-23; supersedes the earlier same-day full-universe risk acceptance).** AMFI's terms allow "personal and non-commercial use only" and also bar storing "any significant portion" of the site (doc 17 §3). Personal use therefore does **not** authorise bulk storage of the ~38,000-scheme history.

  | Rule | Setting |
  |---|---|
  | Rights-register entry | Source `amfi`, basis `amfi_terms_personal_use`, mode `personal`. Grants: `automated_retrieval` and `storage` **within the personal scope only**, `derived_metrics`, `display` (the one local user), `ai_processing_internal`. Denies `ai_processing_external`, `export`, display to anyone else, and all SaaS-mode use |
  | Bulk acquisition | **Gated, off.** The full-universe backfill cannot run until an adequate legal basis is recorded (permission, or a licensed supplier) |
  | Personal scope | A bounded, owner-set AMFI scope (setting `amfi.personal_scope`). **Default: none** (synthetic fixtures only) until the owner records a scope it considers defensible (ADR-023 §6) |
  | Capability | The full-universe pipeline is built and tested anyway. Schema, import contracts, fetcher, validation and the daily job are designed for ~38,000 schemes × ~20 years, and verified at that scale on **synthetic** data |
  | Retrieval | The AMFI adapter fetches direct from amfiindia.com (no mirrors), only within the gate and scope. Disabled by default; rate-limited; resumable; honest User-Agent; raw files kept with SHA-256 and fetch time. Owner exception to [ADR-021](ADR-021-data-supply-policy.md) rule 2, limited to this |
  | Models | Local Ollama only. No AMFI-derived content in any `external` payload or telemetry export (AC-5) |
  | Storage | The local database and raw-file store only. **Never** in the repository, CI, test fixtures or shared backups |
  | Tests and CI | Synthetic fixtures that copy AMFI layouts and the doc 17 quirks (skipped days, null NAVs, ISIN reuse, unadjusted splits, merged/matured/segregated schemes) |
  | Exit | If the legal basis fails: set scope to none, delete stored AMFI data and raw files, and use a licensed supplier's adapter. Core, agent and tests stay unchanged |

- **Owner actions running in parallel (outward-facing; not part of this ADR):** the AMFI permission request (doc 17 P1, including both AI-processing uses), and/or qualified legal advice.
- **Not used:** AMFI data through mirrors (mfnav.in, TigZig, mfapi.in), AMC files, index data, and real CAS files (A3 forbids real CAS in development).

### 2.12 Data refresh policy (owner decision, 2026-10-23)

**Principle: acquire once, validate once, serve many times.** Neither users nor the agent ever trigger a fetch.

| Setting | Decision |
|---|---|
| Frequency | Once daily, every calendar day |
| Time | **11:30 IST** |
| Why 11:30 | NAV deadlines (SEBI MF Master Circular 2026, §9.3.4): 11 PM on T for most schemes; 9 AM on T+1 for schemes with ETCD exposure; 10 AM on T+1 for FoFs and for index funds/ETFs with ≥80% overseas assets. 11:30 on T+1 is after every fixed deadline. Schemes that cannot value same-day publish at the time stated in their SID; the next run picks them up |
| Source | AMFI, direct. Personal mode: within the permitted personal scope only (§2.11). SaaS mode: only after a commercial permission is recorded (doc 17 P1). The same job runs in both modes (ADR-023) |
| Acquisition | Scheduled batch job, run as a durable job (A3 §5.1), resumable, rate-limited |
| Late NAVs and corrections | Each run re-reads a trailing **correction look-back window**, configurable; the initial value comes from observed correction frequency. Changed values append a new revision; history is never overwritten |
| Storage | Local PostgreSQL, in the MF-owned schema with MF-owned versioning and its own Alembic environment (ADR-023 §2.8); raw files kept with SHA-256 and fetch time |
| Validation | Completeness against the expected scheme list, duplicates (including ISIN reuse), nulls/zeros/negatives, day-over-day anomalies, future-dated rows, unadjusted splits flagged for review |
| Publication | **Atomic:** a run that passes validation becomes the current revision in one transaction. A failed run publishes nothing and alerts; the last good revision keeps serving |
| Missing or delayed NAVs | Keep the last valid value and show its **actual NAV date**, never today's date |
| Weekends and holidays | The job still runs. Liquid and overnight funds publish a NAV for every calendar day (§9.3.1), so those days carry real updates. If the source content hash is unchanged, the run records a no-op and publishes no new revision |
| Agent and API reads | Through Wickstreet's application interfaces only; every value carries `as_of` and `data_revision` (§2.3) |

Consequence: between about 23:00 on T and 11:30 on T+1, Wickstreet shows T−1 NAVs even where AMFI already has T. The owner accepted this for one consistent daily snapshot.

## 3. Consequences
- One module, four thin ports plus a routing table. Framework, model and language services can be swapped without touching financial logic.
- Correctness never depends on the model. Templates are a complete fallback, and the validator reduces, but does not eliminate, the risk of misleading text.
- Local Ollama keeps development data on the developer's machine.
- The rights gate grows by two use values.
- The evaluation sets (per language, advice-seeking, adversarial, injection) become maintained release assets. **They, the tools and the validator are the main engineering investment; the SDK choice is secondary.**

## 4. Acceptance criteria (synthetic data and user-entered calculations)

| # | Criterion | Evidence |
|---|---|---|
| AC-1 | 0 displayed numbers without a matching tool value and provenance | Validator unit tests + full evaluation set |
| AC-2 | Same tool inputs, data revision and method version produce byte-identical structured results and template renderings | Property tests |
| AC-3 | Unregistered tools cannot be called; invalid arguments are rejected; entitlement and rights checks deny by default | Unit/integration tests |
| AC-4 | **0 critical advice violations** in the release suite (C5). A critical violation is a scheme pick, allocation, suitability statement, or historical return presented as expected. The suite covers en, hi and hi-Latn, with direct, indirect, multi-turn and adversarial prompts (role-play, "just hypothetically", translation tricks, injected scheme text). Owner sets suite size; passing it does not guarantee zero production failures | Evaluation set |
| AC-5 | No licensed-field class appears **anywhere** in an outbound payload (prompt, history, tool definitions, tool results) or in a telemetry export when the matching AI-processing right is absent. Redaction verified across the whole payload in all three languages | Egress and telemetry tests with fixture rights records |
| AC-6 | Validator failure always yields the template answer in the user's language; template-only mode can be switched on per route | Fault-injection tests |
| AC-7 | Fixture research tasks (discover, compare, explain, operate the screen, save, diff) are completed in each language. Owner sets the bar after a first baseline | Task evaluation set |
| AC-8 | **Framework verification (C6):** the suite passes on (A) a local Ollama open-weight model and (B) a second compatible backend, local or already authorised, by configuration only. Both show en/hi/hi-Latn tool selection, correct calculations, grounded explanations, save confirmation, validator fallback, no unauthorised outbound payloads, and token/latency metering | CI job + verification note |
| AC-9 | Every model call is metered and normalised (§2.10) | Integration test |
| AC-10 | Injected instructions inside fixture scheme text change no tool call and cause no write | Injection test set |
| AC-11 | `research.save` executes only the stored payload after server verification. Tampered hash, other user or tenant, expired or reused id, and client-only approval are all rejected | Integration + E2E tests |
| AC-12 | Existing Momentum25 and stock capabilities pass their regression suites (A3 §3.2) | Existing CI |
| AC-13 | The workstation completes all fixture tasks with the agent disabled | E2E test |

## 5. Alternatives considered
- **OpenAI Agents SDK as primary:** capable and supported for non-OpenAI endpoints. It gives a less direct provider-neutral path for this application. Kept as fallback.
- **Claude Agent SDK:** the Claude Code harness with built-in file, bash and web tools; the wrong shape for a restricted agent. Claude models stay reachable through Pydantic AI if routing ever selects them.
- **A Wickstreet-wide model-provider abstraction:** rejected (C4); it would duplicate Pydantic AI.
- **Template-only explanations:** rejected by the owner; they lose conversational value.
- **Free model prose without a validator:** rejected.
- **A separate agent service:** rejected for now (A3 §1, §12).

## 6. Open questions
1. AC-4 suite size and AC-7 thresholds (owner).
2. Which open-weight models to evaluate first, after a licence and Indic-language desk check.
3. Conversation retention period and the deletion policy.
4. Whether Stage C may give the agent read-only Portfolio tools (separate decision).

## 7. Corrections applied at acceptance (2026-10-23)

| # | Correction |
|---|---|
| C1 | The validator is a safety boundary, not a correctness guarantee (§2.6) |
| C2 | Outbound checks cover the complete payload, history, tool results and telemetry (§2.8, AC-5) |
| C3 | Save confirmation is server-verified and bound to the exact stored action (§2.5, AC-11) |
| C4 | No second model abstraction; Pydantic AI is the provider layer (§2.2, §2.3) |
| C5 | AC-4 requires 0 critical advice violations with broader multilingual and adversarial coverage |
| C6 | Framework decided (Pydantic AI; OpenAI Agents SDK fallback; local Ollama for development; production model deferred). The spike becomes a two-backend verification (AC-8) |

## 8. Architecture review update (2026-10-23)

An independent review checked this ADR against current SDK documentation and the repository. The decisions in §2 stand. Items V1–V9 sharpen how they are built. Where an item and the text above differ, the item governs. No item changes C1–C6 or an acceptance criterion's intent.

**Framework check.** Both SDKs can meet §2. Pydantic AI stays the choice because its safe configuration is its default one.

| Need | Pydantic AI | OpenAI Agents SDK |
|---|---|---|
| Local Ollama, vLLM, other OpenAI-compatible servers | Native providers (`ollama:`, `vllm:`) | OpenAI-compatible client in Chat Completions mode; LiteLLM adapter is beta |
| Default wire API | Each provider's own | Responses API; most non-OpenAI providers need `chat_completions` |
| Telemetry default | Instrumentation off unless enabled | Tracing on; spans export to OpenAI |
| One hook before every model call | `WrapperModel` subclass sees messages, tool definitions and settings | `RunConfig.call_model_input_filter` |
| Deterministic tests | `TestModel`, `FunctionModel`, `ALLOW_MODEL_REQUESTS=False` | Scripted models in `agents.testing` |
| Tool approval | Deferred tools; the docs say approval is not an authorisation boundary | Pause and resume from `RunState` |

If the fallback is ever used: set `OPENAI_AGENTS_DISABLE_TRACING=1` and use Chat Completions.

| # | Item |
|---|---|
| V1 | **One framework port.** `AgentRuntime` is the only port over the SDK, and `run_turn` is `async`, like the rest of the stack. The tool catalogue is framework-free data: name, Pydantic argument and result models (`extra="forbid"`), owning application interface, entitlement and rights needs, template id. The adapter builds the Pydantic AI toolset from it and filters it per turn (`prepare_tools`). Each tool body re-checks entitlement and rights before it calls the owning interface. `ToolRegistry`, `OutboundPolicy`, `ResponseValidator` and template rendering are deterministic services of the agent context, not ports: each has one implementation. Language detection becomes a port only when a second implementation, such as BHASHINI, is adopted |
| V2 | **One egress choke point.** A `WrapperModel` subclass wraps every routed model, and each `FallbackModel` member separately, because members can differ in `location`. It runs `OutboundPolicy` on instructions, messages and tool definitions before it delegates. A test asserts that every route in the routing table is wrapped |
| V3 | **Server-held history.** The server loads history from the tenant-scoped conversation store. A client sends a conversation id and new text only. The server never accepts client-supplied history or tool results: forged tool results would carry false provenance into the turn |
| V4 | **Save without an SDK resume.** `research.save` becomes `research.propose_save`, an ordinary tool that stores the proposed action (§2.5 step 1) and returns its id. Confirmation is a plain endpoint, `POST /api/v1/mf/agent/actions/{id}/confirm`, that runs §2.5 steps 2–3 and executes the stored payload. No second model run follows. C3 and AC-11 are unchanged |
| V5 | **Two test tiers.** Per-commit CI uses scripted models and `ALLOW_MODEL_REQUESTS=False`. It covers AC-1 to AC-3, AC-5, AC-6, AC-9, AC-11 to AC-13 and the plumbing of AC-10. The live-model suites (AC-4, AC-7, AC-8 and live AC-10) are a recorded release gate on local Ollama, because model output varies between runs. AC-8's evidence is a release-gate run and verification note, not a CI job |
| V6 | **Agent data ownership.** Conversations, turns, proposed actions, model-call meter rows and audit records are tenant-owned tables under ADR-023 §2.6: non-null tenant and owner, RLS. Templates and the glossary are versioned shared reference data |
| V7 | **Refresh job.** The "durable job" in §2.12 is the `ingestion_run` record of [ADR-017 MF-10](ADR-017-funds-etfs-holdings.md#wickstreet-20-realignment-proposed-2026-10-23). Phase 1 adds no job queue and no worker process. MF revisions, corrections and atomic publication follow ADR-017 MF-5 to MF-8 |
| V8 | **History depth.** The owner set it to the last 10 years. That replaces the "~38,000 schemes × ~20 years" in §2.11; see [ADR-023 §7 U4](ADR-023-operating-modes.md#7-architecture-review-update-2026-10-23) |
| V9 | **Rights exit reaches saved records.** Saved turns and saved research hold tool values, so each stores the sources behind its values. When a source's rights end, the §2.11 exit deletes or redacts those values in tenant records too, not only the MF tables and raw files. Replay then shows the item as withdrawn for that source. The same rule serves SaaS deletion-at-termination terms ([14 §5](../../plans/wickstreet-2/14-stage-b-implementation-plan.md#5-data-acquisition-and-permissions-gate)) |

## Sources (accessed 2026-10-23)
- Pydantic AI model providers: <https://pydantic.dev/docs/ai/models/overview/>; deferred tools: <https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/>; licence (MIT): <https://github.com/pydantic/pydantic-ai/blob/main/LICENSE>
- OpenAI Agents SDK models and caveats: <https://openai.github.io/openai-agents-python/models/>; licence (MIT): <https://github.com/openai/openai-agents-python/blob/main/LICENSE>
- Claude Agent SDK scope: <https://code.claude.com/docs/en/agent-sdk>
- §8 review: Pydantic AI testing <https://pydantic.dev/docs/ai/guides/testing/>, `WrapperModel` <https://pydantic.dev/docs/ai/api/models/wrapper/>, `Model.request` <https://pydantic.dev/docs/ai/api/models/base/>; OpenAI Agents SDK tracing <https://openai.github.io/openai-agents-python/tracing/>, running agents <https://openai.github.io/openai-agents-python/running_agents/>, testing <https://openai.github.io/openai-agents-python/testing/>
