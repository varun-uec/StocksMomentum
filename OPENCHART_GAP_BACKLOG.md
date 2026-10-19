# OpenChart Parity Gap Backlog

**Date:** 2026-10-19 · **Source:** the [parity matrix](OPENCHART_WICKSTREET_PARITY_MATRIX.md), [interaction](OPENCHART_INTERACTION_PARITY.md) and [UX](OPENCHART_UX_VISUAL_AUDIT.md) reports.

Rank = user impact × how often users meet it, then lower effort and lower regression risk first. Nothing here is authorised by this audit. Items marked **Decision** need an owner or ADR decision before work starts. Every item must keep the clean-room rule: build from Wickstreet's own requirement, and add a design-record entry first.

Effort: S ≤ 1 day, M ≤ 1 week, L more. Risk: regression risk to existing behaviour.

## Done in this audit

| ID | Fix | Regression test |
|---|---|---|
| D1 | Range presets count back from the last stored bar | `useChartShell.test.ts` (`rangeStartIndex`), `openchart-parity.spec.ts` |
| D2 | Moving averages warm up on earlier stored closes | `openchart-parity.spec.ts` (MA200 has a value on 1W) |
| D3 | One definition per pane; the pane row removes a duplicate dialog study | `openchart-parity.spec.ts` |
| D4 | Crosshair readout moved off the price axis | `openchart-parity.spec.ts` |
| D5 | Workspace keys work after a checkbox click | `openchart-parity.spec.ts` |
| D6 | Double-click no longer saves a zero-length drawing | `openchart-parity.spec.ts` |
| D8 | Layout cells keep their own symbol | `workspace.test.ts` (`withLayout`), `openchart-parity.spec.ts` |
| D9 | Synced readout clears with the crosshair | `openchart-parity.spec.ts` |
| D10 | Enter adds the first indicator match | `openchart-parity.spec.ts` |
| D11 | Edits made while a document loads are kept and merged | `server-document.test.ts`, `r2-stress-bench.spec.ts` |
| Fixture | The E2E seed screens a benchmark strategy too, so the legacy comparison has two runs on one date | `r2-adversarial.spec.ts` |
| Test isolation | The endurance test waits for the new symbol's bars; the 200% reflow test resets documents first | `r2-stress-bench.spec.ts`, `r2-accessibility.spec.ts` |

## P1: high impact, do next

| ID | Gap | Why it matters | Effort | Risk | Notes |
|---|---|---|---|---|---|
| BL-01 | Scroll back through all history; ranges as visible windows | Every chart user pans left. Today panning stops at the range start. | M | Medium | The full history now loads once per symbol (D1). Remaining work: give the chart all bars and set the visible range from the preset. Check compare's "% since" label, the analysis screen's pattern window, catalogue overlays' default anchors (Anchored VWAP, relative strength) and the 16-chart benchmark (M13_BENCH). |
| BL-02 | Drawing rail for the active grid cell | In 2×2 and larger layouts, drawing works only by shortcut. | S | Low | Reuse the single-chart rail; it acts on the active cell. |
| BL-03 | Legend on the chart for dialog studies | Bollinger, EMA and other studies show no name or value on the chart; users cannot tell lines apart. | S | Low | The legend data already exists (`OverlayPicker` "Legend · latest value"). Show it in the legend row above the price pane. |
| BL-07 | Edit an armed alert | Today a typo means delete and create again. OpenChart documents editing. | S–M | Low | Needs `PATCH /alerts/{id}` for armed alerts only; fired alerts stay immutable for history. |

## P2: completes a workflow

| ID | Gap | Effort | Risk | Notes |
|---|---|---|---|---|
| BL-04 | Per-study colour, and hide/show without removing | M | Low | Store `color` and `hidden` on `ActiveIndicator`; schema change in `ChartV1.indicators`. |
| BL-05 | Inline editor for text notes, in place of `window.prompt` | S | Low | The native prompt blocks the page and ignores the theme. |
| BL-06 | Show armed price alerts on the chart as dashed lines | S | Low | Read-only; drag-to-edit can follow BL-07. |
| BL-08 | Lock and hide drawings; dash style | S | Low | Booleans and a style field on the drawing; server schema change in `SymbolDrawingsV1`. |
| BL-09 | Alert history | S–M | Low | List fired events (date, value, threshold) in the Alerts tab. |
| BL-10 | Volume Profile | M | Low | Visible-range volume by price from daily bars; label it "from daily bars". Display only (NFR-1a). |
| BL-11 | RSI and MACD with editable periods | S–M | Low | Browser studies for display. Alerts keep the backend RSI(14) and MACD(12,26,9), so the alert source stays authoritative. |
| BL-12 | One percent-scale base for every series (D7) | M | Medium | Today each MA starts at 0% from its own first value. Compute MA and compare lines as % of the price's first visible close, or hide MAs on the % scale. |
| BL-13 | Sort the watchlist | S | Low | By symbol, change, rank. Manual order later. |
| BL-14 | Denser chart chrome on phones and in grids | M | Medium | Phone: controls use the top 41% of the screen. 4×4: about 50 of each cell's 180 px are header. Collapse controls into one row or a menu. Carried over from the Round 2 UX audit. |
| BL-15 | **Decision:** alerts attached to drawings | M–L | Medium | Capability gap only. A daily "close crosses this horizontal line" or "close leaves this rectangle" fits the M15 model. Sloped lines need the line's price on each evaluation date, and a drawing's price basis is traded prices (ADR-013 §5), so the evaluator must adjust them. Needs an ADR amendment before any code. |

## P3: later or only on request

| ID | Gap | Effort | Notes |
|---|---|---|---|
| BL-16 | Wedge, polyline, curve, freehand tools | S–M each | Low value for daily-bar analysis; polyline and freehand need variable point counts. |
| BL-17 | Squeeze Momentum study | S | Public definitions vary; define our own. |
| BL-18 | Repeat mode and pause for alerts | S | Today: one-shot and Re-arm. |
| BL-19 | Browser notification when a fired alert is first seen | M | No delivery outside the app (A1). |
| BL-20 | Resizable grid panels; named workspaces | M | Common convention; no OpenChart evidence. |
| BL-21 | Pattern alerts | L | Needs deterministic, point-in-time pattern events. Research first. |
| BL-22 | Market heat map | M | OpenChart shows one only inside an AI dashboard demo. |
| BL-23 | Quiet first-open 404s | S | A new symbol's drawings and the first workspace return 404, which the browser logs as a console error. This is a correct API response, so change it only with the document-API contract. |

## Proposals outside the agreed scope

These need a separate proposal with benefits, costs and architecture effects. This audit does not recommend them.

| Capability (OpenChart) | Wickstreet position |
|---|---|
| AI agents, Select and Explain, schedules, Copilot | Excluded (A1 §4, design record D8) |
| Tea or Pine-style scripting; user-defined strategy code | Excluded. Strategy Studio's registry-bounded configs are the alternative. |
| Intraday and real-time data | Excluded. Wickstreet is NSE end-of-day. |
| Broker connection, order proposals | Excluded |
| Hosted multi-tenant service | Excluded (ADR-010, ADR-012) |
