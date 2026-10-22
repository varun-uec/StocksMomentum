# Wickstreet Round 2 Defect Register

**Date:** 2026-10-19. Severity uses the requested P0–P3 definitions. “Fixed” means the regression test and affected suite passed after the smallest correction. Inherited findings remain visible so the Round 2 disposition is not mistaken for closure.

## Round 2 defects

| ID | Severity | Reproduced behavior / evidence | Root cause | Disposition |
|---|---|---|---|---|
| R2-01 | **P1 — fixed** | At 768 px, route pages measured 1120 px wide and horizontally overflowed. The initial sweep log records this on all routes. | Desktop nav/search breakpoint was `md`, leaving desktop-only navigation active at tablet width. Long strategy labels and diagnostic grid also lacked containment. | Nav switches at `lg`; long Studio labels wrap; chart grid scrolls within container. Re-swept 26 routes × 4 viewport widths × 2 themes: 208 states, no root overflow. Evidence: `playwright-viewport-audit-r2-initial-failure.log`, `playwright-viewport-audit-r2-final.log`, `viewport-audit.json`. |
| R2-02 | **P2 — fixed** | Two concurrent alert evaluators both read an active alert; one state transition was stored, but both API responses reported a firing. | Firing count was incremented from pre-update evaluation result, without checking whether the conditional state transition won. | Repository `fire()` now returns success based on active→triggered update rowcount; use case increments only on success. Deterministic barrier regression passes in full backend suite. |
| R2-03 | **P2 — fixed** | Under `prefers-reduced-motion: reduce`, root scroll behavior still computed to `smooth`. | No reduced-motion override for smooth scroll and CSS transitions. | Added media query disabling smooth scrolling and near-zero transitions/animations. Browser computes `auto` and durations below 0.01s. |
| R2-04 | **P2 — fixed** | Strategy comparison controls could not be addressed through their visible labels/accessibility names. | Labels were not connected to select IDs. | Added stable IDs and `htmlFor`; browser can select by label. Covered in the final 37-case interaction suite. |
| R2-05 | **P2 — fixed** | Second real `momentum25 screen` invocation raised `UniqueViolationError` for `(strategy_id, run_date, data_version, config_hash)` even though an immutable completed result existed. Raw failure: `cli-screen-r2.log`. | The use case always attempted a new run instead of resolving the full existing completed identity. | Added exact-identity lookup to repository port/implementation; ordinary repeated screens reuse completed result without rewriting it. Regression `test_repeated_screen_reuses_exact_completed_snapshot`; actual CLI called twice and reused run 1 (`cli-screen-r2-final.log`). Same-date data corrections are still not versioned separately by current date-only `data_version` semantics; see financial report. |

## Prior Round 1 defects still fixed and regression-covered

Round 1 P1 fixes remain in the baseline suite: inconsistent historical/PIT source view, adjusted-close instead of adjusted-open walk-forward fill, permanently pending run scheduling, and nullable validation rates. Round 1 P2 fixes remain covered: ranking order, search focus race, mobile fixed nav overlap, dashboard horizontal-scroll cue, CLI no-op behavior, disabled-by-default exchange downloads, forced-run rejection, and Data screen `.env` instructions. No Round 2 regression was found in these fixes. See [`E2E_DEFECT_REGISTER.md`](../2026-10-19-e2e-r1/E2E_DEFECT_REGISTER.md).

## Open inherited findings / limitations

| ID | Severity | Finding | Evidence status / next action |
|---|---|---|---|
| R1-P2-09 | **P2 — open, legacy research path** | Research parameter override helper is not called by the legacy research harness. | Not independently reproduced in Round 2. Route through registered schema and pin a test, or retire helper before relying on that legacy variant workflow. |
| R1-P2-10 | **P2 — open, explanation clarity** | Stale engine registry/strategy descriptions may confuse signal explanations. | No incorrect output isolated in Round 2. Reconcile catalogue copy with registered executable engines. |
| R1-P2-11 | **P2 — open, load optimization** | Main web JavaScript chunk exceeds 500 kB raw. | Build emits 565.81 kB raw / 182.14 kB gzip. NFR-11 passes, but route splitting may improve initial load. |
| R1-P2-12 | **P2 — open, tooling** | Development toolchain advisories/upgrades remain. | Not a reproduced runtime exploit. Review compatibility upgrades and dependency audit before publication. |
| R2-LIMIT-01 | **P2 — insufficient evidence** | Same-session corrected market data is not distinguished by date-only run `data_version` for an unchanged config. | The immutable completed snapshot is safely reused and not rewritten, but the CLI cannot yet create a distinct same-session corrected snapshot. Need a stable source revision/manifest identity before claiming correction replay. |
| R2-LIMIT-02 | **P2 — insufficient evidence** | DB failure mid-transaction, backup/restore, crash during import, syntactically malformed HTTP, and extended endurance were not exercised. | Add deterministic fault injection and backup restore drill in isolated infrastructure before technical release certification. |
| R2-LIMIT-03 | **P2 — accessibility evidence gap** | Screen-reader flows and measured color-contrast audit not completed. | Keep accessibility conformance unclaimed; run assistive-technology and ratio-based checks. |
| R2-LIMIT-04 | **P2 — performance evidence gap** | Repeated search/save/restore/screening/research/alert latency distributions not captured. | Instrument and collect representative percentiles; do not infer speed from functional pass. |

## P0 status

No Round 2 P0 was reproduced. Synthetic-data isolation was verified, no shared user database was modified, no NSE download ran, the loopback security boundary held in the negative cases, and no financial regression in the pinned fixtures was observed. This is a statement about tested evidence, not a guarantee that untested paths are defect-free.
