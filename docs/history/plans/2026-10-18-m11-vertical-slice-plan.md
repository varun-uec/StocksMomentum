# M11 Vertical Slice — Find → Analyse → Draw → Restore

> **Status:** Proposed, under review, 2026-10-18. It assumes M10 is done (the SPA served same-origin). Persistence follows ADR-013 §5.

## Goal
A TradingView user opens Wickstreet and does these four things without help:
1. Finds an NSE stock.
2. Reads its daily chart with indicators.
3. Draws on it.
4. Closes the browser, comes back (in the same browser or another one) and finds everything as they left it.

This is the first major review gate. It proves the foundation, not the feature count.

## User flow

| Step | What the user does | What the system does |
|---|---|---|
| Find | Starts typing anywhere on the chart, or presses `/` | The search dialog opens with the typed text. `GET /securities?q=&limit=10`. Arrow keys and Enter pick a result. The URL changes to `/chart/RELIANCE`. |
| Analyse | Reads candles, adds an MA, adds RSI | Bars come from `GET /securities/{symbol}/ohlcv`. RSI and MACD panes use server series (`/stocks/{symbol}/indicators/series`). MAs come from the existing browser catalogue (display-only, NFR-1a). The crosshair legend shows OHLC and the indicator values. |
| Draw | Picks a trendline, draws, selects it, drags it, deletes another | The existing 4 tools plus **select, move and delete**. Delete and Backspace remove the selected drawing. Esc cancels. |
| Restore | Reloads, or opens the URL in another browser | Workspace and drawings load from the server. The chart reopens on the same symbol, indicators and drawings. |

## Design: reuse first

What exists, and how the slice uses it:

| Existing | Use in the slice |
|---|---|
| `PriceChart.tsx` (1,050 lines) | Mount unchanged. Pull workspace state *out* of it. No new state goes in. |
| `useChartShell.ts` | Already the single place that wires bars, panes and preferences per symbol. It stays the seam. |
| `chart-drawings.ts` | Add hit-testing and a selected state to the existing primitive. The drawing model is already plain JSON with a stable `id`. |
| `chart-preferences.ts` / `overlay-preferences.ts` | **Keep their hook APIs and swap the backing store.** Today both write `localStorage`. After the slice, they read and write server documents. Callers do not change. |
| `api-client.ts` / generated types (M10) | Add four calls. |
| Watchlist backend pattern (`0007_watchlist`) | Copy its layering for `user_documents`. |

**The split of today's `ChartPreferences` (one blob per symbol):**
- `drawings` → the `symbol_drawings` document for that symbol.
- `timeframe` (a visible range), `activeMas`, `activePanes` and the overlay list → the chart entry (`chart_id`) inside the `workspace` document.

**One new web primitive: `useServerDocument(kind, key)`.** It owns `ETag`, debounced saves (one in flight), `412` recovery and the conflict notice. Both preference hooks use it. Nothing else talks to the documents API directly.

## Proposed changes

### Backend
- `migrations/versions/0014_user_documents.py`: the `user_documents` table (ADR-013 §5).
- `persistence/models.py`: `UserDocumentModel`.
- `domain/ports/repositories.py`: a `UserDocumentRepository` port with `get` and `put(expected_revision | create_only)`, plus a `RevisionMismatch` error.
- `persistence/repositories/user_documents.py`: one conditional `UPDATE … WHERE revision = :expected` (atomic, no read-then-write race), plus `INSERT … ON CONFLICT DO NOTHING` for create-only.
- `application/dto/workspace.py`: Pydantic `WorkspaceBodyV1` and `SymbolDrawingsBodyV1`, with a size cap.
- `application/use_cases/user_documents.py`: get and put, plus `schema_version` upgrades on read.
- `interface/api/routers/workspace.py`: `GET/PUT /workspaces/{workspace_id}` and `GET/PUT /drawings/{symbol}`, with `ETag`, `If-Match`, `If-None-Match`, `412` and `428`.

### Web
- `lib/server-document.ts`: `useServerDocument`.
- `lib/chart-preferences.ts` and `lib/overlay-preferences.ts`: swap the backing store and split as above.
- `lib/local-import.ts`: the one-time idempotent import (ADR-013 §5).
- `components/workspace/SymbolSearch.tsx` and `ConflictNotice.tsx`.
- `components/stock/chart-drawings.ts` and `PriceChart.tsx`: select, move and delete.
- Route `/chart/:symbol`, which uses `useChartShell`.

## Tests

| Layer | Test |
|---|---|
| Backend unit | Conditional put: match → revision + 1; mismatch → `RevisionMismatch`; create-only twice → one row |
| Backend unit | Schema upgrade golden test for v1 |
| API contract | `200` + `ETag`; `412` with the current body; `428` without `If-Match`; `201` / `412` on `If-None-Match: *`; size cap → `422` |
| Web unit (Vitest) | Preferences round-trip; split and merge of the old blob; drawing hit-test and move geometry; merge of drawings by `drawing_id` |
| E2E (Playwright) | **Happy path:** search → open → add MA and RSI → draw 2 → move 1 → delete 1 → reload → state intact |
| E2E | **Second browser:** a fresh context opens the URL → same state |
| E2E | **Conflict:** two contexts edit the *same* drawing → the second save shows the notice, and no data is lost. Edits to *different* drawings → both kept. |
| E2E | **Migration:** seed `localStorage` with old preferences → first load imports them → a reload imports nothing more → a second seeded context keeps the server state and its local backup |
| Regression | The full backend suite, the indicator self-check and every existing route load |

## Acceptance (review gate)
- Every test above passes.
- **Measured to NFR-11:** warm open P95 ≤ 1 s, cold open P95 ≤ 3 s (provisional), with at least 30 runs per case across at least 10 symbols. The report records the hardware, OS, browser, dataset date and commit. A Playwright script makes the measurement repeatable. The time to the first search result is also reported.
- No console errors or warnings on the slice routes.
- Light and dark themes both work. The attribution link is visible (from M10).
- You run the flow yourself and judge whether it feels professional. This is the real gate.

## Not in M11
Weekly bars (M11b), more drawing tools, toolbars beyond what the flow needs, the watchlist panel, multi-chart, alerts, Strategy Studio and renaming routes other than adding `/chart/:symbol`.

## Risks
- **`PriceChart` size.** Adding select and move to a 1,050-line component risks regressions. Mitigation: hit-testing lives in `chart-drawings.ts`, and `PriceChart` only forwards pointer events.
- **The visible range is not an interval.** Today `1W` and `1M` are ranges. The slice keeps ranges and labels them as such. M11b adds a separate interval control, so the two never share a button.
