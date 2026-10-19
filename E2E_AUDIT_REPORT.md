# Wickstreet Comprehensive E2E Product Audit

**Audit date:** 2026-10-19

**Audited code:** local branch `wickstreet/m10-m11`, fixes at `e7fd455`

**Result:** the audited flows passed, and the focused release-hardening pass closed the high-priority E2E gaps exercised below. **Wickstreet remains on publication hold** until the project licence and Wickstreet name/trademark decision are resolved. Direct NSE/BSE downloads are now off by default and not required for distribution. Any network-exposed app instance remains unauthenticated and is not secure without an authenticating proxy. Long-tail paths listed in the coverage matrix remain untested.

## Executive findings

- All 26 documented SPA routes, including the chart-grid diagnostic and not-found route, were opened in Chromium. Key workflows were additionally exercised with real browser input and API/database state.
- The audit caught and fixed three important backend/workflow correctness defects: legacy historical replays were not using one point-in-time view; walk-forward rebalance fills were priced at adjusted close instead of adjusted open; and `POST /runs` could return a permanently pending run. Fixes and regression coverage are in `e7fd455`.
- The full backend suite passed **815 tests**; strict mypy and Ruff passed. Web lint passed, Vitest passed **101 tests**, and the production build passed. Playwright passed **108 tests**, with six opt-in benchmark cases skipped in the full run; those six benchmark cases passed separately.
- NFR-11 passed comfortably: warm chart-open P95 **165 ms** and first chart open after fresh API process P95 **482 ms**, against 1 s and 3 s targets. The method and environment are recorded in `audit-evidence/benchmarks/nfr11.json`.
- Multi-chart panning stayed at 61–63 FPS in the measured runs. The 16-chart warm-open P95 was **1,772 ms** and JS heap samples peaked at **79 MB**. See `audit-evidence/benchmarks/m13-bench.json`.
- No unresolved P0/P1 defect was observed in the covered workflows after the focused pass. The repaired findings have regression coverage. Publication decisions and untested long-tail permutations remain as recorded below.

## Release assessment

| Area | Assessment | Evidence / limit |
|---|---|---|
| Core chart workflow | Pass | Symbol search, interval/range changes, chart types/scales, indicator examples, crosshair, pan/zoom and drawing interaction were exercised in Chromium. |
| Workspaces and persistence | Pass for exercised paths | 1/2/4/9/16 layouts, synchronization, reload/second-browser restore, conflict handling and split/bonus drawing alignment were exercised. Full arbitrary concurrent-edit stress was not run. |
| Momentum25 preservation | Route pass; workflow depth mixed | All legacy routes opened; dashboard ranking/filter/sort, explanation, stock analysis, Elliott Wave and watchlist flows were covered by route and targeted tests. Not every legacy report/export state was traversed. |
| Strategy Studio | Pass for focused failure/hold-out paths; broader matrix partial | Browser checks reject reconstructed hold-out provenance without creating an evaluation or spending the family window, and complete one matured hold-out once while preserving the “One evaluation is not validation” label. All parameter constraints and failed-worker permutations were not exhausted. |
| Alerts | Pass for create/fire/list and one bonus-adjusted threshold | 7 supported value kinds × 3 intervals, firing, one-shot/seen/rearm and delete were exercised. A close alert armed before a bonus retained its adjusted threshold; other historical re-evaluation date/action combinations were not exhaustively browser-verified. |
| Reliability | Pass for selected durable state; broader fault matrix partial | Injected delay, HTTP 503 and incomplete JSON; fresh app process; plus PostgreSQL restart on a new named volume with chart workspace, drawing and alert recovery were tested. DB outage mid-write, every migration path and corrupted-document permutations were not tested. |
| Performance | Pass for recorded targets | NFR-11 and 1/4/16-chart measures pass on the recorded synthetic dataset and machine. Strategy screening/evaluation, 10-year 4/9/16 chart combinations beyond the listed benchmarks, very large drawings, and memory soak were not benchmarked. |
| Security boundary | Pass within the loopback single-user model | Host/Origin and same-origin write checks are defense in depth, not authentication. The application has no login. A network-exposed instance is not secure without an authenticating proxy. |
| Open-source publication | **On hold for owner decisions** | Direct exchange downloads default off; supported CSV imports use operator-authorized data. ADR-015 remains proposed and Wickstreet name/trademark clearance is incomplete. No unauthenticated public hosted service is endorsed. See [data-use review](docs/history/audits/2026-10-19-m16-nse-data-use.md), [ADR-015](docs/architecture/adr/ADR-015-licence.md), and [security boundary](SECURITY.md). |

The linked data-use review records the project’s prior assessment; it is not independent legal advice. Neither the initial audit nor this hardening pass made an NSE automated download; all test market fixtures were synthetic.

## Verification record

