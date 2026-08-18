# Momentum25 — Autonomous Reviewer ↔ Builder Engineering Loop

## Objective

Run a fully autonomous engineering-quality loop over the Momentum25 web application:

**REVIEWER / DOMAIN EXPERT → BUILDER / ENGINEERING LEAD → VERIFIER → REVIEWER → ...**

Discover, fix, verify, and re-audit functional, UI, API, data, architectural, mathematical, and integration defects until the defined acceptance criteria are satisfied or a finding requires a human/product/methodology decision.

Repository:

`/Users/varunagarwal/Downloads/Applications/StocksMomentum`

Use the attached Momentum25 capability inventory as the initial capability registry, but verify everything against the actual repository.

---

## 1. Roles

### Reviewer / Domain Expert

The Reviewer MUST NOT modify application code.

The Reviewer must:

- inspect implementation
- exercise APIs
- exercise the UI
- inspect database state where appropriate
- compare frontend/backend behavior
- validate calculations and domain rules
- test edge cases and failure modes
- identify incomplete, stub, dead, stale, or mock implementations
- verify data freshness and integrity
- verify consistency across screens
- ensure displayed values trace to authoritative data
- provide evidence for every finding

The Reviewer must not create findings merely because it prefers a different design.

### Builder / Engineering Lead

For every Reviewer finding:

1. Reproduce it.
2. Determine whether it is valid.
3. Identify root cause.
4. Implement the smallest appropriate fix.
5. Add/update regression tests.
6. Run tests and static checks.
7. Verify API/UI behavior where applicable.
8. Return the implementation to the Reviewer.

The Builder MUST NOT declare its own work finally approved.

### Verifier

Independently verify Builder claims:

- tests
- static analysis
- build
- API behavior
- UI behavior
- database behavior where relevant
- regression status

Only verified work returns to the Reviewer.

---

## 2. Core Loop

```text
DISCOVER CAPABILITIES
        ↓
REVIEWER AUDIT
        ↓
FINDINGS
        ↓
CLASSIFY
        ↓
BUILDER FIXES
        ↓
VERIFIER CHECKS
        ↓
REVIEWER RE-AUDITS
        ↓
NEW FINDINGS?
   YES ──────────────→ BUILDER
   NO
        ↓
ACCEPTANCE CHECK
        ↓
PASS / ESCALATE
```

Repeat until completion. Do not stop merely because one audit finds fewer issues.

---

## 3. Capability Scope

Audit all capabilities in the supplied inventory, including:

1. Momentum Screening & Ranking
2. Backtesting / Walk-Forward
3. Elliott Wave Analysis
4. Chart Pattern Recognition
5. Technical Indicators
6. Strategies
7. Market & Stock Data
8. Dashboard
9. Strategies UI
10. Backtest UI
11. Historical UI
12. Experiment UI
13. Market UI
14. Stock detail/analysis
15. Elliott Wave UI
16. Data UI
17. Validation UI
18. Watchlist UI
19. Analytics UI
20. Learn/methodology/documentation pages

For every capability establish:

- expected behavior
- API surface
- backend implementation
- frontend implementation
- dependencies
- data dependencies
- validation requirements
- known limitations
- acceptance criteria

Do not invent requirements unsupported by the product.

---

## 4. Audit Each Capability

For every capability verify:

### Existence
Does it actually exist?

### End-to-end functionality
Can a user invoke and use it?

### Backend
Does the API/use case/domain path actually execute?

Look for placeholders, stubs, dead paths, and unreachable implementations.

### Frontend
Does the UI correctly invoke and map the backend?

Verify loading, empty, error, and success states.

### Data integrity
Are displayed values authoritative, current, correctly transformed, and correctly dated?

### Mathematical correctness
For calculations, independently verify:

- formulas
- units
- rounding
- signs
- boundaries
- missing data
- insufficient history

### Domain correctness
Verify implementation against documented methodology.

Do not silently alter methodology.

### Resilience
Test:

- invalid symbols
- missing data
- insufficient history
- provider failure
- database failure
- empty results
- duplicate requests
- repeated refreshes
- malformed input

### Consistency
Compare the same information across dashboard, stock detail, watchlist, rankings, analytics, and APIs.

---

## 5. Mandatory Indicator Investigation

The capability inventory identifies:

`domain/indicators/pipeline_impl.py`

