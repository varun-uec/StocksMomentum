# Wickstreet transformation — 2026-10-19

Baseline: `b8a9a1b`, clean working tree. Existing audit and accepted architecture reviewed; no repeat compatibility audit or competitor source exposure. Local-only implementation. Synthetic PostgreSQL container `wickstreet-transform-tests`, port 55439; application database untouched, exchange downloads and scheduler disabled.

## Evidence gates

- Baseline full Playwright suite running, including the previously order-dependent 200% reflow regression.
- Before screenshots preserved under `audit-evidence/transformation/before/`.
- Design provenance: D17–D21 in the append-only design record.

## Increments

1. Charting foundation: shell, initial visible history windows, study legends, responsive geometry.
2. Workspace: stable grid cells, contextual drawing management, display-study configuration.
3. Monitoring: armed-alert editing, levels, history and bounded drawing snapshots (ADR amendment).
4. Product refinement and regression/performance evidence.

## Completed implementation / verification in progress

- Baseline 200% equivalent reflow, reduced motion and mobile keyboard navigation: 3/3 pass before UI changes. Full baseline reached150 passes; concurrent Playwright invocations shared its artifact directory, causing two ENOENT harness failures and one unrun test. This was an orchestration error; final full-suite runs are serial.
- Original drawing load/merge store unchanged. Traded-price conversion, per-drawing undo and conflict resolution retained.
- Chart-first shell, full-history preset windows, stable comparison anchors, chart legends, contextual study/object inspectors, stable grid cells and drawing rails implemented.
- Editable display RSI/MACD use separate keys; backend alert studies untouched. Indicator colour/visibility and drawing lock/visibility/dashes round-trip in server documents.
- Backend increments `f76ada7`, `677b41b`: revision-safe armed-alert edits, drawing snapshots, corporate-action-safe re-arm, stale drawing/data guards. 874 backend tests, strict mypy, Ruff and layer contracts pass.
- Web unit suite110 passes; lint/typecheck clean. Focused integrated browser pass16/18: remaining two were overly narrow date and first-save polling test assumptions, corrected. Accessibility axe checks pass on dashboard/chart/Studio in both themes.
- Screenshot measurements: desktop plot1076×676 (previous1068×600), y163 (previous198). Phone334×544, y215 (previous319×544, y345), no document overflow. Grid headers subsequently consolidated into one row.
- Full regression suite running serially on a fresh synthetic database. No publication, exchange download or real-data mutation.

## Review hardening

- Preserved pane0 across price-series replacement, including charts with no quick MAs and only an oscillator; stopped independently rebasing price-study overlays on percentage axes.
- Draft notes/tools/selections clear when the symbol changes. Historical viewport survives same-symbol refreshes. Colour updates reach existing pane series.
- Shared drawing rail now applies to research charts too; side-panel tabs use roving keyboard focus; dialog list IDs are unique; larger touch controls and truthful mobile panel state added.
- Added cached-symbol annotation, pane lifetime, touch drawing/panel and global-command-search journeys.
- Full-suite iteration found research-drawing discovery regression (fixed by shared rails), an initial-navigation-save race in a concurrency test (now waits for a confirmed base), and an ambiguous alert-status selector (now named). Final production-build run follows these corrections.
- Manual native Chrome200% zoom exercised; automated equivalent reflow and theme axe checks remain in regression coverage.

## Final experience checks

-30-run grid benchmark passed:16-chart warm P95 1,348ms, fresh-context P95 1,377ms; pan P5 61fps. Final source receives an additional focused production-build pass after responsive geometry refinement.
- Replaced single-chart fixed height assumptions with measured header/toolbar geometry and bottom-navigation clearance; touch tests assert the plot's bottom edge too.
- Added context-menu arrow/Home/End focus coverage, retained focus through style changes, and ensured hidden drawings cannot remain selected for keyboard moves.
- Stale alert edits refresh both alert revisions and price schedules; other-symbol alerts link directly back to their charts.

## Workstation plan, Phase A — 2026-10-20

Local commits on `wickstreet/m10-m11`, none pushed: `b3baee1` phase breakdown; `ac8a0ec` A1 baseline and ledger; `8fab319` A2.1 shell; `08b0229` A2.2 panel in the shell; `980215b` A2.3 header toolbar; `e2d21ba` A2.4 adaptive folding; `ba7182f` A3.1 rail portal gate; `06e8b65` A3.2 chrome slots; `537657c` A3.3 overlay legend; `30fe23b` A3.4 range bar and bare cells; `9fdcd15` A4.1 grouped rail; `c7c9717` A4.2 Object tree; `35883c9` A5–A8b Momentum25 integration, surfaces and journeys; then the A9 evidence and docs commit.

- End of A4: full serial suite 174 passed, 6 skipped (opt-in benchmarks), 0 failed.
- After A5–A8b: 191 passed, 6 skipped, 0 failed.
- A9.3 final run: 190 passed, 2 failed, both from one 390 px overflow in the strategy picker's new one-row layout. Fixed by wrapping below 1024 px; both specs then passed. The repeat full serial run on `1a9a945`: 192 passed, 6 skipped, 0 failed.
- NFR-11: warm P95 166 ms, cold P95 474 ms (limits 1 s, 3 s). `M13_BENCH`: 16 charts warm P95 1,288 ms, pan P5 61 fps; the A3.1 portal gate measured 1,338 ms.
- Backend: one additive enum value (`right_panel: "objects"`); user-documents API tests 34/34; Ruff and strict mypy clean on the touched files. Web: 124 unit tests, zero-warning lint, typecheck and build pass.
- Screenshots under `audit-evidence/` stay uncommitted, as for every earlier run.

## Phase B visual sign-off continuation — 2026-10-20

Resumed from Claude's `a5cb551` and `.dashboard/index.html`, steps 3–8 of `phase-b-signoff`. B5 remains deferred by the owner; Phase C is not started.

- `fea198b`: exact E2ECANDLE fixture-isolation regression; importing the fixture generator no longer invokes its CLI. Daily screening/ranks, live RS, breadth and point-in-time equity outputs are identical before/after insertion. No production calculations changed.
- `1ed0dd8`: screenshot review found a real interval-loading viewport race. Displayed bars now retain their actual interval until the requested data arrives. A delayed weekly response regression checks the full visible year. Same-interval refresh behavior is retained.
- Focused browser checks:16/16. Backend:921 tests; strict mypy263 source files; both import contracts; touched-test Ruff. Web:141 unit tests; lint and TypeScript clean.
- Final full production-build run on `1ed0dd8`:227 passed,0 failed,0 skipped in20.5minutes, including all six opt-in benchmarks and two representative capture journeys. All26routes×2themes×4viewports, 200% equivalent reflow, axe, touch, keyboard, persistence and recovery checks pass.
- NFR-11:30warm/30fresh-API-cold runs, P95 166ms/505ms. Isolated6/6 benchmark repeat:16charts warm1361ms/cold1383ms, pan P5 61fps, heapmax85MB. The standalone warm result is +5.7% versus Phase A1288ms, within10%; the full-suite1483ms sample is retained too.
- Refreshed standalone sign-off HTML and PDF:28 embedded synthetic screenshots,26 inspected PDF pages, no missing glyphs or clipped text. General test-generated PNG changes are restored. Local preview:127.0.0.1:8772, synthetic database only, scheduler/downloads disabled.
- The local `.dashboard/index.html` is updated at each gate. Evidence and sign-off documents are committed separately. B5 remains deferred, Phase C not started, nothing pushed.
