# Wickstreet 2.0 — independent acceptance review

**24 October 2026 · IST · http://localhost:8000/mf**  
**Verdict: Further Remediation Required. Overall: 7.8/10 (weighted 7.78).**

The remediation is substantial and mostly works: **14 findings Verified Fixed; A-04 Partially Fixed; none Unresolved or Regressed.** The delivered frontend now matches the reviewed artifact. Drawdown truth, anniversary tax, search selection, scenario replay and workspace recovery have improved materially.

Two issues prevent acceptance as a premium consumer release: **an overseas fund still receives an incorrect automatic tax result, and the delivered mobile experience takes roughly 7–8 seconds to render under the documented constrained profile.** This is a considerably stronger research candidate, but neither visual excellence nor an overall advantage over Tickertape is established. Keep moving forward with the product; do not repeat the comprehensive audit or redesign everything.

Unavailable datasets and explicitly Planned capabilities are **not defects or additional acceptance gates** here. This verdict concerns the delivered research UI, not completion of every future Wickstreet capability.

## 1. Scope and evidence

Reviewed the mandatory [independent audit](../independent-audit-2026-10-23/REPORT.md), [handoff](../independent-audit-2026-10-23/HANDOFF-CLAUDE-OPUS.md), [remediation report](../independent-remediation-2026-10-24/REPORT.md), [Codex design atlas](../wireframes/index.html), its Fund Intelligence artboard, design/interaction contracts, and both [owner reference A](../audit-2026-10-23/refs/owner-ref-a-app-screens.png) and [reference B](../audit-2026-10-23/refs/owner-ref-b-visual-proposal.png). Existing before images are linked below, not copied.

The checkout is **9eaabc3**, whose changes after **c70edf6** are audit documentation/scripts only. The actual port-8000 entry is **index-CKzs1glZ.js**, **657,896 bytes**, SHA-256 **66ec2eb71e9449f0751d64873bbd55bb42b39f6a92dc29a09ad8108a33a684e9**. It matches local `web/dist` and the remediation's recorded artifact. This review did not rebuild or replace the deployment. [Live artifact/API evidence](evidence/api-checks.json), [local hash](evidence/local-build.json).

Executed targeted checks, rather than full regressions:

- **19/19 remediation browser tests** against port 8000, plus **2/2 accessibility/keyboard tests**, covering 19 routes in light/dark (38 route/theme combinations). [Browser log](evidence/targeted-browser.log), [accessibility log](evidence/accessibility.log).
- **31/31 focused frontend tests** and **3/3 tax tests**, including 12/24/36-month boundaries. [Frontend](evidence/targeted-unit.log), [tax](evidence/tax-unit.log).
- Independent raw-NAV drawdown reconstruction; four live equity tax dates around the rate change/anniversary; debt and ambiguous-class checks; active/historical searches; missing-snapshot response; nested-filter predicates on 100 returned rows. [Requests, results and calculations](evidence/api-checks.json).
- Independent browser save → leave → replay for **SIP, lump sum, SWP and STP**, checking exact requests and provenance; comparison currency/period persistence; responsive captures at 1440, 768, 390 and 320 px; nine cold mobile measurements. [Independent probe results](evidence/browser-checks.json), [script](scripts/browser-checks.cjs).
- Manual live Edge inspection of Discover/search, the tax failure and Risk, alongside screenshot inspection. All automated workspace calls were intercepted in memory; **no real workspace record was edited**. Database restart durability/concurrent-write behavior uses the previous [real-Postgres evidence](../independent-audit-2026-10-23/evidence/workspace-concurrency.json), not a newly claimed database test.

Application code unchanged. No commit or push. An initial sandbox-prevented browser run and two capture-selector mistakes were corrected; they were harness failures, not product regressions. Final logs/results above are the completed runs.

## 2. Weighted scorecard

Scores judge the delivered product. Tests establish behavior; they do not establish taste or category leadership.