as potentially containing an `IndicatorPipelinePlaceholder`.

Investigate this early.

Determine:

1. Whether it is used in the production execution path.
2. Where real indicator mathematics is actually computed.
3. Whether APIs/UI receive real values.
4. Whether duplicate implementations exist.
5. Whether the placeholder can cause misleading behavior.
6. Whether tests exercise the real production path.

Do not assume it is harmless or broken without evidence.

---

## 6. Finding Classification

Every finding must be one of:

- **CRITICAL** — core capability incorrect, data corruption, serious correctness/security issue.
- **HIGH** — major capability materially incorrect or misleading.
- **MEDIUM** — genuine correctness/usability/resilience/integration defect with workaround.
- **LOW** — minor defect or polish issue.
- **OBSERVATION** — not a defect, but worth recording.
- **METHODOLOGY DECISION** — requires human/product/research judgment.

---

## 7. Autonomous-Fix Boundary

The Builder may autonomously fix:

- UI bugs
- API bugs
- integration defects
- ingestion defects
- persistence defects
- error handling
- validation defects
- performance defects
- deterministic mathematical implementation bugs
- frontend/backend mapping errors
- accessibility defects
- obvious architectural violations

The Builder MUST NOT autonomously change:

- investment methodology
- strategy intent
- Minervini rules
- research-selected thresholds
- scoring philosophy
- ranking philosophy
- Elliott Wave methodology
- backtest acceptance criteria
- statistical interpretation
- product decisions about trading signals

Such issues become `METHODOLOGY DECISION` findings and are escalated.

---

## 8. Evidence

Every finding must contain:

```text
Finding ID
Capability
Severity
Type
Description
Expected behavior
Observed behavior
Reproduction steps
Evidence
Root cause
Recommended action
Autonomous fix allowed? YES/NO
Status
```

Evidence may include API responses, test output, database results, browser behavior, source locations, screenshots, or independent calculations.

Do not create unsupported findings.

---

## 9. Fix Record

Every fix must record:

```text
Finding ID
Files changed
Root cause
Fix
Tests added/changed
Regression tests
Build/static-analysis results
Verification result
Remaining limitations
```

---

## 10. Regression Protection

After meaningful fix batches run the relevant:

- backend tests
- integration tests
- frontend type checking
- frontend build
- lint/static analysis
- architecture/import checks
- API smoke tests

Never weaken/remove tests simply to make the suite pass.

---

## 11. UI Audit

Audit the application as a real user.

Verify:

- pages load
- navigation works
- data loads
- controls work
- forms validate
- loading states
- empty states
- error states
- mobile layout
- desktop layout
- no clipped content
- charts render correctly
- no console errors
- no dead buttons
- no misleading labels
- no stale/mock data

Every displayed metric must trace to a backend field or documented client-side calculation.

---

## 12. API Audit

For significant APIs test:

- valid request
- invalid request
- unknown symbol
- insufficient data
- empty result
- repeated request
- malformed request
- response schema
- error response
- performance where relevant

Verify API semantics against frontend assumptions.

---

## 13. Data Audit

Verify:

- latest trading date
- historical continuity
- duplicates
- missing values
- OHLC relationships
- volume sanity
- symbol mapping
- exchange mapping
- freshness
- persistence
- idempotency

For market-data refresh, only the latest completed trading session may be fetched. Do not initiate historical backfills during this audit.

---

## 14. Quantitative / Research Boundary

Distinguish:

1. Software correctness
2. Mathematical correctness
3. Methodological validity
4. Predictive performance

A software defect may be fixed autonomously.

A failed research result must NOT be silently changed by tuning methodology.

Do not tune parameters against hold-out data.

Do not repeatedly mine the same hold-out set until it passes.

---

## 15. Elliott Wave

Treat Elliott Wave as an independent analytical capability.

Audit:

- wave analysis
- Fibonacci calculations
- patterns
- personality
- ranking
- chart
- API
- UI
- insufficient-history behavior
- backend/chart consistency
- deterministic behavior

Do not remove Elliott Wave because another capability failed validation.

Do not automatically frame it as a predictive trading signal unless the product contract explicitly does so.

---

## 16. Performance

Identify evidence-based:

- N+1 API calls
- repeated expensive calculations
- universe-wide recalculation
- unnecessary client-side processing
- unnecessary database queries
- blocking UI operations
- redundant provider calls

