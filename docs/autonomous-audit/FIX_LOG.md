# Fix Log

Append-only. One entry per fix.

---

### Fix for B1-001
- Files changed: `backend/src/momentum25/domain/indicators/pipeline_impl.py` (deleted), `backend/src/momentum25/domain/indicators/__init__.py`
- Root cause: M2 scaffolding. The real pipeline shipped as `IndicatorPipelineImpl` in `infrastructure/pipelines/indicator_pipeline.py`, but the domain-layer placeholder was never deleted.
- Fix: Deleted the placeholder module. Removed its import and `__all__` entry from the package `__init__.py`, and updated the module docstring. The domain package now exports only the `IndicatorPipeline` Protocol port. No touch to `pipeline.py` or to `IndicatorPipelineImpl`.
- Tests added/changed: None. Deletion-only change with zero callers; no behaviour to cover.
- Regression tests: Existing indicator suite (`-k indicator`, 40 tests) passes. Package import check confirms `momentum25.domain.indicators.__all__ == ['IndicatorPipeline']`.
- Build/static-analysis results: `make lint` (ruff) — all checks passed. `make typecheck` (mypy strict, 230 files) — success, no issues. `make test` — 533 passed, 104 errors, all errors are `asyncpg InvalidPasswordError: password authentication failed for user "momentum25"` at fixture setup (no database in this environment). Pre-existing and unrelated to this change.
- Verification result: `grep -rn "IndicatorPipelinePlaceholder" backend/src backend/tests` returns zero hits. Production wiring of `IndicatorPipelineImpl` is unchanged.
- Remaining limitations: DB-backed integration tests were not executed here. A run against a live Postgres is still needed for full confirmation, though no DB-touching code changed.

### Fix for B1-002
- Files changed: `docs/autonomous-audit/CAPABILITY_REGISTRY.md` (row 5, Technical Indicators)
- Root cause: The registry was built from a provisional file scan. It named the placeholder as the backend and put the indicator-series route under `securities.py`.
- Fix: Row 5 now names `infrastructure/pipelines/indicator_pipeline.py::IndicatorPipelineImpl` as the real implementation, notes that `domain/indicators/pipeline.py` holds only the Protocol port, and records the route as `GET /stocks/{symbol}/indicators/series` in `stocks.py` (with `/securities/{symbol}/ohlcv` and `/history` kept separate).
- Tests added/changed: None. Documentation only.
- Regression tests: Not applicable.
- Build/static-analysis results: Not applicable (Markdown).
- Verification result: Route location confirmed at `backend/src/momentum25/interface/api/routers/stocks.py:56-70`; `securities.py` exposes no indicator route.
- Remaining limitations: Other registry rows were not re-verified in this pass.

### Fix for B2-001
- Files changed: `backend/src/momentum25/domain/rules/` (whole package deleted: `base.py`, `registry.py`, `__init__.py`)
- Root cause: Early scaffolding for a per-rule-class dispatch design. The codebase settled on a per-engine `evaluators` dict keyed by `rule_id`, plus `domain/strategy/engine_registry.py` for engine-level dispatch. The scaffold was never removed.
- Fix: Deleted the package. `grep -rn "RuleRegistry|rule_registry|domain.rules"` over `backend/src` and `backend/tests` returned hits only inside the package's own three files, so nothing outside it imported `Rule`, `RuleRegistry`, or `rule_registry`. `domain/strategy/engine_registry.py` and all 8 factor engines are untouched.
- Tests added/changed: None. Deletion-only change with zero callers; no behaviour to cover.
- Regression tests: `pytest -k "relative_strength or rules"` — 9 passed.
- Build/static-analysis results: `make lint` (ruff) — all checks passed. `make typecheck` (mypy strict, 227 files) — success, no issues. Full `pytest` — 533 passed, 104 errors, all `asyncpg InvalidPasswordError` at fixture setup (no local Postgres). Pre-existing environment limitation, not a regression.
- Verification result: `momentum25.domain.rules` no longer exists and no module imports it. Rule dispatch in production is unchanged.
- Remaining limitations: DB-backed integration tests were not executed here. No DB-touching code changed.

### Fix for B2-002
- Files changed: `backend/src/momentum25/domain/engines/relative_strength.py`
- Root cause: Copy-paste of the `rs_sector_relative` call site when `rs_industry_relative` was added. `security.industry` was never substituted for `security.sector`.
- Fix: The call now passes `security.industry` to `_eval_rs_industry_relative`, and the helper's parameter is renamed `sector` -> `industry`. The parameter is not read in the helper body, so no explanation string, no `raw_value`, no threshold, no contribution and no pass/fail outcome changes. `industry_rs_percentile` computation is untouched.
- Tests added/changed: None. The change produces no observable output difference today; it corrects the wiring so a future use of the label reads the right field.
- Regression tests: `pytest -k "relative_strength or rules"` — 9 passed, covering the relative strength engine.
- Build/static-analysis results: `make lint` (ruff) — all checks passed. `make typecheck` (mypy strict, 227 files) — success, no issues. Full `pytest` — 533 passed, 104 pre-existing DB-connection errors.
- Verification result: No call site or test depended on the old argument. Engine scores and rankings are bit-identical.
- Remaining limitations: The `industry` parameter stays unused inside the helper. Surfacing the peer-group name in the no-peer-data explanation, mirroring the sector rule, would change user-visible explanation text and is left out of this fix.

