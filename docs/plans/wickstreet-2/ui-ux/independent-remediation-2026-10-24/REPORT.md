# Wickstreet 2.0 — remediation of the independent audit

**Date:** 24 October 2026, IST
**Branch:** `wickstreet/m10-m11` (local; not pushed)
**Baseline:** [independent audit](../independent-audit-2026-10-23/REPORT.md) and its [handoff](../independent-audit-2026-10-23/HANDOFF-CLAUDE-OPUS.md). Both stay unchanged, with all their evidence.
**Data:** revision 2801, NAVs to 22 Oct 2026, method v5.
**Score:** not self-certified. The audit scored the candidate 7.2/10 and the served app 6.7/10. A new independent review must set the next score.

## 1. Summary

Every confirmed P0 and P1 defect in the audit's register is fixed in source, covered by a regression test and deployed to port 8000. The P2 defects are fixed too. Section 4 lists what remains, as the audit asked.

| Release gate (audit §12) | State | Evidence |
|---|---|---|
| 1 · Tax boundary and default class (A-03, A-04) | **Fixed** | Exact-anniversary case returns **₹78,245.97** on the live API; the debt fund shows **₹21,647.40** under debt treatment with no user action |
| 2 · Chart truth (A-02, A-13, A-14) | **Fixed** | The −31.2021% trough on 24 Mar 2020 survives the plot, zoom and table; the Compare table reads ₹; backtest points sit on realised month ends |
| 3 · Save, reopen and conflict (A-05, A-09, A-10, A-11) | **Fixed** | Four calculator kinds round-trip every field; drafts survive conflicts, failures and record switches; every write failure is visible with a retry |
| 4 · Search and nested logic (A-06, A-07, A-08) | **Fixed** | Stale results cannot be chosen; `nippon india` opens on current Direct Growth plans; Match any keeps a two-level tree |
| 5 · Artifact parity (A-01) | **Fixed** | Port 8000 serves the entry built from this commit; the MF suite passes against it (section 5) |

## 2. Defect register

Severity follows the audit: P0 is a wrong financial output, P1 a misleading signature feature or broken core journey, P2 a narrower defect.

### A-01 · P1 · Served artifact differed from the reviewed source — **Fixed**

- **Cause.** The image builds `web/` inside Docker, but the container had not been rebuilt after the last source change. Port 8000 served `index-JwG64Xyp.js`.
- **Correction.** Rebuilt with `docker compose up -d --build api` and `BUILD_ID` set to the commit. `playwright.mf.config.ts` now accepts `MF_BASE_URL`, so the MF suite can test the served app itself instead of a fresh preview.
- **Verification.** Section 5 records the served entry name, its SHA-256 and the MF run against `http://localhost:8000`.

### A-02 · P1 · Drawdown chart and table dropped the deepest fall — **Fixed**

- **Cause.** `thin()` kept every n-th row. The zoom only sliced rows the chart had already dropped.
- **Correction.** `thin()` now keeps, in each bucket, the first row plus the rows with each series' lowest and highest values, on their own dates. `TimeChart` keeps every row and thins only the rows in view, so zoom shows full detail. The Risk chart takes the raw series, gains zoom and pins a labelled dot on the service's deepest trough. The legend states "Deepest −31.2% on 24 Mar 2020". The table keeps every fall's lowest day. The Risk tab now opens with this chart.
- **Files.** `components/charts.tsx`, `components/fund/Risk.tsx`.
- **Verification.** `charts.test.ts` (trough kept at 80–700 rows; per-series extremes in merged rows). Browser: `A-02` checks the legend, the dot, a keyboard zoom and the table against `/underwater`. [Before](../independent-audit-2026-10-23/screens/probe2-drawdown-omitted-trough.png) · [after](screens/d-fund-risk-viewport.png).

### A-03 · P0 · Tax used fixed day counts — **Fixed**

