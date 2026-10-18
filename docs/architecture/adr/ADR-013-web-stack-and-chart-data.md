# ADR-013: Web Stack, Chart Data Semantics and Workspace Persistence

**Status:** Accepted (2026-10-18). The owner accepted the [M10 spike evidence](../../history/audits/2026-10-18-m10-stack-spike-report.md) (S1–S7 pass) and approved Vite 7 + React. §4 and §5 were revised during M11 to match what was built; the changes are marked *(M11)*.

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
- **Daily bars** use the same corporate-action-adjusted series that screening reads. *(M11)* `GET /securities/{symbol}/ohlcv` applies the stored `adj_factor` the same way the indicator pipeline does: price × factor, volume ÷ factor. A split no longer shows as a price jump on the chart. The response also carries `adjustments`, the factor of every date in the stored history, for drawings (§5).
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
- *(M11b, as built)*
  - Weekly bars aggregate the **adjusted** daily bars. Raw prints never enter a weekly bar, so a week with a split or bonus has no jump inside it. The domain function refuses unadjusted input.
  - `partial` is true when the calendar has a session in the bar's week after the bar's last session. It depends only on the data and the calendar, never on the clock, so it is deterministic. It covers the running week, and also a week the security stopped trading in.
  - `data_version`: no ingest-run record exists, so the interim manifest is a content hash of the inputs. It hashes every stored bar of the symbol (raw prices, volume and `adj_factor`) plus `INDICATOR_VERSION`, and the response carries its first 12 hex characters. A new session, a corrected print or a refreshed factor each give a new version. The price series and the indicator series of one symbol carry the same version when they use the same data. ADR-014's manifest replaces it in M14.
  - Daily indicator series keep the snapshot's own bar window, so their last value still equals `/stocks/{symbol}/live`. Weekly series run the same functions on weekly bars built from the whole history.
  - The interval is saved per chart (`ChartV1.interval`, default `1D`). Only the chart workspace offers the switch. The research screens mark daily signals, so they stay daily.
  - On weekly bars, a drawing point shows on the bar of its ISO week. It keeps its saved date and price until the owner moves it.
  - `spec=` is not built yet. M13's indicator dialog and M15's alerts need it; M11b serves the four existing panes.
- *(M13, as built)* **Monthly bars** (`interval=1M`): one bar per calendar month of sessions, with the same rules as weekly bars. One domain function, `period_bars`, builds both. Monthly indicators run on monthly bars. `partial` marks the running month. On monthly bars a drawing point shows on the bar of its month.
- *(M13, as built)* The indicator dialog serves the browser catalogue, which is display-only (NFR-1a), so it still needs no `spec=`. M15's alerts add it.

### 5. Workspace persistence
**Documents.** We store two kinds of JSON document, each versioned on its own:

| Document | Key | Holds |
|---|---|---|
| `workspace` | `workspace_id` | Name, layout grid, panel sizes, and the chart slots. Each chart has a stable `chart_id`, a symbol, an interval, a chart type, indicator specs, scale mode and sync flags. |
| `symbol_drawings` | `symbol` | Every drawing on that symbol. Each drawing has its own `drawing_id`. |

