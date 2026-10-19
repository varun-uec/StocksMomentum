# Security

## The boundary

Wickstreet has **no login**. Each copy has one owner, and every browser that reaches it acts as that owner ([ADR-010](docs/architecture/adr/ADR-010-no-auth-mvp.md), [ADR-012](docs/architecture/adr/ADR-012-open-source-self-hosted.md)). The network is the only access control, so the defaults keep it closed:

- Every published port listens on `127.0.0.1`: the app, PostgreSQL, Redis and the dev tools.
- `APP_BIND=0.0.0.0` opens **the app port only** to your LAN. Everyone on that network then has full read and write access. The database and Redis stay on loopback.
- The API rejects a `Host` header that is not on `M25_ALLOWED_HOSTS` (`421`, against DNS rebinding). It also rejects a state-changing request whose `Origin` is not allowed (`403`, against cross-site request forgery).

These checks do not replace authentication. **Do not expose Wickstreet to the internet** unless an authenticating reverse proxy stands in front of it.

## Known limits

- Default database credentials (`momentum25` / `momentum25`) are in `.env.example`. They are safe only because the database listens on loopback. Change them if you change that.
- The API sets no limit on request-body size, and Strategy Studio evaluations run in the API process with no limit on how many run at once. An owner can slow their own copy, but no one else can reach it.
- Market data comes from NSE's public archives. Each user is responsible for following NSE's terms. The project grants no data rights.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting on the repository ("Security" → "Report a vulnerability"). Include the version, the steps to reproduce and the impact.
