# Wickstreet and Momentum25 — Comprehensive Audit Report (Round 3)

Date: 2026-10-20. Branch `wickstreet/m10-m11`, local only, nothing pushed, published or deployed. Audit base `1977039`. 35 local commits of fixes, tests and evidence.

## 1. The answer

**Is the platform functionally correct, financially trustworthy, operationally reliable, seamlessly integrated and ready for its intended release? Not yet.** Correctness and integration are now strong. Operations and release rights are not ready.

| Question | Verdict | Reason |
|---|---|---|
| Functionally correct | **Yes** | The full serial browser suite passes at the final code (229 passed, 0 failed, 8 opt-in skipped). Backend: 981 passed. |
| Financially trustworthy: the live screener | **Yes** | Adjustment, indicators, RS, eligibility, gates, scores, ranks, determinism and point-in-time boundaries equal independent recomputations. |
| Financially trustworthy: the backtest | **No** | 27% of walk-forward notional fills at stale prices (R3-B-09, open, owner decision). |
| Operationally reliable | **No, until deployed** | The scheduler fired once unattended (good). The running image still fires Tuesday to Saturday, has no catch-up, does not restart, and records the wrong trigger. Every fix is in source and none is deployed. |
| Seamlessly integrated | **Yes** | Strategy lifecycle, cross-screen provenance, multi-chart routing and `/validation` for saved strategies pass end to end. |
| Ready for release | **No** | See the blockers. |

### Genuine release blockers (need an owner decision or action)

1. **R3-B-09** — walk-forward fill policy. Blocks any backtest claim. The live screener is unaffected.
2. **R3-B-10** — four code-versus-spec differences (amend the spec or change the code).
3. **Deployment** — the running image predates every Round 3 fix, including the import date guard (R3-B-02, P1) and the scheduler fixes. Rebuild with `make up`. This audit did not deploy.
4. **A repeat of the scheduled run on the rebuilt image** — one unattended run is observed; stable repeated operation is not.
5. **No authorised automated data source** — downloads are off by design and no subscriber agreement exists. The job only re-screens stored data. (BLOCKED, legal.)
6. **Licence, data rights, name** — ADR-015 unaccepted, no LICENSE or NOTICE file, NSE and BSE terms unverified, name clearance open. These block publication, not local use.

### Accepted limitations (documented, not blockers)

- `/validation/experiment/run` and `/research/compare/strategies` still resolve a strategy by name, not by version.
- The screener and watchlist APIs use opposite signs for rank change; the UI shows each correctly.
- Remaining main-chunk weight (react-router, lightweight-charts, TanStack) is left whole to protect chart-open times.
- Indicators with no vendor-neutral convention (Supertrend, Parabolic SAR, regression channel, pivots, VWAP variants) have property tests but no golden reference.
- Chart-open benchmarks for 1, 4 and 16 charts have no acceptance limit in ADD A1 ("reports the results"); the figures are recorded.

### Not verified

Real screen-reader use; Safari and Firefox; forced-colours mode; `pip-audit` and `npm audit` (they send the dependency list off-machine; awaiting your approval); multi-hour memory stability. The worker ran the full-universe financial recomputation; the main session spot-checked it and did not repeat it.

There is **no P0**. No financial methodology was changed.

## 2. Scope and method

