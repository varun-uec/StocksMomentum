# Wickstreet 2.0 — independent product, UI and correctness audit

**Audit date:** 23 October 2026, IST  
**Repository:** `ab993516ed4f47f3ef490a8c295004ba6739fccf` (`wickstreet/m10-m11`)  
**Requested application:** `http://localhost:8000/mf`  
**Latest frontend candidate:** independently rebuilt, then examined separately from the frontend already served on port 8000  
**Data:** revision 2801; NAV as of 22 October 2026; analytics method 5; sources AMFI, RBI and Tigzig  
**Recommendation:** **Requires Further Remediation**  
**Latest candidate score:** **7.2/10**. **Actually served application:** **6.7/10**. Previous assessment: 6.9/10.

**Safe-point status:** Report and evidence saved at the owner's request. Audit-only browser checks and the separate candidate server were stopped. The Momentum25 browser run is explicitly incomplete below. No application source was modified, committed or pushed. No real personal workspace record was edited.

## 1. Executive verdict

The remediation is meaningful, particularly in the latest source build: proper time axes, visible screener actions, useful first-use examples, sparklines, a historical frontier, clearer fund evidence, sliders, zoom and a better phone fund header. The analytical foundation is substantial. Independent calculations agreed with the representative NAV returns, rolling statistics, risk ratios, correlations, cash-flow simulations and every month of the default selection backtest.

**The claim that all defects are resolved is too broad, and category leadership is not established.** Three findings change the readiness decision:

1. **The delivered frontend differs from the reviewed source.** Port 8000 serves an earlier bundle. It lacks several claimed improvements and fails 14 of the 37 current MF browser tests. The separately served latest candidate passes all 37. Those are different artifacts and cannot share a release sign-off.
2. **Trust defects remain outside the existing tests.** The tax engine misclassifies an exact 12-calendar-month holding across a leap year. The Lab defaults a real debt fund to equity taxation. Uniform chart sampling removes the actual maximum drawdown. Saved scenarios reopen with different inputs. Search can select an old result for a new query. Rename conflicts discard the proposed name while saying the text remains.
3. **The complete accepted product is unfinished.** Fund costs, holdings and benchmark research need datasets; alerts, decision briefs, snapshot replay, AI research and portfolio intelligence also need implementation. The accepted scope retains these in 2.0. Clearly marking them Planned is good UX, but does not complete the product.

**Keep this as an internal research candidate. Do not sign off the requested app or the complete Wickstreet 2.0 ambition yet.** Fix the financial and persistence defects, deploy the exact validated artifact, then complete the investment-decision workflow and the missing capabilities. More decorative cards will not resolve the principal gaps.

### Most consequential evidence

| Finding | Observed result | Evidence |
|---|---|---|
| Risk chart understates the deepest fall | True trough **−31.2021% on 24 Mar 2020**; plotted minimum **−26.8098% on 26 Mar**; sampled table minimum only **−19.1684%** | [Chart and tooltip](screens/probe2-drawdown-omitted-trough.png), [numeric probe](evidence/followup.json) |
| Incorrect historical tax | ₹10 lakh, 24 Jul 2023–24 Jul 2024, equity: app **₹32,653.73**; calendar-month treatment **₹78,245.97**; difference **₹45,592.24** | [Browser](screens/probe2-tax-boundary.png), [API case](evidence/api/tax-12m-anniversary.json), [independent results](evidence/independent-financial-results.json) |
| Wrong tax default for debt | HDFC Corporate Bond, code 118987, default SIP: auto-selected equity tax **₹271.53**; explicitly selecting debt at 30% slab produces **₹21,647.40** | [Default](screens/probe3-debt-default-equity-tax.png), [corrected input](screens/probe3-debt-correct-tax.png) |
| Saved scenario does not replay | Saved ₹25,000/month, day 15, 10% step-up, custom dates; reopened as ₹10,000, day 1, no step-up, default dates | [Saved record](screens/probe-scenario-saved.png), [reopened Lab](screens/probe-scenario-replayed.png), [inputs](evidence/interactions.json) |
| Different release artifacts | Served `index-JwG64Xyp.js`; independently rebuilt candidate `index-BD6rybRp.js` | [Build identities and performance](evidence/performance-builds.json), [independent build](evidence/independent-build.log) |

## 2. Method, baseline and limits

I inspected the requested [original report](../audit-2026-10-23/REPORT.md), its 82 screenshots and both owner references, the [remediation report](../remediation-2026-10-23/REPORT.md), the original design atlas/wireframes, UI contracts, accepted complete scope (doc 20), architecture and data dependencies, the latest changes, frontend components, backend analytics methods, HTTP contracts and tests. The original screenshots were reviewed through five contact sheets and relevant full-size comparisons. Existing evidence was preserved.

The live app was exercised with Chromium at **1440×1000 desktop, 768×1024 tablet, 390×844 mobile and 320×740 narrow mobile**. The existing suite additionally covers 1024 px and screener actions at 1280/1440/1920 px. Dedicated phone probes used touch/mobile emulation. These are browser emulations, not a physical-phone certification.

All browser workspace calls were intercepted with empty or isolated `ZZ-AUDIT-*` records. Financial reads used the actual local APIs and NAVs. Database writes used dedicated `*_test` or newly created `wickstreet_independent_audit_e2e` databases. The workspace concurrency record was archived in the test database. The user's application database and personal workspace records were not changed.

Evidence labels throughout:

- **Verified:** reproduced in a browser, actual API, independent calculation or named code path.
- **Judgment:** design evaluation, not an objective defect or user-study result.
- **Dependency:** an unavailable dataset or unimplemented service, distinguished below.
- **Fault-injected:** a controlled browser failure/concurrency/revision case; not a claim that today's live snapshot actually changed during this audit.

I did not perform an authenticated Tickertape/Pro walkthrough, physical-device testing, a human screen-reader session or research with investors aged 18–35. A genuine daily publication/revision change was unavailable; revision drift was tested by altering response metadata in an isolated browser. Slow-network measurements are individual laboratory observations, not production percentiles.

### The deployment mismatch is independently established

| Artifact | Entry bundle | SHA-256 |
|---|---|---|
| Port 8000 | `index-JwG64Xyp.js`, 657,727 bytes | `6241a1c1eb6be1caaba5eefb0058c08d89753aec85c25a3d7877a7837f0696c1` |
| Latest candidate | `index-BD6rybRp.js`, 657,800 bytes | `009d92cbbecb6a9b6febda9d7fd8912c257645f724f8b3bf623852e5130d9f5f` |

A fresh Vite build into `/private/tmp/wickstreet-independent-build-20261023` produced the same candidate entry filename. The candidate was examined on port 8767 without replacing port 8000. The candidate server was stopped at the safe point. Neither test result is silently substituted for the other.

## 3. Weighted scorecard

Scores are independent judgments. 10 means a category-leading investment-research experience; a passing test suite alone does not earn it. The baseline's underlying weighted sum was 6.95, displayed as 6.9; this report compares with the requested published 6.9.