| Dimension | Weight | Previous candidate | Current | Reason |
|---|---:|---:|---:|---|
| Visual design | 25% | 7.8 | **8.0** | Distinctive paper/ink identity and coherent dark theme; more useful Discover composition. Repeated cards, oversized Overview and weak analytical hierarchy remain. |
| UX and navigation | 20% | 7.0 | **7.7** | Reliable search/replay/recovery close core journey failures. Period/snapshot continuity and editable nested screens remain incomplete. |
| Financial visualisations | 20% | 6.8 | **7.9** | True trough, meaningful zoom, dates, currency and backtest endpoints repaired. Still a collection of largely separate charts rather than a coordinated investigation surface. |
| Functional correctness | 15% | 6.8 | **7.4** | Broad targeted checks pass; automatic overseas tax remains materially wrong. No penalty for Planned features or absent datasets. |
| Mobile experience | 10% | 7.0 | **7.4** | Result-first Lab and compact non-Overview tabs help. Overview fills the first screen; compact Risk identity truncates heavily; cold rendering is slow. |
| Engineering quality | 10% | 8.0 | **8.1** | Delivered-build parity, error recovery, drafts and revision warning are stronger. Initial transfer and rendering remain below a consumer release standard. |
| **Weighted** | **100%** | **7.23 → 7.2** | **7.78 → 7.8** | **+0.6** versus published 7.2; **+0.9** versus initial 6.9; **+1.1** versus previously served 6.7. |

The main improvement is restored trust and usable task completion. Visual quality improves modestly; it has not suddenly become a 9/10 product.

## 3. A-01–A-15 verification matrix

“Verified Fixed” applies to the original reported defect and the tested scope, not every possible future edge case. Browser recovery/revision failures below are controlled fault injection.

| ID | Classification | Independent evidence |
|---|---|---|
| A-01 Served/source mismatch | **Verified Fixed** | Live entry bytes/hash match `web/dist` and remediation identity; all 19 focused browser tests run on that exact served path. No candidate-preview substitution. |
| A-02 Dropped deepest fall | **Verified Fixed** | Rebuilt from **2,470 valid raw NAVs**: **−31.202149% on 24 Mar 2020**, exactly matching `/underwater`. Browser confirms marker, date-valued keyboard zoom and table trough. Extrema/zoom tests pass. [Current chart](screens/d-risk.png). |
| A-03 Calendar tax boundaries | **Verified Fixed** | ₹10 lakh, 122639, 24 Jul 2023 → 24 Jul 2024: **₹78,245.97**, all short term. Live 22/23/24/25 Jul cases match independent rate/exemption arithmetic; unit checks cover 12/24/36 months, leap day and month end. This is not a certification of every tax-class rule. |
| A-04 Automatic tax class | **Partially Fixed** | 118987 defaults to debt and **₹21,647.40**, with no explicit class sent. UTI index returns `tax_class_needed`; fund change clears manual choice. **119517 still silently defaults to equity and returns ₹0 instead of approximately ₹15,320.16** in the historical case below. |
| A-05 Scenario replay | **Verified Fixed** | Independent actual UI saves/replays all **four kinds**, preserving amounts, dates, day, step-up, target, class/slab and snapshot provenance as applicable. Missing revision 1 returns 404; UI provides latest-snapshot recovery. Workspace persistence is mocked in this browser run; prior database durability evidence is retained. |
| A-06 Stale search selection | **Verified Fixed** | Delayed SBI response: Enter and forced click on old Parag result cannot navigate; selection works after current response. Shared `current` guard covers click, Enter and active descendant. |
| A-07 Historical plans outrank active | **Verified Fixed** | Live `nippon india`, `hdfc`, `sbi` open on active Direct Growth plans; historical code 144891 remains findable. Browser checks historical grouping and dated badge. Liquid-first within a broad AMC query is acceptable relevance, not a suitability recommendation. |
| A-08 Nested Match any fails | **Verified Fixed** | Saved nested example switches without 422 and sends depth ≤2. Filter helper equivalence tests pass. Independent API check: all **100/100** inspected results obey active/direct/growth gates and the OR predicate (792 matched overall). **Editing the nested group remains a separate limitation.** |
| A-09 Rename conflict loses draft | **Verified Fixed** | Injected 412 preserves proposed name; copy and explicit overwrite/discard choices remain; overwrite saves version 3. Shared field-draft implementation inspected. |
| A-10 Silent watchlist write failure | **Verified Fixed** | Injected 503 produces visible unsaved status, specific failed removal and retry; retry completes. Fund-star failure path also inspected in source. |
| A-11 Note switching loses text | **Verified Fixed** | Switch A → B → A retains A's unsaved text and marks the draft. Drafts survive route-component unmount; reload protection is a warning, not durable draft storage. |
| A-12 Pixel brush/hidden focus | **Verified Fixed** | Native date-labelled handles expose `aria-valuetext`; keyboard focus has a visible outline; served axe/keyboard checks pass. Human screen-reader use remains untested. |
| A-13 Comparison table units | **Verified Fixed** | Independent **201-row** table check: rupees throughout; initial row **₹10,000 for all three funds**, last row ₹46,362 / ₹41,343 / ₹32,865. |
| A-14 Backtest dated too early | **Verified Fixed** | `growthByMonth` now anchors 100 at signal-month end and realizes returns at next month end; date/compounding tests and live table endpoint check pass. Existing 83-month NAV reconstruction is referenced, not rerun. |
| A-15 Mixed-revision guard | **Verified Fixed** | Injected older `/score` revision raises the banner; refreshing all sections clears it. Intentionally pinned scenario reads are excluded. **This warns on mixed reads; it does not implement shared snapshot continuity.** |