### Fix for B3-001
- Files changed: `backend/src/momentum25/application/use_cases/walk_forward.py`, `backend/src/momentum25/interface/cli/main.py`, `backend/tests/unit/test_walk_forward.py`
- Root cause: The `start > end` guard existed only at the API router boundary. The CLI called `WalkForwardRunner.run` with no check, and `_first_session_of_each_month` filtered every session out, so a reversed range produced a valid-looking 0-rebalance, 0% return report.
- Fix: Moved the guard to the one place every caller routes through. `WalkForwardRunner.run` now raises `ValueError("start must be on or before end")` before any session work. The CLI `walk-forward` command converts that to `typer.BadParameter` (exit code 2). The API keeps its 422 pre-check, so its HTTP contract is unchanged. No backtest math, walk-forward mechanics, or look-ahead protections touched.
- Tests added/changed: Added `test_reversed_date_range_is_rejected` in `backend/tests/unit/test_walk_forward.py`.
- Regression tests: `pytest tests/unit/test_walk_forward.py tests/integration/test_backtest_api.py -q` — 15 passed (was 14; +1 new). Existing determinism, NAV-reconstruction and as-of enforcement tests still pass.
- Build/static-analysis results: `make lint` (ruff) — all checks passed. `make typecheck` (mypy strict, 227 files) — success.
- Verification result: A reversed range now fails loudly on both surfaces: API 422, CLI `BadParameter`. The single guard also covers any future caller that constructs a runner directly.
- Remaining limitations: On the CLI the guard fires after `build_walk_forward_runner` has loaded (empty) provider data, so it is not strictly fail-fast. Adding a second pre-DB check would duplicate the rule in three places; the DB work for a reversed range is an empty-range query. No CLI end-to-end test was added because the command requires a live Postgres connection, which is unavailable in this environment.

### Fix for B3-003
- Files changed: `web/src/app/historical/page.tsx`
- Root cause: `runsLoading` was destructured from the runs `useQuery` but never referenced in the render, so the "Available Historical Runs" card showed its empty state while the fetch was still in flight.
- Fix: Added a `runsLoading` branch ahead of the empty check: `{runsLoading ? <LoadingSpinner text="Loading runs…" /> : uniqueDates.length === 0 ? <EmptyState .../> : ...}`. Uses the existing shared `LoadingSpinner` and matches the rankings-query pattern already on the same page.
- Tests added/changed: None. No frontend test harness exists in `web/`; the change is a single render branch covered by the type check and production build.
- Regression tests: N/A (render-only change, no shared component or API contract touched).
- Build/static-analysis results: `npx tsc --noEmit` — clean. `npm run build` — succeeded, all routes emitted.
- Verification result: The loading state ("Loading runs…") is now visually distinct from the empty state ("No completed runs available to replay.").
- Remaining limitations: The runs query has no error branch; a failed fetch still falls through to the empty state. Out of scope for this finding.

### Fix for B5-001
- Files changed: `web/src/components/shared/NavBar.tsx`
- Root cause: The `/backtest` route was wired into `RESEARCH_TOOLS` after the icon set was drawn, so it reused `Icons.analytics`. "Analytics" and "Backtest" rendered the same glyph in the desktop dropdown and the mobile "More" sheet.
- Fix: Added one `Icons.backtest` entry to the existing icon set — a replay arc with a play triangle, same 20x20 viewBox and `currentColor` style as every other icon — and pointed the Backtest menu entry at it. "Analytics" keeps `Icons.analytics`. No new icon library or dependency. Every icon in `NAV_ITEMS`/`RESEARCH_TOOLS` is now unique.
- Tests added/changed: None. No frontend test harness exists in `web/`; the change is a static SVG constant and one property reference.
- Regression tests: N/A (presentational only, no logic, data or route change).
- Build/static-analysis results: `npx tsc --noEmit` — clean. `npm run lint` (next lint) — no warnings or errors. `npm run build` — succeeded, all routes emitted.
- Verification result: `Icons.analytics` is referenced once and `Icons.backtest` once; the two menu rows are now visually distinct.
- Remaining limitations: Verified from source and a production build, not from a rendered browser screenshot.

### Fix for B5-002
- Files changed: `web/src/lib/types.ts`
- Root cause: `trades` was stubbed as `unknown[]` because no UI consumed it, and the stub was never tightened when `TradeDTO` landed in `backend/src/momentum25/application/dto/walk_forward.py`.
- Fix: Added a `BacktestTrade` interface mirroring `TradeDTO` field for field (`security_id: number`, `side: string`, and `quantity`/`fill_price`/`notional`/`cost` as `string` because Pydantic serializes `Decimal` to a JSON string, `fill_date: string`). Changed `BacktestResponse.trades` to `BacktestTrade[]`. The string-for-Decimal choice matches `BacktestRebalance` directly above it in the same file (`total_cost`, `nav_pre_cost`).
- Tests added/changed: None. Type-only change with no runtime surface; the type check is the test.
- Regression tests: Grepped all of `web/src` for `trades` — the only reference is the type declaration itself. `web/src/lib/api-client.ts` returns `BacktestResponse` whole and never touches the field; `web/src/app/backtest/page.tsx` reads only `trade_count`. Nothing to break.
- Build/static-analysis results: `npx tsc --noEmit` — clean. `npm run lint` — no warnings or errors. `npm run build` — succeeded.
- Verification result: Frontend and backend contracts now agree on every field of `BacktestResponse`.
- Remaining limitations: The mirror is hand-maintained, so backend DTO edits can still drift silently — no generated client or contract test guards it. Not verified against a live response payload, since the backtest endpoint needs a live Postgres connection unavailable here.