| Dimension | Weight | Prior | Served app | Latest candidate | Evidence for candidate rating |
|---|---:|---:|---:|---:|---|
| Visual design and aesthetics | 25% | 7.0 | 7.2 | **7.8** | Strong editorial identity, coherent colours, monograms and real sparklines. Oversized hero/header, repetitive card grids and weak scatter labels remain below the owner's compositional standard. |
| UX and navigation | 20% | 6.5 | 6.2 | **7.0** | First-use examples and category-aware screening help. Search races, archived-fund relevance, replay defaults, lost drafts and incomplete shared context damage the research loop. |
| Financial visualisations | 20% | 6.0 | 6.3 | **6.8** | Time bands, ticks, frontier, cumulative backtest and brush improve materially. Dropped risk extrema, shifted backtest dates, inaccessible units and limited linked interaction prevent a high score. |
| Functionality and correctness | 15% | 8.0 | 6.8 | **6.8** | Representative calculations are strong; tax boundary/default errors and scenario/persistence failures are material. Complete 2.0 functionality is not implemented. |
| Mobile experience | 10% | 7.0 | 6.3 | **7.0** | Score and key actions now fit the first fund viewport; no page overflow observed. Lab results remain below a long form, header density remains high, some controls stay small. |
| Engineering quality | 10% | 8.0 | 7.2 | **8.0** | Scoped theme system, architecture contracts, extensive passing tests and optimistic concurrency are strengths. Release parity, missing error paths, revision guards and chart semantics need work. |
| **Weighted total** | **100%** | **6.9 published** | **6.67 → 6.7** | **7.23 → 7.2** | Candidate **+0.3** over the published baseline. |

The lower functionality score does not mean the numerical foundation deteriorated wholesale. This audit found cases the earlier review did not test. The source candidate improves the product; the newly established trust defects limit how much readiness credit it earns.

## 4. Original defect remediation matrix

This classification concerns the **latest candidate**, independently checked. Served-app exceptions follow the table. F-10b is listed separately because the original report described two conflict/save issues under F-10.

| Original ID | Classification | Independent evidence and remaining issue |
|---|---|---|
| F-01 Regime bands | **Fixed** | Twelve nonzero bands, correct crash/correction/recovery colours. DOM edges agree with API start dates within **0.001 day**. [Geometry](evidence/followup.json), [candidate chart](candidate/screens/d-studio-regimes.png). |
| F-02 Numeric axes | **Fixed** | Round gridlines and labels now agree with the 1–2–5 axis implementation and passing axis tests; browser frontier shows coherent 8/10/12/14/16/18% ticks. This does not fix lost chart extrema (A-02). |
| F-03 Hidden row actions | **Fixed** | Sticky right action column; all three existing viewport checks pass on the candidate. [Screener](candidate/screens/d-screen-viewport.png). |
| F-04 Search relevance/aliases | **Partially Fixed** | `parag`, `ppfas`, `sbi smallcap`, `axis bluechip`, code and ISIN succeed. Broad `nippon india` returns eight historical IDCW plans, with no historical warning. See A-07; new-query stale selection is A-06. |
| F-05 Match any/universe | **Partially Fixed** | Flat filters retain Active/Direct/Growth gates; both served and candidate send `ALL(gates, ANY(rest))`. A valid saved nested group becomes an unsupported third level when Match any is selected, yielding 422 after retries (A-08). |
| F-06 Category-relative default sort | **Fixed** | Default is Flexi Cap by score; a cross-category score sort warns and offers CAGR sorting. Top-ten below-median CAGR is possible under the disclosed multi-part score; that alone is not a calculation defect or grounds to silently change methodology. |
| F-07 Financial labels | **Fixed** | Risk says Worst 1-month window; its Worst 1-year tile and Performance both use rolling minimum −21.3%. Compare still exposes the separate raw `worst_1y` measure at −21.5%; explain the annualised/raw distinction consistently. |
| F-08 Peer counts | **Fixed** | Category card names 36 funds with 3 years of NAVs; fund score names 31 scored peers and explains complete-part eligibility; screener count is 46 eligible plans. [Fund overview](candidate/screens/d-fund-overview.png). |
| F-09 Invalid formula destroys screen | **Fixed** | Candidate parser preflight leaves invalid formula in the drawer, outside the URL/results; current regression passes. Port 8000 still fails this check. |
| F-10 Failed-save message | **Partially Fixed** | Notes now show a save-specific error and retain text. Watchlist body edits still fail silently because their mutation error is not rendered (A-10). |
| F-10b Conflict draft replacement | **Partially Fixed** | Notes offer Copy my text and explicit replacement wording. Rename conflict refetch overwrites the name draft, offers no copy and claims text is still here (A-09). |
| F-11 Unexplained blanks | **Fixed** | Trailing peer cells show a dash with screen-reader/hover reason: category figures cover 1/3/5Y. A tap-accessible reason would improve phones. |
| F-12 Exhausting default SWP | **Fixed** | ₹10 lakh corpus/₹6,000 monthly: 60 withdrawals, ending ₹12,50,995.66. Independently reconstructed. A different default-tax defect remains (A-04). |
| F-13 Developer Appearance text | **Fixed** | Removed in candidate; current browser test passes. Still present on port 8000. |
| F-14 Compare tray obstruction | **Fixed** | Candidate tray is 48 px, page reserves end padding, and the phone fund action bar replaces the tray on fund routes. Served app still overlaps the two bars. Remaining mobile density is a design issue, not evidence that the candidate fix is absent. |
| F-15 Irregular time ticks | **Fixed** | Numeric time scale, calendar-aligned ticks and readable years. Browser regime geometry independently checks date mapping. |
| F-16 Internal formula labels | **Fixed** | Friendly field labels and grouping; registry coverage checked across all 160 fields. Expression identifiers remain necessary arithmetic syntax. |
| F-17 Stretched cards | **Fixed** | Short Overview and Peers cards align to their own content height. [Six-tab contact sheets](comparisons/candidate-fund-tabs-1.png). |
| F-18 Missing backtest interpretation | **Fixed** | Explicitly states in-sample success and hold-out underperformance: 7.5% versus 8.4%. |
| F-19 Smoothed monthly backtest/caption | **Fixed** | Compounded growth and shaded hold-out caption replace the old presentation. The new wealth points are dated too early (A-14), a separate remaining defect. |

**Register count:** 16 Fixed, 4 Partially Fixed, 0 wholly Unresolved, 0 Regressed in the latest candidate. This does **not** mean release-ready: the new defect register below includes financial and persistence failures.

**Port 8000 exceptions:** hidden screener actions persist at 1280 and 1440 px; invalid formulas still replace the result with a request error; category-count wording and Appearance text are old; cross-category/gate explanatory copy is missing; first-use Compare is empty; hero search, sparklines and some newer chart additions are absent. Its phone compare tray overlaps the new fund action bar. Zoom charts retain an image role around focusable handles and fail axe. Some of the 14 browser failures are changed-role/copy selectors rather than 14 separate functional defects; the full results preserve that distinction.

## 5. Screen-by-screen evaluation

### 5.1 Discover and personalisation

**Verified improvement:** candidate desktop hero search, category and fund sparklines, fund-house monograms, equity-first idea ordering, rule explanation and a recent-research panel. The real snapshot and method remain visible. The result is more useful and visually richer than the original audit.

**Judgment:** the hero occupies roughly 400 px of the 1000 px desktop viewport. Registry facts plus a two-row category grid push actionable ideas well below the fold. The owner references combine search, compact category trends and useful ideas in a more integrated first composition. Current flat SVG trees are coherent with the brand but less distinctive than the reference landscape/collection artwork. The answer is a tighter composition and stronger research content, not additional decoration.

Personalisation is currently recent public funds and watchlists. There is no implemented investor profile, personalised allocation, portfolio-aware research or AI recommendation flow. Examples are identified, which is honest. Category sparklines are the top-scored **fund's** NAV, not an aggregate category series: label that distinction visibly beside the sparkline.

[Before / served / candidate](comparisons/discover-before-served-candidate.png). [Candidate full page](candidate/screens/d-discover.png).

### 5.2 Advanced Mutual Fund Screener

