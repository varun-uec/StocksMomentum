# 03 · Screen and interaction contracts

Each numbered experience has desktop `Dxx` and mobile `Mxx` SVG artboards in [the gallery](wireframes/index.html). Artboards are compositions, not pixel-locked implementation limits. All actions below are proposed product behaviour. Common state contracts are in [02](02-design-system.md). Screen criteria supplement the milestone gates in [05](05-slice-4-delivery-plan.md).

## 01 · Discover — start with a question

**Hierarchy:** product shell → greeting and research command → optional goal/horizon → editorial collections → category explorer → resume research. The lead message is “Make your next investment a considered one.” The hero has one primary “Explore consistent funds” action and one quiet “Build a screen”. A “Why this collection?” link states its exact filter and default Direct Growth/active universe. Future personal change briefs occupy a reserved module, not a fake feed.

**Desktop:** three editorial collections, two-column category and resume region; a contextual “What changed?” card appears only when saved historical evidence exists. **Mobile:** command, one lead collection, swipeable category chips with visible next-item affordance, vertical collection cards. No forced onboarding carousel.

**Actions:** (a) collection → same preset in Screen, (b) category → category filter at pinned revision, (c) fund search → exact plan-option, (d) resume → saved view and original/latest choice, (e) edit preferences → optional goal/horizon form. Preferences initially reorder chosen collections; do not claim suitability.

**Current:** six presets and registry categories; screener composes results. No popularity, social proof, “hot today” or invented ratings. **Future:** persisted preferences/recents/briefs in M6; E1/E4 change briefs and Slice 5 recommendations.

**States:** no snapshot offers service status and retry; no saved research invites a first collection; planned change brief explains the data dependency; inactive search result clearly labels historical NAV.

**Accept:** J1 requires one collection activation to see its screen. Collection filter matches backend preset exactly. Keyboard can open all visible cards. Mobile order prioritises command and research action. Personalisation is optional and reversible.

## 02 · Screen — express a thesis, inspect its consequences

**Hierarchy:** title/results count → preset/save bar → filter clauses → missing/coverage line → sortable results → compare tray. Left rail contains searchable metric groups; default table contains fund identity, 3Y CAGR, consistency, worst 3Y fall, category score and category. All 215 current metrics are discoverable; custom column sets expose more without forcing horizontal scanning by default.

**Desktop:** field/filter rail, full table, sticky column header and identity. Basic mode is the default: selecting a metric adds it to result columns and immediately shows its latest available snapshot value without changing the matching fund set. Search covers the full metric registry; popular return, TER, AUM, risk and score metrics are one-step choices. “Filter” is a separate optional action. Advanced mode retains typed condition editors, ALL/ANY logic, formulas and nested groups. Counts/results debounce by 300 ms and stale results remain visibly marked until the new response arrives. **Mobile:** “Filters (n)” opens a sheet; choosing metrics updates results immediately with no secondary Apply action. Advanced condition edits retain draft/Apply/Cancel. Results use cards with priority metrics and “All metrics”. Column view remains available as a focusable table.

**Actions:** show/hide a metric without changing the filter; optionally filter a metric through the condition editor; choose ALL/ANY with at most two levels in Advanced; type-aware operators; add custom formula; change columns/sort; save/copy screen; explain matched conditions; add watch/compare; open fund; export all matched results through pinned cursor pages. A progress/cancel export state distinguishes “loaded page” from “all results”. Standard trailing returns use the current analytics snapshot; no date input is needed. Percent inputs display human units and serialize fractions; `top_pct` is over the snapshot's available field values, not necessarily the filtered category.

**Current:** registry, presets, formulas, nested filter tree, five sort keys, cursor pages (max 500), excluded-missing list, conditions, zero-result relaxations, Basic/Advanced progressive disclosure. Saved views and URL semantics remain the same. **Future:** cross-device local-server persistence M6; alerts require a new evaluator/event service. Synonym search can use a versioned UI glossary without pretending registry synonyms exist.

**States:** syntax/type error pins to affected rule; old result visibly marked “Not updated” until valid request succeeds; empty result can apply a returned relaxation; missing values exclude a row even for `!=` and `not_in`; unsupported metric shows dependency in field browser. Default backend sort includes stable identity tie-break.

**Accept:** selecting a metric adds its data to results while the matching set and filter tree stay unchanged; thresholding starts only after the user explicitly asks to filter; mobile Basic has no Apply/Cancel step; values/counts respond after the existing 300 ms debounce; every registry metric is searchable in Basic and all condition operators remain accessible in Advanced; help shows unit/coverage; fraction input round-trips; no cursor crosses revision/filter changes; conditions can be explained; export has full-precision values plus state/reason and filter/method/revision metadata. Browser Back restores the original row and filter state. Errors never look like zero matches.