Evidence for named browser checks is in [targeted-browser.log](evidence/targeted-browser.log); independent extensions are in [browser-checks.json](evidence/browser-checks.json) and [api-checks.json](evidence/api-checks.json).

## 4. Before/after visual acceptance

| Area | Before → current | Assessment |
|---|---|---|
| Discover | [Prior candidate](../independent-audit-2026-10-23/candidate/screens/d-discover-viewport.png) → [current](screens/d-discover.png) | Better: useful market context, ideas and research appear together. Hero remains substantial, but now earns more of its space. Abstract landscape has less craft than the owner artwork; commissioning decoration is not a release gate. |
| Fund Intelligence | [Prior Overview](../independent-audit-2026-10-23/candidate/screens/d-fund-overview-viewport.png) → [current](screens/d-fund-overview.png) | Recent underperformance now balances the score and historical crash. However score, returns and downside repeat in header, insight strip and metric cards. The main analytical chart remains below the 1000 px viewport. This falls short of the owner's compact, chart-led signature screen. |
| Risk | [Omitted trough](../independent-audit-2026-10-23/screens/probe2-drawdown-omitted-trough.png) → [current](screens/d-risk.png) | Strongest improvement: the question, actual deepest fall and chart now lead. Correctness and hierarchy both improve. |
| Compare | [Prior](../independent-audit-2026-10-23/candidate/screens/d-compare.png) → [current light](screens/d-compare.png), [dark](screens/d-compare-dark.png) | Readable dates, units and consistent colour across growth/scatter; annotations now support analysis. Still lacks linked investigation across compatible charts. |
| Mobile | [Earlier Lab](../independent-audit-2026-10-23/candidate/screens/m-lab-sip-viewport.png) → [current Lab](screens/m-lab.png); [Overview](screens/m-fund-overview.png), [Risk](screens/m-risk.png) | Lab outcome is visible immediately. Overview uses virtually the entire first viewport for identity/score/narrative before tabs/charts. Risk is faster to reach, but its compact header reduces the name to “Parag …”. A responsive layout is present; a polished mobile research composition is still incomplete. |
| Screening | [Current desktop](screens/d-screener.png), [phone](screens/m-screen.png) | Controls and actions are legible; long names compete with width and relatively few rows fit. Phone's first result begins well down the screen. Density is a worthwhile next improvement, not evidence the screen is broken. |

The visual direction is premium and contemporary, with readable Indian currency and coherent palettes. Current [Monsoon light](screens/d-monsoon-light.png) and [Monsoon dark](screens/d-monsoon-dark.png) Risk captures preserve hierarchy, loss semantics and readable dates; Paper light/dark is also shown above. No gross palette inconsistency or page-level overflow was observed in the sampled 1440/768/390/320 px layouts. For investors aged 18–35 it avoids obvious trading-terminal overload, while explanations expose substantial depth. Yet repeated dashboard cards weaken progressive disclosure, and the mobile page lengths and disconnected chart interactions stop it achieving the full **Groww simplicity + TradingView interactivity + Bloomberg analytical depth** ambition. The analytical substance is stronger than the composition.

## 5. Remaining material issues and acceptance criteria

### P0 · R-01 — overseas fund receives equity tax treatment automatically

