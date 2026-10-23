# Inspection record · 23 October 2026

## Repository and scope

Working tree was clean before the initial build request. On the later planning-only instruction, the three newly created, untracked application files were removed. The final intended diff is restricted to this `ui-ux/` directory. No existing frontend, backend, accepted methodology or Momentum25 behaviour is changed.

Read sources: `CLAUDE.md`, `CONTRIBUTING.md`; plans 01, 03, 06, 08, 18, 20, 21, 22; current `architecture.md`, `design.md`, `mf-metrics.md`; ADR-022 and ADR-023 including U1–U13; frontend `main.tsx`, root/shell/nav, providers, globals, package and Vite/Playwright config, `server-document.ts`; backend `apphost/main.py`, MF app, research HTTP/application and screening/formula/preset/backtest domain code. No applicable `AGENTS.md` was found in the workspace/ancestor inspection.

Scope precedence: owner-accepted doc 20 governs complete personal MF scope; doc 21 analytics, method v5 and later ADR updates supersede stale restrictions/examples in older plans. Current Slice 4 is research UI plus personal workspace; future Slice 5/6 services remain required within 2.0. E2 is already built; E1/E3–E7 remain dependencies in the inspected docs.

Stack: React 18, TypeScript strict, Vite 7, React Router 7, React Query 5, Recharts 3, Lightweight Charts 5, bundled Inter. Existing app is a code-split Momentum25 workstation with server-persisted documents, conflict handling, responsive shell and extensive Playwright suites. Existing `/studio` is Momentum25 research. Current `gen:api` exports only the Momentum25 OpenAPI. MF host mounts `/api/v1/mf` ahead of the existing app.

## Live reference

Local service `http://127.0.0.1:8000/api/v1/mf` read through loopback. No database writes, data import, settings updates or real portfolio records were used. POST calls were deterministic research screens/backtests/simulations. Single response timings are smoke observations under concurrent requests, not performance benchmarks.

- Revision 2801; method v5; data through 22 October 2026; sources AMFI, RBI, TigZig.
- Registry 160 fields, six presets. Full field metadata/coverage recorded in the companion catalogue; raw historical data is not committed.
- AMFI 122639, Parag Parikh Flexi Cap Fund – Direct Plan – Growth: 2,470 valid NAVs, first stored valid NAV 17 October 2016, last 22 October 2026. Not an inception claim.
- 1Y return −5.693386%; 3Y CAGR 12.178021%; 5Y CAGR 10.585327%; 10Y CAGR 16.505708%.
- 3Y volatility 9.923142%; worst 3Y drawdown −10.977288%; current drawdown −6.645283%, 360 days below peak. 3Y peak 27 October 2025; trough 30 March 2026; not recovered at snapshot.
- Score 97.777778/100, category score rank 1 of 31; consistency 100%. Score is equal-weight percentile average of consistency_3y, ret_risk_3y and mdd_3y. Sharpe 3Y 0.596853; not a score part.
- 3Y rolling series 1,731 observations. Historical rank series 108 month ends. Flexi-cap direct-growth frontier 36 points. Rolling 3Y SIP 84 start months; negative outcomes exist even though 3Y rolling lump-sum returns were all positive for this reference fund. Never equate the two.
- Risk-free series 529 observations. Fund confidence response has source-range objects rather than the normal string source list. Confidence notes identify current-category historical application and stopped-fund inclusion limits.
- Lumpsum simulation returned a summary with an empty timeline. The planned view handles that explicitly.

Reference UI rounds for display only. No diagram uses real personal financial information. Curves in the wireframes are labelled schematic, never presented as calculated returns. A ₹10,000 amount in a form is an editable scenario input, not an outcome claim.

## Competitor and tooling limits

Public pages and official Tickertape documentation reviewed through web search/open; source links and confidence in [competitive plan](../06-competitive-and-validation.md). No browser surface was available through CUA. No authentication/Pro/mobile walk-through or timed competitor task was performed.

The tldraw skill was read. Its boards are hosted and edits sync immediately. The user's local-only direction takes precedence, so no board was created. Local SVGs and editable Mermaid source supply inspectable diagrams. No third-party design assets or new dependencies were added. Headless browser use, when available, is only for validating these local documentation artefacts under the user's request for visual deliverables; it does not operate user accounts.