## 03 · Fund intelligence — one fund, an honest picture

**Hierarchy:** identity/variant/status → three balanced evidence statements → performance journey → return/risk summary → expandable research sections. Sticky actions: Watch, Compare, Test an investment, Save to brief, Ask about this. Tabs: Overview, Performance, Risk, Peers, Holdings, Profile. Cost/manager/riskometer are future E1 data; their unavailable panel is designed, not populated with guessed values.

**Desktop:** 8/4 primary/evidence grid; snapshot strip under identity. **Mobile:** plan/option remain visible; single-column chart then insight/risks; section navigation scrolls horizontally. Deep link `tab=risk` moves focus to its heading without hiding the context header.

**Current reference:** AMFI 122639, Parag Parikh Flexi Cap Direct Growth, 3Y CAGR 12.18%, worst 3Y drawdown −10.98%, score 97.78/100, rank 1 of 31 scored peers, consistency 100.0%. This score coexists with a −5.69% 1Y return. The UI explicitly presents both; a high historical score cannot erase recent losses. Metrics are snapshot examples, not recommendations.

**Actions:** time/window changes; rebased/NAV view; inspect exact anchor; annual CY/FY and heatmap; rolling distribution; underwater episode; score breakdown; peer/rank history; direct/regular counterpart; confidence/source drawer. The score drawer shows each of three current equal-weight percentile parts and its peer count; cost is absent, not zero. Profile distinguishes first stored NAV from launch date.

**Future:** E1 profile and fees, E3 official benchmark-relative metrics, E4 holdings and dated changes, E5 IDCW total returns. If a curated plan link is missing, show no continuation splice. Never infer historic category changes.

**Accept:** each displayed metric agrees with pinned `/metrics`; score formula matches `/score`; current loss and unrecovered drawdown visible; risk-free attribution includes RBI acknowledgement; “No risk-free data” does not fall back to zero. Every critical chart has a data table and accessible pinned tooltip. Holdings/profile panels explain their unavailable dependencies.

## 04 · Analytics studio — explore the evidence

**Hierarchy:** question-mode navigation → fund/peer selection → common window/revision → linked charts → sample/method strip → save research. Modes: rolling outcomes, rank persistence, risk–return frontier, regime behaviour, top-N selection backtest. This is distinct from Momentum25 Strategy Studio at `/studio`.

**Desktop:** a central primary plot and two supporting views. One linked crosshair for date-based views; selection opens evidence in the right margin. **Mobile:** one primary plot per mode, explicit next chart tabs, accessible table alternative; scatter points can be selected from a sorted list.

**Actions:** switch holding tenor, select category × plan × option, highlight a fund, inspect transition cell, choose valid backtest signal/top-N, run/cancel research read, save exact specification to brief. Changes recompute through deterministic services, not browser finance formulas. Only compare compatible windows; changing category clears incompatible selection with an explanation.

**Current:** rolling series/summaries; rank-history; peer transitions; frontier; regimes; backtests. Backtest UI shows “Historical Research — In-Sample” separately from “Out-of-Sample Evaluation”; display the server's hold-out start and limits. No “validated strategy” badge. Proxy regimes retain the backend label and are not named after events by inference.

**States:** insufficient peers/sample/date history gives an explanation; no frontier point for missing 3Y metrics; long read offers cancel; changing inputs leaves prior run labelled with its old inputs until replaced.

**Accept:** rank tooltip includes month, rank and peer count; 12-month transition denominator visible; frontier explicitly says historical/non-dominated, not optimal; selection backtest uses only server-supported signals and limits. Changing signals cannot mix in-sample with hold-out charts. Exact state survives reload.

## 05 · Compare — make differences legible

**Hierarchy:** 2–5 fund identities → common-period banner → rebased journey → difference summary → aligned metric matrix → correlation → brief action. Default comparison groups Growth/Return, Consistency, Downside; Costs and Holdings appear with availability information until enriched. A pair with different categories has visible peer-key labels and no combined score winner.

**Desktop:** fund columns, sticky metric labels, highlighted differences chosen by the user. **Mobile:** two focus columns at a time, choose A/B from selected funds, swipe/scroll table with persistent labels; chart can retain up to five direct labels. No tiny five-column cards.

**Actions:** search/add/replace/remove/reorder plan, change start, toggle metric group, inspect correlation pair, run investment scenario, save comparison or brief, export. Compare 1 is a guided empty state; sixth fund explains the five-fund cap.