- **Cause.** `tax.py` tested `held > 365/730/1095` days. A 12-month holding across a leap year is 366 days, so it became long term.
- **Correction.** New `held_over(bought, sold, months)` compares the sale date with the calendar anniversary. A sale on the anniversary is short term. A purchase on a day the anniversary month lacks (29 Feb, 31st) uses that month's last day. All three thresholds (12, 24 and 36 months) use it. The Lab states the rule beside the tax result.
- **Files.** `backend/src/wickstreet/analytics/domain/tax.py`.
- **Verification.** `test_holding_periods_use_calendar_anniversaries`: the audit case gives ₹78,245.97; before, on and after anniversaries for 12, 24 and 36 months; leap-day and month-end purchases; debt at 24 months. Live API: 24 Jul 2023 → 24 Jul 2024, ₹10 lakh, code 122639 → short term ₹3,76,182.53, tax **₹78,245.97**. One day later → long term. Browser `A-03` repeats both cases.

### A-04 · P1 · The Lab taxed a debt fund as equity by default — **Fixed**

- **Cause.** The Lab always sent `tax_class: 'equity'`. The backend already derives the class from the category and answers `tax_class_needed` when the category does not settle it, but never got the chance.
- **Correction.** The default is now "From the fund's category". The request omits `tax_class`, and the slab travels whenever the class is not chosen as equity. The result names the class and its source ("Debt-oriented · from the fund's category" or "your choice") and the slab. An ambiguous fund (index fund, FoF, gold, dynamic hybrid) shows "Tax class needed" with a plain instruction, not a number. Changing the fund resets a chosen class. Captions now separate hypothetical full redemption (SIP, lump sum) from realised sales only (SWP, STP), and the exit-load, surcharge and STT exclusions sit beside the result.
- **Files.** `routes/simulate.tsx`, new `scenario.ts`, `api.ts`.
- **Verification.** `scenario.test.ts`; browser `A-04` ×2: code 118987 shows the API's ₹21,647 with no `tax_class` sent; UTI Nifty 50 Index asks for a class; a fund change resets it. [Before](../independent-audit-2026-10-23/screens/probe3-debt-default-equity-tax.png) · [after](screens/d-lab-debt-viewport.png).

### A-05 · P1 · Saved scenarios reopened with defaults — **Fixed**

- **Cause.** The workspace link passed only `kind` and `code`.
- **Correction.** `scenario.ts` holds the Lab's pure input logic: `toRequest`, `scenarioHref` and `inputsFromSearch`. Every request field round-trips through the URL: amount, instalment, day, dates, step-up, target, tax class and slab. A save now stores a provenance envelope (revision, method, as-of date, calculator version, tax class and its source). The workspace offers **Rerun on the latest snapshot** and **Replay on that snapshot**. Replay pins `data_revision`, and a banner says so. If the snapshot is gone, the error offers a rerun on the latest. Older records without provenance say they can only rerun.
- **Files.** `scenario.ts`, `routes/simulate.tsx`, `routes/workspace.tsx`.
- **Verification.** `scenario.test.ts`: all four kinds round-trip; malformed links keep defaults. Browser `A-05`: ₹25,000, day 15, 10% step-up, 15 Apr 2019–15 Oct 2025 and equity class reopen exactly; replay sends the saved revision.

### A-06 · P1 · A new query could select old results — **Fixed**

- **Correction.** `FundSearch` treats results as current only when the debounced query matches the typed text and the response is neither a placeholder nor fetching. Older results stay visible but dimmed, `aria-disabled` and `aria-busy`. Enter, click and the active descendant do nothing until the current answer arrives.
- **Files.** `components/FundSearch.tsx`.
- **Verification.** Browser `A-06`: with `sbi` delayed 2.5 s, Enter and a forced click on a Parag result do nothing. After the response, Enter opens the SBI fund.

### A-07 · P1 · Broad AMC search ranked historical IDCW plans first — **Fixed**