- **Two agents plus the main session.** An engineering agent (Opus) took backend, financial correctness, EOD pipeline, database reliability, security and ADR compliance on isolated databases, and later the provenance, resource-isolation, document-contract and rate-limit work. A dashboard agent kept `.dashboard/index.html`. The main session took browser, UI, accessibility, charting, integration, performance and the reports. The main session re-ran the backend gate itself (ruff, mypy strict on 265 files, import contracts, 981 passed) and reviewed the worker's commits, the RS read-path diff and the walk-forward evidence.
- **Inventory** rebuilt from source and the running app: 68 API operations on 59 paths, 24 page routes, 21 drawing kinds, about 35 indicators, 6 layouts, 7 alert sources, 18 ADR files (`CAPABILITY_VALIDATION_MATRIX.md`).
- **Real application, read-only:** Chromium on `localhost:8000` with every non-GET API call blocked; GET-only API and read-only SQL on the real database (run #149, data through 2026-10-19).
- **Isolated environments for anything that writes:** disposable PostgreSQL databases in labelled containers on named volumes with a hard memory cap (`scripts/test-infra.sh`), and a restored dump for the worker's real-data checks. No NSE or BSE request was made. Direct downloads stayed off.
- **Independent references:** pure-Python recomputation of indicators, aggregation, adjustment, RS, eligibility and gates. None imports Momentum25 code.

## 3. Record of verification

| Check | Result |
|---|---|
| Backend `ruff check` / `mypy --strict` / `lint-imports` | Clean / clean, 265 files / 2 kept, 0 broken (run by the main session on the final code) |
| Backend `pytest`, isolated `_test` database | **981 passed**, 2 warnings (run by the main session). HEAD had 6 failing at the audit's start (R3-B-01). |
| Web ESLint, `tsc --noEmit` | Clean |
| Web Vitest | **148 passed**, 21 files |
| Web production build, main chunk | 654 kB raw, 209 kB gzip (was 1,010 / 316; R2: 566 / 182) |
| **Browser suite, full serial, final code** | **229 passed, 0 failed, 8 skipped** (18.1 min). Log: `ui/playwright-final4.log`. Skipped: 6 opt-in layout benchmark cases (run separately, below) and 2 opt-in visual sign-off cases. |
| Browser suite, first run at audit HEAD | 214 passed, 8 failed, 12 skipped |
| Axe, 23 routes × light and dark; scrollable regions at 390 and 1440 px | 0 violations (`r3-axe-routes.spec.ts`) |
| NFR-11, 30 samples, final build | Warm P50 134 / P95 **147 ms** (limit 1 s). Cold P50 214 / P95 **228 ms** (limit 3 s). `ui/nfr11-final.json` |
| 1 / 4 / 16 charts, 30 samples, final build | Warm P95 147 / 380 / 1,316 ms. Cold P95 190 / 408 / 1,333 ms. Pan FPS P5 61 / 61 / 60. Heap max 12 / 27 / 84 MB. `ui/m13-bench-final.json` |
| Full-universe screening (3.2 M bars, 3,096 universe, 5 runs, real-data copy) | Pipeline P50 32.6 s, P95 33.5 s |
| Scheduled EOD run | Observed at 18:30:00 IST (run 150, 37 s, results identical to run 149) |
| Dev API under concurrent test load | 429 polls, 0 non-200, 0 OOMKilled (`backend/isolation/`) |

Environment: Apple M4 Pro, 14 cores, 48 GB; Chromium 153 headless; Docker VM 8 GB. Benchmarks ran on an otherwise idle machine (load average about 1.8) with 2,610-bar synthetic fixtures.

**The eight tests that failed in the first run, reconciled.**

| First-run failure | Cause | Resolution |
|---|---|---|
| journey 1, 3, 7+8 and `momentum25` watchlist | Specs expected the UI from before commit `cecb3e5` (config hash in provenance, hash-valued selector) | Specs updated |
| `m12-shell` Assessment tab | Copy changed to "Why it is not ranked" | Spec updated |
| journey 4 | **Real defect R3-U-10**: a stored strategy the workspace no longer offers hung the chart Assessment | Fixed (provider reset; the fallback is the default production strategy) |
| `/strategies` hard load (no `h1`) | Did not reproduce on any rerun, including the later full runs | Not reproduced; treated as a flake (R3-O-04) |
| `strategy-integration` data_version | `data_version` moved with the git commit and with earlier specs' data corrections | Provenance fixed (R3-U-09); the spec now checks a 12-hex key, not equality with the seeded run |

A previously triaged failure is not a pass, so the full suite was rerun after each round of fixes. Those reruns found more: stale helpers after the document contract change (about 45 tests), an order-dependent race I had introduced in the provider, and a wrong fallback. The last full run is clean.

## 4. System health by layer

| Layer | Health |
|---|---|
| Calculation engine and screener | Strong. Byte-deterministic. Matches independent recomputation. |
| Chart workstation | Strong. 21 drawing tools, indicators, layouts, replay and alerts pass. Candle geometry guarded by pixel tests. The earlier wick-size defect has not returned. |
| Strategy lifecycle and research | Strong. `/validation` now validates saved versions. Backtest fill pricing is wrong (open). |
| Persistence and concurrency | Strong. Ten parallel writes give one 200 and nine 412. A never-saved document now reads as revision 0. Backup and restore verified on 14 tables. |
| Accessibility | Automated WCAG 2.x A and AA clean on every route in both themes. Screen readers not tested. |
| Security (loopback model) | Sound. No authentication by design: never expose it to a network. |
| Operations | Weak until deployed (blockers 3 and 4). |
| Documentation | Counts and drawing-tool claims corrected. ADR-003, 007, 009, 012 text and the ADR index are still stale. |

## 5. Findings

Full list with status, owner and verification criteria: `REMEDIATION_REGISTER.md`.

| Severity | Count | Fixed in source | Open |
|---|---|---|---|
| P0 | 0 | — | — |
| P1 | 3 | 2 (R3-B-02; R3-B-08, awaiting your confirmation) | 1 (R3-B-09, **blocker**) |
| P2 | 26 (23 new, 3 inherited) | 17 | 9 (R3-B-10, 13, 14, 15, 16, 21 in part, and 3 inherited) |
| P3 | 17 | 8 | 9 |

**Resolved in this round, in the owner's priority order**

1. **R3-U-09 / R3-B-12 provenance identity** — ADR-014 §10. `data_version` hashes market data and engine versions; the strategy keeps `config_hash`; the build id is stored, not hashed; stored manifests keep their keys (run 149's `8790a000bd4f` reproduced in a test); stable across commits and with no git. Confirmed live before the fix: run 150 had identical results and a different key. Pending: an `ENGINE_VERSION` constant (Q4).
2. **R3-U-07 `/validation`** — the picker lists each production and saved version; `config_hash` flows through the dashboard and the five GETs; evidence never mixes versions; an unrun version reads empty.
3. **R3-O-01 resource isolation** — compose memory and CPU caps and `restart: unless-stopped`; `scripts/test-infra.sh` (named volume, hard cap, refuses without headroom, never tmpfs). My own test database moved to it. The dev API was unaffected under load.
4. **R3-U-01 bundle** — 1,010 to 654 kB; chart-open times did not degrade (16-chart warm P95 1,525 to 1,316 ms).
5. **EOD** — observed run; weekday numbering defect found and fixed (R3-B-26); catch-up added; source availability BLOCKED.
6. **R3-U-06, U-08, U-11** — never-saved documents read 200 at revision 0 (ADR-013 §5); rate limit 1,200 a minute with `Retry-After` and a client retry; the improved-rank arrow points up.
7. **The eight failing tests** — reconciled (section 3); the full suite is clean.
8. **ADR-056** — not found anywhere (section 6).

**Also found and fixed:** R3-B-02 (P1) import date guard; R3-U-10 stale stored strategy; R3-U-02 to R3-U-05 and R3-U-12 accessibility; R3-B-03 to R3-B-07; R3-U-15, a race I introduced and then removed. That regression came from my first R3-U-10 fix, which set the strategy hash on every first visit, so a fast Alt+W wrote to a stale query key. I found it by bisecting an order-dependent failure.

## 6. ADR-056

It does not exist. I searched the working tree, all git history, `docs/`, the plans, the ADD and its amendment, the implementation spec, the design record, the README, the owner's memory notes and the sibling projects. The only hits are in this audit's own reports. No ADR above 015 is mentioned anywhere. I did not invent or renumber a record. All 18 ADR files were reviewed (`ADR_COMPLIANCE.md`). **Owner: name the document.**

## 7. Gate status

| # | Gate | Status | Basis |
|---|---|---|---|
| 1 | System inventory | **PASS** | Matrix rebuilt from source; document drift recorded; ADR-056 absent |
| 2 | Functional validation | **PASS** | 229 / 0 / 8 on the final code; real-app read-only runs |
| 3 | Momentum25 financial correctness | **PARTIAL** | Screener PASS; backtest fills FAIL (R3-B-09); spec differences open (R3-B-10) |
| 4 | Strategy lifecycle integration | **PASS** | Journeys 1 to 8; saved-strategy spec; `/validation` spec |
| 5 | Charting engine | **PASS** | Geometry, aggregation, adjustment, indicators, replay, layouts. Seven indicator families lack a golden reference (NOT VERIFIED). |
| 6 | EOD refresh and pipeline | **PARTIAL** | Scheduler implemented, installed (in the container), enabled, one run observed. Deployed image defective. Source BLOCKED. |
| 7 | Backend and database reliability | **PASS with open P2** | Concurrency, validation, migrations and restore verified. Schema drift open (R3-B-15). |
| 8 | Security and licensing | **PARTIAL** | Code PASS. Licence and data rights BLOCKED. Dependency audits NOT VERIFIED. |
| 9 | UI, UX, accessibility | **PASS (automated)** | Screen reader NOT VERIFIED |
| 10 | Performance, resilience, regression | **PASS** | NFR-11 and layouts measured; full suites green; isolation verified |
| 11 | ADR and documentation | **PARTIAL** | ADR-014 §10 and ADR-013 §5 amended; ADR-056 unresolved; some docs stale |
| 12 | Findings and remediation | **PASS** | Register with owners and dispositions |
| 13 | Final acceptance | **NOT READY** | Blockers 1 to 6 |

## 8. Incident during the audit

At 10:59 UTC the owner's API container was OOM-killed when the worker's first restore, held in tmpfs (RAM), took the Docker VM's memory. The main session restarted it; the real database stayed healthy and was never written. The API container had no memory limit and no restart policy, so it died and stayed down. Both are fixed in source (not deployed). My own test container also used tmpfs (1.1 GB at its peak); it was replaced by the isolated infrastructure.

## 9. Owner decisions

1. **R3-B-09** backtest fill policy. No default taken.
2. **R3-B-10** per item: amend the spec or change the code. No default taken.
3. **R3-B-08** confirm the read-path RS universe fix (`51f3239`). Kept; revert if you disapprove.
4. **R3-U-09** add an `ENGINE_VERSION` constant. Not added.
5. **R3-B-22** which document is ADR-056. Unresolved.
6. Approve `pip-audit` and `npm audit`. Not run.
7. **Deploy** the rebuilt image (`make up`). Not deployed.
8. **R3-B-13** the `/live` `data_as_of` contract; **R3-B-18** repair of 22,328 `adj_close` rows in the development database (a real-data write).
9. Accept ADR-012 and ADR-015; add LICENSE and NOTICE; clear the name; legal review of NSE and BSE terms.

## 9a. Deliverables

| Deliverable | File |
|---|---|
| Comprehensive Audit Report | this file |
| Capability Validation Matrix | `CAPABILITY_VALIDATION_MATRIX.md` |
| Financial Correctness Report | `FINANCIAL_CORRECTNESS_REPORT.md` |
| EOD Automation Report | `EOD_AUTOMATION_REPORT.md` |
| UX Validation Report | `UX_VALIDATION_REPORT.md` |
| Security and Release-Gate Report | `SECURITY_RELEASE_GATE_REPORT.md` |
| Prioritised Remediation Register | `REMEDIATION_REGISTER.md` |
| Updated Progress Dashboard | `.dashboard/index.html` |
| Also | `ADR_COMPLIANCE.md`; raw evidence in `ui/` and `backend/` |
