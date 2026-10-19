# Round 2 evidence index

This folder contains Round 2-only evidence. Screenshots and raw JSON use synthetic fixtures; logs show the isolated test runs. No real user database was reset or written, and automated NSE downloads were disabled.

## Isolation

- Browser app, seed helpers, and cleanup all used the same explicit database URL targeting database `wickstreet_r2_e2e` on container `wickstreet-r2-e2e-db`.
- Backend integration tests used the separate `wickstreet_r2_backend_test` database; the pytest fixture refuses database names that do not end in `_test` before truncating tables.
- Both databases ran in the Postgres container labelled `wickstreet.audit=round2`, bound to loopback port 65439, on named volume `wickstreet_r2_e2e_data`.
- Browser tests disabled the scheduler and direct exchange downloads. The restart test restarted only the container with that Round 2 label and confirmed workspace/drawing/alert state through a fresh API process.
- Redis was a separate `wickstreet-r2-e2e-redis` container on loopback port 16379.
- Synthetic symbols and test configuration are defined in `web/e2e/` and the R2 Playwright specs. No shared user database was copied or used as a test target.
- After test runs and evidence capture, both exact `wickstreet.audit=round2` containers and the named synthetic Postgres volume were removed. The evidence files remain; no application/user data was touched.

## Raw measurements and logs

| Artifact | Content |
|---|---|
| [`nfr11-r2.json`](nfr11-r2.json) | 30 warm + 30 cold single-chart runs, hardware, browser, data, p50/p95/max |
| [`m13-layout-benchmark-r2.json`](m13-layout-benchmark-r2.json) | 30 warm/cold runs each for 1/4/16 charts, panning and heap |
| [`stress-benchmark.json`](stress-benchmark.json) | Loaded 1/4/16 layouts with 7 indicators, 4 comparisons, 4 moving averages and 120 drawings per symbol; 8-cycle endurance samples |
| [`viewport-audit.json`](viewport-audit.json) | 26 routes × 4 widths × 2 themes, page/body widths and page heights |
| [`backend-pytest-r2-final.log`](backend-pytest-r2-final.log) | Final full backend suite: 833 passed, two warnings |
| [`backend-static-r2-final.log`](backend-static-r2-final.log) | Ruff clean and strict mypy clean across 261 source files |
| [`web-quality-r2-final.log`](web-quality-r2-final.log) | Final ESLint, Vitest (101), and production build output |
| [`playwright-regressions-r2-final.log`](playwright-regressions-r2-final.log) | 37 browser regressions spanning charting, layouts, Studio, alerts, and adversarial API/save cases |
| [`playwright-accessibility-r2-final.log`](playwright-accessibility-r2-final.log) | Reduced motion, keyboard focus/Escape, 200% equivalent viewport |
| [`playwright-stress-benchmark-r2-final.log`](playwright-stress-benchmark-r2-final.log) | Four loaded stress/endurance browser tests |
| [`playwright-viewport-audit-r2-final.log`](playwright-viewport-audit-r2-final.log) | Successful 208-state responsive sweep |
| [`playwright-viewport-audit-r2-initial-failure.log`](playwright-viewport-audit-r2-initial-failure.log) | Initial 768 px overflow before correction |
| [`playwright-db-restart-phase1-r2.log`](playwright-db-restart-phase1-r2.log), [`playwright-db-restart-phase2-r2.log`](playwright-db-restart-phase2-r2.log) | Browser state write and restore in separate runs around isolated PostgreSQL/API restart |
| [`playwright-trace-capture-r2.log`](playwright-trace-capture-r2.log) | Test run that generated the retained browser trace |
| [`trace-run-artifacts/r2-adversarial-R2-a-drawin-5146f-ys-local-and-can-be-retried-chromium/trace.zip`](trace-run-artifacts/r2-adversarial-R2-a-drawin-5146f-ys-local-and-can-be-retried-chromium/trace.zip) | Playwright trace for drawing edit, injected network failure, visible unsaved state, and retry |
| [`cli-screen-r2.log`](cli-screen-r2.log) | Reproduced duplicate screen insert / unique constraint failure before fix |
| [`cli-screen-r2-final.log`](cli-screen-r2-final.log) | Two real CLI invocations return the existing immutable run without a duplicate insert |

Screenshots include tablet/mobile route states, restart-before/restored, failed drawing save, reopened Studio result comparison, and the 200%-equivalent chart. There are 46 PNG files in this folder. Round 1 retains separate historical traces/screenshots in `audit-evidence/`; those are not represented here as newly captured R2 browser traces.

## Captured limitations

The loaded chart benchmark’s Long Tasks API result is empty; the browser did not provide a positive long-task observation, so this cannot establish that rendering had no stalls. The bounded endurance test ran eight cycles, not an overnight or multi-hour soak. Search/save/restore/screen/research/alert latency distributions were not captured. The actual browser zoom control, screen readers, and contrast ratios were not measured.
