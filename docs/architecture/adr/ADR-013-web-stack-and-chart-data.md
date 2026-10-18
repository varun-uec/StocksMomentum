# ADR-013: Web Stack, Chart Data Semantics and Workspace Persistence

**Status:** Proposed (draft, 2026-10-18). The web-stack part stays Proposed until the M10 spike passes. The data and workspace parts take effect in M11 once you approve them.

## Context
Wickstreet is a client-heavy workspace (ADD A1). Four facts from the code shape this decision:

1. **The web app is a SPA inside Next.js.** 53 of the 69 files in `web/src` are `"use client"`. The app uses only `next/link` (8 files), `next/navigation` (6) and `next/font/google` (1). It has no `next.config`, no middleware and no route handlers.
2. **The API URL is fixed at build time, and the setting is broken.** `web/src/lib/api-client.ts:22` reads `NEXT_PUBLIC_API_BASE`. But `docker-compose.yml:56` and `.env.example:35` set `NEXT_PUBLIC_API_BASE_URL`. The setting is silently ignored, so the client always uses `http://localhost:8000`.
3. **API types are handwritten** (`web/src/lib/types.ts`, 1,054 lines). ADR-008 requires a client generated from OpenAPI.
4. **No bar aggregation exists.** `1W` in `PriceChart.tsx:59` is a visible range of 7 days, not weekly bars. Chart state lives in browser `localStorage` (`chart-drawings.ts`, `chart-preferences.ts`, `overlay-preferences.ts`).

`next@14.2.0` is also in published advisory ranges. That needs patching under any option, so it is not a reason for this decision.

## Decision

### 1. Web stack
- **Vite + React 18 SPA**, with a client router. Routes are the same as today, plus `/chart/:symbol`.
- **Same-origin API.** The API container serves the built SPA as static files and falls back to `index.html` for client routes. Every request goes to the relative path `/api/v1`. No API URL exists at build time or run time. Note: Vite's `VITE_*` variables are also fixed at build time, so Vite alone does not solve this. Same origin does.
- **UI primitives:** Radix (menus, context menus, dialogs, popovers, tooltips) and `react-resizable-panels`. No docking library: the layout has fixed regions.
- **Generated types:** `openapi-typescript` generates them from the FastAPI schema. CI fails if the generated file drifts. This closes the ADR-008 gap.
- **Tests:** Vitest for units and Playwright for end-to-end tests. `scripts/indicator-selfcheck.ts` moves into Vitest.
- **Kept unchanged:** React 18, TanStack Query and Table, `lightweight-charts` 5, Recharts, Tailwind 3.

### 2. M10 spike: acceptance criteria
The web-stack part is accepted only if a spike on two routes (`/chart/:symbol` and the screener) meets every item below:

| # | Criterion |
|---|---|
| S1 | A deep link such as `/chart/RELIANCE` survives a hard reload and a new tab |
| S2 | `PriceChart` and the drawing primitive run unchanged |
| S3 | All requests use same-origin `/api/v1`, with no URL setting |
| S4 | Query cache and chart state survive navigation between routes |
| S5 | The API container serves the build; Compose loses the `web` service |
| S6 | Image size and start time are no worse than today (measured) |
| S7 | Smoke check: 16 charts mount, pan and unmount with no errors. This tests feasibility only. M13 sets the real performance targets. |

If S1 to S6 fail and cannot be fixed cheaply, take option B below.

### 3. Comparison

| | A. Vite SPA (proposed) | B. Keep Next, upgrade to a patched release |
|---|---|---|
| Same-origin API | Static files from the API container | Needs `next start` behind a proxy, or `output: 'export'` |
| Dynamic routes (`/stock/[symbol]`) | Native client routing | `export` cannot pre-render unknown symbols. Needs a proxy rewrite to a shell page, or `next start`. |
| Containers | db, api (+ redis) | db, api, web (+ redis) |
| Migration effort | About 14 routes; replace 15 Next imports | Version bump; fix the env name; add a proxy |
| Ongoing cost | Smaller surface; no server runtime to patch | Next major upgrades; Node server to patch |

### 4. Chart data semantics (backend domain)
- **The backend owns bars, intervals and alert-capable indicators.** The browser draws them.
- **Daily bars** use the same corporate-action-adjusted series that screening reads.
- **Weekly bars (M11b):** one bar per ISO week of NSE trading sessions, using the existing `TradingCalendar` port.
  - Open = first session's open, High = max high, Low = min low, Close = last session's close, Volume = sum.
  - The bar is dated at its last trading session.
  - A week with holidays still has one bar. A week with no sessions has no bar.
  - The current week has `partial: true` until its last session closes.
