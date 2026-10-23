# Claude Opus handoff — resume from verified evidence

**Status: safely paused at owner's request. Do not repeat this audit.**

Read [REPORT.md](REPORT.md) first. It contains the complete defect register, original F-01–F-19 remediation matrix, screen reviews, calculations, source references, competitor assessment and acceptance criteria. Preserve this directory and the original audit/remediation evidence.

**Verdict: Requires Further Remediation.** Latest source candidate **7.2/10** (weighted 7.23), versus previous published **6.9/10**. Actual port-8000 app **6.7/10** (weighted 6.67). The served frontend differs from the candidate; do not treat their results as interchangeable.

## Fix next, in order

1. **A-03 · P0 — calendar tax thresholds.** `backend/src/wickstreet/analytics/domain/tax.py` uses 365/730/1095 days. Exact 12 calendar months across a leap year is misclassified. Fund 122639, ₹10 lakh, 24 Jul 2023–24 Jul 2024: reported tax ₹32,653.73, expected ₹78,245.97 under the tested assumptions. Correct calendar anniversaries and cover before/on/after boundaries. Evidence: `evidence/api/tax-12m-anniversary.json`, `evidence/independent-financial-results.json`.
2. **A-04 · P1 — remove the silent equity-tax default.** `routes/simulate.tsx` initialises all funds as equity. HDFC Corporate Bond 118987 automatically shows ₹271.53 tax instead of ₹21,647.40 with debt treatment at 30% slab. Require authoritative or explicitly confirmed classification; invalidate confirmation when the fund changes.
3. **A-02 · P1 — preserve chart extrema.** `components/fund/Risk.tsx` and `components/charts.tsx:thin` drop the 24 Mar 2020 −31.2021% trough. Plot shows only −26.8098%; its table only −19.1684%. Preserve event anchors/extrema, restore full-resolution zoom and accurate accessible tables. See `screens/probe2-drawdown-omitted-trough.png` and `evidence/followup.json`.
4. **A-05 · P1 — replay every saved scenario parameter.** `routes/workspace.tsx:201` passes only kind/code to the Lab. Restore amount, day, dates, step-up, target and tax/slab; save provenance. The isolated ₹25,000/day-15 scenario reopens as ₹10,000/day-1 with default dates.
5. **A-06/A-07 · P1 — search identity and relevance.** Block selection of previous-query results while the new query is pending. Rank current plans ahead of historical phrase matches for broad AMC queries. `nippon india` currently returns eight historical IDCW plans without a Historical badge.
6. **A-08 · P1 — nested Match any.** `view-spec.ts:filterOf` adds a third group level to valid saved nested views. Backend returns 422 after retries. Preserve valid logical trees or prevent unsupported transformations without losing the last-good view.
7. **A-09 · P1; A-10/A-11 · P2 — all-field draft/write reliability.** Rename conflict refetch replaces the local proposed name while saying it remains. Watchlist PUT failures render no error. Switching notes discards unsaved text. Extend the successful note-text conflict handling to every field and record kind.
8. **A-12–A-15 · P2 — semantics/context.** Date-labelled brush values and visible chart focus; comparison table currency consistent with ₹10,000 chart; backtest points at realised next-month endpoints instead of signal-month day 28; shared revision guard/context. Revision-drift reproduction was fault-injected, not a real publication event.
9. **A-01 · P1 — validate and deliver one exact artifact.** Port 8000 entry is `index-JwG64Xyp.js`; rebuilt candidate is `index-BD6rybRp.js`. Fix source defects first, then run release checks against the exact delivered build. Do not replace the app merely to make this audit appear passed.

Full acceptance criteria and screenshots are in report sections 6 and 12. After these gates, address mobile result-first hierarchy, linked/full-resolution charts and compact evidence-led composition. Complete E1/E3/E4 fund facts plus W2/W3, AI and portfolio implementation for the accepted full 2.0 scope; these are not all external-data blockers.

## Completed checks — retain their results

- Web: **193 unit tests passed**, lint/typecheck pass, independent frontend build pass.
- Backend: **1,414 passed, 13 skipped** on dedicated test DB; **9 architecture contracts kept**.
- MF browser suite: **37 passed on candidate**; **23 passed/14 failed on actual port 8000**. Some served failures are old role/copy selectors; do not count them as 14 distinct product defects.
- Independent financial reconstruction: **157 pass, 1 tax-boundary failure**.
- Screening: **160/160 field coverage checks pass**.
- Backtest: **83/83 months/pick lists match**, rebuilt from **47 funds' raw NAVs**.
- Candidate accessibility: **40 route/theme combinations, zero axe violations**; manual semantics defects still exist.
- Real-Postgres concurrency: **one 200/five 412** for six same-version writes; winning record survives a fresh app lifespan.

## Incomplete / not certified

- **Momentum25 browser regression stopped at owner's request:** **153 passed, 6 skipped, 1 interrupted, 84 not run**. No completed-test failure observed. Interrupted case: `m14-studio.spec.ts` matured hold-out test. Do not call this a full regression pass. Logs/results are in `evidence/momentum-browser*`.
- No authenticated Tickertape/Pro walkthrough, physical phone, human screen-reader session or investor usability study.
- Real responses all used revision 2801. A true publication race was unavailable; only isolated metadata drift was injected.
- Performance measurements are single cold laboratory observations, not production percentiles.
- The opt-in backend real-data test suite was skipped; separate independent raw-API reconstruction was completed as described above.

## Environment and preservation

- Application source was not modified. Nothing committed or pushed.
- Port 8000 was not rebuilt or replaced. The temporary candidate preview on 8767 was stopped.
- Browser workspace calls used isolated mocks. No real personal workspace record was edited.
- Backend tests used `momentum25_test` on port 65479. Momentum25 browser tests used newly created `wickstreet_independent_audit_e2e` on port 65480. The concurrency record was archived in the test DB.
- Temporary Momentum25 harness: `/private/tmp/wickstreet-independent-audit-20261023/web`. Its evidence paths were isolated from previous audits.
- Independent source build: `/private/tmp/wickstreet-independent-build-20261023`.
- `screens/`, `candidate/screens/`, `comparisons/`, `evidence/` and `scripts/` preserve the review. Financial/provenance claims should cite these exact artifacts.

The next agent should implement fixes only after receiving authorisation for application changes. This session was review-only and is now paused.