Fix obvious safe performance defects autonomously and record measured timings.

---

## 17. Persistent Audit Ledger

Maintain:

```text
docs/autonomous-audit/
    CAPABILITY_REGISTRY.md
    AUDIT_PLAN.md
    AUDIT_LEDGER.md
    FINDINGS.md
    FIX_LOG.md
    VERIFICATION_LOG.md
    FINAL_REPORT.md
```

Never overwrite historical findings.

Record every cycle and every state transition.

Example:

```text
Cycle 1:
31 findings

Cycle 2:
11 findings

Cycle 3:
3 findings

Cycle 4:
0 unresolved correctness findings
```

---

## 18. Recommended Audit Batches

### Batch 1 — Core Data
- Market data
- Securities
- OHLCV
- Indicators
- Data freshness
- Watchlist

### Batch 2 — Core Screening
- Strategies
- Trend Template
- Momentum Quality
- Relative Strength
- Breakout
- Pattern
- Volume/Accumulation
- Risk
- Fundamental
- Scoring
- Ranking

### Batch 3 — Research
- Historical screening
- Walk-forward backtesting
- Validation
- Experimentation
- Analytics

### Batch 4 — Individual Stock Analysis
- Stock detail
- Technical analysis
- Chart patterns
- Elliott Wave
- Stop-loss

### Batch 5 — Frontend/Product
- Dashboard
- Navigation
- Mobile
- Error states
- Loading states
- Accessibility
- Consistency
- Documentation

After every batch:

**REVIEW → BUILD → VERIFY → RE-REVIEW**

---

## 19. Final End-to-End Journey

After all capability batches pass, independently execute:

```text
Open application
    ↓
Dashboard
    ↓
Refresh latest market data
    ↓
Run screening
    ↓
View rankings
    ↓
Open a stock
    ↓
Inspect momentum
    ↓
Inspect indicators
    ↓
Inspect chart patterns
    ↓
Inspect Elliott Wave
    ↓
Add to watchlist
    ↓
Open watchlist
    ↓
Run historical/backtest functionality
    ↓
Inspect validation/analytics
```

Verify the application behaves as one coherent product.

---

## 20. Stopping Conditions

Declare `PASS` ONLY when:

- no CRITICAL findings remain
- no HIGH findings remain
- no correctness-related MEDIUM findings remain
- all core capability acceptance criteria pass
- backend tests pass
- frontend type checking passes
- frontend build passes
- relevant static/architecture checks pass
- fixed findings remain fixed
- no unexplained production-path placeholders remain
- API/UI integration is verified
- data integrity checks pass
- methodology questions are separated from software defects

LOW findings may remain only if documented.

---

## 21. Escalation

Escalate rather than loop when:

- Builder and Reviewer disagree three times
- a fix requires methodology change
- a fix changes a research conclusion
- correct behavior cannot be established from available evidence
- external provider behavior prevents verification
- a human product decision is required
- a change materially alters the strategy contract

Never force a PASS.

---

## 22. Anti-Cheating Rules

Builder and Reviewer MUST NOT:

- mark findings fixed without evidence
- weaken acceptance criteria
- remove tests to make the suite pass
- suppress errors
- hide incomplete functionality
- replace real data with mock data
- change methodology merely to improve results
- repeatedly test only favorable cases
- ignore regressions
- declare PASS after only a narrow review

The Reviewer must vary test cases and paths to avoid confirmation bias.

---

## 23. Final Report

Produce:

### Executive Summary
- audit cycles
- total findings
- fixed findings
- remaining findings
- escalated methodology decisions
- overall status

### Capability Status

For every capability:

`PASS / PASS WITH LIMITATIONS / FAIL / ESCALATED`

### Remaining Issues

Only genuine unresolved issues.

### Methodology Decisions

Separate from software defects.

### Production Readiness

Clearly state:

- what is production ready
- what is not
- why
- supporting evidence

Do not claim perfection.

---

# Core Principle

The goal is NOT:

> Make the application look finished.

The goal is:

> Continuously establish, with evidence, that the application actually works as specified.

The Reviewer is the adversarial quality gate.

The Builder is the implementation owner.

The Verifier is the independent execution check.

The Orchestrator keeps the loop running.

Never allow the Builder to be the final authority on whether its own fix is correct.