- **Weekly indicators are computed on weekly bars.** They are never resampled from daily indicator values.
- **`data_version`** is the hash of the manifest defined in ADR-014 §7. Every bar and series response carries it. The chart, alerts and explanations can then show that they used the same data.
  - Until the history tables exist (M14), the manifest holds the last ingested session, the latest ingest run and `INDICATOR_VERSION`. That is enough to prove chart and alert parity on one instance. It is not enough for historical replay, so no result before M14 claims it.
- **Indicator spec:** `(indicator_id, params, interval)`. The API serves a series for any spec in the server catalogue. Alerts (M15) store a spec, and the chart requests the same spec. One function computes both, so the chart and the alert cannot disagree.
- **API changes:** `GET /securities/{symbol}/ohlcv?interval=1D|1W` and `GET /stocks/{symbol}/indicators/series?interval=&spec=`. The defaults keep today's behaviour (NFR-13).

### 5. Workspace persistence
**Documents.** We store two kinds of JSON document, each versioned on its own:

| Document | Key | Holds |
|---|---|---|
| `workspace` | `workspace_id` | Name, layout grid, panel sizes, and the chart slots. Each chart has a stable `chart_id`, a symbol, an interval, a chart type, indicator specs, scale mode and sync flags. |
| `symbol_drawings` | `symbol` | Every drawing on that symbol. Each drawing has its own `drawing_id`. |

- **Drawings belong to the symbol.** They appear on every chart that shows that symbol, at any interval. **Presentation belongs to the chart.** Two charts of the same symbol can have different intervals and indicators but share drawings. M11 uses one workspace with one chart. M13 adds slots with no schema change.
- **Table:** `user_documents(kind, key, body JSONB, schema_version, revision BIGINT, tenant_id NULL, updated_at)`, primary key `(kind, key)`. It follows the watchlist pattern: a port in `domain/ports/repositories.py`, a repository, use cases and a router. Pydantic validates `body` at the boundary, with a size cap.
- **Schema evolution:** `schema_version` plus pure upgrade functions applied on read, with golden tests for each version.

**Concurrency (optimistic, standard HTTP):**

| Request | Server response |
|---|---|
| `GET /workspaces/{id}`, `GET /drawings/{symbol}` | `200` with `ETag: "<revision>"` |
| `PUT` with a matching `If-Match` | `200`, revision + 1, new `ETag` |
| `PUT` with a stale `If-Match` | `412 Precondition Failed`. The body holds the current document and its `ETag`. |
| `PUT` to an existing document with no `If-Match` | `428 Precondition Required` |
| `PUT` with `If-None-Match: *` (create only) | `201`, or `412` if the document exists |

**Conflict recovery (client).**
- Saves are debounced, with one save in flight per document.
- On `412`, the client loads the server document and shows "Changed in another window". The user picks **Keep theirs** (discard local edits) or **Apply mine** (re-apply the local edits on top of the new revision and save again).
- The client never overwrites silently.
- For `symbol_drawings`, the client merges by `drawing_id`, so edits to *different* drawings never conflict. Only a same-drawing edit asks the user.

**Migration from `localStorage` (one time, idempotent):**
1. On first load, if local chart state exists and no import marker is set, the client sends `PUT` with `If-None-Match: *`.
2. On `201`, it sets the marker. It keeps the local data under a backup key for one release, then removes it.
3. On `412`, the document already exists, so the server wins. The client keeps the local backup and sets the marker. It tells the user once that a local copy was kept.
4. Running the migration again, or from a second browser, changes nothing.

## Consequences
- One authority per number: the browser draws bars and indicators but never computes an alert-capable value.
- A self-hosted user never configures an API URL, which removes a class of setup failures.
- One persistence model covers workspaces, drawings and later layouts. M13 multi-chart needs no redesign.
- New backend work: interval aggregation, indicator specs, `user_documents` and five endpoints.
- If the spike fails, sections 4 and 5 still apply under Next.js.

## Alternatives considered
- **Keep Next.js unchanged:** rejected. The broken env setting and build-time URL break self-hosting.
- **Browser-side indicators for everything:** rejected. The chart and alerts would use two implementations that can disagree.
- **Per-symbol chart state only:** rejected. It cannot show one symbol in two panels with different settings.
- **Last-writer-wins saves:** rejected. A second browser silently destroys work.
- **A docking-layout library:** rejected. The layout has fixed regions.
