# Wickstreet — Final Engineering Readiness

**Date:** 2026-10-19  
**Scope:** Focused final stabilisation after the accepted Round 2 audit. No broad re-audit, real-data import, or NSE download was performed.

## Assessment

**Conditional technical readiness for single-user, local analysis.** The corrected-data, snapshot immutability, screening recovery, backup/restore, accessibility, and NFR-11 checks passed in the isolated synthetic environment. No known P0 or P1 defect remains in the exercised scope.

This is not an unconditional professional-research sign-off: the historical research corpus used by the earlier reconciliation is unavailable in an isolated copy, so its stored-versus-current results remain unresolved. Freshly generated runs are traceable and repeatable; conclusions in legacy reports should not be treated as revalidated by this pass. Legal and publication readiness also remains blocked as listed below.

## Verified invariants

### Corrected market data and immutable runs

- A correction to the latest bar on the same session advances the committed input revision and creates a new manifest and screening run, even though `run_date` is unchanged.
- The run stores the full manifest body, its `data_version`, and the strategy configuration hash. The corrected row’s `recorded` provenance is preserved and its revision is covered by the run manifest.
- Latest-run selection returns the corrected run. Repeating execution with identical data and configuration returns that same run and does not duplicate screening-result rows.
- A market-data revision that commits during scoring is detected before result persistence. The mixed-revision run fails with a retry message and leaves no scores, rule results, or universe memberships; a subsequent execution can use the new manifest.
- The earlier completed snapshot’s identity and stats remain unchanged. Repository updates now reject mutation of a completed screening snapshot.
- An aborted versioned write can consume a PostgreSQL sequence value, but it no longer changes the committed data revision or manifest. The revision is derived from committed current/history rows and indexed for lookup.
- The Playwright API benchmark repeated ten same-session synthetic corrections; all ten produced distinct run IDs and data versions, and `/runs/latest` selected the last run.

Evidence: the corrected-data and manifest regressions are in [test_execute_screening_incremental.py](/Users/varunagarwal/Downloads/Applications/StocksMomentum/backend/tests/integration/test_execute_screening_incremental.py), [test_point_in_time.py](/Users/varunagarwal/Downloads/Applications/StocksMomentum/backend/tests/integration/test_point_in_time.py), [test_universe_admission.py](/Users/varunagarwal/Downloads/Applications/StocksMomentum/backend/tests/integration/test_universe_admission.py), [performance.json](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/performance.json), and [verification-results.md](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/verification-results.md).

### Failure recovery and backup

- A screening run’s `RUNNING` lifecycle is committed before result computation. Score, rule-result, universe-membership, and `COMPLETED` writes then share one transaction. A late injected failure rolled those result rows back and persisted an explicit `FAILED` run.
- A test terminated the isolated PostgreSQL backend after a security row was flushed but before commit. Commit failed, and a fresh session confirmed the row did not survive.
- On actual FastAPI lifespan startup, unfinished `PENDING`/`RUNNING` screening rows became `FAILED` with a restart reason. A second recovery sweep was idempotent; a completed snapshot and its stats remained intact.
- A custom-format backup of the marked synthetic E2E database restored successfully into a separate empty database. Migration version and counts matched across securities, bars, manifests, screening runs/results, rule results, memberships, Strategy Studio families/evaluations, alerts, and documents. Both databases retained the same counts after the isolated PostgreSQL container restart, and a fresh Wickstreet application startup read the restored latest screening run over HTTP (200, `COMPLETED`).

Evidence: [test_screening_recovery.py](/Users/varunagarwal/Downloads/Applications/StocksMomentum/backend/tests/integration/test_screening_recovery.py) and [backup-restore.json](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/backup-restore.json). The dump was synthetic-only and its checksum is recorded; the temporary dump was not added to the repository.

### Accessibility

- axe-core reported zero WCAG 2 A/AA violations on the dashboard, chart, and Strategy Studio in light and dark themes.
- Keyboard checks exercised drawing-tool activation, accessible names and pressed state, the shortcuts dialog, Escape closure, focus return to the chart, and the focused Close button’s visible ring.
- The checks found and fixed text contrast failures in secondary labels, chart controls, the price-change metric, and indicator labels. The shortcuts dialog initially had no visible focus indicator; it now uses the shared focus treatment.

Evidence: [accessibility-axe.json](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/accessibility-axe.json) and [final-accessibility.spec.ts](/Users/varunagarwal/Downloads/Applications/StocksMomentum/web/e2e/final-accessibility.spec.ts).

## Performance and endurance

Environment: Apple M4 Pro, 14 CPU cores, 48 GB RAM; Darwin 27.0; Chromium 153.0.8010.12 headless. API and browser measurements used loopback and an isolated synthetic database. Chart histories contained 2,610 daily bars per symbol (2016-08-08 through 2026-08-07).

| Measurement | Samples | P50 | P95 | Max |
|---|---:|---:|---:|---:|
| Search API | 30 | 5 ms | 8 ms | 40 ms |
| Workspace save API | 30 | 6 ms | 7 ms | 37 ms |
| Corrected-data screening with revision guard | 10 | 340 ms | 394 ms | 394 ms |
| Strategy Studio screening result | 10 | 895 ms | 924 ms | 924 ms |
| In-sample Strategy Studio research | 3 | 66.744 s | 67.052 s | 67.052 s |
| Evaluation of 20 active daily alerts | 20 | 757 ms | 781 ms | 1,002 ms |

The API latency distributions were collected after the concurrent-revision guard was added. Strategy Studio and chart endurance were collected earlier the same day; the guard affects the live screening path only. The research P95 is the maximum of three samples and is not a stable production percentile. These values are measurements, not new acceptance targets. No timing limit was set for search, workspace, screening, research, or alerts.

