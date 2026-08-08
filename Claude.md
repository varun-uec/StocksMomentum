# CLAUDE.md — Engineering Constitution

## Mission

You are implementing **Momentum25 India**, a production-quality, deterministic momentum screening platform.

Your responsibility is to faithfully implement the approved architecture while maximizing correctness, simplicity, maintainability, determinism, and long-term extensibility.

The codebase should remain understandable and maintainable by a senior engineering team for the next decade.

---

# Sources of Truth

When instructions conflict, follow this precedence:

1. Architecture Design Document (ADD)
2. Architecture Decision Records (ADRs)
3. Implementation Specification
4. CLAUDE.md
5. Current task prompt
6. Existing implementation

Never violate a higher-priority source to satisfy a lower-priority one.

---

# Engineering Mindset

Think before coding.

Understand before modifying.

Verify before concluding.

Refactor before duplicating.

Simplify before extending.

Finish before starting something new.

Every change should move the codebase closer to the approved architecture.

---

# Implementation Workflow

For every task:

1. Understand the objective.
2. Read the affected code.
3. Understand dependencies.
4. Verify assumptions from the code—not previous summaries.
5. Identify the smallest clean solution.
6. Implement.
7. Test.
8. Refactor if it improves clarity.
9. Validate against the architecture.

Do not skip steps to save time.

---

# Architecture

Maintain strict Hexagonal / Clean Architecture.

### Domain

* Pure business logic.
* No I/O.
* No framework dependencies.
* No infrastructure dependencies.

### Application

* Orchestrates use cases.
* Coordinates domain services.
* Depends only on domain abstractions.

### Infrastructure

* Implements ports.
* Contains adapters for persistence, external APIs, scheduling, caching, messaging and configuration.
* Never contains business rules.

### Interface

* HTTP
* CLI
* DTO mapping
* Validation
* Serialization

Dependencies always point inward.

---

# Architectural Discipline

Do not redesign the architecture during implementation.

If implementation exposes a genuine architectural weakness:

* Stop.
* Explain the issue.
* Explain the trade-offs.
* Recommend the change.
* Wait for approval before changing architecture.

Never introduce architectural drift through incremental changes.

---

# Repository Discipline

Treat the repository as a long-lived product.

Prefer:

* modifying existing modules
* extending existing abstractions
* reducing duplication
* simplifying code
* improving readability

Avoid:

* speculative abstractions
* dead code
* commented-out code
* unnecessary files
* temporary fixes
* architectural shortcuts
* duplicated business logic

Every commit should leave the repository cleaner than before.

---

# Determinism

Business behaviour must be deterministic.

Given identical inputs:

* identical outputs
* identical scores
* identical rankings
* identical explanations

Never introduce hidden state, randomness or non-deterministic behaviour.

Every score must be reproducible and explainable.

---

# Don't Guess

Never invent:

* business rules
* APIs
* schemas
* configuration
* architecture
* implementation requirements

If information is missing:

* identify the ambiguity
* locate the relevant architecture document
* ask for clarification if necessary

Evidence always takes precedence over assumptions.

---

# Scope Discipline

Implement only the current milestone.

Do not begin future milestones early.

Do not implement speculative features.

Create extension points only where the architecture explicitly requires them.

---

# Code Quality

Prefer:

* simple solutions
* explicit behaviour
* cohesive modules
* small functions
* descriptive names
* composition over inheritance
* immutable value objects
* dependency inversion

Avoid clever solutions that reduce readability.

Optimize for maintainability rather than brevity.

---

# Testing

Every business change should include appropriate tests.

Prefer:

* unit tests
* integration tests
* deterministic golden tests

Never bypass failing tests.

Never reduce coverage to satisfy implementation.

---

# Performance

Write clear code first.

Optimize only when:

* justified by measurement, or
* required by the architecture.

Do not sacrifice readability for premature optimization.

---

# Milestone Discipline

Complete one milestone completely before beginning another.

A milestone is complete only when:

* implementation is complete
* tests pass
* documentation is updated where required
* architecture remains intact
* the application builds successfully
* the repository remains deployable

Never leave partially implemented architectural components.

---

# Definition of Success

Success is measured by:

* architectural consistency
* correctness
* simplicity
* maintainability
* determinism
* testability
* readability
* extensibility

Success is **not** measured by:

* lines of code
* files created
* implementation speed
* feature count

---

# Default Behaviour

Unless instructed otherwise:

* be concise
* minimize token usage
* verify from the code
* preserve the approved architecture
* make the smallest high-quality change
* explain significant decisions briefly
* stop when architectural clarification is required

Think like a Principal Engineer, implement like a Senior Engineer, and leave the codebase better than you found it.
