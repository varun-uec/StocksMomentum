# Wickstreet 2.0 · The research notebook

**UI/UX master plan · 23 October 2026 · Planning proposal for Slice 4 and the complete MF product.**

> **Status, 23 October 2026 (later):** the Slice 4 workstation is now built at `/mf`. Where this package says "unbuilt", read [08 · Slice 4 implementation](08-slice-4-implementation.md) for what shipped and what still depends on a service or dataset.

Start with [the visual gallery](wireframes/index.html). Open it in a browser; it is a local, self-contained design document. Choose any of ten experiences, inspect desktop and mobile artboards, and read its capability and interaction notes. The individual SVGs open in browsers and vector editors. [The overview contact sheet](wireframes/contact-sheet.svg) shows all twenty main artboards. Six additional artboards specify error, explanation, CAS review, analytical matrices and post-import portfolio states.

This package proposes the UI and its delivery sequence. It does not change accepted financial methodology, existing ADRs or application code. It records the inspected implementation, not a promise that future services already exist. All work stays local. No account, data import, hosted board, deployment or push is part of this delivery.

## Read in this order

| Deliverable | Contents |
|---|---|
| [01 · Product strategy and navigation](01-strategy-and-ia.md) | Personas, jobs, complete vision, routes, research context and responsive models |
| [02 · Design system](02-design-system.md) | Tokens, typography, components, chart grammar, accessibility, content and motion |
| [03 · Screen and interaction contracts](03-screen-contracts.md) | All ten desktop/mobile screens, actions, states, dependencies and acceptance criteria |
| [04 · Capability and API map](04-api-capability-map.md) | Every current research endpoint, contract differences from older plans, missing service contracts and data dependencies |
| [05 · Implementation milestones](05-slice-4-delivery-plan.md) | Independently deliverable milestones, tasks, dependencies, tests and exit evidence |
| [06 · Competitive baseline and evaluation](06-competitive-and-validation.md) | Screen-by-screen comparison, source confidence, parity gaps and a measurable usability study |
| [07 · Interaction flows](07-flows.md) | Local SVG diagrams plus editable Mermaid sources |
| [08 · Slice 4 implementation](08-slice-4-implementation.md) | What was built at `/mf`, the theme architecture, workspace persistence (W1), test evidence and the remaining dependencies |
| [Field catalogue](evidence/v5-field-catalogue.md) | All 160 registry fields, types, units, explanations and observed coverage |
| [Artefact validation](evidence/validation.md) | Browser, XML, accessibility, responsive and link checks; reproduction commands |
| [Inspection evidence](evidence/inspection.md) | Repository paths, live read observations and limits of this planning exercise |

## How to interpret the artboards

- **AVAILABLE API** means backend implemented and a live response observed where recorded. The proposed UI remains unbuilt.
- **CLIENT COMPOSITION** means the UI can arrange existing results without defining new financial methods.
- **PLANNED SERVICE / DATA** means a named backend or enrichment dependency must be delivered first. Do not ship an enabled control that only mimics completion.
- Reference figures for Parag Parikh Direct Growth are from the local v5 snapshot, revision 2801, as of 22 October 2026. They are frozen research examples. No portfolio records are used.
- Chart paths marked **schematic** show visual structure, not historical fund observations. Planned portfolio, tax and recommendation results have labels instead of invented values.
- The gallery navigates design artefacts. Its device, screen and note controls work; fund actions drawn inside the SVGs describe future interactions. This is a wireframe set, not an application prototype.

## Decisions made in this package

Use a distinct `/mf` route family for MF work while `/`, `/chart` and every Momentum25 route retain their current meaning. Use six visible destinations—Discover, Screen, Studio, Compare, Simulate, Workspace—with Portfolio promoted when its service ships. Fund research is a contextual destination. **Decide** is a saved research brief across those views, not a seventh competing navigation system. The agent has a prominent command entry and a shared context panel; it is central to the complete vision and never required to operate the conventional tools.

Use server-owned, tenant-scoped MF research persistence. Reuse the existing document-store interaction pattern, not Momentum25's storage endpoints or tenant identity. Browser state holds only non-sensitive transient view preferences. Portfolio records, CAS passwords and agent transcripts never go in URL parameters, repository files or analytics events.

## Completion boundary

The blueprint covers all requested experiences, future dependencies, twenty main artboards in ten desktop/mobile pairs, six detailed state artboards, three navigation/interaction diagrams and delivery/acceptance plans. No usability session with people, authenticated competitor walkthrough or production UI test has occurred. Competitive superiority is a measurable hypothesis, not an established result. The validation report records artefact checks separately from the future application acceptance suite.
