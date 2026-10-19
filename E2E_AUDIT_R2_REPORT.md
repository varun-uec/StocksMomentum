# Wickstreet Comprehensive E2E Audit — Round 2

**Audit date:** 2026-10-19  
**Purpose:** independent adversarial follow-up to Round 1.  
**Audit result:** no known open P0/P1 defects remain in the tested scope after the Round 2 fixes. **Wickstreet is not certified technically release-ready**: several required fault, accessibility, data-reconciliation, and endurance cases remain untested or lack sufficient evidence. Public release readiness is a separate decision and remains blocked by data-use, licence, and name-clearance gates.

## Scope and method

Round 2 used the Round 1 reports as a gap list, inspected the application and test inventory, then exercised critical routes and stateful flows independently in Chromium and with synthetic backend fixtures. Route access and HTTP success were not treated as workflow proof. Every persistence claim below is backed by server/API/database assertions or a real restart.

The E2E app, seeder, and cleanup all received the same explicit database URL: `wickstreet_r2_e2e` on a dedicated Postgres container labelled `wickstreet.audit=round2`, bound to `127.0.0.1:65439`, with the named volume `wickstreet_r2_e2e_data`. Backend pytest used a different isolated `wickstreet_r2_backend_test` database on the same container. The alert concurrency test and screening snapshot retry test ran in the latter. The browser persistence test restarted only the labelled R2 Postgres container, waited for readiness, then started a new API process. No development/user database was reset or seeded. No automated NSE download was triggered; market data in the browser/performance fixtures was synthetic.

Machine: Apple M4 Pro, 14 CPU cores, 48 GB RAM, Darwin 27.0.0 arm64. Browser: Chromium 153.0.8010.12 headless. Detailed traces, logs, screenshots, and raw measurements are indexed in [`audit-evidence/r2/README.md`](audit-evidence/r2/README.md).

## Round 2 outcome

| Area | Result | Evidence and boundary |
|---|---|---|
| Routes and visual states | **Pass for tested render states** | All 26 Round 1 routes were rendered at 1440×900, 1920×1080, 768×1024, and 390×844 in light and dark themes: 208 measured page states, zero document-width overflow after the fix. This is not a visual review of every dynamic state at every size. |
| Chart and drawings | **Pass for specified lifecycle; edge geometry partial** | All 12 tools were drawn, selected, moved, edited/restyled, undone/redone, deleted/restored, saved, and reloaded. Chart types, ranges, scales, representative indicators, comparisons, monthly bars, sync, and layouts through 16 charts were re-exercised. Invalid geometry, off-range drags, all indicator parameter combinations, and concurrent drawing saves under network loss remain partial. |
| Strategy Studio | **Pass for key lifecycle and tested safeguards** | Create/configure/version/screen/reopen/compare; deterministic evaluation; insufficient-data refusal; matured one-shot holdout; restart/retry on the sealed snapshot. Close-but-not-identical hypotheses are not semantically clustered; broader family-renaming and exhausted-budget sequences were not run end-to-end. |
| Alerts | **Pass for sources, intervals, one-shot and concurrent response counting** | 7 supported sources × daily/weekly/monthly combinations, firing, acknowledgement, repeated checks, edits/deletion, bonus-adjusted threshold, and concurrent manual requests. Scheduled scheduler overlap was simulated as two concurrent API evaluations while the scheduler was disabled. Data correction after firing and restart mid-alert transaction were not tested. |
| Financial pipeline | **Pass for pinned invariants and named regressions; production data audit partial** | Backend golden fixtures cover exactly-once split/bonus adjustment, dividend non-adjustment, adjusted OHLCV/volume, chart parity, PIT as-of boundaries, manifests, and MCX/GOLDIAM cases. Round 2 did not independently access the prior research-copy database to rerun all stored-vs-PIT samples. |
| Persistence/recovery | **Pass for ordinary saves and full DB/API restart; failure matrix partial** | Workspace, drawing, and alert state survived named-volume Postgres restart and a new API process. Browser offline drawing edits remained visible and were retried successfully. Mid-write DB loss, failed migrations/partial imports, backup restore, and crashed-process transaction boundaries remain unverified. |
| Security boundary | **Pass within local loopback model** | Confirmed loopback binding; hostile Host and Origin rejection; JSON 404/405; malformed JSON no-write; `.env` path not served. This is not authentication, and syntactically malformed raw HTTP headers were not injected. |
| Performance | **NFR-11 passes; loaded behavior measured, wider NFRs partial** | 30 warm + 30 cold single-chart opens passed. Separate 30-run 1/4/16 benchmarks and loaded stress measurements are recorded below. Search, workspace save/restore, screening, research, and alert durations do not all have repeated percentile benchmarks. |
| Momentum25/CLI | **Existing routes preserved; commands no longer claim no-op success** | Full web and backend regression checks passed. `ingest` explicitly retires in favor of authorized imports. `screen` screens stored data and repeated calls reuse the exact immutable completed snapshot. Real CLI was invoked twice against the isolated E2E database; both returned the same stored run. |