The candidate is substantially better: one-category default, protected universe gates, a warning on cross-category score sorting, sticky actions, small real charts and marks. Filters, URL view state, typed percentages, columns, formula validation and CSV provenance are valuable analyst tools. All 160 field availability counts match the registry; this is broader coverage testing, not a proof of every field's methodology.

Remaining verified problems are nested-group Match any failure (A-08), search selection/relevance (A-06/A-07), and unresolved shared revision context. Nested groups can run from a link but cannot be opened and edited in the UI. Users see an opaque group chip. This was disclosed previously and remains unfinished.

**Judgment:** default rows trade long fund names against a fixed sparkline and a wide filter rail. Two-line names still truncate; there is no compact analyst density setting. Mobile starts with substantial page/preset/filter chrome before the first result. Support a beginner shortlist layout and an explicit compact advanced view, with identical filter semantics. Explain whether percentile operators use the whole snapshot or category peers—the backend's top/bottom-% operators use the former.

[Screener comparison](comparisons/screener-before-served-candidate.png). [Phone filters](screens/probe-filters-390.png).

### 5.3 Fund Intelligence — all six tabs

| Tab | What works | Main remaining assessment |
|---|---|---|
| Overview | Strong fund identity, clear 98 score and 31-peer explanation, negative 1Y beside positive 3Y, key metrics, source-labelled proxy, distribution | Score repeats in header and body; generic deepest-fall verdict dominates current evidence. Growth/distribution remain below the first desktop viewport. No category or official benchmark line. |
| Performance | Trailing returns, calendar/FY bars, rolling series/distribution, monthly heatmap, partial-year hatching, missing reasons | Good depth. Charts use reduced samples and lack linked crosshairs; compare exact periods/units consistently. Long mobile page. |
| Risk | Plain-language tiles, underwater chart, episode/recovery tables, fund/proxy window bars and capture explanations | **A-02 is release-blocking:** chart and its data table omit the true deepest fall. No amount of visual polish compensates for that. |
| Peers & rankings | Rank history, peer counts, direction labels, direct/regular gap, near-duplicate correlation explicitly distinguished from holdings | Clear analytical value. Frontier/rank/selection contexts need consistent period/revision; historical ranks use current categories, appropriately disclosed. |
| Holdings | Dependencies honestly named; no fabricated exposure | Not implemented. Four Planned cards are an empty research destination, not competitive holdings intelligence. |
| Data & profile | Source ranges, valid NAV count, gap/anomaly coverage, first stored NAV versus launch distinction, exact identity | Good provenance. Missing costs/manager/riskometer facts prevent complete fund assessment. Revision metadata is displayed but not enforced across reads. |

For code 122639 the API score is 97.7778, the equal mean of 93.3333, 100 and 100. Three-year CAGR is 12.1780%, volatility 9.9231%, Sharpe 0.59685 and Sortino 0.84036. Independent calculations agreed. A 98 score is relative to this score's category and parts; it is not a recommendation or a universal safety grade.

**Judgment:** the repeated header is too tall across all six tabs, especially on phones. Replace repeated narrative with a compact identity strip after the first overview, while retaining plan, NAV date and risk context. A category-leading verdict should include current counter-evidence (for example 1Y relative weakness), not always lead with a historical crash. The reference's richer chart/metric balance is still missing.

[Six tabs, part 1](comparisons/candidate-fund-tabs-1.png), [part 2](comparisons/candidate-fund-tabs-2.png), [mobile comparison](comparisons/mobile-fund-before-served-candidate.png).

### 5.4 Analytics Studio — seven modes

| Mode | Verification / judgment |
|---|---|
| Rolling returns | Prepopulated, multi-fund chart, distribution/statistics and brush are useful. Sampled paths and unlinked interactions remain below TradingView-like investigation. |
| Drawdowns | Multi-fund comparison is useful, but uniform sampling can remove the most important loss dates. Zoom only cuts already-reduced data; it does not recover full resolution. |
| Peer rankings | Historical percentile and standing are useful; current-category caveat is present. Better linked date inspection is needed. |
| Risk–return | Correct round axes, frontier line and labelled selected fund improve the old map. Labels wrap into narrow vertical word stacks. Selected funds share a highlight colour; comparison identity is weaker than the growth chart. |
| Rank persistence | Counts and row shares, sample explanation and current-category caveat are good. It is historical frequency, not a predictive probability; the page says so. |
| Market regimes | Original broken block is fixed. Twelve accurately located bands plus fund/proxy bars are a real improvement. On phones, many small window labels still require the table for precision. |
| Selection backtest | All **83 months and picks** reconstructed from **47 funds' raw NAV histories** agree. Hold-out underperformance is stated. The cumulative chart's dates are wrong (A-14). A retrospective split is not itself proof of an untouched, prospective hold-out protocol. |

The Studio now starts with data; it is no longer an empty toolkit. It still behaves as a sequence of separate charts rather than a continuous investigative canvas with linked dates, context and explanations.

[Regimes before/after](comparisons/regimes-before-served-candidate.png), [frontier](candidate/screens/d-studio-frontier.png), [backtest](candidate/screens/d-studio-backtest.png).

### 5.5 Multi-fund Comparison

Candidate first use has three named example funds, a common-start banner, period controls, growth with brush, risk–return map, aligned metrics and correlation with observation counts. Cross-category scores are not presented as a universal winner. This is a sound base.

The chart's Show data table presents index-100 values under a **Growth of ₹10,000** title (A-13). Saved/recent context does not include a shared period or pinned revision. Growth periods do not recalculate every trailing metric/correlation; the banner explains the metrics' own windows, but explicit correlation dates and a selectable correlation lookback would improve decision support. No cost/holdings trade-off can be completed yet.

**Judgment:** a useful next improvement is a one-screen explanation of why two shortlisted funds differ: consistency, recent downside, costs when available, and correlated behavior. Do not declare a better fund from the largest CAGR. The scatter's vertical labels and identical highlight colours need refinement.

[Candidate comparison](candidate/screens/d-compare.png), [data-table unit defect](screens/probe2-compare-table-units.png).

### 5.6 Investment Lab and calculators

SIP, lump sum, SWP and STP run on actual NAVs. Currency sliders, historical date shortcuts, auto-updating results and the start-month distribution make the Lab much more inviting. No forecast is falsely presented as a historical result. SIP stamp duty, NAV trade dates, cash flows and XIRR independently match representative outputs.

It is nevertheless **not ready for financial trust**: wrong holding-period classification (A-03), automatic equity taxation for debt (A-04), lost saved parameters (A-05). The generic tax caption also needs to distinguish hypothetical full redemption for SIP/lump sum from only realised source withdrawals/transfers for SWP/STP. Remaining holdings are not liquidated for those latter tax estimates. The absence of exit loads, surcharge and STT is disclosed and should remain adjacent to the tax result.

On mobile, the first screen remains almost entirely a scenario form. Prefilling data does not provide a first-screen story if the result sits below it. The design contract's result-first/collapsible-input state after a run remains a better direction.

[Lab before/after](comparisons/lab-before-served-candidate.png). [Phone first viewport](candidate/screens/m-lab-sip-viewport.png).

### 5.7 Workspace, saved screens, notes and research

Durable backend records, versioned writes, archive/restore and optimistic concurrency work. Independent real-Postgres HTTP testing produced one 200 and five 412s for six simultaneous saves; the winning body/version survived a fresh application lifespan. Missing If-Match returned 428 and malformed If-Match returned 412.

The frontend is less reliable than that backend: replay drops inputs; failed watchlist edits are silent; rename conflict destroys the local proposed name; switching notes silently discards unsaved text. Notes preserve their text on the tested save/conflict path, so that remediation should be credited. Its behavior must extend to every editable field and record kind.

