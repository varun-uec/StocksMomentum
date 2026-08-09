# Full Functional Audit — Momentum25 India

## Context

The app has grown across ~10 phases (screening → live lookup → watchlist →
market context → Elliott Wave → chart patterns → charting). Only the most
recent phases have been exercised; earlier features have not been re-verified
since. The goal is a whole-surface audit: run every feature against the real
dev database through the real API and a real browser, find defects, fix the
mechanical ones, and separately flag anything that touches scoring/ranking
methodology.

Three standing product constraints must be re-checked as part of this:
no target price / profit projection / R-multiple outside the explicitly
validated swing-target research module; no Buy/Sell verdict on indicators or
patterns; risk-only features (stop-loss) isolated from reward/target logic.

## Environment (already established, read-only)

- `conftest.py::_require_test_database` refuses any DB whose name does not end
  in `_test`. The audit will **not** run pytest DB fixtures against the dev
  database, and will use only read-only queries + read-only API calls against
  it. No `TRUNCATE`, no migrations, no ingestion scripts.
- Dev DB is the running container `momentum25-db-1`, published on **port 55432**
  (not the 5432 in `.env`). Contents are real: 3.07M `ohlcv_daily` rows, 3235
  securities, 13 strategies, but only **1** `screening_runs` row and 0 rows in
  `watchlist_items`, `corporate_actions`, `forward_returns`.
- Launch commands (both previously failed only on a stale relative `cd`):
  - API: `cd backend && M25_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:55432/momentum25 M25_STRATEGY_DIR=../docs/architecture/strategies .venv/bin/uvicorn momentum25.main:app --port 8000`
  - Web: `cd web && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1 npm run dev`

## Feature inventory (from routers + use cases, not from a prose list)

| Area | Endpoints | Frontend |
|---|---|---|
| Screening / trend template | `runs` (list/trigger/execute/latest/get), `rankings/runs/{id}`, `rankings/.../explain` | `/` dashboard, `MomentumTable`, `RunSummaryCards` |
| On-demand stock lookup | `stocks/{sym}`, `/live`, `/history`, `/indicators/series` | `/stock/[symbol]`, `MomentumView`, `WhyItRanks`, `RulePassMatrix` |
| Stop-loss (risk-only) | part of `/live` payload | `SuggestedStop` |
| Watchlist | `watchlist` GET/POST/DELETE | `/watchlist`, `WatchlistTable`, `WatchlistStar` |
| Elliott Wave | `stocks/{sym}/elliott-wave` | `/stock/[symbol]/elliott-wave` |
| Chart patterns | `POST stocks/{sym}/chart-patterns` | `PatternCard` |
| Charting / drawing tools | `securities/{sym}/ohlcv`, `stocks/{sym}/indicators/series` | `PriceChart`, `TechnicalWorkbench`, `chart-drawings.ts`, `chart-preferences.ts` |
| Market context | `market/context` | `/market`, `SectorStrengthTable`, `MarketBreadthPanel` |
| Strategies | `strategies`, `strategies/{name}` | `/strategies` |
| Validation | 6 endpoints incl. scorecard, alpha, rules, engines, experiment, dashboard | `/validation`, `/analytics` |
| Research | 7 endpoints incl. historical screen, determinism, contribution, compare | `/historical`, `/experiment` |
| Health / ops | `health`, `/live`, `/ready`, `/startup`, `/data-freshness`, `/metrics` | freshness badge |
| Learn | — | 6 static `/learn/*` pages |

## Preliminary findings — resolved (see `docs/audit-findings-2026-08-09.md`)

1. ~~`securities.py:34` — `from` param silently returns empty.~~ **Fixed.**
   `from`/`to` are honoured end to end (`?from=2020-01-01&to=2020-06-01` returns
   2020 bars).
2. ~~`securities.py` bypasses the application layer.~~ **Fixed.** The router now
   routes through `GetSecurityOHLCV` / `SearchSecurities`.
