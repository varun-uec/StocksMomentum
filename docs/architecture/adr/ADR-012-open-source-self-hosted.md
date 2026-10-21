# ADR-012: Open-Source, Self-Hosted Distribution, Local by Default

**Status:** Proposed (draft revision 2, 2026-10-18)

## Context
Wickstreet will be a public GitHub project. It uses NSE daily data only. A hosted service that shows NSE data to many users would redistribute that data and would need authentication. A copy that each user runs privately avoids central redistribution and needs no shared auth. It does **not** by itself settle whether NSE's terms permit each user's retrieval and use of the data.

ADR-010 has no login. That is safe only when the network limits who can reach the app. Today `docker-compose.yml` publishes the API (8000), the web app (3000), Postgres (5432) and Redis (6379) on every network interface. On a laptop on shared Wi-Fi, anyone on that network can change strategies and workspaces, and can reach the database directly.

## Decision

### Distribution
- Publish the source on GitHub. The licence is decided in ADR-015.
- Each user runs a private copy with `docker compose up`. Each copy fetches its own NSE bhavcopy. The project ships no market data and runs no shared service.
- The product name is **Wickstreet**. The name is provisional until domain and trademark clearance is complete (M16). Internal identifiers stay `momentum25` (ADD §4a).

### Ownership model
- One instance has one owner. Every browser that reaches the instance acts as that owner. There are no accounts and no roles.
- This is a **deployment assumption, not a security control.** The controls below make the assumption hold by default.
- Multi-user use needs authentication. That stays deferred to the SaaS path (ADR-010). `tenant_id` stays the seam.

### Security boundary
1. **Loopback by default.** Compose binds every published port to `127.0.0.1`: the app, Postgres, Redis and the dev-profile tools (Adminer, RedisInsight). Local non-Docker runs keep working, because they connect through `localhost` (`.env.example:20-21`). Nothing is reachable from another machine.
2. **LAN access is an explicit opt-in.** It is one documented setting (`APP_BIND=0.0.0.0`), and it applies to the app port only. The database and Redis always stay on loopback. The docs state that LAN access gives full read and write access to everyone on that network.
3. **Defence in depth: `Host` and `Origin` checks.** By default the allowlist holds the loopback names (`localhost`, `127.0.0.1`, `[::1]`) with the configured port. LAN opt-in adds the configured host names.

   | Request | Rule | Why |
   |---|---|---|
   | Any request whose `Host` is not on the allowlist | Reject with `421 Misdirected Request` | Blocks DNS rebinding |
   | State-changing (`POST`, `PUT`, `PATCH`, `DELETE`) with an allowlisted `Origin` | Allow | The Wickstreet SPA (same origin) |
   | State-changing with any other `Origin`, including `Origin: null` | Reject with `403` | Blocks cross-site request forgery from other websites and sandboxed frames |
   | State-changing with **no** `Origin` header | Allow, if `Host` passes | Non-browser clients (`curl`, scripts, the OpenAPI client) send no `Origin`. Browsers always send `Origin` on cross-origin state-changing requests, so a missing `Origin` cannot come from a cross-site page. |
   | `GET`, `HEAD`, `OPTIONS` | `Host` rule only | Reads change no state |

   The `momentum25` CLI runs use cases in-process and does not call the HTTP API, so these rules do not affect it. CORS is off, because the app is same-origin (ADR-013). M10 tests every row of this table, including `curl` without `Origin` against `localhost` and `127.0.0.1`.
4. **These checks do not replace authentication.** To expose an instance beyond a trusted local network, the user must put it behind an authenticating reverse proxy. The README says this plainly. Until auth exists, the project supports no other remote setup.

### Positioning
- The name never contains "TradingView" or "OpenChart".
- The README may say "an open-source, self-hosted alternative to TradingView for NSE daily charts".
- The README and the About page state: "Not affiliated with or endorsed by TradingView, Inc."
- We use no TradingView or OpenChart names, logos, icons or other brand assets (ADD §1a).

### Attribution (licence requirement, lands in M10)
- The `lightweight-charts` licence requires us to credit TradingView as the creator of the chart library, include its NOTICE text, and link to https://www.tradingview.com/ on a page users can reach.
- Today the chart sets `attributionLogo: false` (`web/src/components/stock/PriceChart.tsx:499`), and the app has no other credit.
- Fix in **M10**: add an About page with the NOTICE text and the link, and link to it from the app footer. The README gets the same credit. This does not wait for the release.

### Data-use compliance (release check, M16)
- Self-hosting means the project does not redistribute NSE data. It does not prove that no licence or permission is needed. NSE's website terms of use and data policies may restrict automated retrieval or certain uses.
- **Before release:** review the current NSE terms for each source the app uses (bhavcopy archives, and any endpoint reached through `nsemine`). Record the findings and the date in the release checklist.
- The README states that NSE's terms apply to each user's retrieval and use, that each user is responsible for following them, and that the project grants no data rights.
- If the terms forbid the app's retrieval method, the release waits until the provider strategy changes (ADR-003).

### Before the first public push (M16)
- Scan the full git history for secrets and data files.
- Add `.env.example` with safe defaults.
- Remove anything that must not be public.

## Consequences
- No central redistribution and no auth work for the release. Data-use compliance is a release check, not an assumption.
- A fresh install exposes nothing to the network. Users who opt in to LAN access do so knowingly.
- Users are responsible for their own use of the NSE data source.
- A developer who reached Postgres or Redis from another machine must use an SSH tunnel or a local override file.
- Any history rewrite to remove secrets must happen before the first public push.

## Alternatives considered
- **Hosted multi-user service:** rejected for now. It would redistribute data, which needs NSE permission, plus auth and operations.
- **Keep publishing all ports on all interfaces:** rejected. A no-login app on an open port lets anyone on the network change its state.
- **A shared-secret token instead of auth:** deferred. It adds setup friction for the local case and is still weaker than a real proxy for the remote case.
- **Closed source:** rejected. It does not meet the goal of an open project.

## Update, 2026-10-21 (R3-B-21)
Status stays Proposed. Implemented in code: loopback binding, the Host and Origin guard (421 and 403, one test per row of the request table), a 5 MiB request body cap (413, or 411 for a chunked write), and the rate limit with `Retry-After`. Not done, and owner decisions: the LICENSE and NOTICE files, name clearance, NSE and BSE terms.
