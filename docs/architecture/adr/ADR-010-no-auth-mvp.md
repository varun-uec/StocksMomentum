# ADR-010: No Auth in MVP, SaaS Seams Pre-built

**Status:** Accepted

## Context
The MVP is local/self-hosted and single-user, so authentication adds friction without value now. However, the architecture must evolve into a multi-tenant commercial SaaS without rearchitecture.

## Decision
Ship the MVP with **no authentication**. Pre-build the seams: a `get_current_user()` FastAPI dependency returning a singleton `AnonymousUser`, and a nullable `tenant_id` convention on tenant-scopable tables/queries. Secrets via env; CORS locked; rate-limit hook present.

## Consequences
- Fast MVP with no auth UX/infra.
- Adding auth later = replace one dependency (JWT/OAuth2), populate `tenant_id`, add role checks + per-tenant limits + audit log — no domain or use-case change.

## Alternatives considered
- **Full auth/multi-tenancy now:** rejected — premature for a local single-user MVP.
- **No seams (retrofit later):** rejected — retrofitting tenancy into queries/handlers is costly and error-prone.