- **Cause.** Two defects. (1) The SQL candidate order tested `plan = 'direct'`, but listings say "Direct Plan". Postgres also sorts a NULL test result *first* under `DESC`, so 2,567 master-only historical rows filled the 500 candidates before any current plan. (2) The ranker put a phrase match ahead of current status.
- **Correction.** The candidate order uses case-insensitive prefixes with `DESC NULLS LAST`, on both the exact-match and Direct Growth terms. The ranker orders exact code or ISIN, then current before historical, then phrase, Direct Growth, history length and name. Search hits now carry `status` and `last_nav_date`. The list puts historical plans under a "Historical plans · no longer published" heading with "Historical · last NAV <date>".
- **Files.** `analytics/domain/search.py`, `mf_data/infrastructure/reader.py`, `analytics/interface/http.py`, `components/FundSearch.tsx`.
- **Verification.** `test_current_plans_come_before_historical_phrase_matches`; real-data test extended for `nippon india`. Live API top 8 for `nippon india`: all active, first is Nippon India Liquid Fund Direct Growth. `hdfc` and `sbi` also open on active Direct Growth plans; code `144891` still finds its historical plan. Browser `A-07`.

### A-08 · P1 · Match any broke a valid nested screen — **Fixed**

- **Correction.** `filterOf` merges a saved ANY group into the ANY. When an ALL group is among the other conditions, the gates move inside each alternative: `ANY(ALL(gates, …), …)`. That selects the same funds and stays at two levels. A 4xx response is no longer retried anywhere (`app/providers.tsx`), so a server's final answer arrives at once.
- **Files.** `view-spec.ts`, `app/providers.tsx`.
- **Verification.** `view-spec.test.ts` checks depth ≤ 2 and identical selections over 16 synthetic funds for three nested shapes. Browser `A-08` asserts every request's depth on the audit's view.

### A-09 · P1 · Rename conflict discarded the draft — **Fixed**

- **Correction.** A new draft store (`useDraft`) keeps each record field's edit outside the component, keyed by record and field. A refetch cannot replace it. A conflict shows the other window's version, **Copy my name**, **Save mine over theirs** and **Use their version (discards my name)**. The same component serves names of every record kind and note bodies.
- **Files.** `workspace.ts`, `routes/workspace.tsx`.
- **Verification.** Browser `A-09`: after a forced 412 the proposed name stays; saving over theirs writes version 3.

### A-10 · P2 · Failed watchlist edits were silent — **Fixed**

- **Correction.** Watchlist edits use one shared `saveToggle`, which re-applies a set edit once after a conflict. A failure shows "Could not remove AMFI …", keeps the requested change for **Try again**, and the header reads "Not saved: removing … · last saved version N". The fund-page star shows its own failure and retry, and names its destination list.
- **Files.** `workspace.ts`, `routes/workspace.tsx`, `components/CompareTray.tsx`.
- **Verification.** Browser `A-10`: a 503 shows the alert and status; retry succeeds.

### A-11 · P2 · Switching notes discarded unsaved text — **Fixed**

- **Correction.** Note drafts live in the draft store, so they survive opening another note or page. The record list marks "Unsaved draft". **Discard changes** is explicit. The browser warns before a reload or close while any draft exists.
- **Verification.** Browser `A-11`.

### A-12 · P2 · Brush spoke pixels; chart focus was hidden — **Fixed**

- **Correction.** The Recharts Brush is replaced by two native range inputs over an overview line. Each is named "<chart>: start date" or "… end date", and its `aria-valuetext` is a date. Arrows move a day; Page Up and Page Down move further. The thumbs show a visible focus ring. **Show all dates** resets the zoom. The CSS that hid chart focus now hides it only for pointer focus.
- **Files.** `components/charts.tsx`, `mf.css`.
- **Verification.** Browser `A-02` (keyboard zoom, date value text) and `A-12` (visible outline). A human screen-reader session is still outstanding (section 4).

