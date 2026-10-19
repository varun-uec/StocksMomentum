# OpenChart Parity Audit: Clean-Room Record

**Date:** 2026-10-19 · **Branch:** `wickstreet/m10-m11` · **Rule:** [ADD A1 §1a](docs/architecture/ADD-amendment-A1.md) and the [design record](docs/architecture/design-record.md).

This record lists every OpenChart source the audit used, what each one showed, and where each Wickstreet change in this audit came from. The [design record](docs/architecture/design-record.md) has matching entries X7–X8 and D10–D16.

## 1. What we did not do

- We did not read, clone or download OpenChart source code, components, CSS, bundled assets or internal APIs.
- We did not use browser developer tools on any OpenChart page.
- We did not copy OpenChart logos, icons, artwork or visual design.
- We did not install or run the OpenChart desktop app. It is a native download (macOS and Windows). No web instance exists: `chart.chat` returns HTTP 301 to `openchart.co`. Installing a third-party binary on the owner's machine needs the owner's consent, so the audit stayed with public documentation. Every OpenChart behaviour in this audit is therefore **documentation-only**.

"OpenChart" here means OpenChart by Longsurf AI (`github.com/longsurf-ai/openchart`, `openchart.co`). It does not mean other projects with similar names.

## 2. Sources used

| ID | Date | URL | What it gave | Kind |
|---|---|---|---|---|
| R1 | 2026-10-19 | github.com/longsurf-ai/openchart (README section only) | Capability claims: indicators, Volume Profile, 4×4 grid, line and zone drawings, price, indicator and drawing alerts, agents, Tea, desktop app, licence summary | Public README |
| R2 | 2026-10-19 | openchart.co/docs/ | Docs index; capability summary; "coming soon" list | Public docs |
| R3 | 2026-10-19 | openchart.co/docs/getting-started/ | Install, Settings → Models / Data Providers / Permissions, runtime caveat | Public docs |
| R4 | 2026-10-19 | openchart.co/docs/alerts/ | Alert kinds (prices, patterns, drawings, indicators), sidebar creation and editing, Feed, runtime limits | Public docs |
| R5 | 2026-10-19 | openchart.co/docs/data-providers/ | Binance, yfinance, OpenChart Cloud (provisional $9/month), data caveats | Public docs |
| R6 | 2026-10-19 | openchart.co/docs/select-and-explain/ | "Chart explain" range selection sent to an agent | Public docs |
| R7 | 2026-10-19 | openchart.co (home page) | Product claims; named indicators and drawing tools; drawing context-menu items; alert Once/Repeat and Enabled; screenshot structure (layout only) | Public marketing page |
| R8 | 2026-10-19 | openchart.co/changelog/ | Releases 0.1.5–0.1.7: sidebar alerts, drawing alerts on channels, Fibonacci, curves and freehand paths, sortable sidebar lists, Feed | Public changelog |
| R9 | 2026-10-19 | chart.chat | HTTP 301 to openchart.co. No separate product. | Redirect |

Not read: the Tea language page. Tea is excluded from scope ([ADD A1 §4](docs/architecture/ADD-amendment-A1.md), design record D8).

Earlier exposure (design record X1–X6, 2026-10-18): the OpenChart README and `LICENSE`, the getting-started page, the TradingView Charting Library shortcut docs, the owner's everyday TradingView use, and the Lightweight Charts™ licence files.

## 3. Confidence scale

| Level | Meaning |
|---|---|
| Documented | A docs page or the README states the behaviour in words. |
| Illustrated | A product image on the home page shows it. It may be a demo, not a shipped feature. |
| Coming soon | The docs navigation lists it as not yet available. |
| Unverified | No public evidence. The audit makes no claim. |

## 4. Wickstreet changes in this audit and their origin

Every fix came from a Wickstreet defect seen in the Wickstreet browser session. None came from OpenChart material. No fix copies an OpenChart design.

| Fix | Wickstreet defect | Origin of the design |
|---|---|---|
| D1 | Range presets counted back from today, so stale stored data gave an empty 1W and 1M chart | Own: a range is a slice of the stored bars, counted back from the last bar |
| D2 | Moving averages used only the bars in the range, so MA200 on a 1Y chart drew 10 bars | Own: the chart passes up to 199 earlier stored closes as warm-up, through the existing `sma` |
| D3 | RSI added from the indicator dialog showed twice in the readout, and its pane-row checkbox could not turn it off | Own: one definition per pane id; the pane row removes the dialog entry it duplicates |
| D4 | The crosshair readout covered the price-axis labels | Own: the readout sits top-left, where no axis is |
| D5 | Alt+I, Alt+W, `?` and type-to-search did nothing after a click on a checkbox | Own: only text-entry controls count as typing |
| D6 | A double-click with a two-point tool saved a zero-length line | Own: a click within the handle radius of the last anchor is the second half of a double-click and is ignored |
| D8 | Grid cells without their own symbol followed the active chart, even with symbol sync off | Own: a layout gives each new cell the active chart's symbol |
| D9 | A synced crosshair readout stayed after a dialog opened over the hovered chart | Own: the follower clears its readout when it clears its crosshair |
| D10 | Enter in indicator search did nothing | Own: Enter adds the first match, as Wickstreet's symbol search already does |
| D11 | A drawing placed while the symbol's drawings loaded was dropped | Own: ADR-013 §5 three-way merge, applied to edits made during the load |

## 5. Rules for the backlog

The [gap backlog](OPENCHART_GAP_BACKLOG.md) names capabilities that OpenChart documents. An item there is a capability gap, not an instruction to copy. Any build must start from Wickstreet's own requirements and its own design, and must add a design-record entry before any code.
