# E2E Audit Evidence

Evidence for the 2026-10-19 Wickstreet product audit, run against code revision `e7fd455`.

## Data and safety

- Full-suite and trace application/API URL was explicitly set to `postgresql+asyncpg://audit:…@127.0.0.1:60560/wickstreet_final_e2e`.
- The clean Studio screenshot used a second empty target, `wickstreet_visual_e2e`, in the same disposable tmpfs container. It was independently marker-verified and migrated; it contains synthetic price fixtures but no Studio families.
- The harness rejected unapproved database names, verified the exact `_e2e` name and safety marker before migrations/fixture writes, and used the same database for app requests and cleanup.
- Postgres ran as `wickstreet-audit-final-db` on Docker tmpfs with no persistent volume. A restart intentionally erased that disposable database; the guard, schema, fixtures and same-database browser check were then restored.
- Market data is synthetic. No NSE automated download or real database mutation was performed.

## Artifacts

### Screenshots

[`screenshots/`](screenshots/) contains 42 Chromium captures: every documented SPA route at desktop width, plus chart search, indicators, alerts, 4×4 grid, light/dark states, dashboard and Studio mobile views, API failure/loading states, and the post-fix mobile navigation/table states. Studio desktop/mobile empty states were captured on the separate clean synthetic database so retained strategy-family test records do not appear as product content. The browser viewport was set explicitly in the test. Captures are rendered product states that were visually inspected; they are not golden-image diffs.

### Traces

- [`traces/chart-state-restore.zip`](traces/chart-state-restore.zip) — browser reload and second-browser workspace restore.
- [`traces/api-slow-response.zip`](traces/api-slow-response.zip) — delayed market API loading, then success.

Both traces were recorded with Playwright tracing enabled on the isolated E2E target and both tests passed.

### Benchmarks

- [`benchmarks/nfr11.json`](benchmarks/nfr11.json) — 30 warm opens and 30 cold opens, each cold sample after a fresh API process.
- [`benchmarks/m13-bench.json`](benchmarks/m13-bench.json) — 1/4/16 chart performance, 30 samples per open case, pan FPS and heap observations.
- [`benchmarks/api-resilience.json`](benchmarks/api-resilience.json) — injected delay and observed render time.
- [`benchmarks/e2e-suite-summary.json`](benchmarks/e2e-suite-summary.json) — final backend, web and browser-suite totals and restart/fault summaries.

Warm/cold methods are recorded in each JSON. NFR-11 cold starts chart navigation after the fresh API answers its health check (boot time excluded). M13 cold means a fresh browser context against the already-running API. Performance measurements use synthetic histories and are local to the listed Mac/Chromium environment.

## Interpreting the evidence

The screenshots and trace archive are examples of rendered states and interactions, not exhaustive coverage of all possible user input. The [coverage matrix](../E2E_COVERAGE_MATRIX.md) describes tested and untested states. The [defect register](../E2E_DEFECT_REGISTER.md) links the repaired issues to regression tests. Synthetic history validates application behavior and performance under a controlled workload; it does not validate data-vendor correctness, investment results, production-scale reliability or public security.