**Current:** metrics, rebased series and pairwise daily-return correlations with sample counts; common start from service. **Future:** E1 fees/exit load, E4 overlap, post-tax cross-fund comparison service, allocation optimiser in Slice 6.

**Accept:** selected plans cannot duplicate; rebasing start and per-pair correlation coverage visible; raw score not compared across unlike peer groups as universal quality; correlation never labelled “holdings overlap”. A fund lacking history remains in the metric matrix with its own missing reasons. Removing to one selection returns a valid empty state. Return to Screen preserves its selection and scroll.

## 06 · Simulate — understand the path, not just the ending

**Hierarchy:** kind switch SIP/Lump sum/SWP/STP → amount/schedule/date inputs → fund(s) → assumptions/tax class → Run → outcome, cash flows, tax limitations. “Historical” mode is primary for current APIs. Future forward goal scenarios must be separately labelled assumptions and depend on an approved deterministic scenario method.

**Desktop:** 320 px input panel beside result, then tax/cash-flow detail. **Mobile:** compact result summary above a collapsible editable input card after Run; first use starts at inputs. Sticky “Run historical scenario” only while inputs are valid; inputs becoming dirty label old result “Previous scenario”.

**Actions:** use a researched fund, amount, schedule day, annual step-up, start/end, target fund for STP, explicit tax class/slab where required, run, compare saved scenario revisions, export and save brief. Defaults may prefill ₹10,000 as an editable input; it is not a claimed outcome.

**Current:** SIP/lumpsum/SWP/STP real-NAV calculators; FIFO, XIRR and sale-date-versioned tax estimates; rolling SIP by starting month. Include stamp duty and backend cautions. Lumpsum summary may have an empty timeline—do not fabricate intermediate balance points. Tax is an estimate, may be unmodelled and needs caller tax classification; TER is already reflected in NAV, not deducted a second time. Exit loads await E1. Tax rule ids do not imply rules beyond the backend's supported dates.

**Accept:** impossible dates, amount ≤0, source=target STP and missing instalment/tax inputs handled; summary equals API, trade dates follow first NAV on/after schedule; tax omissions visible next to after-tax figures; SWP exhaustion visible. No assumed annual return masquerades as a historical backtest. Original versus revised scenario inputs saved with revision.

## 07 · Portfolio and CAS — see through the wrappers

**Complete-vision design; Slice 6 service dependency.** Hierarchy: local import trust statement → choose file/format/password → parse → reconcile/duplicate review → confirm import → allocation, performance, look-through, drift and decision scenarios. The production menu promotes Portfolio only when the capability is available. Before then a clearly named roadmap detail is accessible; there is no working upload claim.

**Desktop:** portfolio summary, cash-flow-adjusted performance, exposure/overlap/drift views and reconciliation drawer. **Mobile:** import is a separate step flow; file picker, password reveal, parse result, row issue details; imported overview uses stacked exposure bars and a holdings list. No drag-and-drop-only upload.

**Actions:** local file selection, one-use password, retry wrong password, preview unresolved fund mapping, resolve exact plan by code/ISIN, exclude/review duplicates, commit reviewed batch, undo batch, inspect transactions, export, explore target allocation and proposed rebalance. Changes to a target show a scenario; no broker order or trade placement. Recommendations cite constraints and estimated taxes only after those services exist.

**Data:** owner's CAS/ledger; E1 loads and fees; E4 dated holdings/overlap/look-through; E7 style as available; portfolio XIRR/attribution, goal and optimisation services. CAS parsing remains local and raw files/passwords never enter agent context. Holdings dates/publication dates and unresolved weights remain visible. Exposure sums include an “unreported” bucket; no false precision on drifting disclosure weights.

**States:** encrypted/unsupported/corrupt file, duplicate batch, unresolved id, partial transactions, missing NAV, failed reconciliation, rollback/retry. Preview is read-only and commit is idempotent. No real CAS used in these artefacts.

**Accept:** preview cannot mutate ledger; importing twice has no duplicate impact; password/file absent from logs and persistent state; rollback is exact; unresolved data prevents falsely precise portfolio XIRR; all exposure totals reconcile; network-disabled parser test. Separate SaaS worker/egress requirements remain future architecture work.

## 08 · Workspace — research that compounds

**Hierarchy:** resume brief → tabs Watchlists / Screens / Briefs / Notes / Alerts → selected record → save state. Saved screen remembers filter/sort/columns/formulas and original/latest preference. Notes attach to plan-option and revision. Lists can be named/reordered; duplicate addition is harmless.

**Desktop:** left record list with main content preview; notebook sections and a dated activity timeline. **Mobile:** list-first, detail is a separate page with Back; bottom sheet for create/rename, text editing full screen. Always show Saved/Unsaved status.