## Reproduced defects and disposition

1. **Tablet navigation and layout overflow (P1, fixed).** At 768 px, the desktop navigation/search breakpoint persisted and forced every route to a 1120 px document width. The 208-state sweep reproduced it before the fix. The shell now switches to the mobile navigation at the `lg` breakpoint; long Strategy Studio labels and the diagnostic grid also wrap/scroll within the viewport. The post-fix sweep measured no root overflow at any requested size/theme.
2. **Concurrent alert response over-count (P2, fixed).** Two evaluators both read one active alert before either write. The database still transitioned it once, but both responses reported a new firing. A conditional active→triggered update now returns whether the state changed; only the winner reports `fired=1`. Deterministic regression forces both readers to overlap.
3. **Reduced-motion preference ignored (P2, fixed).** A browser with `prefers-reduced-motion: reduce` still computed smooth scrolling. A CSS media rule now disables smooth scrolling and collapses transitions/animations. Browser regression checks computed styles.
4. **Strategy comparison labels were not associated with their controls (P2, fixed).** The visible labels did not reliably name the comparison selects. IDs/`htmlFor` now bind labels to controls; the browser workflow locates them by accessible name.
5. **Repeated stored-data screening collided with immutable-run uniqueness (P2, fixed).** Running `momentum25 screen` after a completed run with the same `(strategy, run_date, data_version, config_hash)` attempted another insert and raised PostgreSQL `UniqueViolationError`. Round 2 captured the failure in `cli-screen-r2.log` and added a regression. The use case now returns the exact completed identity without changing its stored results; two real CLI invocations reused run 1. A same-date data correction is still indistinguishable from the same data version under the current date-based identity; see limitations.

No reproduced financial, silent-data-loss, test-isolation, or serious-security defect remained open at audit end. The prior Round 1 open P2 research-override helper, stale strategy/engine descriptions, large JavaScript bundle, and development-toolchain advisories remain. They are not promoted to P1 because this audit did not reproduce incorrect output from them, but the research-override path needs direct coverage before relying on that legacy workflow.

## Performance and endurance

NFR-11 used 10 synthetic symbols × 2,610 daily bars (2016-08-08 to 2026-08-07), 30 runs per case. A cold run starts a fresh API process and browser context; API boot is excluded after `/health/live` succeeds.

| Case | Runs | P50 | P95 | Max | Target |
|---|---:|---:|---:|---:|---:|
| Warm single chart | 30 | 181 ms | **184 ms** | 188 ms | P95 ≤ 1 s |
| Cold single chart | 30 | 491 ms | **506 ms** | 528 ms | P95 ≤ 3 s |

Separate 30-run 1/4/16 layout results: warm P95 185/495/1,772 ms; cold P95 201/528/1,785 ms; pan FPS P5 61 across all layouts; post-GC heap max 11/25/79 MB. A heavier configuration used 2,610 bars, seven indicators, four comparisons, four moving averages, and 120 drawings per symbol. One measured open took 1,244/1,136/2,348 ms for 1/4/16 charts; pan was 62 FPS; post-GC heap was 22.9/67.6/242.9 MB and chart canvases numbered 19/76/304. These are single samples, not P95 results or assigned acceptance limits.

