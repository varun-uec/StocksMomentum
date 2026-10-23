# Design artefact validation · 23 October 2026

This validates the planning package, not an implemented Wickstreet frontend.

| Check | Result |
|---|---|
| Main screen/device selections | 20/20 loaded: ten experiences × desktop/mobile |
| SVG render and XML parse | 30/30 valid and rendered: 20 main, 6 detail states, contact sheet, 3 flows |
| Text outside artboard bounds | None in the 29 individual artboards/flows; contact sheet uses nested view boxes |
| Gallery keyboard activation | Screen selection through focus + Enter passed |
| Gallery device/notes/hash controls | Passed; selected device, direct hash links, image decode and show/hide notes |
| Gallery responsive page width | No page-level overflow at 320, 390, 768, 1024, 1440 px |
| Automated gallery accessibility | No axe WCAG 2 A/AA and WCAG 2.1 A/AA violations in inspected states |
| External requests by gallery | Zero; all artwork, scripts, fonts and links used for rendering are local/system |
| Markdown links | All relative file targets resolve |
| Generator syntax | Python AST parse and Node syntax check passed |
| Live research contracts | 28/28 representative calls returned 200; snapshot 2801, method v5 |
| Repository boundary | Only new files under `docs/plans/wickstreet-2/ui-ux/`; application code unchanged |

Visual review: inspected the full contact sheet plus enlarged fund, screener, agent, score-evidence, frontier/matrices, desktop/mobile portfolio and navigation views. Corrected mobile destination highlights, matrix header alignment and a screener example whose sample rows initially did not match its selected preset. Final Screen example uses active Direct Growth flexi-cap funds with positive 3Y CAGR; both displayed reference rows meet those conditions. Their figures come from the inspected snapshot.

Screenshots: [desktop gallery](gallery-desktop.png), [mobile gallery](gallery-mobile.png). Machine-readable result: [artifact-checks.json](artifact-checks.json). Endpoint call observations: [endpoint-observations.md](endpoint-observations.md). Rendered individual previews were kept in `/tmp/wickstreet-wireframe-previews/`, not added as redundant repository assets.

Reproduce from repository root:

```sh
python3 docs/plans/wickstreet-2/ui-ux/render_wireframes.py
node docs/plans/wickstreet-2/ui-ux/validate-artifacts.cjs
```

The validator uses the repository's installed Playwright and axe-core. It reads local files, launches installed headless Chromium and writes documentation screenshots/results. On macOS a sandboxed launch may need the normal execution permission because Chromium's bootstrap port is restricted. It does not call Wickstreet APIs, access accounts or seed/migrate databases.

Limitations: no application code was implemented or tested; no authenticated competitor audit, real-participant usability study, real-device screen-reader test, delivered-product performance measurement or agent-language evaluation occurred. The corresponding release gates and measurement protocol are specified in documents 03, 05 and 06. Chart curves/matrix intensities and portfolio bar lengths remain labelled schematic; no performance or owned-portfolio claims are derived from them.