NFR-11 was retested on the final build with 30 warm and 30 cold opens of ten synthetic symbols. Warm was P50 165 ms / P95 **183 ms** / max 185 ms against ≤1 second; cold was P50 477 ms / P95 **495 ms** / max 501 ms against ≤3 seconds. The cold measurement starts after a fresh API process passes its health check, so process boot is excluded. Results are in [nfr11.json](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/nfr11.json).

The 24-cycle endurance test alternated 1×1, 4×4, and 1×1 layouts with 2,610-bar histories, changed symbols, and created/deleted one drawing per cycle. After garbage collection, JS heap moved from 15.27 MB to 18.47 MB (+3.20 MB); the observed samples settled near 18.5–19.0 MB. Canvas count returned from 7 to 7. This bounded run did not show meaningful growth, but it does not establish stability over hours. Listener counts were not instrumented.

## Historical research reconciliation

**Unresolved; not represented as a pass.** The earlier isolated `momentum25_e2e` historical copy was not available in the final-stabilisation environment. The active single-user application database was not queried or copied. No legacy reports or stored results were rewritten.

The preserved M14.7 report remains the only evidence: it sampled eight historical runs and found point-in-time qualification changes of up to 17 names. It attributed the difference to later split/bonus adjustment factors, date-appropriate universe membership, and the raw-close RS defect that was subsequently fixed. The report includes a 2023-02-28 case where only 8 of the stored Top-25 survived the then-current live code, and its MCX split case showed a raw 12-month return of −76% versus +20% after adjusted-price treatment. Those figures were not recomputed here and do not establish current parity. See [research-reconciliation.md](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/research-reconciliation.md) and the preserved [M14.7 report](/Users/varunagarwal/Downloads/Applications/StocksMomentum/docs/history/audits/2026-10-19-m14-pit-rerun-report.md).

## Resolved defects

| Severity | Issue | Root cause | Resolution |
|---|---|---|---|
| P0, resolved | Same-session corrected data reused a stale completed result | Live screening identity used the date where point-in-time evaluation used a market-data manifest | Capture the committed manifest after ingestion and use strategy/date/data-version/config-hash identity; exact repeats reuse the immutable run, corrected inputs create a new run |
| P0, resolved | A correction during a live screen could be mislabeled as one input revision | Current-row reads happened after manifest capture and were not pinned to one database snapshot | Compare the committed revision after scoring and before persistence; reject mixed-revision results with an actionable retry message |
| P1, resolved | Rolled-back writes could perturb data-version identity | PostgreSQL sequences are non-transactional; sequence `last_value` included aborted changes | Compute the revision from visible committed row versions and deletion history; add revision indexes |
| P1, resolved | Failed screening could leave partial result rows | Exception handling committed the failure status in the same session that held partial result writes | Commit the lifecycle row before work; rollback result writes on exception, then commit `FAILED` separately |
| P1, resolved | Interrupted screening rows could remain pending/running after restart | Startup recovery covered Strategy Studio evaluations but not screening runs | Fail unfinished screening rows during startup; permit explicit retry and preserve completed rows |
| P2, resolved | Low-contrast labels and an invisible keyboard focus state | Several muted Tailwind colors missed contrast ratios; shortcuts dialog Close button lacked focus styling | Darken readable text colors, use neutral indicator labels with colored swatches, and apply the shared focus ring |

## Remaining limitations

- Legacy research reconciliation awaits an authorized isolated copy. Existing report findings are historical evidence only.
- A physical assistive-technology screen-reader session was not run. axe semantics and keyboard interactions passed on the three primary views; the audit did not repeat every route at every Round 2 viewport size.
- Endurance checked mounted chart/canvas release and post-GC heap, but not event-listener counts or multi-hour usage.
- Research timing used three full in-sample evaluations. It is not sufficient for a robust tail-latency estimate.
- Alert timing sampled 20 active daily close alerts; weekly/monthly interval timing was not measured in this pass.
- The tests use synthetic data and do not establish vendor-data accuracy, licensed-source coverage, or production-scale history performance.
- Direct exchange downloads remained disabled. The final pass exercised imported/locally stored data paths and did not validate the opt-in forced-download path.
- The production build still emits a main JavaScript chunk of about 566 kB raw (about 182 kB gzip). This is a pre-existing optimization issue, not a functional regression.

## Technical and public-release status

**Technical:** Conditional readiness for sustained single-user local use with newly generated, manifest-traceable runs, immutable completed snapshots, explicit failed-run recovery, and verified backup/restore. No P0/P1 defects remain in the tested scope. Do not cite legacy research conclusions as reconciled until the isolated historical comparison is rerun.

**Legal/publication:** Still blocked independently by NSE data-use compliance/permission review, final licence approval, Wickstreet name/trademark clearance, and publication permissions. This engineering pass does not resolve any of them. The no-login deployment remains a loopback-only single-user application; no network deployment model or authentication change was made.

## Verification summary

- Backend: 841 tests passed in the full suite. Focused corrected-data/provenance coverage passed 4/4; focused failure/recovery coverage passed 4/4. Two pre-existing deprecation warnings remain.
- Web: 101 Vitest tests passed; ESLint passed with zero warnings; production build passed; final accessibility E2E passed 2/2; final performance/endurance E2E passed 3/3.
- Backend Ruff and mypy passed. The local changes were committed without pushing or publishing.

Full commands and isolated-database details are recorded in [verification-results.md](/Users/varunagarwal/Downloads/Applications/StocksMomentum/audit-evidence/final-stabilisation/verification-results.md). The final implementation commit is recorded in the repository history.
