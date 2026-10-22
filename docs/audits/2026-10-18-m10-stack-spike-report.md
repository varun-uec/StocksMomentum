# M10 Stack Spike Report

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Decides:** [ADR-013](../architecture/adr/ADR-013-web-stack-and-chart-data.md) §1–§3
> **Status:** evidence for the owner's decision. ADR-013 stays Proposed until the owner accepts it.

## Verdict

**Option A (Vite SPA) passes every spike criterion.** Recommendation: accept ADR-013 §1–§3.

The spike migrated the whole web app, not only two routes. The Next.js surface was small (8 `next/link` files, 6 `next/navigation` files, 1 `next/font`), so a full migration cost less than running two stacks side by side.

## Criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| S1 | Deep link survives a hard reload and a new tab | **Pass** | `e2e/m10-stack.spec.ts`: 21 routes hard-loaded; `/stock/RELIANCE/analysis?strategy=…` reloaded and opened in a new tab |
| S2 | `PriceChart` and the drawing primitive run unchanged | **Pass** | No change to `PriceChart.tsx` or `chart-drawings.ts` beyond removing `'use client'`. Charts render on `/stock/*` and in the 16-chart grid. |
| S3 | Same-origin `/api/v1`, no URL setting | **Pass** | `API_BASE = '/api/v1'`. E2E asserts no request leaves the page origin. |
| S4 | Query cache and state survive navigation | **Pass** | E2E: after `/stock/RELIANCE` → `/watchlist` → back, the OHLCV request count stays the same |
| S5 | The API container serves the build; Compose loses `web` | **Pass** | `docker compose up -d --build api`: `/` and `/stock/RELIANCE` return `200 text/html`. Compose has 3 services. |
| S6 | Image size and start time no worse | **Pass** | See below |
| S7 | Smoke: 16 charts mount, pan and unmount with no errors | **Pass** | E2E on `/lab/chart-grid?n=16`: 16 canvases visible, a drag pans one chart, navigation unmounts all, no console errors |

Every E2E test also fails on any browser console error, uncaught error or CSP violation.

### S6 measurements

| | Before (Next.js) | After (Vite) |
|---|---|---|
| Images | `api` 126.9 MB + `web` 356.5 MB = **483.4 MB** | one image, **128.2 MB** (−73%) |
| Containers for the app | 2 (`api`, `web`) | 1 (`api`) |
| Start to ready, 3 runs | API 2.44–2.72 s; web 0.45–0.56 s (in parallel) | 2.50–2.62 s to serve `/` |

Sizes are `docker image inspect .Size`. Start time runs from `docker run` until the first `200` (API: `/api/v1/health/live`; new image: `/`). Measured on the owner's laptop against the E2E database clone.

## Security boundary (ADR-012), tested on the running container

| Request | Expected | Got |
|---|---|---|
| `GET`, `Host: evil.example:8000` | 421 | 421 |
| `GET localhost`, no `Origin` | 200 | 200 |
| `GET 127.0.0.1`, foreign `Origin` | 200 | 200 |
| `POST localhost`, no `Origin` (curl) | passes the guard | 404 (unknown symbol, so the guard let it through) |
| `POST 127.0.0.1`, no `Origin` (curl) | passes | 404 |
| `POST`, same `Origin` | passes | 404 |
| `POST`, `Origin: https://evil.example` | 403 | 403 |
| `POST`, `Origin: null` | 403 | 403 |
| `POST`, same host on another port | 403 | 403 |
| `POST`, `Host: evil.example` | 421 | 421 |
| App port from the LAN address | unreachable | unreachable |

Unit tests cover the same table (`tests/unit/test_host_origin_guard.py`). The rule for writes: when `Origin` is present, its authority must equal the `Host` header. That is same-origin by definition, so it needs no port setting and survives a changed `API_PORT`.

## Decisions taken during the spike

- **Vite 7.3.6, not Vite 8.** Vite 8 declares optional devtools peers that pull in the newest Vitest. That crashes npm 10's resolver (`Cannot read properties of null (reading 'edgesOut')`). Vite 7 is the older, settled line and has no such peers. Vitest 4.1.11 matches it. The lockfile was generated once with npm 11.21.0 (through `npx`). `npm ci` on npm 10 installs it cleanly, so CI and Docker are unaffected.
- **React Router 7 used directly**, with no compatibility layer for Next APIs. `Link href` became `Link to`, and `useRouter().push` became `useNavigate()`. Routes are lazy-loaded, one chunk per route, as Next did.
- **The theme script became a file** (`public/theme-init.js`), because the API's CSP allows only same-origin scripts.
- **The font is self-hosted** (`@fontsource-variable/inter`). Next downloaded it at build time. The app now makes no request to a third party at run time.
- **ESLint keeps Next's rule set** (`react`, `react-hooks`, the six `jsx-a11y` rules), pinned to the plugin versions Next had installed. `import/no-anonymous-default-export` (one warning-level rule) was dropped with `eslint-plugin-import`.
- **E2E runs against a clone of the local database** (`make e2e-db`, `CREATE DATABASE … TEMPLATE`), so tests that write data never touch the owner's own workspace.
- **The rate limiter now counts API calls only.** One page load fetches many static files, and those are not API traffic.

## Defects found and fixed

1. **The Docker image had no strategy configs.** `M25_STRATEGY_DIR` pointed outside the image, so a fresh `docker compose up` skipped strategy sync with only a warning. The image now copies them. Startup synced 7 strategies.
2. **`EngineEffectivenessResponse` dropped `measurability`.** The router passed the field, but the DTO did not declare it, so Pydantic discarded it silently. `/validation` crashed whenever engine rows existed. The E2E suite found it. Regression test: `test_validation_dto_measurability.py`.
3. **The API URL setting never worked.** The client read `NEXT_PUBLIC_API_BASE`; Compose and `.env.example` set `NEXT_PUBLIC_API_BASE_URL`. Same-origin removes the setting entirely.
4. **Chart attribution was missing.** Every page footer now credits TradingView Lightweight Charts™ and links to tradingview.com. `/about` holds the NOTICE text.

## Not done in M10

- **Generated OpenAPI types.** `npm run gen:api` exists. The handwritten `types.ts` stays for existing screens. M11 uses generated types for its new endpoints. A CI drift check follows once a generated file is in use.
- **E2E in CI.** It needs a populated market database. It runs locally with `make web-test`.
- **Defect class, not fixed:** every response DTO uses Pydantic's default `extra="ignore"`, so any other field the router passes but the DTO lacks would vanish the same way. A shared DTO base with `extra="forbid"` would catch this at test time. Proposed for M12 hardening.
