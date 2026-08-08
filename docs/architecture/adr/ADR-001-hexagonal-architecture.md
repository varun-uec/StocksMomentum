# ADR-001: Hexagonal / Clean Architecture

**Status:** Accepted

## Context
The product's core value is a *deterministic, explainable* scoring engine. That core must be trivially testable, reproducible, and free of incidental coupling to data sources, storage, scheduling, or transport — all of which will change over the product's lifetime (Bhavcopy → broker APIs, Postgres → managed, REST → mobile/queue).

## Decision
Adopt Hexagonal (Ports & Adapters) / Clean Architecture with four layers — `domain` (pure), `application` (use cases), `infrastructure` and `interface` (adapters). The dependency rule (dependencies point inward) is enforced in CI via import-linter. The domain core performs **no I/O**.

## Consequences
- The quant core is a pure function of (data + config): unit-testable with golden masters, reproducible.
- Swapping providers/storage/clients never touches business logic.
- Slightly more boilerplate (ports + mapping) than a monolithic MVC app — accepted for long-term maintainability.

## Alternatives considered
- **Layered MVC / "fat service" app:** rejected — couples I/O to logic, undermines determinism and testability.
- **Framework-centric (Django-style):** rejected — business logic leaks into ORM/views.
