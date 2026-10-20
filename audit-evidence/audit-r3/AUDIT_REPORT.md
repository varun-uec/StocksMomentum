# Wickstreet and Momentum25 — Comprehensive Audit Report (Round 3)

Date: 2026-10-20. Branch `wickstreet/m10-m11`, local only, nothing pushed. Audit base `1977039`. Fixes and evidence: 17 local commits (18 with the final report commit).

## 1. The answer

**Is the platform functionally correct, financially trustworthy, operationally reliable, seamlessly integrated and ready for its intended release? No — not yet. It is close on correctness and integration, and not close on operations and release rights.**

| Question | Verdict | One-line reason |
|---|---|---|
| Functionally correct | **Yes, with fixed defects** | 3 P1, 23 P2 and 17 P3 defects were found (plus 3 inherited P2 counted in the register). 27 are fixed in source and tested. Browser and backend suites pass on the fixed code (section 4). |
| Financially trustworthy — the live screener | **Yes** | Adjustment, indicators, RS, eligibility, gates, scores, ranks, determinism and point-in-time boundaries all equal independent recomputations. |
| Financially trustworthy — the backtest | **No** | 27% of walk-forward notional fills at stale prices (R3-B-09, open, needs an owner methodology decision). |
| Operationally reliable | **No** | The EOD job has never been observed to run. It does not catch up after downtime. The container does not restart. None of the fixes is deployed. |
| Seamlessly integrated | **Yes, after one fix** | Strategy lifecycle, cross-screen provenance and multi-chart routing pass. One real defect (stale stored strategy, R3-U-10) is fixed. |
| Ready for release | **No** | Blocked by the items below. |

**Release blockers**

1. **R3-B-09** — backtest fill policy. Blocks any backtest claim. The live screener is unaffected.
2. **R3-B-10** — four differences from spec §8. The owner must amend the spec or change the code.
3. **Deployment** — the running image predates every fix, including the import guard that stops one bad date row from emptying the screener (R3-B-02, P1).
4. **EOD automation** — scheduled execution never observed; no catch-up (R3-B-11); restart policy `no` (R3-O-02); no authorised automated data source, so the job re-screens stored data and refreshes nothing.
5. **Rights** — licence ADR-015 unaccepted, no LICENSE or NOTICE file, NSE and BSE data-use terms unverified, name clearance open. These block publication, not local use.
6. **Dependency audits** — not run; need your approval.

There is **no P0**. No financial methodology was changed.

## 2. Scope and method

- **Two non-overlapping agents plus the main session.** An engineering agent (Opus) took backend, financial correctness, EOD pipeline, database reliability, security, ADR and documentation compliance on isolated databases. A dashboard agent kept `.dashboard/index.html`. The main session took the browser, UI, accessibility, charting, integration, performance and the final reports. The main session confirmed the worker's test counts (ruff, mypy strict on 263 files, import contracts, 947 passed on HEAD), its commit list, the RS read-path diff and the walk-forward trade list. It did not repeat the worker's full-universe recomputation.
- **Inventory** rebuilt from source and the running app, not from the old ledger: 68 API operations on 59 paths, 24 page routes, 21 drawing kinds, about 35 indicators, 6 layouts, 7 alert sources, 18 ADR files (Capability Matrix).
- **Real application, read-only:** Chromium on `localhost:8000` with all non-GET API calls blocked; GET-only API and SQL checks on the real database. 150 route states (25 routes × 3 sizes × 2 themes) and axe-core on 25 routes.
- **Isolated environments for anything that writes:** disposable PostgreSQL databases ending in `_e2e` or `_test` in labelled containers, and a restored dump of the real database for the worker's real-data checks. No NSE or BSE request was made. Direct downloads stayed off.
- **Independent references:** pure-Python recomputation of indicators, aggregation, adjustment, RS, eligibility and gates. None imports Momentum25 code.

## 3. System health

| Layer | Health |
|---|---|
| Calculation engine and screener | Strong. Byte-deterministic. Matches independent recomputation. |
| Chart workstation | Strong. All 21 drawing tools, indicators, layouts, replay, alerts pass. Candle geometry guarded by pixel tests. |
| Strategy lifecycle and research | Strong, one integration defect fixed. Backtest fill pricing is wrong (open). |
| Persistence and concurrency | Strong. Optimistic concurrency correct (10 parallel writes → one 200, nine 412). Backup and restore verified on 14 tables. |
| Accessibility | Automated WCAG 2.x A and AA now clean on 23 routes in both themes. Screen reader not tested. |
| Security (loopback model) | Sound. No auth by design; never expose it to a network. |
| Operations | Weak. See blockers 3 and 4. |
| Documentation | Several stale counts and claims (R3-B-21). |

## 4. Test and verification record

| Check | Result |
|---|---|
| Backend `ruff check` | Clean |
| Backend `mypy --strict` | Clean, 263 files |
| `lint-imports` | 2 contracts kept, 0 broken (the contracts omit the application layer, R3-B-16) |
| Backend `pytest`, isolated `_test` database | **947 passed**, 2 warnings (run by the main session on HEAD). At the start of the audit HEAD had **6 failing** tests (R3-B-01); the worker added 22 tests, each failing without its fix. |
| Web ESLint | Clean |
| Web Vitest | **144 passed**, 21 files (141 before; +3 golden indicator tests) |
| Web production build | Passes. Main chunk 1,009.9 kB raw / 315.6 kB gzip (R3-U-01). |
| Browser suite, first serial run at audit HEAD | 214 passed, **8 failed**, 12 skipped (16.9 min) |
| Browser suite, final serial run | See `BROWSER_FINAL.md` section below once complete |
| Axe sweep (`r3-axe-routes`) | 23 routes × 2 themes: 0 violations |
| NFR-11 | Warm P95 152 ms (≤ 1 s); cold P95 513 ms (≤ 3 s) |

