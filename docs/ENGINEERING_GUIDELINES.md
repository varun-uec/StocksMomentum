# Momentum25 India — Engineering Guidelines

## Mission

Build a production-grade quantitative research platform for momentum investing in the Indian stock market.

The objective is long-term engineering excellence rather than rapid feature delivery.

Every implementation should improve one or more of the following:

- Correctness
- Determinism
- Explainability
- Maintainability
- Extensibility
- Testability
- Operational Excellence

---

# Engineering Philosophy

Think before coding.

Challenge assumptions.

Do not preserve an implementation simply because it already exists.

If a better solution exists without violating the approved architecture, recommend it before implementation.

Prefer simplicity over cleverness.

Optimize for lifetime maintainability rather than implementation speed.

---

# Authority

Project decisions must follow this order:

1. Architecture Design Document
2. ADRs
3. Implementation Specification
4. CLAUDE.md
5. Engineering Guidelines
6. Current Milestone
7. Existing Code

---

# Architecture

Always preserve:

- Hexagonal Architecture
- Clean Architecture
- Dependency Inversion
- High Cohesion
- Low Coupling
- Composition over Inheritance
- Single Responsibility

Business logic belongs only inside the Domain.

Infrastructure must remain replaceable.

The UI must never contain business logic.

---

# Quantitative Principles

Momentum25 is a deterministic quantitative research platform.

Never implement:

- discretionary behaviour
- AI generated rankings
- subjective trading rules

Every calculation must be reproducible.

Historical replay must never leak future information.

Every formula should be mathematically correct.

Every score must be explainable.

---

# Product Philosophy

The application should feel like an institutional quantitative research platform.

Prioritize:

- clarity
- transparency
- responsiveness
- information density
- usability

Avoid unnecessary complexity.

Avoid decorative UI.

---

# Education

Every feature should improve user understanding.

Every score should explain:

- why it exists
- how it was calculated
- what influenced it
- what prevented a higher score

Documentation should never diverge from implementation.

---

# Evidence Based Engineering

Major implementation decisions should be supported by one or more of:

- Architecture
- ADRs
- Published methodology
- Technical literature
- Empirical research
- Deterministic testing

If evidence does not exist, clearly identify assumptions.

---

# Continuous Improvement

Assume the first implementation is not the best implementation.

Continuously evaluate:

- Simplicity
- Maintainability
- Coupling
- Readability
- Performance

Improve where justified.

---

# Quality Gates

A milestone is complete only when:

✓ Architecture preserved

✓ Determinism preserved

✓ Explainability preserved

✓ Tests pass

✓ Frontend builds

✓ Manual smoke testing completed

✓ Documentation updated

✓ No unnecessary technical debt introduced

✓ Existing behaviour preserved

---

# Principal Engineer Review

Before declaring completion perform a critical review.

Evaluate:

- correctness
- architecture
- maintainability
- cohesion
- coupling
- readability
- performance
- extensibility
- product quality

If the implementation would not pass a Principal Engineer review, continue improving it.

---

# Definition of Done

A milestone is complete only when:

- Objectives satisfied
- Quality gates passed
- Manual verification completed
- Documentation updated
- Existing functionality verified