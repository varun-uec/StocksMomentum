# 06 · Competitive baseline and validation

## Evidence quality

Research date: **23 October 2026 (IST)**. The current public screener homepage was readable. A public fund page and screen results were also readable, but crawled fund figures were stale/inconsistent with the local snapshot, so none was used as Wickstreet data. Browser control had no available browser; this is a public-page/first-party-document review, **not an authenticated hands-on audit**. Login, Pro boundaries, tap/click counts, mobile behaviour, task timings, CAS import and conversational quality remain unverified. Absence from these pages is not evidence of feature absence.

Primary sources:

- **T1:** [Current MF screener home](https://www.tickertape.in/screener/home/mutual-fund) — public page advertises over sixty filters, named collections, custom filters and Basic/Pro filter entry points.
- **T2:** [Official screener guide](https://www.tickertape.in/blog/how-to-use-tickertape-mutual-fund-screener/) — published December 2022; describes preloaded/custom/saved screens, exports, individual research and watchlists. Useful as documented capability, not proof of current interaction details.
- **T3:** [Public Parag Parikh fund page](https://www.tickertape.in/mutualfunds/parag-parikh-flexi-cap-fund-M_PARO?chartScope=sip) — overview, scorecard, peers, return comparison, SIP view, portfolio, manager and tax sections were exposed. Some chart content was unavailable in extraction; full interaction is unverified.
- **T4:** [Current terms](https://www.tickertape.in/meta/terms) — AI Assistant/third-party AI provisions. Establishes an AI offering, not its language quality or tool coverage.
- **T5:** [Public growth-fund screen](https://www.tickertape.in/screener/mutual-fund/user/explore-growth-option-for-your-investments-ap_nb3FayJU_lDJg) — table columns, result pagination, saved-screen context. Public extraction only.

Do not transfer older stock Scorecard evidence to MF claims. Do not claim that Tickertape lacks AI, research memory, rolling returns or portfolio intelligence based on an incomplete inspection. Wickstreet's proposed advantages below must be tested.

## Screen-by-screen assessment

| Screen | Baseline established | Wickstreet target and mechanism | Dependency / proof required |
|---|---|---|---|
| 01 Discover | T1 has purpose-labelled collections | Editable purpose→filter→evidence continuity; optional goals; resume a dated decision brief | Current presets + M6; test first-use comprehension and collection discoverability |
| 02 Screen | T1/T2/T5 support rich filters, custom screens and exports | 160 registry dimensions today, explicit missing reasons, condition explanations, zero-result relaxations, transparent units/formulas | M3; compare actual task completion, field findability and export correctness; field count alone is not superiority |
| 03 Fund | T3 offers scorecard, profile and analytical sections | Balanced evidence beside recent loss, score decomposition, source/anchor drawer and a full downside journey | M4; E1/E3/E4 needed for profile/holdings parity; ask users to explain score versus risk |
| 04 Studio | T3 exposes research comparisons; advanced persistence/regime workflow unverified | Linked rolling/rank/underwater/frontier/regime views and separate backtest evaluation windows | Existing analytics + M4; verify competitor counterpart before claiming unique functionality |
| 05 Compare | T3 exposes peers and return comparison | Explicit common start, pair samples, annotated differences, replayable shortlist→scenario→brief | M5/M6; E1/E4 add costs/overlap; measure interruptions and period mistakes |
| 06 Simulate | T3 exposes SIP scope and tax content | Historical SIP/SWP/STP/lumpsum with actual schedules, cash flows, tax uncertainty and rolling start-date outcomes | Existing calculators + M5; full competitor calculator breadth unverified |
| 07 Portfolio | T3 includes fund composition; investor-CAS workflow not observed | Local preview/reconcile/commit/undo, unresolved exposure, look-through and decision scenarios | Slice 6/E1/E4; do not equate fund holdings with investor portfolio; test exact reconciliation |
| 08 Workspace | T2 documents saving, watchlisting and export | Dated briefs with original/latest replay, durable notes, explicit save/conflict state and evidence alerts | W1–W3; competitor current replay/alert details unverified |
| 09 Agent | T4 establishes AI Assistant provisions | English/Hindi/Hinglish tool operation; validated numeric citations; editable research view and saved tool evidence | Slice 5/6; compare language/task accuracy, not mere presence of AI |
| 10 Mobile | No controlled mobile inspection | One-hand research continuity, explicit apply/cancel, accessible chart tooltips and stable Back restoration | M1–M8; run same tasks on actual mobile viewports/devices |

Wickstreet currently has an analytical backend, not delivered parity at the user interface. Known parity gaps include AUM/TER, manager/exit loads/riskometer, security holdings and benchmark-relative metrics. These await E1/E3/E4; the new design cannot erase them. An advantage in NAV analytics must be demonstrated while these gaps remain visible.

## Comparative study protocol

Recruit **12 participants minimum**: 6 beginners (0–2 years researching funds), 6 experienced (3+ years, comfortable with risk/returns). Mix ages within 18–35, devices and English/Hindi/Hinglish use; age does not determine skill. Use separate consent for recordings, no real holdings/account credentials. Prototype inspection can identify navigation issues but cannot substantiate product speed, live data correctness or completed-backend claims.

Run the same tasks in Wickstreet and Tickertape, counterbalancing order within skill/device groups. Use equivalent plan-option identity, periods and criteria rather than identical results: different data providers and as-of dates can legitimately differ. Record data dates, account/plan access and any blocked task. Never buy a plan or bypass an access boundary for the study without authorization. If blocked, report “not comparable under available access”, not failure.

| Task | Defined start/end | Wickstreet design budget* | Comprehension check |
|---|---|---|---|
| Find a consistent equity shortlist | Discover → a saved screen with stated consistency criterion | ≤5 major activations excluding text entry | Explain peer key and why some funds are excluded |
| Explain a loss period | Search result → worst-fall episode and recovery status | ≤4 | Distinguish drawdown from negative 1Y return |
| Compare alternatives | Fund → selected two-fund comparison with period and correlation | ≤4 | Explain common start and why correlation is not overlap |
| Test a monthly SIP | Fund → valid historical scenario result | ≤5 plus input entry | Identify invested/value/XIRR and a tax/load omission |
| Resume research | Workspace → original brief → refresh a copy | ≤3 | Tell original evidence from new revision |
| Audit an advanced rule | Screen → formula → Studio result and method | ≤7 plus input entry | Name sample/hold-out/category-history limitation |
| Import portfolio (later) | Local CAS file → reconciled commit | No click target until parser usability pilot | Explain unresolved records and local file handling |
| Ask in own language (later) | Contextual command → cited answer → editable view | ≤3 plus text | Verify one number and explain recommendation counter-evidence |

*These are proposed design budgets, **not measured interaction counts**. A major activation changes a view, commits a rule/input, opens a chart detail or saves research. Typing, scrolling, focus movement and hover are counted separately so they cannot be hidden. Record total taps/clicks, misclicks, backtracks, abandonment and time including service wait. No moderator hints before recording unaided success.

Success rubric: completed correct result + correct interpretation + no critical data mistake. Partial completion is separate. Collect time-on-task median/p75, completion %, total interactions, help requests, single-ease-question 1–7 after each task, and a short think-aloud explanation. Report per group/device and raw anonymised task rows; small-sample findings are directional, not statistically proven population superiority.

**Release targets:** ≥90% overall correct completion, ≥80% beginner comprehension for each core concept, ≥90% experienced completion of deep-research tasks; median time ≤75% of comparator and median interactions ≤80% where equivalently accessible. No critical misunderstanding of guaranteed returns, tax completeness, score suitability or overlap. Failure triggers a design change and targeted rerun. Do not average an inaccessible competitor task into an artificial win.

## Technical and visual validation

**Planning artefacts now:** XML parse every SVG; check generated asset/document links; verify 10 desktop + 10 mobile main screens, 6 detailed states and 3 flow SVGs; render gallery at desktop/mobile; inspect all artboards for clipping and typography; test screen selection/device switching/notes/keyboard; inspect source labels and future dependency badges. No application unit/build tests are implied by artefact validation.

**During implementation:** snapshot contract tests and safe synthetic fixtures, read-only live checks at pinned revision, Playwright core journeys J1–J8 as services ship, axe and manual screen-reader/keyboard/touch, responsive screenshots, slow/offline/cancel/conflict tests, actual p50/p95 performance profiles, Momentum25 regression suites. Use synthetic CAS only. Do not store owned holdings in screenshots or telemetry.

## Acceptance scorecard to fill after implementation

| Dimension | Evidence | Current status |
|---|---|---|
| Visual coherence | Reviewed screenshots in both themes and five viewport widths | Wireframe artefacts only |
| NAV analytics correctness | Same-revision UI/API numeric assertions | API reads observed; UI unbuilt |
| Beginner comprehension | Unaided task/interview rubric | Not measured |
| Expert depth | Formula/peer/backtest reproduction task | Not measured |
| Task speed and interaction count | Counterbalanced study results | Not measured |
| Portfolio and agent quality | Later J6/J7 data/privacy/language suites | Dependencies unbuilt |
| Tickertape parity/superiority | Controlled feature and usability evidence | Public baseline reviewed; superiority unproven |
