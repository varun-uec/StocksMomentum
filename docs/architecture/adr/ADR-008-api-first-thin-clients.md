# ADR-008: API-first, Thin Clients (Mobile Readiness)

**Status:** Accepted

## Context
The first client is a responsive web app, but the architecture must support future native/cross-platform mobile **without** significant backend, API, domain, or business-logic changes.

## Decision
Keep **all business logic server-side** behind a stable, versioned **REST/JSON API** (`/api/v1`). Clients (web now, React Native later) are thin presentation layers. Publish an OpenAPI-generated TypeScript client consumed by both web and mobile.

## Consequences
- A future mobile app requires no server change; web and mobile share contracts.
- Forces clean DTO boundaries and prevents business logic leaking into the UI.
- Versioned paths allow non-breaking evolution.

## Alternatives considered
- **Server-rendered HTML / business logic in web app:** rejected — not reusable by mobile.
- **GraphQL:** deferred — REST + OpenAPI is simpler for MVP; can be added as an additional interface adapter later.