**Reproduce:** open [this local Lab case](http://localhost:8000/mf/simulate?kind=lumpsum&code=119517&amount=1000000&start=2023-07-24&end=2024-07-25&slab=30). Leave tax class at “From the fund's category”. The live API returns gain **₹49,103.06868**, class `equity`, tax **₹0**; the browser explicitly attributes this to the category. [Screenshot](screens/d-overseas-tax.png), `overseas-tax-boundary` in [API evidence](evidence/api-checks.json).

The [AMC's scheme document](https://mutualfund.adityabirlacapital.com/-/media/bsl/bulkport/sid/sid---aditya-birla-sun-life-international-equity-fund-281125.pdf) specifies 90–100% foreign equity. The [AMC merger notice](https://mutualfund.adityabirlacapital.com/-/media/bsl/files/resources/addendums/2023/notice-for-merger-of-absl-international-equity-fundplanaandb-andcommodityequitiesfundglobalagriplan.pdf) identifies Plan A as the surviving international scheme. For these post-March-2023 units sold in FY2024-25, [AMFI's historical section 50AA explanation](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TaxRegimeForMutualFunds) supports slab treatment, not the domestic equity exemption. At the entered 30% slab: **₹49,103.06868 × 30% × 1.04 = ₹15,320.16**. This expected result is an inference combining the mandate, dated tax rule and actual API gain; it is not copied from another calculator. Explicitly choosing `other` in the same live API case also returns **₹15,320.16**, isolating the automatic-classification failure.

**Cause:** `tax_class_of` in `backend/src/wickstreet/analytics/domain/tax.py` equates broad asset class `Equity` with tax-qualified equity. SEBI investment category alone does not establish domestic-equity tax status. This is an unsafe inference, not a complaint about a missing dataset.

**Release acceptance:** this case must either calculate **₹15,320.16** under verified historical classification or withhold the automatic numeric estimate and require a supported explicit tax-class decision. No unverified overseas/thematic category may silently inherit domestic equity exemptions. Cover acquisition/sale rule transitions, domestic equity, debt, overseas, index/FoF and uncertain hybrids; preserve A-03's anniversary behavior. A conservative “class needed” fallback is an acceptable focused fix; acquiring all enrichment datasets is unnecessary.

### P1 · R-02 — slow delivered mobile rendering

**Reproduce:** cold Chromium at 390×844, cache disabled, 4× CPU slowdown, 150 ms network latency, 200,000 B/s download and 93,750 B/s upload; load each route three times through port 8000. [Script](scripts/browser-checks.cjs), [raw measurements](evidence/browser-checks.json).

| Route | Cold LCP, three runs | Median LCP | CLS | Decoded JS |
|---|---|---:|---:|---:|
| Discover | 7.088 / 7.104 / 7.104 s | **7.104 s** | 0.018 | 1.175 MB |
| Fund Overview | 8.256 / 8.268 / 8.256 s | **8.256 s** | 0.070 | 1.204 MB |
| Lab | 7.072 / 7.060 / 7.080 s | **7.072 s** | 0.035 | 1.174 MB |

These are repeatable single-machine lab observations, not population percentiles or measured INP. Layout stability is acceptable in these runs; the principal problem is late initial rendering. Entry transfer takes approximately 3.845 s under this profile.

The entry alone transfers **657,896 uncompressed bytes** despite `Accept-Encoding: gzip, br`; no `Content-Encoding` is returned. Total route JavaScript is larger. This is a measured delivery problem, not a finding based solely on Vite's 500 kB warning. The previous candidate preview's faster timings used a different serving path and cannot establish a product performance gain here.

**Release acceptance:** serve compressed static assets and reduce unnecessary initial work/transfer while preserving Momentum25's first-render keyboard and chart-layout behavior. Repeat this exact profile, three cold runs per route: **median LCP ≤3.0 s and CLS ≤0.10** for Discover, Fund Overview and Lab. Record encoded/decoded bytes. This is a proposed local acceptance budget, not a claim of field Core Web Vitals compliance. Do not require a particular chunk size if the actual budget is met.

### P2 · research continuity and advanced investigation — next product iteration

| Gap and reproduction | Impact / decision | Precise completion criterion |
|---|---|---|
| Compare → choose 1Y → reload: returns to All; “Test an investment” passes only first code. Fund/Studio periods and snapshot are not a shared research context. | **Material workflow limitation**, but disclosed per-view periods and A-15 warning prevent it being an immediate correctness blocker. | Preserve fund set, date window and intended original/latest revision through supported Screen → Fund → Studio → Compare → Lab paths, reload and Back. Explicitly explain when Lab operates on one fund. Test with two funds and a nondefault period/revision. |
| Open [A-08's valid saved nested view](screens/d-nested.png); its “Any of 2 conditions” chip cannot open either child for editing. | **Advanced-screener limitation**, not a recurrence of the fixed 422. Reasonable follow-up for this release slice; blocks claiming a complete advanced builder. | Open group, inspect/edit/remove either predicate, change AND/OR, cancel without mutation, save/reopen with identical valid semantics; retain fixed universe gates. |
| Studio/Compare charts have independent cursors and zooms; no compatible-date crosshair linking. | **Differentiation improvement**, not a release blocker. | On compatible time charts, one hover/keyboard date shows the same date across series; missing observations remain explicit; optionally lock and reset shared zoom. |
| Default screener shows few long rows; mobile Overview uses a screen of repeated header information; compact Risk truncates the fund name. | **Material composition opportunity**, not a fresh calculation defect. | At 390×844 keep exact fund identity and one useful chart/insight with a next action available; reduce repeated score/narrative. Offer optional dense screener geometry without tiny text or losing row actions. |

Compare's separate raw `worst_1y` versus rolling minimum still deserves a short method explanation (−21.5% versus −21.3% in the representative fund). This is a P2 interpretation refinement, not a newly established numerical failure.

## 6. Competitive acceptance

Public Tickertape fund/screener pages and primary feature documentation were refreshed for this review; existing local competitor screenshots are reused. No authenticated/Pro walkthrough or matched investor task study was performed.

| Position | Actual research task / evidence |
|---|---|
| **Exceeds the inspected public experience** | Explaining NAV downside and reproducibility: Wickstreet exposes the exact deepest fall/recovery, transparent score parts, accessible chart tables and replayable scenario provenance together. Its calm, promotion-free presentation also gives the core research task more focus. This is a bounded reviewer judgment, not a claim about unseen Pro tools. |
| **Parity in core capability** | Finding a plan, category shortlisting, custom conditions, historical returns, peer comparison and saving research are credible. Tickertape also documents custom filters, rolling metrics and drawdown; 160 fields is not itself a competitive win. [Tickertape screener documentation](https://www.tickertape.in/knowledge-base/modules/evaluating-mutualfunds/mf-screener/), [public collections](https://www.tickertape.in/screener/home/mutual-fund?switch=true). No claim of equal search speed/task success is made. |
| **Falls behind in complete investment decisions** | The [public Tickertape fund page](https://www.tickertape.in/mutualfunds/parag-parikh-flexi-cap-fund-M_PARO) supplies expenses, exit loads, benchmark identity, portfolio sections and manager context. Wickstreet's NAV analysis cannot yet answer the same whole-fund decision. These are competitive scope limits, **not defects assigned to unavailable datasets**. Its tax failure and measured mobile delay additionally weaken trust and convenience today. |
| **Cannot reliably compare** | Authenticated portfolio/AI/alerts, Pro chart depth, full mobile performance, real-user task time and suitability outcomes. Planned Wickstreet services are excluded from defect counts; no absence of a competitor feature is inferred from a public page. |

**Substantially better overall research experience: not demonstrated.** Wickstreet is meaningfully closer, especially for downside explanation and reproducible NAV research. A novice can now discover, screen, inspect, compare and save with far fewer broken steps; the overseas tax case still breaks the decision chain. Analytical depth and an attractive theme do not alone surpass a mature research product.

## 7. Five highest-impact improvements

1. **Make automatic tax classification safe**, with dated treatment or explicit uncertainty. This is the principal correctness gate.
2. **Fix delivered mobile loading**, starting with compression and measured initial dependencies. Validate behavior, not just bundle warnings.
3. **Carry research context across tools**, preserving selected funds, periods and snapshot intent instead of making users reconstruct their question.
4. **Make Fund Intelligence the signature composition:** one compact identity, one balanced evidence summary and the primary chart; disclose repeated score/method detail on demand. Preserve full mobile identity.
5. **Complete the analyst interaction loop:** editable nested groups and synchronized compatible chart dates; then offer a denser screener view. These create more research value than decorative polish.

**Decision:** fix R-01 and meet R-02's delivered rendering budget, then reconsider acceptance through a narrow confirmation of those two gates and smoke checks for the affected paths. P2 items guide the next product iteration; none requires repeating the full audit. No new datasets or Planned features are demanded to close this review.

**Not completed / not certified:** physical phone, human screen reader, investor usability study, authenticated Tickertape/Pro, real publication race, production percentile performance, a new full backend/Momentum25 regression, or database restart durability in this review. Prior successful suites are attributed to the remediation report rather than presented as newly executed.