Saved screens rerun on the latest snapshot. Scenarios save the request and summary but omit the full provenance envelope; decision briefs, original/latest replay and evidence comparison are not built. Watchlist stars also lack an explicit destination-list choice. These gaps limit the accepted “research notebook” loop.

### 5.8 Portfolio intelligence, AI research and alerts

All three are **Planned**, with working conventional research shortcuts rather than fake execution. This is honest. It is not an implemented AI assistant, CAS parser, portfolio optimiser, alert evaluator or event log.

Distinguish dependencies: holdings/benchmark/cost facts need datasets, whereas agent runtime, CAS ledger, alert lifecycle and research replay also require software implementation. Those capabilities cannot all be excused as missing external data. Their inclusion in accepted 2.0 scope is explicit in [doc 20](../../20-wickstreet-2.0-complete-mf-scope.md).

### 5.9 Mobile and tablet research journeys

No page-level overflow was observed across the captured 320/390/768 layouts or the existing 390/768/1024/1440 route checks. The candidate's score, loss verdict and watch/compare actions are visible at 390×844. Sheets and bottom navigation provide a real responsive design rather than merely shrinking a desktop table.

**Judgment:** the fund header still spends most of the first viewport on repeated identity/evidence; the first chart is below the fold. Lab forms obscure their live result. The persistent tray consumes scarce phone space, and phone controls lack a direct Clear selection action. Several controls remain below 44 px—especially 20 px information buttons and 32 px fund-change controls—even though generic chips/buttons grow. This is not a blanket WCAG failure: target spacing exceptions matter. It is a thumb-use gap against the stated design system.

On the served app, two overlapping fund action/tray bars are an actual obstruction. The candidate fixes that overlap. Tablet layouts are readable, but remain vertically long and need a deliberate result-first layout rather than treating every non-desktop width identically.

## 6. New verified defect register

**Severity convention:** To preserve the previous audit's standard, an objectively wrong financial output is **P0**. **P1** means a materially misleading signature feature or broken core research/save journey. **P2** means a narrower usability, semantics or accessibility defect. A P0 here does not imply that Wickstreet executed a transaction; it is a release gate for financial correctness.

### A-01 · P1 · Served artifact does not match the claimed remediation

**Reproduce:** visit port 8000 Discover, Screener and Appearance; compare the served entry bundle with a fresh source build. Run the current MF suite directly against port 8000 without rebuilding it.

**Actual:** 23 pass, 14 fail. Hidden actions, bad-formula behavior, old copy and empty first-use Compare persist. Zoom chart image roles fail axe; the phone tray covers fund actions. Candidate: 37/37 pass. **Expected:** the reviewed release artifact is exactly the one delivered.

**References:** `Dockerfile`, `web/vite.config.ts`, deployed build output; [build hashes](evidence/performance-builds.json), [served results](evidence/mf-browser-results.json), [candidate results](evidence/candidate-mf-browser-results.json). This is a delivery finding; exact older source provenance is not asserted from a filename alone.

### A-02 · P1 · Drawdown chart and table remove the deepest fall

**Reproduce:** `/mf/funds/122639?tab=risk`; inspect March 2020, then the deepest-falls table and raw underwater response.

**Actual:** raw −31.2021% on 24 Mar; plotted minimum −26.8098% on 26 Mar; accessible sampled table minimum −19.1684% on 16 Mar. The subtitle says every day. Uniform every-nth-row reduction omits extrema, and brush zoom cannot restore discarded dates.

**References:** `components/fund/Risk.tsx:31,49,56`; `components/charts.tsx:165` (`thin`) and TimeChart data reduction. [Browser tooltip](screens/probe2-drawdown-omitted-trough.png), [raw API](evidence/api/122639-underwater.json), [probe](evidence/followup.json).

**Accept:** preserve true minima/maxima and episode anchors in every display window; full-resolution zoom/inspection; data table/export retains the actual extreme and date. Assert this case numerically and in the browser.

### A-03 · P0 · Tax uses fixed day counts instead of calendar holding periods

**Reproduce:** lump sum, code 122639, ₹10,00,000, start 24 Jul 2023, end 24 Jul 2024, equity tax class.

**Actual:** 366 days is treated as long term by `held > 365`; gains ₹3,76,182.53 receive LTCG exemption/rate, tax ₹32,653.73. Exactly 12 calendar months remains short term under the cited holding-period definition; the same model's 20% rate plus 4% cess produces ₹78,245.97. Understatement ₹45,592.24. This is not a dispute about surcharge or the disclosed exit-load omission.