The bounded endurance run repeated eight symbol changes, drawing create/delete, and 1×1↔2×2 layout changes. Sampled heap rose from 12.78 to 15.86 MB while returning to one chart (about 3.1 MB over this short run); canvas count returned to 7 each sample. This does not establish memory stability over hours or hundreds of cycles. The Long Tasks API produced an empty entry list; that is not proof that no rendering stalls occurred. Screening/research/alert and save/restore latency need instrumented repeated measurements before claiming performance coverage beyond chart open and pan.

## Verification summary

| Check | Round 2 result |
|---|---|
| Backend full pytest, isolated `*_test` database | **833 passed, 2 warnings** in 35.01 s |
| Backend Ruff and strict mypy | Clean; 261 source files |
| Web ESLint | Clean |
| Web Vitest | **101 passed**, 13 files |
| Production web build | Passed; main JS 565.81 kB raw / 182.14 kB gzip, with existing >500 kB chunk warning |
| Browser core regressions | **37 passed**: chart/drawing, ranges, indicators, layouts, Studio, alerts, API negatives/concurrency/recovery |
| Accessibility-focused Playwright | **3 passed**: reduced motion, keyboard More menu focus/Escape, 720×450 desktop-equivalent reflow |
| Stress/endurance Playwright | **4 passed**: 1/4/16 loaded charts plus bounded endurance |
| Route/theme/viewport sweep | **208 states**, zero root document-width overflows after fix |
| Persistence restart | **1 + 1 passed** on separate browser invocations before/after labelled PostgreSQL restart and fresh API process |
| Browser trace capture | **1 passed**, trace saved for failed drawing save and retry |
| CLI real repeat | Two stored-data invocations both returned run 1 without a duplicate insert |

## Round 1 comparison

Round 1 already opened all 26 routes at desktop and exercised all 12 drawing tools. It reported 815 backend tests and 108 Playwright tests, with six opt-in layout benchmark cases run separately. It called out incomplete tablet, accessibility, loaded-drawing, memory-soak, error recovery, and concurrent alert coverage. Round 2 kept the same 26 route inventory but measured 208 route/theme/viewport states, repeated critical workflows with database/API state assertions, added long-history loaded 1/4/16 stress, a bounded navigation soak, reduced-motion/keyboard checks, persistence across a real database restart, concurrent alert evaluation, and immutable evaluation retry coverage. The backend suite increased to 833 passing tests. Round 2 also found the repeated `screen` uniqueness collision and tablet overflow that were not established as fixed by Round 1 evidence.

## Release assessment

### Technical readiness

**Not certified release-ready from this audit.** The critical exercised financial invariants pass, all drawing tools pass the requested core lifecycle, core Studio and alert flows pass, the explicit isolated persistence/restart test passes, the NFR-11 targets pass, and no known open P0/P1 issue remains in the audited scope. Certification is withheld because mid-transaction database failure/recovery, backup restoration, complete concurrency/failure permutations, full screen-reader/contrast coverage, longer endurance, broad historical snapshot remeasurement, and repeated performance percentiles for search/save/screen/research/alerts remain incomplete. No technical pass is claimed for evidence that was not collected.

### Legal and public-release readiness

This is separate from technical quality. The project’s NSE data-use review/permission, final licence approval (ADR-015 remains proposed), Wickstreet name/trademark clearance, and publication permissions remain distinct release blockers. The no-login application is a local single-user tool bound to loopback; do not expose it to a network as a multi-user service without an authenticating proxy. This audit did not broaden the deployment model or add authentication.

See [`E2E_R2_COVERAGE_MATRIX.md`](E2E_R2_COVERAGE_MATRIX.md), [`E2E_R2_DEFECT_REGISTER.md`](E2E_R2_DEFECT_REGISTER.md), [`UX_AUDIT_R2.md`](UX_AUDIT_R2.md), and [`E2E_R2_FINANCIAL_CORRECTNESS.md`](E2E_R2_FINANCIAL_CORRECTNESS.md) for findings by area.