### A-13 · P2 · Compare table showed index values — **Fixed**

- **Correction.** The table shows rupees from ₹10,000, the chart's unit, on dates kept by the extremum-preserving `thin`.
- **Verification.** Browser `A-13`: the first row reads ₹10,000.

### A-14 · P2 · Backtest growth was drawn before the return — **Fixed**

- **Correction.** `growthByMonth` starts at 100 on the first signal month's end and books each return on the holding month's end. The table adds "Return earned to". The hold-out band starts at the end of its first signal month.
- **Files.** `series.ts`, `routes/studio.tsx`.
- **Verification.** `series.test.ts` (Oct 2019 → 100 on 31 Oct, +0.591268% on 30 Nov; leap February). Browser `A-14`.

### A-15 · P2 · No mixed-revision guard — **Fixed**

- **Correction.** The shell watches every active MF query. When reads on screen report different `data_revision` values, a banner says new data was published while the page loaded. One button refreshes every section. A replay pinned on purpose is left out.
- **Files.** `queries.ts`, `components/MfShell.tsx`.
- **Verification.** Browser `A-15`: an injected older revision on `/score` raises the banner; refresh clears it. This is fault injection, as in the audit; no real publication race was available.

### Original findings still Partially Fixed in the audit

| ID | Now | Through |
|---|---|---|
| F-04 search relevance | Fixed | A-06, A-07 |
| F-05 Match any | Fixed | A-08 |
| F-10 failed-save message | Fixed | A-10 |
| F-10b conflict draft | Fixed | A-09 |
| F-07 raw `worst_1y` against rolling minimum in Compare | Unchanged | Not in the audit's defect register. Section 4 lists it. |

## 3. Visual and UX changes

| Area | Audit finding | Change | Evidence |
|---|---|---|---|
| Discover | Hero took ~400 px; ideas below the fold; sparkline unlabeled | Two-column hero: search and collections beside a **Market today** panel built from the proxy's current regime window, its last 12 months and the T-bill rate. The four fact cards become one line. Ideas and Your research move into the first viewport. Category sparklines say "Top fund's NAV, 3 years", not a category average. | [after](screens/d-discover-viewport.png) · [audit candidate](../independent-audit-2026-10-23/candidate/screens/d-discover-viewport.png) |
| Fund header | Tall header on every tab; verdict always led with a crash | Overview pairs a **Recent** line (1Y against the category median and percentile, distance below peak) with the **Worst fall** line. Other tabs use a one-row identity strip (name, plan, status, score, NAV). On phones the three key numbers come before the narrative. | [overview](screens/d-fund-overview-viewport.png) · [risk](screens/d-fund-risk-viewport.png) · [phone](screens/m-fund-overview-viewport.png) |
| Risk tab | Chart below tiles | The underwater chart comes first, with a named trough and zoom | [after](screens/d-fund-risk-viewport.png) |
| Scatter | Labels stacked vertically; one highlight colour | Single-line labels with a halo, alternating above and below. Each fund keeps its growth-chart colour. | [compare](screens/d-compare.png) · [frontier](screens/d-studio-frontier-viewport.png) |
| Lab | Phone opened on a long form; layout shift; generic tax caption | Result first on phones, with an "Edit inputs" summary link. The result column reserves height. Tax captions are kind-specific. | [phone](screens/m-lab-debt-viewport.png) · [desktop](screens/d-lab-debt-viewport.png) |
| Touch targets | 20 px info and 32 px change buttons | 44 px hit areas through a layout-free pseudo-element; phone tray gains **Clear** | Browser test "information buttons have a 44 px touch area" |
| Screener | Percentile scope unclear | The top/bottom-% hint says it ranks the whole snapshot, and points to category percentile fields | `ConditionEditor.tsx` |
| Load | 658 kB entry chunk; >500 kB warning | **Tried and reverted.** Loading the stock shell and the stock app's settings import as separate chunks cut the entry to 249 kB. It also delayed the stock app's first render, and two Momentum25 browser tests failed: an immediate Ctrl+K and a chart-layout switch. With the original `main.tsx` restored, both spec files pass 52/52. Momentum25 behaviour comes first, so the entry stays at 658 kB (section 4). | Section 5 |

