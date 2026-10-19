# Security

## The boundary

Wickstreet has **no login**. Each copy has one owner, and every browser that reaches it acts as that owner ([ADR-010](docs/architecture/adr/ADR-010-no-auth-mvp.md), [ADR-012](docs/architecture/adr/ADR-012-open-source-self-hosted.md)). The network is the only access control, so the defaults keep it closed:

- Every published port listens on `127.0.0.1`: the app, PostgreSQL, Redis and the dev tools.
- `APP_BIND=0.0.0.0` exposes **the app port only** to your LAN. Everyone on that network then has full read and write access. The database and Redis stay on loopback.
- The API rejects a `Host` header that is not on `M25_ALLOWED_HOSTS` (`421`, against DNS rebinding). It also rejects a state-changing request whose `Origin` is not allowed (`403`, against cross-site request forgery).

These checks do not replace authentication. **An unauthenticated network-exposed instance is not secure.** Keep Wickstreet loopback-only. For any network exposure, put an authenticating reverse proxy in front of it; the application itself still has no login.

## Known limits

- Default database credentials (`momentum25` / `momentum25`) are in `.env.example`. They are safe only because the database listens on loopback. Change them if you change that.
- The API sets no limit on request-body size, and Strategy Studio evaluations run in the API process with no limit on how many run at once. An owner can slow their own copy, but no one else can reach it.
- Exchange downloads are disabled by default. If an operator explicitly enables direct exchange downloads, they are responsible for confirming the provider's current terms and permitted use. The project grants no data rights. The supported default workflow imports an operator-authorized CSV export.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting on the repository ("Security" → "Report a vulnerability"). Include the version, the steps to reproduce and the impact.