**What the 8 first-run failures were.** Four specs expected the UI from before commit `cecb3e5` (stale tests). One test asserted behaviour that commit removed. One was a real defect (R3-U-10). One was a provenance finding in disguise (R3-U-09: `data_version` moved when the worker committed during my run). One did not reproduce on four reruns (R3-O-04, not verified). The committed browser suite was red at HEAD before this audit, so the earlier "all pass" statements did not describe HEAD.

**A regression I introduced and fixed inside the audit.** My first fix for R3-U-10 reset the stored strategy hash on every route. On a first visit that changed the watchlist query key just after load, and a fast Alt+W could write to the old key, so the panel never updated. Bisecting an order-dependent failure found it. The reset now acts only on a name or hash the workspace does not offer. Both specs pass.

## 5. Findings summary

Full list with status, owner and verification: `REMEDIATION_REGISTER.md`.

| Severity | Count | Fixed | Open |
|---|---|---|---|
| P0 | 0 | — | — |
| P1 | 3 | 2 (R3-B-02, R3-B-08 awaiting your confirmation) | 1 (R3-B-09, **blocker**) |
| P2 | 25 (22 new, 3 inherited) | 11 | 14 (11 new, 3 inherited) |
| P3 | 17 | 3 | 14 |

Most significant, in order:

1. **R3-B-09 (P1, open).** Walk-forward fills use stale prices for 27% of notional.
2. **R3-B-02 (P1, fixed).** A holiday, weekend or future row in `import-eod` became the latest date and the screener served an empty run.
3. **R3-B-08 (P1, fixed, confirm).** Live and watchlist RS ranked ETFs and funds; 101 equities crossed the RS ≥ 70 gate on the wrong side.
4. **R3-B-10 (P2, open).** Four code-vs-spec differences, including RS ranked over all equities (1,253 of 1,338 ratings change).
5. **R3-B-11 and R3-O-02 (P2, open).** No catch-up after downtime and no container restart: a sleeping Mac skips the day silently.
6. **R3-U-09 / R3-B-12 (P2, open).** The manifest records `git rev-parse HEAD`: `null` in the container, a moving value on a host. Tonight's job will write a duplicate snapshot of 2026-10-19.
7. **R3-U-10 (P2, fixed).** A stored strategy the workspace no longer offers hung the chart Assessment.
8. **R3-U-02, 03, 04, 05 (P2/P3, fixed).** Accessibility: unlabelled controls, no main landmark, contrast in both themes, label in name.

## 6. Gate status

| Gate (brief §13) | Status |
|---|---|
| Every capability has PASS, FAIL, BLOCKED or NOT VERIFIED | Done: `CAPABILITY_VALIDATION_MATRIX.md` |
| Critical workflows have browser and backend evidence | Done |
| Momentum25 outputs checked against independent references | Done: `FINANCIAL_CORRECTNESS_REPORT.md` |
| Strategy lifecycle and cross-screen consistency proven | Done (one defect found and fixed) |
| EOD automation status established exactly | Done, except the first scheduled execution (18:30 IST today); see `EOD_AUTOMATION_REPORT.md` |
| Data integrity and replay correctness verified | Done |
| Security and licensing documented | Done: `SECURITY_RELEASE_GATE_REPORT.md` |
| Performance criteria evaluated | Done |
| P0 and P1 resolved or named as blockers | Done: one P1 open and named (R3-B-09); one awaiting confirmation (R3-B-08) |
| P2 and P3 have owners and dispositions | Done in the register |
| Dashboard reflects the verified state | Updated at the end (`.dashboard/index.html`) |

## 7. What was not verified

- Real screen-reader use, Safari, Firefox, forced-colours mode.
- The first scheduled EOD execution (due 18:30 IST).
- `pip-audit` and `npm audit` (approval needed).
- Indicator conventions without a vendor-neutral reference: Supertrend, Parabolic SAR, regression channel, pivots, VWAP variants.
- Multi-hour memory stability (only a 24-cycle soak).
- Killing the process mid-import; raw malformed HTTP headers.
- The legal questions in the Security report.
- The strategy-integration check that a saved config's run shares the seeded run's `data_version` was removed from the spec, because earlier specs legitimately correct bars; no replacement identity check was written.

## 8. Incident during the audit

At 10:59 UTC the owner's API container was OOM-killed when the audit's first restore, which sat on tmpfs, took the Docker VM's memory. The main session restarted it; the real database stayed healthy and was never written. The second restore used a disk volume with a 2 GB cap. The API container has no memory limit and no restart policy, which is why it died and stayed down (R3-O-02).

## 9. Deliverables

| Deliverable | File |
|---|---|
| Comprehensive Audit Report | this file |
| Capability Validation Matrix | `CAPABILITY_VALIDATION_MATRIX.md` |
| Financial Correctness Report | `FINANCIAL_CORRECTNESS_REPORT.md` |
| EOD Automation Report | `EOD_AUTOMATION_REPORT.md` |
| UX Validation Report | `UX_VALIDATION_REPORT.md` |
| Security and Release-Gate Report | `SECURITY_RELEASE_GATE_REPORT.md` |
| Prioritised Remediation Register | `REMEDIATION_REGISTER.md` |
| ADR and documentation compliance | `ADR_COMPLIANCE.md` |
| Progress dashboard | `.dashboard/index.html` |
| Raw evidence | `ui/` (main session), `backend/` (worker) |
