# Wickstreet Comprehensive E2E Product Audit

**Audit date:** 2026-10-19

**Audited code:** local branch `wickstreet/m10-m11`, fixes at `e7fd455`

**Result:** core charting, workspace, Momentum25 web surfaces, alerts and Studio flows passed the exercised browser checks. **Wickstreet is not ready for public release.** Data-use permission, licence/name decisions and public-deployment security boundaries remain release gates. The exhaustive exit criteria in the request are not fully met: several long-tail paths and fault conditions are listed as not tested in the coverage matrix.

## Executive findings

- All 26 documented SPA routes, including the chart-grid diagnostic and not-found route, were opened in Chromium. Key workflows were additionally exercised with real browser input and API/database state.
- The audit caught and fixed three important backend/workflow correctness defects: legacy historical replays were not using one point-in-time view; walk-forward rebalance fills were priced at adjusted close instead of adjusted open; and `POST /runs` could return a permanently pending run. Fixes and regression coverage are in `e7fd455`.
- The full backend suite passed **815 tests**; strict mypy and Ruff passed. Web lint passed, Vitest passed **101 tests**, and the production build passed. Playwright passed **108 tests**, with six opt-in benchmark cases skipped in the full run; those six benchmark cases passed separately.
- NFR-11 passed comfortably: warm chart-open P95 **165 ms** and first chart open after fresh API process P95 **482 ms**, against 1 s and 3 s targets. The method and environment are recorded in `audit-evidence/benchmarks/nfr11.json`.
- Multi-chart panning stayed at 61–63 FPS in the measured runs. The 16-chart warm-open P95 was **1,772 ms** and JS heap samples peaked at **79 MB**. See `audit-evidence/benchmarks/m13-bench.json`.
- No confirmed P0 defect remains. The repaired P1 findings are closed with regression coverage. Remaining known issues are mostly non-critical, but the release boundary is not satisfied and some exhaustive test requests were not covered.

## Release assessment

| Area | Assessment | Evidence / limit |
|---|---|---|
| Core chart workflow | Pass | Symbol search, interval/range changes, chart types/scales, indicator examples, crosshair, pan/zoom and drawing interaction were exercised in Chromium. |
| Workspaces and persistence | Pass for exercised paths | 1/2/4/9/16 layouts, synchronization, reload/second-browser restore, conflict handling and split/bonus drawing alignment were exercised. Full arbitrary concurrent-edit stress was not run. |
| Momentum25 preservation | Route pass; workflow depth mixed | All legacy routes opened; dashboard ranking/filter/sort, explanation, stock analysis, Elliott Wave and watchlist flows were covered by route and targeted tests. Not every legacy report/export state was traversed. |
| Strategy Studio | Partial pass | Family lineage, bounded parameter edits, screening evaluation and the hold-out confirmation gate were tested. Full schema matrix, actual OOS exhaustion, failed evaluation recovery and all insufficient-data variants were not exhaustively run. |
| Alerts | Pass for create/fire/list lifecycle | 7 supported value kinds × 3 intervals, firing, one-shot/seen/rearm and delete were exercised. Corporate-action threshold adjustment and historical re-evaluation were not fully browser-verified. |
| Reliability | Partial pass | Injected delay, HTTP 503 and incomplete JSON; application restart; and isolated tmpfs database restart/bootstrap were tested. Durable volume recovery, database outage mid-write, all migration paths and corrupted-document permutations were not tested. |
| Performance | Pass for recorded targets | NFR-11 and 1/4/16-chart measures pass on the recorded synthetic dataset and machine. Strategy screening/evaluation, 10-year 4/9/16 chart combinations beyond the listed benchmarks, very large drawings, and memory soak were not benchmarked. |
| Security boundary | Pass within local deployment model | Anonymous loopback deployment, Host/Origin and CSRF checks pass. This is not a public or multi-user security assessment; there is no authentication. |
| Open-source release | **Blocked** | Project's 2026-10-19 data-use review identifies a conflict between automated NSE collection/simulation and the cited terms; licence ADR-015 is proposed, name clearance is incomplete, and public deployment has no auth. See [M16 data-use review](docs/history/audits/2026-10-19-m16-nse-data-use.md), [ADR-015](docs/architecture/adr/ADR-015-licence.md), and [security boundary](SECURITY.md). |

The data-use conclusion above reports the project’s documented review, not independent legal advice. The audit made no NSE automated downloads and generated only synthetic market fixtures.

## Verification record

| Check | Observed result |
|---|---|
| Backend | `815 passed, 2 warnings`; Ruff clean; strict mypy clean across 260 source files |
| Web | ESLint clean; 101 Vitest tests passed across 13 files; build passed (565.72 kB main JS, 182.13 kB gzip) |
| Browser suite | 108 passed, 6 opt-in benchmark tests skipped; six M13 benchmark cases then passed separately |
| Browser route crawl | 26 routes hard-loaded successfully; interactive coverage is separately described in [coverage matrix](E2E_COVERAGE_MATRIX.md) |
| Search stability | 20 consecutive fast open/type/close/reopen cases passed |
| Browser fault injection | 1,200 ms API delay, 503, and incomplete JSON cases passed |
| Disposable DB restart | tmpfs-only `wickstreet-audit-final-db` restarted empty; E2E guard, migrations, synthetic reseed and same-database browser check passed |
| API restart recovery | Each cold NFR-11 sample started a fresh API process; app and DB bootstrap were also checked after restart |
| Traces | [chart state restore](audit-evidence/traces/chart-state-restore.zip), [slow API response](audit-evidence/traces/api-slow-response.zip) |

The database was an explicitly configured, exact-name `*_e2e` target, verified by the harness before migration or fixture writes. It used Docker tmpfs with no persistent volume. No user or production database was reset, copied, seeded, or modified. The tmpfs restart test intentionally demonstrated that the disposable database loses state on restart; it is not evidence of a durable backup/restore procedure.

## Product-quality conclusion

An experienced TradingView user should recognize the chart mental model: terminal-style chart area, drawing rail, symbol search, intervals/ranges, indicator dialog, crosshair values, scale choices, synchronized chart grid and per-symbol drawings. The desktop core is coherent and the public-reference study followed the clean-room rule. Small-screen chart controls are crowded and wrap, the screener table still requires horizontal scrolling, and advanced Momentum25 pages live under **More**; the last two are discoverability/usability costs rather than broken routes. Detailed observations are in [UX usability audit](UX_USABILITY_AUDIT.md).

The implementation is credible for private, local evaluation with synthetic or properly licensed data. It should not be presented as a public NSE-data product or as evidence of profitable ranking: stored research results show negative qualified-set ranking IC, and the E2E data was synthetic. Release gates and remaining defect findings are recorded in [defect register](E2E_DEFECT_REGISTER.md).

## Evidence and related docs

- [Coverage matrix](E2E_COVERAGE_MATRIX.md)
- [UX usability audit](UX_USABILITY_AUDIT.md)
- [Defect register](E2E_DEFECT_REGISTER.md)
- [Evidence index](audit-evidence/README.md)
- [Benchmark JSON](audit-evidence/benchmarks/)
- [Rendered screenshots](audit-evidence/screenshots/)