**References:** `backend/src/wickstreet/analytics/domain/tax.py:106–117`, specifically the 365/730/1095 thresholds. [API](evidence/api/tax-12m-anniversary.json), [browser](screens/probe2-tax-boundary.png), [independent calculation](scripts/financial-checks.py). The Income Tax Department defines the applicable threshold in **months**, including equity-fund units: [holding-period FAQ](https://wmstatic-prd.incometaxindia.gov.in/web/guest/w/what-is-the-meaning-of-the-term-short-term-capital-asset-). The applicable equity rates are documented in [tax treatment guidance](https://www.incometaxindia.gov.in/w/treatment-of-income-from-different-sources-1).

**Accept:** calendar-aware 12/24/36-month anniversary checks; before/on/after-anniversary cases including leap days; reconcile the exact browser case above. Review other fixed-day tax thresholds. No methodology approval is a substitute for correcting this implementation error.

### A-04 · P1 · Automatic Lab result uses equity tax for a debt fund

**Reproduce:** fresh `/mf/simulate?code=118987` (HDFC Corporate Bond Direct Growth). Do not change tax classification. Then select Debt-oriented, keeping the prefilled 30% slab.

**Actual:** automatic equity estimate ₹271.53 versus debt estimate ₹21,647.40, a ₹21,375.88 difference. The form says Wickstreet does not guess taxation but silently supplies an equity assumption. A mathematically correct conditional calculation still misleads when the product preselects the wrong class for its fund.

**References:** `routes/simulate.tsx:278–299` initial inputs (`taxClass: 'equity'`), request construction and auto-run; [default screenshot](screens/probe3-debt-default-equity-tax.png), [debt result](screens/probe3-debt-correct-tax.png), [paired API responses](evidence/api/debt-tax-as-debt.json).

**Accept:** no tax number until classification is authoritative or explicitly confirmed; ambiguous funds request an assumption; changing the fund invalidates prior tax confirmation. Preserve disclosed, editable slab assumptions. Cover equity, debt, gold/FoF and ambiguous hybrids.

### A-05 · P1 · Saved scenarios reopen with default inputs

**Reproduce:** use the isolated saved SIP record shown in evidence: ₹25,000, day 15, start 15 Apr 2019, end 15 Oct 2025, 10% step-up. Open in the lab.

**Actual:** only `kind` and `code` are passed; amount becomes ₹10,000, day 1, step-up 0 and default dates. The record says opening reruns it on the latest snapshot, implying the saved scenario is preserved.

**References:** `routes/workspace.tsx:196–217`, especially `:201`; `routes/simulate.tsx` initial state and save handler. [Before](screens/probe-scenario-saved.png), [after](screens/probe-scenario-replayed.png), [input evidence](evidence/interactions.json). The workspace fixture was isolated; its illustrative saved summary is not an independently verified investment result.

**Accept:** round-trip every request field for all four calculator kinds, including STP target, tax/slab, step-up, amounts, day and dates. Distinguish original revision replay from rerun-latest. Save the provenance envelope.

### A-06 · P1 · New query can select old search results

**Reproduce:** search `parag`; change to `sbi smallcap` while delaying the latter response by two seconds; press Enter during the pending request.

**Actual:** Parag results remain selectable and Enter opens `/mf/funds/122639` for the new query. This is reproduced with controlled latency, not a claim of a server returning a wrong match.

**References:** `queries.ts` `useFundSearch` uses `keepPreviousData`; `components/FundSearch.tsx:47–57,110–126` derives/selects results without a matching-query guard. [Screenshot](screens/probe-stale-search.png), [selected URL](evidence/interactions.json).

**Accept:** only matching-query results are selectable; reset active descendant and block Enter/click while the result belongs to an older query. Test rapid typing, deletion and out-of-order responses.

### A-07 · P1 · Broad AMC search prioritises historical IDCW plans

**Reproduce:** `nippon india` in fund search or `/api/v1/mf/funds?q=nippon%20india&limit=8`.

**Actual:** all eight results are historical IDCW plans. First code 144891 last NAV 31 Jan 2022; third code 141898 last NAV 6 Jan 2023. Search does not mark them Historical. Phrase match sorts before active Direct Growth preference.

**References:** `backend/.../analytics/domain/search.py:31–40`; `components/FundSearch.tsx` result badges; [search response](evidence/api/search-nippon-india.json), [fund status](evidence/api/search-historical-144891.json), [browser](screens/probe3-nippon-search.png).

**Accept:** broad AMC queries put eligible current plans first; historical results remain searchable but visibly separated and dated. Expand regression queries beyond exact flagship names. Do not hide archived matches for exact code/ISIN searches.

### A-08 · P1 · Match any breaks a valid nested saved screen

**Reproduce:** open an ALL view containing Active/Direct/Growth plus `ANY(CAGR 3Y > 15%, volatility 3Y < 12%)`. It returns 792 matches. Select Match any and allow retries to finish.

**Actual:** protected gates wrap the existing group into `ALL(gates, ANY(ANY(...)))`; the backend rejects the extra nesting with **422: `all[3].any[0]: groups nest at most 2 levels`**. The page becomes an error with Try again.

**References:** `view-spec.ts:73–80` `filterOf`; backend `screening.py:MAX_DEPTH` and `_node`; [browser](screens/probe4-nested-any-final.png), [responses](evidence/consistency-probes.json).

**Accept:** valid saved trees remain valid when supported controls are used, or unsupported transformations are prevented with a clear explanation and last-good state. Do not send deterministically invalid trees and retry them.

### A-09 · P1 · Rename conflict discards the draft while claiming it remains

**Reproduce:** edit a record name; simulate another window saving first; submit rename.

**Actual:** refetch changes `record.name`, the effect replaces the local proposed name with the other window's name, and the conflict warning says Your text is still here. There is no Copy my text for names.

**References:** `routes/workspace.tsx:78,87,99`; mutation invalidation in `workspace.ts`. [Screenshot](screens/probe-rename-conflict.png), [value and warning](evidence/interactions.json).

**Accept:** preserve all local fields through conflict, expose mine/theirs and copy/retry options; replacement must be explicit. Exercise names and bodies across record kinds, not only note text.

### A-10 · P2 · Failed watchlist changes have no visible error

**Reproduce:** isolate a watchlist with code 122639; return 503 for its PUT; remove the fund.

**Actual:** no alert/error/retry is rendered; header still shows Saved version 1. The body-edit mutation is separate from Header's mutation and its error is unused.

**References:** `routes/workspace.tsx:104–145`, `components/CompareTray.tsx` WatchButton also ignores returned `watch.error`. [Failure screenshot](screens/probe-watchlist-save-failure.png), [zero alerts](evidence/interactions.json).

**Accept:** every write failure is visible and announced; preserve the requested operation and offer retry; saved state must identify the last acknowledged operation.

### A-11 · P2 · Switching notes silently discards unsaved text

**Reproduce:** edit note A without saving; select B; return to A.

**Actual:** A returns to Saved A with no warning/recovery. The settled reproduction waits for each selection; this is not merely an intermediate render.

**References:** `routes/workspace.tsx:173–178`, record selection; [screenshot](screens/probe3-unsaved-note-lost.png), [settled value](evidence/final-probes.json).

**Accept:** retain per-record drafts or provide an explicit save/discard decision before switching/navigating away. No durable server record was lost in this test.

### A-12 · P2 · Chart brush speaks pixels/undefined bounds; chart focus is suppressed

**Reproduce:** focus the fund growth chart's brush and use ArrowRight. Inspect its accessibility name/value and focus the chart SVG.

**Actual:** handle moves, but name is `Min value: undefined, Max value: undefined`; value changes from 58 to approximately 58.95 (pixel coordinates, not dates). SVG computed outline is `none` despite keyboard focus. Candidate axe passes because these semantic defects are not caught by that sweep.

**References:** `components/charts.tsx` Brush; `mf.css:37` focus suppression. [Probe](evidence/followup.json), [focus evidence](evidence/final-probes.json), [screenshot](screens/probe3-chart-focus.png).

**Accept:** named start/end handles with date-valuetext, meaningful bounds, visible keyboard focus and documented keys. Manually test with a screen reader and touch. The served app additionally has the serious nested-interactive axe failure recorded under A-01.

### A-13 · P2 · Comparison data table uses the wrong displayed units

**Reproduce:** open Compare and Show data table on Growth of ₹10,000.

**Actual:** first row says `100.0`, rather than ₹10,000, under the same chart title; later rows are also index values. No index-100 unit is stated. This undermines the accessible alternative to the chart.

**References:** `routes/compare.tsx` growth ChartFrame table (`toFixed(1)` on index values) versus currency plot formatter. [Screenshot](screens/probe2-compare-table-units.png), [table text](evidence/followup.json).

**Accept:** table and plot use the same units, or the table explicitly offers a separately labelled index view. Assert first and final values in both 1Y and All windows.

### A-14 · P2 · Backtest growth is drawn before the return occurred

**Reproduce:** inspect the first cumulative backtest point. API signal month October 2019 selects at that month end and earns the next-month return.

**Actual:** tooltip **28 Oct 2019, Top-N 100.6** already contains the November holding return (0.591268%). The frontend labels every next-month outcome as the 28th of its signal month. Hold-out shading likewise needs dates consistent with the displayed return interval.

**References:** `routes/studio.tsx:426–427`; backend `analytics/domain/backtest.py:run` compares month with month+1. [Browser tooltip](screens/probe4-backtest-dates.png), [first API month](evidence/api/backtest.json), [probe](evidence/consistency-probes.json).

**Accept:** use actual holding-period endpoints; include a starting 100 anchor; separately label signal and realised-return dates. Verify the first point and the hold-out boundary.

### A-15 · P2 · No mixed-revision guard across fund reads

**Evidence type: fault-injected architectural defect.** All real reads in this audit used 2801. Injecting a score response labelled revision 2800/as-of 21 Oct alongside metrics at 2801 produced no warning; the page footer stated only 2801. Numeric payloads were left unchanged to isolate metadata handling.

**References:** `queries.ts` query keys and fund reads lack a revision parameter/guard; `routes/fund.tsx:191` footer uses metrics envelope alone. [Screenshot](screens/probe4-mixed-revision.png), [probe](evidence/consistency-probes.json).

**Accept:** shared revision/method context for a research view; pin compatible reads or clearly block/mark mismatched sections. Test publication during navigation and retained caches. No real publication race is claimed here.

## 7. Financial and API validation detail

The independent scripts import no Wickstreet financial implementation. They reconstruct results from saved raw NAVs and RBI yields using Python's standard library. [Financial script](scripts/financial-checks.py), [field/backtest script](scripts/field-backtest-checks.py).

| Check | Result / representative evidence |
|---|---|
| Three funds' trailing 1M/3M/6M/1Y and 3/5/10Y CAGR | Match actual anchors and disclosed 365.25-day annualisation; codes 122639, 118955, 120166 |
| Volatility, current/max drawdown, RBI compounded risk-free rate, Sharpe, Sortino, historical VaR/CVaR | Match representative API values under method v5 |
| Rolling 1Y/3Y | Full endpoint counts and representative summaries/point errors match reconstructed NAV windows |
| Composite scores | Equal-weight percentile mean matches for three sample funds; category specificity retained |
| Fund/proxy regime returns | Representative window endpoint returns match raw NAV calculations |
| Correlations | All three pairs reconstructed: 0.75787684, 0.80092296, 0.92767039; 2,469 observations each; average 0.82882340 |
| Default SIP | 61 instalments, invested ₹6,10,000, value **₹7,98,277.99**, XIRR **10.6171265%**; stamp duty included |
| Default SWP | 60 withdrawals, ₹3,60,000 withdrawn, final **₹12,50,995.66**, XIRR 11.4337%; no default exhaustion |
| Representative lump sum and STP | Reconstructed ending values and XIRRs agree; STP uses joint trade dates and target purchase stamp duty |
| Representative SIP tax | Netting/exemption/cess reconstruct **₹8,226.14**; the separate exact-anniversary test fails |
| Selection backtest | **83/83** monthly strategy/median returns and selected-code lists match raw NAV reconstruction for **47** group members |
| All-field screening | **160/160** `is_available` match counts equal registry coverage at revision 2801 |
| Snapshot metadata | Actual responses consistently 2801/method 5/as-of 22 Oct; cross-read drift guard fails the isolated metadata probe |
| Workspace concurrency/durability | Six parallel version-1 writes: one 200/five 412, final v2; new application lifespan reads the winning body; 428 without version |

The main financial result file contains **157 passing checks and one failed tax-boundary check**, not “all financial calculations pass.” Field coverage and 83-month backtest reconstruction are additional checks. They do not certify every possible tax class, fund history, missing-data pattern or return window.

**Interpretation matters:** NAV returns for IDCW plans are not total investor returns without distributions; proxy capture is not official-benchmark capture; a high category score is not suitability; overlapping rolling windows are not independent samples; daily-return correlation is not holdings overlap; hypothetical end-redemption tax is not tax already incurred. The product discloses several of these well. Preserve and sharpen those distinctions.

## 8. Visual-reference fidelity and interaction quality

The owner's references and original atlas establish an appropriate direction, not a financial source of truth. Their illustrative fund numbers were not substituted for actual data.

| Reference intent | Latest implementation | Remaining design recommendation |
|---|---|---|
| Editorial warmth with analytical precision | Serif headings, warm paper, restrained sea green and coherent surfaces | Reduce oversized repeated headers; create more varied but disciplined layouts instead of repeated white-card grids |
| Search-led discovery and compact trends | Hero search, real sparklines and monograms delivered | Prioritise a useful shortlist/insight in the first viewport; visibly identify what each sparkline represents |
| Insight-first fund research | Plain-language loss comparison and score explanation | Show balanced current evidence and counter-evidence; avoid repeating the same crash sentence on every tab |
| Sophisticated charts | Brush, log scale, regime bands, frontier and heatmaps | Preserve extreme events; linked crosshairs, full-resolution zoom, consistent series identity and annotations |
| Rich category/benchmark context | Scalar category medians; labelled large-cap NAV proxy | Category distribution/range where derivable; approved category series and licensed TRI where required—do not fabricate them |
| Mobile research continuity | Bottom navigation, filter sheet, first-screen score/actions | Compact context strip; result-first Lab with collapsible inputs; make all essential actions reachable without precision scrolling |
| Premium micro-interactions | Short rise/hover transitions, skeletons, debounced inputs | More meaningful feedback for changes/saves; avoid animation as a substitute for analytical clarity |

The monograms are an acceptable original alternative to copying AMC logos. The current landscape is serviceable but generic. Neither issue is as consequential as chart truth, research continuity or preservation of a user's reasoning.

Comparison plates retain the original, served and candidate captures side by side:

- [Discover](comparisons/discover-before-served-candidate.png)
- [Screener](comparisons/screener-before-served-candidate.png)
- [Fund overview](comparisons/fund-before-served-candidate.png)
- [Market regimes](comparisons/regimes-before-served-candidate.png)
- [Studio first use](comparisons/studio-first-before-served-candidate.png)
- [Investment Lab](comparisons/lab-before-served-candidate.png)
- [Mobile fund](comparisons/mobile-fund-before-served-candidate.png)

Owner references remain at [reference A](../audit-2026-10-23/refs/owner-ref-a-app-screens.png) and [reference B](../audit-2026-10-23/refs/owner-ref-b-visual-proposal.png). The original [wireframe gallery](../wireframes/index.html) and [selected atlas rendering](comparisons/original-atlas-selected.png) are separate from production screenshots.

### Original improvement register, beyond F-01–F-19

| Improvement | Independent state |
|---|---|
| U-01 First-use story | Data prefill delivered in candidate Studio/Compare/Lab; mobile Lab still begins with the form. Served Compare remains empty. |
| U-02 Verdict line | Delivered, with API numbers; needs balanced current counter-evidence and less repetition. |
| U-03 Interactive chart layer | Partial: brush/log/bands; no linked crosshair; sampled zoom loses detail. |
| U-04 Category growth context | Partial: log helps; a category series remains absent and linear scales can still include zero after rounding. |
| U-05 Sparklines | Delivered in candidate categories, results and ideas; absent from served Discover. |
| U-06 Fund-house marks | Delivered as monograms, explicitly not official logos. |
| U-07 Hero search | Delivered in candidate desktop; absent from served desktop. |
| U-08 Shared research context | Partial: recent codes travel; explicit fund set, period, pinned snapshot and original/latest replay do not. |
| U-09 Live sliders | Delivered desktop; mobile hierarchy remains incomplete; tax assumptions must be corrected. |
| U-10 Backtest story | Verdict/cumulative view delivered; realised-return dates remain wrong. |
| U-11 Nested editor | Unresolved; opaque groups cannot be edited. Match-mode transformation also breaks them. |
| U-12 Frontier and labels | Line delivered; labels wrap vertically and need collision-aware layout. |
| U-13 Phone score/actions | Delivered in candidate at 390×844; charts remain below the large header. |
| U-14 Why shown | Collection-level rule and equity-first ordering delivered; per-fund explanation is limited. |
| U-15 Portfolio preview | Unresolved design suggestion. More importantly, actual portfolio functionality remains Planned. |
| U-16 44 px targets | Partial: common chips/buttons grow; information/change controls remain small. |

## 9. Engineering, accessibility and performance

### Architecture and maintainability

The MF route tree has its own shell and stylesheet. Shared primitives, formatting, series helpers, theme roles, API transport and React Query hooks reduce duplication. Backend bounded-context and layering contracts independently pass **9/9**. Full backend tests pass. No direct evidence of Momentum25 source coupling introduced by this remediation was found.

There are nevertheless maintainability pressure points: `screen.tsx` is 549 lines, `studio.tsx` 530 and shared charts 555. They combine routing, query orchestration, controls, transformation and presentation. Extract feature-specific controllers and chart adapters around stable contracts when fixing the defects; a large rewrite is unnecessary. The hand-maintained MF response interfaces and dictionary-heavy backend responses should gain explicit contract validation. Types alone do not guard runtime unit/revision drift.

Query cancellation and URL restoration are good. `keepPreviousData` is appropriate for some views but unsafe for selectable search results without query identity. Mutations do not share a complete error/draft policy. Retrying a deterministic 422 adds delay without recovery. Recent-fund storage is convenience state, not durable research or a shared snapshot contract.

### Theme modularity

**Verified strength.** Paper & Ink and Monsoon, light and dark, were captured and tested. Forty representative route/palette/mode axe runs on the candidate produced no violations. Colours use scoped semantic variables from `theme/themes.ts`; marks, charts, hero and surfaces follow them. Appearance enumerates `THEMES`, and completeness tests enforce every colour role. Adding a theme is a new theme entry, with no per-component colour changes required by the inspected architecture.

That is a code-architecture conclusion, not a claim that an arbitrary new palette automatically passes contrast. I did not modify the theme file to add a third palette. New palettes still require semantic contrast/chart differentiation QA. The existing palette completeness test validates syntax/roles, not perceptual quality.

### Accessibility

Candidate improvements include a skip link, labelled controls, native sheets, keyboard search, data tables, partial-year patterns and reduced-motion styles. All 37 candidate MF tests pass, including the current light/dark route axe sweep. Additional independent four-theme checks also pass.

Port 8000 fails axe on zoomable charts because `role=img` contains focusable brush handles. Candidate `figure` fixes that structural problem. Manual inspection still finds meaningless brush names/values, suppressed chart focus, reduced data tables that omit key events, a currency/index mismatch and small help targets. “Zero axe violations” is therefore not a sufficient accessibility sign-off. A screen-reader session and a keyboard/touch journey remain required.

### Performance observations

Cold Chromium measurements below used disabled browser cache. Slow mobile used 390×844, 4× CPU slowdown, 150 ms network latency and 1.6 Mbps download. Each route/profile is a single observation; concurrent background test load and local hosting limit comparability. These are not Core Web Vitals population percentiles.

| Route | Served JS decoded | Served slow-mobile LCP | Candidate slow-mobile LCP |
|---|---:|---:|---:|
| Discover | 1.175 MB | 7.04 s | 2.81 s |
| Fund overview | 1.205 MB | 8.21 s | 3.90 s |
| Lab | 1.173 MB | 7.04 s | 2.81 s |

Candidate decoded JS remains approximately **1.18–1.21 MB**; its preview transferred fewer bytes than port 8000. This is a different serving setup, so the difference must not all be attributed to UI optimisations. The main entry remains 657.8 kB minified and the independent build retains the over-500-kB chunk warning. Desktop Lab CLS was approximately **0.116** for the candidate and **0.132** served, suggesting a result-space reservation problem. Browser response/capture evidence showed no normal-route console errors in either sweep; expected failures were introduced only in named probes.

**Acceptance targets:** repeat cold tests against the final production serving path; compressed assets; field p75 LCP ≤2.5 s/CLS ≤0.1/INP ≤200 ms when a representative population exists; meanwhile use a documented repeatable local mobile budget. Separate the stock-workstation dependency graph where safe, lazy-load chart/calculator work, reserve result geometry and remeasure instead of merely raising the bundle warning threshold.

### Checks actually executed

| Check | Independent result |
|---|---|
| Web unit tests | **193 passed**, 29 files |
| ESLint, TypeScript | Pass |
| Fresh production frontend build to separate temporary output | Pass; candidate entry hash/name consistent |
| Full backend suite, dedicated test DB | **1,414 passed, 13 skipped**, 3 warnings; opt-in real-data suite not enabled |
| Architecture import contracts | **9 kept, 0 broken** |
| MF browser suite, actual port 8000 | **23 passed, 14 failed** |
| Same MF suite, latest candidate | **37 passed** |
| Independent candidate axe sweep | **40 route/theme combinations, 0 violations** |
| Independent served axe sweep | Four tested theme combinations reproduce nested-interactive on fund overview; full existing suite also finds affected zoom routes |
| Independent financial reconstruction | **157 pass, 1 fail** (tax boundary) |
| All-field availability checks | **160/160 pass** |
| Raw-NAV backtest reconstruction | **83/83 months pass**, 47 funds |
| Real-Postgres workspace concurrency | One 200/five 412; persists across a fresh app lifespan |
| Momentum25 full browser regression | **Paused at owner's request:** 153 passed, 6 skipped, 1 interrupted, 84 not run; no completed-test failure observed. **Not a full regression pass.** |

Momentum25 was run from a temporary copy of the harness, redirecting its hard-coded evidence paths away from prior audits. An existing test-database preflight refused non-fixture screening data; it was not cleared to force progress. A fresh audit-only E2E database was created for the subsequent run. The one interrupted test was `m14-studio.spec.ts`'s matured hold-out test. Its interruption is not reported as a product failure. [Partial log](evidence/momentum-browser.log), [results](evidence/momentum-browser-results.json).

## 10. Tickertape competitive gap analysis

**Method:** current public fund, screener and collection pages were opened in desktop/mobile browsers and saved locally. No login or Pro purchase was attempted. Public feature documentation supplemented observation; older guides establish documented capabilities, not a fresh guarantee of their gated implementation. No claim of absence is made solely because a capability was not visible.

| Research task | Assessment | Basis |
|---|---|---|
| First impression / calm focus | **Candidate Wickstreet advantage in restraint; category-leading polish unproven** | Its editorial identity and absence of promotional clutter help. Tickertape's public fund capture contains prominent promotions, but the paid experience may differ. |
| Search and discovery | **Wickstreet shortcoming; relative winner unverified** | Flagship queries improved, but historical AMC results and stale-result selection remain. Competitor search relevance was not exhaustively tested. |
| Advanced screening | **Both have substantial capability; no field-count victory** | Tickertape publicly documents custom filters, saved screens, universes and exports. Wickstreet's transparent typed conditions/provenance are strengths, but its nested workflow still breaks. [Tickertape guide](https://www.tickertape.in/blog/how-to-use-tickertape-mutual-fund-screener/) |
| Research breadth: costs, fund facts, benchmark, holdings | **Tickertape verified advantage** | Its public fund page supplies costs, load/minimum information, benchmark and portfolio/manager sections. Wickstreet cannot complete those checks today. [Public fund page](https://www.tickertape.in/mutualfunds/parag-parikh-flexi-cap-fund-M_PARO) |
| NAV/risk explanation | **Wickstreet verified strength; exclusivity unverified** | Accessible score decomposition, episode/recovery analysis, rolling distributions and provenance are substantial. But A-02 currently weakens visual trust. Tickertape documentation also includes rolling-return and drawdown metrics; saying it has none would be wrong. [Filter documentation](https://www.tickertape.in/knowledge-base/modules/evaluating-mutualfunds/mf-screener/) |
| Comparing a shortlist | **Mixed** | Wickstreet has common-start growth, five-fund metrics, risk map and daily correlation. Tickertape publicly exposes peer and asset comparison. Costs/holdings remain a practical Wickstreet gap; gated functionality was not assumed absent. |
| Historical simulation | **Wickstreet shows useful depth; readiness blocked** | Four kinds, XIRR, tax and start-month history are implemented, but A-03/A-04/A-05 block a trustworthy workflow. Competitor public page exposes SIP/chart controls; absence of other authenticated tools is unverified. |
| Personalisation / portfolio / AI | **Wickstreet promised capabilities are unimplemented** | Recent-fund convenience is not portfolio intelligence or AI. Relative authenticated competitor depth remains unverified. |
| Mobile effectiveness | **No defensible overall winner** | Both public mobile layouts were captured. Wickstreet has intentional navigation and filters; its large header/form delay analysis. No matched participant task study was run. |

The competitive standard should be a completed task: **identify two suitable candidates, explain their trade-offs and costs, examine downside, simulate a schedule accurately, save the reasoning and return to the same evidence**. Current Wickstreet cannot reliably complete that chain. Transparent NAV analytics and original theme design are advantages, but they do not yet outweigh the missing fund facts and broken trust paths. Tickertape's [public screener](https://www.tickertape.in/screener/mutual-fund) and [collections](https://www.tickertape.in/screener/home/mutual-fund?switch=true) establish a broader discovery baseline than raw metric counts suggest.

[Desktop competitor capture](screens/tickertape-desktop-fund-viewport.png), [mobile](screens/tickertape-mobile-fund-viewport.png), [screener](screens/tickertape-desktop-screen.png). No competitor score is invented for unavailable authenticated experiences.

## 11. Dependency and scope ledger

| Capability | Classification | What remains |
|---|---|---|
| TER/AUM/exit loads/minimums/manager/riskometer | **Dataset dependency E1** | Acquire dated disclosures/rights grant, ingest and validate, then implement facts/screens/compare integration |
| Official benchmark TRI, alpha/beta/tracking analysis | **Dataset dependency E3** | Licensed series and changing scheme benchmark mapping; retain honest proxy labels until then |
| Holdings/sector/concentration/overlap | **Dataset dependency E4/E7** | Dated disclosures, security mapping, coverage/unreported handling and UI integration |
| IDCW total investor returns | **Dataset dependency E5** | Distribution history; NAV-only caveat remains |
| Category growth/range series | **Method/API work**, not an automatic external-data blocker | Approved construction from available NAVs, survivorship/membership rules and an explicit service contract |
| Alerts | **Missing service W2** | Rule persistence, evaluator, event lifecycle and UI; not merely a colour/theme task |
| Decision briefs, original/latest research | **Missing W3/UI** | Provenance schema, replay/diff and conflict-safe editing |
| AI research/recommendation assistance | **Missing Slice 5 runtime/methods** | Tool orchestration, validated citations, cancellation, language and persistence; no fake chat |
| CAS and portfolio intelligence | **Missing Slice 6**, some E1/E4 dependencies | Local parser/reconciliation/ledger, XIRR and allocations/overlap/rebalance services |
| Forward goal planner | **Missing approved S1 method** | Explicit assumptions and separate forward presentation |

Dataset dependencies are not counted as coding bugs. They are still material gaps against the accepted full-product readiness criterion. W2, W3, AI and CAS work must remain visible on the delivery plan rather than being bundled into a generic “waiting for data” explanation.

## 12. Prioritised path to readiness and excellence

| Priority | Work | Measurable acceptance gate |
|---|---|---|
| **Release gate 1** | Tax boundary and default classification (A-03/A-04) | Exact anniversary case returns ₹78,245.97 under the stated assumptions; before/on/after calendar anniversaries tested; debt/ambiguous funds cannot silently receive equity-tax results |
| **Release gate 2** | Chart truth (A-02/A-13/A-14) | Actual −31.2021%/24 Mar trough survives plot, zoom and accessible table; currency values match the chart; backtest outcomes appear at realised endpoints |
| **Release gate 3** | Save/reopen/conflict reliability (A-05/A-09/A-10/A-11) | All scenario fields round-trip for four kinds; six concurrent edits remain conflict-safe; every field draft survives failed/conflicted writes; errors are visible and announced |
| **Release gate 4** | Search and nested logic (A-06/A-07/A-08) | Pending old results cannot be selected; broad AMC queries rank current plans with historical sections; supported mode changes never send invalid trees |
| **Release gate 5** | Artifact parity (A-01) | One immutable build identity in app and report; full MF suite/axe/mobile checks run against the exact port-8000 artifact; finish Momentum25 regression |
| **Next** | Research context and accessibility (A-12/A-15/U-08) | Fund set, period, method and revision travel through Screen→Fund→Studio→Compare→Lab; deliberate original/latest choice; mismatch test warns/blocks; date-labelled keyboard brush with visible focus |
| **Next** | Mobile/desktop composition | At 390×844, researched fund insight and next action visible without repeated header; Lab exposes outcome after run with collapsible inputs; no final controls hidden by fixed chrome; essential touch targets reach design-system target |
| **Next** | Chart investigation | Extrema-preserving/full-resolution zoom, linked compatible crosshairs, stable series identity, annotations, legible collision-aware labels; event/date/unit checks accompany visual tests |
| **Product completion** | E1/E3/E4 plus W2/W3/Slices 5/6 | Real costs/holdings/benchmarks complete fund decisions; alerts truly evaluate; saved reasoning replays; portfolio/AI features work with evidence and honest unavailable states |
| **Excellence validation** | Matched user tasks against Tickertape | Recruit beginners and advanced Indian investors; record completion, time, wrong-fund selections, unit misunderstandings and saved-evidence accuracy; test authenticated competitor where permitted; report results without inferring unseen features |

For visual acceptance, compare the actual final build with the owner references at matched artboard sizes, not only isolated component screenshots. Require the first viewport to answer a research question, not just show a welcome message and counts. Preserve Wickstreet's own identity while making typography, spacing, chart labels and mobile hierarchy more deliberate.

## 13. Final recommendation and paused handoff

**Requires Further Remediation.** The source candidate is a materially better NAV research workstation, at **7.2/10**, but financial output, visual truth and saved-research continuity still have release-gating defects. The application specifically requested at port 8000 is a different, less complete artifact, at **6.7/10**. Neither supports a defensible claim that Wickstreet 2.0 substantially surpasses Tickertape overall.

The shortest credible path is to close the tax/chart/persistence/search release gates, validate and deliver one exact artifact, then finish the accepted fund-facts and intelligence workflows. After those gates, an internal NAV-only slice could be reconsidered separately; that would not certify the complete accepted 2.0 scope.

**Paused safely at the owner's request.** All completed evidence and scripts are local. The separate candidate preview was stopped; port 8000 was not replaced. The remaining Momentum25 regression is the principal unfinished automated check: 153 passed, 6 skipped, 1 interrupted and 84 did not run. Physical phone, screen-reader, participant research and authenticated competitor evaluation remain unperformed. No application code, commit or push was made.

## 14. Evidence guide

- [Local evidence gallery](index.html): comparison plates and browsable screenshots.
- `screens/`: requested port-8000 captures, independent fault/interaction probes, public Tickertape captures and performance screenshots. Probe filenames identify tests; mock records are isolated.
- `candidate/screens/`: latest source-build captures, including desktop, tablet, 390/320 widths and four colour/mode combinations.
- `evidence/api/`: original API payloads, requests, status and timing; no real personal workspace content.
- [Financial results](evidence/independent-financial-results.json), [83-month reconstruction](evidence/independent-backtest-results.json), [160-field checks](evidence/all-field-checks.json).
- [Workspace concurrency](evidence/workspace-concurrency.json), [interaction probes](evidence/interactions.json), [additional probes](evidence/final-probes.json), [date/revision/nesting probes](evidence/consistency-probes.json).
- [Build/performance](evidence/performance-builds.json), [served browser results](evidence/mf-browser-results.json), [candidate browser results](evidence/candidate-mf-browser-results.json), [partial Momentum25 results](evidence/momentum-browser-results.json).
- `scripts/`: reproducible capture, API, calculation and isolated browser harnesses. They are audit artifacts, not application tests installed into the product.
- Original [82 screenshots](../audit-2026-10-23/screens/), [original report](../audit-2026-10-23/REPORT.md) and [remediation report](../remediation-2026-10-23/REPORT.md) remain unchanged.