| Check | Observed result |
|---|---|
| Backend | `815 passed, 2 warnings`; Ruff clean; strict mypy clean across 260 source files |
| Web | ESLint clean; 101 Vitest tests passed across 13 files; build passed (565.72 kB main JS, 182.13 kB gzip) |
| Browser suite | 108 passed, 6 opt-in benchmark tests skipped; six M13 benchmark cases then passed separately |
| Browser route crawl | 26 routes hard-loaded successfully; interactive coverage is separately described in [coverage matrix](E2E_COVERAGE_MATRIX.md) |
| Search stability | 20 consecutive fast open/type/close/reopen cases passed |
| Browser fault injection | 1,200 ms API delay, 503, and incomplete JSON cases passed |
| Disposable DB restart | Initial tmpfs bootstrap check passed. Focused follow-up restarted PostgreSQL with a newly created named volume and recovered browser workspace/drawing/alert state using a fresh API process; see `release-hardening-e2e-confirmed.log`. |
| API restart recovery | Each cold NFR-11 sample started a fresh API process; app and DB bootstrap were also checked after restart |
| Traces | [chart state restore](audit-evidence/traces/chart-state-restore.zip), [slow API response](audit-evidence/traces/api-slow-response.zip) |

The database was an explicitly configured, exact-name `*_e2e` target, verified by the harness before migration or fixture writes. It used Docker tmpfs with no persistent volume. No user or production database was reset, copied, seeded, or modified. The tmpfs restart test intentionally demonstrated that the disposable database loses state on restart; it is not evidence of a durable backup/restore procedure.

## Product-quality conclusion

An experienced TradingView user should recognize the chart mental model: terminal-style chart area, drawing rail, symbol search, intervals/ranges, indicator dialog, crosshair values, scale choices, synchronized chart grid and per-symbol drawings. The desktop core is coherent and the public-reference study followed the clean-room rule. Small-screen chart controls are crowded and wrap, the screener table still requires horizontal scrolling, and advanced Momentum25 pages live under **More**; the last two are discoverability/usability costs rather than broken routes. Detailed observations are in [UX usability audit](UX_USABILITY_AUDIT.md).

The implementation is credible for local single-user evaluation with synthetic or properly licensed data. Do not present the optional direct exchange adapter as authorized by default or the Momentum25 ranking as evidence of profitable returns: the observed historical qualified-set ranking IC is negative and E2E data is synthetic. The source publication hold is the unaccepted licence and name/trademark decision; hosting the no-login app on a network also requires an authenticating proxy. Remaining findings are in the [defect register](E2E_DEFECT_REGISTER.md).

## Focused release-hardening pass — 2026-10-19

This follow-up targeted the high-risk gaps from the accepted audit; it did not repeat route discovery or claim exhaustive coverage of every fault permutation.

| Check | Observed result |
|---|---|
| Drawing lifecycle | 12 of 12 tools passed draw, select, move, recolor, undo/redo, delete/restore and reload persistence in Chromium. |
| Strategy Studio | Reconstructed-input hold-out rejected before creating an evaluation or consuming the one-shot; one matured evaluation completed and retained the uncertainty label. |
| Corporate-action alert | Synthetic GOLDIAM bonus adjustment factor `0.75`, adjusted close `75`, threshold `90`; the alert stayed active without a false trigger. |
| DB and app restart | Workspace `1W`/`3M` settings, TCS horizontal drawing and active alert survived a PostgreSQL named-volume restart and a fresh API process. Both restart phases passed. |
| Market data | Direct downloads default off; refresh and forced-download API paths return `409` before unintended work. Authorized CSV import is documented and tested with synthetic EOD/action/benchmark fixtures. |
| Regression checks | 29 focused Playwright cases plus a post-fix Data-screen capture check; 9 focused backend unit tests; 6 focused backend integration tests; Ruff, strict mypy, web lint, 101 Vitest tests and production build passed. The full backend suite result remains the initial audit's 815 passed; it was not rerun in this focused pass. |
| Performance | NFR-11 was not rerun. The prior measured warm/cold P95 values remain 165/482 ms against ≤1 s/≤3 s. |

The final browser and API logs, isolation description and limits are in [release-hardening evidence](audit-evidence/benchmarks/release-hardening.md). The final route/workflow coverage updates are in [E2E coverage matrix](E2E_COVERAGE_MATRIX.md).

The default distribution no longer depends on automated NSE downloads. The optional NSE/BSE adapters remain disabled unless the operator confirms permission for the source and intended use. Public source publication remains on hold for the proposed licence and Wickstreet name/trademark decision. Authentication remains a deployment boundary: this is a loopback single-user app; any network-exposed instance is not secure without an authenticating proxy.

## Evidence and related docs

- [Coverage matrix](E2E_COVERAGE_MATRIX.md)
- [UX usability audit](UX_USABILITY_AUDIT.md)
- [Defect register](E2E_DEFECT_REGISTER.md)
- [Evidence index](audit-evidence/README.md)
- [Benchmark JSON](audit-evidence/benchmarks/)
- [Rendered screenshots](audit-evidence/screenshots/)
