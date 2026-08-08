# ADR-002: Python 3.12 / FastAPI Backend

**Status:** Accepted

## Context
The system is dominated by numeric, quant logic (indicators, statistical ranking) and needs strong typing, fast iteration, and a first-class data ecosystem. It also needs an async HTTP API with auto-generated contracts for web (and future mobile) clients.

## Decision
Use **Python 3.12** with **FastAPI** + **Pydantic v2** for the backend; numpy for vectorized indicator math, `Decimal` at the persistence boundary for determinism; SQLAlchemy 2.0 async + Alembic for persistence.

## Consequences
- Best-in-class libraries for technical analysis and data handling.
- Auto OpenAPI → generated TS client shared by web/mobile.
- Must enforce the Decimal/float boundary carefully (see ADR-009) to preserve determinism.

## Alternatives considered
- **TypeScript end-to-end (NestJS + Next + RN):** maximal code sharing, but a weaker quant/TA ecosystem — more bespoke numeric code, higher bug surface. Rejected.
- **Java/Kotlin (Spring Boot):** robust for long-lived SaaS but heavier, slower iteration, weaker quant tooling. Rejected for MVP.