- **Drawings belong to the symbol.** They appear on every chart that shows that symbol, at any interval. **Presentation belongs to the chart.** Two charts of the same symbol can have different intervals and indicators but share drawings. M11 uses one workspace with one chart. M13 adds slots with no schema change.
- *(M11)* **Drawing prices are traded prices:** the price as printed on each point's date, not adjusted. Stored prints never change, but factors do: every new split or bonus rescales all earlier bars. The chart converts each point with the factor of its date, from the `adjustments` schedule that `GET /securities/{symbol}/ohlcv` returns for the whole history. A drawing therefore stays on its bars after any corporate action. Drawings made before M11, on the raw chart, were already in this basis, so none needed migrating. A point dated after the last bar takes the latest factor. The document records the basis as `price_basis: "traded"`, and the server rejects any other value. Adjustment happens only when the chart draws.
- *(M13)* Each drawing also holds a line `width` (1 to 4) and, for a text note, its `text`. The server fills the defaults (2, null), and the client writes them out too. Merges compare JSON with keys sorted, so the server's key order can never make an untouched drawing look edited.
- *(M13)* A chart also holds `compare`: up to 4 symbols drawn as lines on it. Each line is rebased to the chart symbol's close at the first bar both have, so it shows relative performance from there. Both series are adjusted.
- *(M13)* **Layouts.** The workspace holds `layout` (`1x1`, `2x1`, `1x2`, `2x2`, `3x3` or `4x4`, columns × rows) and `sync` (`symbol`, `interval`, `crosshair`). Grid slot *i* is chart `main` for the first slot, else `c{i+1}`, so a slot keeps its settings when the grid changes size. Sync flags belong to the layout, not to each chart: the owner syncs a grid, not a pair of charts. Synced values are applied when drawing; each chart keeps its own saved symbol and interval, so turning sync off restores them. The active chart is the route's symbol. Any chart update marks its chart active, including the research screens', so an active id outside the grid means `main`. The crosshair is shared through an in-memory bus, never through saved state.
- *(M12)* The workspace also holds `right_panel`: the side panel's open tab (`watchlist` or `details`) or none. Every top-level field merges like a chart setting; only `active_chart_id` follows the newest window.
- **Table:** `user_documents(kind, key, body JSONB, schema_version, revision BIGINT, tenant_id NULL, updated_at)`, primary key `(kind, key)`. It follows the watchlist pattern: a port in `domain/ports/repositories.py`, a repository, use cases and a router. Pydantic validates `body` at the boundary, with a size cap.
- **Schema evolution:** `schema_version` plus pure upgrade functions applied on read, with golden tests for each version. *(M11)* Only version 1 exists, so no upgrade function exists yet; the first v2 adds one.

**Concurrency (optimistic, standard HTTP):**

| Request | Server response |
|---|---|
| `GET /workspaces/{id}`, `GET /drawings/{symbol}` | `200` with `ETag: "<revision>"` |
| `PUT` with a matching `If-Match` | `200`, revision + 1, new `ETag` |
| `PUT` with a stale `If-Match` | `412 Precondition Failed`. The body holds the current document and its `ETag`. |
| `PUT` with neither `If-Match` nor `If-None-Match` | `428 Precondition Required` *(M11: for a missing document too, so every save states its intent)* |
| `PUT` with `If-None-Match: *` (create only) | `201`, or `412` if the document exists |

**Conflict recovery (client).** *(M11: as built in `web/src/lib/server-document.ts` and `merge.ts`)*
- One store per document, shared by every component that shows it. Saves are debounced (400 ms), one is in flight at a time, and unsaved edits are sent with `keepalive` when the page is left.
- On `412`, the client does a three-way merge of its last-seen version, its current version and the server's, then saves again:
  - **`symbol_drawings`:** merged by `drawing_id`. Edits to different drawings both survive with no notice. When both windows changed the *same* drawing differently, the client shows "Changed in another window" and the user picks **Keep theirs** or **Apply mine**.
  - **`workspace`:** merged chart by chart and field by field. A field only one window changed takes that window's value. When both windows changed the *same* field differently, the client shows the same notice for "Your chart settings" and the user picks a side. A chart that did not exist yet merges against the default chart.
  - **Navigation fields** (`symbol`, the open symbol of a chart, and `active_chart_id`) record where the owner is, not what they set. For those the newest window wins without a notice.
  - While a document waits for a choice, edits to it are held back, and the notice shows on every screen, not only the chart workspace.
- The client never overwrites silently.

**Migration from `localStorage` (one time, idempotent):**
1. On start, for each `chart-prefs:<symbol>` key with no import marker, the client sends the symbol's drawings with `If-None-Match: *`.
2. On `201`, it sets the marker. On `412`, the document already exists, so the server wins, and it sets the marker too. A failed request is retried on the next start.
3. The original keys stay in place as the backup for one release.
4. Running the migration again, or from a second browser, changes nothing.

*(M11)* Chart settings are imported too, in one pass marked `wickstreet:imported:presentation`. They were stored per symbol (`chart-prefs:<symbol>` and the analysis screen's `chart-overlays:<symbol>`) and now belong to a chart. Each chart takes the setting the owner chose on the most symbols; symbols left at the defaults do not count, and a tie goes to the first in JSON order. Range, moving averages and panes go to the `main`, `stock`, `analysis` and `elliott-wave` charts; indicators and the signal preset go to `analysis` only. The import only adds charts the server does not have, so the server copy wins. The one-time "a local copy was kept" message was not built.

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