The theme stays in `theme/themes.ts`; new colours use existing tokens only. The light and dark axe sweep passes (section 5).

## 4. Remaining issues — explicit

**Open P2 and usability items**

- U-11 nested group editor: a nested group still shows as one chip and cannot be edited. Match any now keeps it valid (A-08).
- Linked crosshairs across charts, and annotations beyond the deepest-fall dot.
- A compact analyst density setting for the screener, and a beginner shortlist layout.
- F-07 follow-up: Compare's raw `worst_1y` (−21.5%) sits beside the rolling minimum (−21.3%) used elsewhere. The label difference needs one explanation everywhere.
- U-08 shared research context: a fund set, period and pinned snapshot do not yet travel across Screen → Fund → Studio → Compare → Lab. Only the scenario replay pins a revision. A-15 warns on mixed revisions; it does not pin them.
- Mobile header density on the Overview tab remains high. Other tabs are compact.
- Entry bundle: 658 kB minified, with the >500 kB build warning. A split that keeps the stock app's first render as fast as today needs its own change. One option is to preload the settings import on stock routes while `/mf` skips it. Section 3 records the reverted attempt.

**Not performed**

- Human screen-reader session, physical phone, matched investor task study and an authenticated Tickertape comparison.
- A true publication race; A-15 is verified by fault injection only.
- Production performance percentiles. Only the entry size was measured.

**Product scope the audit lists as incomplete (unchanged)**

- Data dependencies E1 (TER, AUM, exit loads, manager, riskometer), E3 (benchmark TRI), E4/E7 (holdings), E5 (IDCW total returns).
- Software: W2 alerts, W3 decision briefs and original/latest evidence diff, the Slice 5 AI research runtime, Slice 6 CAS and portfolio intelligence, the S1 forward goal planner, and an approved category series.

These keep the complete Wickstreet 2.0 scope open. This remediation does not claim category leadership over Tickertape; that needs the independent review and user study above.

## 5. Verification

| Check | Result |
|---|---|
| Backend suite, dedicated `momentum25_test` | **1,416 passed, 13 skipped** (audit: 1,414 / 13) |
| Ruff, import-linter | Clean; **9 contracts kept, 0 broken** |
| Web unit tests (Vitest) | **211 passed** (audit: 193) |
| ESLint, TypeScript | Pass |
| MF browser suite, fresh preview build | **56 passed** (37 prior + 19 new) |
| MF browser suite, served port 8000 (`MF_BASE_URL=http://localhost:8000`) | **56 passed** — includes the light/dark axe sweep and phone checks |
| Momentum25 browser regression, full suite, final code, fresh `wickstreet_remediation_final_e2e` | **236 passed, 8 skipped, 0 failed** of 244 (the audit's run stopped at 160) |
| Served artifact | `index-CKzs1glZ.js`, 657,896 bytes, SHA-256 `66ec2eb71e9449f0751d64873bbd55bb42b39f6a92dc29a09ad8108a33a684e9`. The local `web/dist` build of the same source is byte-identical. |

The opt-in real-data backend suite was not run; its new `nippon india` assertion was checked by hand against the live API (A-07). All browser workspace calls used the in-memory mock. Momentum25 browser tests used new `wickstreet_remediation*_e2e` databases in the test container: the seed refuses a used database, and none was deleted. No real personal workspace record was read or changed.

**Screenshots.** `screens/` holds desktop (1440×1000; `-viewport` and full page) and phone (390×844) captures of the served app, made by [capture.mjs](capture.mjs) with workspace calls answered empty. The audit's `screens/` and `candidate/screens/` are the before images.