3. **`stocks.py` — private-attribute reach-through. Still stands, accepted debt.**
   `getattr(self._ohlcv_repo, "_session", None)` is not dead — it is the commit
   path, and it is used identically at 12 call sites across the application
   layer. Replacing it properly needs a unit-of-work port on the repository
   protocols; a local `hasattr` swap would move the reach-through, not remove
   it. Behaviour is correct today, so this is recorded as architectural debt
   rather than a defect. (The per-security commit in
   `RefreshCorporateActions` uses the same path and is load-bearing — see the
   data-loss note in that use case.)
4. ~~Inconsistent symbol normalization.~~ **Fixed.** `/stocks/reliance` →
   `"RELIANCE"` everywhere.
5. ~~`GetStockHistory` N+1.~~ **Fixed.** The use case now calls the already-existing
   `ScreeningRunRepository.score_history(strategy_id, security_id, limit)` — one
   indexed query, instead of listing every completed run and pulling up to
   10,000 rankings from each to find one security. `score_history` also filters
   to `COMPLETED` runs, preserving the previous semantics.

`legacy_ohlcv_daily_bak` (1,731,889 rows) is a pre-backfill snapshot;
`legacy_ohlcv_daily` is empty. Nothing in the codebase reads either table —
the only reference is a comment in `backend/scripts/reingest_history.py`
stating the re-ingest deliberately does *not* recover from the `_bak` table.
It is therefore unused by the application, but it is the only surviving copy of
the pre-backfill history, so **no table has been dropped**; removal is an
operator decision, not an engineering one.

Ruled out during the static pass, and re-checked live: frontend
`status=completed` vs backend `"COMPLETED"` is safe on the dashboard
(`screening_run.py:104` applies `.upper()`) but **was not** safe on
`/analytics`, which read `statusCounts['completed']` — fixed at the API-client
boundary. The `POST` verb on chart-patterns is deliberate and documented.

## Execution

1. Start API + web dev server; confirm `/health/ready` and `/health/data-freshness`.
2. **API sweep**: exercise every endpoint above with real symbols drawn from the
   dev DB, recording status, shape, and whether an empty result is honest or a
   masked error. Capture a transcript per feature.
3. **Browser sweep** (Playwright MCP): visit each page, exercise the interactive
   paths — watchlist add/remove, chart pane toggles and drawing tools, pattern
   detection trigger, Elliott Wave view, strategy/horizon switching — and record
   console errors and failed network requests.
4. **Constraint re-check across the interface layer**, not just domain: confirm
   no target/profit/R-multiple or Buy/Sell wording reaches the DTOs or the UI
   outside `swing_targets.py` / the research surface where it is validated.
5. **Fix all** non-methodology defects found (items 1–5, including the
   `securities.py` use-case extraction and the `_session` reach-through, plus
   whatever the sweeps surface), each with a focused test where the logic is
   non-trivial. Delivered as one commit-ready diff.
6. **Flag, do not change**: anything touching trend-template thresholds, RS
   rating, `risk_rr`, gate composition, or scoring weights — reported separately
   for sign-off.

### Dev-DB writes (approved)

Additive writes only — **no deletes of existing data, no truncation, no
migrations**:
- Watchlist add/remove to exercise CRUD (self-cleaning: remove what I add).
- Execute additional screening runs via `POST /runs/execute` so run-comparison,
  score history, contribution, and strategy-comparison endpoints have more than
  one run to work with. Existing run id stays untouched.

### Known coverage limits to report honestly

- `refresh=true` on `/stocks/{sym}/live` hits NSE live; it will be tested for
  graceful degradation only, not for successful fetch.
- `corporate_actions` and `forward_returns` are empty; endpoints depending on
  them will be reported as not verifiable rather than backfilled.

## Verification

- Every fix re-exercised through the same real API call and browser interaction
  that exposed it.
- `cd backend && ruff check src tests && mypy src` clean.
- `pytest` run only with `M25_DATABASE_URL` pointed at a `*_test` database, so
  the conftest guard is satisfied and the dev DB is untouched.

## Deliverable

A report organized by feature: verified working / broken and fixed / not
verifiable and why, with the methodology-touching items in a separate
sign-off section.