**Actions:** create/rename/archive/restore list/brief; add fund; restore view; attach evidence; compare changes after refresh; export brief or screen; define alert; inspect active event. Alert rule has metric, threshold/unit/direction, scope, evaluation cadence, last-evaluated revision and event history. New screen-entrant or disclosure-change alerts are separately specified rule types, not current endpoints.

**Current:** no MF workspace endpoints exist. Momentum25's conflict-safe document pattern can be reused after MF tenant-scoped services are built. Browser localStorage is not the durable MF source of truth. **Future:** M6 persistence, alert scheduler/evaluator/event/outbox; E1/E4 change feeds, Slice 5 research memory.

**Accept:** restart retains saved records; two windows editing one brief trigger merge/conflict; failed save preserves draft and is not marked saved; alert is “Active” only after service registration; no event duplicated for same rule/revision. Export includes source/method/revision and optional personal content only when requested. No CAS-derived data in public links.

## 09 · Multilingual research — the workstation speaks

**Complete-vision design; Slice 5 dependency.** Primary command entry on every MF page; context panel knows selected funds, window, filters and revision. Full research page lets chat and evidence workspace sit side by side. This is a tool-operating research surface rather than an isolated chat bubble.

**Desktop:** conversation 40%, editable evidence 60%; tool trace collapsed but visible. **Mobile:** conversation then an “Open research view” card; expanded evidence becomes a full screen with Back to conversation. Language choice English / हिन्दी / Hinglish persists; no flag icons.

**Actions:** “Explain this fall”, “Compare these”, “What changed?”, “Suggest an allocation”, refine, inspect cited metric, edit proposed filters, open resulting view, save brief, stop/retry. Personal recommendations use deterministic ranking/allocation services and constraints. Tool output is authoritative; model wording may vary. Raw CAS files are never model inputs. Portfolio tools require Slice 6 boundaries; external model egress is not enabled by the UI.

**States:** model unavailable → explain/retry and conventional controls; insufficient data → named dependencies; ambiguous amount/category → one targeted clarification; tool failure → preserve earlier verified results; validation failure → reviewed template fallback; permission denied → no leaked input. Before a saved-research write, preview concrete change; read-only tool navigation can run immediately. Show the research action, not invented confidence percentages.

**Accept:** every number/entity/date has a cited tool result; no partial unvalidated financial claim appears during streaming; language keeps numeric units and fund identity intact; zero hallucinated citations in fixed English/Hindi/Hinglish suite; stop stops new tool requests; saved brief records exact shown answer, tools, template and model/prompt versions. The same command opens the same underlying view spec. No fake chat responses before runtime ships.

## 10 · Mobile research loop — continuity in one hand

The mobile-focused artboard set shows Discover plus search/filter overlay and fund-risk continuation. Other M01–M09 artboards specify their full mobile layout. Main shell destinations and overflow match [01](01-strategy-and-ia.md); Portfolio replaces Workspace in the primary bottom slot only after launch. Search is always reachable at the top; Ask can be a full-width command, not a floating button covering charts.

**Actions:** search → exact result → Risk → pinned tooltip → add comparison → More/Compare → save brief. Thumb actions stay above safe area. Bottom sheet has heading, close button, focus trap, Escape/back dismissal and returns focus. Apply and Cancel have distinct effects. Browser Back restores prior tab/scroll/filter draft rules.

**Accept:** at 320, 390, 768, 1024 and 1440 CSS px no page-level horizontal overflow; chart/table regions may scroll with labels and keyboard access. At 200% zoom single-column reflow remains readable. Virtual keyboard leaves input and submit visible. Touch and keyboard can pin chart tooltip and read its data. Sticky header/tray/nav never cover the final row or validation error. No action requires hover or a precision drag.

## Detailed state artboards

- `S01-screen-empty.svg`: zero matches and returned relaxations; loading/error/missing distinctions.
- `S02-score-evidence.svg`: exact current score decomposition, sources, caveats and missing-data detail.
- `S03-cas-review.svg`: future encrypted-CAS preview, unresolved/duplicate states, commit disabled before reconciliation.

- `S04-studio-visuals.svg`: frontier scatter, quartile-transition matrix and monthly return heatmap, all explicitly schematic.
- `S05-portfolio-overview.svg`: post-import desktop portfolio, look-through, unknown exposures, dated overlap and allocation scenario.
- `S06-mobile-portfolio.svg`: post-import mobile portfolio with the same exposure and uncertainty hierarchy.

These complement the twenty main artboards and the full state matrices above. Their figures are verified reference values or non-numeric field labels; none implies a running portfolio/agent service.
