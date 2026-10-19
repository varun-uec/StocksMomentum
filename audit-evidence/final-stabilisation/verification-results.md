# Final stabilisation verification log

## Isolation

- Backend tests explicitly used `wickstreet_final_test` via `M25_DATABASE_URL`; the pytest fixture refuses database names without the `_test` suffix.
- Browser tests explicitly used marked databases via `E2E_DATABASE_URL`, including `wickstreet_nfr11_e2e`, `wickstreet_final_e2e`, and the fresh `wickstreet_guard_perf_e2e` used to remeasure the guarded live-screening path. Playwright passes that exact URL to the application as `M25_DATABASE_URL` and to the seed/cleanup helpers as `E2E_DATABASE_URL`.
- `web/e2e/db.py` checked the connected database name and `wickstreet_e2e_guard` marker before mutating synthetic fixtures. The database container was labeled `wickstreet.audit=final-stabilisation` and `wickstreet.data=synthetic-only`, and published only on `127.0.0.1:65440`.
- The shared application database and its volume were not connected to, changed, or used for cleanup. Direct exchange downloads were disabled; no NSE website downloads were triggered.

## Results

| Check | Result |
|---|---|
| Full backend pytest suite | 841 passed after the mixed-revision guard. Two existing deprecation warnings remain (Starlette test client and SQLAlchemy `DISTINCT ON`). |
| Focused corrected-data/provenance regression | 4 passed. |
| Focused mixed-revision correction regression | 1 passed; no result rows survived. |
| Focused failure/recovery integration | 4 passed, including terminated DB connection, actual application startup sweep, and completed-run immutability. |
| Backend Ruff | Passed. |
| Backend mypy | Passed: 262 source files. |
| Web Vitest | 101 passed across 13 files. |
| Web ESLint | Passed with zero warnings. |
| Web production build | Passed. Vite still reports a 566.07 kB raw main chunk. |
| Final accessibility browser suite | 2 passed; axe reported zero WCAG 2 A/AA violations on dashboard, chart, and Strategy Studio in both themes. |
| Initial complete performance / endurance browser suite | 3 passed: repeated API timings, Strategy Studio timings, and 24 chart/layout cycles. |
| Post-guard API performance regression | 1 passed: 30 searches, 30 workspace saves, 10 corrected-data screenings, 20 alert evaluations. |
| NFR-11 | 30 warm and 30 cold opens passed; see `nfr11.json`. |
| Database backup/restore and restart | `pg_restore --exit-on-error` succeeded, source/restore row counts matched, both remained consistent after PostgreSQL restart, and the application returned the restored latest screening run over HTTP; see `backup-restore.json`. |

The full backend run includes the optimistic revision guard and the mixed-revision rollback regression. The focused corrected-data file and recovery file were also run separately. The only measurement collected on an earlier source state is the Strategy Studio/chart soak: the later live-screening guard affects neither path. Search, save, screening, and alert timings were recaptured after the guard.
